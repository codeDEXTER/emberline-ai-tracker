"""Tests for bin/worklog-nightly (common-rules proposal 27, W-03).

The correctness property that matters: a session (via the Stop hook's fast,
best-effort `worklog.collect()`) never commits `worklog/` itself -- only
this, separate, non-interactive script does, and it commits at most once
per calendar day however many times it runs that day.

`tools.worklog.collect` itself is monkeypatched throughout -- these tests
are about the commit-once-per-day mechanism around it, not about collect's
own transcript reading (covered by tests/test_worklog.py), and patching it
out keeps every test here fast and independent of this machine's real
`~/.agent-data/projects` transcripts.

Run:  python3 -m unittest discover -s tests -p 'test_worklog_nightly.py' -v
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin" / "worklog-nightly"


def load_nightly():
    loader = importlib.machinery.SourceFileLoader("worklog_nightly", str(BIN))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                           capture_output=True, text=True)


def commit_count(repo) -> int:
    r = subprocess.run(["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
                        capture_output=True, text=True, check=False)
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else 0


class NightlyHarness(unittest.TestCase):

    def setUp(self):
        self.N = load_nightly()
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "README.md").write_text("scratch\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")
        self.out = self.repo / "worklog"
        self.out.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write_row(self, name="2026-09-01.jsonl", text='{"item": "Q-01"}\n'):
        """Simulate the fast Stop-hook collect having already written a day
        file -- untracked, as it always is until the nightly commit."""
        (self.out / name).write_text(text)

    def patched_collect(self, **_kw):
        """A stand-in for `worklog.collect()` that does nothing further --
        the day files this test writes directly are what `run()` should
        find and commit."""
        return {"days": [], "lines": 0, "transcripts": 0, "unpriced_models": []}


class TestCommitsOncePerDay(NightlyHarness):

    def test_commits_new_worklog_content(self):
        self.write_row()
        with mock.patch.object(self.N.worklog, "collect", side_effect=self.patched_collect):
            result = self.N.run(repo=self.repo, out=self.out, date="2026-09-01")
        self.assertTrue(result["committed"], result)
        self.assertEqual(2, commit_count(self.repo))  # setUp's "init" + this
        log = git(self.repo, "log", "-1", "--format=%s").stdout.strip()
        self.assertIn("2026-09-01", log)

    def test_second_run_same_day_does_not_recommit(self):
        self.write_row()
        with mock.patch.object(self.N.worklog, "collect", side_effect=self.patched_collect):
            first = self.N.run(repo=self.repo, out=self.out, date="2026-09-01")
            self.assertTrue(first["committed"])
            before = commit_count(self.repo)

            # More content shows up (as if the Stop hook wrote more rows
            # later the same day) -- still no second commit for this date.
            self.write_row("2026-09-01.jsonl", '{"item": "Q-01"}\n{"item": "Q-02"}\n')
            second = self.N.run(repo=self.repo, out=self.out, date="2026-09-01")

        self.assertFalse(second["committed"], second)
        self.assertEqual(before, commit_count(self.repo))

    def test_running_many_times_same_day_commits_once(self):
        self.write_row()
        with mock.patch.object(self.N.worklog, "collect", side_effect=self.patched_collect):
            for _ in range(5):
                self.N.run(repo=self.repo, out=self.out, date="2026-09-01")
        self.assertEqual(2, commit_count(self.repo))  # setUp's "init" + exactly one

    def test_a_new_day_gets_its_own_commit(self):
        self.write_row("2026-09-01.jsonl")
        with mock.patch.object(self.N.worklog, "collect", side_effect=self.patched_collect):
            self.N.run(repo=self.repo, out=self.out, date="2026-09-01")
            self.write_row("2026-09-02.jsonl")
            second = self.N.run(repo=self.repo, out=self.out, date="2026-09-02")
        self.assertTrue(second["committed"], second)
        self.assertEqual(3, commit_count(self.repo))  # init + day 1 + day 2

    def test_nothing_new_commits_nothing(self):
        with mock.patch.object(self.N.worklog, "collect", side_effect=self.patched_collect):
            result = self.N.run(repo=self.repo, out=self.out, date="2026-09-01")
        self.assertFalse(result["committed"], result)
        self.assertEqual(1, commit_count(self.repo))  # unchanged from setUp's "init"

    def test_dry_run_never_commits(self):
        self.write_row()
        with mock.patch.object(self.N.worklog, "collect", side_effect=self.patched_collect):
            result = self.N.run(repo=self.repo, out=self.out, date="2026-09-01", dry_run=True)
        self.assertFalse(result["committed"], result)
        self.assertEqual(1, commit_count(self.repo))  # unchanged
        # State was not advanced either -- a real (non-dry-run) run for the
        # same date should still be free to commit.
        with mock.patch.object(self.N.worklog, "collect", side_effect=self.patched_collect):
            real = self.N.run(repo=self.repo, out=self.out, date="2026-09-01")
        self.assertTrue(real["committed"], real)
        self.assertEqual(2, commit_count(self.repo))


class TestSessionNeverCommits(NightlyHarness):
    """The other half of the correctness property: the Stop hook's fast
    collect (see hooks/stop's `_collect_worklog`) never runs any git
    command at all -- only this script does. Exercised here by confirming
    `hooks/stop` contains no git-commit machinery, and in tests/test_hooks.py
    by confirming a Stop hook run never advances the real repository's
    HEAD."""

    def test_hooks_stop_has_no_commit_logic(self):
        text = (ROOT / "hooks" / "stop").read_text()
        # A git *subcommand* argument is always a quoted literal in this
        # codebase's subprocess calls (see `_rules_moved_line`'s own
        # `"rev-parse"`) -- so `"commit"` or `"add"` appearing as one is
        # the actual signal, not the English word turning up in a comment.
        self.assertNotIn('"commit"', text)
        self.assertNotIn("'commit'", text)


if __name__ == "__main__":
    unittest.main()
