"""`tracker render` turns a ledger into its page (proposal 19, W-02, V-03).

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
  * V-03: readiness, gates, quality floors, open requests, owner markers,
    "merged, awaiting evidence" markers and switches-off only ever appear
    when the ledger declares that data -- a ledger with none of it renders
    byte for byte as it did before this file existed, and every one of these
    numbers comes from tools/tracker/ledger.py's own functions, never
    recomputed here.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import importlib.util
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
ENGINE_71 = Path("/Users/the-sponsor/apps/PhotoVault/engine/docs/proposals/71-engine-1-3-programme.json")
APP_70 = Path("/Users/the-sponsor/apps/PhotoVault/app/docs/proposals/70-r9-delivery-plan.json")

# The commit V-01 landed the ledger contract v2 on, and the exact base V-03
# branched from -- pinned so this test does not drift if origin/p20 moves
# while this branch is out for review.
V01_COMMIT = "db0ad0cb702ab1383d6169100cf07130d7b98eb5"


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


def render_html(data: dict) -> str:
    """Render an arbitrary ledger dict and return the page text (one-shot,
    for tests that need a variant of sample() rather than the fixed one
    RenderCase carries)."""
    p = Project(data)
    try:
        r = p.run(str(p.ledger))
        assert r.returncode == 0, r.stdout + r.stderr
        return p.page.read_text()
    finally:
        p.close()


def _load_render_module(ref: str, name: str):
    """The render.py blob at `ref`, imported under `name` so it can be called
    side by side with the current module without clobbering it."""
    content = subprocess.run(["git", "show", f"{ref}:tools/tracker/render.py"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w")
    tmp.write(content)
    tmp.close()
    spec = importlib.util.spec_from_file_location(name, tmp.name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


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


class TestReadiness(unittest.TestCase):

    def test_readiness_line_has_its_four_parts(self):
        d = sample()
        d["readiness_weights"] = {"work": 60, "gates": 20, "floors": 10, "receipts": 10}
        d["gates"] = [{"id": "G0", "title": "Foundation", "passed": True},
                      {"id": "G1", "title": "Shell", "passed": False}]
        d["quality_floors"] = [{"title": "Tests green", "met": True},
                               {"title": "Coverage", "met": False}]
        html = render_html(d)
        self.assertIn('<section class="readiness">', html)
        self.assertIn("work 15.0", html)
        self.assertIn("gates 10.0", html)
        self.assertIn("floors 5.0", html)
        self.assertIn("receipts 0.0", html)
        self.assertIn("30%", html)

    def test_no_readiness_weights_means_no_readiness_line(self):
        html = render_html(sample())
        self.assertNotIn('class="readiness"', html)


class TestGatesAndFloors(unittest.TestCase):

    def test_gates_table_shows_id_title_and_passed(self):
        d = sample()
        d["gates"] = [{"id": "G0", "title": "Foundation", "passed": True},
                      {"id": "G1", "title": "Shell", "passed": False}]
        html = render_html(d)
        section = re.search(r'<section class="gates">.*?</section>', html, re.S).group(0)
        self.assertIn("G0", section)
        self.assertIn("Foundation", section)
        self.assertIn("G1", section)
        self.assertIn("Shell", section)
        self.assertIn("passed", section)
        self.assertIn("not passed", section)

    def test_quality_floors_table_shows_met(self):
        d = sample()
        d["quality_floors"] = [{"title": "Tests green", "met": True},
                               {"title": "Coverage", "met": False}]
        html = render_html(d)
        section = re.search(r'<section class="floors">.*?</section>', html, re.S).group(0)
        self.assertIn("Tests green", section)
        self.assertIn("Coverage", section)
        self.assertIn("met", section)
        self.assertIn("not met", section)

    def test_no_gates_or_floors_means_no_section(self):
        html = render_html(sample())
        self.assertNotIn('class="gates"', html)
        self.assertNotIn('class="floors"', html)


class TestOpenRequests(unittest.TestCase):

    def test_open_requests_render_both_directions_and_hide_closed_ones(self):
        d = sample()
        d["requests"] = [
            {"id": "RQ-01", "from": "lead", "to": "sponsor", "state": "open", "unblocks": ["W-02"]},
            {"id": "RQ-02", "from": "sponsor", "to": "lead", "state": "in progress", "unblocks": []},
            {"id": "RQ-03", "from": "lead", "to": "sponsor", "state": "declined", "unblocks": []},
        ]
        html = render_html(d)
        self.assertRegex(html, r'<tr class="request" data-id="RQ-01" data-state="open">')
        self.assertRegex(html, r'<tr class="request" data-id="RQ-02" data-state="in progress">')
        self.assertNotIn('data-id="RQ-03"', html)
        row = re.search(r'<tr class="request" data-id="RQ-01".*?</tr>', html, re.S).group(0)
        self.assertIn("lead", row)
        self.assertIn("sponsor", row)
        self.assertIn("W-02", row)

    def test_no_requests_means_no_section(self):
        html = render_html(sample())
        self.assertNotIn('class="requests"', html)
        self.assertNotIn('class="request"', html)


class TestOwnerMarkers(unittest.TestCase):

    def test_blocked_row_shows_its_owner(self):
        d = sample()
        d["items"][2]["owner"] = "sponsor"  # W-03, blocked
        html = render_html(d)
        row = re.search(r'<tr class="item" data-id="W-03".*?</tr>', html, re.S).group(0)
        self.assertIn("sponsor", row)

    def test_open_ask_shows_its_owner(self):
        d = sample()
        d["asks"][1]["owner"] = "lead"  # A-02, open
        html = render_html(d)
        row = re.search(r'<tr class="ask" data-id="A-02".*?</tr>', html, re.S).group(0)
        self.assertIn("lead", row)

    def test_answered_ask_does_not_show_an_owner_marker(self):
        d = sample()
        d["asks"][0]["owner"] = "sponsor"  # A-01, became-item, not open
        html = render_html(d)
        row = re.search(r'<tr class="ask" data-id="A-01".*?</tr>', html, re.S).group(0)
        self.assertNotIn("sponsor", row)

    def test_no_owner_means_no_marker(self):
        html = render_html(sample())
        row = re.search(r'<tr class="item" data-id="W-03".*?</tr>', html, re.S).group(0)
        self.assertNotIn("owner", row)


class TestMergedAwaitingEvidence(unittest.TestCase):

    def test_merged_but_not_done_row_is_marked(self):
        d = sample()
        d["items"][1]["merged"] = "abc1234"  # W-02, in progress
        html = render_html(d)
        row = re.search(r'<tr class="item" data-id="W-02".*?</tr>', html, re.S).group(0)
        self.assertIn("merged, awaiting evidence", row)

    def test_merged_and_done_row_is_not_marked(self):
        d = sample()
        d["items"][0]["merged"] = "abc1234"  # W-01, already done
        html = render_html(d)
        row = re.search(r'<tr class="item" data-id="W-01".*?</tr>', html, re.S).group(0)
        self.assertNotIn("merged, awaiting evidence", row)

    def test_no_merged_field_means_no_marker_anywhere(self):
        html = render_html(sample())
        self.assertNotIn("awaiting evidence", html)


class TestSwitches(unittest.TestCase):

    def test_off_switch_shows_by_and_at(self):
        d = sample()
        d["switches"] = {"publish": {"on": False, "by": "sponsor", "at": "2026-09-14T10:00:00+02:00"}}
        html = render_html(d)
        section = re.search(r'<section class="switches">.*?</section>', html, re.S).group(0)
        self.assertIn("publish", section)
        self.assertIn("sponsor", section)
        self.assertIn("2026-09-14 10:00", section)

    def test_on_switch_is_not_listed(self):
        d = sample()
        d["switches"] = {"issues": {"on": True}}
        html = render_html(d)
        self.assertNotIn('class="switches"', html)

    def test_no_switches_means_no_section(self):
        html = render_html(sample())
        self.assertNotIn('class="switches"', html)


class TestWaitingOn(unittest.TestCase):

    def test_owners_are_grouped_with_what_blocks_them(self):
        d = sample()
        d["items"][2]["owner"] = "sponsor"  # W-03, blocked
        d["asks"][1]["owner"] = "lead"      # A-02, open
        html = render_html(d)
        section = re.search(r'<section class="waiting">.*?</section>', html, re.S).group(0)
        self.assertIn("sponsor", section)
        self.assertIn("W-03", section)
        self.assertIn("lead", section)
        self.assertIn("A-02", section)

    def test_no_owners_means_no_waiting_section(self):
        html = render_html(sample())
        self.assertNotIn('class="waiting"', html)


class TestBackwardCompatibility(unittest.TestCase):

    def test_a_ledger_without_the_new_keys_renders_byte_for_byte_as_before(self):
        baseline = _load_render_module(V01_COMMIT, "tracker_render_v01_baseline")
        from tools.tracker import render as current
        data = sample()
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "19-proposal-warmup.json"
            ledger_path.write_text(json.dumps(data, indent=2))
            old_html = baseline.render(data, ledger_path, None)
            new_html = current.render(data, ledger_path, None)
        self.assertEqual(old_html, new_html)


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

    @unittest.skipUnless(APP_70.exists(), f"{APP_70} is not on this machine")
    def test_the_app_ledger_renders_and_shows_its_gates_floors_and_merged_rows(self):
        sys.path.insert(0, str(ROOT))
        from tools.tracker import ledger
        d = ledger.load(APP_70)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "70.html"
            r = subprocess.run([sys.executable, str(TRACKER), "render", str(APP_70), "--out", str(out)],
                               capture_output=True, text=True, check=False)
            self.assertEqual(0, r.returncode, r.stderr)
            html = out.read_text()
        self.assertEqual(len(ledger.items(d)), len(re.findall(r'<tr class="item" ', html)))
        c = ledger.counts(d)
        self.assertIn(f'data-done="{c["done"]}"', html)
        # This ledger declares gates and quality floors, and has rows merged
        # but not yet done -- all three sections/markers should appear.
        self.assertIn('<section class="gates">', html)
        self.assertIn('<section class="floors">', html)
        self.assertIn("merged, awaiting evidence", html)


if __name__ == "__main__":
    unittest.main()
