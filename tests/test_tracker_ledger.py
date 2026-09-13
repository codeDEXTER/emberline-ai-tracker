"""The ledger contract every tracker command builds on (proposal 19, W-00).

The strongest test here is the real one: the PhotoVault engine's proposal 71
ledger -- 39 items, 58 commits in one day -- must load and validate unchanged,
because the standard is lifted from it. When that file is not on this machine
the test says so and skips rather than passing vacuously.

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

from tools.tracker import ledger  # noqa: E402

ENGINE_71 = Path("/Users/aashish/apps/PhotoVault/engine/docs/proposals/71-engine-1-3-programme.json")
TRACKER = ROOT / "bin" / "tracker"


def minimal(**over):
    d = {
        "proposal": 19, "title": "t", "status": "accepted",
        "phases": [{"id": "W", "name": "build"}],
        "items": [
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "done",
             "log": [{"at": "2026-09-13T20:00:00+02:00", "event": "merged", "by": "lead", "evidence": "abc123"}]},
            {"id": "W-02", "phase": "W", "cx": "C3", "title": "b", "status": "not started", "depends": "W-01"},
            {"id": "W-03", "phase": "W", "cx": "C2", "title": "c", "status": "not started", "depends": ["W-02"]},
        ],
        "asks": [{"id": "A-01", "at": "2026-09-13", "kind": "research", "quote": "look into it",
                  "became": None, "state": "open"}],
    }
    d.update(over)
    return d


class TestShape(unittest.TestCase):

    def test_a_well_formed_ledger_has_no_problems(self):
        self.assertEqual([], ledger.validate(minimal()))

    def test_both_spellings_of_a_list_are_read(self):
        self.assertEqual(["R-01", "R-02"], ledger.as_list("R-01 R-02"))
        self.assertEqual(["a.py", "b.py"], ledger.as_list("a.py, b.py"))
        self.assertEqual(["x"], ledger.as_list(["x", " "]))
        self.assertEqual([], ledger.as_list(""))
        self.assertEqual([], ledger.as_list(None))

    def test_counts_always_carry_all_four_states_in_order(self):
        c = ledger.counts(minimal())
        self.assertEqual(["done", "in progress", "blocked", "not started"], list(c))
        self.assertEqual("1 done / 0 in progress / 0 blocked / 2 not started", ledger.status_line(minimal()))

    def test_unblocked_means_every_dependency_is_done(self):
        self.assertEqual(["W-02"], [i["id"] for i in ledger.unblocked(minimal())])

    def test_open_asks_are_found(self):
        self.assertEqual(["A-01"], [a["id"] for a in ledger.open_asks(minimal())])


class TestProblemsAreNamed(unittest.TestCase):

    def problems(self, d):
        return "\n".join(ledger.validate(d))

    def test_a_status_outside_the_vocabulary(self):
        d = minimal(); d["items"][1]["status"] = "wip"
        self.assertIn("W-02: status 'wip'", self.problems(d))

    def test_a_duplicate_id(self):
        d = minimal(); d["items"][2]["id"] = "W-02"
        self.assertIn("W-02: id appears more than once", self.problems(d))

    def test_a_dependency_on_nothing(self):
        d = minimal(); d["items"][1]["depends"] = "W-99"
        self.assertIn("W-02: depends on W-99", self.problems(d))

    def test_done_with_no_log_is_a_claim_without_evidence(self):
        d = minimal(); d["items"][0]["log"] = []
        self.assertIn("W-01: done with an empty log", self.problems(d))

    def test_discovered_from_must_resolve(self):
        d = minimal(); d["items"][2]["discovered_from"] = "X-09"
        self.assertIn("discovered_from X-09", self.problems(d))
        d["items"][2]["discovered_from"] = "A-01"
        self.assertNotIn("discovered_from", self.problems(d))

    def test_an_ask_without_the_sponsors_words(self):
        d = minimal(); d["asks"][0]["quote"] = ""
        self.assertIn("A-01: no `quote`", self.problems(d))

    def test_an_ask_that_became_nothing(self):
        d = minimal(); d["asks"][0]["state"] = "became-item"
        self.assertIn("A-01: became-item but `became` names nothing", self.problems(d))


class TestTheRealLedger(unittest.TestCase):

    @unittest.skipUnless(ENGINE_71.exists(), f"{ENGINE_71} is not on this machine")
    def test_the_engine_ledger_the_standard_was_lifted_from_validates(self):
        d = ledger.load(ENGINE_71)
        self.assertEqual([], ledger.validate(d), "the loader rejects the ledger it was modelled on")
        self.assertGreaterEqual(len(ledger.items(d)), 30)


class TestTheCommand(unittest.TestCase):

    def run_tracker(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(TRACKER), *args], capture_output=True,
                              text=True, cwd=cwd, check=False)

    def test_validate_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "19-x.json"; good.write_text(json.dumps(minimal()))
            bad_d = minimal(); bad_d["items"][0]["status"] = "wip"
            bad = Path(tmp) / "20-y.json"; bad.write_text(json.dumps(bad_d))
            self.assertEqual(0, self.run_tracker("validate", str(good)).returncode)
            r = self.run_tracker("validate", str(bad))
            self.assertEqual(1, r.returncode)
            self.assertIn("status 'wip'", r.stdout)
            broken = Path(tmp) / "21-z.json"; broken.write_text("{nope")
            self.assertEqual(2, self.run_tracker("validate", str(broken)).returncode)

    def test_an_unbuilt_command_says_so_rather_than_crashing(self):
        r = self.run_tracker("import")
        self.assertEqual(2, r.returncode)
        self.assertIn("not built yet", r.stderr)


if __name__ == "__main__":
    unittest.main()
