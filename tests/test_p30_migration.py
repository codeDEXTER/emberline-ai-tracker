"""Proposal 30, P-05: every open item in the repo's ledgers is either split
into valid lettered parts or is one of proposal 30's own whole items (P-01
through P-06, tracked without parts by design -- see that proposal's own
P-05 row). Also pins the lead's approved shares for the five migrated items.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import ledger as LEDGER  # noqa: E402
from tools.tracker import parts as PARTS  # noqa: E402

PROPOSAL_30_WHOLE_ITEMS = {"P-01", "P-02", "P-03", "P-04", "P-05", "P-06"}

EXPECTED_SHARES = {
    "W-10": [20, 20, 20, 20, 20],
    "L-02": [60, 30, 10],
    "L-07": [80, 20],
    "S-07": [100],
    "S-08": [100],
}


def open_items():
    """(ledger_path, item) for every item whose status is not 'done'."""
    for path in LEDGER.find(ROOT):
        data = LEDGER.load(path)
        for i in LEDGER.items(data):
            if i.get("status") != "done":
                yield path, i


class TestEveryOpenItemHasPartsOrIsWholeByDesign(unittest.TestCase):

    def test_every_open_item_has_valid_parts_or_is_a_p30_whole_item(self):
        problems = []
        for path, i in open_items():
            iid = i.get("id")
            if iid in PROPOSAL_30_WHOLE_ITEMS:
                self.assertNotIn("parts", i, f"{path.name} {iid}: a proposal-30 P-0x "
                                  "item is tracked whole, without parts")
                continue
            part_problems = PARTS.validate_parts(i)
            if not i.get("parts"):
                problems.append(f"{path.name} {iid}: open item has no parts and is not "
                                 "a P-0x whole item")
            elif part_problems:
                problems.extend(f"{path.name}: {p}" for p in part_problems)
        self.assertEqual([], problems)

    def test_every_ledger_still_validates(self):
        for path in LEDGER.find(ROOT):
            data = LEDGER.load(path)
            self.assertEqual([], LEDGER.validate(data), path.name)


class TestApprovedShares(unittest.TestCase):
    """The lead's split, as approved (proposal 30's mockup data)."""

    def _parts(self, path_name, item_id):
        path = next(p for p in LEDGER.find(ROOT) if p.name == path_name)
        data = LEDGER.load(path)
        item = LEDGER.by_id(data)[item_id]
        return PARTS.parts(item)

    def test_w10_shares(self):
        ps = self._parts("19-proposal-warmup.json", "W-10")
        self.assertEqual(EXPECTED_SHARES["W-10"], [p["share"] for p in ps])
        self.assertEqual(["W-10.A", "W-10.B", "W-10.C", "W-10.D", "W-10.E"], [p["id"] for p in ps])
        self.assertEqual("in progress", ps[1]["status"])  # B: whole parts, so "in progress"
        self.assertEqual("done", ps[2]["status"])

    def test_l02_shares(self):
        ps = self._parts("23-eight-levers-for-token-spend.json", "L-02")
        self.assertEqual(EXPECTED_SHARES["L-02"], [p["share"] for p in ps])

    def test_l07_shares(self):
        ps = self._parts("23-eight-levers-for-token-spend.json", "L-07")
        self.assertEqual(EXPECTED_SHARES["L-07"], [p["share"] for p in ps])

    def test_s07_and_s08_shares(self):
        s07 = self._parts("21-standard-is-mandatory.json", "S-07")
        s08 = self._parts("21-standard-is-mandatory.json", "S-08")
        self.assertEqual(EXPECTED_SHARES["S-07"], [p["share"] for p in s07])
        self.assertEqual(EXPECTED_SHARES["S-08"], [p["share"] for p in s08])
        self.assertEqual("session:PhotoVault App", s07[0]["owner"])
        self.assertEqual("session:PhotoVault Engine", s08[0]["owner"])


if __name__ == "__main__":
    unittest.main()
