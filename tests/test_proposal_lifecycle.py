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

BEFORE_FLOOR = "2026-08-10"   # < EFFECTIVE_DATE (2026-08-19) in proposalcheck
ON_FLOOR = "2026-08-19"
AFTER_FLOOR = "2026-08-20"


def proposal(status: str, decided: str | None = None, *,
             asks_decisions: bool = False, answered: bool = False,
             exceptions: bool = False) -> str:
    """A minimal but structurally real proposal document."""
    meta = ['<meta name="proposal-id" content="01">',
            f'<meta name="proposal-status" content="{status}">']
    if decided:
        meta.append(f'<meta name="proposal-decided" content="{decided}">')

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
        proj = ROOT.parent / "finance-tracker"
        if not proj.exists():
            self.skipTest("finance-tracker not present on this machine")
        r = run(proj)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # -- no docs/proposals at all -------------------------------------------

    def test_no_proposals_directory_is_could_not_check_not_a_pass(self):
        empty = self.tmp / "empty-project"
        empty.mkdir()
        r = run(empty)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
