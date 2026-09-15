"""M-10: CLAUDE-workflow.md's Autopilot and Talking-to-the-user sections had
their dated, proposal-specific rationale (grandfather clauses, a five-arm/
bake-off-style citation, sample register and milestone rows) moved into
CHANGELOG.md history, with a one-line pointer left behind. Table shapes stay;
sample rows go; nothing is deleted -- it is moved."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def section(text, start_marker, end_marker):
    lines = text.splitlines()
    s = e = None
    for i, line in enumerate(lines):
        if line.startswith(start_marker):
            s = i
        elif s is not None and line.startswith(end_marker):
            e = i
            break
    assert s is not None and e is not None, (start_marker, end_marker)
    return "\n".join(lines[s:e])


class TestWorkflowTrim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / "CLAUDE-workflow.md").read_text(encoding="utf-8")
        cls.changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        cls.autopilot = section(cls.workflow, "## Autopilot", "## Issues")
        cls.talking = section(
            cls.workflow, "## Talking to the user", "## Verifying a change"
        )

    def test_table_shapes_survive(self):
        self.assertIn("| # | Feature | State |", self.autopilot)
        self.assertIn("| # | Milestone | Proves | You get | State |", self.autopilot)

    def test_sample_rows_removed_from_workflow(self):
        # the worked example rows moved to CHANGELOG.md; the file itself
        # keeps only the table header now
        self.assertNotIn("Capture a document and see it filed", self.autopilot)
        self.assertNotIn("One corpus indexed, answering a question", self.autopilot)

    def test_sample_rows_present_in_changelog(self):
        self.assertIn("Capture a document and see it filed", self.changelog)
        self.assertIn("One corpus indexed, answering a question", self.changelog)

    def test_grandfather_clause_detail_moved_to_changelog(self):
        # the workflow file keeps the operative dates, not the measurement
        # narrative behind them
        self.assertNotIn("issue #584", self.autopilot)
        self.assertNotIn("issue #584", self.talking)
        self.assertIn("issue #584", self.changelog)
        self.assertIn("2026-08-19", self.talking)  # operative date kept

    def test_five_arm_style_citation_moved(self):
        self.assertNotIn("bake-off arm that did this logged six", self.talking)
        self.assertIn("bake-off", self.changelog)

    def test_word_count_reduced_from_original(self):
        # measured against the pre-M-10 file (HEAD before this bundle):
        # autopilot 1384 + talking 884 = 2268 words. Completeness outranks
        # hitting an exact target (sponsor's own ruling, M-11) -- this pins
        # a real, meaningful reduction rather than an exact "half".
        total = len(self.autopilot.split()) + len(self.talking.split())
        self.assertLess(total, 2268 * 0.85, f"only trimmed to {total} words")

    def test_no_prohibition_or_rule_deleted(self):
        # spot-check load-bearing rules are still present, just condensed
        for phrase in (
            "A proposal that asked numbered decisions must record the answers",
            "A document is either a proposal or an artifact",
            "A question to the user is a cost, not a safety move",
            "The accepted plan is the queue",
        ):
            self.assertIn(phrase, self.workflow)


if __name__ == "__main__":
    unittest.main()
