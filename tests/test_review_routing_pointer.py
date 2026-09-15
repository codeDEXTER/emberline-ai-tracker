"""M-08: the six-category review list ("money, real user data, auth and
secrets, release and packaging, cross-cutting changes, any common-rules
change") in CLAUDE-workflow.md and templates/lead-prompt.md SS3 is replaced
by a pointer to `tracker route` (proposal 25 Z-02, proposal 26 C-02), not
left standing beside it.

Do not start before proposal 25's Z-02 and proposal 26's C-02 are adopted --
both are `status: done` in their ledgers and tools/tracker/route.py and
tools/tracker/lanes.py exist and are wired into bin/tracker as `route` and
`lanes` (verified before this test was written).
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Fragments of the old, duplicated six-category prose. None of these may
# appear anywhere in either file any more -- the category list is gone, not
# just reworded in one of the two places it used to live.
OLD_FRAGMENTS = [
    "money or financial data;\nreal user data stores",
    "money, real user data, auth and secrets, release and",
]


class TestSixCategoryListReplaced(unittest.TestCase):
    def setUp(self):
        self.workflow = (ROOT / "CLAUDE-workflow.md").read_text(encoding="utf-8")
        self.lead_prompt = (ROOT / "templates/lead-prompt.md").read_text(encoding="utf-8")

    def test_old_six_category_list_gone_from_workflow(self):
        self.assertNotIn("money or financial data", self.workflow)
        self.assertNotIn("real user data stores (photo libraries", self.workflow)

    def test_old_six_category_list_gone_from_lead_prompt(self):
        self.assertNotIn(
            "money, real user data, auth and secrets, release and",
            self.lead_prompt,
        )

    def test_workflow_points_to_tracker_route(self):
        self.assertIn("tracker route", self.workflow)
        self.assertIn("proposal 25 Z-02", self.workflow)
        self.assertIn("proposal 26 C-02", self.workflow)

    def test_lead_prompt_section3_points_to_tracker_route(self):
        # Section 3 is "Parallelism is expected" -- find it explicitly so a
        # pointer added somewhere else in the file does not satisfy this.
        lines = self.lead_prompt.splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith("## 3 "))
        end = next(i for i, l in enumerate(lines) if i > start and l.startswith("## 4 "))
        section3 = "\n".join(lines[start:end])
        self.assertIn("tracker route", section3)
        self.assertIn("restricted", section3)
        self.assertIn("bundled", section3)


if __name__ == "__main__":
    unittest.main()
