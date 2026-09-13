"""`bin/land` refuses a branch that names a ledger item and did not move its row.

Proposal 19, W-03. Prose rules measured 1-in-7 compliance in this repo; the
executable ones get used. "The ledger row moves in the same turn as the state"
was the engine's best habit on its best day (58 ledger commits on 13 Sep) and
it arrived on day eight. This is what makes it unconditional: `tracker check`
exits 1 for a branch whose commits name an item whose row did not move, and
this gate consumes that exit code in the same PR that added the checker --
the lesson of #106/#107, where a checker shipped with nothing calling it.

Mirrors tests/test_land_proposalcheck.py: a throwaway repo, `land --check`,
the stamp written at the current rules version so only this gate is under
test.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAND = ROOT / "bin" / "land"
RULECHECK = ROOT / "bin" / "rulecheck"
STAMP = ".common-rules-version"
LEDGER = "docs/proposals/19-proposal-warmup.json"

REFUSAL = "ledger row did not move"


def current_rules_version() -> str:
    return subprocess.run([str(RULECHECK), "--version"], capture_output=True,
                          text=True, check=True).stdout.strip()


def ledger(status="not started", log=None):
    return json.dumps({
        "proposal": 19, "title": "Warm-up", "status": "accepted",
        "phases": [{"id": "W", "name": "build"}],
        "items": [{"id": "W-01", "phase": "W", "cx": "C2", "title": "templates",
                   "status": status, "log": log or []}],
        "asks": []}, indent=2)


class LandHarness(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "proj"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.repo / "README.md").write_text("seed\n")
        self.write(LEDGER, ledger())
        self.git("add", "-A"); self.git("commit", "-qm", "seed")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a], capture_output=True, text=True, check=False)

    def write(self, rel, body):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def stamp_main(self):
        self.git("checkout", "-q", "main")
        self.write(STAMP, current_rules_version() + "\n")
        self.git("add", "-A"); self.git("commit", "-qm", "align with common-rules")

    def branch(self, name, message, files):
        self.git("checkout", "-q", "-b", name)
        for rel, body in files.items():
            self.write(rel, body)
        self.git("add", "-A"); self.git("commit", "-qm", message)

    def land(self, env=None):
        e = dict(os.environ); e.update(env or {})
        return subprocess.run([str(LAND), "--check"], cwd=str(self.repo),
                              capture_output=True, text=True, check=False, env=e)


class TestNoStampMeansNoGate(LandHarness):

    def test_a_project_that_never_adopted_is_not_gated(self):
        self.branch("work", "W-01 the templates", {"README.md": "seed\nwork\n"})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)


class TestCompliantBranchLands(LandHarness):

    def test_the_row_moved_so_it_lands(self):
        self.stamp_main()
        entry = [{"at": "2026-09-13T21:00:00+02:00", "event": "started", "by": "lead", "evidence": "x"}]
        self.branch("work", "W-01 the templates",
                    {"README.md": "seed\nwork\n", LEDGER: ledger("in progress", entry)})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)
        self.assertIn("READY", out.stdout)

    def test_a_branch_naming_no_item_lands(self):
        self.stamp_main()
        self.branch("work", "fix a typo", {"README.md": "seed\ntypo\n"})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)
        self.assertIn("READY", out.stdout)


class TestUnmovedRowIsRefused(LandHarness):

    def test_refused_and_names_the_item(self):
        self.stamp_main()
        self.branch("work", "W-01 the templates", {"README.md": "seed\nwork\n"})
        out = self.land()
        combined = out.stdout + out.stderr
        self.assertIn(REFUSAL, combined)
        self.assertIn("W-01", combined)
        self.assertNotIn("READY", out.stdout)

    def test_the_override_exists_and_is_explicit(self):
        self.stamp_main()
        self.branch("work", "W-01 the templates", {"README.md": "seed\nwork\n"})
        self.assertIn(REFUSAL, self.land().stdout)
        allowed = self.land(env={"LAND_ALLOW_UNLOGGED_ITEM": "1"})
        self.assertNotIn(REFUSAL, allowed.stdout + allowed.stderr)
        self.assertIn("READY", allowed.stdout)


if __name__ == "__main__":
    unittest.main()
