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
from unittest.mock import patch

BIN = Path(__file__).resolve().parent.parent / "bin" / "spend"


def load_spend():
    """Import bin/spend, which has no .py extension."""
    spec = importlib.util.spec_from_loader(
        "spend", importlib.machinery.SourceFileLoader("spend", str(BIN)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_transcript(path: Path, cwd: str, out_tokens: list[int], agents=(),
                      message_id=None):
    """A minimal transcript in the shape spend actually reads.

    `message_id`, if given, is written on every usage record with that same
    id -- the shape a streamed response actually takes, so a caller can
    build the "one message.id, written three times" fixture the dedupe fix
    exists to survive.
    """
    with path.open("w") as fh:
        for i, n in enumerate(out_tokens):
            usage = {"output_tokens": n}
            if message_id:
                usage["output_tokens"] = n  # last write wins on dedupe
            rec = {
                "timestamp": f"2026-08-0{(i % 5) + 1}T10:00:0{i % 10}.000Z",
                "cwd": cwd,
                "message": {"role": "assistant", "usage": usage,
                            **({"id": message_id} if message_id else {})},
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
            out, r"TOTAL\s+0\s+0\s+0\s+0\b",
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

    def test_a_session_spanning_worktrees_is_management_not_a_task(self):
        """A management session enters several worktrees; charging it to one
        of them over-claims that task and hides the rest. Regression guard for
        2026-08-07, when attribution by first-cwd hid 88% of all spend."""
        (self.repo / ".claude" / "worktrees" / "task-two").mkdir(parents=True)
        path = self.projects / "manager.jsonl"
        with open(path, "w") as fh:
            for cwd in (str(self.repo / ".claude" / "worktrees" / "task-one"),
                        str(self.repo / ".claude" / "worktrees" / "task-two")):
                fh.write(json.dumps({
                    "cwd": cwd, "timestamp": "2026-08-07T10:00:00Z",
                    "message": {"usage": {"output_tokens": 700}},
                }) + "\n")
        out = self.report()
        self.assertIn("(management)", out)
        self.assertIn("1,400", out, "both worktrees' spend lands on one management row")

    def test_by_agent_counts_dispatches_from_transcripts(self):
        out = self.report(by_agent=True)
        self.assertRegex(out, r"code-engineer\s+1")
        self.assertRegex(out, r"test-engineer\s+1")


class TestSubagentsAndDedupe(SpendHarness):
    """W-01: subagent transcripts were never read, and streamed records were
    summed instead of deduped by message.id -- both undercounted or
    overcounted the same session, in opposite directions."""

    def test_subagent_transcripts_are_counted(self):
        """Subagent transcripts live at <project>/<session>/subagents/*.jsonl
        and were entirely missed before this fix."""
        session_dir = self.projects / "ssss4444"
        sub_dir = session_dir / "subagents"
        sub_dir.mkdir(parents=True)
        write_transcript(sub_dir / "agent-aaaa.jsonl",
                          str(self.repo / ".claude" / "worktrees" / "task-one"),
                          [500])
        out = self.report()
        self.assertIn("4,400", out, "task-one's 3,900 plus the subagent's 500")

    def test_streamed_records_are_deduped_by_message_id(self):
        """One response streamed three times must count once, at its final
        (largest) usage -- not summed to ~3.6x the real total."""
        write_transcript(self.projects / "dddd5555.jsonl",
                          str(self.repo / ".claude" / "worktrees" / "task-one"),
                          [1000, 1800, 2500], message_id="msg_streamed_1")
        out = self.report()
        self.assertIn("6,400", out, "task-one's 3,900 plus the final 2,500, not the sum 8,700")
        self.assertNotIn("8,200", out, "would be 3,900 + (1000+1800+2500) if not deduped")


class TestTasksForPath(SpendHarness):
    """#78. The Tower needs a project's cost without changing the process's
    working directory: its collectors run in a thread pool, and a global chdir
    there is the kind of race that yields a wrong number occasionally rather
    than an obvious failure."""

    def test_by_path_matches_the_current_directory_form(self):
        """The whole promise: an access change, not a measurement one."""
        here_root, here = self.spend.tasks_for()
        os.chdir(self.cwd)                      # deliberately leave the project
        there_root, there = self.spend.tasks_for(str(self.repo))
        self.assertEqual(os.path.realpath(there_root), os.path.realpath(here_root))
        self.assertEqual([(t["task"], t["out"]) for t in there],
                         [(t["task"], t["out"]) for t in here])

    def test_it_does_not_change_the_working_directory(self):
        """If this ever regresses to a chdir, the race comes back silently.

        Deliberately called from OUTSIDE the project: the first version of this
        test ran from inside it, so a chdir to that same directory changed
        nothing observable and the guard passed against the very bug it exists
        to catch.
        """
        os.chdir(self.cwd)
        before = os.getcwd()
        self.spend.tasks_for(str(self.repo))
        self.assertEqual(os.getcwd(), before,
                         "tasks_for changed the process working directory")

    def test_sessions_from_elsewhere_are_still_excluded(self):
        """The harness plants a 99,999-token session outside the project. It
        must not be attributed by the path form any more than by the CLI."""
        os.chdir(self.cwd)
        _, tasks = self.spend.tasks_for(str(self.repo))
        self.assertNotIn(99999, [t["out"] for t in tasks])

    def test_tasks_here_is_still_the_current_directory(self):
        """The CLI path must be untouched — every existing caller goes through
        _tasks_here()."""
        root, tasks = self.spend._tasks_here()
        self.assertEqual(os.path.realpath(root), os.path.realpath(self.repo))
        self.assertTrue(tasks)


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


class TestHelp(SpendHarness):
    """Proposal 23 F-04: `-h`/`--help` on any subcommand must print usage and
    exit 0 without doing any work. Before this fix, `spend calibrate --help`
    fell straight through to `cmd_calibrate`, running a real calibration
    against the default worklog dir (16 Sep 2026: an agent wrote a false
    `last_calibrated_at` into the real repo this way).

    Each case below patches the subcommand's own worker function to raise if
    it is ever called at all -- proof that `--help` short-circuits before any
    work, not just before its visible side effect.
    """

    def test_calibrate_help_never_calls_calibrate(self):
        with patch.object(self.spend, "_calibrate") as fake_calibrate:
            fake_calibrate.calibrate.side_effect = AssertionError(
                "spend calibrate --help must never run a real calibration")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.spend.main(["calibrate", "--help"])
        self.assertEqual(rc, 0)
        self.assertIn("spend calibrate", buf.getvalue())
        fake_calibrate.calibrate.assert_not_called()

    def test_calibrate_dash_h_also_short_circuits(self):
        with patch.object(self.spend, "_calibrate") as fake_calibrate:
            fake_calibrate.calibrate.side_effect = AssertionError("must not run")
            rc = self.spend.main(["calibrate", "-h"])
        self.assertEqual(rc, 0)
        fake_calibrate.calibrate.assert_not_called()

    def test_calibrate_help_writes_no_state_or_log_file(self):
        """Belt and braces on top of the mock above: even pointing at a
        fresh temp --out dir, --help must leave it untouched (empty or
        nonexistent), never create `.calibration-state.json` or
        `calibration-log.jsonl` there."""
        out_dir = Path(self.tmp.name) / "would-be-worklog-out"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.spend.main(["calibrate", "--help", "--out", str(out_dir)])
        self.assertEqual(rc, 0)
        self.assertFalse(out_dir.exists(),
                          "spend calibrate --help must not create the --out dir")

    def test_report_help_never_calls_cmd_report(self):
        with patch.object(self.spend, "cmd_report") as fake:
            fake.side_effect = AssertionError("must not run")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.spend.main(["report", "--help"])
        self.assertEqual(rc, 0)
        self.assertIn("spend report", buf.getvalue())
        fake.assert_not_called()

    def test_agentlog_help_never_writes_the_log(self):
        log = self.repo / "AGENT-LOG.md"
        with patch.object(self.spend, "cmd_agentlog") as fake:
            fake.side_effect = AssertionError("must not run")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.spend.main(["agentlog", "--help"])
        self.assertEqual(rc, 0)
        self.assertIn("spend agentlog", buf.getvalue())
        fake.assert_not_called()
        self.assertFalse(log.exists())

    def test_log_help_never_appends_an_entry(self):
        log = self.repo / "AGENT-LOG.md"
        with patch.object(self.spend, "cmd_log") as fake:
            fake.side_effect = AssertionError("must not run")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.spend.main(["log", "--help"])
        self.assertEqual(rc, 0)
        self.assertIn("spend log", buf.getvalue())
        fake.assert_not_called()
        self.assertFalse(log.exists())

    def test_today_help_never_calls_cmd_today(self):
        with patch.object(self.spend, "cmd_today") as fake:
            fake.side_effect = AssertionError("must not run")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.spend.main(["today", "--help"])
        self.assertEqual(rc, 0)
        fake.assert_not_called()

    def test_unknown_command_is_unaffected(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.spend.main(["bogus", "--help"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
