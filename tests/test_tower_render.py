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

    def test_long_feature_title_survives_the_board(self):
        row = {"project": "pockets", "items": None, "unparsed": 0, "closed": {1: False},
               "features": [{"number": 2, "title": LONG_TITLE, "state": "in flight — issue #1",
                             "kind": "in flight", "implements": [1], "blocked_by": []}]}
        self.assertIn(LONG_TITLE, T.render_board([row]))
        self.assertIn(LONG_TITLE, T.render_ledger([row], None))

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
            ("ledger", T.render_ledger(None, None)),
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


class TheLedgerStatesItsDenominator(unittest.TestCase):
    """#71. A figure that silently averages over projects which declared
    nothing is proposal 08's failure mode, and it binds hardest here because
    this is the number the sponsor asked for by name."""

    ROWS = [{"project": "pockets", "items": None, "unparsed": 0, "closed": {1: True},
             "features": [{"number": 2, "title": "A feature", "state": "in flight — issue #1",
                           "kind": "in flight", "implements": [1], "blocked_by": []}]},
            {"project": "finance-tracker", "items": (18, 54), "unparsed": 0,
             "features": None, "closed": {}}]

    def test_the_figure_names_how_many_projects_it_covers(self):
        out = T.render_ledger(self.ROWS, None)
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
        self.assertIn("no whole-product figure", T.render_ledger(rows, None))


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
        for fn in (T.render_board, T.render_ledger):
            params = set(inspect.signature(fn).parameters)
            self.assertNotIn("worktrees", params, f"{fn.__name__} takes worktrees")


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
        self.assertIsNone(T.staleness(), f"branch {here} is {ahead} ahead, not stale")


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


class DriftEscalatesInsteadOfSitting(unittest.TestCase):
    """#75. `5 behind: …` sat unchanged in the header through a whole working
    day. A permanent warning at constant volume is decoration."""

    def test_a_far_behind_project_earns_a_row(self):
        out = T.render_needs_you([], {}, [], None, None,
                                 [{"project": "pip", "behind": 17,
                                   "stamped": 103, "current": 120}])
        self.assertIn("17 rules versions behind", out)

    def test_never_stamped_is_its_own_case_not_zero(self):
        """Reporting a project that has never recorded a version as '0 behind'
        would be the same lie as reporting undeclared scope as 0% done."""
        out = T.render_needs_you([], {}, [], None, None,
                                 [{"project": "idea-lab", "behind": None}])
        self.assertIn("never recorded a rules version", out)
        self.assertNotIn("0 rules versions", out)

    def test_the_rows_are_capped_so_the_band_stays_scannable(self):
        """Measured on the live estate every project was 8-17 versions behind,
        so escalating all five put five rows in the band and recreated the
        wallpaper one level up. The worst two get rows; the rest is a count."""
        drift = [{"project": f"p{i}", "behind": 10 + i, "stamped": 100, "current": 120}
                 for i in range(5)]
        out = T.render_needs_you([], {}, [], None, None, drift)
        self.assertEqual(out.count("rules versions behind"), T.DRIFT_ROWS_SHOWN)
        self.assertIn("+3 more project(s) behind the rules", out)
        # and the worst is the one that earns a row
        self.assertIn("p4 is 14 rules versions behind", out)

    def test_full_project_names_in_prose_not_the_compact_tag(self):
        """project_tag is built for chips ("finance #41") and reads as a typo in
        a sentence — "idea has never recorded a rules version"."""
        out = T.render_needs_you([], {}, [], None, None,
                                 [{"project": "idea-lab", "behind": None}])
        self.assertIn("idea-lab has never recorded", out)

    def test_below_the_threshold_nothing_escalates(self):
        self.assertNotIn("rules versions behind",
                         T.render_needs_you([], {}, [], None, None, []))

    def test_an_empty_band_still_collapses_to_one_line(self):
        """#51's rule, and the whole reason this proposal could add to the band
        at all: reserving empty space is the failure mode proposal 09 fixed."""
        out = T.render_needs_you([], {}, [], None, None, [])
        self.assertIn("nothing needs you", out)
        self.assertNotIn("you-row", out)


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
