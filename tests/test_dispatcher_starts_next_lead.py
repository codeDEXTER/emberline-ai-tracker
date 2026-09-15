"""proposal 28, R-04: when an item lead passes its closing check
(`bin/handover --check`, proposal 24 H-01), the dispatcher (the Dispatcher
form in templates/lead-prompt.md, proposal 24 H-02) starts the next item
lead whose first message is `/warmup <item> [context]`, using the
`claude --bg -p` mechanism proposal 24's H-03 research recommends."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dispatcher_form(text: str) -> str:
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("## Dispatcher form"))
    end = next(i for i, l in enumerate(lines) if i > start and l.startswith("## Item-lead form"))
    return "\n".join(lines[start:end])


class TestDispatcherStartsNextLead(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "templates/lead-prompt.md").read_text(encoding="utf-8")
        self.form = dispatcher_form(self.text)

    def test_dispatcher_form_still_present_and_headings_unmoved(self):
        # Other bundles already built these headings -- this bundle only adds.
        self.assertIn("## Dispatcher form", self.text)
        self.assertIn("## Item-lead form", self.text)
        self.assertLess(
            self.text.index("## Dispatcher form"), self.text.index("## Item-lead form")
        )

    def test_starts_next_lead_on_closing_check_passing(self):
        self.assertIn("bin/handover --check", self.form)
        self.assertIn("H-01", self.form)
        self.assertIn("no sponsor click", self.form)

    def test_first_message_is_warmup_item_plus_context(self):
        self.assertIn("/warmup <item id> [context]", self.form)

    def test_names_the_bg_mechanism_and_research(self):
        self.assertIn("claude --bg -p", self.form)
        self.assertIn("docs/research/starting-item-leads.md", self.form)

    def test_session_id_is_recorded_in_the_ledger(self):
        self.assertIn("recorded in the ledger", self.form)


if __name__ == "__main__":
    unittest.main()
