"""The tracker board's C-04 addition: every open item's lane (proposal 26
C-02's share/risk/80% cut), grouped Now/Daily/Weekly/When touched with the
cut line marked once, and an item whose `next_check` has passed shown as
overdue (proposal 26, C-04).

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
from tools.tracker import board  # noqa: E402


def item(iid, status="not started", files=None, **more):
    d = {"id": iid, "phase": "Q", "cx": "C2", "title": iid.lower(), "status": status}
    if files is not None:
        d["files"] = files
    d.update(more)
    return d


def ledger(number, items):
    return {"proposal": number, "title": f"proposal {number}", "status": "accepted",
            "phases": [{"id": "Q", "name": "q"}], "items": items, "asks": []}


def write(root: Path, number, data) -> Path:
    """render() hashes the ledger file for its digest meta tag -- a real file
    on disk, not just a dict, is needed to call it directly in a test."""
    path = root / f"{number}-x.json"
    path.write_text(json.dumps(data))
    return path


class LanesSectionCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / P.FILE).write_text(json.dumps({}))
        self.today = datetime.date(2026, 9, 15)

    def make(self, items):
        led = ledger(1, items)
        state = board.lane_state([(Path("1.json"), led)], self.root, self.today)
        return led, state

    def test_the_cut_line_appears_once_between_now_and_the_tail(self):
        # Q-00 dominates the share -> Now; Q-01 is tiny -> tail (When touched).
        _, state = self.make([item("Q-00", value="high", points=13, impact=1, likelihood=1),
                              item("Q-01", value="low", points=1, impact=1, likelihood=1)])
        block = board.lanes_block(state)
        self.assertEqual(block.count('class="cut-line"'), 1)
        self.assertLess(block.index("Q-00"), block.index('class="cut-line"'))
        self.assertLess(block.index('class="cut-line"'), block.index("Q-01"))

    def test_lane_groups_carry_their_items(self):
        _, state = self.make([item("Q-00", value="high", points=13, impact=1, likelihood=1),
                              item("Q-01", value="low", points=1, impact=2, likelihood=2)])  # risk 4 -> Weekly
        block = board.lanes_block(state)
        self.assertIn('class="lane lane-now"', block)
        self.assertIn('class="lane lane-weekly"', block)

    def test_an_overdue_item_is_flagged(self):
        _, state = self.make([
            item("Q-00", value="high", points=13, impact=1, likelihood=1),
            item("Q-01", value="low", points=1, impact=1, likelihood=1, next_check="2026-09-01"),
        ])
        rows = {r["id"]: r for r in state["items"]}
        self.assertTrue(rows["Q-01"]["overdue"])
        self.assertFalse(rows["Q-00"]["overdue"])
        block = board.lanes_block(state)
        self.assertIn('lane-item overdue', block)
        self.assertIn("badge-overdue", block)
        self.assertIn("overdue since 2026-09-01", block)

    def test_a_not_yet_due_tail_item_is_not_flagged(self):
        _, state = self.make([
            item("Q-00", value="high", points=13, impact=1, likelihood=1),
            item("Q-01", value="low", points=1, impact=1, likelihood=1, next_check="2026-09-29"),
        ])
        rows = {r["id"]: r for r in state["items"]}
        self.assertFalse(rows["Q-01"]["overdue"])

    def test_render_includes_the_lanes_section(self):
        led = ledger(1, [item("Q-01", value="high", points=13, impact=1, likelihood=1)])
        path = write(self.root, 1, led)
        text = board.render([(path, led)], "demo", None, self.root)
        self.assertIn('id="lanes"', text)


if __name__ == "__main__":
    unittest.main()
