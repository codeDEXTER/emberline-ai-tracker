"""Proposal 23, M-11. The lead's decision (recorded in the ledger's own
`what`): target 3,000 words for the fresh-lead mandatory read, but
completeness outranks hitting the number -- the sponsor's own ruling. This
test pins the *structure* M-11 committed to (the card replaces the raw
ledger, docs/OPERATING-RULES.md folds into HANDOFF.md, the checkpoint stays
mandatory) and reports the real word count rather than hard-failing on 3,000,
since a checkpoint, prohibition or other load-bearing content is never cut
just to hit a target."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def words(rel):
    return len((ROOT / rel).read_text(encoding="utf-8").split())


class TestMustReadWordBudget(unittest.TestCase):
    def test_operating_rules_folded_into_handoff_not_a_separate_read(self):
        handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("Operating rules, learned the hard way", handoff)
        # the standalone file still exists (reserved-to-the-sponsor files
        # still name its path) but carries near-zero words
        self.assertLess(words("docs/OPERATING-RULES.md"), 120)

    def test_checkpoint_stays_in_the_mandatory_read(self):
        handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("checkpoint", handoff.lower())
        self.assertIn("handovers/*-checkpoint.md", handoff)

    def test_read_order_lines_say_the_card_not_the_raw_ledger(self):
        for rel in ("skills/warmup/SKILL.md", "templates/lead-prompt.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("card", text.lower())
        skill = (ROOT / "skills/warmup/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("not the raw\nledger JSON", skill)
        lead_prompt = (ROOT / "templates/lead-prompt.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("the warmup card, not the raw ledger JSON", lead_prompt)

    def test_must_read_word_count_is_reported_honestly(self):
        # CLAUDE.md + HANDOFF.md (merged) + checkpoint + CLAUDE-workflow.md.
        # The warmup card itself (~1,061 words, measured 2026-09-15 against
        # 11 proposals) is not re-measured here since it is generated, not
        # a static file -- its word count is the item's own evidence, not
        # this test's job to recompute.
        total = (
            words("CLAUDE.md")
            + words("HANDOFF.md")
            + words("docs/handovers/2026-09-15-checkpoint.md")
            + words("CLAUDE-workflow.md")
        )
        # Not a pass/fail gate on 3,000: completeness outranks the number
        # (sponsor's ruling). This is a regression guard only -- if the
        # static must-read set balloons past what M-09/M-10 measured it
        # down to, that is worth a human looking at again.
        self.assertLess(
            total, 10000,
            f"must-read set grew to {total} words without a recorded reason",
        )

    def test_no_prohibition_lost_from_handoff_after_the_merge(self):
        handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("Never change common-rules on your own initiative", handoff)
        self.assertIn(
            "Never write into another project or its data", handoff
        )


if __name__ == "__main__":
    unittest.main()
