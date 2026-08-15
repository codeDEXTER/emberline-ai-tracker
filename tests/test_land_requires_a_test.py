"""A branch that changes code and no test does not land.

Why this exists, measured 2026-08-10: **29% of every Bash call a session makes
is a one-off verification probe** — an inline script that proves something and
then dies with the session. 3,873 of them in the transcripts, against 106 from
the eight agent roles combined. The verification is already being done and
already being written; it is simply thrown away afterwards.

So this guard does not ask anyone to test more. It asks the probe that was
already written to land in `tests/` rather than in a chat message.

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

# The exact refusal. Matching a loose "no test" also catches land's unrelated
# "no test suite found -- landing on the gate alone", which made the first
# draft of this file pass and fail for the wrong reasons.
REFUSAL = "changes code but no test"


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


class TestCodeNeedsATest(LandHarness):

    def test_code_without_a_test_is_refused(self):
        self.branch("feat", {"app.py": "def f():\n    return 1\n"})
        out = self.land()
        self.assertIn(REFUSAL, out.stdout + out.stderr,
                      "a code-only branch should not land")
        self.assertNotIn("READY", out.stdout)

    def test_code_with_a_test_proceeds(self):
        self.branch("feat", {
            "app.py": "def f():\n    return 1\n",
            "tests/test_app.py": "def test_f():\n    assert True\n",
        })
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)

    def test_a_docs_only_branch_is_never_asked_for_a_test(self):
        """The guard must not make documentation expensive."""
        self.branch("docs", {"README.md": "seed\nmore words\n",
                             "docs/note.html": "<p>hi</p>\n"})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)

    def test_a_script_under_bin_counts_as_code(self):
        """bin/ holds the tooling; it has no extension and is where the two
        worst silent defects of the week lived (spend, derecord)."""
        self.branch("tooling", {"bin/thing": "#!/bin/sh\necho hi\n"})
        out = self.land()
        self.assertIn(REFUSAL, out.stdout + out.stderr)

    def test_the_override_exists_and_is_explicit(self):
        """Some changes genuinely cannot be tested. The escape hatch must be
        deliberate — an env var someone had to type — not a silent default."""
        self.branch("feat", {"app.py": "def f():\n    return 1\n"})
        blocked = self.land()
        self.assertIn(REFUSAL, blocked.stdout + blocked.stderr)
        allowed = self.land(env={"LAND_ALLOW_UNTESTED": "1"})
        self.assertNotIn(REFUSAL, allowed.stdout + allowed.stderr)


if __name__ == "__main__":
    unittest.main()
