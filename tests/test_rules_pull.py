"""tools/rules_pull.check_and_pull -- fast-forwarding a shared rules checkout
(proposal 28, R-05).

Every case here runs against temp clones only -- never the real
/Users/the-sponsor/apps/common-rules checkout's git state, per the bundle's own
MUST: no fetch or pull on it, ever, from a test.

Run:  python3 -m unittest discover -s tests -p 'test_rules_pull.py' -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import rules_pull as RP  # noqa: E402


def git(cwd: Path, *args: str):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)


class PairedRepos(unittest.TestCase):
    """An `origin` bare repo and a `local` clone of it -- both temp, both
    thrown away in tearDown."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.origin = root / "origin.git"
        self.local = root / "local"
        git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))

        seed = root / "seed"
        git(root, "init", "-q", "-b", "main", str(seed))
        git(seed, "config", "user.email", "t@example.com")
        git(seed, "config", "user.name", "t")
        (seed / "f.txt").write_text("one\n")
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", "one")
        git(seed, "remote", "add", "origin", str(self.origin))
        git(seed, "push", "-q", "origin", "main")

        git(root, "clone", "-q", str(self.origin), str(self.local))
        git(self.local, "config", "user.email", "t@example.com")
        git(self.local, "config", "user.name", "t")
        self.seed = seed

    def tearDown(self):
        self.tmp.cleanup()

    def advance_origin(self):
        """Push a second commit to `origin` via the seed clone, so `local`
        is behind."""
        (self.seed / "f.txt").write_text("two\n")
        git(self.seed, "add", "-A")
        git(self.seed, "commit", "-q", "-m", "two")
        git(self.seed, "push", "-q", "origin", "main")


class TestBehindAndClean(PairedRepos):

    def test_fast_forwards(self):
        self.advance_origin()
        before = git(self.local, "rev-parse", "HEAD").stdout.strip()
        line = RP.check_and_pull(self.local, no_pull=False)
        self.assertIn("fast-forwarded", line, line)
        after = git(self.local, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(before, after)
        self.assertEqual(after, git(self.seed, "rev-parse", "HEAD").stdout.strip())

    def test_already_up_to_date_is_a_no_op(self):
        line = RP.check_and_pull(self.local, no_pull=False)
        self.assertIn("up to date", line, line)


class TestNoPull(PairedRepos):

    def test_no_pull_flag_skips_everything(self):
        self.advance_origin()
        before = git(self.local, "rev-parse", "HEAD").stdout.strip()
        line = RP.check_and_pull(self.local, no_pull=True)
        self.assertIn("skipped", line)
        after = git(self.local, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(before, after)


class TestDirtyIsLeftAlone(PairedRepos):

    def test_tracked_change_blocks_the_pull(self):
        self.advance_origin()
        (self.local / "f.txt").write_text("dirty\n")
        before = git(self.local, "rev-parse", "HEAD").stdout.strip()
        line = RP.check_and_pull(self.local, no_pull=False)
        self.assertIn("tracked changes", line, line)
        after = git(self.local, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(before, after)


class TestDivergedIsLeftAlone(PairedRepos):

    def test_local_commit_not_on_origin_blocks_the_pull(self):
        self.advance_origin()
        (self.local / "g.txt").write_text("local only\n")
        git(self.local, "add", "-A")
        git(self.local, "commit", "-q", "-m", "diverge")
        before = git(self.local, "rev-parse", "HEAD").stdout.strip()
        line = RP.check_and_pull(self.local, no_pull=False)
        self.assertIn("diverged", line, line)
        after = git(self.local, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(before, after)


class TestNotOnMainIsLeftAlone(PairedRepos):

    def test_other_branch_blocks_the_pull(self):
        self.advance_origin()
        git(self.local, "checkout", "-q", "-b", "other")
        before = git(self.local, "rev-parse", "HEAD").stdout.strip()
        line = RP.check_and_pull(self.local, no_pull=False)
        self.assertIn("not on main", line, line)
        self.assertIn("other", line)
        after = git(self.local, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(before, after)


class TestFetchFailureIsNamed(unittest.TestCase):

    def test_no_origin_remote_is_named_not_a_crash(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            repo = Path(tmp.name) / "solo"
            git(Path(tmp.name), "init", "-q", "-b", "main", str(repo))
            git(repo, "config", "user.email", "t@example.com")
            git(repo, "config", "user.name", "t")
            (repo / "f.txt").write_text("one\n")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "one")
            line = RP.check_and_pull(repo, no_pull=False)
            self.assertIn("not pulled", line, line)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
