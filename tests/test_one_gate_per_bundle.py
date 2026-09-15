"""proposal 26, C-03: `bin/ruflo-item done` accepts several item ids and
runs the merge gate once, not once per item; `templates/lead-prompt.md` and
`templates/brief.md` say one full suite and at most one review per bundle
or batch, with restricted items still going alone (not batched)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestOneGatePerBundleWording(unittest.TestCase):
    def setUp(self):
        self.lead_prompt = (ROOT / "templates/lead-prompt.md").read_text(encoding="utf-8")
        self.brief = (ROOT / "templates/brief.md").read_text(encoding="utf-8")

    def test_lead_prompt_states_one_gate_per_bundle(self):
        self.assertIn("One full suite and at most one review per bundle or batch", self.lead_prompt)
        self.assertIn("ruflo-item done ID1 ID2 ID3", self.lead_prompt)

    def test_lead_prompt_states_restricted_items_go_alone(self):
        section2 = self.lead_prompt.split("## 2 Ruflo is mandatory", 1)[1].split("## 3 ", 1)[0]
        self.assertIn("never joins a bundle", section2)
        self.assertIn("restricted", section2)

    def test_brief_states_restricted_items_never_batched(self):
        self.assertIn("one gate run, one PR closing all of them", self.brief)
        self.assertIn("A restricted item is never in a bundle", self.brief)

    def test_brief_tracker_stage_line_untouched(self):
        # Owned by a different bundle -- this bundle must not have touched it.
        self.assertIn(
            "Stage ledger updates with `tracker stage` -- never `tracker set`, "
            "never `tracker ask`, never hand-editing its JSON.",
            self.brief,
        )


if __name__ == "__main__":
    unittest.main()
