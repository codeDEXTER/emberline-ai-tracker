"""The six warm-up templates and the brief (proposal 19, W-01).

Every template is checked for its required `##` (or, for brief.md, bare
uppercase) sections, in order, and every file under templates/ is checked
for placeholder hygiene: the only `{{...}}` form allowed anywhere is
`{{UPPER_SNAKE}}` (proposal 19 section B, W-01's MUST). A failure names the
template file and the section that is missing or out of order, never just
"assertion failed".

Run:  python3 -m unittest discover -s tests -p 'test_templates.py' -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import ledger  # noqa: E402

TEMPLATES = ROOT / "templates"

PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}")
UPPER_SNAKE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def read(name: str) -> str:
    path = TEMPLATES / name
    if not path.exists():
        raise AssertionError(f"{name}: template does not exist at {path}")
    return path.read_text()


def headings(text: str, marker: str = "## ") -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.startswith(marker)]


def bare_headings(text: str, names: set[str]) -> list[str]:
    """Plain uppercase heading lines (brief.md's shape -- no `##`), filtered
    to the known heading vocabulary so body prose cannot masquerade as one."""
    return [line.strip() for line in text.splitlines() if line.strip() in names]


class SectionOrder(unittest.TestCase):
    def assert_ordered(self, template_name: str, actual: list[str], expected: list[str]) -> None:
        missing = [e for e in expected if e not in actual]
        if missing:
            self.fail(f"{template_name}: missing section(s) {missing} -- has {actual}")
        extra = [a for a in actual if a not in expected]
        self.assertEqual(
            actual, expected,
            f"{template_name}: sections out of order or unexpected extras {extra} -- "
            f"got {actual}, expected {expected}",
        )


class TestPlaceholderHygiene(unittest.TestCase):
    """No `{{` form other than `{{UPPER_SNAKE}}` appears anywhere under templates/."""

    def test_every_placeholder_is_upper_snake(self):
        self.assertTrue(TEMPLATES.is_dir(), f"templates/ does not exist at {TEMPLATES}")
        files = sorted(TEMPLATES.rglob("*"))
        files = [f for f in files if f.is_file()]
        self.assertTrue(files, "templates/ is empty")
        for f in files:
            text = f.read_text()
            for m in PLACEHOLDER.finditer(text):
                inner = m.group(1)
                self.assertRegex(
                    inner, UPPER_SNAKE,
                    f"{f.relative_to(ROOT)}: placeholder {{{{{inner}}}}} is not {{{{UPPER_SNAKE}}}} form",
                )
            # A stray single/triple brace run would slip past the non-greedy
            # regex above silently; check the brace counts line up instead.
            self.assertEqual(
                text.count("{{"), text.count("}}"),
                f"{f.relative_to(ROOT)}: unbalanced {{{{ / }}}} -- a placeholder is malformed",
            )


class TestHandoff(SectionOrder):
    EXPECTED = [
        "## Start here",
        "## Prohibitions, verbatim",
        "## Standing rulings",
        "## State, measured",
        "## Plan of record",
        "## How to verify",
        "## What good looks like",
    ]

    def test_sections_in_order(self):
        text = read("HANDOFF.md")
        self.assert_ordered("HANDOFF.md", headings(text), self.EXPECTED)

    def test_standing_rulings_explains_the_convention(self):
        text = read("HANDOFF.md")
        section = text.split("## Standing rulings", 1)[1].split("## State, measured", 1)[0]
        self.assertIn("VERIFIED", section, "HANDOFF.md: Standing rulings does not mention VERIFIED")
        self.assertIn("[INFERRED]", section, "HANDOFF.md: Standing rulings does not mention [INFERRED]")

    def test_state_measured_is_a_table_with_command_and_date(self):
        text = read("HANDOFF.md")
        section = text.split("## State, measured", 1)[1].split("## Plan of record", 1)[0]
        self.assertIn("|", section, "HANDOFF.md: State, measured has no table")
        header_line = next((l for l in section.splitlines() if l.strip().startswith("|")), "")
        self.assertIn("Command", header_line, "HANDOFF.md: State, measured table has no Command column")
        self.assertIn("Date", header_line, "HANDOFF.md: State, measured table has no Date column")


class TestOperatingRules(SectionOrder):
    EXPECTED = [
        "## 1 Proposals and the plan",
        "## 2 Running work",
        "## 3 Merging and shipping",
        "## 4 The real data",
        "## 5 Ruflo",
        "## 6 Reporting to the sponsor",
        "## 7 Other sessions",
        "## Superseded",
    ]

    def test_sections_in_order(self):
        text = read("OPERATING-RULES.md")
        self.assert_ordered("OPERATING-RULES.md", headings(text), self.EXPECTED)

    def test_entry_shape_shown_once(self):
        text = read("OPERATING-RULES.md")
        # The demonstration entry: a rule in bold, a date, the incident.
        self.assertRegex(
            text, r"\*\*[^*]+\*\*.*\{\{DATE\}\}",
            "OPERATING-RULES.md: no demonstration entry (bold rule followed by a date) shown",
        )

    def test_seeded_with_proposal_19_standard_rules(self):
        text = read("OPERATING-RULES.md").lower()
        required_phrases = [
            "same-turn",
            "a-nn",
            "x-nn",
            "lane",
            "one writer per worktree",
            "fast-forward first",
            "git stash",
            "checkpoint before stopping",
            "ruflo loop mandatory",
            "paraphrase",
            "quote",
        ]
        for phrase in required_phrases:
            self.assertIn(
                phrase, text,
                f"OPERATING-RULES.md: missing the seeded rule about {phrase!r}",
            )

    def test_superseded_section_explains_dated_never_deleted(self):
        text = read("OPERATING-RULES.md")
        section = text.split("## Superseded", 1)[1]
        self.assertIn("dated", section, "OPERATING-RULES.md: Superseded section does not say rules are dated")
        self.assertIn(
            "never deleted", section,
            "OPERATING-RULES.md: Superseded section does not say rules are never deleted",
        )


class TestLedgerTemplate(unittest.TestCase):
    def load(self) -> dict:
        path = TEMPLATES / "ledger.json"
        self.assertTrue(path.exists(), f"ledger.json: template does not exist at {path}")
        return ledger.load(path)

    def test_validates_with_zero_problems(self):
        data = self.load()
        problems = ledger.validate(data)
        self.assertEqual(problems, [], f"templates/ledger.json: {problems}")

    def test_proposal_is_an_integer(self):
        data = self.load()
        self.assertIsInstance(data.get("proposal"), int, "templates/ledger.json: `proposal` must be an integer")

    def test_tiers_c1_through_c4(self):
        data = self.load()
        tiers = data.get("tiers") or {}
        for cx in ("C1", "C2", "C3", "C4"):
            self.assertIn(cx, tiers, f"templates/ledger.json: tiers missing {cx}")
            for key in ("tier", "model", "effort", "rule"):
                self.assertIn(
                    key, tiers[cx],
                    f"templates/ledger.json: tiers.{cx} missing {key!r}",
                )

    def test_build_phase_and_research_lane(self):
        data = self.load()
        phase_ids = {p["id"] for p in data.get("phases") or []}
        self.assertIn("X", phase_ids, "templates/ledger.json: no research lane phase 'X'")
        self.assertTrue(
            phase_ids - {"X"}, "templates/ledger.json: no build phase besides 'X'",
        )

    def test_one_build_item_and_one_research_item_not_started_empty_log(self):
        data = self.load()
        items = data.get("items") or []
        x_items = [i for i in items if i.get("phase") == "X"]
        build_items = [i for i in items if i.get("phase") != "X"]
        self.assertEqual(len(x_items), 1, "templates/ledger.json: expected exactly one X (research) item")
        self.assertEqual(len(build_items), 1, "templates/ledger.json: expected exactly one build item")
        for i in items:
            self.assertEqual(i.get("status"), "not started", f"{i.get('id')}: expected status 'not started'")
            self.assertEqual(i.get("log"), [], f"{i.get('id')}: expected an empty log")

    def test_asks_and_proposed_changes_empty(self):
        data = self.load()
        self.assertEqual(data.get("asks"), [], "templates/ledger.json: `asks` must be []")
        self.assertEqual(data.get("proposed_changes"), [], "templates/ledger.json: `proposed_changes` must be []")

    def test_execution_ruflo_route_placeholder(self):
        data = self.load()
        self.assertEqual(
            data.get("execution", {}).get("ruflo_route"), "{{RUFLO_ROUTE}}",
            "templates/ledger.json: execution.ruflo_route must be the {{RUFLO_ROUTE}} placeholder",
        )


class TestLeadPrompt(SectionOrder):
    EXPECTED = [
        "## 1 The plan is the law",
        "## 2 Ruflo is mandatory",
        "## 3 Parallelism is expected",
        "## 4 Keep the ledger current",
        "## 5 Do not stop",
        "## 6 Hand-over to other sessions",
        "## 7 How you talk",
    ]

    def test_sections_in_order(self):
        text = read("lead-prompt.md")
        self.assert_ordered("lead-prompt.md", headings(text), self.EXPECTED)

    def test_read_order_named(self):
        text = read("lead-prompt.md")
        section = text.split("## 1 The plan is the law", 1)[1].split("## 2 Ruflo is mandatory", 1)[0]
        for name in ("HANDOFF.md", "OPERATING-RULES.md", "CLAUDE-workflow.md", "checkpoint"):
            self.assertIn(name, section, f"lead-prompt.md: read order does not mention {name}")

    def test_status_line_shape_named(self):
        text = read("lead-prompt.md")
        section = text.split("## 7 How you talk", 1)[1]
        self.assertIn("done", section)
        self.assertIn("in progress", section)
        self.assertIn("blocked", section)
        self.assertIn("not started", section)

    def test_removed_lines_absent(self):
        """Proposal 20 D10: the app runs parallel high-tier agents; the
        lead is no longer a bottleneck of one C3 item, nor forbidden from
        spawning a subagent on its own model."""
        text = read("lead-prompt.md")
        self.assertNotIn(
            "You never spawn a subagent on your own model.", text,
            "lead-prompt.md: removed rule (own-model) is still present",
        )
        self.assertNotIn(
            "Only one C3 item runs at a time, and it is yours.", text,
            "lead-prompt.md: removed rule (one C3 at a time) is still present",
        )

    def test_parallel_c3_and_report_only_reviewer(self):
        text = read("lead-prompt.md")
        section = text.split("## 3 Parallelism is expected", 1)[1].split(
            "## 4 Keep the ledger current", 1
        )[0]
        self.assertIn("C3", section, "lead-prompt.md: §3 no longer names C3")
        self.assertIn(
            "report-only", section,
            "lead-prompt.md: §3 has no report-only reviewer rule",
        )
        self.assertIn(
            "two rounds", section,
            "lead-prompt.md: §3 has no at-most-two-rounds limit",
        )

    def test_model_routing_and_ruflo_item_referenced(self):
        text = read("lead-prompt.md")
        self.assertIn(
            "model_routing", text,
            "lead-prompt.md: no reference to the ledger's model_routing (D2)",
        )
        self.assertIn(
            "bin/ruflo-item", text,
            "lead-prompt.md: no reference to bin/ruflo-item (D11)",
        )

    def test_read_order_owner_and_republish_referenced(self):
        text = read("lead-prompt.md")
        self.assertIn(
            "read_order", text,
            "lead-prompt.md: no reference to .common-rules.json read_order (D9)",
        )
        self.assertIn(
            "owner", text,
            "lead-prompt.md: no owner reference for blocked rows and decision asks (D4)",
        )
        self.assertIn(
            "republish", text,
            "lead-prompt.md: no republish-when-changed reference (D1)",
        )


class TestCheckpoint(SectionOrder):
    EXPECTED = [
        "## Ledger count",
        "## Where the code is",
        "## In progress",
        "## Blocked, and why",
        "## Open asks",
        "## Decisions only the sponsor can make",
        "## Incidents",
        "## Exact next action",
    ]

    def test_sections_in_order(self):
        text = read("checkpoint.md")
        self.assert_ordered("checkpoint.md", headings(text), self.EXPECTED)


class TestBrief(unittest.TestCase):
    HEADING_NAMES = {"CONTEXT", "OWNS", "MUST", "MUST NOT", "OUTPUT", "EFFORT"}
    EXPECTED = ["OWNS", "MUST", "MUST NOT", "OUTPUT", "EFFORT"]

    def test_first_line(self):
        text = read("brief.md")
        first = text.splitlines()[0]
        self.assertEqual(
            first, "[ruflo · {{TIER}} · {{MODEL}}] {{ITEM_ID}} {{TITLE}}",
            f"brief.md: first line is {first!r}",
        )

    def test_five_headings_in_order_context_optional(self):
        text = read("brief.md")
        found = bare_headings(text, self.HEADING_NAMES)
        if found and found[0] == "CONTEXT":
            found = found[1:]
        missing = [e for e in self.EXPECTED if e not in found]
        if missing:
            self.fail(f"brief.md: missing heading(s) {missing} -- has {found}")
        self.assertEqual(
            found, self.EXPECTED,
            f"brief.md: headings out of order -- got {found}, expected {self.EXPECTED}",
        )

    def test_output_ends_with_handoff_line(self):
        text = read("brief.md")
        section = text.split("\nOUTPUT\n", 1)[1].split("\nEFFORT\n", 1)[0]
        self.assertIn(
            "HANDOFF: status=<done|blocked> commit=<sha> needs=",
            section,
            "brief.md: OUTPUT does not carry the literal HANDOFF: status=... line",
        )

    def test_must_requires_verify_level(self):
        """Proposal 20 D6: every brief names the row's verification level
        from the project's ladder."""
        text = read("brief.md")
        section = text.split("\nMUST\n", 1)[1].split("\nMUST NOT\n", 1)[0]
        self.assertIn(
            "{{VERIFY_LEVEL}}", section,
            "brief.md: MUST does not require a {{VERIFY_LEVEL}}",
        )
        self.assertIn(
            "from the project's verification ladder", section,
            "brief.md: MUST does not reference the project's verification ladder",
        )


if __name__ == "__main__":
    unittest.main()
