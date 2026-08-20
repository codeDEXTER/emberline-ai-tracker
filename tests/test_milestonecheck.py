"""`bin/milestonecheck` reads a project's milestone plan and says what is wrong.

`CLAUDE-workflow.md`, "And every project keeps a milestone plan": a
`## Milestones` table in `CLAUDE-checklist.md` carrying, per row, what the step
*proves* and what the sponsor *gets*.

Structure only, and the boundary matters. This checker cannot know whether
"retrieval is good enough to build on" was actually proven, and it deliberately
does not judge freshness -- "in flight for N days" fires on every genuinely slow
milestone and trains everyone to ignore the checker. What it can know is that a
row claiming to be a milestone left the Proves column empty, which means it is a
task with a milestone's formatting.

The "nothing to hold" case is the one worth pinning: a plan whose first steps
deliver nothing visible is a fine plan, and the rule says the sponsor should be
told so at the start. So the column may not be blank, but it may say no --
a checker that rejected "nothing to hold" would push people to invent a
deliverable, which is the opposite of what the rule is for.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "bin" / "milestonecheck"

GOOD = """# Checklist

## Milestones

| # | Milestone | Proves | You get | State |
|---|---|---|---|---|
| 1 | One corpus indexed | retrieval is good enough to build on | nothing to hold | done |
| 2 | Model timed on the phone | the felt speed, and the retrieval budget | nothing to hold | in flight |
| 3 | First real screen | the design survives contact with a hand | an app you can use | next |
"""


def run(project: Path):
    return subprocess.run([str(CHECK), "--project", str(project)],
                          capture_output=True, text=True, check=False)


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        self.proj.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, body: str):
        (self.proj / "CLAUDE-checklist.md").write_text(body)


class AWellFormedPlanPasses(Harness):

    def test_the_shape_the_rule_documents_is_accepted(self):
        """Byte-for-byte the columns CLAUDE-workflow.md prints. If this fails,
        the rule and its checker have drifted apart and the rule is the one
        people read."""
        self.write(GOOD)
        r = run(self.proj)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_nothing_to_hold_is_a_valid_answer_not_a_violation(self):
        """The rule's own example uses it twice. A checker that rejected it
        would push people to invent a deliverable per milestone, which is the
        failure the You-get column exists to prevent."""
        self.write(GOOD)
        self.assertEqual(run(self.proj).returncode, 0)


class AMissingOrEmptyPlanIsRefused(Harness):

    def test_no_milestones_section_is_a_violation_and_names_the_rule(self):
        self.write("# Checklist\n\n## Features\n\n| # | Feature | State |\n|---|---|---|\n")
        r = run(self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Milestones", r.stdout)
        self.assertIn("milestone plan", r.stdout, "must point at the rule, not just fail")

    def test_a_heading_with_no_table_under_it_is_a_violation(self):
        self.write("# Checklist\n\n## Milestones\n\nComing soon.\n")
        self.assertEqual(run(self.proj).returncode, 1)

    def test_a_header_with_no_rows_is_a_violation(self):
        self.write("# Checklist\n\n## Milestones\n\n"
                   "| # | Milestone | Proves | You get | State |\n|---|---|---|---|---|\n")
        r = run(self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no milestones", r.stdout.lower())


class TheTwoColumnsThatEarnTheTable(Harness):

    def test_a_table_without_a_proves_column_is_refused(self):
        self.write("# Checklist\n\n## Milestones\n\n"
                   "| # | Milestone | You get | State |\n|---|---|---|---|\n"
                   "| 1 | Index it | an app | next |\n")
        r = run(self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Proves", r.stdout)

    def test_a_table_without_a_you_get_column_is_refused(self):
        self.write("# Checklist\n\n## Milestones\n\n"
                   "| # | Milestone | Proves | State |\n|---|---|---|---|\n"
                   "| 1 | Index it | retrieval works | next |\n")
        r = run(self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("You get", r.stdout)

    def test_an_empty_proves_cell_is_called_a_task_not_a_milestone(self):
        """The distinction the rule turns on: "the index builds" is a task,
        "retrieval is good enough to build on" is a milestone."""
        self.write("# Checklist\n\n## Milestones\n\n"
                   "| # | Milestone | Proves | You get | State |\n|---|---|---|---|---|\n"
                   "| 1 | The index builds |  | nothing to hold | next |\n")
        r = run(self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("task", r.stdout)
        self.assertIn("The index builds", r.stdout, "must name the offending row")

    def test_an_empty_you_get_cell_is_refused_and_suggests_the_words(self):
        """Blank is refused, but the fix is offered -- a blank cell is usually
        someone who had no deliverable and no phrase for it."""
        self.write("# Checklist\n\n## Milestones\n\n"
                   "| # | Milestone | Proves | You get | State |\n|---|---|---|---|---|\n"
                   "| 1 | Index it | retrieval is good enough |  | next |\n")
        r = run(self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("nothing to hold", r.stdout)


class StatesComeFromTheRegistersVocabulary(Harness):

    def test_an_invented_state_is_refused(self):
        self.write("# Checklist\n\n## Milestones\n\n"
                   "| # | Milestone | Proves | You get | State |\n|---|---|---|---|---|\n"
                   "| 1 | Index it | retrieval is good enough | nothing to hold | wip |\n")
        r = run(self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("wip", r.stdout)

    def test_every_state_the_register_uses_is_accepted(self):
        for state in ("in flight", "next", "later", "built", "done", "completed", "blocked"):
            with self.subTest(state=state):
                self.write("# Checklist\n\n## Milestones\n\n"
                           "| # | Milestone | Proves | You get | State |\n|---|---|---|---|---|\n"
                           f"| 1 | Index it | retrieval is good enough | nothing to hold | {state} |\n")
                self.assertEqual(run(self.proj).returncode, 0, f"{state!r} rejected")

    def test_completed_is_accepted_alongside_the_grandfathered_done(self):
        """`completed` is the word to write going forward (matching
        proposal-status's own vocabulary); `done` is a grandfathered synonym,
        not a violation -- finance-tracker's own plan already uses it."""
        for state in ("completed", "done"):
            with self.subTest(state=state):
                self.write("# Checklist\n\n## Milestones\n\n"
                           "| # | Milestone | Proves | You get | State |\n|---|---|---|---|---|\n"
                           f"| 1 | Index it | retrieval is good enough | nothing to hold | {state} |\n")
                self.assertEqual(run(self.proj).returncode, 0, f"{state!r} rejected")


class NothingToCheckIsNotAFailure(Harness):

    def test_a_project_with_no_checklist_exits_2_not_1(self):
        """Same 0/1/2 shape as rulecheck and proposalcheck. 2 must not collide
        with either -- `bin/land` reads only 1 as a refusal, so a 2 landing in
        the 1 slot would block every project this gate has nothing to say
        about."""
        r = run(self.proj)
        self.assertEqual(r.returncode, 2)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
