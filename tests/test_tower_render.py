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
        out = T.render_strip(wt, {}, [], [])
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
            ("features", T.render_features(None)),
            ("pipeline", T.render_pipeline(None, [])),
        ]:
            with self.subTest(region=label):
                self.assertIn("unavailable", out)

    def test_region_marks_a_failed_collector(self):
        self.assertIn("unavailable",
                      T.region("T", None, "<p>body</p>", "boom", "thing"))
        self.assertNotIn("unavailable",
                         T.region("T", None, "<p>body</p>", None))

    def test_empty_session_list_is_not_an_exception(self):
        self.assertIn("no worktrees", T.render_strip([], {}, [], []))


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

    def test_unmapped_worktrees_are_counted_and_never_named(self):
        """#51 collapsed these behind a <details> that still listed worktree
        names. #65 removes the names outright: a worktree with no mapped issue
        has nothing to identify it by except its directory, and a directory is
        not a fact about the product. The count stays; the names go."""
        out = T.render_pipeline(self.PIPE, [])
        self.assertIn("18 session(s) ahead of main", out)
        for i in range(18):
            self.assertNotIn(f"w{i}", out)

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


class NoBranchNameReachesTheScreen(unittest.TestCase):
    """Issue #65, and the whole of the sponsor's complaint: *"it doesn't help
    when you are saying some random branch name."*

    This is the guard that must not rot. Every renderer that takes a worktree
    gets one whose directory name is unmistakable, and the assertion is that it
    appears nowhere in the output — not in a label, not in a hover, not in a
    collapsed disclosure."""

    BRANCH = "arm-f-filing-9c3e21"

    def _worktree(self):
        return _wt(self.BRANCH, short=self.BRANCH, issue=81,
                   issue_title="zero logging calls", session=None, ahead=4)

    def test_strip_never_names_the_worktree(self):
        out = T.render_strip([self._worktree()], {}, [], [])
        self.assertNotIn(self.BRANCH, out)

    def test_needs_you_band_never_names_the_worktree(self):
        out = T.render_needs_you([self._worktree()],
                                 {self.BRANCH: {"why": "waiting on you", "age": "9m"}},
                                 [], [])
        self.assertNotIn(self.BRANCH, out)

    def test_contested_row_never_names_the_worktree(self):
        other = "arm-b-contract-77aa10"
        out = T.render_needs_you([self._worktree(), _wt(other, short=other)], {},
                                 [(self.BRANCH, other, "pulse.py")], [])
        self.assertNotIn(self.BRANCH, out)
        self.assertNotIn(other, out)

    def test_pipeline_never_names_the_worktree(self):
        pipe = {"in_flight": [], "in_flight_worktrees": [self._worktree()],
                "queued": [], "queued_more": 0, "merged": []}
        self.assertNotIn(self.BRANCH, T.render_pipeline(pipe, []))


REGISTER = """# Checklist

## Features

| # | Feature | State |
|---|---|---|
| [#2](https://example.com/2) | Prove the classifier is good enough | **in flight** — issue [#1](https://example.com/1) |
| [#3](https://example.com/3) | Capture a document and see it filed | blocked by #2 |
| [#8](https://example.com/8) | Get the vault onto the second phone | version 2 |

## Now

- [x] something unrelated that mentions #99
"""


class TheRegisterIsReadNotGuessed(unittest.TestCase):
    """Issue #65. Features come from the declared register; nothing is inferred
    from an issue title's prefix any more."""

    def setUp(self):
        self.feats = T.parse_features(REGISTER)

    def test_every_row_is_read(self):
        self.assertEqual([f["number"] for f in self.feats], [2, 3, 8])
        self.assertEqual(self.feats[0]["title"], "Prove the classifier is good enough")

    def test_blocked_by_is_never_read_as_progress(self):
        """The subtlety that would corrupt every percentage: `blocked by #2` is
        a dependency. Counting it as an implementing issue would make a blocked
        feature inherit its blocker's completion — the opposite of true."""
        blocked = self.feats[1]
        self.assertEqual(blocked["implements"], [])
        self.assertEqual(blocked["blocked_by"], [2])
        self.assertEqual(blocked["kind"], "blocked")

    def test_an_implementing_issue_is_read(self):
        self.assertEqual(self.feats[0]["implements"], [1])
        self.assertEqual(self.feats[0]["kind"], "in flight")

    def test_the_table_does_not_leak_into_the_next_section(self):
        """#99 lives under `## Now`. Reading past the section boundary would
        invent a feature out of an ordinary checklist line."""
        self.assertNotIn(99, [f["number"] for f in self.feats])

    def test_a_project_with_no_register_reports_none_not_zero(self):
        self.assertEqual(T.parse_features("# Checklist\n\n## Now\n\n- [ ] a thing"), [])


class UndeclaredScopeIsNotZero(unittest.TestCase):
    """Proposal 08's rule, restated where it now matters most: the sponsor asked
    for a completion figure by name, so an invented denominator is the most
    tempting lie on the screen."""

    def test_no_features_says_so_rather_than_showing_a_percentage(self):
        out = T.render_features([{"project": "finance-tracker", "features": None,
                                  "items": (18, 54), "unparsed": 0, "closed": {}}])
        self.assertIn("no features declared", out)
        self.assertNotIn("0%", out)
        self.assertIn("against no product definition", out)

    def test_all_tickets_shut_is_not_the_same_as_done(self):
        """Proposal 05: the sponsor closes features."""
        row = {"project": "p", "items": None, "unparsed": 0,
               "features": [{"number": 2, "title": "A feature", "state": "in flight",
                             "kind": "in flight", "implements": [1], "blocked_by": []}],
               "closed": {1: True}}
        out = T.render_features([row])
        self.assertIn("awaiting your close", out)


class StillEscapes(unittest.TestCase):
    def test_markup_in_data_cannot_reach_the_page(self):
        """Retargeted in #64 from render_handovers, which no longer exists.
        The coverage is the point, not the renderer: a worktree or issue title
        is attacker-adjacent text that reaches the page, and the strip puts it
        inside a title attribute where an unescaped quote would break out."""
        evil = '<script>alert(1)</script>" onmouseover="x'
        wt = [_wt("wt-1", issue_title=evil)]
        for out in (T.render_strip(wt, {}, [], []),
                    T.render_needs_you(wt, {"wt-1": {"why": "waiting on you",
                                                     "age": "1m"}}, [])):
            self.assertNotIn("<script>", out)
            self.assertNotIn('" onmouseover="', out)
            self.assertIn("&lt;script&gt;", out)


if __name__ == "__main__":
    unittest.main()
