"""M-07: CLAUDE-workflow.md's "one command, everywhere" rule reads as
forbidding a second test command; this pins that the declared
gates.quick/gates.merge split (proposal 23, L-03) is named as the one
sanctioned exception, without disturbing the rest of that paragraph."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestOneCommandException(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "CLAUDE-workflow.md").read_text(encoding="utf-8")

    def test_exception_sentence_present(self):
        self.assertIn("sanctioned exception", self.text)
        self.assertIn("gates.quick", self.text)
        self.assertIn("gates.merge", self.text)
        self.assertIn("proposal 23, L-03", self.text)

    def test_core_rule_still_forbids_inventing_a_second_command(self):
        self.assertIn(
            "Do not\ninvent a second command, a second directory, or a "
            "second runner",
            self.text,
        )

    def test_exception_sits_in_the_one_command_paragraph(self):
        idx_rule = self.text.index("**One command, everywhere.**")
        idx_exception = self.text.index("sanctioned exception")
        idx_next_heading = self.text.index(
            "**Verification you performed lands as a test.**"
        )
        self.assertTrue(idx_rule < idx_exception < idx_next_heading)


if __name__ == "__main__":
    unittest.main()
