"""Proposal 23 (Eight levers for token spend), items L-01, L-02, L-05, L-06,
L-07: the sponsor's picked levers show up as rules and tools every project on
the standard reads, not just as a proposal page.

Checks that a session actually reading these files at the point it matters
(brief, scout brief, lead prompt, shared rules) sees the lever, not just that
the words exist somewhere in the repo.

Run:  python3 -m unittest discover -s tests -p 'test_levers_in_templates.py' -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEMPLATES = ROOT / "templates"


def read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"{path}: does not exist")
    return path.read_text()


class TestBriefCarriesTheTools(unittest.TestCase):
    """L-07: the brief names the existing tool, not an inline copy."""

    def setUp(self):
        self.text = read(TEMPLATES / "brief.md")

    def test_read_tool_named(self):
        self.assertIn(
            "Read tool", self.text,
            "brief.md: does not name the Read tool in place of cat/sed -n",
        )

    def test_quiet_named(self):
        self.assertIn(
            "bin/quiet", self.text,
            "brief.md: does not name bin/quiet in place of a raw test runner",
        )

    def test_tracker_set_named(self):
        self.assertIn(
            "tracker set", self.text,
            "brief.md: does not name `tracker set` in place of hand-edited ledger JSON",
        )


class TestBriefBundleForm(unittest.TestCase):
    """L-05: small issues on one surface go in one brief as a bundle."""

    def setUp(self):
        self.text = read(TEMPLATES / "brief.md")

    def test_items_bundle_section_present(self):
        lines = [l.strip() for l in self.text.splitlines()]
        self.assertIn(
            "ITEMS", lines,
            "brief.md: no bare ITEMS heading for the bundle form",
        )

    def test_bundle_placeholder_present(self):
        self.assertIn(
            "{{BUNDLE_ITEMS}}", self.text,
            "brief.md: ITEMS section has no {{BUNDLE_ITEMS}} placeholder",
        )

    def test_one_commit_per_issue_named(self):
        self.assertIn(
            "one commit per issue", self.text.lower(),
            "brief.md: bundle form does not require one commit per issue naming its id",
        )


class TestBriefContextPackPointsAtScout(unittest.TestCase):
    """L-06: the CONTEXT section points at the Haiku scout's pack."""

    def setUp(self):
        self.text = read(TEMPLATES / "brief.md")

    def test_context_section_names_scout(self):
        section = self.text.split("CONTEXT\n", 1)[1].split("\nITEMS", 1)[0]
        self.assertIn(
            "scout", section.lower(),
            "brief.md: CONTEXT section does not point at the scout",
        )
        self.assertIn(
            "scout-brief.md", self.text,
            "brief.md: does not reference templates/scout-brief.md",
        )


class TestScoutBrief(unittest.TestCase):
    """L-06: a scout brief template exists with a Haiku tag, read-only
    tools, and the CONTEXT pack format the builder's brief expects."""

    def setUp(self):
        self.path = TEMPLATES / "scout-brief.md"
        self.text = read(self.path)

    def test_haiku_tag_on_first_line(self):
        first = self.text.splitlines()[0]
        self.assertIn("haiku", first.lower(), f"scout-brief.md: first line {first!r} has no haiku tag")

    def test_read_only_tools_named(self):
        for tool in ("Read", "Grep", "Glob"):
            self.assertIn(
                tool, self.text,
                f"scout-brief.md: does not name the read-only tool {tool}",
            )
        self.assertIn(
            "no Edit", self.text,
            "scout-brief.md: does not say Edit is withheld",
        )

    def test_pack_format_has_files_symbols_tests_gate_recall(self):
        for heading in ("FILES", "SYMBOLS", "TESTS", "GATE", "RECALL"):
            self.assertIn(
                heading, self.text,
                f"scout-brief.md: pack format missing {heading}",
            )

    def test_line_ranges_and_why_named(self):
        self.assertIn(
            "{{LINE_START}}", self.text,
            "scout-brief.md: FILES entries do not carry a line range",
        )
        self.assertIn(
            "{{WHY}}", self.text,
            "scout-brief.md: FILES entries do not carry a reason",
        )

    def test_placeholders_upper_snake(self):
        import re
        placeholder = re.compile(r"\{\{(.*?)\}\}")
        upper_snake = re.compile(r"^[A-Z][A-Z0-9_]*$")
        for m in placeholder.finditer(self.text):
            self.assertRegex(
                m.group(1), upper_snake,
                f"scout-brief.md: placeholder {{{{{m.group(1)}}}}} is not UPPER_SNAKE",
            )


class TestLeadPromptTokenBudget(unittest.TestCase):
    """L-01: a lead ends at a boundary, in section 9, appended to the
    existing template."""

    def setUp(self):
        self.text = read(TEMPLATES / "lead-prompt.md")

    def test_section_9_present(self):
        self.assertIn(
            "## 9 Token budget", self.text,
            "lead-prompt.md: no '## 9 Token budget' section",
        )

    def headings_after_section_9(self, text: str) -> list[str]:
        headings = [l.rstrip() for l in text.splitlines() if l.startswith("## ")]
        idx = headings.index("## 9 Token budget")
        return headings[idx + 1:]

    def test_only_the_two_h02_forms_may_follow_section_9(self):
        """Restores L-01's strict boundary (proposal 23), which a bundle-d
        H-02 fixup had relaxed to "any number of numbered sections may
        follow, we just don't check unnumbered ones" -- letting any future
        heading after §9 grow unnoticed (bundle-d review, MEDIUM). Proposal
        24, H-02 names exactly two appendices after §9, in this order --
        the Dispatcher form and the Item-lead form -- and they are the only
        exception this rule grants; anything else after §9 fails it."""
        after = self.headings_after_section_9(self.text)
        self.assertEqual(
            after, ["## Dispatcher form", "## Item-lead form"],
            f"lead-prompt.md: only the Dispatcher form and Item-lead form may follow "
            f"'## 9 Token budget' -- got {after}",
        )

    def test_the_strict_check_itself_rejects_an_extra_heading(self):
        """Proof the check above is load-bearing, not just true of today's
        file by coincidence: a text with one more heading appended after
        the two allowed forms must fail it."""
        mutated = self.text + "\n\n## 10 Something new\n\nunauthorized.\n"
        with self.assertRaises(AssertionError):
            self.assertEqual(["## Dispatcher form", "## Item-lead form"],
                             self.headings_after_section_9(mutated))

    def test_boundary_rule_named(self):
        section = self.text.split("## 9 Token budget", 1)[1]
        self.assertIn("150k", section, "lead-prompt.md: §9 does not name the ~150k token boundary")
        self.assertIn("milestone", section, "lead-prompt.md: §9 does not name the milestone boundary")
        self.assertIn(
            "end of a day", section,
            "lead-prompt.md: §9 does not name the end-of-day boundary",
        )

    def test_handover_mechanism_named(self):
        section = self.text.split("## 9 Token budget", 1)[1]
        for phrase in ("tracker checkpoint", "/warmup", "compaction"):
            self.assertIn(
                phrase, section,
                f"lead-prompt.md: §9 does not name {phrase!r}",
            )

    def test_handover_checklist_named(self):
        section = self.text.split("## 9 Token budget", 1)[1]
        self.assertIn("worktree", section, "lead-prompt.md: §9 handover list does not mention worktree")
        self.assertIn("branch", section, "lead-prompt.md: §9 handover list does not mention branch")

    def test_only_one_new_section_added(self):
        """The parallel p22 edit to this file must not be clobbered: this
        change is append-only, one new section."""
        headings = [l.rstrip() for l in self.text.splitlines() if l.startswith("## ")]
        for n in range(1, 9):
            self.assertTrue(
                any(h.startswith(f"## {n} ") for h in headings),
                f"lead-prompt.md: section {n} missing -- append-only edit removed something",
            )


class TestWorkflowRules(unittest.TestCase):
    """L-02: the risky-work list. L-05: the bundle rule, in the Issues
    section."""

    def setUp(self):
        self.text = read(ROOT / "CLAUDE-workflow.md")

    def test_risky_work_routed_via_tracker_route(self):
        """L-02, superseded by proposal 26 C-02 / proposal 23 M-08: the
        fixed risky-work category list this test used to pin word-for-word
        is gone by design -- `tracker route` (reading each project's own
        `risk_paths`/`risk_always`) decides now, not a list repeated here in
        prose. See tests/test_review_routing_pointer.py for the full check
        that the old list is gone; this only keeps L-02's original intent
        (risky work is named and routed to a reviewer) alive under the new
        mechanism."""
        self.assertIn(
            "tracker route", self.text,
            "CLAUDE-workflow.md: risky-work decision no longer names tracker route",
        )
        self.assertIn(
            "restricted", self.text,
            "CLAUDE-workflow.md: risky-work section no longer names the restricted class",
        )
        for phrase in ("money", "common-rules"):
            self.assertIn(
                phrase, self.text.lower(),
                f"CLAUDE-workflow.md: risky-work examples missing {phrase!r}",
            )

    def test_review_only_risky_work_stated(self):
        self.assertIn(
            "build → gate → land, no reviewer", self.text,
            "CLAUDE-workflow.md: does not state everything else skips review",
        )

    def test_bundle_rule_in_issues_section(self):
        section = self.text.split("## Issues", 1)[1].split("\n## ", 1)[0]
        self.assertIn(
            "one bundle", section,
            "CLAUDE-workflow.md: Issues section has no bundle rule",
        )
        self.assertIn(
            "one PR closing all of them", section,
            "CLAUDE-workflow.md: Issues section bundle rule missing the one-PR line",
        )


if __name__ == "__main__":
    unittest.main()
