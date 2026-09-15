"""M-05: the light path for tiny items (points 1, risk standard) is a real,
named thing in CLAUDE-workflow.md, so proposal 26's C-05 findings-triage work
can reference it. common-rules' own items are exempt (always restricted)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestLightPathDocumented(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "CLAUDE-workflow.md").read_text(encoding="utf-8")

    def test_light_path_named_and_defined(self):
        self.assertIn("The light path (proposal 23, M-05)", self.text)
        self.assertIn("skips the\nscout", self.text)
        self.assertIn("one commit, one gate run, one log\nline", self.text)

    def test_common_rules_items_are_never_light(self):
        self.assertIn("Common-rules items are\nnever light", self.text)

    def test_findings_triage_cross_reference_present(self):
        self.assertIn("proposal 26, C-05", self.text)


if __name__ == "__main__":
    unittest.main()
