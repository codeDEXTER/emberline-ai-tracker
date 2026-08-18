"""`bin/land` refuses to land from a project that is behind on common-rules.

Measured 2026-08-18: three adopting projects (`mac-explorer`, `pockets`,
`pip`) were 27, 30 and 51 versions behind, and all three already had
`rulecheck --quiet` installed as a `SessionStart` hook -- so the signal was
firing every session and nothing consumed it, because a hook's exit status
does not stop the session. `land` is the point that actually merges work, so
it is the right place to make the signal load-bearing instead of ignorable.

This mirrors `test_land_requires_a_test.py`'s harness: a throwaway repo with
a `main` branch and one feature branch, driven through `land --check` so
nothing is actually pushed.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAND = ROOT / "bin" / "land"
RULECHECK = ROOT / "bin" / "rulecheck"
STAMP = ".common-rules-version"

REFUSAL = "not aligned with common-rules"


def current_rules_version() -> str:
    """The version `land` will compute, from the same `bin/rulecheck` it calls.

    Not hardcoded: this worktree's own HEAD moves as commits land on it, and
    a hardcoded version would drift out from under the test the same way the
    thing under test is designed to catch drift.
    """
    out = subprocess.run([str(RULECHECK), "--version"], capture_output=True,
                         text=True, check=True)
    return out.stdout.strip()


class LandHarness(unittest.TestCase):
    """A throwaway repo with a main branch and one feature branch."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "proj"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.repo / "README.md").write_text("seed\n")
        self.git("add", "-A"); self.git("commit", "-qm", "seed")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a],
                              capture_output=True, text=True, check=False)

    def stamp_main(self, version: str):
        """Write and commit a stamp to `main`, as `rulecheck --align` would."""
        self.git("checkout", "-q", "main")
        (self.repo / STAMP).write_text(version + "\n")
        self.git("add", "-A"); self.git("commit", "-qm", "align with common-rules")

    def branch(self, name, files: dict):
        self.git("checkout", "-q", "-b", name)
        for rel, body in files.items():
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
        self.git("add", "-A"); self.git("commit", "-qm", f"work on {name}")

    def land(self, env=None):
        e = dict(os.environ); e.update(env or {})
        return subprocess.run([str(LAND), "--check"], cwd=str(self.repo),
                              capture_output=True, text=True, check=False, env=e)


class TestNoStampMeansNoGate(LandHarness):

    def test_a_project_with_no_stamp_is_never_blocked_on_alignment(self):
        """Never opted in, so never checked -- pointing at CLAUDE-workflow.md
        in prose alone is not the same as running `rulecheck --align`."""
        self.branch("docs", {"NOTE.md": "seed\nmore words\n"})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)


class TestAlignedProjectLands(LandHarness):

    def test_a_stamp_matching_current_is_not_blocked(self):
        self.stamp_main(current_rules_version())
        self.branch("docs", {"NOTE.md": "seed\nmore words\n"})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)


class TestStaleProjectIsRefused(LandHarness):

    def test_a_stale_stamp_is_refused_and_says_both_versions(self):
        self.stamp_main("1-0000000")
        self.branch("docs", {"NOTE.md": "seed\nmore words\n"})
        out = self.land()
        combined = out.stdout + out.stderr
        self.assertIn(REFUSAL, combined)
        self.assertIn("1-0000000", combined, "must name the project's current version")
        self.assertIn(current_rules_version(), combined, "must name the current version")
        self.assertNotIn("READY", out.stdout)

    def test_the_fix_commands_are_actionable(self):
        """The refusal must say what to run, including the gotcha that
        --align writes the stamp but does not commit it."""
        self.stamp_main("1-0000000")
        self.branch("docs", {"NOTE.md": "seed\nmore words\n"})
        out = self.land()
        combined = out.stdout + out.stderr
        self.assertIn("rulecheck --align", combined)
        self.assertIn("does NOT commit it", combined)
        self.assertIn("git commit", combined)

    def test_the_override_exists_and_is_explicit(self):
        """Same shape as LAND_ALLOW_UNTESTED -- an env var someone had to
        type, never a silent default."""
        self.stamp_main("1-0000000")
        self.branch("docs", {"NOTE.md": "seed\nmore words\n"})
        blocked = self.land()
        self.assertIn(REFUSAL, blocked.stdout + blocked.stderr)
        allowed = self.land(env={"LAND_ALLOW_STALE_RULES": "1"})
        self.assertNotIn(REFUSAL, allowed.stdout + allowed.stderr)


if __name__ == "__main__":
    unittest.main()
