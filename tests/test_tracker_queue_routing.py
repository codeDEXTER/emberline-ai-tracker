"""A row `warmup --queue` writes is routed from the ledger's own tiers table.

Rows used to be written with `cx: C2` and no tier, model or tag at all, so
every project that ran `--queue` -- which the standard makes routine --
failed conformance item 6 on the very rows the standard had just asked it to
record. Found 2026-09-16 when common-rules' own reheat queued two rows and
conformance dropped from 12 to 11 on them.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import ledger as L  # noqa: E402
from tools.tracker import queue as Q  # noqa: E402


def ledger(tiers=True):
    d = {
        "proposal": 99, "title": "fixture", "status": "accepted", "updated": "2026-01-01",
        "phases": [{"id": "W", "name": "build"}],
        "items": [{"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "not started"}],
        "asks": [],
    }
    if tiers:
        d["tiers"] = {
            "C2": {"tier": "medium", "model": "sonnet", "effort": "medium", "rule": "bounded"},
            "C4": {"tier": "lead", "model": "opus", "effort": "low or medium", "rule": "lead"},
        }
    return d


class QueueCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "docs" / "proposals").mkdir(parents=True)
        self.path = root / "docs" / "proposals" / "99-fixture.json"

    def write(self, data):
        self.path.write_text(json.dumps(data, indent=2) + "\n")

    def queued(self):
        rows = [i for i in L.items(json.loads(self.path.read_text())) if i.get("queue_source")]
        self.assertEqual(1, len(rows))
        return rows[0]


class TestQueuedRowIsRouted(QueueCase):

    def test_the_row_carries_tier_model_and_tag_from_the_ledgers_own_table(self):
        self.write(ledger())
        self.assertTrue(Q.queue(self.path, "standard item 4", "conformance:4"))
        row = self.queued()
        tier = json.loads(self.path.read_text())["tiers"][row["cx"]]
        self.assertEqual(tier["tier"], row["tier"])
        self.assertEqual(tier["model"], row["model"])
        self.assertEqual(f"[ruflo · {tier['tier']} · {tier['model']}]", row["tag"])

    def test_the_route_follows_the_table_rather_than_a_hardcoded_model(self):
        """A project that routes C2 elsewhere gets its own model, not ours --
        the tier change of 2026-09-16 broke every generator that hardcoded one."""
        d = ledger()
        d["tiers"]["C2"] = {"tier": "medium", "model": "haiku", "effort": "low", "rule": "cheap"}
        self.write(d)
        Q.queue(self.path, "standard item 4", "conformance:4")
        self.assertEqual("haiku", self.queued()["model"])
        self.assertEqual("[ruflo · medium · haiku]", self.queued()["tag"])

    def test_a_ledger_with_no_tiers_table_still_queues(self):
        self.write(ledger(tiers=False))
        self.assertTrue(Q.queue(self.path, "standard item 4", "conformance:4"))
        self.assertNotIn("tag", self.queued())


if __name__ == "__main__":
    unittest.main()
