"""bin/handover -- the four checks an item lead runs before ending a turn
(proposal 24, H-01).

Each check is exercised on a broken fixture first (shown failing), then on
the same fixture fixed (shown passing) -- never the reverse, so a check
that always prints PASS regardless of the fixture would still be caught.

Run:  python3 -m unittest discover -s tests -p 'test_handover.py' -v
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HANDOVER = ROOT / "bin" / "handover"


def _load_handover():
    import importlib.machinery
    loader = importlib.machinery.SourceFileLoader("handover", str(HANDOVER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


H = _load_handover()


def git(*args, cwd):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git("init", "-q", "-b", "main", cwd=root)
    git("config", "user.email", "test@example.com", cwd=root)
    git("config", "user.name", "test", cwd=root)
    (root / "README.md").write_text("fixture\n")
    git("add", "-A", cwd=root)
    git("commit", "-q", "-m", "initial", cwd=root)


def write_ledger(root: Path, name: str, data: dict) -> Path:
    p = root / "docs" / "proposals" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return p


def base_ledger(**over) -> dict:
    d = {
        "proposal": 90, "title": "fixture", "status": "accepted", "updated": "2026-01-01",
        "phases": [{"id": "W", "name": "build"}],
        "items": [{"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "in progress", "log": []}],
        "asks": [],
    }
    d.update(over)
    return d


class CheckAsksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        init_repo(self.root)

    def write_transcript(self, entries: list[dict]) -> Path:
        p = self.root / "transcript.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        return p

    def user_entry(self, text: str, at: str, sidechain=False) -> dict:
        return {"type": "user", "isSidechain": sidechain, "timestamp": at,
                "message": {"role": "user", "content": [{"type": "text", "text": text}]}}

    def tool_result_entry(self, at: str) -> dict:
        return {"type": "user", "timestamp": at,
                "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}

    def test_no_transcript_is_skipped_not_failed(self):
        write_ledger(self.root, "90-fixture.json", base_ledger())
        mark, _ = H.check_asks(self.root, None, None)
        self.assertEqual(H.SKIP, mark)

    def test_sponsor_message_with_no_ask_row_fails(self):
        """Broken fixture: a real sponsor message, no ask row anywhere."""
        write_ledger(self.root, "90-fixture.json", base_ledger(asks=[]))
        t = self.write_transcript([
            self.user_entry("please rename the widget to gadget", "2026-01-01T10:00:00+00:00"),
        ])
        mark, detail = H.check_asks(self.root, t, None)
        self.assertEqual(H.FAIL, mark, detail)
        self.assertIn("widget", detail)

    def test_sponsor_message_with_ask_row_passes(self):
        """Same fixture, fixed: the ask row now exists, quoting the message."""
        write_ledger(self.root, "90-fixture.json", base_ledger(asks=[
            {"id": "A-01", "at": "2026-01-01T10:00:00+00:00", "by": "sponsor", "kind": "instruction",
             "quote": "please rename the widget to gadget", "state": "open", "became": None},
        ]))
        t = self.write_transcript([
            self.user_entry("please rename the widget to gadget", "2026-01-01T10:00:00+00:00"),
        ])
        mark, detail = H.check_asks(self.root, t, None)
        self.assertEqual(H.PASS, mark, detail)

    def test_tool_results_and_sidechain_and_wrappers_are_not_sponsor_messages(self):
        write_ledger(self.root, "90-fixture.json", base_ledger(asks=[]))
        t = self.write_transcript([
            self.tool_result_entry("2026-01-01T10:00:00+00:00"),
            self.user_entry("<system-reminder>ignore me</system-reminder>", "2026-01-01T10:01:00+00:00"),
            self.user_entry("<task-notification>ignore too</task-notification>", "2026-01-01T10:02:00+00:00"),
            self.user_entry("real message", "2026-01-01T10:03:00+00:00", sidechain=True),
        ])
        mark, detail = H.check_asks(self.root, t, None)
        self.assertEqual(H.PASS, mark, detail)

    def test_since_filters_earlier_messages(self):
        write_ledger(self.root, "90-fixture.json", base_ledger(asks=[]))
        t = self.write_transcript([
            self.user_entry("old message before the window", "2026-01-01T00:00:00+00:00"),
        ])
        mark, detail = H.check_asks(self.root, t, datetime(2026, 1, 1, 9, tzinfo=timezone.utc))
        self.assertEqual(H.PASS, mark, detail)


class CheckWorktreesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "proj"
        init_repo(self.root)

    def add_active_worktree(self, name: str) -> None:
        wt = self.root / ".claude" / "worktrees" / name
        wt.parent.mkdir(parents=True, exist_ok=True)
        git("worktree", "add", "-q", "-b", f"agent-{name}", str(wt), cwd=self.root)
        (wt / "change.txt").write_text("hi\n")
        git("add", "-A", cwd=wt)
        git("commit", "-q", "-m", "agent work", cwd=wt)

    def test_no_active_worktree_is_skipped(self):
        write_ledger(self.root, "90-fixture.json", base_ledger())
        mark, _ = H.check_worktrees(self.root)
        self.assertEqual(H.SKIP, mark)

    def test_active_worktree_with_no_ledger_evidence_fails(self):
        """Broken fixture: agent worktree has commits, no ledger names it."""
        write_ledger(self.root, "90-fixture.json", base_ledger())
        self.add_active_worktree("p90-w01")
        mark, detail = H.check_worktrees(self.root)
        self.assertEqual(H.FAIL, mark, detail)
        self.assertIn("p90-w01", detail)

    def test_active_worktree_named_in_ledger_log_passes(self):
        """Same fixture, fixed: an item's log entry names the worktree."""
        write_ledger(self.root, "90-fixture.json", base_ledger(items=[
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "in progress", "log": [
                {"at": "2026-01-01T10:00:00+00:00", "by": "subagent sonnet, worktree",
                 "event": "started", "evidence": "worktree .claude/worktrees/p90-w01 from main"},
            ]},
        ]))
        self.add_active_worktree("p90-w01")
        mark, detail = H.check_worktrees(self.root)
        self.assertEqual(H.PASS, mark, detail)

    def test_run_from_a_linked_worktree_still_sees_its_sibling(self):
        """Regression (bundle-d review, HIGH): the reviewer found check 2
        blind when `--project` is a linked worktree, not the main checkout
        -- `git worktree list` reports every worktree's path relative to the
        main checkout's `.claude/worktrees/`, and the old code only ever
        looked under `--project` itself, so a lead running `bin/handover
        --check` from its own worktree (the item-lead form's own
        instruction) saw 0 candidates. Two linked worktrees here, ledger
        names neither: --project set to worktree A must still report
        worktree B (its unnamed sibling) as a failing candidate."""
        write_ledger(self.root, "90-fixture.json", base_ledger())
        git("add", "-A", cwd=self.root)
        git("commit", "-q", "-m", "add ledger", cwd=self.root)
        self.add_active_worktree("p90-a")
        self.add_active_worktree("p90-b")
        project_a = self.root / ".claude" / "worktrees" / "p90-a"
        mark, detail = H.check_worktrees(project_a)
        self.assertEqual(H.FAIL, mark, detail)
        self.assertIn("p90-b", detail)


class CheckCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        init_repo(self.root)

    def test_no_open_ledger_is_not_needed(self):
        write_ledger(self.root, "90-fixture.json", base_ledger(items=[
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "done", "log": []},
        ]))
        mark, _ = H.check_checkpoint(self.root)
        self.assertEqual(H.SKIP, mark)

    def test_open_ledger_no_checkpoint_fails(self):
        """Broken fixture: an open ledger, no checkpoint on disk at all."""
        write_ledger(self.root, "90-fixture.json", base_ledger())
        mark, detail = H.check_checkpoint(self.root)
        self.assertEqual(H.FAIL, mark, detail)

    def test_stale_checkpoint_fails(self):
        lp = write_ledger(self.root, "90-fixture.json", base_ledger())
        cp = self.root / "docs" / "handovers" / "2026-01-01-checkpoint.md"
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text("# Checkpoint\n<!-- ledger-digest: " + "0" * 64 + " -->\n")
        mark, detail = H.check_checkpoint(self.root)
        self.assertEqual(H.FAIL, mark, detail)

    def test_matching_checkpoint_passes(self):
        """Same fixture, fixed: checkpoint carries the ledger's real digest."""
        from tools.tracker import checkpoint as CP
        lp = write_ledger(self.root, "90-fixture.json", base_ledger())
        digest = CP.digest_of([lp])
        cp = self.root / "docs" / "handovers" / "2026-01-01-checkpoint.md"
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(f"# Checkpoint\n<!-- ledger-digest: {digest} -->\n")
        mark, detail = H.check_checkpoint(self.root)
        self.assertEqual(H.PASS, mark, detail)


class CheckWarmupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        init_repo(self.root)

    def stub(self, exit_code: int) -> Path:
        p = Path(self.tmp.name) / f"stub_warmup_{exit_code}.py"
        p.write_text(f"#!/usr/bin/env python3\nimport sys\nprint('stub problem' if {exit_code} else 'ok')\n"
                      f"sys.exit({exit_code})\n")
        return p

    def test_failing_warmup_check_fails(self):
        """Broken fixture: the (stubbed) warmup --check exits non-zero."""
        import os
        old = os.environ.get("HANDOVER_WARMUP_BIN")
        os.environ["HANDOVER_WARMUP_BIN"] = str(self.stub(1))
        try:
            mark, detail = H.check_warmup(self.root)
        finally:
            if old is None:
                os.environ.pop("HANDOVER_WARMUP_BIN", None)
            else:
                os.environ["HANDOVER_WARMUP_BIN"] = old
        self.assertEqual(H.FAIL, mark, detail)

    def test_passing_warmup_check_passes(self):
        """Same fixture, fixed: the (stubbed) warmup --check exits 0."""
        import os
        old = os.environ.get("HANDOVER_WARMUP_BIN")
        os.environ["HANDOVER_WARMUP_BIN"] = str(self.stub(0))
        try:
            mark, detail = H.check_warmup(self.root)
        finally:
            if old is None:
                os.environ.pop("HANDOVER_WARMUP_BIN", None)
            else:
                os.environ["HANDOVER_WARMUP_BIN"] = old
        self.assertEqual(H.PASS, mark, detail)

    def test_real_warmup_on_this_project_passes(self):
        """Integration: the real bin/warmup, run against common-rules itself
        (this worktree), which is expected to already pass --check."""
        mark, detail = H.check_warmup(ROOT)
        self.assertEqual(H.PASS, mark, detail)


class MainCLITests(unittest.TestCase):
    """The whole binary, via subprocess -- exit code follows the checks."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        init_repo(self.root)

    def stub(self, exit_code: int) -> Path:
        p = Path(self.tmp.name) / "stub_warmup.py"
        p.write_text(f"#!/usr/bin/env python3\nimport sys\nsys.exit({exit_code})\n")
        return p

    def run_handover(self, *args, warmup_exit=0):
        import os
        env = dict(os.environ, HANDOVER_WARMUP_BIN=str(self.stub(warmup_exit)))
        return subprocess.run([sys.executable, str(HANDOVER), "--check", "--project", str(self.root), *args],
                              capture_output=True, text=True, env=env)

    def test_broken_project_exits_1(self):
        """Broken fixture: an open ledger, no checkpoint -- exit 1."""
        write_ledger(self.root, "90-fixture.json", base_ledger())
        r = self.run_handover()
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("not ready", r.stdout)

    def test_fixed_project_exits_0(self):
        """Same fixture, fixed: ledger closed, nothing else outstanding."""
        write_ledger(self.root, "90-fixture.json", base_ledger(items=[
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "done", "log": []},
        ]))
        r = self.run_handover()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("handover --check: ready", r.stdout)


if __name__ == "__main__":
    unittest.main()
