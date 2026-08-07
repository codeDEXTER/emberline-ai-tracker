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
        self.assertEqual(r.returncode, 0, f"expected 'nothing to check', got:\n{r.stdout}{r.stderr}")
        self.assertIn("does not adopt", r.stdout)
        self.assertNotIn("NEVER recorded", r.stdout)

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
        self.assertNotIn("does not adopt", r.stdout,
                         "a project that has aligned before was treated as never having adopted")

    def test_a_project_with_no_claude_md_at_all_does_not_adopt(self):
        p = self.project("scratch")
        r = run(p)
        self.assertEqual(r.returncode, 0)
        self.assertIn("does not adopt", r.stdout)

    def test_quiet_says_nothing_for_a_non_adopting_project(self):
        """--quiet is for the SessionStart hook; a non-adopter must not print."""
        p = self.project("idea-lab", "Deliberately separate.\n")
        r = run(p, "--quiet")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")


class TheRulesDoNotAdoptThemselves(unittest.TestCase):

    def test_common_rules_itself_is_not_an_adopter(self):
        r = run(ROOT)
        self.assertEqual(r.returncode, 0)
        self.assertIn("the rules themselves", r.stdout)
        self.assertNotIn("NEVER recorded", r.stdout)

    def test_common_rules_never_acquires_a_stamp(self):
        r = run(ROOT, "--align")
        self.assertFalse((ROOT / STAMP).exists(),
                         "common-rules stamped itself with its own version")


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
                self.assertNotIn("does not adopt", r.stdout,
                                 f"{name} adopts the rules but was skipped")


if __name__ == "__main__":
    unittest.main()
