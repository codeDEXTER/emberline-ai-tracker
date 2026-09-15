"""`tracker findings` -- findings-as-ledger-rows, the shared share/risk queue
with items, catalogue/decide/defer/decline, triage into batches
(proposal 26, C-05).

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
from tools.tracker import findings as F  # noqa: E402
from tools.tracker import ledger as L  # noqa: E402

TRACKER = ROOT / "bin" / "tracker"


def finding(fid, source="review", file="x.py", severity="low", state="catalogued", **more):
    d = {"id": fid, "source": source, "file": file, "severity": severity, "state": state}
    d.update(more)
    return d


def item(iid, value=None, points=None, impact=None, likelihood=None, status="not started", **more):
    d = {"id": iid, "phase": "Q", "cx": "C2", "title": iid.lower(), "status": status}
    for k, v in (("value", value), ("points", points), ("impact", impact), ("likelihood", likelihood)):
        if v is not None:
            d[k] = v
    d.update(more)
    return d


def base_ledger(items=(), findings=()):
    return {"proposal": 99, "title": "t", "status": "accepted", "updated": "2026-01-01",
            "phases": [{"id": "Q", "name": "q"}], "items": list(items), "findings": list(findings), "asks": []}


class FindingsCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / P.FILE).write_text(json.dumps({"risk_paths": {"restricted": ["finance_data/*"]}}))


# ---------------------------------------------------------------------------
# Validation: findings are ledger rows, checked by tools/tracker/ledger.py.

class TestValidation(unittest.TestCase):
    def test_a_well_formed_finding_validates(self):
        d = base_ledger(findings=[finding("F-01", value="low", points=2, impact=1, likelihood=1)])
        self.assertEqual(L.validate(d), [])

    def test_bad_id_source_severity_state_are_each_named(self):
        d = base_ledger(findings=[{"id": "bad", "source": "nope", "file": "", "severity": "??", "state": "??"}])
        problems = L.validate(d)
        self.assertTrue(any("finding id is not F-NN" in p for p in problems))
        self.assertTrue(any("source" in p for p in problems))
        self.assertTrue(any("no `file`" in p for p in problems))
        self.assertTrue(any("severity" in p for p in problems))
        self.assertTrue(any("state" in p for p in problems))

    def test_duplicate_of_must_name_another_finding_and_declined_state(self):
        d = base_ledger(findings=[
            finding("F-01", state="declined", duplicate_of="F-02"),  # fine: names a real finding, declined
            finding("F-02", state="catalogued"),
            finding("F-03", state="catalogued", duplicate_of="F-99"),  # F-99 does not exist
            finding("F-04", state="catalogued", duplicate_of="F-04"),  # names itself
        ])
        problems = L.validate(d)
        self.assertTrue(any("F-03" in p and "not a finding" in p for p in problems))
        self.assertTrue(any("F-04" in p and "names itself" in p for p in problems))
        self.assertTrue(any("F-03" in p and "duplicate_of is set but state is not declined" in p for p in problems))
        self.assertFalse(any(p.startswith("F-01:") and "state is not declined" in p for p in problems))

    def test_findings_must_be_a_list(self):
        d = base_ledger()
        d["findings"] = "nope"
        self.assertIn("findings: must be a list", L.validate(d))

    def test_an_item_id_and_a_finding_id_never_collide_in_shape(self):
        self.assertFalse(L.FINDING_ID.match("Q-01"))
        self.assertTrue(L.FINDING_ID.match("F-01"))


# ---------------------------------------------------------------------------
# Lifecycle: catalogue (add) -> decide -> defer / decline.

class TestLifecycle(FindingsCase):
    def test_add_catalogues_with_a_log_entry(self):
        d = base_ledger()
        fid = F.add(d, source="review", file="tools/x.py", line=12, severity="low", by="quality-manager")
        self.assertEqual(fid, "F-01")
        f = L.findings_by_id(d)["F-01"]
        self.assertEqual(f["state"], "catalogued")
        self.assertEqual(f["log"][-1]["event"], "catalogued")
        self.assertEqual(L.validate(d), [])

    def test_ids_increment(self):
        d = base_ledger()
        F.add(d, source="review", file="a.py", severity="low")
        fid2 = F.add(d, source="test", file="b.py", severity="medium")
        self.assertEqual(fid2, "F-02")

    def test_decide_moves_state_and_can_set_size(self):
        d = base_ledger(findings=[finding("F-01")])
        f = F.decide(d, "F-01", quote="ship it small", value="low", points=2, impact=1, likelihood=1)
        self.assertEqual(f["state"], "decided")
        self.assertEqual((f["value"], f["points"]), ("low", 2))
        self.assertEqual(f["log"][-1]["evidence"], "ship it small")

    def test_decide_unknown_finding_is_none(self):
        d = base_ledger()
        self.assertIsNone(F.decide(d, "F-77", quote="x"))

    def test_defer_keeps_it_visible_not_declined(self):
        d = base_ledger(findings=[finding("F-01")])
        f = F.defer(d, "F-01", quote="later")
        self.assertEqual(f["state"], "deferred")

    def test_decline_with_duplicate_of(self):
        d = base_ledger(findings=[finding("F-01"), finding("F-02")])
        f = F.decline(d, "F-02", quote="same as F-01", duplicate_of="F-01")
        self.assertEqual(f["state"], "declined")
        self.assertEqual(f["duplicate_of"], "F-01")
        self.assertEqual(L.validate(d), [])

    def test_a_catalogued_finding_stays_a_catalogued_finding_until_decided(self):
        d = base_ledger(findings=[finding("F-01", value="low", points=1, impact=1, likelihood=1)])
        result = F.lanes([d], self.root)
        row = {r["id"]: r for r in result["items"]}["F-01"]
        self.assertIn(row["lane"], ("Now", "Daily", "Weekly", "When touched", "Unscored"))
        self.assertEqual(L.findings_by_id(d)["F-01"]["state"], "catalogued")


# ---------------------------------------------------------------------------
# Shared lane sort: findings and items in one queue, the same 80% cut (C-02).

# Mirrors tests/test_tracker_lanes.py's fixture: raw shares
# I-01 3x13=39, I-02 3x8=24, F-01 2x5=10 (finding, same share as an item
# would get), I-03 1x5=5, F-02 2x1=2 -> total 80.
QUEUE_ITEMS = [
    item("I-01", "high", 13, impact=2, likelihood=1),
    item("I-02", "high", 8, impact=1, likelihood=1),
    item("I-03", "low", 5, impact=2, likelihood=2),
]
QUEUE_FINDINGS = [
    finding("F-01", state="decided", value="medium", points=5, impact=3, likelihood=1),
    finding("F-02", state="catalogued", value="medium", points=1, impact=1, likelihood=1),
]


class TestSharedLaneSort(FindingsCase):
    def ledger(self):
        return base_ledger(items=QUEUE_ITEMS, findings=QUEUE_FINDINGS)

    def test_a_finding_and_an_item_with_the_same_share_are_adjacent(self):
        # An item and a finding sized to the identical raw share (3x8=24 and
        # 2x12=24) sort next to each other, not split apart by kind.
        d = base_ledger(
            items=[item("I-09", "high", 8)],
            findings=[finding("F-09", state="decided", value="medium", points=12)],
        )
        result = F.lanes([d], self.root)
        ids = [r["id"] for r in result["items"]]
        self.assertEqual(set(ids), {"I-09", "F-09"})
        # Only two rows: they are trivially adjacent; assert their shares match.
        rows = {r["id"]: r for r in result["items"]}
        self.assertAlmostEqual(rows["I-09"]["share"], rows["F-09"]["share"])

    def test_finding_and_item_interleave_by_share_not_kind(self):
        d = self.ledger()
        result = F.lanes([d], self.root)
        ids = [r["id"] for r in result["items"]]
        # By raw share: I-01 39, I-02 24, F-01 10, I-03 5, F-02 2.
        self.assertEqual(ids, ["I-01", "I-02", "F-01", "I-03", "F-02"])

    def test_the_80_percent_cut_applies_across_both_kinds(self):
        d = self.ledger()
        result = F.lanes([d], self.root)
        rows = {r["id"]: r for r in result["items"]}
        # Cumulative: 48.75%, 78.75%, 91.25% (crosses -> Now), 97.5%, 100%.
        self.assertEqual(rows["I-01"]["lane"], "Now")
        self.assertEqual(rows["I-02"]["lane"], "Now")
        self.assertEqual(rows["F-01"]["lane"], "Now")  # the finding that crosses 80%
        self.assertNotEqual(rows["I-03"]["lane"], "Now")
        self.assertNotEqual(rows["F-02"]["lane"], "Now")

    def test_a_declined_finding_is_left_out_like_a_done_item(self):
        d = base_ledger(
            items=[item("I-01", "high", 5)],
            findings=[finding("F-01", state="declined", value="low", points=1, duplicate_of=None)],
        )
        result = F.lanes([d], self.root)
        self.assertNotIn("F-01", {r["id"] for r in result["items"]})

    def test_restricted_finding_is_alone(self):
        d = base_ledger(findings=[finding("F-01", state="decided", value="low", points=1,
                                           file="finance_data/book.json")])
        result = F.lanes([d], self.root)
        row = {r["id"]: r for r in result["items"]}["F-01"]
        self.assertTrue(row["alone"])
        self.assertEqual(row["risk"], 9)


# ---------------------------------------------------------------------------
# Light path: decided, small, not alone.

class TestLightPath(FindingsCase):
    def test_decided_small_standard_finding_is_light(self):
        d = base_ledger(findings=[finding("F-01", state="decided", value="low", points=2, impact=1, likelihood=1)])
        self.assertEqual(F.light_eligible(d, self.root), ["F-01"])

    def test_catalogued_finding_is_not_light_yet(self):
        d = base_ledger(findings=[finding("F-01", state="catalogued", value="low", points=2, impact=1, likelihood=1)])
        self.assertEqual(F.light_eligible(d, self.root), [])

    def test_restricted_or_high_risk_finding_is_never_light(self):
        d = base_ledger(findings=[
            finding("F-01", state="decided", value="low", points=1, file="finance_data/book.json"),
            finding("F-02", state="decided", value="low", points=1, impact=4, likelihood=3),
        ])
        self.assertEqual(F.light_eligible(d, self.root), [])

    def test_big_decided_finding_is_never_light(self):
        d = base_ledger(findings=[finding("F-01", state="decided", value="high", points=8, impact=1, likelihood=1)])
        self.assertEqual(F.light_eligible(d, self.root), [])

    def test_review_and_test_findings_both_batch_together(self):
        d = base_ledger(findings=[
            finding("F-01", source="review", state="decided", value="low", points=2, impact=1, likelihood=1),
            finding("F-02", source="test", state="decided", value="low", points=1, impact=1, likelihood=1),
        ])
        self.assertEqual(set(F.light_eligible(d, self.root)), {"F-01", "F-02"})


# ---------------------------------------------------------------------------
# Triage: shared root cause groups, duplicates excluded.

class TestTriage(unittest.TestCase):
    def test_two_findings_sharing_a_root_cause_group_to_one_line(self):
        d = base_ledger(findings=[
            finding("F-01", state="decided", cause="missing null check", fix="add guard"),
            finding("F-02", source="test", state="decided", cause="missing null check"),
            finding("F-03", state="decided"),
        ])
        groups = F.triage(["F-01", "F-02", "F-03"], d)
        self.assertEqual(len(groups), 2)
        by_cause = {g["cause"]: g for g in groups}
        self.assertEqual(by_cause["missing null check"]["findings"], ["F-01", "F-02"])
        self.assertEqual(by_cause["missing null check"]["fix"], "add guard")

    def test_a_duplicate_finding_is_declined_and_excluded_from_the_count(self):
        d = base_ledger(findings=[
            finding("F-01", state="decided", cause="c"),
            finding("F-02", state="declined", duplicate_of="F-01"),
        ])
        groups = F.triage(["F-01", "F-02"], d)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["findings"], ["F-01"])

    def test_log_lines_are_one_per_group(self):
        d = base_ledger(findings=[
            finding("F-01", state="decided", cause="c", fix="do x"),
            finding("F-02", state="decided", cause="c"),
            finding("F-03", state="decided"),
        ])
        groups = F.triage(["F-01", "F-02", "F-03"], d)
        lines = F.triage_log_lines(groups)
        self.assertEqual(len(lines), 2)
        self.assertIn("F-01, F-02 -> do x", lines[0])


# ---------------------------------------------------------------------------
# CLI round trip.

class TestCommand(FindingsCase):
    def ledger_path(self, findings=()):
        path = self.root / "docs" / "proposals" / "99-q.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(base_ledger(items=[item("I-01", "high", 5)], findings=list(findings))))
        return path

    def run_findings(self, *args):
        return subprocess.run([sys.executable, str(TRACKER), "findings", *map(str, args)],
                              capture_output=True, text=True)

    def test_add_writes_and_renders(self):
        path = self.ledger_path()
        out = self.run_findings("add", path, "--source", "review", "--file", "a.py", "--severity", "low")
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(path.read_text())
        self.assertEqual(data["findings"][0]["id"], "F-01")
        self.assertTrue((path.parent / "tracker" / "99-q.html").exists())

    def test_decide_then_decline_round_trip(self):
        path = self.ledger_path(findings=[finding("F-01")])
        out = self.run_findings("decide", path, "F-01", "--quote", "go", "--value", "low", "--points", "2")
        self.assertEqual(out.returncode, 0, out.stderr)
        out = self.run_findings("decline", path, "F-01", "--quote", "actually no")
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(path.read_text())
        self.assertEqual(data["findings"][0]["state"], "declined")

    def test_unknown_finding_id_is_exit_1_and_writes_nothing(self):
        path = self.ledger_path()
        before = path.read_text()
        out = self.run_findings("decide", path, "F-77", "--quote", "x")
        self.assertEqual(out.returncode, 1)
        self.assertEqual(path.read_text(), before)

    def test_lanes_json_includes_items_and_findings(self):
        path = self.ledger_path(findings=[finding("F-01", state="decided", value="low", points=1,
                                                    impact=1, likelihood=1)])
        out = self.run_findings("lanes", path, "--json")
        self.assertEqual(out.returncode, 0, out.stderr)
        ids = {r["id"] for r in json.loads(out.stdout)["items"]}
        self.assertEqual(ids, {"I-01", "F-01"})

    def test_triage_prints_one_line_per_group(self):
        path = self.ledger_path(findings=[
            finding("F-01", state="decided", cause="c", fix="fix it"),
            finding("F-02", state="decided", cause="c"),
        ])
        out = self.run_findings("triage", path, "--batch", "F-01", "F-02")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(len(out.stdout.strip().splitlines()), 1)
        self.assertIn("fix it", out.stdout)


if __name__ == "__main__":
    unittest.main()
