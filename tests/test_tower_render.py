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
    def test_long_issue_title_survives_into_a_session_dot(self):
        wt = [{"name": "wt-1", "short": "wt-1", "project": "finance-tracker",
               "issue": 81, "issue_title": LONG_TITLE, "session": None,
               "newest_transcript": None}]
        out = T.render_strip(wt, {}, [])
        # the strip has no room for a label at all, so the hover is the *only*
        # place the title exists — cutting it here would lose it outright
        self.assertIn(LONG_TITLE, out, "the dot's hover dropped the issue title")

    def test_long_issue_title_survives_into_the_needs_you_band(self):
        wt = [{"name": "wt-1", "short": "wt-1", "project": "finance-tracker",
               "issue": 81, "issue_title": LONG_TITLE, "session": None,
               "newest_transcript": None}]
        out = T.render_needs_you(wt, {"wt-1": {"why": "waiting on you",
                                               "age": "41m"}}, [])
        self.assertIn(LONG_TITLE, out)
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
        self.assertIn("no worktrees", T.render_strip([], {}, []))


def _wt(name, **kw):
    base = {"name": name, "short": name, "project": "finance-tracker",
            "issue": None, "issue_title": None, "session": None,
            "ahead": 0, "branch": name, "newest_transcript": None}
    base.update(kw)
    return base


class InFlightMeansWorkInFlight(unittest.TestCase):
    """Issue #51. The header read `IN FLIGHT · 19` when one of those nineteen
    was a mapped issue and eighteen were git ahead-counts."""

    PIPE = {"in_flight": [{"project": "finance-tracker", "number": 81,
                           "title": "zero logging calls"}],
            "in_flight_worktrees": [_wt(f"w{i}", ahead=i + 1) for i in range(18)],
            "queued": [], "queued_more": 0, "merged": []}

    def test_count_counts_mapped_issues_only(self):
        out = T.render_pipeline(self.PIPE, [])
        self.assertIn("IN FLIGHT · 1", out)
        self.assertNotIn("IN FLIGHT · 19", out)

    def test_unmapped_worktrees_are_collapsed_but_still_present(self):
        out = T.render_pipeline(self.PIPE, [])
        self.assertIn("<details", out)
        self.assertIn("18 worktree(s) ahead of main, no mapped issue", out)
        # collapsed, NOT hidden — every one still reachable by expanding
        for i in range(18):
            self.assertIn(f"w{i}", out)

    def test_no_disclosure_when_there_is_nothing_to_disclose(self):
        pipe = dict(self.PIPE, in_flight_worktrees=[])
        self.assertNotIn("<details", T.render_pipeline(pipe, []))


class TheBandGivesItsHeightBack(unittest.TestCase):
    """Issue #51. Reserving empty space is the failure mode proposal 09 exists
    to fix, so an empty band must not render an empty box."""

    def test_nothing_waiting_is_one_line_not_a_box(self):
        out = T.render_needs_you([_wt("a")], {}, [])
        self.assertIn("nothing needs you", out)
        self.assertNotIn("you-row", out)

    def test_contested_pair_appears_once_not_once_per_end(self):
        wts = [_wt("alpha"), _wt("beta")]
        out = T.render_needs_you(wts, {}, [("alpha", "beta", "pulse.py")])
        self.assertEqual(out.count("you-row"), 1, "one row per pair")
        self.assertIn("pulse.py", out)


class RepeatedEventsCollapse(unittest.TestCase):
    """Issue #52. Four of nine ticker lines were the same event."""

    def test_identical_bodies_in_window_collapse_with_a_count(self):
        same = "## 2026-08-03 (continued) — v4: redesign personalId"
        rows = [(1000 + i, f"agent-log-{i}", "sha", same) for i in range(4)]
        out = T.render_ticker(rows)
        self.assertEqual(out.count("<div class=\"tick\">"), 1)
        self.assertIn("×4", out)

    def test_a_single_character_difference_is_a_different_event(self):
        rows = [(1000, "a", "sha", "deployed v4"),
                (1001, "b", "sha", "deployed v5")]
        out = T.render_ticker(rows)
        self.assertEqual(out.count("<div class=\"tick\">"), 2)
        self.assertNotIn("×", out)

    def test_the_same_body_outside_the_window_stays_two_rows(self):
        body = "identical text"
        rows = [(0, "a", "sha", body), (T.DEDUP_WINDOW + 60, "b", "sha", body)]
        self.assertEqual(T.render_ticker(rows).count("<div class=\"tick\">"), 2)

    def test_an_unparseable_timestamp_never_folds_a_row_away(self):
        """_epoch returns 0.0 on junk. Two junk-stamped rows must not collapse
        into one just because their stamps are equally unparseable — losing a
        real event is the one outcome worse than an untidy list."""
        rows = [{"ts": "not-a-date", "sender": "s", "to_label": "t",
                 "to_session": "x", "summary": "different one"},
                {"ts": "also-junk", "sender": "s", "to_label": "t",
                 "to_session": "y", "summary": "different two"}]
        out = T.render_handovers(rows)
        self.assertEqual(out.count('class="hand"'), 2)

    def test_count_is_always_shown_when_a_row_stands_for_many(self):
        self.assertEqual(T.times(1), "")
        self.assertIn("×3", T.times(3))


class FitsTheWindow(unittest.TestCase):
    """Issue #56. The page height used to be a function of how much work
    existed — 1,721px to 1,792px in half an hour, purely because worktrees were
    added. Capping the regions and letting them scroll fixes that by
    construction, but only if four CSS rules all survive together.

    This is a proxy: whether the page truly fits 1280x900 can only be settled
    in a browser, and it was (page height 900, every region scrolling, verified
    at 1280 and again at 820 where the caps must NOT apply). What the proxy
    guards is the two rules that silently undo it, both of which I got wrong
    on the way here:

      * `align-items:start` (inherited from the uncapped layout) makes a grid
        item size to its content and overflow its track, so the cap never binds
        and the overflow lands straight back on the page. The fix is an
        explicit `align-items:stretch`.
      * without `min-height:0`, a grid item refuses to shrink below its content
        for exactly the same net effect.

    Either one reads as harmless in review and puts the scrollbar back on the
    page. Hence a test rather than a comment.
    """

    def setUp(self):
        css = T.CSS
        start = css.index("@media (min-width:1001px)")
        depth, i = 0, start
        while True:                       # walk to the matching brace
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        self.fit = css[start:i + 1]

    def test_cells_are_stretched_not_content_sized(self):
        self.assertIn("align-items:stretch", self.fit)

    def test_cells_may_shrink_below_their_content(self):
        self.assertIn("min-height:0", self.fit)

    def test_cells_scroll_internally(self):
        self.assertIn("overflow-y:auto", self.fit)

    def test_the_page_itself_does_not_scroll(self):
        self.assertRegex(self.fit, r"body\s*\{[^}]*overflow:hidden")

    def test_the_band_is_capped_too(self):
        """Unbounded, three waiting items took 28% of the height and squeezed
        the pipeline to 165px. It is the most important region and still must
        not be allowed to own the screen."""
        self.assertRegex(self.fit, r"\.band\s*\{[^}]*max-height")

    def test_the_caps_do_not_apply_to_a_narrow_window(self):
        """A narrow window is a browser being read, not the wall screen —
        locking it to the viewport would squash six regions into nothing."""
        self.assertIn("min-width:1001px", self.fit)
        self.assertNotIn("@media (max-width", self.fit)


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
