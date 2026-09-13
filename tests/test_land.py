"""`bin/land`'s closes_trailer() -- which issues a landed PR should close.

A PR that finishes an issue has to say "Closes #N" in its body or the issue
silently outlives its fix. `land` wrote a fixed body until 2026-08-10, so
every branch it landed left its issue open; issue #362 in finance-tracker was
found fixed, merged and still open.

The interesting half is what it must NOT match. A trailing "(#N)" on a commit
subject is the *PR* number, not the issue, and (as common-rules 149 measured)
PR numbers overlap the range issues live in -- so keying on a bare "#N" would
close an unrelated issue most of the time. These tests pin both directions.

The function is extracted from the real `bin/land` rather than copied here:
the script runs `land_one` at import, so it cannot simply be sourced, and a
copy of the regex would test the copy.
"""
import re
import subprocess
import unittest
from pathlib import Path

LAND = Path(__file__).resolve().parent.parent / "bin" / "land"


def closes_trailer(subjects: str) -> list[str]:
    """Run the real shell function against `subjects`, return its lines."""
    source = LAND.read_text()
    match = re.search(r"^closes_trailer\(\) \{.*?^\}", source, re.S | re.M)
    if not match:
        raise AssertionError("closes_trailer() not found in bin/land")
    script = match.group(0) + '\ncloses_trailer "$1"\n'
    out = subprocess.run(
        ["bash", "-c", script, "bash", subjects],
        capture_output=True, text=True, check=True,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


class ClosesTrailerTests(unittest.TestCase):
    def test_the_word_issue_is_a_mention_not_a_closing_keyword(self):
        """f9ed133, 2026-08-30: "issues #821-#826" in a proposal branch's body
        closed a live finance-tracker bug on merge. GitHub's own closing
        keywords never included "issue"; land's no longer does either."""
        self.assertEqual(
            [], closes_trailer("Guard /people's four mutation handlers (issue #362)"))
        self.assertEqual([], closes_trailer("this does NOT fix issue #800"))

    def test_fix_and_resolve_wording_also_count(self):
        self.assertEqual(["Closes #376"], closes_trailer("Fix #376: opening balances"))
        self.assertEqual(["Closes #41"], closes_trailer("Resolves #41"))
        self.assertEqual(["Closes #9"], closes_trailer("closed #9"))

    def test_a_bare_pr_number_is_never_matched(self):
        """The whole point. "(#389)" is the PR gh created, not an issue."""
        self.assertEqual([], closes_trailer("Add shared test-support modules (#389)"))
        self.assertEqual([], closes_trailer("Some subject #123"))

    def test_pr_number_alongside_a_real_issue_takes_only_the_issue(self):
        self.assertEqual(
            ["Closes #362"],
            closes_trailer("Guard the handlers (fixes #362) (#390)"),
        )

    def test_nothing_named_means_no_trailer(self):
        self.assertEqual([], closes_trailer("Tidy up the launcher probe"))
        self.assertEqual([], closes_trailer(""))

    def test_several_issues_across_commits_are_deduped_and_sorted(self):
        self.assertEqual(
            ["Closes #7", "Closes #41", "Closes #362"],
            closes_trailer("resolves #41\nfixes #7 (#380)\nissue #41 again\nCloses #362"),
        )

    def test_body_lines_count_not_just_subjects(self):
        """land passes '%s%n%b', so a Closes: in a commit body must be seen."""
        self.assertEqual(
            ["Closes #55"],
            closes_trailer("Some subject\n\nLonger explanation.\nCloses #55"),
        )


class LandUsesTheTrailerTests(unittest.TestCase):
    def test_the_pr_body_includes_it(self):
        """A helper nothing calls would pass every test above and still leave
        every issue open -- which is the bug this file exists for."""
        source = LAND.read_text()
        self.assertIn('closes_trailer "$($GIT log "main..$branch"', source)
        self.assertIn('--body "$body"', source)

    def test_the_trailer_is_filtered_by_issue_here(self):
        """A commit may legitimately cite another repo's issue -- this change's
        own commit cites finance-tracker #362 -- and closing whatever happens to
        wear that number here would be exactly the wrong-issue failure the
        bare-"(#N)" rule exists to avoid. The number must resolve in THIS repo.
        """
        source = LAND.read_text()
        self.assertIn("issue_here", source)
        self.assertIn('gh issue view "$1" --json number', source)
        # The filter has to sit between the helper and the body, not anywhere.
        trailer = source.split("closes=\"$(closes_trailer")[1].split("\n\n")[0]
        self.assertIn("issue_here", trailer)

    def test_issue_here_is_false_without_gh(self):
        """No gh means no way to check, so nothing is claimed -- rather than
        assuming the issue exists and closing something unrelated."""
        source = LAND.read_text()
        match = re.search(r"^issue_here\(\) \{.*?^\}", source, re.S | re.M)
        self.assertIsNotNone(match)
        script = match.group(0) + '\nPATH=/nonexistent issue_here 1 && echo YES || echo NO\n'
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual("NO", out.stdout.strip())


if __name__ == "__main__":
    unittest.main()
