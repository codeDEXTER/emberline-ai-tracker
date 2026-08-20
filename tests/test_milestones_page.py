"""`bin/milestones` renders the plan, and `bin/land` refuses a stale picture.

The rule this backs (`CLAUDE-workflow.md`, "the plan has a picture, generated")
exists because a hand-maintained second copy of the milestone plan is the exact
drift the plan rule already warns about, with extra steps -- and the picture is
the copy people actually look at. So the page is generated from the table and
never written, and the only interesting question is whether that stays true.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "bin" / "milestones"
LAND = ROOT / "bin" / "land"
RULECHECK = ROOT / "bin" / "rulecheck"
STAMP = ".common-rules-version"
REFUSAL = "milestone plan's page is missing or out of date"

PLAIN = """# c

## Milestones

| # | Milestone | Proves | You get | State |
|---|---|---|---|---|
| 1 | Index one corpus | retrieval is good enough to build on | nothing to hold | done |
| 2 | The first screen | the design survives a hand | an app you can use | next |
"""

TRACKED = """# c

## Milestones

| # | Milestone | Proves | You get | Track | State |
|---|---|---|---|---|---|
| 1 | Money is right | the figures survive negative cases | nothing to hold | Correctness | in flight |
| 2 | Spending page | holders are never pooled | the Spending page | Surfaces | in flight |
| 3 | Ledger writes | the book corrects in place | the Ledger | Surfaces | next |
"""


def run(*args):
    return subprocess.run([str(GEN), *args], capture_output=True, text=True, check=False)


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        self.proj.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, body):
        (self.proj / "CLAUDE-checklist.md").write_text(body)

    def page(self):
        return (self.proj / "docs" / "milestones.html").read_text()

    def gen(self):
        return run("--project", str(self.proj))


class ThePageComesFromTheTable(Harness):

    def test_every_milestone_reaches_the_page(self):
        self.write(PLAIN)
        self.assertEqual(self.gen().returncode, 0)
        for title in ("Index one corpus", "The first screen"):
            self.assertIn(title, self.page())

    def test_nothing_to_hold_is_not_counted_as_a_deliverable(self):
        """The column may not be blank but may say no, so the marker must
        distinguish them -- otherwise every row claims to hand something over
        and the "when do I get something" question goes unanswered again."""
        self.write(PLAIN)
        self.gen()
        data = re.search(r"const D=(\[.*?\]);", self.page(), re.S).group(1)
        self.assertIn('"deliver": false', data.replace('"deliver":false', '"deliver": false'))
        self.assertEqual(data.count("true"), 1, "exactly one row hands something over")

    def test_the_page_says_it_is_generated(self):
        """A reader who edits it must be told the edit will be lost."""
        self.write(PLAIN)
        self.gen()
        self.assertIn("Regenerate rather than editing", self.page())


class TracksBecomeLanes(Harness):

    def test_a_track_column_is_optional(self):
        self.write(PLAIN)
        self.assertEqual(self.gen().returncode, 0)

    def test_tracks_reach_the_page_and_keep_the_plan_s_order(self):
        """Never sorted: a plan's lanes are listed in the order the plan
        introduces them, the same as its rows."""
        self.write(TRACKED)
        self.gen()
        data = re.search(r"const D=(\[.*?\]);", self.page(), re.S).group(1)
        order = [m for m in re.findall(r'"tr":\s*"([^"]*)"', data)]
        self.assertEqual(order[0], "Correctness")
        self.assertEqual(order[1], "Surfaces")


class TheDigestMakesStalenessCheckable(Harness):

    def test_a_freshly_generated_page_checks_clean(self):
        self.write(PLAIN)
        self.gen()
        self.assertEqual(run("--check", "--project", str(self.proj)).returncode, 0)

    def test_a_missing_page_is_refused_and_names_the_command(self):
        self.write(PLAIN)
        r = run("--check", "--project", str(self.proj))
        self.assertEqual(r.returncode, 1)
        self.assertIn("bin/milestones", r.stderr)

    def test_changing_the_plan_makes_the_page_stale(self):
        self.write(PLAIN)
        self.gen()
        self.write(PLAIN.replace("The first screen", "The second screen"))
        r = run("--check", "--project", str(self.proj))
        self.assertEqual(r.returncode, 1)
        self.assertIn("stale", r.stderr)

    def test_regenerating_clears_it(self):
        self.write(PLAIN)
        self.gen()
        self.write(PLAIN.replace("The first screen", "The second screen"))
        self.assertEqual(run("--check", "--project", str(self.proj)).returncode, 1)
        self.gen()
        self.assertEqual(run("--check", "--project", str(self.proj)).returncode, 0)

    def test_the_check_is_not_a_byte_comparison(self):
        """The page stamps its own generation time. A byte comparison would
        call every page stale the moment the clock moved, so the digest covers
        the DATA and nothing else. Rewriting the timestamp must not trip it."""
        self.write(PLAIN)
        self.gen()
        page = self.proj / "docs" / "milestones.html"
        page.write_text(re.sub(r"Generated \d{4}-\d\d-\d\d \d\d:\d\d",
                               "Generated 1999-01-01 00:00", page.read_text()))
        self.assertEqual(run("--check", "--project", str(self.proj)).returncode, 0)

    def test_no_checklist_is_two_not_one(self):
        self.assertEqual(run("--check", "--project", str(self.proj)).returncode, 2)


class LandRefusesAStalePicture(unittest.TestCase):
    """Mirrors tests/test_land_milestonecheck.py's harness."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "proj"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.repo / "README.md").write_text("seed\n")
        self.git("add", "-A"); self.git("commit", "-qm", "seed")
        v = subprocess.run([str(RULECHECK), "--version"], capture_output=True,
                           text=True, check=True).stdout.strip()
        (self.repo / STAMP).write_text(v + "\n")
        self.git("add", "-A"); self.git("commit", "-qm", "align")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a],
                              capture_output=True, text=True, check=False)

    def land(self, env=None):
        e = dict(os.environ); e.update(env or {})
        return subprocess.run([str(LAND), "--check"], cwd=str(self.repo),
                              capture_output=True, text=True, check=False, env=e)

    def branch_with(self, checklist, generate):
        self.git("checkout", "-q", "-b", "work")
        (self.repo / "CLAUDE-checklist.md").write_text(checklist)
        if generate:
            subprocess.run([str(GEN), "--project", str(self.repo)],
                           capture_output=True, check=False)
        self.git("add", "-A"); self.git("commit", "-qm", "work")

    def test_a_plan_with_no_page_is_refused(self):
        self.branch_with(PLAIN, generate=False)
        out = self.land()
        self.assertIn(REFUSAL, out.stdout + out.stderr)
        self.assertNotIn("READY", out.stdout)

    def test_a_generated_page_lands(self):
        self.branch_with(PLAIN, generate=True)
        out = self.land()
        self.assertNotIn(REFUSAL, out.stdout + out.stderr)
        self.assertIn("READY", out.stdout)

    def test_the_refusal_says_to_run_it_not_edit_it(self):
        """The whole design fails if someone fixes this by hand-editing."""
        self.branch_with(PLAIN, generate=False)
        combined = self.land().stdout + self.land().stderr
        self.assertIn("not by editing", combined)

    def test_the_override_exists_and_is_explicit(self):
        self.branch_with(PLAIN, generate=False)
        self.assertIn(REFUSAL, self.land().stdout + self.land().stderr)
        ok = self.land(env={"LAND_ALLOW_STALE_MILESTONE_PAGE": "1"})
        self.assertNotIn(REFUSAL, ok.stdout + ok.stderr)
        self.assertIn("READY", ok.stdout)


if __name__ == "__main__":
    unittest.main()
