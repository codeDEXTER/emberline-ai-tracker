"""A proposal number is claimed by exactly one document.

CLAUDE-workflow.md, "Number every proposal": proposals live in
`docs/proposals/` as `NN-<type>-<slug>.html`, "numbered sequentially per
project, never reused". Nothing checked the "never reused" half.

That is not theoretical. Auditing four projects for the lead/section rule
(2026-08-20) turned up three pre-existing collisions in finance-tracker --
ids 14, 15 and 20, each claimed by two different documents -- found only
because somebody happened to be reading every proposal for an unrelated
reason. `proposalcheck` validated that decisions were recorded and that a
lead carried a status, and passed both documents of every colliding pair.

A collision is worse than an ordinary violation because it silently breaks
every reference *to* a proposal: `proposal-part-of` names an id, the shared
rules cite proposals by number, and `<meta name="proposal-id">` is how the
Tower groups a topic's pages. When two documents answer to "14", every one
of those references is ambiguous and nothing says so.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROPOSALCHECK = ROOT / "bin" / "proposalcheck"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from projects import apps_dir  # noqa: E402


def doc(pid: str | None, *, status: str | None = "proposed",
        part_of: str | None = None) -> str:
    """A minimal proposal. `pid=None` omits the id meta entirely -- the shape
    pip's 02a/02b sections have, which must not be read as colliding with
    each other."""
    meta = []
    if pid is not None:
        meta.append(f'<meta name="proposal-id" content="{pid}">')
    if status is not None:
        meta.append(f'<meta name="proposal-status" content="{status}">')
    if part_of:
        meta.append(f'<meta name="proposal-part-of" content="{part_of}">')
    return "<html><head>" + "\n".join(meta) + \
        "</head><body><h1>x</h1></body></html>"


def run(project: Path):
    return subprocess.run([sys.executable, str(PROPOSALCHECK),
                           "--project", str(project)],
                          capture_output=True, text=True, check=False)


class ProposalIdsAreUnique(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.tmp / "CLAUDE.md").write_text("test project\n")
        self.proposals = self.tmp / "docs" / "proposals"
        self.proposals.mkdir(parents=True)

    def write(self, name: str, text: str):
        (self.proposals / name).write_text(text)

    def test_two_documents_claiming_one_id_fails(self):
        self.write("08-a.html", doc("08"))
        self.write("08-b.html", doc("08"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("08", r.stdout)
        self.assertIn("08-a.html", r.stdout)
        self.assertIn("08-b.html", r.stdout)

    def test_distinct_ids_pass(self):
        self.write("08-a.html", doc("08"))
        self.write("09-b.html", doc("09"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_section_shares_no_id_with_its_lead(self):
        """A section carries its *own* id and points at the lead through
        `proposal-part-of` -- it does not re-claim the lead's number. The
        pairs already live in finance-tracker (03/03a) and pip work this
        way, so the check must not read the lead/section relationship as a
        collision."""
        self.write("03-lead.html", doc("03"))
        self.write("03a-section.html", doc("03a", status=None, part_of="03"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_documents_with_no_id_at_all_do_not_collide_with_each_other(self):
        """The exact shape of pip's 02a/02b: two sections carrying no
        `proposal-id`. Absent is not a value -- grouping them under one
        bucket would fail a project on day one for a rule about reuse, which
        is how a check gets disabled."""
        self.write("02a-x.html", doc(None, status=None, part_of="02"))
        self.write("02b-y.html", doc(None, status=None, part_of="02"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_three_documents_on_one_id_name_all_three(self):
        """A message naming two of three would send someone to renumber one
        document and leave the collision standing."""
        for n in "abc":
            self.write(f"08-{n}.html", doc("08"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        for n in "abc":
            self.assertIn(f"08-{n}.html", r.stdout)

    def test_the_collision_is_reported_once_not_once_per_document(self):
        """One id, one line. Reporting per-document would count a two-way
        collision as two violations and inflate the total."""
        self.write("08-a.html", doc("08"))
        self.write("08-b.html", doc("08"))
        r = run(self.tmp)
        self.assertEqual(r.stdout.count("is claimed by"), 1, r.stdout)

    def test_no_date_floor_applies(self):
        """Every other rule in proposalcheck is grandfathered by decision
        date, because its history cannot honestly be reconstructed. A
        collision is different in kind: it is always fixable by renumbering,
        and it is a live ambiguity rather than a missing record. Measured
        blast radius when this landed was one collision, in common-rules
        itself, and zero across every adopting project."""
        self.write("08-a.html", doc("08", status="accepted"))
        self.write("08-b.html", doc("08", status="accepted"))
        (self.proposals / "08-a.html").write_text(
            doc("08", status="accepted").replace(
                "<head>", '<head><meta name="proposal-decided" content="2026-01-01">'))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 1,
                         "a collision predating every floor must still fail: "
                         + r.stdout + r.stderr)


class TheSummaryLineSaysWhatWasChecked(unittest.TestCase):
    """The success line read "every proposal that asked decisions recorded
    them" whatever it had actually looked at -- and across common-rules' own
    sixteen proposals, *none* carries a decisions list, so that sentence has
    been vacuously true for the tool's whole life while reading as a pass.

    A checker that cannot distinguish "checked and clean" from "there was
    nothing to check" is the failure mode proposal 16 names: called, always
    skipping, reporting success. The exit code already separates them (2 is
    "could not check"); the line a person reads did not."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.tmp / "CLAUDE.md").write_text("test project\n")
        self.proposals = self.tmp / "docs" / "proposals"
        self.proposals.mkdir(parents=True)

    def write(self, name: str, text: str):
        (self.proposals / name).write_text(text)

    def test_it_reports_how_many_proposals_asked_decisions(self):
        self.write("01-x.html", doc("01"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 asked decisions", r.stdout,
                      "a pass over documents that asked nothing must say so")

    def test_a_project_whose_proposals_all_ask_nothing_still_passes(self):
        """Saying the check was vacuous is not the same as failing it. The
        exit code stays 0 -- this is reporting, not a new rule."""
        self.write("01-x.html", doc("01"))
        self.write("02-y.html", doc("02"))
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TheRealProjectsHaveNoCollisions(unittest.TestCase):
    """The measured blast radius, pinned. Guards against a fix that quietly
    stops looking -- and against a project acquiring a collision unnoticed."""

    def test_this_repo_is_free_of_collisions(self):
        """common-rules itself, which no other check here reaches. It carries
        no `.common-rules-version`, so every gate in `bin/land` skips it --
        the rules repo is the one place a violation of its own rules cannot
        be refused. This ran red until 2026-08-20, when `08` was claimed by
        both `08-proposal-work-packages.html` (the logbook proposal, which
        ten passages in CLAUDE-workflow.md and the changelog call "proposal
        08") and the workflow bake-off, since renumbered to 17.

        Named directly rather than resolved through apps_dir(): this is the
        repository the suite lives in, so it is always present and this check
        can never quietly skip -- which is the whole complaint against the
        gate that cannot fire here."""
        r = run(ROOT)
        self.assertNotIn("is claimed by", r.stdout,
                         "common-rules has a proposal-id collision")

    def test_adopting_projects_are_free_of_collisions(self):
        apps = apps_dir()
        for name in ("finance-tracker", "pockets", "pip", "mac-explorer"):
            with self.subTest(project=name):
                proj = apps / name if apps else None
                if proj is None or not (proj / "docs" / "proposals").is_dir():
                    self.skipTest(f"{name} not present beside {apps}")
                r = run(proj)
                self.assertNotIn("is claimed by", r.stdout,
                                 f"{name} has a proposal-id collision")


if __name__ == "__main__":
    unittest.main()
