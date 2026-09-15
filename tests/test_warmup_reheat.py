"""bin/warmup --reheat and --queue (proposal 28, R-01).

--reheat is --since against a state file warmup keeps for itself, with the
standard's own status (conformance + mandatory-pending) always appended.
--queue writes: each non-holding conformance item and each pending mandatory
Standard change becomes a ledger item, owner lead, status not started,
first in the ledger's own item list -- idempotent, so a second run adds
nothing for a source already queued.

Run:  python3 -m unittest discover -s tests -p 'test_warmup_reheat.py' -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_warmup import Project  # noqa: E402
from test_rulecheck import FakeRules  # noqa: E402

WARMUP = ROOT / "bin" / "warmup"


class ReheatCase(unittest.TestCase):

    def setUp(self):
        self.p = Project(seeded=True)
        self.rules = FakeRules(Path(self.p.tmp.name))

    def tearDown(self):
        self.p.close()

    def stamp(self, version):
        self.p.write(".common-rules-version", version + "\n")

    def warm(self, *args):
        import os
        env = {**os.environ, "COMMON_RULES_DIR": str(self.rules.root)}
        # --no-pull: bin/warmup's own RULES_DIR (unlike rulecheck's, which
        # honours COMMON_RULES_DIR) is still the real common-rules checkout
        # in a test run -- R-05's fetch/pull must never touch it.
        return subprocess.run([sys.executable, str(WARMUP), "--project", str(self.p.root),
                               "--no-recall", "--no-pull", *args],
                              capture_output=True, text=True, check=False, env=env)

    def ledger_items(self):
        data = json.loads((self.p.root / "docs" / "proposals" / "19-proposal-warmup.json").read_text())
        return data["items"]


class TestQueueOnThePlainCard(ReheatCase):

    def test_a_pending_mandatory_change_is_queued(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        r = self.warm("--queue")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("queued standard:", r.stdout)
        titles = [i["title"] for i in self.ledger_items()]
        self.assertTrue(any("Reheat is mandatory" in t for t in titles), titles)
        queued = [i for i in self.ledger_items() if i.get("phase") == "Q"]
        for i in queued:
            self.assertEqual("not started", i["status"])
            self.assertEqual("lead", i["owner"])
        # placed first
        self.assertEqual(queued[0]["id"], self.ledger_items()[0]["id"])

    def test_without_queue_nothing_is_written(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        before = (self.p.root / "docs" / "proposals" / "19-proposal-warmup.json").read_text()
        r = self.warm()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("Reheat is mandatory", r.stdout)  # shown
        after = (self.p.root / "docs" / "proposals" / "19-proposal-warmup.json").read_text()
        self.assertEqual(before, after)  # never written


class TestQueueOnReheat(ReheatCase):

    def test_first_reheat_prints_the_full_card_plus_standard_and_queues(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        r = self.warm("--reheat", "--queue")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("no earlier state", r.stdout)
        self.assertIn("standard:", r.stdout)
        self.assertIn("queued standard:", r.stdout)
        titles = [i["title"] for i in self.ledger_items()]
        self.assertTrue(any("Reheat is mandatory" in t for t in titles), titles)

    def test_a_second_reheat_is_a_delta_and_still_shows_the_standard(self):
        self.stamp(self.rules.version())
        self.warm("--reheat")  # writes the default state file
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        r = self.warm("--reheat")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("no earlier state", r.stdout)
        self.assertIn("standard:", r.stdout)


class TestQueueIsIdempotent(ReheatCase):

    def test_a_second_queue_run_adds_nothing_new(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        self.warm("--queue")
        n_after_first = len(self.ledger_items())
        r = self.warm("--queue")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("nothing new", r.stdout)
        self.assertEqual(n_after_first, len(self.ledger_items()))


class TestNothingQueuedWhenAligned(ReheatCase):

    def test_no_mandatory_standard_change_is_queued_once_aligned(self):
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        self.stamp(self.rules.version())  # stamped past the only entry
        r = self.warm("--queue")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        titles = [i["title"] for i in self.ledger_items()]
        self.assertFalse(any("mandatory Standard change" in t for t in titles), titles)


class TestContextReachesTheCard(ReheatCase):

    def test_context_on_the_card(self):
        r = self.warm("--context", "picking up where the last session left off")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("Context: picking up where the last session left off", r.stdout)

    def test_context_in_json(self):
        r = self.warm("--context", "a note for the state file", "--json")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual("a note for the state file", data["context"])


if __name__ == "__main__":
    unittest.main()
