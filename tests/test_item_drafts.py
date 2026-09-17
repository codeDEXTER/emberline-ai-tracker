"""`bin/pr-body` and `bin/item-notes` -- drafts assembled from recorded
facts, never a verdict (proposal 31, O-05/O-06; shared facts in
tools/itemfacts.py).

Builds a throwaway git repo with a fixture ledger, a "main" line and a
feature branch with real commits and a real diff (one source file changed,
one test file added), then runs both scripts against it as subprocesses --
the same pattern tests/test_ruflo_item.py and tests/test_tracker_history.py
already use for a real git fixture. Pins: the PR body names the item's
title and the files the diff actually touched; its counts match a plain
`git diff --numstat`; the `Gate:` line is present and unfilled; a missing
item exits non-zero with a message naming it; an item with parts lists
them; `item-notes` prints both labelled blocks plus the "these are drafts"
line; `--commit`/`--pr` show up only when given; and neither command
writes anything -- `git status --porcelain` is byte-identical before and
after running both.

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

PR_BODY = ROOT / "bin" / "pr-body"
ITEM_NOTES = ROOT / "bin" / "item-notes"


class Repo:
    """A throwaway git repo: a main line, then a feature branch with a real
    diff, so pr-body/item-notes read real git output, not a mock."""

    def __init__(self, root: Path):
        self.root = root
        (root / "docs" / "proposals").mkdir(parents=True)
        (root / "tests").mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")

    def git(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, text=True, check=True)

    def write(self, rel: str, text: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, message: str):
        self.git("add", "-A")
        self.git("commit", "-qm", message)


def ledger(items):
    return {"proposal": 99, "title": "Fixture", "status": "accepted", "updated": "2026-09-17",
            "items": items}


def item(iid, title, what="", done="", parts=None, **extra):
    row = {"id": iid, "phase": iid.split("-")[0], "cx": "C2", "title": title,
           "status": "in progress", "what": what, "done": done}
    if parts is not None:
        row["parts"] = parts
    row.update(extra)
    return row


def part(iid, letter, share, status="not started", title=""):
    return {"id": f"{iid}.{letter}", "title": title, "share": share, "status": status}


def run(binary: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(binary), *args], capture_output=True, text=True)


class BaseFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Repo(Path(self._tmp.name) / "proj")

        self.repo.write("docs/proposals/99-fixture.json", json.dumps(ledger([
            item("X-01", "Draft scripts wire up",
                 what="A script prints a PR skeleton from recorded facts.",
                 done="Prints a usable body for a real branch and item."),
            item("X-02", "Item with parts",
                 what="Split across two parts.",
                 done="Both parts done.",
                 parts=[part("X-02", "A", 60, "done", "first half"),
                        part("X-02", "B", 40, "not started", "second half")]),
        ]), indent=2))
        self.repo.write("a.py", "print('a')\n")
        self.repo.commit("seed: a.py and the fixture ledger")

        self.repo.git("branch", "feature")
        self.repo.git("checkout", "-q", "feature")
        self.repo.write("a.py", "print('a')\nprint('changed')\n")
        self.repo.write("tests/test_a.py", "def test_a():\n    assert True\n")
        self.repo.commit("X-01: touch a.py and add its test")
        self.repo.write("a.py", "print('a')\nprint('changed')\nprint('again')\n")
        self.repo.commit("X-01: one more line")

    def porcelain(self) -> str:
        return self.repo.git("status", "--porcelain").stdout


class PrBodyTests(BaseFixture):
    def test_names_the_item_title_and_the_gate_line_is_unfilled(self):
        r = run(PR_BODY, "--project", str(self.repo.root), "--item", "X-01", "--base", "main")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("X-01", r.stdout)
        self.assertIn("Draft scripts wire up", r.stdout)
        self.assertIn("Gate:", r.stdout)
        gate_line = next(l for l in r.stdout.splitlines() if l.startswith("Gate:"))
        self.assertNotRegex(gate_line, r"\bOK\b")
        self.assertIn("NOT FILLED IN", gate_line)

    def test_trailer_is_present(self):
        r = run(PR_BODY, "--project", str(self.repo.root), "--item", "X-01", "--base", "main")
        self.assertIn("Generated with [Claude Code](https://claude.com/claude-code)", r.stdout)

    def test_diff_counts_match_the_real_diff(self):
        real = self.repo.git("diff", "--numstat", "main...HEAD").stdout
        real_files = {}
        for line in real.splitlines():
            ins, dele, path = line.split("\t", 2)
            real_files[path] = (ins, dele)

        r = run(PR_BODY, "--project", str(self.repo.root), "--item", "X-01", "--base", "main")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("a.py", r.stdout)
        self.assertIn("tests/test_a.py", r.stdout)
        for path, (ins, dele) in real_files.items():
            self.assertIn(f"+{ins}/-{dele}", r.stdout, f"counts for {path} not found verbatim")
        # 1 test file among the 2 changed
        self.assertIn("1 test file(s) touched", r.stdout)
        self.assertIn("2 file(s) changed", r.stdout)

    def test_branch_and_commits_are_listed(self):
        r = run(PR_BODY, "--project", str(self.repo.root), "--item", "X-01", "--base", "main")
        self.assertIn("feature", r.stdout)
        self.assertIn("2 commit(s)", r.stdout)
        self.assertIn("touch a.py and add its test", r.stdout)
        self.assertIn("one more line", r.stdout)

    def test_title_only(self):
        r = run(PR_BODY, "--project", str(self.repo.root), "--item", "X-01",
                "--base", "main", "--title-only")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("X-01: Draft scripts wire up", r.stdout.strip())

    def test_item_with_parts_lists_them(self):
        r = run(PR_BODY, "--project", str(self.repo.root), "--item", "X-02", "--base", "main")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("X-02.A", r.stdout)
        self.assertIn("X-02.B", r.stdout)
        self.assertIn("done", r.stdout)
        self.assertIn("not started", r.stdout)

    def test_missing_item_exits_nonzero_with_a_message(self):
        r = run(PR_BODY, "--project", str(self.repo.root), "--item", "X-99", "--base", "main")
        self.assertNotEqual(0, r.returncode)
        self.assertIn("X-99", r.stderr)

    def test_writes_nothing(self):
        before = self.porcelain()
        run(PR_BODY, "--project", str(self.repo.root), "--item", "X-01", "--base", "main")
        self.assertEqual(before, self.porcelain())

    def test_default_base_is_origin_main(self):
        source = PR_BODY.read_text()
        self.assertIn('DEFAULT_BASE = "origin/main"', source)


class ItemNotesTests(BaseFixture):
    def test_prints_both_labelled_blocks_and_the_draft_notice(self):
        r = run(ITEM_NOTES, "--project", str(self.repo.root), "--item", "X-01", "--base", "main")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("DRAFT", r.stdout)
        self.assertIn("do not paste unread", r.stdout.lower())
        self.assertIn("ruflo-item done:", r.stdout)
        self.assertIn("tracker set --event:", r.stdout)
        self.assertIn("X-01", r.stdout)
        self.assertIn("Draft scripts wire up", r.stdout)

    def test_commit_and_pr_appear_only_when_given(self):
        bare = run(ITEM_NOTES, "--project", str(self.repo.root), "--item", "X-01", "--base", "main")
        self.assertNotIn("PR #", bare.stdout)
        self.assertNotIn("Commit ", bare.stdout)
        self.assertNotIn("commit ", bare.stdout.lower().replace("do not paste", ""))

        given = run(ITEM_NOTES, "--project", str(self.repo.root), "--item", "X-01", "--base", "main",
                    "--commit", "abc1234", "--pr", "42")
        self.assertIn("abc1234", given.stdout)
        self.assertIn("PR #42", given.stdout)

    def test_event_text_matches_the_voice_of_real_log_entries(self):
        """Real log entries (read across docs/proposals/*.json before this
        was written) are a prose sentence describing what changed, often
        naming a PR -- never a checklist and never a bare "done"."""
        r = run(ITEM_NOTES, "--project", str(self.repo.root), "--item", "X-01", "--base", "main",
                "--pr", "42")
        event = r.stdout.split("tracker set --event:\n", 1)[1].strip()
        self.assertTrue(event.endswith("."))
        self.assertNotIn("\n-", event)  # no checklist bullets
        self.assertIn("PR #42", event)

    def test_missing_item_exits_nonzero_with_a_message(self):
        r = run(ITEM_NOTES, "--project", str(self.repo.root), "--item", "X-99", "--base", "main")
        self.assertNotEqual(0, r.returncode)
        self.assertIn("X-99", r.stderr)

    def test_writes_nothing(self):
        before = self.porcelain()
        run(ITEM_NOTES, "--project", str(self.repo.root), "--item", "X-01", "--base", "main",
            "--commit", "abc1234", "--pr", "42")
        self.assertEqual(before, self.porcelain())


class BothCommandsTogetherTests(BaseFixture):
    def test_running_both_leaves_the_repo_exactly_as_it_was(self):
        before = self.porcelain()
        run(PR_BODY, "--project", str(self.repo.root), "--item", "X-01", "--base", "main")
        run(ITEM_NOTES, "--project", str(self.repo.root), "--item", "X-01", "--base", "main",
            "--commit", "abc1234", "--pr", "42")
        self.assertEqual(before, self.porcelain())


if __name__ == "__main__":
    unittest.main()
