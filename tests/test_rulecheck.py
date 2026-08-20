"""rulecheck must only ever ask the adoption question of projects that adopt.

Not every folder under apps/ follows these rules. `idea-lab` deliberately does
not — it is v2, and its own LAB-RULES.md says "no gates, no worktrees, no issues
here". rulecheck used to treat every directory as an adopter, so it reported
idea-lab as "NEVER recorded a rules version" forever: a false alarm every
session had to re-derive and dismiss, whose only offered remedy (`--align`)
would have written a stamp asserting something untrue.

The stamp is load-bearing precisely because it is trusted without re-checking —
the next session inherits it and skips reading the rules. So a wrong stamp is
worse than a missing one, and refusing to write one is the behaviour under test.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULECHECK = ROOT / "bin" / "rulecheck"
STAMP = ".common-rules-version"
POINTER = "Shared workflow rules: ../common-rules/CLAUDE-workflow.md — read it.\n"


def run(project: Path, *args, rules_dir: Path | None = None):
    env = {**os.environ, "COMMON_RULES_DIR": str(rules_dir or ROOT)}
    return subprocess.run([sys.executable, str(RULECHECK), "--project", str(project), *args],
                          capture_output=True, text=True, env=env, check=False)


# rulecheck prints its verdict, then (for a stale project) quotes the changelog
# under this heading. See bin/rulecheck, "What changed since (N changelog lines)".
DUMP_MARKER = "What changed since"


def verdict(stdout: str) -> str:
    """rulecheck's own words, with the changelog it quotes cut off.

    A stale project's report quotes the changelog, and the changelog is prose
    *about these rules* -- including the line "common-rules does not adopt
    itself." Asserting against raw stdout therefore searches the verdict and
    its evidence as one string, so a phrase occurring in the evidence reads as
    a verdict.

    That is exactly what broke RealProjectsStillCheck on `main` from the day
    that changelog entry was written: pockets, pip and mac-explorer were
    correctly recognised as adopting and correctly reported stale, and the test
    called them skipped because the changelog it was shown contained the words
    it was grepping for. The projects were fine. The assertion was reading the
    wrong half of the output.

    Same failure the render tests already guard against -- see
    test_tower_render.test_no_forecast_in_the_data_rows, which scopes its
    search to the data rows precisely because the page's own disclaimer
    contains the forecast words it bans.

    Harmless for a non-adopting project: rulecheck returns before printing any
    dump, so there is no marker and the whole of stdout is the verdict.
    """
    return stdout.split(DUMP_MARKER, 1)[0]



class AdoptionIsRead(unittest.TestCase):
    """Adoption comes from the project's own declaration, never from assumption."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def project(self, name, claude_md=None, stamp=None):
        p = self.tmp / name
        p.mkdir()
        if claude_md is not None:
            (p / "CLAUDE.md").write_text(claude_md)
        if stamp is not None:
            (p / STAMP).write_text(stamp + "\n")
        return p

    def test_non_adopting_project_is_not_reported_as_behind(self):
        """The idea-lab case: a CLAUDE.md that names common-rules to disown it.

        The mention alone must not count, or the fix would not fix anything —
        idea-lab's CLAUDE.md says it is "deliberately separate from
        ../common-rules/", which is the opposite of adopting them.
        """
        p = self.project("idea-lab",
                         "This is v2, deliberately separate from ../common-rules/.\n"
                         "No gates, no worktrees, no issues here.\n")
        r = run(p)
        # Not 0: exit 0 means "verified aligned", and nothing was verified here
        # -- there is no version to be aligned or behind on. Not 1 either: 1
        # means "verified, and stale", which is also not what happened. This is
        # its own outcome, "could not check", and it gets its own status (2).
        self.assertEqual(r.returncode, 2, f"expected 'could not check' (2), got:\n{r.stdout}{r.stderr}")
        self.assertIn("does not adopt", verdict(r.stdout))
        self.assertNotIn("NEVER recorded", verdict(r.stdout))

    def test_align_refuses_to_stamp_a_non_adopting_project(self):
        p = self.project("idea-lab", "Deliberately separate from ../common-rules/.\n")
        r = run(p, "--align")
        self.assertEqual(r.returncode, 2)
        self.assertFalse((p / STAMP).exists(),
                         "wrote a stamp claiming adoption into a project that does not adopt")
        self.assertIn("not stamping it", r.stderr)

    def test_pointer_in_claude_md_is_what_makes_a_project_adopt(self):
        p = self.project("finance-tracker", POINTER)
        r = run(p)
        self.assertEqual(r.returncode, 1, "an adopting project with no stamp is behind")
        self.assertIn("NEVER recorded", r.stdout)

    def test_existing_stamp_counts_as_adoption_on_its_own(self):
        """Rewording a CLAUDE.md must not silently un-adopt a project."""
        p = self.project("pockets", "No pointer here any more.\n", stamp="1-deadbee")
        r = run(p)
        self.assertNotIn("does not adopt", verdict(r.stdout),
                         "a project that has aligned before was treated as never having adopted")

    def test_a_project_with_no_claude_md_at_all_does_not_adopt(self):
        p = self.project("scratch")
        r = run(p)
        self.assertEqual(r.returncode, 2)
        self.assertIn("does not adopt", verdict(r.stdout))

    def test_quiet_says_nothing_for_a_non_adopting_project(self):
        """--quiet is for the SessionStart hook; a non-adopter must not print.

        The hook does not read the exit code (a SessionStart hook's exit
        status does not stop the session), so this only pins the *output*
        contract -- the exit code is pinned separately, below.
        """
        p = self.project("idea-lab", "Deliberately separate.\n")
        r = run(p, "--quiet")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), "")


class TheRulesDoNotAdoptThemselves(unittest.TestCase):

    def test_common_rules_itself_is_not_an_adopter(self):
        r = run(ROOT)
        # This is the exact case that motivated giving "could not check" its
        # own status: a session run from inside common-rules used to get exit
        # 0 here -- indistinguishable from "checked, and aligned" -- and
        # treated a vacuous run as a pass.
        self.assertEqual(r.returncode, 2)
        self.assertIn("the rules themselves", r.stdout)
        self.assertNotIn("NEVER recorded", r.stdout)

    def test_common_rules_never_acquires_a_stamp(self):
        r = run(ROOT, "--align")
        self.assertFalse((ROOT / STAMP).exists(),
                         "common-rules stamped itself with its own version")


class CannotCheckIsItsOwnStatus(unittest.TestCase):
    """0 = verified aligned. 1 = verified, and stale. 2 = nothing was verified.

    Before this, "could not check" shared exit 0 with "aligned" in both cases
    it can happen -- common-rules itself, and a non-adopting project -- so a
    caller that only looked at the exit code could not tell a real pass from
    "there was nothing to check". That is what let a session tick the box
    after running rulecheck from inside common-rules and reading exit 0 as a
    pass.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_could_not_check_is_distinct_from_both_aligned_and_stale(self):
        non_adopter = self.tmp / "scratch"
        non_adopter.mkdir()
        r_non_adopter = run(non_adopter)
        r_common_rules = run(ROOT)
        for r, label in ((r_non_adopter, "non-adopter"), (r_common_rules, "common-rules")):
            self.assertEqual(r.returncode, 2, f"{label}: expected 2, got {r.returncode}")
            self.assertNotEqual(r.returncode, 0, f"{label}: 2 must not collide with aligned")
            self.assertNotEqual(r.returncode, 1, f"{label}: 2 must not collide with stale")


class RealProjectsStillCheck(unittest.TestCase):
    """Guard against a fix that quietly stops checking everything."""

    def test_the_adopting_projects_are_still_recognised(self):
        apps = ROOT.parent
        for name in ("finance-tracker", "pockets", "pip", "mac-explorer"):
            p = apps / name
            if not p.exists():
                self.skipTest(f"{name} not present on this machine")
            with self.subTest(project=name):
                r = run(p)
                self.assertNotIn("does not adopt", verdict(r.stdout),
                                 f"{name} adopts the rules but was skipped")


class TheChangelogIsEvidenceNotVerdict(unittest.TestCase):
    """The bug RealProjectsStillCheck actually had, pinned so it cannot return.

    Hermetic on purpose: this builds its own two-commit rules repo whose
    changelog delta contains the poisoned phrase, rather than relying on the
    real CHANGELOG.md still containing "common-rules does not adopt itself."
    A regression test that depends on the prose it is guarding against stops
    testing the moment someone rewords a changelog entry.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rules = Path(self.tmp.name) / "rules"
        self.rules.mkdir()
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")
        (self.rules / "CLAUDE-workflow.md").write_text("# rules\n")
        (self.rules / "CHANGELOG.md").write_text("# Changelog\n\n## Old entry\n\nnothing here.\n")
        self._git("add", "-A"); self._git("commit", "-qm", "seed")
        self.old_sha = self._git("rev-parse", "--short", "HEAD").stdout.strip()

        # the entry that poisons the dump -- prose about a project NOT adopting
        (self.rules / "CHANGELOG.md").write_text(
            "# Changelog\n\n## A newer entry\n\n"
            "- **common-rules does not adopt itself.** Running rulecheck inside\n"
            "  this repo checks nothing, so it must not read as a pass.\n\n"
            "## Old entry\n\nnothing here.\n")
        self._git("add", "-A"); self._git("commit", "-qm", "add the entry")

        self.proj = Path(self.tmp.name) / "pockets"
        self.proj.mkdir()
        (self.proj / "CLAUDE.md").write_text(POINTER)
        (self.proj / STAMP).write_text(f"1-{self.old_sha}\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _git(self, *a):
        return subprocess.run(["git", "-C", str(self.rules), *a],
                              capture_output=True, text=True, check=False)

    def test_a_stale_project_is_not_called_a_non_adopter_by_its_own_changelog(self):
        """An adopting project, correctly reported stale, whose evidence quotes
        the words "does not adopt". It is stale, not un-adopted, and the two
        must not be confused by a substring search."""
        r = run(self.proj, rules_dir=self.rules)
        self.assertEqual(r.returncode, 1, f"expected stale (1):\n{r.stdout}{r.stderr}")
        self.assertIn("does not adopt", r.stdout,
                      "precondition: the dump must carry the phrase, or this proves nothing")
        self.assertNotIn("does not adopt", verdict(r.stdout),
                         "the changelog it quotes was read as rulecheck's own verdict")

    def test_the_marker_that_splits_verdict_from_evidence_still_exists(self):
        """verdict() cuts on a heading bin/rulecheck prints. If that wording
        changes, verdict() silently stops cutting and every assertion above
        goes back to searching the whole dump -- passing, and testing nothing."""
        r = run(self.proj, rules_dir=self.rules)
        self.assertIn(DUMP_MARKER, r.stdout,
                      "bin/rulecheck no longer prints this heading -- update verdict()")


if __name__ == "__main__":
    unittest.main()
