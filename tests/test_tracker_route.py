"""`tracker route` -- how an item is reviewed and bundled (proposal 25, Z-02).

  restricted                          -> separate reviewer, the sponsor sees the result, never bundled
  elevated, or value high & points>=5 -> separate reviewer, own branch
  otherwise                           -> gate and tests only; points 1-3 bundle by cluster

Points are set by the lead or the scout and never reach the builder's brief
(D3). Models are unchanged (proposal 23, D8).

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
from tools.tracker import route  # noqa: E402

TRACKER = ROOT / "bin" / "tracker"


class RouteCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / P.FILE).write_text(json.dumps({
            "value_defaults": {"ui": "high"},
            "risk_paths": {"restricted": ["finance_data/*"], "elevated": ["shared/*"]},
        }))

    def r(self, **item):
        base = {"id": "Z-09", "phase": "Z", "cx": "C2", "title": "t", "status": "not started"}
        base.update(item)
        return route.route(base, self.root)


class TestTheTable(RouteCase):
    def test_restricted_is_never_bundled(self):
        got = self.r(risk="restricted", value="low", points=1, cluster="ui")
        self.assertEqual(got["review"], "separate reviewer, the sponsor sees the result")
        self.assertEqual(got["bundle"], "never bundled")

    def test_restricted_from_paths(self):
        got = self.r(files=["finance_data/book.json"], value="low", points=1, cluster="ui")
        self.assertEqual(got["risk"], "restricted")
        self.assertEqual(got["bundle"], "never bundled")

    def test_elevated_gets_its_own_reviewer_and_branch(self):
        got = self.r(files="shared/x.py", value="low", points=2, cluster="ui")
        self.assertEqual((got["review"], got["bundle"]), ("separate reviewer", "own branch"))

    def test_high_value_and_big_gets_its_own_reviewer(self):
        got = self.r(value="high", points=5, cluster="ui")
        self.assertEqual((got["review"], got["bundle"]), ("separate reviewer", "own branch"))

    def test_high_value_by_default_counts(self):
        got = self.r(points=8, cluster="ui")
        self.assertEqual(got["value"], "high")
        self.assertEqual(got["review"], "separate reviewer")

    def test_small_standard_items_bundle_by_cluster(self):
        for points in (1, 2, 3):
            got = self.r(value="medium", points=points, cluster="ui")
            self.assertEqual((got["review"], got["bundle"]), ("gate and tests only", "bundle by cluster ui"))

    def test_big_standard_items_take_their_own_branch(self):
        got = self.r(value="medium", points=8, cluster="ui")
        self.assertEqual((got["review"], got["bundle"]), ("gate and tests only", "own branch"))

    def test_small_item_without_a_cluster_takes_its_own_branch(self):
        got = self.r(value="low", points=1)
        self.assertEqual(got["bundle"], "own branch (no cluster)")

    def test_unsized_is_said_not_guessed(self):
        got = self.r(cluster="other")
        self.assertEqual(got["notes"], ["value unsized", "points unsized"])


class TestCommand(RouteCase):
    def ledger(self, item) -> Path:
        path = self.root / "docs" / "proposals" / "99-x.json"
        path.parent.mkdir(parents=True)
        base = {"id": "Z-09", "phase": "Z", "cx": "C2", "title": "t", "status": "not started"}
        base.update(item)
        path.write_text(json.dumps({"proposal": 99, "title": "x", "status": "accepted",
                                    "phases": [{"id": "Z", "name": "b"}], "items": [base], "asks": []}))
        return path

    def run_route(self, *args):
        return subprocess.run([sys.executable, str(TRACKER), "route", *map(str, args)],
                              capture_output=True, text=True)

    def test_prints_the_route(self):
        path = self.ledger({"value": "medium", "points": 2, "cluster": "ui"})
        out = self.run_route(path, "Z-09")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Z-09", out.stdout)
        self.assertIn("gate and tests only", out.stdout)
        self.assertIn("bundle by cluster ui", out.stdout)

    def test_unknown_item_is_exit_1(self):
        path = self.ledger({})
        out = self.run_route(path, "Z-77")
        self.assertEqual(out.returncode, 1)
        self.assertIn("Z-77", out.stderr)

    def test_json(self):
        path = self.ledger({"risk": "restricted"})
        out = self.run_route(path, "Z-09", "--json")
        self.assertEqual(json.loads(out.stdout)["bundle"], "never bundled")


class TestBriefKeepsPointsFromTheBuilder(unittest.TestCase):
    def test_brief_has_no_points_placeholder_and_says_why(self):
        text = (ROOT / "templates" / "brief.md").read_text()
        self.assertNotIn("{{POINTS}}", text)
        self.assertIn("never carries the item's points", text)


if __name__ == "__main__":
    unittest.main()
