"""bin/recall and bin/remember (proposal 19, D11, W-06).

Every case here runs against a scratch corpus built in a TemporaryDirectory
and passed with --corpus / --dir -- never against a real memory dir, LESSONS
file or ledger. See docs/proposals/19-proposal-warmup.html section L for the
design (D11: memory is recall over what is already written).

Run:  python3 -m unittest discover -s tests -p 'test_recall.py' -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECALL = ROOT / "bin" / "recall"
REMEMBER = ROOT / "bin" / "remember"


def run(script, *args, cwd=None, stdin=None):
    r = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, cwd=cwd, input=stdin,
    )
    return r.returncode, r.stdout, r.stderr


class TestRecallMarkdown(unittest.TestCase):
    """Line-based search over markdown-shaped files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text)
        return p

    def test_multi_word_ranking_prefers_lines_matching_more_words(self):
        self.write("LESSONS.md", (
            "- **[gotcha] 2026-09-09, issue #225. worktree isolation matters here.**\n"
            "- **[gotcha] 2026-09-10, issue #226. worktree matters, isolation matters too, a lot.**\n"
            "- unrelated line about nothing at all\n"
        ))
        rc, out, err = run(RECALL, "--corpus", str(self.dir / "*.md"), "worktree", "isolation")
        self.assertEqual(0, rc)
        lines = out.strip().splitlines()
        # both terms present on line 2 -> score 2, ranks above line 1 (score 2 also,
        # since line 1 has both "worktree" and "isolation" too) -- use a line with
        # only one term to prove the ranking, checked below with an exact score.
        self.assertTrue(any(l.startswith("2  ") for l in lines))
        self.assertIn("recall: ", err)

    def test_single_word_beats_nothing_and_scores_one(self):
        self.write("LESSONS.md", "- **[gotcha] 2026-09-09, issue #1. banana only.**\n")
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "banana")
        self.assertEqual(0, rc)
        line = out.strip().splitlines()[0]
        self.assertTrue(line.startswith("1  "))

    def test_ranking_prefers_more_matched_words_over_fewer(self):
        self.write("A.md", "one banana\n")
        self.write("B.md", "one banana two\n")
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "one", "two")
        self.assertEqual(0, rc)
        lines = out.strip().splitlines()
        self.assertTrue(lines[0].startswith("2  "))
        self.assertIn("B.md", lines[0])

    def test_date_taken_from_the_line_itself_iso(self):
        self.write("LESSONS.md", "- **[gotcha] 2026-09-09, issue #225. banana thing.**\n")
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "banana")
        self.assertEqual(0, rc)
        self.assertIn("2026-09-09", out)

    def test_date_taken_from_the_line_itself_day_month(self):
        self.write("OPERATING-RULES.md", "Rule added 7 Sept: bananas are now allowed.\n")
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "bananas")
        self.assertEqual(0, rc)
        self.assertIn("7 Sept", out)

    def test_date_taken_from_nearest_preceding_line_within_15(self):
        body = "8 September 2026\n" + ("filler line\n" * 5) + "banana appears here with no date of its own\n"
        self.write("OPERATING-RULES.md", body)
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "banana")
        self.assertEqual(0, rc)
        self.assertIn("8 September 2026", out)

    def test_date_beyond_15_lines_back_does_not_count(self):
        body = "2026-01-01 something dated\n" + ("filler\n" * 20) + "banana with no nearby date\n"
        self.write("OPERATING-RULES.md", body)
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "banana")
        self.assertEqual(0, rc)
        self.assertNotIn("2026-01-01", out)
        self.assertIn("~", out)  # falls back to mtime, marked

    def test_date_falls_back_to_mtime_marked_with_tilde(self):
        p = self.write("LESSONS.md", "banana with no date anywhere in this file\n")
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "banana")
        self.assertEqual(0, rc)
        line = out.strip().splitlines()[0]
        self.assertIn("~", line)

    def test_no_hit_exits_1(self):
        self.write("LESSONS.md", "nothing relevant here\n")
        rc, out, err = run(RECALL, "--corpus", str(self.dir / "*.md"), "zzzznotfound")
        self.assertEqual(1, rc)
        self.assertEqual("", out.strip())
        self.assertIn("0 hits", err)

    def test_limit_caps_the_number_printed(self):
        text = "".join(f"banana line {i}\n" for i in range(30))
        self.write("LESSONS.md", text)
        rc, out, err = run(RECALL, "--corpus", str(self.dir / "*.md"), "--limit", "5", "banana")
        self.assertEqual(0, rc)
        self.assertEqual(5, len(out.strip().splitlines()))
        self.assertIn("30 hits", err)

    def test_json_shape(self):
        self.write("LESSONS.md", "- **[gotcha] 2026-09-09, issue #1. banana thing.**\n")
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "--json", "banana")
        self.assertEqual(0, rc)
        data = json.loads(out)
        self.assertIsInstance(data, list)
        self.assertEqual(1, len(data))
        hit = data[0]
        for key in ("score", "date", "location", "text"):
            self.assertIn(key, hit)
        self.assertEqual(1, hit["score"])
        self.assertTrue(hit["location"].endswith(":1"))

    def test_case_insensitive(self):
        self.write("LESSONS.md", "BANANA in capitals\n")
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "banana")
        self.assertEqual(0, rc)
        self.assertIn("BANANA", out)

    def test_text_trimmed_to_160_chars(self):
        long_line = "banana " + ("x" * 300)
        self.write("LESSONS.md", long_line + "\n")
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.md"), "--json", "banana")
        data = json.loads(out)
        self.assertLessEqual(len(data[0]["text"]), 160)

    def test_unreadable_file_is_skipped_and_counted(self):
        good = self.write("LESSONS.md", "banana here\n")
        bad = self.dir / "bad.md"
        bad.write_bytes(b"\xff\xfe\x00\xff not valid utf-8 \xff")
        rc, out, err = run(RECALL, "--corpus", str(self.dir / "*.md"), "banana")
        self.assertIn("hits in 2 files (1 unreadable)", err)

    def test_no_arguments_is_a_bad_argument(self):
        rc, out, err = run(RECALL, "--corpus", str(self.dir / "*.md"))
        self.assertEqual(2, rc)


class TestRecallLedger(unittest.TestCase):
    """Search over the JSON ledger shape: item log entries and asks."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.ledger_path = self.dir / "19-proposal-warmup.json"
        self.ledger_path.write_text(json.dumps({
            "proposal": 19, "title": "t", "status": "accepted",
            "items": [
                {"id": "W-06", "phase": "W", "cx": "C2", "title": "recall", "status": "done",
                 "log": [
                     {"at": "2026-09-13T21:05:00+02:00", "event": "started", "by": "lead",
                      "evidence": "banana investigation began"},
                     {"at": "2026-09-13T22:00:00+02:00", "event": "finding", "by": "lead",
                      "evidence": "unrelated evidence text"},
                 ]},
            ],
            "asks": [
                {"id": "A-04", "at": "2026-09-13T20:30:00+02:00", "kind": "feature",
                 "quote": "Can we have something like memory, banana style",
                 "became": "W-06", "state": "became-item"},
            ],
        }))

    def test_log_entry_hit_has_item_log_location_and_at_date(self):
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.json"), "banana")
        self.assertEqual(0, rc)
        self.assertIn("#W-06.log[0]", out)
        self.assertIn("2026-09-13", out)

    def test_ask_quote_hit_has_ask_id_location(self):
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.json"), "banana")
        self.assertEqual(0, rc)
        self.assertIn("#A-04", out)

    def test_only_matching_log_entries_are_hits(self):
        rc, out, _ = run(RECALL, "--corpus", str(self.dir / "*.json"), "banana")
        self.assertNotIn("log[1]", out)


class TestRemember(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "memory"

    def test_writes_exact_frontmatter_and_body(self):
        rc, out, err = run(
            REMEMBER, "--name", "bananas-are-great", "--description", "a fact about bananas",
            "--type", "user", "--dir", str(self.dir), "bananas are indeed great",
        )
        self.assertEqual(0, rc, err)
        content = (self.dir / "bananas-are-great.md").read_text()
        self.assertEqual(
            "---\n"
            "name: bananas-are-great\n"
            "description: a fact about bananas\n"
            "metadata:\n"
            "  type: user\n"
            "---\n"
            "\n"
            "bananas are indeed great\n",
            content,
        )

    def test_appends_index_line_creating_memory_md(self):
        run(REMEMBER, "--name", "bananas-are-great", "--description", "a fact about bananas",
            "--type", "user", "--dir", str(self.dir), "body text")
        index = (self.dir / "MEMORY.md").read_text()
        self.assertEqual(
            "# Memory index\n\n"
            "- [Bananas are great](bananas-are-great.md) — a fact about bananas\n",
            index,
        )

    def test_second_entry_appends_without_disturbing_the_first(self):
        run(REMEMBER, "--name", "first-fact", "--description", "d1",
            "--type", "user", "--dir", str(self.dir), "b1")
        run(REMEMBER, "--name", "second-fact", "--description", "d2",
            "--type", "project", "--dir", str(self.dir), "b2")
        index = (self.dir / "MEMORY.md").read_text()
        self.assertIn("- [First fact](first-fact.md) — d1\n", index)
        self.assertIn("- [Second fact](second-fact.md) — d2\n", index)

    def test_duplicate_name_refused_and_file_unchanged(self):
        run(REMEMBER, "--name", "bananas-are-great", "--description", "a fact about bananas",
            "--type", "user", "--dir", str(self.dir), "original body")
        before = (self.dir / "bananas-are-great.md").read_text()
        rc, out, err = run(
            REMEMBER, "--name", "bananas-are-great", "--description", "a different fact",
            "--type", "user", "--dir", str(self.dir), "replacement body",
        )
        self.assertEqual(1, rc)
        after = (self.dir / "bananas-are-great.md").read_text()
        self.assertEqual(before, after)
        self.assertIn("already remembered", err)

    def test_bad_slug_exits_2_and_writes_nothing(self):
        rc, out, err = run(
            REMEMBER, "--name", "Not_A_Slug", "--description", "d",
            "--type", "user", "--dir", str(self.dir), "body",
        )
        self.assertEqual(2, rc)
        self.assertFalse((self.dir / "Not_A_Slug.md").exists())

    def test_body_from_stdin_when_omitted(self):
        rc, out, err = run(
            REMEMBER, "--name", "stdin-fact", "--description", "d",
            "--type", "reference", "--dir", str(self.dir),
            stdin="body via stdin\n",
        )
        self.assertEqual(0, rc, err)
        content = (self.dir / "stdin-fact.md").read_text()
        self.assertIn("body via stdin", content)

    def test_item_and_issue_produce_ledger_line(self):
        run(REMEMBER, "--name", "with-ledger", "--description", "d",
            "--type", "user", "--item", "W-06", "--issue", "140",
            "--dir", str(self.dir), "body")
        content = (self.dir / "with-ledger.md").read_text()
        self.assertIn("Ledger: W-06 · issue #140", content)

    def test_default_dir_derives_from_cwd(self):
        # Exercise the default --dir computation without touching any real
        # memory directory: point HOME at a scratch dir for this one process.
        home = Path(self.tmp.name) / "home"
        home.mkdir()
        cwd = Path(self.tmp.name) / "projA"
        cwd.mkdir()
        env = dict(os.environ)
        env["HOME"] = str(home)
        r = subprocess.run(
            [sys.executable, str(REMEMBER), "--name", "cwd-fact", "--description", "d",
             "--type", "user", "body"],
            capture_output=True, text=True, cwd=str(cwd), env=env,
        )
        self.assertEqual(0, r.returncode, r.stderr)
        # Python's own os.getcwd() resolves symlinks (e.g. macOS /tmp -> /private/tmp),
        # so compare against the same resolved path the script itself will see.
        expected_dir = home / ".claude" / "projects" / str(cwd.resolve()).replace("/", "-") / "memory"
        self.assertTrue((expected_dir / "cwd-fact.md").exists())


if __name__ == "__main__":
    unittest.main()
