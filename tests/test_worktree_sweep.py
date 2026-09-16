"""bin/worktree-sweep -- remove finished worktrees (WT-01).

Fixture shape: a bare `origin.git`, a `main` clone of it (the project under
test), and worktrees added off that clone's branches. `gh` and `claude` are
never called for real here -- every test passes an injectable runner (or
lets the module's own "command unavailable" path fire, since neither
binary is assumed present in the test environment) so results never depend
on what happens to be installed or logged in on the machine running the
suite.

Run:  python3 -m unittest discover -s tests -p 'test_worktree_sweep.py' -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWEEP_PATH = ROOT / "bin" / "worktree-sweep"

spec = importlib.util.spec_from_loader("worktree_sweep", loader=None, origin=str(SWEEP_PATH))
WS = importlib.util.module_from_spec(spec)
sys.modules["worktree_sweep"] = WS
exec(compile(SWEEP_PATH.read_text(), str(SWEEP_PATH), "exec"), WS.__dict__)


def git(cwd, *args, check=True):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"git {args} failed: {r.stderr}")
    return r


def no_gh(cmd):
    raise AssertionError(f"gh must never be called for real in tests: {cmd}")


def no_claude(cmd):
    raise AssertionError(f"claude must never be called for real in tests: {cmd}")


def empty_gh(cmd):
    """Stands in for `gh pr list ...` reporting no merged PR -- used as the
    default so a worktree with an unmerged commit exercises the real
    (negative) gh lookup path without ever shelling out to the real gh."""
    return subprocess.CompletedProcess(cmd, 0, "[]", "")


def empty_claude(cmd):
    """Stands in for `claude agents --json --all` reporting no sessions."""
    return subprocess.CompletedProcess(cmd, 0, "[]", "")


class SweepFixture(unittest.TestCase):
    """A bare origin, a `main` clone (the project), and helpers to add
    worktrees off it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.origin = root / "origin.git"
        git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))

        self.project = root / "main"
        git(root, "clone", "-q", str(self.origin), str(self.project))
        git(self.project, "config", "user.email", "t@example.com")
        git(self.project, "config", "user.name", "t")
        (self.project / "f.txt").write_text("one\n")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "one")
        git(self.project, "push", "-q", "origin", "main")

        self.worktrees_dir = root / "worktrees"
        self.worktrees_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def add_worktree(self, name, branch=None, detach=False):
        path = self.worktrees_dir / name
        branch = branch or name
        if detach:
            git(self.project, "worktree", "add", "--detach", str(path), "main")
        else:
            git(self.project, "worktree", "add", "-b", branch, str(path), "main")
        git(path, "config", "user.email", "t@example.com")
        git(path, "config", "user.name", "t")
        return path

    def sweep(self, idle_hours=2, apply=False, gh_runner=None, claude_runner=None, lsof_runner=None):
        gh_runner = gh_runner or empty_gh
        claude_runner = claude_runner or empty_claude
        lsof_runner = lsof_runner or (lambda cmd: subprocess.CompletedProcess(cmd, 0, "", ""))
        rows, fetch_ok, pruned = WS.sweep(str(self.project), idle_hours,
                                           gh_runner=gh_runner, claude_runner=claude_runner,
                                           lsof_runner=lsof_runner)
        return rows, fetch_ok, pruned

    def row_for(self, rows, path):
        for r in rows:
            if str(Path(r["path"]).resolve()) == str(Path(path).resolve()):
                return r
        raise AssertionError(f"no row for {path} in {rows}")

    def backdate(self, path, hours):
        """Push every tracked/untracked file's mtime, and the worktree's own
        HEAD/index under its private git-dir, back by `hours` -- git itself
        just wrote HEAD/index moments ago when the worktree was added, so
        without this every fixture worktree reads as freshly active no
        matter what the test is trying to simulate."""
        old = time.time() - hours * 3600
        for root, dirs, files in os.walk(path):
            if ".git" in dirs:
                dirs.remove(".git")
            for f in files:
                os.utime(os.path.join(root, f), (old, old))
        git_dir = git(path, "rev-parse", "--git-dir").stdout.strip()
        git_dir_path = Path(git_dir)
        if not git_dir_path.is_absolute():
            git_dir_path = Path(path) / git_dir_path
        for name in ("HEAD", "index"):
            fp = git_dir_path / name
            if fp.exists():
                os.utime(fp, (old, old))


class TestCleanAncestorMerged(SweepFixture):
    def test_removable(self):
        """Clean, and its branch is exactly main -- an ancestor -- so it
        qualifies with nothing committed beyond origin/main."""
        path = self.add_worktree("clean-merged")
        self.backdate(path, 3)  # so the idle check passes without a real sleep
        rows, fetch_ok, _ = self.sweep(idle_hours=2)
        self.assertTrue(fetch_ok)
        row = self.row_for(rows, path)
        self.assertEqual("REMOVABLE", row["verdict"], row)


class TestDirty(SweepFixture):
    def test_kept(self):
        path = self.add_worktree("dirty")
        (path / "untracked.txt").write_text("scratch\n")
        rows, _, _ = self.sweep()
        row = self.row_for(rows, path)
        self.assertEqual("KEEP", row["verdict"])
        self.assertIn("dirty", row["reason"])


class TestUnmergedCommits(SweepFixture):
    def test_kept(self):
        path = self.add_worktree("unmerged")
        (path / "new.txt").write_text("work\n")
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", "real work, never pushed")
        rows, _, _ = self.sweep()
        row = self.row_for(rows, path)
        self.assertEqual("KEEP", row["verdict"])
        self.assertIn("not merged", row["reason"])


class TestSquashMerged(SweepFixture):
    def test_removable_via_cherry(self):
        """Simulates a squash merge: the branch's commit never becomes an
        ancestor of origin/main, but the same patch lands there under a
        different commit -- `git cherry` is what has to catch this."""
        path = self.add_worktree("squashed", branch="squashed")
        (path / "squash.txt").write_text("payload\n")
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", "feature work")

        # Apply the same patch to main directly (what a squash-merge PR does),
        # then push -- so origin/main advances with an unrelated commit that
        # carries the identical diff.
        git(self.project, "checkout", "-q", "main")
        (self.project / "squash.txt").write_text("payload\n")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "squash-merge #1 (squashed)")
        git(self.project, "push", "-q", "origin", "main")

        self.backdate(path, 3)
        rows, _, _ = self.sweep(idle_hours=2, gh_runner=lambda cmd: subprocess.CompletedProcess(cmd, 1, "", "no gh"))
        row = self.row_for(rows, path)
        self.assertEqual("REMOVABLE", row["verdict"], row)
        self.assertIn("squash", row["reason"])


class TestRecentMtimeKeepsIt(SweepFixture):
    def test_kept(self):
        path = self.add_worktree("recent")
        # Clean AND merged (nothing beyond origin/main) -- but never
        # backdated, so newest_mtime reads "now" and the idle check alone
        # must be what keeps it.
        rows, _, _ = self.sweep(idle_hours=2)
        row = self.row_for(rows, path)
        self.assertEqual("KEEP", row["verdict"])
        self.assertIn("active", row["reason"])
        self.assertIn("modified", row["reason"])


class TestGhMergedPr(SweepFixture):
    def test_removable_when_gh_reports_merged(self):
        path = self.add_worktree("pr-merged", branch="pr-merged")
        (path / "x.txt").write_text("x\n")
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", "work behind a merged PR")
        self.backdate(path, 3)

        def fake_gh(cmd):
            self.assertIn("pr-merged", cmd)
            return subprocess.CompletedProcess(cmd, 0, json.dumps([{"number": 42}]), "")

        rows, _, _ = self.sweep(idle_hours=2, gh_runner=fake_gh)
        row = self.row_for(rows, path)
        self.assertEqual("REMOVABLE", row["verdict"], row)

    def test_gh_error_never_guesses_merged(self):
        path = self.add_worktree("pr-unknown", branch="pr-unknown")
        (path / "x.txt").write_text("x\n")
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", "work, gh errors on lookup")
        self.backdate(path, 3)

        def erroring_gh(cmd):
            return subprocess.CompletedProcess(cmd, 1, "", "rate limited")

        rows, _, _ = self.sweep(idle_hours=2, gh_runner=erroring_gh)
        row = self.row_for(rows, path)
        self.assertEqual("KEEP", row["verdict"])


class TestClaudeSessionKeepsItActive(SweepFixture):
    def test_kept_when_claude_session_cwd_inside(self):
        path = self.add_worktree("live-session")
        self.backdate(path, 3)

        def fake_claude(cmd):
            payload = json.dumps([{"cwd": str(path), "state": "running"}])
            return subprocess.CompletedProcess(cmd, 0, payload, "")

        rows, _, _ = self.sweep(idle_hours=2, claude_runner=fake_claude)
        row = self.row_for(rows, path)
        self.assertEqual("KEEP", row["verdict"])
        self.assertIn("claude", row["reason"])

    def test_done_session_does_not_keep_it(self):
        path = self.add_worktree("done-session")
        self.backdate(path, 3)

        def fake_claude(cmd):
            payload = json.dumps([{"cwd": str(path), "state": "done"}])
            return subprocess.CompletedProcess(cmd, 0, payload, "")

        rows, _, _ = self.sweep(idle_hours=2, claude_runner=fake_claude)
        row = self.row_for(rows, path)
        self.assertEqual("REMOVABLE", row["verdict"], row)


class TestLsofBusyKeepsIt(SweepFixture):
    def test_kept_when_process_cwd_inside(self):
        path = self.add_worktree("busy-process")
        self.backdate(path, 3)

        def fake_lsof(cmd):
            return subprocess.CompletedProcess(cmd, 0, f"n{path}\n", "")

        rows, _, _ = self.sweep(idle_hours=2, lsof_runner=fake_lsof)
        row = self.row_for(rows, path)
        self.assertEqual("KEEP", row["verdict"])
        self.assertIn("process", row["reason"])


class TestDetachedHead(SweepFixture):
    def test_removable_detached_at_main(self):
        path = self.add_worktree("detached", detach=True)
        self.backdate(path, 3)
        rows, _, _ = self.sweep(idle_hours=2)
        row = self.row_for(rows, path)
        self.assertEqual("REMOVABLE", row["verdict"], row)
        self.assertTrue(row["detached"])


class TestApplyRemovesOnlyRemovable(SweepFixture):
    def test_apply(self):
        removable_path = self.add_worktree("to-remove")
        self.backdate(removable_path, 3)

        keep_path = self.add_worktree("to-keep")
        (keep_path / "scratch.txt").write_text("uncommitted\n")

        rows, fetch_ok, _ = self.sweep(idle_hours=2)
        self.assertTrue(fetch_ok)
        removed, failures = WS.apply_removals(str(self.project), rows)
        self.assertEqual([], failures)
        self.assertEqual(1, removed)

        self.assertFalse(removable_path.exists())
        self.assertTrue(keep_path.exists())

        branches = git(self.project, "branch", "--list").stdout
        self.assertNotIn("to-remove", branches)
        self.assertIn("to-keep", branches)

    def test_main_checkout_is_never_a_row(self):
        rows, _, _ = self.sweep()
        for row in rows:
            self.assertNotEqual(str(Path(row["path"]).resolve()), str(self.project.resolve()))


class TestDryRunRemovesNothing(SweepFixture):
    def test_dry_run_touches_nothing(self):
        path = self.add_worktree("would-be-removed")
        self.backdate(path, 3)
        rows, _, _ = self.sweep(idle_hours=2)
        row = self.row_for(rows, path)
        self.assertEqual("REMOVABLE", row["verdict"])
        # sweep() itself never calls apply_removals -- the worktree is
        # still on disk and its branch still exists.
        self.assertTrue(path.exists())
        branches = git(self.project, "branch", "--list").stdout
        self.assertIn("would-be-removed", branches)


class TestPruneReportsGoneDirectories(SweepFixture):
    def test_prune_lists_missing_worktree(self):
        path = self.add_worktree("goes-missing")
        # Remove the directory by hand, bypassing `git worktree remove`, so
        # git's administrative entry is left dangling -- exactly what
        # `worktree prune` exists to clean up.
        import shutil as _sh
        _sh.rmtree(path)
        rows, _, pruned = self.sweep()
        self.assertTrue(any("goes-missing" in line for line in pruned))
        # And it must not appear as a worktree row at all -- its directory
        # is already gone, nothing to remove there.
        for row in rows:
            self.assertNotIn("goes-missing", row["path"])


class TestFetchFailureRefusesApply(SweepFixture):
    def test_apply_refused_without_origin(self):
        # Point "origin" at a URL that cannot be fetched.
        git(self.project, "remote", "set-url", "origin", "/nonexistent/origin.git")
        rc = WS.main(["--project", str(self.project), "--apply"])
        self.assertEqual(2, rc)


class TestCLIDryRunAlwaysExitsZero(SweepFixture):
    def test_cli_dry_run(self):
        path = self.add_worktree("cli-check")
        (path / "scratch.txt").write_text("uncommitted\n")
        rc = WS.main(["--project", str(self.project), "--idle-hours", "2"])
        self.assertEqual(0, rc)
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
