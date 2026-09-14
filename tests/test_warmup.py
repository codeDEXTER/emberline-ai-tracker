"""`bin/warmup` -- the warm card, the check, and the delta (proposal 19, W-05, D1).

What warm-up is for: a cold session reads the same files in the same order
every time and starts from a card instead of a question; a running session
asks for "what changed" and gets only that. What the tests pin:

  * --check fails for what can be verified: a missing standard file, an
    invalid ledger, a rendered page or a checkpoint that no longer matches its
    ledger (by digest, never mtime), a HANDOFF.md still carrying unfilled
    {{PLACEHOLDERS}}. Prose files report how many commits behind HEAD they
    are, and that is shown, never failed -- a count of commits punishes the
    busiest projects, not the neglected ones.
  * the card's numbers are the ledger's numbers, and its prohibitions are
    HANDOFF.md's own lines.
  * the test command it reports is the one `land` would run -- asked of
    land's own test_cmd(), the same guard tests/test_ci_matches_land.py
    keeps on CI.
  * --since prints only what moved.

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
WARMUP = ROOT / "bin" / "warmup"
TRACKER = ROOT / "bin" / "tracker"
LAND = ROOT / "bin" / "land"
LEDGER = "docs/proposals/19-proposal-warmup.json"

HANDOFF = """# demo — start here

## Start here
The demo project.

## Prohibitions, verbatim
1. **Never write to the real store.** It is the only copy.
2. **Never kill a process by name.** A PID you started only.

## Standing rulings
None yet.

## State, measured
| | |
|---|---|

## Plan of record
docs/proposals/19-proposal-warmup.json

## How to verify
python3 -m unittest

## What good looks like
It works.
"""

RULES = "# Operating rules\n\n## 1 Proposals and the plan\n- one plan\n"


def ledger_data(w02="in progress", asks=None):
    entry = [{"at": "2026-09-13T21:00:00+02:00", "event": "merged", "by": "lead", "evidence": "abc"}]
    return {
        "proposal": 19, "title": "Warm-up", "status": "accepted", "updated": "2026-09-13",
        "phases": [{"id": "W", "name": "build"}],
        "items": [
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "templates", "status": "done",
             "tag": "[ruflo · medium · sonnet]", "log": entry},
            {"id": "W-02", "phase": "W", "cx": "C3", "title": "render the page", "status": w02,
             "tag": "[ruflo · high · opus]", "depends": ["W-01"],
             "log": entry if w02 == "done" else []},
            {"id": "W-03", "phase": "W", "cx": "C2", "title": "check the gate", "status": "not started",
             "tag": "[ruflo · medium · sonnet]", "depends": ["W-01"], "log": []},
        ],
        "asks": asks if asks is not None else [
            {"id": "A-01", "at": "2026-09-13", "kind": "research", "quote": "is a sidecar worth it",
             "became": None, "state": "open"}],
    }


class Project:
    def __init__(self, seeded=True):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "demo"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write("README.md", "seed\n")
        if seeded:
            self.write("HANDOFF.md", HANDOFF)
            self.write("docs/OPERATING-RULES.md", RULES)
            self.set_ledger(ledger_data())
            self.render()
            self.checkpoint()
        self.commit("seed")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.root), *a], capture_output=True, text=True, check=False)

    def write(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-qm", msg)

    def set_ledger(self, data):
        self.write(LEDGER, json.dumps(data, indent=2))

    def render(self):
        subprocess.run([sys.executable, str(TRACKER), "render", str(self.root / LEDGER)],
                       capture_output=True, check=True)

    def checkpoint(self):
        subprocess.run([sys.executable, str(TRACKER), "checkpoint", "--project", str(self.root)],
                       capture_output=True, check=True)

    def warmup(self, *args):
        return subprocess.run([sys.executable, str(WARMUP), "--project", str(self.root), "--no-recall", *args],
                              capture_output=True, text=True, check=False)

    def close(self):
        self.tmp.cleanup()


class Case(unittest.TestCase):
    seeded = True

    def setUp(self):
        self.p = Project(seeded=self.seeded)

    def tearDown(self):
        self.p.close()


class TestCheckOnAnUnseededProject(Case):
    seeded = False

    def test_every_missing_standard_file_is_named(self):
        r = self.p.warmup("--check")
        self.assertEqual(1, r.returncode)
        for name in ("HANDOFF.md", "docs/OPERATING-RULES.md", "ledger"):
            self.assertIn(name, r.stdout)


class TestCheckOnASeededProject(Case):

    def test_a_complete_current_project_passes(self):
        r = self.p.warmup("--check")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_unfilled_placeholders_in_handoff_fail(self):
        self.p.write("HANDOFF.md", HANDOFF.replace("The demo project.", "{{PROJECT_SUMMARY}}"))
        self.p.commit("half-seeded")
        r = self.p.warmup("--check")
        self.assertEqual(1, r.returncode)
        self.assertIn("unfilled placeholder", r.stdout)
        self.assertIn("{{PROJECT_SUMMARY}}", r.stdout)

    def test_a_ledger_change_makes_page_and_checkpoint_stale(self):
        self.p.set_ledger(ledger_data(w02="blocked"))
        self.p.commit("W-02 blocked")
        r = self.p.warmup("--check")
        self.assertEqual(1, r.returncode)
        self.assertIn("page", r.stdout)
        self.assertIn("checkpoint", r.stdout)
        self.assertIn("stale", r.stdout)

    def test_an_invalid_ledger_fails_and_names_the_problem(self):
        d = ledger_data(); d["items"][0]["status"] = "wip"
        self.p.set_ledger(d)
        self.p.commit("broken")
        r = self.p.warmup("--check")
        self.assertEqual(1, r.returncode)
        self.assertIn("status 'wip'", r.stdout)

    def test_prose_files_behind_head_are_shown_not_failed(self):
        for n in range(3):
            self.p.write("README.md", f"seed\n{n}\n")
            self.p.commit(f"work {n}")
        r = self.p.warmup("--check")
        self.assertEqual(0, r.returncode, r.stdout)
        self.assertIn("3 commits behind", r.stdout)

    def test_no_open_ledger_needs_no_checkpoint(self):
        d = ledger_data(w02="done")
        d["items"][2]["status"] = "done"; d["items"][2]["log"] = d["items"][0]["log"]
        self.p.set_ledger(d)
        self.p.render()
        for f in (self.p.root / "docs" / "handovers").glob("*-checkpoint.md"):
            f.unlink()
        self.p.commit("all done")
        r = self.p.warmup("--check")
        self.assertEqual(0, r.returncode, r.stdout)


class TestNotARepo(unittest.TestCase):

    def test_outside_git_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(WARMUP), "--project", tmp, "--check", "--no-recall"],
                               capture_output=True, text=True, check=False)
            self.assertEqual(2, r.returncode)


class TestTheCard(Case):

    def test_counts_are_the_ledgers(self):
        out = self.p.warmup().stdout
        self.assertIn("Proposal 19 · Warm-up: 1 done / 1 in progress / 0 blocked / 1 not started", out)

    def test_prohibitions_come_from_handoff_verbatim(self):
        out = self.p.warmup().stdout
        self.assertIn("Never write to the real store.", out)
        self.assertIn("Never kill a process by name.", out)

    def test_in_progress_next_and_open_asks_are_listed(self):
        out = self.p.warmup().stdout
        self.assertIn("W-02", out)
        self.assertIn("[ruflo · high · opus]", out)
        self.assertIn("W-03", out)
        self.assertIn("A-01", out)
        self.assertIn("is a sidecar worth it", out)

    def test_it_reports_what_it_read(self):
        out = self.p.warmup().stdout
        self.assertRegex(out, r"warm-up read \d[\d,]* bytes \(~\d[\d,]* tokens\)")

    def test_it_asks_nothing(self):
        out = self.p.warmup().stdout
        self.assertNotIn("?\n", out.replace("worth it", ""))


ENGINE_SHAPED_HANDOFF = """# engine — start here

## Two prohibitions. Verbatim, non-negotiable.

**1. Never write to the real library.** It holds the only catalogue.

Two agents mishandled a real data store in one day.

**2. Never kill processes by name pattern.** Kill by explicit PID.

---

## The sponsor's standing rules

- **A skip is never silent.** Work not done must say so.
"""


class TestRealProjectShapes(Case):
    """Found by running the card read-only on the PhotoVault engine, 13 Sep --
    the project the standard was lifted from. Its card said "Prohibitions:
    none found" and "checkpoint · stale", and both were wrong."""

    def test_the_engines_own_prohibition_shape_is_read(self):
        self.p.write("HANDOFF.md", ENGINE_SHAPED_HANDOFF)
        self.p.commit("engine-shaped handoff")
        out = self.p.warmup().stdout
        self.assertIn("Never write to the real library.", out)
        self.assertIn("Never kill processes by name pattern.", out)
        self.assertNotIn("A skip is never silent", out, "the next section was swallowed")
        # The exact claim, not the bare phrase: "none found" also appears in the
        # unrelated test-command line, which made the first draft fail for the
        # wrong reason once the prohibitions were already being read.
        self.assertNotIn("Prohibitions: none found", out)

    def test_a_hand_written_checkpoint_is_named_for_what_it_is(self):
        for f in (self.p.root / "docs" / "handovers").glob("*-checkpoint.md"):
            f.unlink()
        self.p.write("docs/handovers/2026-09-14-proposal-19-checkpoint.md", "# written by hand\n")
        self.p.commit("hand-written checkpoint")
        r = self.p.warmup("--check")
        self.assertEqual(1, r.returncode)
        self.assertIn("no ledger digest", r.stdout)
        self.assertNotIn("checkpoint is stale", r.stdout)


class TestTheTestCommandIsLands(unittest.TestCase):

    def land_test_cmd(self, project: Path) -> str:
        script = f'cd "{project}"\neval "$(sed -n \'/^test_cmd()/,/^}}/p\' "{LAND}")"\ntest_cmd\n'
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False).stdout.strip()

    def reported(self, project: Path) -> str:
        r = subprocess.run([sys.executable, str(WARMUP), "--project", str(project), "--no-recall", "--json"],
                           capture_output=True, text=True, check=False)
        return json.loads(r.stdout)["test_command"]

    def test_python_project(self):
        p = Project(seeded=True)
        try:
            p.write("tests/test_x.py", "import unittest\n")
            p.commit("tests")
            self.assertEqual(self.land_test_cmd(p.root), self.reported(p.root))
            self.assertTrue(self.reported(p.root))
        finally:
            p.close()

    def test_project_with_no_suite(self):
        p = Project(seeded=True)
        try:
            self.assertEqual(self.land_test_cmd(p.root), self.reported(p.root))
            self.assertEqual("", self.reported(p.root))
        finally:
            p.close()


    def test_a_declared_command_wins_over_the_guess(self):
        """Found by the PhotoVault engine rehearsing its migration, 13 Sep: its
        gate is pytest, but the card said unittest because tests/*.py exists.
        .common-rules-test declares the command; land and the card read it."""
        p = Project(seeded=True)
        try:
            p.write("tests/test_x.py", "import unittest\n")
            p.write(".common-rules-test", "# the merge gate: the full suite\n\npython3 -m pytest -q -p no:cacheprovider\n")
            p.commit("declare the gate")
            self.assertEqual("python3 -m pytest -q -p no:cacheprovider", self.land_test_cmd(p.root))
            self.assertEqual(self.land_test_cmd(p.root), self.reported(p.root))
        finally:
            p.close()

    def test_a_declaration_with_no_command_falls_back_to_the_guess(self):
        p = Project(seeded=True)
        try:
            p.write("tests/test_x.py", "import unittest\n")
            p.write(".common-rules-test", "# nothing declared yet\n\n")
            p.commit("empty declaration")
            self.assertEqual("python3 -m unittest discover -s tests -q", self.land_test_cmd(p.root))
            self.assertEqual(self.land_test_cmd(p.root), self.reported(p.root))
        finally:
            p.close()

    def test_a_json_merge_gate_wins_over_the_test_file_in_both(self):
        """Proposal 20, D9: .common-rules.json gates.merge, then
        .common-rules-test, then the guess -- the same order in land and card."""
        p = Project(seeded=True)
        try:
            p.write("tests/test_x.py", "import unittest\n")
            p.write(".common-rules-test", "python3 -m pytest -q\n")
            p.write(".common-rules.json", json.dumps({"gates": {"quick": "sh tools/gate.sh --quick",
                                                               "merge": "sh tools/gate.sh"}}))
            p.commit("declare both gates")
            self.assertEqual("sh tools/gate.sh", self.land_test_cmd(p.root))
            self.assertEqual(self.land_test_cmd(p.root), self.reported(p.root))
        finally:
            p.close()

    def test_a_json_declaration_without_a_merge_gate_falls_through_in_both(self):
        p = Project(seeded=True)
        try:
            p.write("tests/test_x.py", "import unittest\n")
            p.write(".common-rules.json", json.dumps({"gates": {"merge": ""}, "plan_page": "make page"}))
            p.commit("declare no merge gate")
            self.assertEqual("python3 -m unittest discover -s tests -q", self.land_test_cmd(p.root))
            self.assertEqual(self.land_test_cmd(p.root), self.reported(p.root))
        finally:
            p.close()

    def test_malformed_json_is_a_refusal_in_both(self):
        p = Project(seeded=True)
        try:
            p.write("tests/test_x.py", "import unittest\n")
            p.write(".common-rules.json", "{not json")
            p.commit("broken declaration")
            self.assertEqual("false  # .common-rules.json is not valid JSON", self.land_test_cmd(p.root))
            self.assertEqual(self.land_test_cmd(p.root), self.reported(p.root))
        finally:
            p.close()

    def test_no_declaration_has_no_quick_gate_on_the_card(self):
        p = Project(seeded=True)
        try:
            r = subprocess.run([sys.executable, str(WARMUP), "--project", str(p.root), "--no-recall"],
                               capture_output=True, text=True, check=False)
            self.assertNotIn("quick gate", r.stdout)
            self.assertNotIn("merge gate", r.stdout)
            self.assertIn("Prohibitions (HANDOFF.md, verbatim):", r.stdout)
        finally:
            p.close()


class TestSince(Case):

    def test_nothing_moved_says_so(self):
        state = self.p.root / ".claude" / "warmup" / "last.json"
        self.p.warmup("--state", str(state))
        r = self.p.warmup("--since", str(state))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("no change since the last warm-up", r.stdout)

    def test_only_what_moved_is_printed(self):
        state = self.p.root / ".claude" / "warmup" / "last.json"
        self.p.warmup("--state", str(state))
        asks = ledger_data()["asks"] + [{"id": "A-02", "at": "2026-09-13", "kind": "question",
                                         "quote": "will a rerun be faster", "became": None, "state": "open"}]
        self.p.set_ledger(ledger_data(w02="blocked", asks=asks))
        self.p.commit("moved")
        out = self.p.warmup("--since", str(state)).stdout
        self.assertIn("W-02 in progress → blocked", out)
        self.assertIn("A-02", out)
        self.assertNotIn("W-01", out)
        self.assertNotIn("W-03", out)


if __name__ == "__main__":
    unittest.main()
