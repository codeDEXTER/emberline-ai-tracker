"""`bin/land` refuses to land a proposal that asked decisions and recorded none.

`bin/proposalcheck` landed in #106 (common-rules 156-8b1cce3) and exits 1 for
a project whose proposals asked numbered decisions and recorded no answers, or
which claim `completed in part` with no `id="exceptions"` block. Nothing
consumed that exit code -- `bin/land` was not modified alongside it -- so the
rule was advisory in every project it governs, the exact gap the alignment
gate (#105, `tests/test_land_alignment.py`) closed for `rulecheck` a day
earlier for the identical reason: a signal nothing acts on is not a rule.

This mirrors that file's harness: a throwaway repo with a `main` branch and
one feature branch, driven through `land --check` so nothing is actually
pushed. The stamp is always written at the current rules version here, so
every case in this file is isolated to the proposalcheck gate and never trips
the (separately tested) alignment gate.

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

REFUSAL = "record neither"

# proposalcheck's EFFECTIVE_DATE is 2026-08-19; anything decided on/after it
# is enforced, anything before (or undated) is grandfathered.
AFTER_FLOOR = "2026-08-20"


def current_rules_version() -> str:
    """Same rationale as test_land_alignment.py: asked, not hardcoded, so this
    file does not drift out from under the thing it is pinning."""
    out = subprocess.run([str(RULECHECK), "--version"], capture_output=True,
                         text=True, check=True)
    return out.stdout.strip()


def proposal_asking_unanswered_decisions() -> str:
    return (
        "<html><head>"
        '<meta name="proposal-id" content="01">'
        '<meta name="proposal-status" content="accepted">'
        f'<meta name="proposal-decided" content="{AFTER_FLOOR}">'
        "</head><body><h1>Test proposal</h1>"
        '<ol class="decisions"><li><b>D1.</b> Ship it or not.</li></ol>'
        "</body></html>"
    )


def proposal_with_answers() -> str:
    return (
        "<html><head>"
        '<meta name="proposal-id" content="01">'
        '<meta name="proposal-status" content="accepted">'
        f'<meta name="proposal-decided" content="{AFTER_FLOOR}">'
        "</head><body><h1>Test proposal</h1>"
        '<ol class="decisions"><li><b>D1.</b> Ship it or not.</li></ol>'
        '<div id="decided"><b>Decided.</b> D1: ship it.</div>'
        "</body></html>"
    )


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

    def test_a_project_with_no_stamp_is_never_blocked_on_proposals(self):
        """Never opted in to common-rules, so never checked -- same guard,
        same reasoning, as the alignment gate right above this one."""
        self.branch("docs", {
            "docs/proposals/01-x.html": proposal_asking_unanswered_decisions(),
        })
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)


class TestCompliantProjectLands(LandHarness):

    def test_answers_recorded_is_not_blocked(self):
        self.stamp_main(current_rules_version())
        self.branch("docs", {
            "docs/proposals/01-x.html": proposal_with_answers(),
        })
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)
        self.assertIn("READY", out.stdout)

    def test_no_proposals_directory_is_not_blocked(self):
        """proposalcheck exits 2 here -- 'nothing to check', not a failure --
        because the .common-rules-version guard already excludes projects
        that never adopted the rules; a proposal-less *adopting* project is
        an ordinary shape, not an error, and must not be confused with the
        exit 2 rulecheck uses for 'could not check at all'."""
        self.stamp_main(current_rules_version())
        self.branch("docs", {"NOTE.md": "seed\nmore words\n"})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)
        self.assertIn("READY", out.stdout)


class TestUnrecordedDecisionsAreRefused(LandHarness):

    def test_unanswered_decisions_are_refused_and_name_the_proposal(self):
        self.stamp_main(current_rules_version())
        self.branch("docs", {
            "docs/proposals/01-x.html": proposal_asking_unanswered_decisions(),
        })
        out = self.land()
        combined = out.stdout + out.stderr
        self.assertIn(REFUSAL, combined)
        self.assertIn("01-x.html", combined, "must name the offending proposal")
        self.assertNotIn("READY", out.stdout)

    def test_the_override_exists_and_is_explicit(self):
        """Same shape as LAND_ALLOW_UNTESTED and LAND_ALLOW_STALE_RULES -- an
        env var someone had to type, never a silent default."""
        self.stamp_main(current_rules_version())
        self.branch("docs", {
            "docs/proposals/01-x.html": proposal_asking_unanswered_decisions(),
        })
        blocked = self.land()
        self.assertIn(REFUSAL, blocked.stdout + blocked.stderr)
        allowed = self.land(env={"LAND_ALLOW_UNRECORDED_DECISIONS": "1"})
        self.assertNotIn(REFUSAL, allowed.stdout + allowed.stderr)
        self.assertIn("READY", allowed.stdout)


if __name__ == "__main__":
    unittest.main()
