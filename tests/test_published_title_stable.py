"""Proposal 22, T-06: a published page's <title> is set once, on first
publish, and never changes on a later republish -- not a differing `title`
parameter, not by hand, not a regenerating rebuild that emits the tag
differently. CLAUDE-workflow.md and skills/warmup/SKILL.md state the rule
(once, not per-artifact).

T-06 was closed with only half its done-when built: the render()-determinism
class below (TestPublishedTitleStable), which pins that board.render()'s
<title> is a pure function of the project name and never moves on its own.
That is necessary but was mistaken for sufficient -- it is structurally
guaranteed to pass (the title never reads ledger content) and so can never
fail against a regression in the runtime check T-06's `done` also promised:
"`tracker published` refuses (or warns loudly) when the file it is about to
publish carries a <title> different from what was last recorded published."
That check did not exist in tools/tracker/render.py until the T-06 repair
that added tools/tracker/render.py's page_title(), _recorded_title() and
_title_check(), used by both published_project_main and published_main.

The mechanical half of *that* half lives here too now (TestTitleCheckHelper,
direct unit coverage of the three functions); the end-to-end CLI coverage --
a changed title actually refused through `tracker published`, an unchanged
one passing, a title-less pre-repair sidecar staying valid, the
--title-changed override -- is TestPublishedTitleGuard and
TestPublishedProjectTitleGuard in tests/test_tracker_render.py, which drive
the real subprocess and so can fail if the check regresses."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))


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


class TestTitleCheckHelper(unittest.TestCase):
    """Direct unit coverage of tools/tracker/render.py's page_title(),
    _recorded_title() and _title_check() -- the pieces the T-06 repair added.
    tests/test_tracker_render.py's TestPublishedTitleGuard and
    TestPublishedProjectTitleGuard exercise the same rule end to end through
    the `tracker published` CLI; these pin the pieces in isolation."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_page_title_extracts_and_unescapes(self):
        from tools.tracker import render as R
        page = self.tmp / "p.html"
        page.write_text("<title>19 &middot; accepted &amp; done &middot; tracker</title><p>x</p>")
        self.assertEqual("19 · accepted & done · tracker", R.page_title(page))

    def test_page_title_is_none_without_a_title_tag(self):
        from tools.tracker import render as R
        page = self.tmp / "p.html"
        page.write_text("<p>generated 2026-09-14</p>")
        self.assertIsNone(R.page_title(page))

    def test_page_title_is_none_for_a_missing_file(self):
        from tools.tracker import render as R
        self.assertIsNone(R.page_title(self.tmp / "nope.html"))

    def test_recorded_title_is_none_for_a_missing_or_title_less_sidecar(self):
        import json
        from tools.tracker import render as R
        sidecar = self.tmp / "s.json"
        self.assertIsNone(R._recorded_title(sidecar), "a missing sidecar has nothing recorded")
        sidecar.write_text(json.dumps({"url": "https://x", "digest": "a" * 64}))
        self.assertIsNone(R._recorded_title(sidecar), "a pre-T-06 sidecar has no title key")
        sidecar.write_text("{not json")
        self.assertIsNone(R._recorded_title(sidecar), "an unreadable sidecar has nothing to compare")

    def test_title_check_accepts_a_first_publish_and_a_match(self):
        from tools.tracker import render as R
        page = self.tmp / "p.html"
        page.write_text("<title>19 tracker</title>")
        sidecar = self.tmp / "s.json"       # does not exist yet: nothing recorded
        title, changed, problem = R._title_check(sidecar, page, override=False)
        self.assertEqual("19 tracker", title)
        self.assertFalse(changed)
        self.assertIsNone(problem)

    def test_title_check_refuses_a_mismatch_without_override(self):
        import json
        from tools.tracker import render as R
        page = self.tmp / "p.html"
        page.write_text("<title>19 renamed</title>")
        sidecar = self.tmp / "s.json"
        sidecar.write_text(json.dumps({"title": "19 tracker"}))
        title, changed, problem = R._title_check(sidecar, page, override=False)
        self.assertEqual("19 renamed", title)
        self.assertFalse(changed)
        self.assertIsNotNone(problem)
        self.assertIn("19 tracker", problem)
        self.assertIn("19 renamed", problem)

    def test_title_check_records_an_override(self):
        import json
        from tools.tracker import render as R
        page = self.tmp / "p.html"
        page.write_text("<title>19 renamed</title>")
        sidecar = self.tmp / "s.json"
        sidecar.write_text(json.dumps({"title": "19 tracker"}))
        title, changed, problem = R._title_check(sidecar, page, override=True)
        self.assertEqual("19 renamed", title)
        self.assertTrue(changed)
        self.assertIsNone(problem)


if __name__ == "__main__":
    unittest.main()
