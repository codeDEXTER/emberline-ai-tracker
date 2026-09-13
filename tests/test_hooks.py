"""Stop, PreCompact and SessionStart hooks, and the checkpoint writer they
share (proposal 19, W-07 / D8). A compaction can only lose what lived
nowhere but the chat (proposal 19, section K) -- these hooks are the write
side: the checkpoint is written from the ledger, on disk, before the summary
is made, and a fresh session is pointed back at the ledger rather than the
summary it just lost context to.

Every hook is exercised the way Claude Code actually calls it: JSON on
stdin, subprocess, in a scratch project (its own git repo, its own
docs/proposals ledger) so nothing here ever touches a real project.

Run:  python3 -m unittest discover -s tests -p 'test_hooks.py' -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import checkpoint, ledger  # noqa: E402

HOOKS = ROOT / "hooks"
PRECOMPACT = HOOKS / "precompact"
STOP = HOOKS / "stop"
SESSIONSTART = HOOKS / "sessionstart"


def minimal(**over) -> dict:
    d = {
        "proposal": 19, "title": "Warm-up", "status": "accepted",
        "phases": [{"id": "W", "name": "build"}],
        "items": [
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "done",
             "tag": "[ruflo · medium · sonnet]",
             "log": [{"at": "2026-09-13T20:00:00+02:00", "event": "merged", "by": "lead", "evidence": "abc123"}]},
            {"id": "W-02", "phase": "W", "cx": "C3", "title": "render", "status": "in progress",
             "tag": "[ruflo · high · opus]", "depends": "W-01",
             "log": [{"at": "2026-09-13T21:00:00+02:00", "event": "started", "by": "lead", "evidence": "branch p19-x"}]},
            {"id": "W-03", "phase": "W", "cx": "C2", "title": "sync", "status": "blocked",
             "tag": "[ruflo · medium · sonnet]", "depends": ["W-01"],
             "log": [{"at": "2026-09-13T21:10:00+02:00", "event": "blocked", "by": "lead", "evidence": "needs gh token"}]},
            {"id": "W-04", "phase": "W", "cx": "C2", "title": "recall", "status": "not started",
             "tag": "[ruflo · medium · sonnet]", "depends": ["W-01"]},
        ],
        "asks": [{"id": "A-01", "at": "2026-09-13", "kind": "decision", "quote": "ruflo mandatory",
                  "became": None, "state": "open"}],
    }
    d.update(over)
    return d


def all_done() -> dict:
    d = minimal()
    for i in d["items"]:
        i["status"] = "done"
        i["log"] = [{"at": "2026-09-13T20:00:00+02:00", "event": "merged", "by": "lead", "evidence": "x"}]
    return d


class ScratchProject(unittest.TestCase):
    """A throwaway project: its own git repo, its own docs/proposals ledger.
    Nothing here ever writes outside `self.proj`."""

    LEDGER = minimal()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        (self.proj / "docs" / "proposals").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)
        subprocess.run(["git", "-C", str(self.proj), "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.proj), "config", "user.name", "t"], check=True)
        self.write_ledger(self.LEDGER)
        (self.proj / "README.md").write_text("scratch\n")
        subprocess.run(["git", "-C", str(self.proj), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.proj), "commit", "-q", "-m", "init"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write_ledger(self, data: dict):
        (self.proj / "docs" / "proposals" / "19-x.json").write_text(json.dumps(data))

    def checkpoint_path(self, date="2026-09-13") -> Path:
        found = list((self.proj / "docs" / "handovers").glob("*-checkpoint.md"))
        self.assertEqual(1, len(found), found)
        return found[0]

    def run_hook(self, hook: Path, payload: dict | None, cwd=None, raw_stdin: str | None = None):
        stdin = raw_stdin if raw_stdin is not None else json.dumps(payload or {})
        return subprocess.run([sys.executable, str(hook)], input=stdin, capture_output=True,
                              text=True, cwd=cwd, timeout=15, check=False)


class TestCheckpointContent(ScratchProject):

    def test_sections_in_order(self):
        rc = checkpoint.main(["--project", str(self.proj), "--reason", "manual"])
        self.assertEqual(0, rc)
        text = self.checkpoint_path().read_text()
        order = [
            "# Checkpoint —", "Reason: manual", "<!-- ledger-digest:",
            "## Proposal 19 · Warm-up", "### In progress", "### Blocked, and why",
            "### Open asks", "### Next unblocked", "## Exact next action",
        ]
        positions = [text.index(m) for m in order]
        self.assertEqual(positions, sorted(positions), text)
        self.assertIn("W-02", text)  # in progress
        self.assertIn("W-03", text)  # blocked
        self.assertIn("A-01", text)  # open ask
        self.assertIn("W-04", text)  # next unblocked
        self.assertIn("needs gh token", text)  # blocked item's last log evidence
        self.assertIn("started", text)  # in-progress item's last log event

    def test_nothing_written_when_all_items_done(self):
        self.write_ledger(all_done())
        rc = checkpoint.main(["--project", str(self.proj), "--reason", "manual"])
        self.assertEqual(0, rc)
        self.assertFalse((self.proj / "docs" / "handovers").exists())

    def test_if_changed_skips_an_unchanged_ledger(self):
        checkpoint.main(["--project", str(self.proj), "--reason", "stop", "--if-changed"])
        path = self.checkpoint_path()
        original = path.read_text()
        path.write_text(original + "\n<!-- marker: untouched -->\n")
        rc = checkpoint.main(["--project", str(self.proj), "--reason", "stop", "--if-changed"])
        self.assertEqual(0, rc)
        self.assertIn("marker: untouched", path.read_text())

    def test_if_changed_rewrites_a_changed_ledger(self):
        checkpoint.main(["--project", str(self.proj), "--reason", "stop", "--if-changed"])
        path = self.checkpoint_path()
        path.write_text(path.read_text() + "\n<!-- marker: stale -->\n")
        changed = minimal()
        changed["items"][3]["status"] = "in progress"
        changed["items"][3]["log"] = [{"at": "2026-09-13T22:00:00+02:00", "event": "started", "by": "lead", "evidence": "y"}]
        self.write_ledger(changed)
        rc = checkpoint.main(["--project", str(self.proj), "--reason", "stop", "--if-changed"])
        self.assertEqual(0, rc)
        self.assertNotIn("marker: stale", path.read_text())

    def test_outside_git_head_is_unknown(self):
        no_git = Path(tempfile.mkdtemp())
        (no_git / "docs" / "proposals").mkdir(parents=True)
        (no_git / "docs" / "proposals" / "19-x.json").write_text(json.dumps(minimal()))
        rc = checkpoint.main(["--project", str(no_git), "--reason", "manual"])
        self.assertEqual(0, rc)
        found = list((no_git / "docs" / "handovers").glob("*-checkpoint.md"))
        self.assertEqual(1, len(found))
        self.assertIn("HEAD unknown", found[0].read_text())


class TestPrecompactHook(ScratchProject):

    def test_writes_a_checkpoint(self):
        r = self.run_hook(PRECOMPACT, {"cwd": str(self.proj), "trigger": "auto"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())
        self.checkpoint_path()  # exists, asserts exactly one

    def test_malformed_stdin_and_missing_cwd_exit_zero(self):
        r = self.run_hook(PRECOMPACT, None, cwd=str(self.proj), raw_stdin="not json{{{")
        self.assertEqual(0, r.returncode, r.stderr)
        self.checkpoint_path()  # still ran, using cwd fallback


class TestStopHook(ScratchProject):

    def test_stop_hook_active_writes_nothing(self):
        r = self.run_hook(STOP, {"cwd": str(self.proj), "stop_hook_active": True})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertFalse((self.proj / "docs" / "handovers").exists())

    def test_stop_twice_writes_once(self):
        r1 = self.run_hook(STOP, {"cwd": str(self.proj)})
        self.assertEqual(0, r1.returncode, r1.stderr)
        path = self.checkpoint_path()
        path.write_text(path.read_text() + "\n<!-- marker: first-write-only -->\n")
        r2 = self.run_hook(STOP, {"cwd": str(self.proj)})
        self.assertEqual(0, r2.returncode, r2.stderr)
        self.assertIn("marker: first-write-only", path.read_text())

    def test_malformed_stdin_and_missing_cwd_exit_zero(self):
        r = self.run_hook(STOP, None, cwd=str(self.proj), raw_stdin="{not valid")
        self.assertEqual(0, r.returncode, r.stderr)
        self.checkpoint_path()


class TestSessionStartHook(ScratchProject):

    def test_compact_prints_the_rewarm_reminder(self):
        r = self.run_hook(SESSIONSTART, {"cwd": str(self.proj), "source": "compact"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("Context was compacted.", r.stdout)
        self.assertIn("the ledger is the record", r.stdout)
        self.assertIn("HANDOFF.md", r.stdout)
        self.assertIn("OPERATING-RULES.md", r.stdout)
        self.assertIn("19-x.json", r.stdout)
        self.assertIn("Quote rulings from disk, never from the summary.", r.stdout)
        self.assertIn("Proposal 19:", r.stdout)

    def test_startup_prints_one_line_per_open_ledger(self):
        r = self.run_hook(SESSIONSTART, {"cwd": str(self.proj), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, len([ln for ln in r.stdout.splitlines() if ln.strip()]))
        self.assertIn("Proposal 19:", r.stdout)
        self.assertIn("run /warmup", r.stdout)
        self.assertNotIn("compacted", r.stdout)

    def test_no_open_ledger_prints_nothing(self):
        self.write_ledger(all_done())
        r = self.run_hook(SESSIONSTART, {"cwd": str(self.proj), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_malformed_stdin_and_missing_cwd_exit_zero(self):
        r = self.run_hook(SESSIONSTART, None, cwd=str(self.proj), raw_stdin="")
        self.assertEqual(0, r.returncode, r.stderr)


if __name__ == "__main__":
    unittest.main()
