"""tracker rescore -- 14-day next_check dates for tail-lane items (proposal
26, C-04): a tail item gets next_check = entry date + 14 days, the date does
not move on a later run, an item that leaves the tail loses it, and overdue()
says whether that date has passed.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import project as P  # noqa: E402
from tools.tracker import ledger as L  # noqa: E402
from tools.tracker import rescore as RS  # noqa: E402


def item(iid, value=None, points=None, impact=None, likelihood=None, status="not started", **more):
    d = {"id": iid, "phase": "Q", "cx": "C2", "title": iid.lower(), "status": status}
    for k, v in (("value", value), ("points", points), ("impact", impact), ("likelihood", likelihood)):
        if v is not None:
            d[k] = v
    d.update(more)
    return d


def ledger(items):
    return {"proposal": 99, "title": "t", "status": "accepted",
            "phases": [{"id": "Q", "name": "q"}], "items": items, "asks": []}


class RescoreCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / P.FILE).write_text(json.dumps({}))
        self.today = datetime.date(2026, 9, 15)

    def test_a_tail_item_gets_next_check_14_days_out(self):
        # Q-00 dominates the share (high, 13 pts) and takes the 80% cut as
        # Now; Q-01 (low, 1 pt, risk 1x1=1) falls to the tail -> When touched.
        d = ledger([item("Q-00", "high", 13, impact=1, likelihood=1),
                   item("Q-01", "low", 1, impact=1, likelihood=1)])
        changed = RS.assign(d, self.root, self.today)
        self.assertEqual(changed, ["Q-01"])
        self.assertEqual(d["items"][1]["next_check"], "2026-09-29")
        self.assertNotIn("next_check", d["items"][0])

    def test_a_now_lane_item_gets_no_next_check(self):
        # value high, points 13 -> dominates share -> Now lane.
        d = ledger([item("Q-01", "high", 13, impact=1, likelihood=1)])
        changed = RS.assign(d, self.root, self.today)
        self.assertEqual(changed, [])
        self.assertNotIn("next_check", d["items"][0])

    def test_an_unsized_item_gets_no_next_check(self):
        d = ledger([item("Q-01")])
        changed = RS.assign(d, self.root, self.today)
        self.assertEqual(changed, [])
        self.assertNotIn("next_check", d["items"][0])

    def test_rerunning_does_not_push_the_date_out(self):
        d = ledger([item("Q-00", "high", 13, impact=1, likelihood=1),
                   item("Q-01", "low", 1, impact=1, likelihood=1)])
        RS.assign(d, self.root, self.today)
        first = d["items"][1]["next_check"]
        RS.assign(d, self.root, self.today + datetime.timedelta(days=5))
        self.assertEqual(d["items"][1]["next_check"], first)

    def test_leaving_the_tail_clears_next_check(self):
        d = ledger([item("Q-01", "low", 1, impact=1, likelihood=1, next_check="2026-09-29")])
        d["items"][0]["value"] = "high"
        d["items"][0]["points"] = 13
        changed = RS.assign(d, self.root, self.today)
        self.assertEqual(changed, ["Q-01"])
        self.assertNotIn("next_check", d["items"][0])

    def test_a_done_item_gets_no_next_check_and_loses_a_stale_one(self):
        d = ledger([item("Q-01", "low", 1, impact=1, likelihood=1, status="done", next_check="2026-09-01")])
        changed = RS.assign(d, self.root, self.today)
        self.assertEqual(changed, ["Q-01"])
        self.assertNotIn("next_check", d["items"][0])


class OverdueCase(unittest.TestCase):
    def test_a_past_date_is_overdue(self):
        self.assertTrue(RS.overdue({"next_check": "2026-09-01"}, datetime.date(2026, 9, 15)))

    def test_a_future_date_is_not_overdue(self):
        self.assertFalse(RS.overdue({"next_check": "2026-09-29"}, datetime.date(2026, 9, 15)))

    def test_todays_date_is_not_overdue(self):
        self.assertFalse(RS.overdue({"next_check": "2026-09-15"}, datetime.date(2026, 9, 15)))

    def test_no_next_check_is_not_overdue(self):
        self.assertFalse(RS.overdue({}, datetime.date(2026, 9, 15)))

    def test_a_malformed_date_is_not_overdue(self):
        self.assertFalse(RS.overdue({"next_check": "not-a-date"}, datetime.date(2026, 9, 15)))

    def test_overdue_items_collects_from_a_ledger(self):
        d = ledger([
            item("Q-01", next_check="2026-09-01"),
            item("Q-02", next_check="2026-09-29"),
            item("Q-03"),
        ])
        self.assertEqual([i["id"] for i in RS.overdue_items(d, datetime.date(2026, 9, 15))], ["Q-01"])


class NextCheckValidationCase(unittest.TestCase):
    def test_a_good_date_passes(self):
        d = ledger([item("Q-01", next_check="2026-09-29")])
        self.assertEqual(L.validate(d), [])

    def test_a_ledger_without_it_is_still_well_formed(self):
        self.assertEqual(L.validate(ledger([item("Q-01")])), [])

    def test_a_bad_date_is_named(self):
        for bad in ("not-a-date", "2026-13-40", 20260929, None, ""):
            d = ledger([item("Q-01", next_check=bad)])
            problems = L.validate(d)
            self.assertTrue(any("Q-01: next_check" in p for p in problems), (bad, problems))


if __name__ == "__main__":
    unittest.main()
