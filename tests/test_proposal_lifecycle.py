"""A proposal that asked numbered decisions must record the answers.

CLAUDE-workflow.md, "Number every proposal": a decision date says *when* a
proposal was decided, never *what*. Measured in finance-tracker (issue #584):
11 proposals `accepted`, 9 carrying a decision date, 3 recording what was
actually decided -- and those three were hand-written on the day the gap was
noticed. `proposal-auditor` measures drift from what a proposal authorised
and had nothing to measure against.

`bin/proposalcheck` is the mechanical form of that rule: a proposal that asks
nothing needs nothing (`did it ask?`, not `is it big?`), and a proposal
predating the rule -- or carrying no `proposal-decided` date at all -- is
grandfathered rather than failed, because a test that fails on day one against
documents nobody can fix gets disabled. These tests pin both halves: the
requirement itself, and the grandfather that keeps it from being retroactive.

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
PROPOSALCHECK = ROOT / "bin" / "proposalcheck"

# Command Line Tools git, because a pending Xcode licence breaks plain `git`.
GIT = next((g for g in ("/Library/Developer/CommandLineTools/usr/bin/git",
                        "/usr/bin/git") if Path(g).exists()), "git")


def apps_dir(start: Path | None = None) -> Path | None:
    """Where this checkout's sibling projects live, read at runtime.

    These checks used to resolve them as `ROOT.parent`, which is
    `/Users/aashish/apps` only from the main checkout. From a task worktree
    (`<apps>/common-rules/.worktrees/<name>`) it is `.worktrees/`, which holds
    no projects -- so every real-project check found nothing and passed. That
    is both places the suite is actually run: `bin/land` tests the branch
    worktree, and CI checks out a repo with no siblings at all. The checks
    could only ever fail in the one place nobody runs them.

    Same class as `bin/rulecheck`'s hardcoded rules path (#116) and
    `bin/milestones`' `RULES.parent` -- a path derived from an assumption
    about the layout rather than from something true at runtime, and invisible
    precisely where it was wrong.

    `git rev-parse --git-common-dir` names the *main* checkout's `.git` from
    inside a worktree as readily as from the checkout itself, so the answer is
    read rather than assumed. It is the corrected form of what `ROOT.parent`
    was reaching for, not a new policy: `bin/milestones` and `bin/pulse` name
    `/Users/aashish/apps` outright, and rightly -- `--all` has to find every
    project on this Mac, which is a claim about the machine. A test only needs
    the projects beside *this* checkout, which is a fact about the repo.

    Returns None when there is no git repository to ask.
    """
    start = Path(start or ROOT)
    r = subprocess.run([GIT, "-C", str(start), "rev-parse", "--git-common-dir"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    common = Path(r.stdout.strip())
    if not common.is_absolute():
        common = (start / common).resolve()
    return common.parent.parent

BEFORE_FLOOR = "2026-08-10"   # < EFFECTIVE_DATE (2026-08-19) in proposalcheck
ON_FLOOR = "2026-08-19"
AFTER_FLOOR = "2026-08-20"

# STATUS_EFFECTIVE_DATE in proposalcheck (2026-08-20) is its own, later floor --
# a different rule, written a day after the one above, so it gets its own
# before/on/after trio rather than reusing BEFORE_FLOOR/ON_FLOOR/AFTER_FLOOR.
STATUS_BEFORE_FLOOR = "2026-08-19"
STATUS_ON_FLOOR = "2026-08-20"
STATUS_AFTER_FLOOR = "2026-08-21"


def proposal(status: str | None, decided: str | None = None, *,
             asks_decisions: bool = False, answered: bool = False,
             exceptions: bool = False, part_of: str | None = None) -> str:
    """A minimal but structurally real proposal document. `status=None` omits
    the meta tag entirely -- a lead with no status at all, the shape the
    status-required rule checks for. `part_of` marks this document as a
    section rather than a lead."""
    meta = ['<meta name="proposal-id" content="01">']
    if status is not None:
        meta.append(f'<meta name="proposal-status" content="{status}">')
    if decided:
        meta.append(f'<meta name="proposal-decided" content="{decided}">')
    if part_of:
        meta.append(f'<meta name="proposal-part-of" content="{part_of}">')

    body = ["<h1>Test proposal</h1>"]
    if asks_decisions:
        body.append(
            '<ol class="decisions"><li><b>D1.</b> Ship it or not.</li></ol>'
        )
    if answered:
        body.append('<div id="decided"><b>Decided.</b> D1: ship it.</div>')
    if exceptions:
        body.append(
            '<div id="exceptions"><b>Not built.</b> The export button, '
            'because the sponsor deprioritised it in favour of the dashboard.</div>'
        )
    return "<html><head>" + "\n".join(meta) + "</head><body>" + \
        "\n".join(body) + "</body></html>"


def run(project: Path):
    return subprocess.run([sys.executable, str(PROPOSALCHECK), "--project", str(project)],
                          capture_output=True, text=True, check=False)


class ProposalLifecycleTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.tmp / "CLAUDE.md").write_text("test project\n")
        self.proposals = self.tmp / "docs" / "proposals"
        self.proposals.mkdir(parents=True)

    def write(self, name: str, text: str):
        (self.proposals / name).write_text(text)

    # -- the requirement itself -------------------------------------------

    def test_accepted_with_unanswered_decisions_fails(self):
        self.write("01-x.html", proposal("accepted", AFTER_FLOOR, asks_decisions=True))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("01-x.html", r.stdout)
        self.assertIn("records no answers", r.stdout)

    def test_accepted_with_answered_decisions_passes(self):
        self.write("01-x.html", proposal("accepted", AFTER_FLOOR,
                                          asks_decisions=True, answered=True))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_accepted_asking_nothing_passes_with_no_answer_block(self):
        """A proposal that asked no numbered decisions needs no answers block --
        scoped mechanically ("did it ask?"), not by size."""
        self.write("01-x.html", proposal("accepted", AFTER_FLOOR))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_empty_decisions_list_asks_nothing(self):
        text = proposal("accepted", AFTER_FLOOR).replace(
            "<h1>Test proposal</h1>",
            '<h1>Test proposal</h1><ol class="decisions"></ol>')
        self.write("01-x.html", text)
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_proposed_status_is_never_checked(self):
        """A proposal still being negotiated is expected to have open decisions."""
        self.write("01-x.html", proposal("proposed", asks_decisions=True))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_built_is_checked_like_completed(self):
        """`built` is a grandfathered *word*, not an exemption from the rule."""
        self.write("01-x.html", proposal("built", AFTER_FLOOR, asks_decisions=True))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    # -- completed in part --------------------------------------------------

    def test_completed_in_part_without_exceptions_fails(self):
        self.write("01-x.html", proposal("completed in part", AFTER_FLOOR))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("no id=\"exceptions\"", r.stdout)

    def test_completed_in_part_with_exceptions_passes(self):
        self.write("01-x.html", proposal("completed in part", AFTER_FLOOR,
                                          exceptions=True))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # -- grandfathering -------------------------------------------------------

    def test_decided_before_the_floor_is_grandfathered(self):
        self.write("01-x.html", proposal("accepted", BEFORE_FLOOR, asks_decisions=True))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0,
                         "a proposal decided before the rule existed was failed by it: "
                         + r.stdout + r.stderr)

    def test_decided_exactly_on_the_floor_is_not_grandfathered(self):
        self.write("01-x.html", proposal("accepted", ON_FLOOR, asks_decisions=True))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1,
                         "the floor date itself must be inside the rule, not before it: "
                         + r.stdout + r.stderr)

    def test_no_decided_date_at_all_is_grandfathered(self):
        """Undated reads the same as 'decided before this rule existed' -- not a
        loophole a new proposal can use by omitting the meta tag going forward,
        since every proposal created after this rule lands is expected to carry
        the date already (a separate, pre-existing convention)."""
        self.write("01-x.html", proposal("accepted", decided=None, asks_decisions=True))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_completed_in_part_exceptions_requirement_is_not_date_gated(self):
        """New vocabulary, nothing existing to grandfather -- so even a proposal
        dated before the floor must still carry the exceptions block once it
        claims this status at all."""
        self.write("01-x.html", proposal("completed in part", BEFORE_FLOOR))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    # -- the real gap this was measured against --------------------------

    def test_finance_tracker_blast_radius_is_all_grandfathered_today(self):
        """Every finance-tracker proposal non-compliant today was decided before
        this rule's floor -- so landing the rule blocks nothing retroactively.
        Guards against a fix that quietly re-tightens the floor and starts
        failing history."""
        apps = apps_dir()
        proj = apps / "finance-tracker" if apps else None
        if proj is None or not proj.exists():
            self.skipTest(f"finance-tracker not present beside {apps}")
        r = run(proj)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # -- no docs/proposals at all -------------------------------------------

    def test_no_proposals_directory_is_could_not_check_not_a_pass(self):
        empty = self.tmp / "empty-project"
        empty.mkdir()
        r = run(empty)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class ProposalIsEitherAProposalOrAnArtifactTests(unittest.TestCase):
    """CLAUDE-workflow.md, 'A document is either a proposal or an artifact':
    a lead (no proposal-part-of) must carry a proposal-status from the known
    vocabulary; a section (has proposal-part-of) must carry none. Its own
    floor (STATUS_EFFECTIVE_DATE, 2026-08-20) is separate from the
    decisions-recorded rule's floor above -- a different rule, a different
    day."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.tmp / "CLAUDE.md").write_text("test project\n")
        self.proposals = self.tmp / "docs" / "proposals"
        self.proposals.mkdir(parents=True)

    def write(self, name: str, text: str):
        (self.proposals / name).write_text(text)

    # -- a lead needs a status -----------------------------------------------

    def test_lead_with_no_status_after_the_floor_fails(self):
        self.write("01-x.html", proposal(None, STATUS_AFTER_FLOOR))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("carries no proposal-status", r.stdout)

    def test_lead_with_a_known_status_passes(self):
        for status in ("proposed", "accepted", "completed", "completed in part",
                        "built", "amends 07", "superseded by 14"):
            with self.subTest(status=status):
                self.tmp2 = tempfile.TemporaryDirectory()
                self.addCleanup(self.tmp2.cleanup)
                proposals = Path(self.tmp2.name) / "docs" / "proposals"
                proposals.mkdir(parents=True)
                (Path(self.tmp2.name) / "CLAUDE.md").write_text("test project\n")
                # "completed in part" separately requires its own id="exceptions"
                # block (the rule above) -- unrelated to the status-vocabulary
                # check this test targets, so give it one to isolate that.
                needs_exceptions = status == "completed in part"
                (proposals / "01-x.html").write_text(
                    proposal(status, STATUS_AFTER_FLOOR, exceptions=needs_exceptions)
                )
                r = run(Path(self.tmp2.name))
                self.assertEqual(r.returncode, 0, f"{status}: " + r.stdout + r.stderr)

    def test_lead_with_an_unrecognized_status_after_the_floor_fails(self):
        self.write("01-x.html", proposal("propsed", STATUS_AFTER_FLOOR))  # typo, on purpose
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("matches none of the known vocabulary", r.stdout)

    def test_superseded_by_hyphenated_is_not_the_known_form(self):
        """The exact typo found live in pockets ('superseded-by 14' instead of
        'superseded by 14') -- the whole-string regex must not accept it."""
        self.write("01-x.html", proposal("superseded-by 14", STATUS_AFTER_FLOOR))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    # -- a section (part-of) carries no status of its own --------------------

    def test_section_with_no_status_passes(self):
        self.write("01-lead.html", proposal("accepted", STATUS_AFTER_FLOOR))
        self.write("02-section.html", proposal(None, part_of="01"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_section_claiming_its_own_status_fails(self):
        self.write("01-lead.html", proposal("accepted", STATUS_AFTER_FLOOR))
        self.write("02-section.html", proposal("proposed", part_of="01"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("also claims its own status", r.stdout)

    # -- grandfathering, this rule's own floor --------------------------------

    def test_lead_with_no_status_decided_before_this_rules_floor_is_grandfathered(self):
        self.write("01-x.html", proposal(None, STATUS_BEFORE_FLOOR))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_lead_with_no_status_decided_exactly_on_this_rules_floor_is_not_grandfathered(self):
        self.write("01-x.html", proposal(None, STATUS_ON_FLOOR))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_lead_with_no_status_and_no_decided_date_at_all_is_grandfathered(self):
        """Matches pip's 02a/02b -- undated leads with no status, predating
        this rule the same way an undated proposal predates the one above."""
        self.write("01-x.html", proposal(None, decided=None))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_pockets_and_pip_blast_radius_is_grandfathered_today(self):
        """Every non-compliant lead in pockets and pip today was decided (or
        undated) before this rule's floor -- guards against a fix that
        quietly re-tightens the floor and starts failing history."""
        apps = apps_dir()
        for name in ("pockets", "pip"):
            with self.subTest(project=name):
                proj = apps / name if apps else None
                # `continue` here reported `ok` after asserting nothing, which
                # is indistinguishable from a run that actually checked the
                # project. A skip at least says so out loud.
                if proj is None or not proj.exists():
                    self.skipTest(f"{name} not present beside {apps}")
                r = run(proj)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TheRealProjectChecksAreNotVacuous(unittest.TestCase):
    """The checks above are the only ones that read real documents. If they
    resolve to a directory with no projects in it they skip, silently, and
    the suite stays green while checking nothing -- which is exactly what
    happened everywhere the suite is actually run. These pin the resolution
    itself, so a regression fails loudly instead of going quiet."""

    def test_no_project_is_resolved_as_root_parent(self):
        """Structural guard, in the shape of #116's 'no home directory is
        baked into the default'. Asserting that the real-project checks pass
        proves nothing -- they pass hardest when they are skipping. What can
        be asserted is that the broken expression is not in the file."""
        # Assembled, so this guard's own text is not a hit for itself.
        # Prose may still name the expression in backticks -- the docstrings
        # here explain the bug and would otherwise trip their own guard.
        forbidden = "ROOT" + ".parent"
        offenders = [f"{n}: {line.strip()}"
                     for n, line in enumerate(
                         Path(__file__).read_text().splitlines(), 1)
                     if forbidden in line and f"`{forbidden}`" not in line]
        self.assertEqual(
            offenders, [],
            f"real projects must be resolved with apps_dir(), not {forbidden} -- "
            "the latter is '.worktrees/' from a task worktree, which is where "
            "bin/land runs this suite")

    def test_apps_dir_finds_the_projects_from_inside_a_worktree(self):
        """Hermetic: builds its own <apps>/<repo>/.worktrees/<name> layout
        rather than depending on this Mac having one. A regression test that
        needs the real machine stops testing the moment it runs anywhere
        else -- which is the bug it is guarding against."""
        with tempfile.TemporaryDirectory() as tmp:
            apps = (Path(tmp) / "apps").resolve()
            repo = apps / "common-rules"
            (apps / "finance-tracker").mkdir(parents=True)
            repo.mkdir(parents=True)

            def git(*args, cwd=repo):
                r = subprocess.run([GIT, "-C", str(cwd), *args],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "T")
            (repo / "README.md").write_text("x\n")
            git("add", "-A")
            git("commit", "-qm", "init")
            wt = repo / ".worktrees" / "task"
            git("worktree", "add", "-q", "-b", "task", str(wt))

            self.assertEqual(apps_dir(repo), apps,
                             "wrong answer from the main checkout")
            self.assertEqual(apps_dir(wt), apps,
                             "wrong answer from a worktree -- the whole bug")
            # The expression this replaces, and what it would have said here.
            self.assertEqual(wt.parent, repo / ".worktrees")
            self.assertFalse((wt.parent / "finance-tracker").exists())

    def test_apps_dir_is_none_outside_a_git_repository(self):
        """No repository to ask means no answer, not a wrong one. The callers
        skip on None rather than resolving something arbitrary."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(apps_dir(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
