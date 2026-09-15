"""One tracker per project, until the sponsor asks for another (proposal 29 A-03).

Proposal 22's `tracker.own` key already lets a ledger keep a page of its own
once the sponsor asks for one — but nothing said, in plain language where a
session reads it, that a *project* keeps a single tracker page by default.
This pins that sentence into the four places a session actually reads:
CLAUDE-workflow.md, both skills that mention the tracker page, and the lead
prompt.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = {
    "CLAUDE-workflow.md": ROOT / "CLAUDE-workflow.md",
    # skills/standard/SKILL.md dropped here (proposal 28, R-02): it is now a
    # short shortcut pointing at skills/warmup/SKILL.md, which still carries
    # this rule -- a session following /standard reads it there.
    "skills/warmup/SKILL.md": ROOT / "skills" / "warmup" / "SKILL.md",
    "templates/lead-prompt.md": ROOT / "templates" / "lead-prompt.md",
}

# The stable page every project publishes, one per project by default.
PAGE = "docs/proposals/tracker/index.html"

# The exception has to be stated, not just the default — "until/unless ...
# asks" (for another tracker) and a pointer to how it is recorded.
EXCEPTION_RE = re.compile(
    r"(until|unless).{0,80}sponsor.{0,40}ask", re.IGNORECASE | re.DOTALL)
RECORD_RE = re.compile(r"`tracker`", re.IGNORECASE)


class TestOneTrackerRuleStatedEverywhere(unittest.TestCase):

    def test_files_exist(self):
        for label, path in FILES.items():
            self.assertTrue(path.exists(), f"{label} is missing")

    def test_each_file_names_the_one_project_page(self):
        for label, path in FILES.items():
            text = path.read_text()
            self.assertIn(
                PAGE, text,
                f"{label} does not name the project's one tracker page "
                f"({PAGE})")

    def test_each_file_states_the_exception(self):
        for label, path in FILES.items():
            text = path.read_text()
            self.assertRegex(
                text, EXCEPTION_RE,
                f"{label} does not state the exception: another tracker "
                f"only when the sponsor asks")

    def test_each_file_points_at_how_the_exception_is_recorded(self):
        for label, path in FILES.items():
            text = path.read_text()
            self.assertRegex(
                text, RECORD_RE,
                f"{label} does not point at the ledger's `tracker` key as "
                f"where the sponsor's ask is recorded")


if __name__ == "__main__":
    unittest.main()
