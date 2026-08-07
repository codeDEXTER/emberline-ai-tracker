"""Regression tests for bin/spend.

The test that matters here is `test_report_is_never_silently_zero`. `spend
report` returned 0 for every row for a week because it parsed a hand-written
file for a field nobody typed. It shipped without tests, so nothing said so.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin" / "spend"


def load_spend():
    """Import bin/spend, which has no .py extension."""
    spec = importlib.util.spec_from_loader(
        "spend", importlib.machinery.SourceFileLoader("spend", str(BIN)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_transcript(path: Path, cwd: str, out_tokens: list[int], agents=()):
    """A minimal transcript in the shape spend actually reads."""
    with path.open("w") as fh:
        for i, n in enumerate(out_tokens):
            rec = {
                "timestamp": f"2026-08-0{(i % 5) + 1}T10:00:0{i % 10}.000Z",
                "cwd": cwd,
                "message": {"role": "assistant", "usage": {"output_tokens": n}},
            }
            fh.write(json.dumps(rec) + "\n")
        for role in agents:
            fh.write(json.dumps({
                "timestamp": "2026-08-05T11:00:00.000Z",
                "cwd": cwd,
                "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "name": "Agent",
                     "input": {"subagent_type": role}}]},
            }) + "\n")


class SpendHarness(unittest.TestCase):
    """A throwaway git repo, a worktree-shaped path, and fake transcripts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "proj"
        (self.repo / ".claude" / "worktrees" / "task-one").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

        self.projects = root / "projects" / "-proj"
        self.projects.mkdir(parents=True)
        write_transcript(self.projects / "aaaa1111.jsonl",
                         str(self.repo / ".claude" / "worktrees" / "task-one"),
                         [1000, 2500], agents=["code-engineer", "test-engineer"])
        write_transcript(self.projects / "bbbb2222.jsonl",
                         str(self.repo), [400])
        # a session somewhere else entirely -- must not be counted
        write_transcript(self.projects / "cccc3333.jsonl",
                         str(root / "elsewhere"), [99999])

        self.spend = load_spend()
        self.spend.PROJECTS = str(root / "projects")
        self.cwd = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def report(self, **kw):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.spend.cmd_report(**kw)
        return buf.getvalue()


class TestReport(SpendHarness):

    def test_report_is_never_silently_zero(self):
        """The bug this file exists for: real usage must never report as 0."""
        out = self.report()
        self.assertIn("3,900", out, "task-one's 1000+2500 and the checkout's 400")
        self.assertNotRegex(
            out, r"TOTAL\s+0\b",
            "a zero total over transcripts that carry usage is the original bug")

    def test_report_does_not_depend_on_a_hand_written_file(self):
        """AGENT-LOG.md is absent here; the numbers must still be right."""
        self.assertFalse((self.repo / "AGENT-LOG.md").exists())
        self.assertIn("3,900", self.report())

    def test_sessions_outside_the_project_are_excluded(self):
        self.assertNotIn("99,999", self.report())

    def test_tasks_are_named_from_the_worktree(self):
        out = self.report()
        self.assertIn("task-one", out)
        self.assertIn("(main checkout)", out)

    def test_by_agent_counts_dispatches_from_transcripts(self):
        out = self.report(by_agent=True)
        self.assertRegex(out, r"code-engineer\s+1")
        self.assertRegex(out, r"test-engineer\s+1")


class TestAgentLog(SpendHarness):

    def test_generated_log_carries_the_cost_column(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.spend.cmd_agentlog()
        text = buf.getvalue()
        self.assertIn("task-one", text)
        self.assertIn("3,500", text)          # task-one's own total
        self.assertIn("code-engineer×1", text)
        self.assertIn("Do not edit by hand", text)

    def test_write_replaces_the_file_on_disk(self):
        log = self.repo / "AGENT-LOG.md"
        log.write_text("# hand-written, stale, and wrong\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.spend.cmd_agentlog(write=True)
        self.assertNotIn("hand-written", log.read_text())
        self.assertIn("3,500", log.read_text())


if __name__ == "__main__":
    unittest.main()
