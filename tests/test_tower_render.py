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
import threading
import time
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

    def test_long_feature_title_survives_the_board(self):
        row = {"project": "pockets", "items": None, "unparsed": 0, "closed": {1: False},
               "features": [{"number": 2, "title": LONG_TITLE, "state": "in flight — issue #1",
                             "kind": "in flight", "implements": [1], "blocked_by": []}]}
        self.assertIn(LONG_TITLE, T.render_board([row]))

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
            ("board", T.render_board(None)),
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
            "ahead": 0, "branch": name, "newest_transcript": None,
            "files": [], "path": Path("/tmp")}
    base.update(kw)
    return base


class TheBoardIsHonestAboutEmptyColumns(unittest.TestCase):
    """#70. The board replaces PIPELINE — which was itself a board of work by
    state, so keeping both would have been two boards of one shape at different
    altitudes."""

    ROWS = [{"project": "pockets", "items": None, "unparsed": 0, "closed": {1: False},
             "features": [
                 {"number": 2, "title": "Prove the classifier", "state": "in flight — issue #1",
                  "kind": "in flight", "implements": [1], "blocked_by": []},
                 {"number": 3, "title": "Capture a document", "state": "blocked by #2",
                  "kind": "blocked", "implements": [], "blocked_by": [2]}]}]

    def test_features_land_in_their_state_column(self):
        out = T.render_board(self.ROWS)
        self.assertIn("IN FLIGHT · 1", out)
        self.assertIn("BLOCKED · 1", out)
        self.assertIn("DONE · 0", out)

    def test_an_empty_done_column_says_why(self):
        """DONE·0 is true and uncomfortable. Hiding it would be the comfortable
        lie; proposal 05 means a feature is done when the sponsor closes it."""
        out = T.render_board(self.ROWS)
        self.assertIn("a feature is done when you close it", out)

    def test_a_blocked_feature_gets_no_bar_and_no_percentage(self):
        """An empty track reads as 0%, and 0% is a claim nothing supports."""
        pct, note = T.feature_pct(self.ROWS[0]["features"][1], {})
        self.assertIsNone(pct)
        self.assertIn("blocked by #2", note)
        self.assertNotIn('<div class="bar">', T.render_board([{
            "project": "p", "items": None, "unparsed": 0, "closed": {},
            "features": [self.ROWS[0]["features"][1]]}]))


class TheEstatePageStatesItsDenominator(unittest.TestCase):
    """#71. A figure that silently averages over projects which declared
    nothing is proposal 08's failure mode, and it binds hardest here because
    this is the number the sponsor asked for by name."""

    ROWS = [{"project": "pockets", "items": None, "unparsed": 0, "closed": {1: True},
             "features": [{"number": 2, "title": "A feature", "state": "in flight — issue #1",
                           "kind": "in flight", "implements": [1], "blocked_by": []}]},
            {"project": "finance-tracker", "items": (18, 54), "unparsed": 0,
             "features": None, "closed": {}}]

    def _data(self, rows):
        return {"features": rows, "history": [], "drift": [], "worktrees": [],
                "needs_input": {}, "contested": [], "pipeline": None, "cost": {}}

    def test_the_figure_names_how_many_projects_it_covers(self):
        """It moved from the retired LEDGER to ALL (#81) — a statement about
        every project cannot sit on a page showing one."""
        out = T.render_all(self._data(self.ROWS))
        self.assertIn("1 of 2 projects", out)

    def test_registerless_projects_are_excluded_not_averaged_in(self):
        pct, n, with_reg, total = T.whole_product(self.ROWS)
        self.assertEqual((n, with_reg, total), (1, 1, 2))
        self.assertEqual(pct, 100)   # the one declared feature is complete

    def test_a_blocked_feature_counts_as_undone_not_as_absent(self):
        """Dropping unscored features from the denominator would flatter the
        figure: a blocked feature is undone, not out of scope."""
        rows = [{"project": "p", "items": None, "unparsed": 0, "closed": {1: True},
                 "features": [
                     {"number": 2, "title": "done one", "state": "in flight — issue #1",
                      "kind": "in flight", "implements": [1], "blocked_by": []},
                     {"number": 3, "title": "blocked one", "state": "blocked by #2",
                      "kind": "blocked", "implements": [], "blocked_by": [2]}]}]
        self.assertEqual(T.whole_product(rows)[0], 50)

    def test_no_registers_anywhere_says_so_rather_than_zero(self):
        rows = [{"project": "p", "items": (1, 5), "unparsed": 0,
                 "features": None, "closed": {}}]
        self.assertIsNone(T.whole_product(rows))
        self.assertIn("no whole-product figure", T.render_all(self._data(rows)))


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

    def test_neither_tab_can_see_a_worktree_at_all(self):
        """The board and ledger are built from the declared register, and take
        no worktree argument — so they cannot leak a name, by construction
        rather than by discipline.

        Deliberately NOT asserting that a branch name typed into the sponsor's
        own State column is suppressed: that is his prose, and rendering what
        he wrote is faithful. The defect #65 fixed was the Tower *deriving*
        labels from directory names, which is a different thing.
        """
        import inspect
        self.assertNotIn("worktrees", set(inspect.signature(T.render_board).parameters),
                         "render_board takes worktrees")


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
        out = T.render_board([{"project": "finance-tracker", "features": None,
                               "items": (18, 54), "unparsed": 0, "closed": {}}])
        self.assertIn("no features declared", out)
        self.assertNotIn("0%", out)
        self.assertIn("against no product definition", out)

    def test_registerless_projects_are_one_line_not_one_each(self):
        """Five separate apologies shouted over the one project that had real
        features — the layout defect that prompted proposal 11."""
        rows = [{"project": n, "features": None, "items": (1, 5), "unparsed": 0,
                 "closed": {}} for n in ("a", "b", "c", "d", "e")]
        self.assertEqual(T.render_board(rows).count("no features declared"), 1)

    def test_a_feature_lands_in_the_column_its_register_says(self):
        """State comes from the sponsor's own State column, never inferred from
        whether the issues happen to be shut — proposal 05."""
        row = {"project": "p", "items": None, "unparsed": 0,
               "features": [{"number": 2, "title": "A feature", "state": "in flight — issue #1",
                             "kind": "in flight", "implements": [1], "blocked_by": []}],
               "closed": {1: True}}
        out = T.render_board([row])
        self.assertIn("IN FLIGHT · 1", out)
        self.assertIn("DONE · 0", out)


class TheScreenSaysWhenItIsStale(unittest.TestCase):
    """Issue #73. Tower.app runs a pinned checkout refreshed only by
    `build_towerapp.sh --install`, so it falls behind on every merge — measured
    two hours after one rebuild, and two days behind before that, serving the
    pre-proposal-09 screen while every session reported it fixed."""

    HDR = {"rules": "114-abc1234", "chips": []}

    def test_silent_when_current(self):
        """A staleness line that is always present becomes wallpaper, which is
        finding 3 of the same proposal. Absent, not 'up to date'."""
        self.assertNotIn("stale", T.render_header(self.HDR, 0, None))
        self.assertNotIn("restart", T.render_header(self.HDR, 0, None))

    def test_names_the_gap_and_the_remedy_when_behind(self):
        out = T.render_header(self.HDR, 0, {"here": "208c789", "behind": 5})
        self.assertIn("208c789", out)
        self.assertIn("5 ahead", out)
        self.assertIn("restart to update", out)

    def test_a_checkout_ahead_of_main_is_not_stale(self):
        """A worktree ahead of main is a session doing its job. Calling that
        stale would put the warning on precisely the screens most likely to be
        read, which is how a signal dies."""
        import subprocess
        here = T.run([T.GIT, "-C", str(T.RULES), "rev-parse", "--abbrev-ref", "HEAD"])
        counts = T.run([T.GIT, "-C", str(T.RULES), "rev-list", "--left-right",
                        "--count", "HEAD...origin/main"])
        if not counts:
            self.skipTest("no origin/main to compare against")
        ahead, behind = (int(n) for n in counts.split())
        if behind:
            self.skipTest(f"this checkout is genuinely {behind} behind")
        self.assertIsNone(T._staleness_now(), f"branch {here} is {ahead} ahead, not stale")


class OnlyRealCollisionsAreContested(unittest.TestCase):
    """Issue #74. Before the filter, 3 of 5 contested pairs on the live tree
    were AGENT-LOG.md, which carries merge=ours — they could not conflict by
    construction. Three in five teaches a person to ignore amber, which costs
    the two that are real."""

    def _repo(self, gitattributes=None):
        import subprocess, tempfile
        d = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", d], check=True)
        if gitattributes is not None:
            (Path(d) / ".gitattributes").write_text(gitattributes)
        return Path(d)

    def test_a_driver_resolved_file_is_filtered(self):
        r = self._repo("AGENT-LOG.md merge=ours\nCHANGELOG.md merge=union\n")
        got = T.driver_resolved(r, {"AGENT-LOG.md", "CHANGELOG.md", "app.py"})
        self.assertEqual(got, {"AGENT-LOG.md", "CHANGELOG.md"})

    def test_glob_rules_are_honoured_not_just_literal_names(self):
        """`*.md merge=union` must filter as reliably as a named file — which is
        why this asks git rather than parsing .gitattributes by hand."""
        r = self._repo("*.md merge=union\n")
        self.assertEqual(T.driver_resolved(r, {"anything.md", "code.py"}), {"anything.md"})

    def test_a_project_without_the_rule_still_reports_the_collision(self):
        """The filter reflects what is *installed*, not what the shared template
        says. #57 landed because four projects had drifted on exactly this."""
        r = self._repo("")
        self.assertEqual(T.driver_resolved(r, {"AGENT-LOG.md"}), set())

    def test_failure_degrades_to_warning_not_to_silence(self):
        """Over-warning is recoverable; under-warning hides a real collision."""
        self.assertEqual(T.driver_resolved(Path("/nonexistent-repo-xyz"), {"a.md"}), set())

    def test_contested_pairs_drops_the_resolved_file(self):
        r = self._repo("AGENT-LOG.md merge=ours\n")
        wts = [_wt("a", files=["AGENT-LOG.md", "real.py"], path=r),
               _wt("b", files=["AGENT-LOG.md", "real.py"], path=r)]
        files = {f for _, _, f in T.contested_pairs(wts)}
        self.assertEqual(files, {"real.py"})


class TheBandCarriesTheDecisionQueue(unittest.TestCase):
    """#75. Open PRs reached the band only from worktrees with a mapped issue,
    so a PR from an unmapped branch was invisible — three were open during the
    session that found this, one from an unrelated session."""

    Q = {"count": 3, "oldest": 0, "projects": ["common-rules"], "numbers": [62, 69, 72]}

    def test_the_queue_appears_and_names_the_prs(self):
        out = T.render_needs_you([], {}, [], None, self.Q, [])
        self.assertIn("3 decision(s) waiting", out)
        self.assertIn("#62", out)

    def test_the_queue_leads_the_band(self):
        """It is the autopilot's blocking state, so it goes first."""
        wt = [_wt("w", issue_title="a thing")]
        out = T.render_needs_you(wt, {"w": {"why": "waiting on you", "age": "1m"}},
                                 [], None, self.Q, [])
        self.assertLess(out.index("decision(s) waiting"), out.index("a thing"))

    def test_no_queue_means_no_row(self):
        self.assertNotIn("decision(s) waiting", T.render_needs_you([], {}, [], None, None, []))


class DriftIsOneLineNotAQueue(unittest.TestCase):
    """#75 gave each drifted project a band row, capped at two plus a count. On
    the live estate that still filled the band: 8 items, 6 of them drift and
    contested notes, exactly 1 an actual decision.

    And the drift was largely self-inflicted — every merge to common-rules bumps
    the version, so a day of work there pushed every project 28–31 behind and
    the band filled with nagging about it. Drift is a *state*; the header
    already carries it. One line here, saying how bad and what to run."""

    DRIFT = [{"project": f"p{i}", "behind": 30 - i, "stamped": 100, "current": 130}
             for i in range(5)]

    def test_five_drifted_projects_produce_one_row(self):
        out = T.render_needs_you([], {}, [], None, None, self.DRIFT)
        self.assertEqual(out.count("you-row"), 1)

    def test_it_names_how_bad_and_what_to_run(self):
        out = T.render_needs_you([], {}, [], None, None, self.DRIFT)
        self.assertIn("5 project(s) behind the rules", out)
        self.assertIn("worst is p0 at 30", out)
        self.assertIn("rulecheck --align", out)

    def test_never_stamped_is_still_called_out_by_name(self):
        """It is a different fact from "behind", and reporting it as 0 behind
        would be the same lie as reporting undeclared scope as 0% done."""
        drift = self.DRIFT + [{"project": "idea-lab", "behind": None}]
        out = T.render_needs_you([], {}, [], None, None, drift)
        self.assertIn("never stamped: idea-lab", out)

    def test_no_drift_means_no_row(self):
        self.assertNotIn("behind the rules",
                         T.render_needs_you([], {}, [], None, None, []))

    def test_an_empty_band_still_collapses_to_one_line(self):
        out = T.render_needs_you([], {}, [], None, None, [])
        self.assertIn("nothing needs you", out)
        self.assertNotIn("you-row", out)


class ASponsorClosedFeatureIsDone(unittest.TestCase):
    """The headline read **0% of declared scope** while four features were
    declared done. Completion came only from closed implementing issues, and a
    `built` feature names none — the work predates the register.

    Proposal 05 already settles it: the sponsor closes features, and his State
    column is the authority. This was the first number on the screen and the one
    he asked for by name."""

    def _f(self, kind, implements=()):
        return {"number": 1, "title": "t", "state": kind, "kind": kind,
                "implements": list(implements), "blocked_by": []}

    def test_a_done_feature_counts_as_complete_without_issues(self):
        pct, note = T.feature_pct(self._f("done"), {})
        self.assertEqual(pct, 100)
        self.assertIn("you closed it", note)

    def test_the_whole_product_figure_reflects_them(self):
        rows = [{"project": "p", "items": None, "unparsed": 0, "closed": {},
                 "features": [self._f("done"), self._f("done"),
                              self._f("blocked"), self._f("blocked")]}]
        self.assertEqual(T.whole_product(rows)[0], 50)

    def test_a_blocked_feature_still_counts_as_undone(self):
        """Unchanged: dropping unscored features would flatter the figure."""
        rows = [{"project": "p", "items": None, "unparsed": 0, "closed": {},
                 "features": [self._f("blocked")]}]
        self.assertEqual(T.whole_product(rows)[0], 0)


class ProgressReportsWhatHappened(unittest.TestCase):
    """#66 and #63. The history is recoverable from each checklist's own git
    log, so no new record file and no revival of the logbook proposal 08
    rejected."""

    # the real finance-tracker shape: seven completed while the percentage FELL
    FT = [("2026-08-03", 9, 25), ("2026-08-05", 16, 41), ("2026-08-07", 16, 51)]

    def test_a_falling_percentage_while_work_completes_is_called_out(self):
        """The case one number actively hides: 36% -> 31% while seven items
        were completed, because scope grew by 26."""
        out = T.render_progress([{"project": "finance-tracker", "points": self.FT}])
        self.assertIn("36% → 31%", out)
        self.assertIn("scope grew by 26", out)

    def test_velocity_is_a_measurement_and_names_its_window(self):
        got = T.velocity(self.FT)
        self.assertEqual(got[1], 7)
        out = T.render_progress([{"project": "f", "points": self.FT}])
        self.assertIn("in the last 7 days", out)

    def test_no_forecast_in_the_data_rows(self):
        """Proposal 08 refused an ETA on four active days; #63 held the line on
        six. A rate is a fact about the past, a date is a claim about a future
        nothing here supports.

        Scoped to the rows, not the whole page: the footnote says the words
        "no ETA" deliberately, and a naive substring check flags the disclaimer
        that exists to prevent the very thing it is checking for.
        """
        out = T.render_progress([{"project": "f", "points": self.FT}])
        rows = out[out.index('<div class="prog">'):out.index("</div>", out.index('class="pnote"'))]
        for word in ("ETA", "projected", "on track", "at this rate", "estimated",
                     "remaining", "will be"):
            self.assertNotIn(word, rows, f"forecast language {word!r} in the data")

    def test_a_shrinking_total_is_shown_as_a_re_scope_not_smoothed(self):
        """mac-explorer's total really went 8 -> 5. A dip is information."""
        import datetime
        today = datetime.date.today().isoformat()
        pts = [("2026-08-05", 1, 8), (today, 1, 5)]
        self.assertEqual(T.moved(pts), (1, 1, 8, 5))
        self.assertIn("re-scoped", T.render_progress([{"project": "m", "points": pts}]))

    def test_two_lines_are_drawn_not_one(self):
        """A burnup, not a burndown: the gap between done and total is the
        point, so a single line would defeat the whole region."""
        svg = T.sparkline(self.FT)
        self.assertEqual(svg.count("<polyline"), 2)
        self.assertIn("sp-done", svg)
        self.assertIn("sp-total", svg)

    def test_too_little_history_says_so_rather_than_drawing_nothing(self):
        self.assertIn("enough history", T.render_progress([]))


class SwitchingIsByProject(unittest.TestCase):
    """#81. The lenses answered a volume problem — six projects' data does not
    fit in 900px. One project's does, so the split is retired rather than
    re-cut."""

    ROWS = [{"project": "pockets", "items": (5, 14), "unparsed": 0, "closed": {1: False},
             "features": [{"number": 2, "title": "Prove the classifier",
                           "state": "in flight — issue #1", "kind": "in flight",
                           "implements": [1], "blocked_by": []}]},
            {"project": "finance-tracker", "items": (19, 54), "unparsed": 0,
             "features": None, "closed": {}}]

    def _data(self):
        return {"features": self.ROWS, "history": [], "drift": [],
                "worktrees": [_wt("w1", project="pockets"),
                              _wt("w2", project="finance-tracker")],
                "needs_input": {}, "contested": [], "pipeline": None,
                "cost": {"pockets": {"week": 1_500_000, "total": 4_000_000}},
                "coupling": []}

    def test_the_tabs_are_links_carrying_the_project(self):
        """Not DOM state: the page re-requests itself every 10s and the DOM does
        not survive that. Measured when the view tabs were built — a CSS
        :checked tab reverted on every reload, a query string did not."""
        out = T.render_tabs([T.ALL, "pockets"], "pockets")
        self.assertIn('href="/?project=pockets"', out)
        self.assertIn('href="/?project=all"', out)
        self.assertNotIn("<input", out)      # no radio/checkbox tab state

    def test_a_project_page_shows_only_that_project(self):
        out = T.render_project("pockets", self._data())
        self.assertIn("Prove the classifier", out)
        self.assertNotIn("finance-tracker", out)

    def test_a_project_page_carries_everything_about_it(self):
        """The point of the rework: no second click for the whole picture."""
        data = self._data()
        data["history"] = [{"project": "pockets",
                            "points": [("2026-08-02", 0, 10), ("2026-08-07", 5, 14)]}]
        out = T.render_project("pockets", data)
        for expect in ("IN FLIGHT", "PROGRESS", "SESSIONS"):
            self.assertIn(expect, out)

    def test_all_lists_every_project_including_the_registerless(self):
        out = T.render_all(self._data())
        self.assertIn("pockets", out)
        self.assertIn("finance-tracker", out)
        self.assertIn("no features declared", out)

    def test_an_unknown_project_is_not_an_error(self):
        """A stale bookmark or a removed project must not 500 the page."""
        self.assertIn(T.ALL, T.tab_projects(self._data()))


class NeedsYouIsNeverFilteredByTab(unittest.TestCase):
    """#81's one hard rule. Filtering the band to the selected project is the
    tempting simplification, and the single change that would make the screen
    actively worse: a decision waiting in an app the sponsor is not looking at
    must still reach him."""

    def test_the_band_takes_no_project_argument(self):
        """By construction rather than by discipline — it cannot be filtered if
        it is never told which project is selected."""
        import inspect
        params = set(inspect.signature(T.render_needs_you).parameters)
        self.assertNotIn("project", params)

    def test_it_counts_worktrees_from_every_project(self):
        wts = [_wt("a", project="pockets", issue_title="pockets thing"),
               _wt("b", project="finance-tracker", issue_title="finance thing")]
        out = T.render_needs_you(wts, {"a": {"why": "waiting on you", "age": "1m"},
                                       "b": {"why": "waiting on you", "age": "2h"}},
                                 [], None, None, [])
        self.assertIn("pockets thing", out)
        self.assertIn("finance thing", out)


class CostIsPerWeekNotPerFeature(unittest.TestCase):
    """#76, rescoped after measurement. Per feature attributed **0%** of
    67,393,007 tokens: 96.8% sits in `(main checkout)` and `(management)`
    pseudo-tasks, and 3.1% in worktrees deleted when their work landed. Most
    work never happens in a task worktree, and the ones that do have their key
    destroyed by finishing. So the unit is the week."""

    HIST = [{"project": "pockets",
             "points": [("2026-08-02", 0, 10), ("2026-08-07", 5, 14)]}]
    COST = {"pockets": {"week": 1_500_000, "total": 4_000_000}}

    def test_the_week_and_what_moved_sit_together(self):
        """The pairing is the point: a cost with no movement beside it is a
        number, and movement with no cost is half an answer."""
        out = T.render_progress(self.HIST, self.COST)
        self.assertIn("1.5M tokens in the last 7 days", out)
        self.assertIn("completed in the last 7 days", out)

    def test_all_time_is_shown_but_second(self):
        self.assertIn("4.0M all time", T.render_progress(self.HIST, self.COST))

    def test_a_project_with_no_recorded_cost_says_nothing(self):
        out = T.render_progress(self.HIST, {})
        self.assertNotIn("tokens", out)

    def test_no_cost_appears_against_any_individual_feature(self):
        """The thing #76 originally asked for and the data cannot support.
        A per-feature number here would be fabricated."""
        row = {"project": "pockets", "items": None, "unparsed": 0, "closed": {1: False},
               "features": [{"number": 2, "title": "A feature",
                             "state": "in flight — issue #1", "kind": "in flight",
                             "implements": [1], "blocked_by": []}]}
        out = T.render_board([row])
        for unit in ("tokens", "M", "k tok"):
            self.assertNotIn(f'>{unit}', out)

    def test_human_tokens_reads_at_a_glance(self):
        self.assertEqual(T.human_tokens(1_500_000), "1.5M")
        self.assertEqual(T.human_tokens(27_600), "27k")
        self.assertEqual(T.human_tokens(940), "940")

    def test_the_window_is_named_wherever_it_is_used(self):
        """A delta or a cost with an unstated window is not a measurement."""
        out = T.render_progress(self.HIST, self.COST)
        self.assertIn(f"last {T.COST_WINDOW_DAYS} days", out)


class ARenderNeverWaitsForACollection(unittest.TestCase):
    """#86. Measured against the running app before this: ~4s per recollect,
    with a 5s cache and a 10s auto-refresh, so the window froze for four
    seconds out of every ten and the visible clock ran up to 14s late. That was
    reported as "outdated data" when the data was correct and merely late."""

    def setUp(self):
        self._data = T._cache["data"]
        self._ts = T._cache["ts"]
        self._collect = T._collect_now
        # Released in tearDown so a background thread from one test cannot
        # still be alive during the next — which is what made the
        # single-refresh assertion see two, from test pollution rather than
        # from a real concurrent refresh.
        self.release = threading.Event()

    def tearDown(self):
        self.release.set()
        for _ in range(100):
            with T._refresh_lock:
                if not T._refresh["running"]:
                    break
            time.sleep(0.01)
        T._cache["data"], T._cache["ts"] = self._data, self._ts
        T._collect_now = self._collect
        with T._refresh_lock:
            T._refresh["running"] = False

    def test_a_stale_cache_is_served_immediately_not_recollected_inline(self):
        """The whole fix. A slow collector must cost nothing at render time."""
        import time
        T._cache["data"] = {"marker": "old"}
        T._cache["ts"] = time.time() - (T.CACHE_TTL + 60)
        def never_finishes():
            self.release.wait(5)
            return {"marker": "new"}

        T._collect_now = never_finishes
        started = time.time()
        got = T.collect()
        elapsed = time.time() - started
        self.assertEqual(got, {"marker": "old"}, "served something other than the cache")
        self.assertLess(elapsed, 0.5, f"collect() blocked for {elapsed:.2f}s")

    def test_only_one_background_refresh_runs_at_a_time(self):
        """Otherwise a slow sweep spawns a thread per request and the machine
        does the same expensive work N times over."""
        import time
        T._cache["data"] = {"marker": "old"}
        T._cache["ts"] = time.time() - (T.CACHE_TTL + 60)
        calls = []

        def counted():
            calls.append(1)
            self.release.wait(5)
            return {"marker": "new"}

        T._collect_now = counted
        for _ in range(5):
            T.collect()
        time.sleep(0.2)
        self.assertEqual(len(calls), 1, f"{len(calls)} concurrent refreshes")

    def test_the_first_render_does_wait(self):
        """A page with no data at all is worse than a slow first page, so the
        cold path is deliberately synchronous."""
        T._cache["data"], T._cache["ts"] = None, 0
        T._collect_now = lambda: {"marker": "seeded"}
        self.assertEqual(T.collect(), {"marker": "seeded"})

    def test_the_age_is_reported_not_implied(self):
        import time
        T._cache["data"], T._cache["ts"] = {"x": 1}, time.time() - 42
        self.assertGreaterEqual(T.data_age(), 41)
        T._cache["ts"] = 0
        self.assertIsNone(T.data_age())


class NoFeatureIsEverDropped(unittest.TestCase):
    """Found when the first real registers landed: pockets declared 7 features
    and the board rendered 6 — silently, since #70. The `version 2` one had
    kind `later`, and there was no LATER column, so it fell through the grouping
    into nothing.

    A feature that vanishes is worse than one shown in the wrong column: the
    board is meant to be the answer to "what is the product made of", and a
    quiet undercount makes it a wrong answer that looks right."""

    def _rows(self, kinds):
        return [{"project": "p", "items": None, "unparsed": 0, "closed": {},
                 "features": [{"number": i, "title": f"feature {i}", "state": k,
                               "kind": k, "implements": [], "blocked_by": []}
                              for i, k in enumerate(kinds)]}]

    def test_every_kind_the_parser_produces_has_a_column(self):
        columns = {k for k, _, _ in T.BOARD_COLUMNS}
        produced = {"in flight", "blocked", "later", "done", "next"}
        self.assertTrue(produced <= columns,
                        f"no column for {produced - columns}")

    def test_all_features_render_whatever_their_state(self):
        kinds = ["in flight", "next", "blocked", "later", "done"]
        out = T.render_board(self._rows(kinds))
        for i in range(len(kinds)):
            self.assertIn(f"feature {i}", out, f"kind {kinds[i]!r} was dropped")

    def test_an_unrecognised_state_is_parked_not_lost(self):
        """A register can be edited by hand, so an unexpected state is a thing
        to correct — not a reason for the feature to stop existing."""
        out = T.render_board(self._rows(["something nobody anticipated"]))
        self.assertIn("feature 0", out)

    def test_a_state_the_register_does_not_spell_out_is_queued_not_invisible(self):
        """`| #7 | Something | |` — no state at all. It is queued."""
        feats = T.parse_features(
            "## Features\n\n| # | Feature | State |\n|---|---|---|\n"
            "| [#7](x) | A thing nobody has stated a state for | |\n")
        self.assertEqual(feats[0]["kind"], "next")
        self.assertIn("A thing nobody", T.render_board(
            [{"project": "p", "items": None, "unparsed": 0, "closed": {},
              "features": feats}]))


class TheRegisterComesFromMainNotTheCheckout(unittest.TestCase):
    """#91. pip's register was merged and on origin/main while its checkout sat
    a commit behind with another session mid-work, so the Tower reported "no
    features declared" for a project that had declared nine.

    A feature is declared when its register is merged. Whether a working copy
    has pulled is an accident of who is working where — the same class of
    defect as #73, an answer that quietly depends on local state it does not
    mention."""

    def _repo(self, committed, working=None):
        import subprocess, tempfile
        d = Path(tempfile.mkdtemp())
        git = [T.GIT, "-C", str(d)]
        subprocess.run([T.GIT, "init", "-q", "-b", "main", str(d)], check=True)
        subprocess.run(git + ["config", "user.email", "t@t"], check=True)
        subprocess.run(git + ["config", "user.name", "t"], check=True)
        (d / "CLAUDE-checklist.md").write_text(committed)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "register"], check=True)
        if working is not None:
            (d / "CLAUDE-checklist.md").write_text(working)
        return d

    TABLE = ("## Features\n\n| # | Feature | State |\n|---|---|---|\n"
             "| [#2](x) | A declared feature | **in flight** — issue #1 |\n")

    def test_a_checkout_behind_main_still_reports_the_merged_register(self):
        """The exact live case: committed register, working file without it."""
        d = self._repo(self.TABLE, working="## Now\n\n- [ ] nothing here\n")
        feats = T.parse_features(T.register_source(d))
        self.assertEqual(len(feats), 1, "read the stale working file, not main")

    def test_an_uncommitted_register_does_not_count_yet(self):
        """Correct rather than unfortunate: a feature is not declared until it
        is merged, which is the rule its own State column follows."""
        d = self._repo("## Now\n\n- [ ] nothing\n", working=self.TABLE)
        self.assertEqual(T.parse_features(T.register_source(d)), [])

    def test_a_repo_with_no_commits_falls_back_to_the_working_file(self):
        """Degrading to LESS scope than exists is the failure mode here, so the
        working file is a resort rather than an error."""
        import subprocess, tempfile
        d = Path(tempfile.mkdtemp())
        subprocess.run([T.GIT, "init", "-q", str(d)], check=True)
        (d / "CLAUDE-checklist.md").write_text(self.TABLE)
        self.assertEqual(len(T.parse_features(T.register_source(d))), 1)

    def test_a_path_that_is_not_a_repo_is_not_an_exception(self):
        self.assertEqual(T.register_source(Path("/nonexistent-xyz")), "")


class AFeatureIsNotAlsoATicket(unittest.TestCase):
    """#93. A feature IS a GitHub issue — that is how the register identifies it
    — so every declared feature also appeared as queued work. Measured: 32 of
    103 open issues were features, and QUEUED read 95 when the real queue was
    63. Per project it was every single one: 9 of 9, 9 of 9, 7 of 7, 7 of 7.

    The same defect proposal 10 removed once already, from the other direction:
    IN FLIGHT counted git ahead-counts as work; this counted features as
    tickets. A feature is the thing tickets roll up into, and listing it as
    queued invites picking it up as one."""

    def _issue(self, n, title="a ticket"):
        return {"project": "p", "number": n, "title": title}

    def test_a_declared_feature_is_excluded_from_the_queue(self):
        keys = frozenset([T.issue_key("p", 2)])
        rows = [self._issue(1), self._issue(2, "A FEATURE"), self._issue(3)]
        kept = [r for r in rows
                if T.issue_key(r["project"], r["number"]) not in keys]
        self.assertEqual([r["number"] for r in kept], [1, 3])

    def test_pipeline_data_takes_the_feature_keys(self):
        """The exclusion cannot happen unless the pipeline is told, and it is
        told only because collect() computes features first — an ordering
        dependency that is invisible in the code without this."""
        import inspect
        self.assertIn("feature_keys",
                      inspect.signature(T.pipeline_data).parameters)

    def test_features_are_computed_before_the_pipeline(self):
        """If this order is ever swapped back, the exclusion silently stops
        working and every feature reappears as queued work — with no error and
        no failing assertion anywhere else."""
        src = TOWER.read_text()
        body = src[src.index("def _collect_now("):]
        self.assertLess(body.index("safe(feature_data"),
                        body.index("safe(pipeline_data"),
                        "pipeline_data runs before feature_data, so it cannot "
                        "be told which issues are features")


class TheHeaderCountMatchesTheRows(unittest.TestCase):
    """It read "NEEDS YOU · 8" above five rows, because drift was still counted
    per project after being consolidated into one line.

    A header that disagrees with the thing directly under it is worse than no
    header — it makes the reader distrust both, which is what "I don't know what
    to do" sounds like."""

    def test_consolidated_drift_counts_as_one(self):
        drift = [{"project": f"p{i}", "behind": 30, "stamped": 100,
                  "current": 130} for i in range(5)]
        out = T.render_needs_you([], {}, [], None, None, drift)
        self.assertEqual(out.count("you-row"), 1,
                         "five drifted projects should render one row")

    def test_the_rendered_row_count_is_derivable_without_rendering(self):
        """render_page computes the header number separately from the body, so
        the two can drift apart. This pins the arithmetic they must share."""
        drift = [{"project": f"p{i}", "behind": 30, "stamped": 100,
                  "current": 130} for i in range(5)]
        queue = {"count": 1, "oldest": 0, "projects": ["x"], "numbers": [62]}
        contested = [("a", "b", "f.py")]
        wts = [_wt("a"), _wt("b"), _wt("c", issue_title="waiting thing")]
        needs = {"c": {"why": "waiting on you", "age": "1m"}}
        out = T.render_needs_you(wts, needs, contested, None, queue, drift)
        expected = (len(needs) + len(T.contested_notes(contested)) // 2
                    + (1 if queue else 0) + (1 if drift else 0))
        self.assertEqual(out.count("you-row"), expected,
                         "header arithmetic and rendered rows disagree")


class TheEstateTableIsNotCapped(unittest.TestCase):
    """Capping `.cell.wide` to make room for the estate table capped the estate
    table too — both regions are wide — so the ALL view rendered 3 of 6 projects
    above a large empty gap. Worse than the inverted priority it was meant to
    fix, and only visible by opening the window.

    A CSS selector that matches more than intended fails silently and looks like
    a layout choice, so it is pinned here rather than left to the eye."""

    def test_only_the_strip_carries_the_cap(self):
        css = T.CSS
        self.assertIn(".cell.strip-cell", css)
        # the bare .cell.wide rule must not constrain height
        import re
        m = re.search(r"\.grid > \.cell\.wide \{([^}]*)\}", css)
        self.assertIsNotNone(m, "the .cell.wide rule went missing")
        self.assertNotIn("max-height", m.group(1),
                         "capping .cell.wide also caps the projects table")

    def test_the_strip_cell_is_the_one_marked(self):
        src = TOWER.read_text()
        self.assertIn('class="cell wide strip-cell"', src)
        self.assertIn('<div class="cell wide">{features}</div>', src)


class TheBarFollowsTheFeatures(unittest.TestCase):
    """Reported as "I am closing issues but the progress bar does not
    increase". Two separate causes, both real.

    The bar showed **checklist ticks**. Closing a GitHub issue moves a
    feature's percentage and never ticks a `- [x]` box, so the most prominent
    thing on the row measured something the sponsor was not doing.

    And 18 issues were closed in a day with **17 inside no feature**, so even a
    correct bar stays nearly still. That is not a bug in the bar — it is work
    the register does not claim, and it has to be visible to be decided on."""

    def _row(self, feats, closed, items=(20, 53)):
        return {"project": "p", "items": items, "unparsed": 0,
                "features": feats, "closed": closed, "closed_at": {}}

    def test_completion_comes_from_features_not_checklist_ticks(self):
        f = [{"number": 2, "title": "t", "state": "in flight — issue #1",
              "kind": "in flight", "implements": [1], "blocked_by": []}]
        row = self._row(f, {1: True}, items=(20, 53))   # ticks would say 38%
        self.assertEqual(T.project_completion(row), 100)

    def test_closing_an_implementing_issue_moves_it(self):
        f = [{"number": 2, "title": "t", "state": "in flight — issue #1",
              "kind": "in flight", "implements": [1, 3], "blocked_by": []}]
        self.assertEqual(T.project_completion(self._row(f, {1: False, 3: False})), 0)
        self.assertEqual(T.project_completion(self._row(f, {1: True, 3: False})), 50)

    def test_a_project_with_no_register_falls_back_to_ticks(self):
        self.assertIsNone(T.project_completion(self._row(None, {})))

    def test_the_bar_and_the_headline_use_the_same_arithmetic(self):
        """They are computed in different functions and would otherwise drift."""
        f = [{"number": 2, "title": "t", "state": "in flight — issue #1",
              "kind": "in flight", "implements": [1, 3], "blocked_by": []}]
        row = self._row(f, {1: True, 3: False})
        self.assertEqual(T.project_completion(row), T.whole_product([row])[0])

    def test_closures_no_feature_claims_are_counted(self):
        """Otherwise the screen is silent about most of the work done."""
        import datetime
        today = datetime.date.today().isoformat()
        f = [{"number": 2, "title": "t", "state": "in flight — issue #1",
              "kind": "in flight", "implements": [1], "blocked_by": []}]
        row = self._row(f, {1: True, 9: True, 10: True})
        row["closed_at"] = {1: today, 9: today, 10: today}
        self.assertEqual(T.unclaimed_closed(row), 2, "#1 is claimed; #9 and #10 are not")

    def test_a_feature_issue_itself_is_not_unclaimed_work(self):
        import datetime
        today = datetime.date.today().isoformat()
        f = [{"number": 2, "title": "t", "state": "done", "kind": "done",
              "implements": [], "blocked_by": []}]
        row = self._row(f, {2: True})
        row["closed_at"] = {2: today}
        self.assertEqual(T.unclaimed_closed(row), 0)

    def test_render_all_shows_the_feature_percentage_not_the_ticks(self):
        """The unit test on project_completion cannot fail from the render path
        alone reverting to ticks -- this exercises the actual HTML."""
        f = [{"number": 2, "title": "t", "state": "in flight — issue #1",
              "kind": "in flight", "implements": [1], "blocked_by": []}]
        row = self._row(f, {1: True}, items=(20, 53))   # ticks would render 38%
        data = {"features": [row], "history": [], "drift": [], "worktrees": [],
                "needs_input": {}, "contested": [], "pipeline": None, "cost": {}}
        out = T.render_all(data)
        self.assertIn("100%", out)
        self.assertNotIn("38%", out)


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
