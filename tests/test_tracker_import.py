"""`tracker import` -- an existing milestone plan becomes a ledger (proposal 19, W-09).

The focus projects already have plans; the standard must not ask anyone to
retype them. pockets keeps a `## Milestones` table in CLAUDE-checklist.md;
finance-tracker keeps its rows in CLAUDE-milestones.json and generates the
table from it. Import reads either and writes a ledger that validates.

Decisions these tests pin, each for a reason:

  * Rows are read with bin/milestones' own parse() -- the table has one
    reader already, and a second copy of a vocabulary is how two readers got
    the same case wrong before (its hands_something_over docstring).
  * The JSON wins over the table when both exist: the table is generated
    from it.
  * Tracks become phases, in the order a plan introduces them; a phase id is
    the track's initial, extended when two tracks share one.
  * State maps into the ledger's four words, and "built" is IN PROGRESS, not
    done: a built milestone awaits sign-off, and calling it done erases the
    gap finance-tracker's chips exist to show. The row's log keeps the source
    state -- verbatim from CLAUDE-milestones.json; as bin/milestones' class for
    a table row, because parse() does not return the raw cell and adding it
    would change every project's milestone-page digest (digest() hashes whole
    rows) and turn land's page gate against all of them.
  * Every imported row is C4, the lead's: a milestone is a planning row that
    the lead decomposes. Import does not guess a class it cannot know.
  * Import never overwrites, never takes a proposal number that already has a
    ledger, and writes nothing that fails validation.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TRACKER = ROOT / "bin" / "tracker"

from tools.tracker import ledger as L  # noqa: E402

AT = "2026-09-13T23:00:00+02:00"

TABLE_WITH_TRACKS = """# checklist

## Milestones

Some prose above the table.

| # | Milestone | Track | Proves | You get | State |
|---|---|---|---|---|---|
| 1 | M0 — the engine clears its gate | desktop | the classifier is good enough | nothing to hold | completed |
| 2 | The loop on a phone | phone | capture survives real hardware | an app that files a photo | built |
| 3 | The registry matters | desktop | the registry moves a decision | nothing to hold | in flight |
| 4 | Import the backlog | desktop | the backlog lands | the backlog, filed | next |
| 5 | Phone, properly | phone | the phone returns | the app | later |
| 6 | Masking first | desktop | credentials never leave | nothing to hold | blocked |

## Next section
"""

TABLE_NO_TRACK = """## Milestones

| Milestone | Proves | You get | State |
|---|---|---|---|
| First | a | nothing to hold | done |
| Second | b | something | next |
"""

MILESTONES_JSON = {
    "meta": {"generated_by": "tools/gen_milestones.py"},
    "rows": [
        {"n": 1, "t": "**Position** — where I stand", "pv": "one surface answers", "gt": "**the Position page**",
         "tr": "Surfaces", "st": "built — awaiting your sign-off", "done": True},
        {"n": 2, "t": "Cashflow", "pv": "money in and out", "gt": "a page", "tr": "Surfaces", "st": "next", "done": False},
        {"n": 3, "t": "Fast enough", "pv": "loads under a second", "gt": "nothing to hold", "tr": "Speed",
         "st": "done", "done": True},
    ],
}


class Scratch:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        (self.root / "docs" / "proposals").mkdir(parents=True)

    def write(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        return p

    def run(self, *args):
        return subprocess.run([sys.executable, str(TRACKER), "import", "--project", str(self.root), "--at", AT, *args],
                              capture_output=True, text=True, check=False)

    def close(self):
        self.tmp.cleanup()


class Case(unittest.TestCase):
    def setUp(self):
        self.s = Scratch()

    def tearDown(self):
        self.s.close()

    def imported(self, *args):
        r = self.s.run("--proposal", "30", "--title", "Milestone plan", *args)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        path = self.s.root / "docs" / "proposals" / "30-milestone-plan.json"
        self.assertTrue(path.exists(), "default output is docs/proposals/NN-<slug of title>.json")
        return L.load(path), r


class TestFromTheChecklistTable(Case):

    def test_the_result_validates(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        d, _ = self.imported()
        self.assertEqual([], L.validate(d))
        self.assertEqual(30, d["proposal"])
        self.assertEqual(6, len(d["items"]))

    def test_tracks_become_phases_in_order_of_first_appearance(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        d, _ = self.imported()
        self.assertEqual([("D", "desktop"), ("P", "phone")], [(p["id"], p["name"]) for p in d["phases"]])
        self.assertEqual(["D-01", "P-01", "D-02", "D-03", "P-02", "D-04"], [i["id"] for i in d["items"]])

    def test_state_maps_to_the_four_words_and_built_is_not_done(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        d, _ = self.imported()
        got = {i["id"]: i["status"] for i in d["items"]}
        self.assertEqual({"D-01": "done", "P-01": "in progress", "D-02": "in progress",
                          "D-03": "not started", "P-02": "not started", "D-04": "blocked"}, got)

    def test_the_source_state_is_kept_verbatim_in_the_log(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        d, _ = self.imported()
        p01 = L.by_id(d)["P-01"]
        self.assertEqual(1, len(p01["log"]))
        entry = p01["log"][0]
        self.assertEqual("imported", entry["event"])
        self.assertEqual(AT, entry["at"])
        self.assertIn("CLAUDE-checklist.md", entry["evidence"])
        self.assertIn("row 2", entry["evidence"])
        self.assertIn("'built'", entry["evidence"])

    def test_every_row_is_the_leads_until_decomposed(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        d, _ = self.imported()
        self.assertEqual({"C4"}, {i["cx"] for i in d["items"]})
        self.assertEqual({"[ruflo · lead · lead model]"}, {i["tag"] for i in d["items"]})

    def test_proves_and_you_get_are_carried(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        d, _ = self.imported()
        what = L.by_id(d)["P-01"]["what"]
        self.assertIn("capture survives real hardware", what)
        self.assertIn("an app that files a photo", what)

    def test_a_table_with_no_track_column_is_one_phase(self):
        self.s.write("CLAUDE-checklist.md", TABLE_NO_TRACK)
        d, _ = self.imported()
        self.assertEqual(["M"], [p["id"] for p in d["phases"]])
        self.assertEqual(["M-01", "M-02"], [i["id"] for i in d["items"]])
        self.assertEqual([], L.validate(d))


class TestFromTheMilestonesJson(Case):

    def test_json_wins_over_the_generated_table(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        self.s.write("CLAUDE-milestones.json", json.dumps(MILESTONES_JSON))
        d, r = self.imported()
        self.assertEqual(3, len(d["items"]))
        self.assertIn("CLAUDE-milestones.json", r.stdout)

    def test_shared_initials_are_extended_and_markdown_is_stripped(self):
        self.s.write("CLAUDE-milestones.json", json.dumps(MILESTONES_JSON))
        d, _ = self.imported()
        self.assertEqual([("S", "Surfaces"), ("SP", "Speed")], [(p["id"], p["name"]) for p in d["phases"]])
        self.assertEqual(["S-01", "S-02", "SP-01"], [i["id"] for i in d["items"]])
        self.assertEqual("Position — where I stand", L.by_id(d)["S-01"]["title"])

    def test_the_state_text_wins_over_the_done_flag(self):
        """finance-tracker marks a built, unsigned milestone done: true. The
        state text says what is actually true of it."""
        self.s.write("CLAUDE-milestones.json", json.dumps(MILESTONES_JSON))
        d, _ = self.imported()
        self.assertEqual("in progress", L.by_id(d)["S-01"]["status"])
        self.assertEqual("done", L.by_id(d)["SP-01"]["status"])
        self.assertEqual([], L.validate(d))


class TestRefusals(Case):

    def test_no_plan_is_exit_2(self):
        r = self.s.run("--proposal", "30", "--title", "Milestone plan")
        self.assertEqual(2, r.returncode)
        self.assertIn("no milestone plan", r.stdout + r.stderr)

    def test_an_existing_output_is_never_overwritten(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        out = self.s.write("docs/proposals/30-milestone-plan.json", '{"keep": "me"}')
        r = self.s.run("--proposal", "30", "--title", "Milestone plan")
        self.assertEqual(1, r.returncode)
        self.assertEqual('{"keep": "me"}', out.read_text())

    def test_a_proposal_number_that_already_has_a_ledger_is_refused(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        self.s.write("docs/proposals/30-something-else.json",
                     json.dumps({"proposal": 30, "title": "x", "items": []}))
        r = self.s.run("--proposal", "30", "--title", "Milestone plan")
        self.assertEqual(1, r.returncode)
        self.assertIn("already has a ledger", r.stdout + r.stderr)
        self.assertFalse((self.s.root / "docs" / "proposals" / "30-milestone-plan.json").exists())

    def test_dry_run_writes_nothing(self):
        self.s.write("CLAUDE-checklist.md", TABLE_WITH_TRACKS)
        r = self.s.run("--proposal", "30", "--title", "Milestone plan", "--dry-run")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("6 rows", r.stdout)
        self.assertFalse((self.s.root / "docs" / "proposals" / "30-milestone-plan.json").exists())


class TestTheRealPlans(unittest.TestCase):
    """The row's done-when: pockets' and finance-tracker's plans import into
    ledgers that validate. Read-only on both projects -- output goes to a
    scratch file, and each project's git status is compared before and after."""

    def import_real(self, project: Path, expected_min_rows: int):
        def porcelain():
            return subprocess.run(["git", "-C", str(project), "status", "--porcelain"],
                                  capture_output=True, text=True).stdout
        before = porcelain()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "99-imported.json"
            r = subprocess.run([sys.executable, str(TRACKER), "import", "--project", str(project),
                                "--proposal", "99", "--title", "Imported plan", "--out", str(out), "--at", AT],
                               capture_output=True, text=True, check=False)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            d = L.load(out)
        self.assertEqual([], L.validate(d))
        self.assertGreaterEqual(len(d["items"]), expected_min_rows)
        self.assertEqual(before, porcelain(), f"import wrote into {project}")
        return d

    @unittest.skipUnless(Path("/Users/aashish/apps/pockets/CLAUDE-checklist.md").exists(), "pockets not on this machine")
    def test_pockets(self):
        self.import_real(Path("/Users/aashish/apps/pockets"), 20)

    @unittest.skipUnless(Path("/Users/aashish/apps/finance-tracker/CLAUDE-milestones.json").exists(),
                         "finance-tracker not on this machine")
    def test_finance_tracker(self):
        self.import_real(Path("/Users/aashish/apps/finance-tracker"), 70)


if __name__ == "__main__":
    unittest.main()
