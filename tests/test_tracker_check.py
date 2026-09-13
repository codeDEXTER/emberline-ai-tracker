"""`tracker check` -- did the ledger move with the code? (proposal 19, W-03)

The rule it enforces: a branch whose commits name a ledger item must also
move that item's row. "Moved" is read from git, not from a clock: the item's
JSON object differs between the merge-base and the branch tip -- a new row,
a new log entry, a status change. A timestamp typed into a log by an agent
is not evidence that anything happened on this branch; the diff is.

Only ids that exist in a ledger count, so a commit saying "SHA-256" or
"UTF-16" is never mistaken for an item.

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
TRACKER = ROOT / "bin" / "tracker"
LEDGER = "docs/proposals/19-proposal-warmup.json"


def ledger(**status_and_logs):
    items = []
    for iid, (status, log) in status_and_logs.items():
        items.append({"id": iid, "phase": "W", "cx": "C2", "title": iid.lower(),
                      "status": status, "log": log})
    return {"proposal": 19, "title": "Warm-up", "status": "accepted",
            "phases": [{"id": "W", "name": "build"}], "items": items, "asks": []}


ENTRY = {"at": "2026-09-13T21:00:00+02:00", "event": "started", "by": "lead", "evidence": "x"}


class Repo:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write("README.md", "seed\n")
        self.write(LEDGER, json.dumps(ledger(**{"W-01": ("not started", []),
                                                "W-02": ("not started", [])}), indent=2))
        self.commit("seed")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.root), *a], capture_output=True, text=True, check=False)

    def write(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def branch(self, name):
        self.git("checkout", "-q", "-b", name)

    def check(self, *extra):
        return subprocess.run([sys.executable, str(TRACKER), "check", "--project", str(self.root), *extra],
                              capture_output=True, text=True, check=False)

    def close(self):
        self.tmp.cleanup()


class CheckCase(unittest.TestCase):
    def setUp(self):
        self.r = Repo()
        self.r.branch("feature")

    def tearDown(self):
        self.r.close()


class TestMoved(CheckCase):

    def test_naming_an_item_and_moving_its_row_passes(self):
        self.r.write("README.md", "seed\nwork\n")
        self.r.write(LEDGER, json.dumps(ledger(**{"W-01": ("in progress", [ENTRY]),
                                                  "W-02": ("not started", [])}), indent=2))
        self.r.commit("W-01 start the templates")
        out = self.r.check()
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertIn("W-01", out.stdout)

    def test_the_row_may_move_in_a_later_commit_of_the_same_branch(self):
        self.r.write("README.md", "seed\nwork\n")
        self.r.commit("W-01 the work")
        self.r.write(LEDGER, json.dumps(ledger(**{"W-01": ("done", [ENTRY]),
                                                  "W-02": ("not started", [])}), indent=2))
        self.r.commit("ledger: W-01 done")
        self.assertEqual(0, self.r.check().returncode)

    def test_a_row_added_on_the_branch_counts_as_moved(self):
        d = ledger(**{"W-01": ("not started", []), "W-02": ("not started", []), "W-03": ("not started", [])})
        self.r.write(LEDGER, json.dumps(d, indent=2))
        self.r.commit("W-03 new item")
        self.assertEqual(0, self.r.check().returncode)


class TestNotMoved(CheckCase):

    def test_naming_an_item_without_moving_its_row_is_a_finding(self):
        self.r.write("README.md", "seed\nwork\n")
        self.r.commit("W-02 build the renderer")
        out = self.r.check()
        self.assertEqual(1, out.returncode)
        self.assertIn("W-02", out.stdout)
        self.assertIn("did not move", out.stdout)

    def test_moving_one_row_does_not_cover_another_named_item(self):
        self.r.write(LEDGER, json.dumps(ledger(**{"W-01": ("in progress", [ENTRY]),
                                                  "W-02": ("not started", [])}), indent=2))
        self.r.commit("W-01 and W-02 together")
        out = self.r.check()
        self.assertEqual(1, out.returncode)
        self.assertIn("W-02", out.stdout)
        self.assertNotIn("W-01 did not move", out.stdout)


class TestWhatDoesNotCount(CheckCase):

    def test_an_id_shape_that_is_not_an_item_is_ignored(self):
        self.r.write("README.md", "seed\nhash\n")
        self.r.commit("use SHA-256 and UTF-16 for the digest")
        self.assertEqual(0, self.r.check().returncode)

    def test_a_branch_naming_no_item_passes(self):
        self.r.write("README.md", "seed\ntypo\n")
        self.r.commit("fix a typo")
        self.assertEqual(0, self.r.check().returncode)

    def test_a_project_with_no_ledger_passes_and_says_so(self):
        self.r.git("checkout", "-q", "main")
        self.r.git("rm", "-q", LEDGER)
        self.r.commit("no ledger")
        self.r.git("checkout", "-q", "-b", "other")
        self.r.write("README.md", "seed\nx\n")
        self.r.commit("W-01 anyway")
        out = self.r.check()
        self.assertEqual(0, out.returncode)
        self.assertIn("no ledger", out.stdout)

    def test_a_ref_that_does_not_exist_is_exit_2(self):
        self.assertEqual(2, self.r.check("--base", "no-such-branch").returncode)


if __name__ == "__main__":
    unittest.main()
