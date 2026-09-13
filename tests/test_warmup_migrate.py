"""`warmup --migrate` -- a running project moves onto the standard (proposal 19, W-12).

Reheat, in the proposal's words: a session already running on its own rules
is moved onto the standard without a restart. What migrate does, and what
these tests hold it to:

  * seeds what derecord seeds (HANDOFF.md, the hooks, the /warmup skill) and
    imports the project's plan into a ledger under the next free proposal
    number, when it has no ledger yet;
  * moves each rule the standard replaces -- only rules whose bold lead
    matches templates/supersedes.json, never a guess -- verbatim into a dated
    block under `## Superseded` in docs/OPERATING-RULES.md. Nothing is
    deleted: every original line is still in the file afterwards;
  * writes the warm-up pointer into CLAUDE.md between markers, and says the
    change is the sponsor's to review and commit -- land reserves CLAUDE.md;
  * never commits, changes nothing on a second run, and writes nothing at all
    with --dry-run;
  * leaves the card showing what was superseded, so a session that still
    remembers an old rule is answered on the card.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import collections
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WARMUP = ROOT / "bin" / "warmup"
sys.path.insert(0, str(ROOT))

from tools.tracker import ledger as L  # noqa: E402

AT = "2026-09-13T23:50:00+02:00"

OLD_RULES = """# Operating rules — how this project is worked on

## 1. Proposals and the plan

- **One plan, updated in place.** `docs/proposals/53-proposal-plan.html` is the
  plan of record. Never a new plan document.
- **Proposals are numbered, tracked, visual.** Each gets the next number.

## 2. Running work

- **Never `git stash`.** The stash is shared across worktrees.

## 3. Merging and shipping

- **Merge continuously.** One fix, not a wave.

  A batch makes a bisect useless.
- **The plan's progress bars are measured after merges,** never estimated:
  green is merged with tests run here.
"""

CHECKLIST = """# checklist

## Milestones

| # | Milestone | Track | Proves | You get | State |
|---|---|---|---|---|---|
| 1 | First | core | a | nothing to hold | done |
| 2 | Second | core | b | a thing | next |
"""

CLAUDE_MD = "# proj\n\nThe project's own instructions, which stay.\n"


class Project:
    def __init__(self, with_plan=True):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write("CLAUDE.md", CLAUDE_MD)
        self.write("docs/OPERATING-RULES.md", OLD_RULES)
        self.write("docs/proposals/05-proposal-something.html", "<title>05 · accepted · Something</title>")
        if with_plan:
            self.write("CLAUDE-checklist.md", CHECKLIST)
        self.git("add", "-A")
        self.git("commit", "-qm", "seed")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.root), *a], capture_output=True, text=True, check=False)

    def write(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def read(self, rel):
        return (self.root / rel).read_text()

    def migrate(self, *extra):
        return subprocess.run([sys.executable, str(WARMUP), "--project", str(self.root), "--no-recall",
                               "--migrate", "--at", AT, *extra], capture_output=True, text=True, check=False)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts}

    def close(self):
        self.tmp.cleanup()


class Case(unittest.TestCase):
    with_plan = True

    def setUp(self):
        self.p = Project(with_plan=self.with_plan)

    def tearDown(self):
        self.p.close()

    def migrated(self, *extra):
        r = self.p.migrate(*extra)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        return r


class TestSeedAndImport(Case):

    def test_the_plan_becomes_a_ledger_under_the_next_free_number(self):
        self.migrated()
        path = self.p.root / "docs" / "proposals" / "06-milestone-plan.json"
        self.assertTrue(path.exists(), "05 is taken by a proposal page; the ledger takes 06")
        self.assertEqual([], L.validate(L.load(path)))

    def test_derecord_seeding_ran(self):
        self.migrated()
        self.assertTrue((self.p.root / "HANDOFF.md").exists())
        self.assertTrue((self.p.root / ".claude" / "skills" / "warmup" / "SKILL.md").exists())

    def test_nothing_is_committed(self):
        head = self.p.git("rev-parse", "HEAD").stdout
        self.migrated()
        self.assertEqual(head, self.p.git("rev-parse", "HEAD").stdout)


class TestSupersede(Case):

    def test_a_matched_rule_moves_into_a_dated_superseded_block(self):
        self.migrated()
        rules = self.p.read("docs/OPERATING-RULES.md")
        superseded = rules.split("## Superseded", 1)
        self.assertEqual(2, len(superseded), "no ## Superseded section")
        before, after = superseded
        self.assertNotIn("One plan, updated in place", before)
        self.assertIn("One plan, updated in place", after)
        self.assertIn("2026-09-13 · superseded by proposal 19", after)
        self.assertNotIn("progress bars are measured", before)
        self.assertIn("progress bars are measured", after)

    def test_an_unmatched_rule_stays_where_it_was(self):
        self.migrated()
        before = self.p.read("docs/OPERATING-RULES.md").split("## Superseded", 1)[0]
        self.assertIn("**Never `git stash`.**", before)
        self.assertIn("**Proposals are numbered, tracked, visual.**", before)
        self.assertIn("**Merge continuously.**", before)
        self.assertIn("A batch makes a bisect useless.", before, "a multi-paragraph rule was split")

    def test_nothing_is_deleted_every_original_line_survives(self):
        self.migrated()
        new = collections.Counter(l for l in self.p.read("docs/OPERATING-RULES.md").splitlines() if l.strip())
        old = collections.Counter(l for l in OLD_RULES.splitlines() if l.strip())
        missing = old - new
        self.assertEqual({}, dict(missing), "lines lost from OPERATING-RULES.md")


    def test_a_replacement_rule_keeps_what_still_holds_where_the_old_one_stood(self):
        """The PhotoVault engine's review of the real dry run, 13 Sep, before any
        write: moving the whole rule left only a one-line replaced_by inside a
        Superseded heading. A project that already has its own OPERATING-RULES
        gets nothing seeded, so it would have lost substance it still follows --
        "never scrap old content" and "green is merged with its tests run". The
        replacement rule now stands in the same section, carrying both."""
        self.migrated()
        whole = self.p.read("docs/OPERATING-RULES.md")
        live = whole.split("## Superseded", 1)[0]
        section1 = live.split("## 1. Proposals and the plan", 1)[1].split("## 2.", 1)[0]
        self.assertIn("**The ledger is the plan of record, updated in place.**", section1)
        self.assertIn("never scraps old content", section1)
        section3 = live.split("## 3. Merging and shipping", 1)[1]
        self.assertIn("**Progress is measured, never estimated.**", section3)
        self.assertIn("merged with its tests run", section3)
        self.assertIn("the earlier wording is under Superseded", section1)


class TestClaudeMd(Case):

    def test_the_pointer_is_added_and_the_projects_own_text_stays(self):
        r = self.migrated()
        text = self.p.read("CLAUDE.md")
        self.assertIn("The project's own instructions, which stay.", text)
        self.assertIn("<!-- common-rules:warmup -->", text)
        self.assertIn("/warmup", text)
        self.assertIn("the ledger is the record", text.lower())
        self.assertIn("CLAUDE.md", r.stdout)
        self.assertIn("reserved", r.stdout.lower())


class TestIdempotentAndDry(Case):

    def test_a_second_run_changes_nothing(self):
        self.migrated()
        first = self.p.snapshot()
        r = self.migrated()
        self.assertEqual(first, self.p.snapshot())
        self.assertIn("nothing to supersede", r.stdout)

    def test_dry_run_writes_nothing_and_lists_the_plan(self):
        before = self.p.snapshot()
        r = self.migrated("--dry-run")
        self.assertEqual(before, self.p.snapshot())
        self.assertIn("One plan, updated in place", r.stdout)
        self.assertIn("would", r.stdout)

    def test_the_card_shows_what_was_superseded(self):
        self.migrated()
        card = subprocess.run([sys.executable, str(WARMUP), "--project", str(self.p.root), "--no-recall"],
                              capture_output=True, text=True, check=False).stdout
        self.assertIn("Superseded", card)
        self.assertIn("One plan, updated in place", card)


class TestNoPlan(Case):
    with_plan = False

    def test_no_plan_still_migrates_and_says_so(self):
        r = self.migrated()
        self.assertIn("no plan to import", r.stdout)
        self.assertEqual([], [p.name for p in (self.p.root / "docs" / "proposals").glob("*.json")])


class TestNotARepo(unittest.TestCase):

    def test_outside_git_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(WARMUP), "--project", tmp, "--migrate", "--no-recall"],
                               capture_output=True, text=True, check=False)
            self.assertEqual(2, r.returncode)


class TestSupersedesData(unittest.TestCase):
    """templates/supersedes.json is data the migration trusts; hold it to shape."""

    def test_every_entry_carries_a_live_replacement_its_own_pattern_cannot_match(self):
        import json
        import re
        rules = json.loads((ROOT / "templates" / "supersedes.json").read_text())["rules"]
        self.assertTrue(rules)
        for r in rules:
            m = re.match(r"^- \*\*(.+?)\*\*", r.get("replacement", ""))
            self.assertIsNotNone(m, f"{r['id']}: replacement must be a '- **lead** ...' rule")
            self.assertIsNone(re.search(r["match"], m.group(1)),
                              f"{r['id']}: a second migration would supersede its own replacement")


if __name__ == "__main__":
    unittest.main()
