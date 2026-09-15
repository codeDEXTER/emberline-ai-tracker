"""`tracker lanes` -- share, risk, the 80% cut and each item's lane
(proposal 26, C-02; D1-D4).

  share = value weight (high 3, medium 2, low 1) x points / the open queue's total
  risk  = impact x likelihood, at least 9 when the item routes restricted
  Now   = items in share order until 80% cumulative, the one crossing the line included
  tail  = risk 6+ Daily, 3-5 Weekly, 1-2 When touched
  risk 9+ is alone: never bundled, in whichever lane

Run:  python3 -m unittest discover -s tests -q
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

from tools import project as P  # noqa: E402
from tools.tracker import lanes  # noqa: E402

TRACKER = ROOT / "bin" / "tracker"


def item(iid, value=None, points=None, impact=None, likelihood=None, status="not started", **more):
    d = {"id": iid, "phase": "Q", "cx": "C2", "title": iid.lower(), "status": status}
    for k, v in (("value", value), ("points", points), ("impact", impact), ("likelihood", likelihood)):
        if v is not None:
            d[k] = v
    d.update(more)
    return d


# Raw shares: Q-01 3x13=39, Q-02 3x8=24, Q-03 2x5=10, Q-04 1x5=5, Q-05 2x1=2 -> total 80.
# Cumulative: 48.75%, 78.75% (still under 80), 91.25% (crosses: included), 97.5%, 100%.
QUEUE = [
    item("Q-04", "low", 5, impact=2, likelihood=2),       # tail, risk 4 -> Weekly
    item("Q-01", "high", 13, impact=2, likelihood=1),
    item("Q-05", "medium", 1, impact=1, likelihood=1),    # tail, risk 1 -> When touched
    item("Q-02", "high", 8, impact=1, likelihood=1),
    item("Q-03", "medium", 5, impact=3, likelihood=1),    # crosses the line -> Now
    item("Q-06", "high", 3, status="done"),               # done: not in the queue
    item("Q-07"),                                         # unsized
]


class LanesCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / P.FILE).write_text(json.dumps({"risk_paths": {"restricted": ["finance_data/*"]}}))

    def by_id(self, queue):
        result = lanes.lanes(queue, self.root)
        return {r["id"]: r for r in result["items"]}, result


class TestShareAndCut(LanesCase):
    def test_shares_and_order(self):
        rows, result = self.by_id(QUEUE)
        self.assertEqual([r["id"] for r in result["items"]], ["Q-01", "Q-02", "Q-03", "Q-04", "Q-05"])
        self.assertAlmostEqual(rows["Q-01"]["share"], 39 / 80)
        self.assertAlmostEqual(rows["Q-03"]["cumulative"], 73 / 80)

    def test_the_item_crossing_80_percent_is_now(self):
        rows, _ = self.by_id(QUEUE)
        self.assertEqual([i for i in ("Q-01", "Q-02", "Q-03") if rows[i]["lane"] == "Now"], ["Q-01", "Q-02", "Q-03"])
        self.assertNotEqual(rows["Q-04"]["lane"], "Now")

    def test_tail_lanes_by_risk(self):
        rows, _ = self.by_id(QUEUE + [item("Q-08", "low", 1, impact=3, likelihood=2)])
        self.assertEqual(rows["Q-04"]["lane"], "Weekly")
        self.assertEqual(rows["Q-05"]["lane"], "When touched")
        self.assertEqual(rows["Q-08"]["lane"], "Daily")

    def test_done_items_are_left_out_and_unsized_are_listed(self):
        rows, result = self.by_id(QUEUE)
        self.assertNotIn("Q-06", rows)
        self.assertEqual([u["id"] for u in result["unsized"]], ["Q-07"])

    def test_unscored_tail_item_says_so(self):
        rows, _ = self.by_id(QUEUE + [item("Q-09", "low", 1)])
        self.assertEqual(rows["Q-09"]["lane"], "Unscored")


class TestRestrictedOverride(LanesCase):
    def test_restricted_paths_raise_risk_to_nine_and_go_alone(self):
        queue = QUEUE + [item("Q-10", "low", 1, impact=1, likelihood=1, files=["finance_data/book.json"])]
        rows, _ = self.by_id(queue)
        self.assertEqual(rows["Q-10"]["risk"], 9)
        self.assertTrue(rows["Q-10"]["alone"])
        self.assertEqual(rows["Q-10"]["lane"], "Daily")
        self.assertFalse(rows["Q-05"]["alone"])

    def test_restricted_head_item_stays_now_but_alone(self):
        queue = [item("Q-01", "high", 13, risk="restricted"), item("Q-02", "low", 1, impact=1, likelihood=1)]
        rows, _ = self.by_id(queue)
        self.assertEqual(rows["Q-01"]["lane"], "Now")
        self.assertTrue(rows["Q-01"]["alone"])

    def test_high_score_without_restriction_is_alone(self):
        rows, _ = self.by_id(QUEUE + [item("Q-11", "low", 1, impact=4, likelihood=3)])
        self.assertEqual(rows["Q-11"]["risk"], 12)
        self.assertTrue(rows["Q-11"]["alone"])


class TestCommand(LanesCase):
    def ledger(self) -> Path:
        path = self.root / "docs" / "proposals" / "99-q.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"proposal": 99, "title": "q", "status": "accepted",
                                    "phases": [{"id": "Q", "name": "q"}], "items": QUEUE, "asks": []}))
        return path

    def run_lanes(self, *args):
        return subprocess.run([sys.executable, str(TRACKER), "lanes", *map(str, args)],
                              capture_output=True, text=True)

    def test_table(self):
        out = self.run_lanes(self.ledger())
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Now", out.stdout)
        self.assertIn("Q-03", out.stdout)
        self.assertIn("unsized: Q-07", out.stdout)

    def test_json(self):
        out = self.run_lanes(self.ledger(), "--json")
        self.assertEqual(json.loads(out.stdout)["items"][0]["id"], "Q-01")


if __name__ == "__main__":
    unittest.main()
