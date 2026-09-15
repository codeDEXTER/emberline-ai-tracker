"""Proposal 22, T-06: a published page's <title> is set once, on first
publish, and never changes on a later republish -- not a differing `title`
parameter, not by hand, not a regenerating rebuild that emits the tag
differently. CLAUDE-workflow.md and skills/warmup/SKILL.md state the rule
(once, not per-artifact); this test is the mechanical half of T-06's
done-when: the project tracker page's <title> for a given project name does
not move even when the ledger content behind it changes (status, item
counts, items added) between two renders. This only reads
tools/tracker/board.py's existing render() -- nothing there is edited."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ledger(number, title, items, status="accepted"):
    return {
        "proposal": number, "title": title, "status": status,
        "updated": "2026-09-14",
        "tiers": {"C2": {"tier": "medium", "model": "sonnet", "effort": "medium",
                          "rule": "bounded"}},
        "phases": [{"id": "W", "name": "Build", "goal": "g", "exit": "e"}],
        "items": list(items), "asks": [],
    }


def item(iid, status, title="an item"):
    return {
        "id": iid, "phase": "W", "cx": "C2", "title": title, "status": status,
        "tier": "medium", "model": "sonnet", "tag": "[ruflo · medium · sonnet]",
        "issue": None,
        "log": [{"at": "2026-09-14T10:00:00+02:00", "event": "started",
                  "by": "lead", "evidence": "e"}],
    }


EXISTING_LEDGER = ROOT / "docs" / "proposals" / "22-one-tracker-per-project.json"


def extract_title(html):
    m = re.search(r"<title>(.*?)</title>", html)
    return m.group(1) if m else None


class TestPublishedTitleStable(unittest.TestCase):
    def test_project_page_title_unchanged_across_two_renders(self):
        from tools.tracker import board

        first = board.render(
            [(EXISTING_LEDGER,
              ledger(19, "X", [item("W-01", "not started")], status="accepted"))],
            "demo-project", None,
        )
        second = board.render(
            [(EXISTING_LEDGER,
              ledger(19, "X",
                     [item("W-01", "done"), item("W-02", "in progress")],
                     status="completed"))],
            "demo-project", None,
        )
        title_1 = extract_title(first)
        title_2 = extract_title(second)
        self.assertIsNotNone(title_1)
        self.assertEqual(
            title_1, title_2,
            "the project tracker page's <title> moved between two renders "
            "of the same project even though only ledger content changed",
        )

    def test_title_depends_on_project_name_not_ledger_status(self):
        from tools.tracker import board

        data = ledger(19, "X", [item("W-01", "not started")], status="accepted")
        rendered_a = board.render([(EXISTING_LEDGER, data)], "alpha", None)
        rendered_b = board.render([(EXISTING_LEDGER, data)], "beta", None)
        self.assertNotEqual(
            extract_title(rendered_a), extract_title(rendered_b),
            "different projects should still get different titles",
        )

    def test_rule_stated_once_in_workflow_and_pointed_to_from_warmup(self):
        workflow = (ROOT / "CLAUDE-workflow.md").read_text(encoding="utf-8")
        warmup = (ROOT / "skills/warmup/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            "A published page's name is set once, and never changes", workflow
        )
        self.assertIn("proposal 22 T-06", warmup)
        # the rule text itself is not duplicated in skills/warmup -- it
        # points back to CLAUDE-workflow.md instead
        self.assertNotIn(
            "A published page's name is set once, and never changes", warmup
        )


if __name__ == "__main__":
    unittest.main()
