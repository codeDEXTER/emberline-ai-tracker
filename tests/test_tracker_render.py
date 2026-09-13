"""`tracker render` turns a ledger into its page (proposal 19, W-02).

What the page is for: the sponsor reads the plan without reading JSON, and a
new session sees the same numbers the ledger holds. So the tests pin the
properties that make the page trustworthy rather than its look:

  * the counts on the page are the ledger's counts, row for row;
  * rendering twice gives identical bytes -- a page that changes when nothing
    changed hides the diff that did matter;
  * `--check` compares CONTENT (a digest of the ledger), not modification
    times, which a checkout resets;
  * text from the ledger is escaped -- titles and evidence are free text;
  * the generated page lives in docs/proposals/tracker/, out of reach of the
    three checkers that glob docs/proposals/*.html (proposalcheck's one-number-
    one-document rule, the engine's index builder and its style checker), and
    it never overwrites the hand-authored proposal page.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TRACKER = ROOT / "bin" / "tracker"
ENGINE_71 = Path("/Users/aashish/apps/PhotoVault/engine/docs/proposals/71-engine-1-3-programme.json")


def sample():
    return {
        "proposal": 19, "title": "Warm-up", "status": "accepted", "updated": "2026-09-13",
        "tiers": {"C2": {"tier": "medium", "model": "sonnet", "effort": "medium", "rule": "bounded"}},
        "phases": [{"id": "W", "name": "Build", "goal": "the goal", "exit": "the exit"},
                   {"id": "X", "name": "Research", "goal": "questions", "exit": "answered"}],
        "items": [
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "templates <b>bold</b>", "status": "done",
             "tag": "[ruflo · medium · sonnet]", "issue": 135,
             "log": [{"at": "2026-09-13T21:00:00+02:00", "event": "merged", "by": "lead", "evidence": "abc & def"}]},
            {"id": "W-02", "phase": "W", "cx": "C3", "title": "render", "status": "in progress",
             "tag": "[ruflo · high · opus]", "issue": 136, "depends": "W-01",
             "log": [{"at": "2026-09-13T21:05:00+02:00", "event": "started", "by": "lead", "evidence": ""}]},
            {"id": "W-03", "phase": "W", "cx": "C3", "title": "check", "status": "blocked",
             "tag": "[ruflo · high · opus]", "issue": None,
             "log": [{"at": "2026-09-13T21:06:00+02:00", "event": "blocked", "by": "lead", "evidence": "waits on W-02"}]},
            {"id": "X-01", "phase": "X", "cx": "C2", "title": "HEIC sidecar?", "status": "not started",
             "tag": "[ruflo · medium · sonnet]", "issue": None, "log": []},
        ],
        "asks": [{"id": "A-01", "at": "2026-09-13", "kind": "research",
                  "quote": "Would it make sense to have a <sidecar>?", "became": "X-01", "state": "became-item"},
                 {"id": "A-02", "at": "2026-09-13", "kind": "question",
                  "quote": "will a rerun be faster?", "became": None, "state": "open"}],
        "proposed_changes": [{"at": "2026-09-13T15:48:00+02:00", "from": "agent", "item": "W-02",
                              "change": "split the page", "state": "recorded, not acted on"}],
    }


class Project:
    """A scratch project: docs/proposals/19-proposal-warmup.json and a
    hand-authored 19-proposal-warmup.html that must survive every render."""

    def __init__(self, data=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.proposals = self.root / "docs" / "proposals"
        self.proposals.mkdir(parents=True)
        self.ledger = self.proposals / "19-proposal-warmup.json"
        self.ledger.write_text(json.dumps(data or sample(), indent=2))
        self.authored = self.proposals / "19-proposal-warmup.html"
        self.authored.write_text("<title>19 · accepted · Warm-up</title><p>hand-written</p>")

    @property
    def page(self):
        return self.proposals / "tracker" / "19-proposal-warmup.html"

    def run(self, *args):
        return subprocess.run([sys.executable, str(TRACKER), "render", *args],
                              capture_output=True, text=True, check=False, cwd=self.root)

    def close(self):
        self.tmp.cleanup()


class RenderCase(unittest.TestCase):

    def setUp(self):
        self.p = Project()

    def tearDown(self):
        self.p.close()

    def render(self, *extra):
        r = self.p.run(str(self.p.ledger), *extra)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        return self.p.page.read_text()


class TestWhereThePageGoes(RenderCase):

    def test_it_lands_in_the_tracker_subdirectory(self):
        self.render()
        self.assertTrue(self.p.page.exists())

    def test_the_hand_authored_page_is_never_touched(self):
        before = self.p.authored.read_bytes()
        self.render()
        self.assertEqual(before, self.p.authored.read_bytes())

    def test_out_overrides_the_default(self):
        out = self.p.root / "elsewhere.html"
        r = self.p.run(str(self.p.ledger), "--out", str(out))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertTrue(out.exists())
        self.assertFalse(self.p.page.exists())


class TestTheNumbersAreTheLedgers(RenderCase):

    def test_status_block_carries_the_four_counts(self):
        html = self.render()
        m = re.search(r'class="status"[^>]*data-done="(\d+)"[^>]*data-in-progress="(\d+)"'
                      r'[^>]*data-blocked="(\d+)"[^>]*data-not-started="(\d+)"', html)
        self.assertIsNotNone(m, "no status block with the four counts")
        self.assertEqual(("1", "1", "1", "1"), m.groups())
        self.assertIn("1 done / 1 in progress / 1 blocked / 1 not started", html)

    def test_one_row_per_item_with_its_status(self):
        html = self.render()
        rows = re.findall(r'<tr class="item" data-id="([^"]+)" data-status="([^"]+)"', html)
        self.assertEqual([("W-01", "done"), ("W-02", "in progress"), ("W-03", "blocked"),
                          ("X-01", "not started")], rows)

    def test_every_phase_has_its_section_and_bar(self):
        html = self.render()
        for pid in ("W", "X"):
            self.assertRegex(html, rf'<section class="phase" data-phase="{pid}"')
        self.assertEqual(2, len(re.findall(r'class="bar"', html)))

    def test_asks_and_proposed_changes_are_shown(self):
        html = self.render()
        self.assertRegex(html, r'<tr class="ask" data-id="A-02" data-state="open"')
        self.assertIn("split the page", html)


class TestItIsSafeAndStable(RenderCase):

    def test_free_text_is_escaped(self):
        html = self.render()
        self.assertNotIn("<b>bold</b>", html)
        self.assertIn("templates &lt;b&gt;bold&lt;/b&gt;", html)
        self.assertIn("&lt;sidecar&gt;", html)
        self.assertIn("abc &amp; def", html)

    def test_two_renders_are_byte_identical(self):
        first = self.render()
        second = self.render()
        self.assertEqual(first, second)

    def test_issue_links_use_the_repo_when_given(self):
        html = self.render("--repo", "owner/name")
        self.assertIn('href="https://github.com/owner/name/issues/135"', html)

    def test_without_a_repo_an_issue_is_plain_text(self):
        html = self.render()
        self.assertIn("#135", html)
        self.assertNotIn("github.com", html)


class TestCheck(RenderCase):

    def check(self):
        return self.p.run(str(self.p.ledger), "--check")

    def test_missing_page_is_stale(self):
        r = self.check()
        self.assertEqual(1, r.returncode)
        self.assertIn("missing", r.stdout + r.stderr)

    def test_fresh_page_passes(self):
        self.render()
        self.assertEqual(0, self.check().returncode)

    def test_a_ledger_change_makes_it_stale_even_with_an_older_mtime(self):
        self.render()
        d = sample(); d["items"][3]["status"] = "in progress"
        self.p.ledger.write_text(json.dumps(d, indent=2))
        # Make the page look newer than the ledger: a timestamp check would pass.
        import os
        os.utime(self.p.page, (4102444800, 4102444800))
        r = self.check()
        self.assertEqual(1, r.returncode)
        self.assertIn("stale", r.stdout + r.stderr)

    def test_check_writes_nothing(self):
        self.check()
        self.assertFalse(self.p.page.exists())

    def test_an_invalid_ledger_is_refused_not_drawn(self):
        d = sample(); d["items"][0]["status"] = "wip"
        self.p.ledger.write_text(json.dumps(d, indent=2))
        r = self.p.run(str(self.p.ledger))
        self.assertEqual(1, r.returncode)
        self.assertIn("status 'wip'", r.stderr)
        self.assertFalse(self.p.page.exists())

    def test_unreadable_ledger_is_exit_2(self):
        self.p.ledger.write_text("{not json")
        self.assertEqual(2, self.p.run(str(self.p.ledger)).returncode)


class TestTheRealLedger(unittest.TestCase):

    @unittest.skipUnless(ENGINE_71.exists(), f"{ENGINE_71} is not on this machine")
    def test_the_engine_ledger_renders_every_item(self):
        sys.path.insert(0, str(ROOT))
        from tools.tracker import ledger
        d = ledger.load(ENGINE_71)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "71.html"
            r = subprocess.run([sys.executable, str(TRACKER), "render", str(ENGINE_71), "--out", str(out)],
                               capture_output=True, text=True, check=False)
            self.assertEqual(0, r.returncode, r.stderr)
            html = out.read_text()
        self.assertEqual(len(ledger.items(d)), len(re.findall(r'<tr class="item" ', html)))
        c = ledger.counts(d)
        self.assertIn(f'data-done="{c["done"]}"', html)


if __name__ == "__main__":
    unittest.main()
