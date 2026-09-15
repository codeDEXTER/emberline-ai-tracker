"""Tests for tools/worklog.py and the bin/worklog CLI (common-rules proposal
27, W-02 and the W-04 page part).

Covers: task naming (brief tag, then branch, then session), active-time gap
accounting, idempotent re-run after a transcript grows, and that nothing
written to a day file or the HTML page ever carries transcript prose.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools import worklog  # noqa: E402


def user_rec(text, ts, cwd="", branch=None):
    rec = {"timestamp": ts, "cwd": cwd,
           "message": {"role": "user", "content": text}}
    if branch:
        rec["gitBranch"] = branch
    return rec


def assistant_rec(ts, message_id, usage, model="claude-sonnet-5", cwd="",
                   attribution=None):
    rec = {"timestamp": ts, "cwd": cwd,
           "message": {"role": "assistant", "id": message_id, "model": model,
                       "usage": usage, "content": []}}
    if attribution:
        rec["attributionAgent"] = attribution
    return rec


def write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


class WorklogHarness(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.projects = root / "projects"
        self.out = root / "worklog"
        self.projects.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def collect(self):
        return worklog.collect(projects=str(self.projects), out=str(self.out))


class TestItemNaming(WorklogHarness):

    def test_brief_tag_on_a_subagent_transcript_wins(self):
        session = "sess-aaaa"
        sub = self.projects / "-proj" / session / "subagents" / "agent-1.jsonl"
        write_jsonl(sub, [
            user_rec("[ruflo · C2 · sonnet] W-02 do the collector work, "
                     "with a lot more detail that must never appear verbatim "
                     "in the output.",
                     "2026-09-15T10:00:00Z", branch="claude/some-branch"),
            assistant_rec("2026-09-15T10:00:05Z", "msg_1",
                          {"input_tokens": 10, "output_tokens": 20,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0},
                          attribution="code-engineer"),
        ])
        self.collect()
        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["item"], "W-02")
        self.assertEqual(rows[0]["agent"], "code-engineer")

    def test_bare_item_id_at_the_very_start_also_matches(self):
        session = "sess-bbbb"
        sub = self.projects / "-proj" / session / "subagents" / "agent-2.jsonl"
        write_jsonl(sub, [
            user_rec("X-07 close out the ledger item.", "2026-09-15T09:00:00Z"),
            assistant_rec("2026-09-15T09:00:05Z", "msg_x7",
                          {"input_tokens": 5, "output_tokens": 5,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(rows[0]["item"], "X-07")

    def test_falls_back_to_branch_then_session(self):
        session = "sess-cccc"
        main = self.projects / "-proj" / f"{session}.jsonl"
        write_jsonl(main, [
            user_rec("just an ordinary chat message, no tag here at all",
                      "2026-09-15T08:00:00Z", branch="claude/feature-x"),
            assistant_rec("2026-09-15T08:00:05Z", "msg_a",
                          {"input_tokens": 1, "output_tokens": 1,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(rows[0]["item"], "claude/feature-x")
        self.assertEqual(rows[0]["agent"], "lead")

        session2 = "sess-dddd"
        main2 = self.projects / "-proj" / f"{session2}.jsonl"
        write_jsonl(main2, [
            user_rec("also ordinary, and no branch recorded either",
                      "2026-09-15T08:10:00Z"),
            assistant_rec("2026-09-15T08:10:05Z", "msg_b",
                          {"input_tokens": 1, "output_tokens": 1,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        rows = worklog.load_day(str(self.out), "2026-09-15")
        by_item = {r["item"] for r in rows}
        self.assertIn(session2, by_item)


class TestActiveTime(WorklogHarness):

    def test_gaps_under_five_minutes_count_gaps_over_do_not(self):
        session = "sess-time"
        main = self.projects / "-proj" / f"{session}.jsonl"
        write_jsonl(main, [
            user_rec("start", "2026-09-15T10:00:00Z", branch="claude/timing"),
            assistant_rec("2026-09-15T10:00:00Z", "m1",
                          {"input_tokens": 1, "output_tokens": 1,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
            # 60s gap -- counted
            assistant_rec("2026-09-15T10:01:00Z", "m2",
                          {"input_tokens": 1, "output_tokens": 1,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
            # 10-minute gap -- not counted
            assistant_rec("2026-09-15T10:11:00Z", "m3",
                          {"input_tokens": 1, "output_tokens": 1,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
            # another 60s gap -- counted
            assistant_rec("2026-09-15T10:12:00Z", "m4",
                          {"input_tokens": 1, "output_tokens": 1,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(len(rows), 1)
        # Two 60s gaps counted, the 600s gap left out -> 120s active.
        self.assertEqual(rows[0]["active_seconds"], 120)


class TestIdempotentCollect(WorklogHarness):

    def test_rerun_after_appending_does_not_double_count(self):
        session = "sess-grow"
        main = self.projects / "-proj" / f"{session}.jsonl"
        write_jsonl(main, [
            user_rec("first turn", "2026-09-15T11:00:00Z", branch="claude/grow"),
            # A streamed response: two records for the same message.id, the
            # second growing the usage. Only the final one may count.
            assistant_rec("2026-09-15T11:00:01Z", "msg_stream",
                          {"input_tokens": 100, "output_tokens": 50,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        r1 = self.collect()
        self.assertEqual(r1["lines"], 1)
        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(rows[0]["input_tokens"], 100)
        self.assertEqual(rows[0]["output_tokens"], 50)

        # Re-run with nothing new: must be a no-op.
        r2 = self.collect()
        self.assertEqual(r2["days"], [])
        rows_again = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(rows, rows_again)

        # The same message.id grows (streamed further) and a new message
        # arrives, in the next batch of bytes.
        write_jsonl(main, [
            assistant_rec("2026-09-15T11:00:02Z", "msg_stream",
                          {"input_tokens": 100, "output_tokens": 300,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
            assistant_rec("2026-09-15T11:00:10Z", "msg_new",
                          {"input_tokens": 20, "output_tokens": 5,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        rows_final = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(len(rows_final), 1, "same group, still one line")
        # Final output must be 300 (msg_stream's last value) + 5 (msg_new),
        # never 50 + 300 + 5 (double-counting the first partial write).
        self.assertEqual(rows_final[0]["output_tokens"], 305)
        self.assertEqual(rows_final[0]["input_tokens"], 120)

    def test_rewriting_a_day_file_is_deterministic(self):
        """Re-running collect with genuinely new data rewrites the day file
        sorted, not appended -- so byte-identical inputs always produce a
        byte-identical file, not one that grows by re-derivation noise."""
        session = "sess-det"
        main = self.projects / "-proj" / f"{session}.jsonl"
        write_jsonl(main, [
            user_rec("hello", "2026-09-15T12:00:00Z", branch="claude/det"),
            assistant_rec("2026-09-15T12:00:01Z", "m1",
                          {"input_tokens": 1, "output_tokens": 1,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        path = self.out / "2026-09-15.jsonl"
        first = path.read_bytes()
        self.collect()
        second = path.read_bytes()
        self.assertEqual(first, second)


class TestStateTrust(WorklogHarness):
    """Bundle B review, 15 Sep 2026 (HIGH): a corrupt or deleted
    worklog/.state.json fell back to empty state, so the next `collect`
    re-added every message's full usage onto day files that already held
    it. Starting from empty state must never be silent -- it must either
    be provably safe (nothing on disk yet to contradict) or refused."""

    def test_corrupt_state_file_refuses_rather_than_doubling(self):
        session = "sess-corrupt"
        main = self.projects / "-proj" / f"{session}.jsonl"
        write_jsonl(main, [
            user_rec("first turn", "2026-09-15T11:00:00Z", branch="claude/c"),
            assistant_rec("2026-09-15T11:00:01Z", "m1",
                          {"input_tokens": 100, "output_tokens": 50,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(rows[0]["input_tokens"], 100)
        self.assertEqual(rows[0]["output_tokens"], 50)

        state_path = self.out / ".state.json"
        state_path.write_text("not valid json {{{")

        with self.assertRaises(worklog.StateTrustError):
            self.collect()

        # Refusing means writing nothing -- the day file must be untouched,
        # not doubled to input 200 / output 100 as the reported bug did.
        rows_after = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(rows_after[0]["input_tokens"], 100)
        self.assertEqual(rows_after[0]["output_tokens"], 50)

    def test_missing_state_with_existing_day_files_refuses(self):
        session = "sess-missing"
        main = self.projects / "-proj" / f"{session}.jsonl"
        write_jsonl(main, [
            user_rec("first turn", "2026-09-15T11:00:00Z", branch="claude/m"),
            assistant_rec("2026-09-15T11:00:01Z", "m1",
                          {"input_tokens": 10, "output_tokens": 5,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        (self.out / ".state.json").unlink()

        with self.assertRaises(worklog.StateTrustError):
            self.collect()
        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(rows[0]["input_tokens"], 10, "untouched, not doubled")

    def test_rebuild_recomputes_single_run_totals(self):
        session = "sess-rebuild"
        main = self.projects / "-proj" / f"{session}.jsonl"
        write_jsonl(main, [
            user_rec("first turn", "2026-09-15T11:00:00Z", branch="claude/r"),
            assistant_rec("2026-09-15T11:00:01Z", "m1",
                          {"input_tokens": 40, "output_tokens": 20,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        (self.out / ".state.json").write_text("not valid json {{{")

        result = worklog.collect(projects=str(self.projects),
                                  out=str(self.out), rebuild=True)
        self.assertIn("2026-09-15", result["days"])
        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["input_tokens"], 40, "not doubled to 80")
        self.assertEqual(rows[0]["output_tokens"], 20, "not doubled to 40")

    def test_first_run_with_no_day_files_and_no_state_works(self):
        session = "sess-first"
        main = self.projects / "-proj" / f"{session}.jsonl"
        write_jsonl(main, [
            user_rec("first turn", "2026-09-15T11:00:00Z", branch="claude/f"),
            assistant_rec("2026-09-15T11:00:01Z", "m1",
                          {"input_tokens": 7, "output_tokens": 3,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        result = self.collect()
        self.assertEqual(result["days"], ["2026-09-15"])
        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(rows[0]["input_tokens"], 7)


class TestNoTranscriptText(WorklogHarness):

    def test_day_file_and_html_never_carry_prompt_text(self):
        session = "sess-secret"
        sub = self.projects / "-proj" / session / "subagents" / "agent-9.jsonl"
        secret = "THIS-SENTENCE-MUST-NEVER-LEAK-INTO-OUTPUT"
        write_jsonl(sub, [
            user_rec(f"[lead · tier · model] K-09 {secret} and more "
                     "prose that follows the tag.",
                     "2026-09-15T13:00:00Z"),
            assistant_rec("2026-09-15T13:00:01Z", "m1",
                          {"input_tokens": 1, "output_tokens": 1,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        day_file = self.out / "2026-09-15.jsonl"
        text = day_file.read_text()
        self.assertNotIn(secret, text)
        self.assertNotIn("prose that follows", text)

        rows = worklog.load_day(str(self.out), "2026-09-15")
        self.assertEqual(set(rows[0]), set(worklog.GROUP_FIELDS) |
                          {"input_tokens", "cache_write_tokens",
                           "cache_read_tokens", "output_tokens",
                           "active_seconds", "cost_usd"})

        page = worklog.render_day_html("2026-09-15", rows)
        self.assertNotIn(secret, page)

    def test_html_escapes_untrusted_branch_names(self):
        """A branch name is untrusted input once it reaches generated HTML
        -- it can carry markup or quotes just as easily as a label can."""
        session = "sess-xss"
        main = self.projects / "-proj" / f"{session}.jsonl"
        write_jsonl(main, [
            user_rec("hi", "2026-09-15T14:00:00Z",
                     branch="claude/\"><script>alert(1)</script>"),
            assistant_rec("2026-09-15T14:00:01Z", "m1",
                          {"input_tokens": 1, "output_tokens": 1,
                           "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}),
        ])
        self.collect()
        rows = worklog.load_day(str(self.out), "2026-09-15")
        page = worklog.render_day_html("2026-09-15", rows)
        self.assertNotIn("<script>alert(1)</script>", page)


class TestSummaryFormatting(WorklogHarness):

    def test_yesterday_line_shape(self):
        rows = [{
            "day": "2026-09-14", "project": "-proj", "session": "s1",
            "agent": "lead", "model": "claude-sonnet-5", "item": "W-04",
            "input_tokens": 1000, "cache_write_tokens": 0,
            "cache_read_tokens": 0, "output_tokens": 500,
            "active_seconds": 3600, "cost_usd": 0.0105,
        }]
        line = worklog.format_yesterday_line(rows)
        self.assertTrue(line.startswith("yesterday: "))
        self.assertIn("1,500 tokens", line)
        self.assertIn("1.0h active", line)
        self.assertIn("1 tasks", line)
        self.assertIn("$0.01", line)


if __name__ == "__main__":
    unittest.main()
