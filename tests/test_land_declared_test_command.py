"""bin/land runs the test command a project declares (proposal 18 B, found in proposal 19's pilot).

land's test_cmd() used to guess from the tree: tests/*.py meant unittest,
package.json meant npm test. The PhotoVault engine's merge gate is pytest with
markers, so land -- and the warm card, which reports land's answer -- would run
the wrong gate there. A project now declares its gate in `.common-rules-test`
at its root, beside `.common-rules-version`: the first line that is neither
blank nor a comment. With no such line, land guesses as before.

These drive land itself, not the extracted function: the declared command
must be the one that runs, so `false` declared must refuse the landing.

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


class LandHarness(unittest.TestCase):

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
        return subprocess.run(["git", "-C", str(self.repo), *a], capture_output=True, text=True, check=False)

    def branch_declaring(self, declared: str):
        self.git("checkout", "-q", "-b", "work")
        (self.repo / ".common-rules-test").write_text(declared)
        (self.repo / "README.md").write_text("seed\nwork\n")
        self.git("add", "-A"); self.git("commit", "-qm", "declare the gate")

    def land(self):
        return subprocess.run([str(LAND), "--check"], cwd=str(self.repo), capture_output=True,
                              text=True, check=False, env=dict(os.environ))


class TestTheDeclaredCommandRuns(LandHarness):

    def test_a_failing_declared_gate_refuses(self):
        self.branch_declaring("# merge gate\nfalse\n")
        out = self.land()
        self.assertIn("running: false", out.stdout)
        self.assertIn("tests are not green", out.stdout + out.stderr)
        self.assertNotIn("READY", out.stdout)

    def test_a_passing_declared_gate_lands(self):
        self.branch_declaring("\n# merge gate\ntrue\n")
        out = self.land()
        self.assertIn("running: true", out.stdout)
        self.assertIn("READY", out.stdout)


if __name__ == "__main__":
    unittest.main()
