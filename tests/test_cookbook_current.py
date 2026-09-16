"""The cookbook is version-controlled and does not drift from the rules it
shows (proposal 28, R-06 -- repair).

R-06 was marked done with its source only in an ephemeral scratchpad: nothing
could "regenerate" a page whose source was never committed, no rule ever said
regeneration was required, and the page went stale for two waves of change --
it still described `docs/OPERATING-RULES.md` as holding the rules content
(folded into HANDOFF.md by proposal 23 M-11) and still showed a six-category
risky-work list that proposal 23 M-08 replaced with `tracker route`. This test
pins down exactly that failure mode: the source must exist under version
control, it must not assert facts the current rule files contradict, and the
regeneration rule must actually be written down somewhere a session reads.

A cookbook rebuild that keeps naming `docs/OPERATING-RULES.md` as the home of
the rules, or keeps the six-category list, fails this test the same way the
real page did -- that is the drift this test exists to catch.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COOKBOOK = ROOT / "docs" / "cookbook.html"
CLAUDE_WORKFLOW = ROOT / "CLAUDE-workflow.md"

# Terms from the six-category risky-work list that proposal 23 M-08 replaced
# with `tracker route` -- CLAUDE-workflow.md's own "Ceremony is opt-in"
# section now states this explicitly: "never a fixed category list here."
SIX_CATEGORY_TERMS = [
    "Money or financial data",
    "Real user data stores",
    "Authentication, credentials or secrets",
    "Release, install or packaging",
    "Cross-cutting changes to shared modules",
]

# The regeneration rule text: a session must be told, somewhere it reads,
# that a Standard change touching warmup/reheat/rules regenerates the
# cookbook and republishes it to its existing URL.
REGEN_RE = re.compile(
    r"docs/cookbook\.html.{0,400}regenerat", re.IGNORECASE | re.DOTALL)
REPUBLISH_RE = re.compile(r"republish", re.IGNORECASE)
EXISTING_URL_RE = re.compile(
    r"existing (artifact|url)|same url|its existing url", re.IGNORECASE)


class TestCookbookSourceIsCommitted(unittest.TestCase):

    def test_cookbook_source_exists_under_version_control(self):
        self.assertTrue(
            COOKBOOK.exists(),
            "docs/cookbook.html is missing -- R-06's source must be "
            "committed to the repo, not left in a session scratchpad")


class TestCookbookDoesNotAssertRetiredFacts(unittest.TestCase):

    def setUp(self):
        if not COOKBOOK.exists():
            self.skipTest("docs/cookbook.html missing -- see other test")
        self.text = COOKBOOK.read_text()

    def test_does_not_call_operating_rules_the_home_of_the_rules(self):
        # docs/OPERATING-RULES.md is now a one-line pointer stub (proposal
        # 23, M-11) -- HANDOFF.md holds the content. The page may still
        # mention the filename in passing (e.g. "folds in ..."), but must
        # not present it as a current source of truth alongside HANDOFF.md
        # the way the original page's meta-row and footer did.
        self.assertNotIn(
            "HANDOFF.md · docs/OPERATING-RULES.md", self.text,
            "cookbook still lists docs/OPERATING-RULES.md as a live source "
            "of truth beside HANDOFF.md -- its content folded into "
            "HANDOFF.md (proposal 23, M-11)")
        self.assertNotIn(
            "built from HANDOFF.md, docs/OPERATING-RULES.md", self.text,
            "cookbook footer still credits docs/OPERATING-RULES.md as a "
            "content source")

    def test_does_not_show_the_retired_six_category_list(self):
        for term in SIX_CATEGORY_TERMS:
            self.assertNotIn(
                term, self.text,
                f"cookbook still shows the six-category risky-work list "
                f"item {term!r} -- proposal 23 M-08 replaced this with "
                f"tracker route, not duplicated it")

    def test_mentions_tracker_route_as_the_current_mechanism(self):
        self.assertIn(
            "tracker route", self.text,
            "cookbook does not mention tracker route, the mechanism that "
            "replaced the six-category list (proposal 23, M-08)")


class TestRegenerationRuleIsWrittenDown(unittest.TestCase):

    def test_claude_workflow_states_the_cookbook_regenerates(self):
        self.assertTrue(CLAUDE_WORKFLOW.exists())
        text = CLAUDE_WORKFLOW.read_text()
        self.assertRegex(
            text, REGEN_RE,
            "CLAUDE-workflow.md does not say the cookbook regenerates when "
            "a Standard change touches warmup/reheat/a rule it shows -- "
            "this is R-06's own done criterion")
        self.assertRegex(
            text, REPUBLISH_RE,
            "CLAUDE-workflow.md's cookbook rule does not say it gets "
            "republished")
        self.assertRegex(
            text, EXISTING_URL_RE,
            "CLAUDE-workflow.md's cookbook rule does not say the republish "
            "goes to the existing URL, not a new artifact")

    def test_regeneration_rule_does_not_restate_t06(self):
        # T-06 (proposal 22) already rules that a published page's <title>
        # never changes on republish. The new cookbook rule must be
        # consistent with that but must not re-derive or restate the title
        # rule itself -- it should reference it instead.
        text = CLAUDE_WORKFLOW.read_text()
        match = REGEN_RE.search(text)
        self.assertIsNotNone(match)
        # Look only at the paragraph containing and following the match --
        # not backward, since T-06's own paragraph (immediately above the
        # cookbook rule) legitimately contains this phrasing when it first
        # defines the title rule. The new rule must not re-derive it.
        window = text[match.start():match.end() + 500]
        self.assertNotIn(
            "not a differing `title` parameter, not by hand", window,
            "the cookbook regeneration rule restates T-06's own wording "
            "instead of pointing back to it")


if __name__ == "__main__":
    unittest.main()
