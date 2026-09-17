"""`tracker set` -- one item, changed and logged in one line (proposal 23,
lever L4, L-04), in place of the inline `python3 -` scripts that used to load
a ledger, edit one item and dump it back.

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

from tools.tracker import ledger as L  # noqa: E402
from tools.tracker import render as R  # noqa: E402

TRACKER = ROOT / "bin" / "tracker"


def fixture(**over):
    d = {
        "proposal": 99, "title": "fixture", "status": "accepted", "updated": "2026-01-01",
        "phases": [{"id": "W", "name": "build"}],
        "items": [
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "not started"},
            {"id": "W-02", "phase": "W", "cx": "C3", "title": "b", "status": "not started"},
        ],
        "asks": [],
    }
    d.update(over)
    return d


class TrackerSetCase(unittest.TestCase):
    """A temp copy of a small fixture ledger, per proposal 23's instruction."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "99-fixture.json"
        self.write(fixture())

    def write(self, data):
        self.ledger.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def read(self):
        return json.loads(self.ledger.read_text())

    def run_set(self, *args):
        return subprocess.run([sys.executable, str(TRACKER), "set", str(self.ledger), *args],
                              capture_output=True, text=True)

    def item(self, iid, data=None):
        return L.by_id(data or self.read())[iid]


class TestStatusAndAutoLog(TrackerSetCase):

    def test_status_change_appends_an_event_equal_to_the_status(self):
        before = self.ledger.read_bytes()
        r = self.run_set("W-01", "--status", "in progress")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotEqual(before, self.ledger.read_bytes())
        item = self.item("W-01")
        self.assertEqual("in progress", item["status"])
        self.assertEqual(1, len(item["log"]))
        self.assertEqual("in progress", item["log"][0]["event"])
        self.assertEqual("lead", item["log"][0]["by"])

    def test_stdout_is_exactly_one_line(self):
        r = self.run_set("W-01", "--status", "in progress")
        self.assertEqual(0, r.returncode, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(1, len(lines))
        self.assertTrue(lines[0].startswith("tracker set: W-01 "))
        self.assertIn("status in progress", lines[0])
        self.assertIn("page rendered", lines[0])


class TestCustomEvent(TrackerSetCase):

    def test_event_evidence_by_and_at_are_all_honoured(self):
        r = self.run_set("W-01", "--status", "in progress", "--event", "started",
                          "--evidence", "kickoff call", "--by", "the-sponsor", "--at",
                          "2026-01-02T09:00:00+05:30")
        self.assertEqual(0, r.returncode, r.stderr)
        item = self.item("W-01")
        entry = item["log"][-1]
        self.assertEqual("started", entry["event"])
        self.assertEqual("kickoff call", entry["evidence"])
        self.assertEqual("the-sponsor", entry["by"])
        self.assertEqual("2026-01-02T09:00:00+05:30", entry["at"])
        self.assertIn('log "started"', r.stdout)


class TestLogEntryStatusKey(TrackerSetCase):
    """RF-01: `--status` stamps the log entry's own `status` key too,
    independent of `--event`'s free text -- bin/conformance item 9 reads the
    close date from `status`, not `event`, since a lead's own `--event`
    wording does not reliably spell "done"."""

    def test_status_alone_stamps_the_log_entry_status_key(self):
        r = self.run_set("W-01", "--status", "done")
        self.assertEqual(0, r.returncode, r.stderr)
        entry = self.item("W-01")["log"][-1]
        self.assertEqual("done", entry.get("status"))
        self.assertEqual("done", entry["event"])

    def test_status_with_a_free_text_event_still_stamps_status(self):
        r = self.run_set("W-01", "--status", "done", "--event", "shipped in PR #99")
        self.assertEqual(0, r.returncode, r.stderr)
        entry = self.item("W-01")["log"][-1]
        self.assertEqual("done", entry.get("status"))
        self.assertEqual("shipped in PR #99", entry["event"])

    def test_event_without_status_never_stamps_a_status_key(self):
        r = self.run_set("W-01", "--event", "a note, no status change")
        self.assertEqual(0, r.returncode, r.stderr)
        entry = self.item("W-01")["log"][-1]
        self.assertNotIn("status", entry)

    def test_the_ledger_still_validates_with_a_status_keyed_entry(self):
        r = self.run_set("W-01", "--status", "done", "--event", "shipped")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual([], L.validate(self.read()))


class TestField(TrackerSetCase):

    def test_field_parses_json_when_valid(self):
        r = self.run_set("W-01", "--field", "weight=2")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(2, self.item("W-01")["weight"])

    def test_field_falls_back_to_a_string(self):
        r = self.run_set("W-01", "--field", "tag=[ruflo · low · haiku]")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("[ruflo · low · haiku]", self.item("W-01")["tag"])

    def test_forbidden_fields_are_refused(self):
        for key in ("id", "log", "phase"):
            before = self.ledger.read_bytes()
            r = self.run_set("W-01", "--field", f"{key}=x")
            self.assertEqual(1, r.returncode)
            self.assertEqual(before, self.ledger.read_bytes())


class TestUnknownItem(TrackerSetCase):

    def test_unknown_item_writes_nothing(self):
        before = self.ledger.read_bytes()
        r = self.run_set("W-99", "--status", "done")
        self.assertEqual(1, r.returncode)
        self.assertEqual(before, self.ledger.read_bytes())


class TestInvalidStatusLeavesFileUntouched(TrackerSetCase):

    def test_a_status_outside_the_vocabulary_writes_nothing(self):
        before = self.ledger.read_bytes()
        r = self.run_set("W-01", "--status", "wip")
        self.assertEqual(1, r.returncode)
        self.assertEqual(before, self.ledger.read_bytes())
        self.assertIn("wip", r.stderr)


class TestPageIsRendered(TrackerSetCase):

    def test_render_check_passes_after_set(self):
        r = self.run_set("W-01", "--status", "done", "--event", "merged")
        self.assertEqual(0, r.returncode, r.stderr)
        check = subprocess.run([sys.executable, str(TRACKER), "render", str(self.ledger), "--check"],
                               capture_output=True, text=True)
        self.assertEqual(0, check.returncode, check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
