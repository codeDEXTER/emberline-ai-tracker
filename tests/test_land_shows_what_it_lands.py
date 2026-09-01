"""`land` must name the commits it is about to land, not just count them.

Why: a branch cut from a local `main` that was ahead of `origin` carries the
unpushed commits too, and a squash merge collapses them under this branch's
title. On 2026-08-07 a PR described as a one-line docs change landed 25 files
and 1,109 insertions of another session's work — and published a real corpus
identifier doing it. It happened twice, because nothing showed the operator
what the branch actually held.

Printing the subjects is the cheapest possible guard: if a line is not yours,
you see it before the merge rather than after.

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


class TestLandShowsItsCommits(unittest.TestCase):

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

    def land(self):
        e = dict(os.environ); e["LAND_ALLOW_UNTESTED"] = "1"
        r = subprocess.run([str(LAND), "--check"], cwd=str(self.repo),
                           capture_output=True, text=True, check=False, env=e)
        return r.stdout + r.stderr

    def commit(self, name, subject):
        (self.repo / name).write_text("x\n")
        self.git("add", "-A"); self.git("commit", "-qm", subject)

    def test_the_subject_of_each_commit_is_printed(self):
        self.git("checkout", "-q", "-b", "feat")
        self.commit("a.md", "the change I meant to make")
        self.assertIn("the change I meant to make", self.land())

    def test_a_commit_that_is_not_mine_is_visible_before_the_merge(self):
        """The regression this exists for: a branch carrying someone else's
        work must show it, not hide it behind a count."""
        self.git("checkout", "-q", "-b", "feat")
        self.commit("other.md", "another session's unpushed work")
        self.commit("mine.md", "my one-line docs change")
        out = self.land()
        self.assertIn("another session's unpushed work", out,
                      "a foreign commit rode along and land never said so")
        self.assertIn("my one-line docs change", out)

    def test_a_long_branch_says_how_many_it_did_not_print(self):
        """Truncation must announce itself — a silent cut is how a backlog
        got under-reported by a third earlier in this project's history."""
        self.git("checkout", "-q", "-b", "feat")
        for i in range(15):
            self.commit(f"f{i}.md", f"commit number {i}")
        out = self.land()
        self.assertIn("and 3 more", out, "15 commits, 12 shown, 3 unannounced")


if __name__ == "__main__":
    unittest.main()
