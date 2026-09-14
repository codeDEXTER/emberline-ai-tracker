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

# Resolving the real projects lives in one place -- see tests/projects.py for
# why it is read from git rather than derived from this file's location.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from projects import apps_dir  # noqa: E402

BEFORE_FLOOR = "2026-08-10"   # < EFFECTIVE_DATE (2026-08-19) in proposalcheck
ON_FLOOR = "2026-08-19"
AFTER_FLOOR = "2026-08-20"

# STATUS_EFFECTIVE_DATE in proposalcheck (2026-08-20) is its own, later floor --
# a different rule, written a day after the one above, so it gets its own
# before/on/after trio rather than reusing BEFORE_FLOOR/ON_FLOOR/AFTER_FLOOR.
STATUS_BEFORE_FLOOR = "2026-08-19"
STATUS_ON_FLOOR = "2026-08-20"
STATUS_AFTER_FLOOR = "2026-08-21"

# NEW_PROPOSAL_FLOOR in proposalcheck (2026-09-14, proposal 21 / S-03) is a
# third, later floor still -- gates a page's own git-add date, not its
# proposal-decided meta, so it gets its own trio too.
NEW_PROPOSAL_AFTER_FLOOR = "2026-09-14T00:00:00+00:00"


def proposal(status: str | None, decided: str | None = None, *,
             asks_decisions: bool = False, answered: bool = False,
             exceptions: bool = False, part_of: str | None = None,
             pid: str = "01") -> str:
    """A minimal but structurally real proposal document. `status=None` omits
    the meta tag entirely -- a lead with no status at all, the shape the
    status-required rule checks for. `part_of` marks this document as a
    section rather than a lead."""
    # Every document needs its *own* id, sections included -- measured across
    # finance-tracker's 14 real sections, where 33-38 all sit part-of 32 and
    # each carries its own number. Hardcoding "01" here made any two-document
    # fixture a proposal-id collision once that became a checked rule.
    meta = [f'<meta name="proposal-id" content="{pid}">']
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
        self.write("02-section.html", proposal(None, part_of="01", pid="02"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_section_claiming_its_own_status_fails(self):
        self.write("01-lead.html", proposal("accepted", STATUS_AFTER_FLOOR))
        self.write("02-section.html", proposal("proposed", part_of="01", pid="02"))
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


class NewProposalMustCarryStatusTests(unittest.TestCase):
    """Proposal 21 (S-03): a lead with no `proposal-status` meta at all is a
    violation once the *page itself* is new -- measured by when it was first
    added to git, not by its (often-absent) `proposal-decided` date.

    PhotoVault's app proposals 72, 75, 76 and the engine's 77 all carry no
    status meta and no decided date, so the existing lead-status check (which
    is gated by `proposal-decided`) reads them as undated and silently
    grandfathers them -- this is the gap that check leaves open. This rule
    has its own floor (NEW_PROPOSAL_FLOOR, 2026-09-14) and needs real git
    history to answer "when was this page first added", so each test here
    builds a scratch git repo rather than writing loose files."""

    NEW_STATUS_MESSAGE = "carries no proposal status"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "proj"
        self.repo.mkdir()
        self.addCleanup(self._tmp.cleanup)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.repo / "CLAUDE.md").write_text("test project\n")
        (self.repo / "docs" / "proposals").mkdir(parents=True)
        self.git("add", "-A")
        self.git("commit", "-qm", "seed")

    def git(self, *args, env=None):
        return subprocess.run(["git", "-C", str(self.repo), *args],
                              capture_output=True, text=True, check=True, env=env)

    def commit_page(self, name: str, text: str, *, when: str | None = None):
        """Write `name` under docs/proposals/ and commit it, optionally
        back-dating the commit (both author and committer, as `git log
        --format=%aI` reads the author date)."""
        (self.repo / "docs" / "proposals" / name).write_text(text)
        self.git("add", "-A")
        env = dict(os.environ)
        if when:
            env["GIT_AUTHOR_DATE"] = when
            env["GIT_COMMITTER_DATE"] = when
        self.git("commit", "-qm", f"add {name}", env=env)

    def write_uncommitted(self, name: str, text: str):
        (self.repo / "docs" / "proposals" / name).write_text(text)

    def run_check(self):
        return run(self.repo)

    def test_new_committed_page_without_status_is_a_violation(self):
        self.commit_page("01-x.html", proposal(None), when=NEW_PROPOSAL_AFTER_FLOOR)
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(self.NEW_STATUS_MESSAGE, r.stdout)
        self.assertIn("01-x.html", r.stdout)

    def test_old_page_committed_before_the_floor_is_not_a_violation(self):
        self.commit_page("01-x.html", proposal(None), when="2026-01-01T00:00:00+00:00")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(self.NEW_STATUS_MESSAGE, r.stdout)

    def test_uncommitted_page_without_status_is_a_violation(self):
        """A proposal cannot dodge this rule by staying out of git entirely."""
        self.write_uncommitted("01-x.html", proposal(None))
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(self.NEW_STATUS_MESSAGE, r.stdout)

    def test_artifact_page_is_not_a_violation(self):
        """An artifact/section (proposal-part-of set) has nothing of its own
        to decide, so it never needs a status -- new or not."""
        self.commit_page("01-lead.html", proposal("accepted", STATUS_AFTER_FLOOR),
                         when=NEW_PROPOSAL_AFTER_FLOOR)
        self.commit_page("02-artifact.html", proposal(None, part_of="01", pid="02"),
                         when=NEW_PROPOSAL_AFTER_FLOOR)
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(self.NEW_STATUS_MESSAGE, r.stdout)

    def test_section_page_is_not_a_violation(self):
        self.commit_page("01-lead.html", proposal("accepted", STATUS_AFTER_FLOOR),
                         when=NEW_PROPOSAL_AFTER_FLOOR)
        self.commit_page("02-section.html", proposal(None, part_of="01", pid="02"),
                         when=NEW_PROPOSAL_AFTER_FLOOR)
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(self.NEW_STATUS_MESSAGE, r.stdout)

    def test_new_page_with_status_passes_the_new_rule(self):
        self.commit_page("01-x.html", proposal("proposed"),
                         when=NEW_PROPOSAL_AFTER_FLOOR)
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(self.NEW_STATUS_MESSAGE, r.stdout)

    def test_outside_a_git_repository_the_rule_never_fires(self):
        """No git history to ask "when was this first added" -- today's
        behaviour holds rather than guessing. Uses a plain (non-git) tmpdir,
        same shape as ProposalLifecycleTests above."""
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            (proj / "CLAUDE.md").write_text("test project\n")
            proposals = proj / "docs" / "proposals"
            proposals.mkdir(parents=True)
            (proposals / "01-x.html").write_text(proposal(None))
            r = run(proj)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn(self.NEW_STATUS_MESSAGE, r.stdout)


if __name__ == "__main__":
    unittest.main()
