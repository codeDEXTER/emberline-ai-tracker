"""`bin/land` refuses to land a project whose milestone plan is missing or malformed.

The ninth gate. `bin/milestonecheck` and this wiring landed in the same PR
deliberately: #106 shipped `bin/proposalcheck` with nothing calling it and #107
had to come back a day later to connect it, and `rulecheck --quiet` sat in a
SessionStart hook whose exit status stops nothing until the 2026-08-18 alignment
gate made it load-bearing. Twice now the checker and its caller were separated by
a PR boundary, and both times the rule was advisory in the gap. A checker with no
caller is a suggestion wearing the shape of a rule.

Mirrors `tests/test_land_proposalcheck.py`'s harness: a throwaway repo with a
`main` branch and one feature branch, driven through `land --check` so nothing is
pushed. The stamp is always written at the current rules version, so every case
here is isolated to the milestone gate and never trips the alignment gate.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAND = ROOT / "bin" / "land"
RULECHECK = ROOT / "bin" / "rulecheck"
STAMP = ".common-rules-version"

REFUSAL = "milestone plan is missing or malformed"

GOOD_PLAN = """# Checklist

## Milestones

| # | Milestone | Proves | You get | State |
|---|---|---|---|---|
| 1 | One corpus indexed | retrieval is good enough to build on | nothing to hold | done |
| 2 | First real screen | the design survives contact with a hand | an app you can use | next |
"""

NO_PLAN = """# Checklist

## Features

| # | Feature | State |
|---|---|---|
| 1 | Search | in flight |
"""

BLANK_PROVES = """# Checklist

## Milestones

| # | Milestone | Proves | You get | State |
|---|---|---|---|---|
| 1 | The index builds |  | nothing to hold | next |
"""


def current_rules_version() -> str:
    """Asked, not hardcoded -- same rationale as the two sibling gate files."""
    out = subprocess.run([str(RULECHECK), "--version"], capture_output=True,
                         text=True, check=True)
    return out.stdout.strip()


class LandHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "proj"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.repo / "README.md").write_text("seed\n")
        self.git("add", "-A"); self.git("commit", "-qm", "seed")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a],
                              capture_output=True, text=True, check=False)

    def stamp_main(self, version: str):
        self.git("checkout", "-q", "main")
        (self.repo / STAMP).write_text(version + "\n")
        self.git("add", "-A"); self.git("commit", "-qm", "align with common-rules")

    def branch(self, name, files: dict):
        self.git("checkout", "-q", "-b", name)
        for rel, body in files.items():
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
        self.git("add", "-A"); self.git("commit", "-qm", f"work on {name}")

    def land(self, env=None):
        e = dict(os.environ); e.update(env or {})
        return subprocess.run([str(LAND), "--check"], cwd=str(self.repo),
                              capture_output=True, text=True, check=False, env=e)


class TestNoStampMeansNoGate(LandHarness):

    def test_a_project_with_no_stamp_is_never_blocked_on_milestones(self):
        """Never ran `rulecheck --align`, so never claimed to be governed by a
        rule that lives inside these rules -- the same opt-in guard the
        alignment and proposal gates use."""
        self.branch("work", {"CLAUDE-checklist.md": NO_PLAN})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)


class TestCompliantProjectLands(LandHarness):

    def test_a_well_formed_plan_is_not_blocked(self):
        self.stamp_main(current_rules_version())
        self.branch("work", {"CLAUDE-checklist.md": GOOD_PLAN, "NOTE.md": "words\n"})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)
        self.assertIn("READY", out.stdout)

    def test_a_project_with_no_checklist_at_all_is_not_blocked_here(self):
        """milestonecheck exits 2 -- 'nothing to check'. An adopting project
        with no CLAUDE-checklist.md is malformed, but that is the checklist
        rule's violation to report, not this gate's. Folding 2 into 'refuse'
        would have this gate reporting someone else's rule in its own words."""
        self.stamp_main(current_rules_version())
        self.branch("work", {"NOTE.md": "words\n"})
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)
        self.assertIn("READY", out.stdout)


class TestAMissingPlanIsRefused(LandHarness):

    def test_a_checklist_with_no_milestones_section_is_refused(self):
        self.stamp_main(current_rules_version())
        self.branch("work", {"CLAUDE-checklist.md": NO_PLAN})
        out = self.land()
        combined = out.stdout + out.stderr
        self.assertIn(REFUSAL, combined)
        self.assertNotIn("READY", out.stdout)

    def test_the_refusal_says_how_to_fix_it(self):
        """A gate that only says no costs the session a round trip to find the
        rule. Every other refusal in this file names the file, the section and
        the shape; this one must too."""
        self.stamp_main(current_rules_version())
        self.branch("work", {"CLAUDE-checklist.md": NO_PLAN})
        combined = self.land().stdout + self.land().stderr
        self.assertIn("CLAUDE-workflow.md", combined)
        self.assertIn("## Milestones", combined)
        self.assertIn("nothing to hold", combined,
                      "must say the blank-vs-no distinction, or it invites invented deliverables")

    def test_a_malformed_row_is_refused_not_just_a_missing_section(self):
        self.stamp_main(current_rules_version())
        self.branch("work", {"CLAUDE-checklist.md": BLANK_PROVES})
        out = self.land()
        self.assertIn(REFUSAL, out.stdout + out.stderr)
        self.assertNotIn("READY", out.stdout)


class TestTheOverrideIsExplicit(LandHarness):

    def test_the_override_exists_and_someone_had_to_type_it(self):
        """Same shape as LAND_ALLOW_UNTESTED, LAND_ALLOW_STALE_RULES and
        LAND_ALLOW_UNRECORDED_DECISIONS -- never a silent default.

        This gate needs its escape hatch more than its siblings did: measured
        on 2026-08-20, all four adopting projects had no `## Milestones`
        section, so the gate blocks 4 of 4 until each writes one."""
        self.stamp_main(current_rules_version())
        self.branch("work", {"CLAUDE-checklist.md": NO_PLAN})
        blocked = self.land()
        self.assertIn(REFUSAL, blocked.stdout + blocked.stderr)
        allowed = self.land(env={"LAND_ALLOW_NO_MILESTONES": "1"})
        self.assertNotIn(REFUSAL, allowed.stdout + allowed.stderr)
        self.assertIn("READY", allowed.stdout)


if __name__ == "__main__":
    unittest.main()
