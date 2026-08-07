"""The Tower's render layer must not truncate, and must fail one region at a time.

Proposal 09 moved the page from one hand-positioned SVG to HTML and CSS. Two
promises came out of that and both are the kind that rot silently:

1. **Nothing is cut mid-word.** The old renderers carried eight hardcoded `[:n]`
   slices — they existed only because SVG `<text>` cannot wrap, and on the live
   tree they produced `arm-f-filin`, `arm-b-contr`, and a pipeline row that
   stopped one character short of "lines". Fitting is CSS's job now. A future
   edit reaching for `[:40]` to "make it fit" would look reasonable in review and
   quietly bring the whole class of bug back.

2. **One collector failing costs one region, never the page.** That contract
   predates this change (it is in the module docstring) and the rewrite had to
   carry it across intact.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOWER = ROOT / "bin" / "tower"


def load_tower():
    loader = importlib.machinery.SourceFileLoader("tower_under_test", str(TOWER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


T = load_tower()

# A title longer than any of the caps the SVG version used, with a word boundary
# past every one of them so a reintroduced slice cannot pass by luck.
LONG_TITLE = ("zero logging calls in 12,679 lines across every collector "
              "and renderer in the repository")


class NothingIsTruncated(unittest.TestCase):
    def test_long_issue_title_survives_into_a_session_card(self):
        wt = [{"name": "wt-1", "short": "wt-1", "project": "finance-tracker",
               "issue": 81, "issue_title": LONG_TITLE, "session": None}]
        out = T.render_sessions(wt, [], [], set())
        self.assertIn(LONG_TITLE, out, "the card dropped or cut the issue title")
        # and again in the title attribute, which is what a hover has to show
        self.assertIn(f'title="{LONG_TITLE}"', out)

    def test_long_pipeline_row_survives(self):
        pipeline = {"in_flight": [{"project": "finance-tracker", "number": 81,
                                   "title": LONG_TITLE}],
                    "in_flight_worktrees": [], "queued": [], "queued_more": 0,
                    "merged": []}
        self.assertIn(LONG_TITLE, T.render_pipeline(pipeline, []))

    def test_long_handover_summary_survives(self):
        rows = [{"ts": "2026-08-07T15:18:00", "sender": "a session with a "
                 "genuinely long descriptive name", "to_label": "another one",
                 "to_session": "abc", "summary": LONG_TITLE}]
        self.assertIn(LONG_TITLE, T.render_handovers(rows))

    def test_long_ticker_subject_survives(self):
        out = T.render_ticker([(0, "common-rules", "deadbee", LONG_TITLE)])
        self.assertIn(LONG_TITLE, out)

    def test_no_value_is_sliced_on_its_way_onto_the_page(self):
        """The guard that matters: no `[:n]` inside an f-string interpolation.

        That is precisely the shape every old truncation had —
        `{e(w["short"][:11])}`, `{e(subj[:90])}` — a value cut at the moment it
        is written into the markup. A plain `behind[:3]` is a *list* slice
        choosing how many project names to name and is not this bug, which is
        why the check looks at interpolations rather than at every `[:n]`.

        Scoped to the rendering half so the collectors, which legitimately
        slice lists (`merged[:4]`, `queued[:8]`), are not implicated.
        """
        src = TOWER.read_text()
        render_half = src[src.index("# --- rendering ---"):]
        # strip docstrings and comments: this file's own explanation of the old
        # `[:11]` cuts is prose, not code, and must not trip its own check
        render_half = re.sub(r'"""(?:.|\n)*?"""', "", render_half)
        render_half = re.sub(r"(?m)^\s*#.*$", "", render_half)
        offenders = re.findall(r"\{[^{}\n]*\[\s*:\s*\d+\s*\][^{}\n]*\}", render_half)
        self.assertEqual(offenders, [],
                         f"value(s) sliced into the markup: {offenders}")


class OneRegionFailsAlone(unittest.TestCase):
    """Each renderer, handed the None a failed collector produces, says so
    rather than raising — which is what would turn one bad `gh` call into a
    500 for the whole screen."""

    def test_each_renderer_degrades_to_a_note(self):
        for label, out in [
            ("work packages", T.render_burnup(None)),
            ("handovers", T.render_handovers(None)),
            ("pipeline", T.render_pipeline(None, [])),
            ("ticker", T.render_ticker([])),
        ]:
            with self.subTest(region=label):
                self.assertIn("unavailable", out)

    def test_region_marks_a_failed_collector(self):
        self.assertIn("unavailable",
                      T.region("T", None, "<p>body</p>", "boom", "thing"))
        self.assertNotIn("unavailable",
                         T.region("T", None, "<p>body</p>", None))

    def test_empty_session_list_is_not_an_exception(self):
        self.assertIn("no worktrees", T.render_sessions([], [], [], set()))


class StillEscapes(unittest.TestCase):
    def test_markup_in_data_cannot_reach_the_page(self):
        evil = '<script>alert(1)</script>'
        rows = [{"ts": "2026-08-07T15:18:00", "sender": evil, "to_label": "x",
                 "to_session": "s", "summary": evil}]
        out = T.render_handovers(rows)
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)


if __name__ == "__main__":
    unittest.main()
