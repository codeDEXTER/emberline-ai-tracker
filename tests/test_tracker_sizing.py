"""Sizing fields on ledger items: value, points, risk and cluster (proposal 25,
Z-01), impact and likelihood (proposal 26, C-01).

Every field is optional -- a ledger without them validates as before -- and a
bad value is a named problem, never a traceback.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import ledger as L  # noqa: E402
from tools.tracker import render as R  # noqa: E402


def one_item(**fields):
    item = {"id": "Z-01", "phase": "Z", "cx": "C2", "title": "a", "status": "not started"}
    item.update(fields)
    return {"proposal": 25, "title": "t", "status": "accepted",
            "phases": [{"id": "Z", "name": "build"}], "items": [item], "asks": []}


class TestValuePointsRiskCluster(unittest.TestCase):
    def test_a_ledger_without_them_is_still_well_formed(self):
        self.assertEqual(L.validate(one_item()), [])

    def test_good_values_pass(self):
        for value in L.VALUES:
            for points in L.POINTS:
                for risk in L.RISKS:
                    d = one_item(value=value, points=points, risk=risk, cluster="tracker")
                    self.assertEqual(L.validate(d), [], (value, points, risk))

    def test_bad_value_is_named(self):
        for bad in ("urgent", "", 3, None, True):
            problems = L.validate(one_item(value=bad))
            self.assertTrue(any("Z-01: value" in p for p in problems), (bad, problems))

    def test_bad_points_are_named(self):
        for bad in (4, 0, 21, "3", 3.0, True, -1):
            problems = L.validate(one_item(points=bad))
            self.assertTrue(any("Z-01: points" in p for p in problems), (bad, problems))

    def test_bad_risk_is_named(self):
        for bad in ("high", "", 1, None):
            problems = L.validate(one_item(risk=bad))
            self.assertTrue(any("Z-01: risk" in p for p in problems), (bad, problems))

    def test_bad_cluster_is_named(self):
        for bad in ("", "   ", 7, ["tracker"], "two\nlines"):
            problems = L.validate(one_item(cluster=bad))
            self.assertTrue(any("Z-01: cluster" in p for p in problems), (bad, problems))
            self.assertTrue(all("\n" not in p for p in problems))

    def test_render_shows_the_four_fields(self):
        d = one_item(value="high", points=5, risk="restricted", cluster="tracker")
        row = R.item_row(d["items"][0], None)
        for text in ("value high", "5 pts", "risk restricted", "cluster tracker"):
            self.assertIn(text, row)

    def test_render_shows_nothing_extra_without_them(self):
        row = R.item_row(one_item()["items"][0], None)
        self.assertNotIn("pts", row)
        self.assertNotIn('size"', row)


class TestImpactAndLikelihood(unittest.TestCase):
    """Proposal 26, C-01: impact 1-4 (4 stops everything, 3 a user-visible
    feature breaks, 2 user-visible but still works, 1 back-end only) and
    likelihood 1-3."""

    def test_good_values_pass(self):
        for impact in (1, 2, 3, 4):
            for likelihood in (1, 2, 3):
                self.assertEqual(L.validate(one_item(impact=impact, likelihood=likelihood)), [])

    def test_bad_impact_is_named(self):
        for bad in (0, 5, "3", 3.0, True, None):
            problems = L.validate(one_item(impact=bad))
            self.assertTrue(any("Z-01: impact" in p for p in problems), (bad, problems))

    def test_bad_likelihood_is_named(self):
        for bad in (0, 4, "2", 2.0, False, None):
            problems = L.validate(one_item(likelihood=bad))
            self.assertTrue(any("Z-01: likelihood" in p for p in problems), (bad, problems))

    def test_render_shows_them(self):
        row = R.item_row(one_item(impact=4, likelihood=2)["items"][0], None)
        self.assertIn("impact 4", row)
        self.assertIn("likelihood 2", row)


if __name__ == "__main__":
    unittest.main()
