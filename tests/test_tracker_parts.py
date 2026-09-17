"""Lettered parts of an item (proposal 30, P-01): shape, completion, groups.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import ledger as L  # noqa: E402
from tools.tracker import parts as P  # noqa: E402

TODAY = datetime.date(2026, 9, 17)


def item(parts=None, status="in progress", iid="W-10"):
    i = {"id": iid, "phase": "W", "cx": "C2", "title": "pilot", "status": status}
    if parts is not None:
        i["parts"] = parts
    return i


def part(letter, share, status="not started", iid="W-10", **extra):
    return {"id": f"{iid}.{letter}", "title": f"part {letter}", "share": share, "status": status, **extra}


class TestShape(unittest.TestCase):

    def test_well_formed_parts_have_no_problems(self):
        self.assertEqual([], P.validate_parts(item([part("A", 60, "done"), part("B", 40)])))

    def test_an_item_without_parts_is_not_checked(self):
        self.assertEqual([], P.validate_parts(item()))

    def test_letters_must_run_in_order_from_a(self):
        problems = P.validate_parts(item([part("A", 50), part("C", 50)]))
        self.assertTrue(any("W-10.B" in p for p in problems), problems)

    def test_shares_must_add_up_to_100(self):
        problems = P.validate_parts(item([part("A", 60), part("B", 30)]))
        self.assertTrue(any("add up to 90" in p for p in problems), problems)

    def test_share_is_a_whole_percent(self):
        for bad in (0, 101, 50.0, "50", True):
            with self.subTest(share=bad):
                self.assertTrue(P.validate_parts(item([part("A", bad)])))

    def test_status_owner_date_and_risk_are_checked(self):
        cases = {
            "status": part("A", 100, "finished"),
            "owner": part("A", 100, owner=""),
            "waiting_until": part("A", 100, waiting_until="23 Sep"),
            "risk": part("A", 100, risk="severe", risk_reason="x"),
            "risk_reason": part("A", 100, risk="high"),
        }
        for label, p in cases.items():
            with self.subTest(label):
                self.assertTrue(P.validate_parts(item([p])), label)

    def test_an_item_cannot_be_done_with_an_open_part(self):
        problems = P.validate_parts(item([part("A", 50, "done"), part("B", 50)], status="done"))
        self.assertTrue(any("still open" in p for p in problems), problems)

    def test_ledger_validate_reports_part_problems(self):
        ledger = {"proposal": 99, "title": "t", "status": "accepted", "updated": "2026-09-17",
                  "phases": [{"id": "W", "name": "w"}], "asks": [],
                  "items": [item([part("A", 70)])]}
        self.assertTrue(any("add up to 70" in p for p in L.validate(ledger)))


class TestCompletionAndGroups(unittest.TestCase):

    def test_completion_is_the_done_shares(self):
        i = item([part("A", 20, "done"), part("B", 30, "done"), part("C", 50, "in progress")])
        self.assertEqual(50, P.completion(i))

    def test_an_item_without_parts_is_one_part_worth_100(self):
        self.assertEqual(0, P.completion(item()))
        self.assertEqual(100, P.completion(item(status="done")))
        self.assertEqual("W-10", P.next_part(item())["id"])

    def test_next_part_is_the_first_open_letter(self):
        i = item([part("A", 50, "done"), part("B", 25), part("C", 25)])
        self.assertEqual("W-10.B", P.next_part(i)["id"])

    def test_under_80_is_finish_now(self):
        self.assertEqual("finish now", P.group(item([part("A", 60, "done"), part("B", 40)]), TODAY))

    def test_80_or_more_is_back_burner(self):
        self.assertEqual("back burner", P.group(item([part("A", 80, "done"), part("B", 20)]), TODAY))

    def test_a_high_risk_open_part_is_finish_now_whatever_the_percent(self):
        i = item([part("A", 90, "done"), part("B", 10, risk="high", risk_reason="money")])
        self.assertEqual("finish now", P.group(i, TODAY))

    def test_every_open_part_waiting_is_waiting(self):
        i = item([part("A", 40, "done"), part("B", 30, waiting_until="2026-09-23"),
                  part("C", 30, owner="session:PhotoVault Engine")])
        self.assertEqual("waiting", P.group(i, TODAY))

    def test_a_date_that_has_arrived_is_no_longer_waiting(self):
        i = item([part("A", 40, "done"), part("B", 60, waiting_until="2026-09-17")])
        self.assertEqual("finish now", P.group(i, TODAY))

    def test_one_open_part_not_waiting_is_enough_to_leave_waiting(self):
        i = item([part("A", 85, "done"), part("B", 10, waiting_until="2026-09-23"), part("C", 5)])
        self.assertEqual("back burner", P.group(i, TODAY))

    def test_all_parts_done_is_done(self):
        self.assertEqual("done", P.group(item([part("A", 100, "done")], status="done"), TODAY))



class TestNestedParts(unittest.TestCase):
    """Sub-parts: W-10.A.1 (numbers), W-10.A.1.a (lowercase letters)."""

    def sub(self, n, share, status="not started", parent="W-10.A", **extra):
        return {"id": f"{parent}.{n}", "title": f"sub {n}", "share": share, "status": status, **extra}

    def test_well_formed_nesting_has_no_problems(self):
        a = part("A", 60, "in progress", parts=[self.sub(1, 50, "done"), self.sub(2, 50)])
        self.assertEqual([], P.validate_parts(item([a, part("B", 40)])))

    def test_second_level_uses_numbers_in_order(self):
        a = part("A", 100, parts=[self.sub("a", 100)])
        self.assertTrue(any("W-10.A.1" in x for x in P.validate_parts(item([a]))))

    def test_third_level_uses_lowercase_letters(self):
        a1 = self.sub(1, 100, parts=[{"id": "W-10.A.1.a", "title": "x", "share": 100, "status": "done"}],
                      status="done")
        self.assertEqual([], P.validate_parts(item([part("A", 100, "done", parts=[a1])], status="done")))

    def test_a_fourth_level_is_refused(self):
        deep = {"id": "W-10.A.1.a", "title": "x", "share": 100, "status": "not started",
                "parts": [{"id": "W-10.A.1.a.1", "title": "y", "share": 100, "status": "not started"}]}
        a = part("A", 100, parts=[self.sub(1, 100, parts=[deep])])
        self.assertTrue(any("three levels" in x for x in P.validate_parts(item([a]))))

    def test_sub_shares_add_up_to_100_within_the_parent(self):
        a = part("A", 100, parts=[self.sub(1, 30), self.sub(2, 30)])
        self.assertTrue(any("W-10.A: part shares add up to 60" in x for x in P.validate_parts(item([a]))))

    def test_a_part_cannot_be_done_with_an_open_sub_part(self):
        a = part("A", 100, "done", parts=[self.sub(1, 50, "done"), self.sub(2, 50)])
        self.assertTrue(any("W-10.A: status done" in x for x in P.validate_parts(item([a]))))

    def test_completion_rolls_up(self):
        # A is 60% of the item and half done (30); B is 40% and done (40): 70.
        a = part("A", 60, "in progress", parts=[self.sub(1, 50, "done"), self.sub(2, 50)])
        self.assertEqual(70, P.completion(item([a, part("B", 40, "done")])))

    def test_tree_carries_completion_at_every_depth(self):
        a = part("A", 60, "in progress", parts=[self.sub(1, 50, "done"), self.sub(2, 50)])
        t = P.tree(item([a, part("B", 40, "done")]))
        self.assertEqual((70, 50, 100), (t["completion"], t["parts"][0]["completion"],
                                         t["parts"][0]["parts"][0]["completion"]))


if __name__ == "__main__":
    unittest.main()
