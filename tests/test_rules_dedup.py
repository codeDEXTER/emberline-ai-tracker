"""M-09: five rules each written out in full in multiple files now have one
canonical home each, with every other mention a one-line pointer naming that
file. This pins the canonical location and checks no other owned file
restates the rule's distinguishing text in full.

M-11 subsequently folds docs/OPERATING-RULES.md into HANDOFF.md, so three of
these five rules' canonical home moves from docs/OPERATING-RULES.md to
HANDOFF.md along with the rest of that file's content -- this test reflects
the post-M-11 layout, not the intermediate M-09-only one."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OWNED_FILES = [
    "HANDOFF.md",
    "docs/OPERATING-RULES.md",
    "CLAUDE-workflow.md",
    "skills/warmup/SKILL.md",
    "templates/lead-prompt.md",
]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def count_occurrences(needle, haystacks):
    hits = []
    for rel in haystacks:
        if needle in read(rel):
            hits.append(rel)
    return hits


class TestRulesDedup(unittest.TestCase):
    def test_ruflo_four_steps_stated_once_in_warmup(self):
        needle = (
            "memory search` and `hooks route` before, `hooks\n  post-task`"
        )
        hits = count_occurrences(needle, OWNED_FILES)
        self.assertEqual(hits, ["skills/warmup/SKILL.md"])
        # the other owned file that mentions ruflo's steps points at it
        self.assertIn(
            "skills/warmup/SKILL.md", read("templates/lead-prompt.md")
        )

    def test_ledger_has_one_writer_stated_once_in_handoff(self):
        needle = "The ledger has one writer."
        hits = count_occurrences(needle, OWNED_FILES)
        self.assertEqual(hits, ["HANDOFF.md"])
        self.assertIn(
            "HANDOFF.md",
            read("templates/lead-prompt.md"),
        )

    def test_reserved_to_the_sponsor_stated_once_in_handoff(self):
        needle = "## Reserved to the sponsor, always"
        hits = count_occurrences(needle, OWNED_FILES)
        self.assertEqual(hits, ["HANDOFF.md"])
        self.assertIn("HANDOFF.md", read("CLAUDE-workflow.md"))
        # content preserved, not lost
        handoff = read("HANDOFF.md")
        for item in (
            "common-rules/",
            "Merging a change to these rules",
            "Creating, picking and closing features",
            "Clearing orphaned processes",
            "finance_data/",
        ):
            self.assertIn(item, handoff)

    def test_checkpoint_before_stopping_stated_once_in_handoff(self):
        needle = "session that ends without"
        hits = count_occurrences(needle, OWNED_FILES)
        self.assertEqual(hits, ["HANDOFF.md"])
        self.assertIn(
            "HANDOFF.md",
            read("templates/lead-prompt.md"),
        )

    def test_ask_row_rule_stated_once_in_handoff(self):
        needle = "becomes an ask\n  row"
        hits = count_occurrences(needle, OWNED_FILES)
        self.assertEqual(hits, ["HANDOFF.md"])
        for rel in ("templates/lead-prompt.md", "skills/warmup/SKILL.md"):
            self.assertIn("HANDOFF.md", read(rel))

    def test_operating_rules_file_is_a_thin_pointer(self):
        # M-11: content moved into HANDOFF.md; this file is now nearly
        # empty, kept only because reserved-to-the-sponsor files still
        # name its path.
        words = len(read("docs/OPERATING-RULES.md").split())
        self.assertLess(words, 120)
        self.assertIn("HANDOFF.md", read("docs/OPERATING-RULES.md"))

    def test_no_duplicated_rule_text_survives_across_owned_files(self):
        # sanity: none of the five key phrases appear in more than one
        # owned file at once.
        checks = {
            "ruflo mandatory steps": "memory search` and `hooks route` before, `hooks\n  post-task`",
            "ledger one writer": "The ledger has one writer.",
            "reserved to sponsor": "## Reserved to the sponsor, always",
            "checkpoint before stopping": "session that ends without",
            "ask row rule": "becomes an ask\n  row",
        }
        for label, needle in checks.items():
            hits = count_occurrences(needle, OWNED_FILES)
            self.assertLessEqual(
                len(hits), 1, f"{label} duplicated in {hits}"
            )


if __name__ == "__main__":
    unittest.main()
