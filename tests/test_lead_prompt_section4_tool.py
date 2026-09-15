"""M-06: templates/lead-prompt.md's own section 4 (not the Dispatcher/
Item-lead form sections at the end) says the lead uses tracker set/tracker
ask, and never hand-edits the ledger JSON -- matching what templates/brief.md
already states for a builder."""
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
    assert s is not None and e is not None
    return "\n".join(lines[s:e])


class TestLeadPromptSection4Tool(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "templates/lead-prompt.md").read_text(
            encoding="utf-8"
        )
        self.section4 = section(self.text, "## 4 Keep the ledger current", "## 5 ")

    def test_section4_names_tracker_set_and_ask(self):
        self.assertIn("`tracker set`", self.section4)
        self.assertIn("`tracker ask`", self.section4)

    def test_section4_forbids_hand_editing_ledger_json(self):
        self.assertIn("hand-edit the ledger JSON", self.section4)

    def test_dispatcher_and_item_lead_sections_unaffected(self):
        # the two sections another bundle added stay exactly where they were
        self.assertIn("## Dispatcher form", self.text)
        self.assertIn("## Item-lead form", self.text)


if __name__ == "__main__":
    unittest.main()
