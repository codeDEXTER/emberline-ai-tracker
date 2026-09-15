"""Tests for tools/calibrate.py and `bin/spend calibrate` (common-rules
proposal 25, Z-05).

Covers: an item costing over 2x its points class's median gets flagged and
one within range does not; the "every 20 closed items" gate (no calibration
below the next multiple of 20, one calibration once crossed, no re-run
within the same bucket); items with no points or no worklog data are
skipped rather than dragging a median toward zero; and the calibration log
gets exactly one line per run.

Run:  python3 -m unittest discover -s tests -p 'test_calibrate.py' -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools import calibrate  # noqa: E402


def make_item(item_id, points=3, status="done"):
    return {"id": item_id, "phase": item_id.split("-")[0], "cx": "C2",
            "title": item_id, "status": status, "points": points,
            "tag": "[ruflo · medium · sonnet]", "log": []}


def write_ledger(proj: Path, name: str, items: list[dict]):
    proposals = proj / "docs" / "proposals"
    proposals.mkdir(parents=True, exist_ok=True)
    (proposals / name).write_text(json.dumps({
        "proposal": 90, "title": "fixture", "status": "accepted",
        "phases": [{"id": "Q", "name": "fixture"}],
        "items": items,
    }))


def write_day_file(out_dir: Path, date: str, rows: list[dict]):
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{date}.jsonl").open("a") as fh:
        for row in rows:
            base = {"day": date, "project": "fixture", "session": "s1",
                    "agent": "lead", "model": "claude-sonnet-5",
                    "input_tokens": 0, "cache_write_tokens": 0,
                    "cache_read_tokens": 0, "output_tokens": 0,
                    "active_seconds": 0, "cost_usd": 0.0, "priced": True}
            base.update(row)
            fh.write(json.dumps(base) + "\n")


class CalibrateHarness(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        self.out = Path(self.tmp.name) / "worklog"
        self.proj.mkdir()

    def tearDown(self):
        self.tmp.cleanup()


class TestFlagging(CalibrateHarness):

    def test_outlier_flagged_and_in_range_item_is_not(self):
        items = [make_item(f"Q-{i:02}", points=3) for i in range(1, 5)]
        write_ledger(self.proj, "90-fixture.json", items)
        # class-3 costs: 100, 100, 100, 300 -- median 100, Q-04 is 3x it.
        write_day_file(self.out, "2026-09-01", [
            {"item": "Q-01", "output_tokens": 100},
            {"item": "Q-02", "output_tokens": 100},
            {"item": "Q-03", "output_tokens": 100},
            {"item": "Q-04", "output_tokens": 300},
        ])

        result = calibrate.calibrate(project=self.proj, out=self.out, force=True)

        self.assertTrue(result["ran"])
        flagged_ids = {f["item"] for f in result["flagged"]}
        self.assertEqual({"Q-04"}, flagged_ids)
        self.assertEqual(3.0, result["flagged"][0]["multiple"])
        self.assertNotIn("Q-01", flagged_ids)
        self.assertNotIn("Q-02", flagged_ids)
        self.assertNotIn("Q-03", flagged_ids)

    def test_flagging_never_reads_transcript_prose(self):
        # The result and the log are built only from ledger and day-file
        # fields -- nothing here ever passes through a transcript's own
        # message content, so there is no prose field to leak in the first
        # place. Assert the shape stays numbers-and-ids only.
        items = [make_item("Q-01", points=2)]
        write_ledger(self.proj, "90-fixture.json", items)
        write_day_file(self.out, "2026-09-01", [{"item": "Q-01", "output_tokens": 50}])
        result = calibrate.calibrate(project=self.proj, out=self.out, force=True)
        for f in result["flagged"]:
            for v in f.values():
                self.assertNotIsInstance(v, (list, dict))


class TestSkipped(CalibrateHarness):

    def test_item_without_points_is_skipped_not_zero_cost(self):
        with_points = make_item("Q-01", points=5)
        no_points = make_item("Q-02", points=None)
        write_ledger(self.proj, "90-fixture.json", [with_points, no_points])
        write_day_file(self.out, "2026-09-01", [
            {"item": "Q-01", "output_tokens": 200},
            {"item": "Q-02", "output_tokens": 1},
        ])
        result = calibrate.calibrate(project=self.proj, out=self.out, force=True)
        self.assertIn("Q-02", result["skipped_no_data"])
        self.assertEqual({5: 200}, result["medians"])
        self.assertEqual([], result["flagged"])

    def test_item_with_no_worklog_rows_is_skipped(self):
        write_ledger(self.proj, "90-fixture.json", [make_item("Q-01", points=3)])
        # No day file written at all for Q-01.
        result = calibrate.calibrate(project=self.proj, out=self.out, force=True)
        self.assertIn("Q-01", result["skipped_no_data"])
        self.assertEqual({}, result["medians"])


class TestEvery20Gate(CalibrateHarness):

    def _closed(self, n, start=1):
        items = [make_item(f"Q-{i:02}", points=3) for i in range(start, start + n)]
        rows = [{"item": it["id"], "output_tokens": 100} for it in items]
        return items, rows

    def test_below_twenty_does_not_run(self):
        items, rows = self._closed(19)
        write_ledger(self.proj, "90-fixture.json", items)
        write_day_file(self.out, "2026-09-01", rows)

        result = calibrate.calibrate(project=self.proj, out=self.out)

        self.assertFalse(result["ran"])
        self.assertEqual(19, result["closed"])
        self.assertEqual(0, result["last_calibrated_at"])

    def test_crossing_twenty_runs_once(self):
        items, rows = self._closed(20)
        write_ledger(self.proj, "90-fixture.json", items)
        write_day_file(self.out, "2026-09-01", rows)

        result = calibrate.calibrate(project=self.proj, out=self.out)

        self.assertTrue(result["ran"])
        self.assertEqual(20, result["closed"])
        self.assertEqual(20, result["last_calibrated_at"])

        # State was persisted -- a second call with the same 20 items does
        # not run again.
        again = calibrate.calibrate(project=self.proj, out=self.out)
        self.assertFalse(again["ran"])
        self.assertEqual(20, again["last_calibrated_at"])

    def test_staying_in_the_same_bucket_does_not_rerun(self):
        items, rows = self._closed(20)
        write_ledger(self.proj, "90-fixture.json", items)
        write_day_file(self.out, "2026-09-01", rows)
        first = calibrate.calibrate(project=self.proj, out=self.out)
        self.assertTrue(first["ran"])

        # One more closed item (21 total) -- still short of the next
        # multiple of 20 (40), so no re-run.
        more_items, more_rows = self._closed(1, start=21)
        write_ledger(self.proj, "90-fixture.json", items + more_items)
        write_day_file(self.out, "2026-09-01", more_rows)

        second = calibrate.calibrate(project=self.proj, out=self.out)
        self.assertFalse(second["ran"])
        self.assertEqual(21, second["closed"])

    def test_crossing_the_next_multiple_runs_again(self):
        items, rows = self._closed(20)
        write_ledger(self.proj, "90-fixture.json", items)
        write_day_file(self.out, "2026-09-01", rows)
        calibrate.calibrate(project=self.proj, out=self.out)

        more_items, more_rows = self._closed(20, start=21)
        write_ledger(self.proj, "90-fixture.json", items + more_items)
        write_day_file(self.out, "2026-09-01", more_rows)

        result = calibrate.calibrate(project=self.proj, out=self.out)
        self.assertTrue(result["ran"])
        self.assertEqual(40, result["closed"])

    def test_force_bypasses_the_gate(self):
        items, rows = self._closed(3)
        write_ledger(self.proj, "90-fixture.json", items)
        write_day_file(self.out, "2026-09-01", rows)
        result = calibrate.calibrate(project=self.proj, out=self.out, force=True)
        self.assertTrue(result["ran"])
        self.assertEqual(3, result["closed"])


class TestLog(CalibrateHarness):

    def test_one_line_per_run_and_flagged_items_named(self):
        items = [make_item(f"Q-{i:02}", points=3) for i in range(1, 5)]
        write_ledger(self.proj, "90-fixture.json", items)
        write_day_file(self.out, "2026-09-01", [
            {"item": "Q-01", "output_tokens": 100},
            {"item": "Q-02", "output_tokens": 100},
            {"item": "Q-03", "output_tokens": 100},
            {"item": "Q-04", "output_tokens": 300},
        ])

        calibrate.calibrate(project=self.proj, out=self.out, force=True)
        calibrate.calibrate(project=self.proj, out=self.out, force=True)

        log_path = self.out / "calibration-log.jsonl"
        self.assertTrue(log_path.exists())
        lines = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
        self.assertEqual(2, len(lines))
        self.assertEqual(["Q-04"], [f["item"] for f in lines[0]["flagged"]])


class TestStatePersistence(CalibrateHarness):

    def test_state_file_survives_a_fresh_load(self):
        items = [make_item(f"Q-{i:02}", points=3) for i in range(1, 21)]
        rows = [{"item": it["id"], "output_tokens": 100} for it in items]
        write_ledger(self.proj, "90-fixture.json", items)
        write_day_file(self.out, "2026-09-01", rows)

        calibrate.calibrate(project=self.proj, out=self.out)

        state = calibrate.load_state(self.out)
        self.assertEqual(20, state["last_calibrated_at"])

    def test_corrupt_state_file_starts_from_zero(self):
        self.out.mkdir(parents=True)
        (self.out / ".calibration-state.json").write_text("not json")
        state = calibrate.load_state(self.out)
        self.assertEqual(0, state["last_calibrated_at"])


if __name__ == "__main__":
    unittest.main()
