"""`tracker ask` -- a sponsor ask recorded as the next A-nn, in his own words
(proposal 23, lever L4, L-04): "every sponsor message that is not an answer
becomes an ask row A-nn quoting his words" (docs/OPERATING-RULES.md section 1).

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

TRACKER = ROOT / "bin" / "tracker"


def fixture(**over):
    d = {
        "proposal": 99, "title": "fixture", "status": "accepted", "updated": "2026-01-01",
        "phases": [{"id": "W", "name": "build"}],
        "items": [{"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "not started"}],
        "asks": [
            {"id": "A-01", "at": "2026-01-01", "kind": "research", "quote": "look into it",
             "became": None, "state": "open"},
            {"id": "A-07", "at": "2026-01-01", "kind": "decision", "quote": "ship it",
             "became": None, "state": "answered"},
        ],
    }
    d.update(over)
    return d


class TrackerAskCase(unittest.TestCase):

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

    def run_ask(self, *args):
        return subprocess.run([sys.executable, str(TRACKER), "ask", str(self.ledger), *args],
                              capture_output=True, text=True)


class TestNumbering(TrackerAskCase):

    def test_continues_from_the_highest_existing_id(self):
        r = self.run_ask("--kind", "question", "--quote", "what about the tests?")
        self.assertEqual(0, r.returncode, r.stderr)
        asks = self.read()["asks"]
        self.assertEqual("A-08", asks[-1]["id"])

    def test_starts_at_a_01_when_none_exist(self):
        self.write(fixture(asks=[]))
        r = self.run_ask("--kind", "feature", "--quote", "add dark mode")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("A-01", self.read()["asks"][-1]["id"])


class TestDefaultsAndFields(TrackerAskCase):

    def test_defaults_state_open_and_by_sponsor(self):
        self.run_ask("--kind", "question", "--quote", "why not?")
        ask = self.read()["asks"][-1]
        self.assertEqual("open", ask["state"])
        self.assertEqual("sponsor", ask["by"])

    def test_became_is_recorded(self):
        r = self.run_ask("--kind", "feature", "--quote", "do X", "--became", "W-01")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("W-01", self.read()["asks"][-1]["became"])

    def test_quote_is_preserved_verbatim(self):
        quote = 'he said "just do it, typo included: teh thing"'
        r = self.run_ask("--kind", "decision", "--quote", quote)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(quote, self.read()["asks"][-1]["quote"])

    def test_trailing_newline_is_trimmed_once(self):
        r = self.run_ask("--kind", "decision", "--quote", "ship it\n\n")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("ship it\n", self.read()["asks"][-1]["quote"])


class TestOutput(TrackerAskCase):

    def test_stdout_is_exactly_one_line(self):
        r = self.run_ask("--kind", "decision", "--quote", "ship it", "--state", "answered")
        self.assertEqual(0, r.returncode, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(1, len(lines))
        self.assertEqual("tracker ask: A-08 decision answered", lines[0])


class TestPageIsRendered(TrackerAskCase):

    def test_render_check_passes_after_ask(self):
        r = self.run_ask("--kind", "question", "--quote", "why?")
        self.assertEqual(0, r.returncode, r.stderr)
        check = subprocess.run([sys.executable, str(TRACKER), "render", str(self.ledger), "--check"],
                               capture_output=True, text=True)
        self.assertEqual(0, check.returncode, check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
