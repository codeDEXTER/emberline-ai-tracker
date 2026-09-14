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
    shown = subprocess.run(["git", "show", f"{ref}:tools/tracker/render.py"], cwd=ROOT,
                           capture_output=True, text=True)
    if shown.returncode != 0:
        raise unittest.SkipTest(f"{ref} is not in this checkout's history (no .git, or a shallow clone)")
    content = shown.stdout
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
        # V-09 made the total the headline; its % is a smaller unit span.
        self.assertIn('>30<span class="unit">%</span>', html)

    def test_no_readiness_weights_means_no_readiness_line(self):
        html = render_html(sample())
        self.assertNotIn('class="readiness"', html)

    def test_readiness_is_the_headline_number_with_its_parts_beneath(self):
        """Proposal 20, V-09 (carried forward from V-03): readiness was small
        grey text beside its label. It is the page's headline: a large number
        first on the page, its four parts on the line beneath it."""
        d = sample()
        d["readiness_weights"] = {"work": 60, "gates": 20, "floors": 10, "receipts": 10}
        d["gates"] = [{"id": "G0", "title": "Foundation", "passed": True},
                      {"id": "G1", "title": "Shell", "passed": False}]
        d["quality_floors"] = [{"title": "Tests green", "met": True},
                               {"title": "Coverage", "met": False}]
        html = render_html(d)
        section = re.search(r'<section class="readiness"[^>]*>.*?</section>', html, re.S).group(0)
        headline = section.find('<p class="headline">30<span class="unit">%</span></p>')
        parts = section.find('<ul class="parts"><li>work 15.0</li><li>gates 10.0</li>'
                             '<li>floors 5.0</li><li>receipts 0.0</li></ul>')
        self.assertGreaterEqual(headline, 0, section)
        self.assertGreater(parts, headline, "the four parts must sit beneath the number")
        self.assertNotIn('class="count"', section, "the number is no longer grey text beside the label")
        # First thing after the header: before the item counts and every phase.
        self.assertLess(html.find('<section class="readiness"'), html.find('<section class="status"'))
        # Large and prominent, in the page's own stylesheet.
        m = re.search(r"\.readiness \.headline\{[^}]*font:700 (\d+)px", html)
        self.assertIsNotNone(m, "no headline rule in the stylesheet")
        self.assertGreaterEqual(int(m.group(1)), 56)

    def test_the_headline_css_is_only_on_pages_with_readiness(self):
        self.assertNotIn(".headline", render_html(sample()))


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


URL = "https://claude.ai/code/artifact/00000000-0000-0000-0000-000000000000"


class TestPublished(RenderCase):
    """Proposal 20, V-09 (D1): an artifact is published only through a
    session's Artifact tool, which no script can call. `tracker published`
    records what was published -- the URL and the digest of the page as it
    stands -- in a committed sidecar beside the page, so the card can say when
    the page has moved since. It refuses to record a page that is not the
    ledger's current page, a URL that is not one https line, and anything at
    all when the ledger switches publishing off."""

    def setUp(self):
        super().setUp()
        # V-11 round 2: a record is made only of a committed ledger, so the
        # scratch project is a git repository.
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.commit("seed")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.p.root), *a], capture_output=True, text=True, check=False)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-qm", msg)

    @property
    def sidecar(self):
        return self.p.proposals / "tracker" / "19-proposal-warmup.published.json"

    def published(self, *args):
        return subprocess.run([sys.executable, str(TRACKER), "published", str(self.p.ledger), *args],
                              capture_output=True, text=True, check=False, cwd=self.p.root)

    def test_an_uncommitted_or_untracked_ledger_is_refused(self):
        """V-11 round 2, D2: the digest of a ledger nobody committed is not a record."""
        self.render()
        d = sample(); d["items"][3]["status"] = "in progress"
        self.p.ledger.write_text(json.dumps(d, indent=2))
        self.render()                                   # the tracker page is fresh; the ledger is not committed
        r = self.published("--url", URL)
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("the ledger has uncommitted changes -- commit it first -- nothing recorded", r.stderr)
        self.assertFalse(self.sidecar.exists())
        self.git("add", str(self.p.ledger))            # staged is not committed either
        self.assertEqual(1, self.published("--url", URL).returncode)
        self.git("rm", "-q", "--cached", str(self.p.ledger))
        self.git("commit", "-qm", "ledger untracked")   # no add -A: it would track the ledger again
        self.assertEqual("", self.git("ls-files", str(self.p.ledger)).stdout)
        r = self.published("--url", URL)
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("the ledger has uncommitted changes -- commit it first -- nothing recorded", r.stderr)
        self.assertFalse(self.sidecar.exists())

    def test_a_ledger_outside_any_git_repository_is_refused(self):
        q = Project()
        try:
            self.assertEqual(0, q.run(str(q.ledger)).returncode)
            r = subprocess.run([sys.executable, str(TRACKER), "published", str(q.ledger), "--url", URL],
                               capture_output=True, text=True, check=False, cwd=q.root)
            self.assertEqual(1, r.returncode, r.stdout + r.stderr)
            self.assertIn("not inside a git repository", r.stderr)
            self.assertEqual([], list(q.root.rglob("*.published.json")))
        finally:
            q.close()

    def test_page_unchanged_without_page_is_refused(self):
        self.render()
        r = self.published("--url", URL, "--page-unchanged")
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("--page-unchanged", r.stderr)
        self.assertFalse(self.sidecar.exists())

    def test_a_sidecar_symlinked_outside_the_project_is_refused(self):
        """V-11 round 2 (from V-09): writing through it would land outside the project."""
        self.render()
        outside = self.p.root.parent / f"{self.p.root.name}-outside.json"
        outside.write_text("untouched\n")
        self.addCleanup(outside.unlink)
        self.sidecar.symlink_to(outside)
        self.commit("sidecar symlinked out")
        r = self.published("--url", URL)
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("outside the project", r.stderr)
        self.assertIn("nothing recorded", r.stderr)
        self.assertEqual("untouched\n", outside.read_text())

    def test_it_records_url_page_digest_real_clock_and_by(self):
        import datetime
        import hashlib
        self.render()
        before = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        r = self.published("--url", URL, "--by", "lead")
        after = datetime.datetime.now(datetime.timezone.utc)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        record = json.loads(self.sidecar.read_text())
        # V-11: ledger_digest joins every record; digest keeps its V-09 meaning.
        self.assertEqual({"url", "digest", "at", "by", "ledger_digest"}, set(record))
        self.assertEqual(URL, record["url"])
        self.assertEqual(hashlib.sha256(self.p.page.read_bytes()).hexdigest(), record["digest"])
        self.assertEqual(hashlib.sha256(self.p.ledger.read_bytes()).hexdigest(), record["ledger_digest"])
        self.assertEqual("lead", record["by"])
        self.assertRegex(record["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")
        at = datetime.datetime.fromisoformat(record["at"])
        self.assertTrue(before <= at <= after, f"{at} is not the real clock ({before} .. {after})")

    def test_the_sidecar_is_deterministic_json(self):
        self.render()
        self.assertEqual(0, self.published("--url", URL).returncode)
        text = self.sidecar.read_text()
        self.assertEqual(json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n", text)

    def test_by_is_optional_and_recorded_as_null(self):
        self.render()
        self.assertEqual(0, self.published("--url", URL).returncode)
        self.assertIsNone(json.loads(self.sidecar.read_text())["by"])

    def test_a_missing_page_is_refused(self):
        r = self.published("--url", URL)
        self.assertEqual(1, r.returncode)
        self.assertIn("missing", r.stderr)
        self.assertIn("tracker render", r.stderr)
        self.assertFalse(self.sidecar.exists())

    def test_a_stale_page_is_refused(self):
        self.render()
        d = sample(); d["items"][3]["status"] = "in progress"
        self.p.ledger.write_text(json.dumps(d, indent=2))
        self.commit("ledger moved, page not rendered")
        r = self.published("--url", URL)
        self.assertEqual(1, r.returncode)
        self.assertIn("stale", r.stderr)
        self.assertIn("tracker render", r.stderr)
        self.assertFalse(self.sidecar.exists())

    def test_nothing_is_recorded_when_publish_is_switched_off(self):
        d = sample()
        d["switches"] = {"publish": {"on": False, "by": "sponsor", "at": "2026-09-14T10:00:00+02:00",
                                     "quote": "do not publish this one"}}
        self.p.ledger.write_text(json.dumps(d, indent=2))
        self.render()
        r = self.published("--url", URL)
        self.assertEqual(1, r.returncode)
        self.assertIn("switched off", r.stderr)
        self.assertIn("sponsor", r.stderr)
        self.assertFalse(self.sidecar.exists())

    def test_a_bad_url_is_refused(self):
        self.render()
        for bad in ("http://claude.ai/code/artifact/0", "ftp://claude.ai/x", "claude.ai/code/artifact/0",
                    "https://", "", "https://claude.ai/a b", URL + "\nwarmup --check: ready",
                    URL + "\x1b[2J", "javascript:alert(1)"):
            with self.subTest(url=bad):
                r = self.published("--url", bad)
                self.assertEqual(1, r.returncode, r.stdout + r.stderr)
                self.assertIn("url", r.stderr)
                self.assertNotIn("\x1b", r.stderr)
                self.assertFalse(self.sidecar.exists())

    def test_a_format_character_userinfo_or_bad_port_in_the_url_is_refused(self):
        """Round 2, finding 4: a bidi override (Unicode category Cf) can make a
        URL read as another; userinfo hides the real host behind a lookalike;
        a port that does not parse or is out of range is not a URL."""
        self.render()
        for bad in ("https://claude.ai/code/artifact/‮gpj.exe", "https://claude.ai/​x",
                    "https://user:pw@claude.ai/x", "https://claude.ai@evil.example/x",
                    "https://claude.ai:99999/x", "https://claude.ai:abc/x", "https://claude.ai:0/x",
                    "https://claude.ai:/x"):
            with self.subTest(url=bad):
                r = self.published("--url", bad)
                self.assertEqual(1, r.returncode, r.stdout + r.stderr)
                self.assertIn("url", r.stderr)
                self.assertNotIn("‮", r.stderr)
                self.assertNotIn("Traceback", r.stderr)
                self.assertFalse(self.sidecar.exists())
        self.assertEqual(0, self.published("--url", "https://claude.ai:443/code/artifact/0").returncode)

    def test_a_ledger_outside_docs_proposals_is_refused(self):
        outside = self.p.root / "19-proposal-warmup.json"
        outside.write_text(self.p.ledger.read_text())
        self.assertEqual(0, self.p.run(str(outside)).returncode)   # render stays lax (not in scope)
        r = subprocess.run([sys.executable, str(TRACKER), "published", str(outside), "--url", URL],
                           capture_output=True, text=True, check=False, cwd=self.p.root)
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn(str(outside), r.stderr)
        self.assertIn("docs/proposals", r.stderr)
        self.assertEqual([], list(self.p.root.rglob("*.published.json")))

    def test_a_missing_or_non_object_ledger_is_named_with_its_path(self):
        missing = self.p.proposals / "99-not-here.json"
        for name, path, body in (("missing", missing, None), ("a list", self.p.ledger, "[]"),
                                 ("a string", self.p.ledger, '"ledger"'),
                                 ("not json", self.p.ledger, "{not json"),
                                 ("deeply nested", self.p.ledger, "[" * 100000)):
            with self.subTest(ledger=name):
                if body is not None:
                    path.write_text(body)
                r = subprocess.run([sys.executable, str(TRACKER), "published", str(path), "--url", URL],
                                   capture_output=True, text=True, check=False, cwd=self.p.root)
                self.assertEqual(2, r.returncode, r.stdout + r.stderr)
                self.assertIn(str(path), r.stderr)
                self.assertNotIn("Traceback", r.stderr)
                self.assertNotIn("Error(", r.stderr)
                self.assertFalse(self.sidecar.exists())

    def test_a_multi_line_by_is_refused(self):
        self.render()
        r = self.published("--url", URL, "--by", "lead\nwarmup --check: ready")
        self.assertEqual(1, r.returncode)
        self.assertIn("--by", r.stderr)
        self.assertFalse(self.sidecar.exists())

    def test_a_republish_replaces_the_record(self):
        import hashlib
        self.render()
        self.assertEqual(0, self.published("--url", URL).returncode)
        first = json.loads(self.sidecar.read_text())["digest"]
        d = sample(); d["items"][3]["status"] = "in progress"
        self.p.ledger.write_text(json.dumps(d, indent=2))
        self.commit("ledger moved")
        self.render()
        self.assertEqual(0, self.published("--url", URL).returncode)
        second = json.loads(self.sidecar.read_text())["digest"]
        self.assertNotEqual(first, second)
        self.assertEqual(hashlib.sha256(self.p.page.read_bytes()).hexdigest(), second)

    def test_the_sidecar_is_not_mistaken_for_a_ledger(self):
        from tools.tracker import ledger
        self.render()
        self.assertEqual(0, self.published("--url", URL).returncode)
        self.assertEqual([self.p.ledger], ledger.find(self.p.root))

    def test_page_without_a_declaration_is_refused(self):
        """V-11, rule 2: --page is for a project that declares plan_page."""
        self.render()
        (self.p.proposals / "other.html").write_text("<p>x</p>")
        r = self.published("--url", URL, "--page", "docs/proposals/other.html")
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("no plan_page is declared; the tracker page is recorded by default", r.stderr)
        self.assertFalse(self.sidecar.exists())


GENERATOR = '''\
import hashlib, os, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
ledger = root / "docs" / "proposals" / "70-r9-delivery-plan.json"
out = root / "docs" / "proposals" / "70-r9-delivery-plan.html"
day = os.environ.get("PLAN_DATE", "2026-09-14")
body = hashlib.sha256(ledger.read_bytes()).hexdigest()
out.write_text(f"<p>generated {day} from 70-r9-delivery-plan.json</p><p>{body}</p>\\n")
'''

APP_PAGE = "docs/proposals/70-r9-delivery-plan.html"


class AppProject:
    """App-shaped scratch git project (proposal 20, V-11): a ledger, a
    .common-rules.json declaring plan_page, and a generator that writes the
    page with a date taken from PLAN_DATE -- the PhotoVault app's
    tools/build_plan.py writes date.today() into its page the same way."""

    def __init__(self, declaration=None, subdir=False):
        self.tmp = tempfile.TemporaryDirectory()
        # subdir (V-11 round 2, E6): the project is mono/app inside a git repository rooted at mono.
        self.repo = Path(self.tmp.name).resolve() / ("mono" if subdir else "app")
        self.root = self.repo / "app" if subdir else self.repo
        self.proposals = self.root / "docs" / "proposals"
        self.proposals.mkdir(parents=True)
        if subdir:
            (self.repo / ".common-rules.json").write_text("{}\n")   # the repo's own: declares no plan_page
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.ledger = self.proposals / "70-r9-delivery-plan.json"
        self.ledger.write_text(json.dumps(sample(), indent=2))
        (self.root / "tools").mkdir()
        (self.root / "tools" / "build_plan.py").write_text(GENERATOR)
        decl = {"plan_page": "python3 tools/build_plan.py"} if declaration is None else declaration
        (self.root / ".common-rules.json").write_text(
            decl if isinstance(decl, str) else json.dumps(decl, indent=2))
        self.generate("2026-09-14")
        self.commit("seed")

    @property
    def sidecar(self):
        return self.proposals / "tracker" / "70-r9-delivery-plan.published.json"

    @property
    def page(self):
        return self.root / APP_PAGE

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a], capture_output=True, text=True, check=False)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-qm", msg)

    def move_the_ledger(self, status="blocked"):
        d = sample(); d["items"][3]["status"] = status
        self.ledger.write_text(json.dumps(d, indent=2))

    def generate(self, day):
        import os
        subprocess.run([sys.executable, str(self.root / "tools" / "build_plan.py")], check=True,
                       env=dict(os.environ, PLAN_DATE=day))

    def published(self, *args):
        return subprocess.run([sys.executable, str(TRACKER), "published", str(self.ledger), "--url", URL, *args],
                              capture_output=True, text=True, check=False, cwd=self.root)

    def close(self):
        self.tmp.cleanup()


class TestPublishedDeclaredPage(unittest.TestCase):
    """Proposal 20, V-11 (D1 with D9). Found by the PhotoVault app on first
    real use: its sponsor publishes the page its own plan_page generator
    writes, but `tracker published` recorded the digest of the tracker page,
    which was never published -- the record claimed a publish that did not
    happen. A project that declares plan_page must name the page it
    published; the record then carries that file and the ledger's digest."""

    def setUp(self):
        self.p = AppProject()

    def tearDown(self):
        self.p.close()

    def assert_refused(self, r, *needles):
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        for needle in needles:
            self.assertIn(needle, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertFalse(self.p.sidecar.exists())
        self.assertEqual([], list(self.p.root.rglob("*.published.json")))

    def test_a_declared_plan_page_without_page_is_refused(self):
        r = self.p.published()
        self.assert_refused(r, "tracker published: this project declares plan_page (python3 tools/build_plan.py); "
                               "pass --page <the file it writes> -- nothing recorded")

    STALE = f"{APP_PAGE} was last committed before the ledger changed -- regenerate and commit it first -- nothing recorded"

    def test_d1_a_page_committed_before_the_ledger_is_refused(self):
        """V-11 round 2, D1: the ledger edited and committed, the page not
        regenerated. Recording it would leave the card silent for good."""
        self.p.move_the_ledger()
        self.p.commit("ledger moved, page not regenerated")
        self.assert_refused(self.p.published("--page", APP_PAGE), self.STALE)

    def test_d2_an_uncommitted_ledger_is_refused(self):
        self.p.move_the_ledger()
        self.p.generate("2026-09-15")
        self.p.git("add", str(self.p.page))
        self.p.git("commit", "-qm", "page only")
        self.assert_refused(self.p.published("--page", APP_PAGE),
                            "the ledger has uncommitted changes -- commit it first -- nothing recorded")

    def test_the_documented_order_records(self):
        self.p.move_the_ledger()
        self.p.commit("ledger first")
        self.p.generate("2026-09-15")
        self.p.commit("then the regenerated page")
        r = self.p.published("--page", APP_PAGE)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("page_unchanged", json.loads(self.p.sidecar.read_text()))

    def test_a_combined_commit_records(self):
        self.p.move_the_ledger()
        self.p.generate("2026-09-15")
        self.p.commit("ledger and page together")
        self.assertEqual(0, self.p.published("--page", APP_PAGE).returncode)

    def test_page_unchanged_is_the_recorded_override(self):
        self.p.move_the_ledger()
        self.p.commit("a ledger change the page does not show")
        self.assert_refused(self.p.published("--page", APP_PAGE), self.STALE)
        r = self.p.published("--page", APP_PAGE, "--page-unchanged")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        record = json.loads(self.p.sidecar.read_text())
        self.assertIs(True, record["page_unchanged"])
        self.assertEqual({"url", "digest", "at", "by", "page", "ledger_digest", "page_unchanged"}, set(record))

    def test_page_unchanged_still_needs_a_committed_ledger(self):
        self.p.move_the_ledger()
        self.assert_refused(self.p.published("--page", APP_PAGE, "--page-unchanged"),
                            "the ledger has uncommitted changes")

    def test_unrelated_declaration_problems_do_not_block(self):
        """V-11 round 2, E2/E3: a missing read_order or safety_rules file, or
        a bad gate, is warmup --check's to name; it does not stop a record."""
        cmd = "python3 tools/build_plan.py"
        for name, decl in (("read_order names a missing file", {"plan_page": cmd, "read_order": ["MISSING.md"]}),
                           ("safety_rules names a missing file", {"plan_page": cmd, "safety_rules": "NOPE.md#rules"}),
                           ("a bad merge gate", {"plan_page": cmd, "gates": {"merge": 7}}),
                           ("gates not an object", {"plan_page": cmd, "gates": "sh gate.sh"})):
            with self.subTest(declaration=name):
                (self.p.root / ".common-rules.json").write_text(json.dumps(decl))
                self.p.commit(name)
                r = self.p.published("--page", APP_PAGE)
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                self.p.sidecar.unlink()

    def test_a_tracker_dir_symlinked_outside_the_project_is_refused(self):
        outside = Path(self.p.tmp.name).resolve() / "elsewhere"
        outside.mkdir()
        (self.p.proposals / "tracker").symlink_to(outside, target_is_directory=True)
        self.p.commit("tracker dir symlinked out")
        self.assert_refused(self.p.published("--page", APP_PAGE), "outside the project")
        self.assertEqual([], list(outside.iterdir()))

    def test_a_broken_declaration_is_refused_with_its_problems_named(self):
        for name, decl, needle in (("not json", "{not json", "not valid JSON"),
                                   ("not an object", "[]", "not a JSON object"),
                                   ("plan_page not a string", {"plan_page": 7}, "plan_page must be a command string"),
                                   ("plan_page two lines", {"plan_page": "a\nb"}, "plan_page must be one line")):
            for extra in ((), ("--page", APP_PAGE)):
                with self.subTest(declaration=name, page=bool(extra)):
                    (self.p.root / ".common-rules.json").write_text(
                        decl if isinstance(decl, str) else json.dumps(decl))
                    self.p.commit(f"declaration {name}")
                    self.assert_refused(self.p.published(*extra), ".common-rules.json", needle)

    def test_records_page_page_digest_and_ledger_digest(self):
        import datetime
        import hashlib
        before = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        r = self.p.published("--page", APP_PAGE, "--by", "lead")
        after = datetime.datetime.now(datetime.timezone.utc)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        text = self.p.sidecar.read_text()
        record = json.loads(text)
        self.assertEqual(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", text)
        self.assertEqual({"url", "digest", "at", "by", "page", "ledger_digest"}, set(record))
        self.assertEqual(APP_PAGE, record["page"])
        self.assertEqual(hashlib.sha256(self.p.page.read_bytes()).hexdigest(), record["digest"])
        self.assertEqual(hashlib.sha256(self.p.ledger.read_bytes()).hexdigest(), record["ledger_digest"])
        self.assertEqual(URL, record["url"])
        self.assertEqual("lead", record["by"])
        self.assertTrue(before <= datetime.datetime.fromisoformat(record["at"]) <= after)
        # The tracker page was never rendered here: its freshness is not asked of a declared page.
        self.assertFalse((self.p.proposals / "tracker" / "70-r9-delivery-plan.html").exists())

    def test_a_dot_slash_page_is_recorded_as_its_plain_relative_path(self):
        r = self.p.published("--page", "./" + APP_PAGE)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual(APP_PAGE, json.loads(self.p.sidecar.read_text())["page"])

    def test_the_page_is_relative_to_the_project_root_not_the_cwd(self):
        r = subprocess.run([sys.executable, str(TRACKER), "published", str(self.p.ledger), "--url", URL,
                            "--page", APP_PAGE], capture_output=True, text=True, check=False,
                           cwd=self.p.proposals)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_an_absolute_page_is_refused(self):
        self.assert_refused(self.p.published("--page", str(self.p.page)), "--page", "absolute")

    def test_a_dotdot_page_is_refused(self):
        self.assert_refused(self.p.published("--page", "docs/../" + APP_PAGE), "--page", "..")

    def test_a_page_outside_through_a_symlink_is_refused(self):
        outside = Path(self.p.tmp.name).resolve() / "outside.html"
        outside.write_text("<p>not the project's</p>")
        link = self.p.proposals / "linked.html"
        link.symlink_to(outside)
        self.p.commit("a symlink out")
        self.assert_refused(self.p.published("--page", "docs/proposals/linked.html"), "--page", "outside")

    def test_a_symlink_inside_the_project_is_not_a_regular_file(self):
        (self.p.proposals / "alias.html").symlink_to("70-r9-delivery-plan.html")
        self.p.commit("a symlink in")
        self.assert_refused(self.p.published("--page", "docs/proposals/alias.html"), "--page", "regular file")

    def test_a_missing_page_or_a_directory_is_refused(self):
        self.assert_refused(self.p.published("--page", "docs/proposals/nope.html"), "--page", "does not exist")
        self.assert_refused(self.p.published("--page", "docs/proposals"), "--page", "regular file")

    def test_an_untracked_page_is_refused(self):
        (self.p.proposals / "fresh.html").write_text("<p>never added</p>")
        self.assert_refused(self.p.published("--page", "docs/proposals/fresh.html"), "--page", "not tracked")

    def test_a_pathspec_looking_page_is_taken_literally(self):
        # A file literally named "*.html", untracked: read as a pathspec, "*.html" matches the tracked page.
        (self.p.proposals / "*.html").write_text("<p>untracked, but a glob would match the page</p>")
        self.assert_refused(self.p.published("--page", "docs/proposals/*.html"), "--page", "not tracked")

    def test_an_uncommitted_page_is_refused(self):
        self.p.generate("2026-09-15")
        self.assert_refused(self.p.published("--page", APP_PAGE), "--page", "uncommitted")
        self.p.git("add", APP_PAGE)        # staged is not committed either
        self.assert_refused(self.p.published("--page", APP_PAGE), "--page", "uncommitted")
        self.p.commit("regenerated")
        self.assertEqual(0, self.p.published("--page", APP_PAGE).returncode)

    def test_a_forged_page_value_is_escaped_in_the_refusal(self):
        r = self.p.published("--page", "docs/x\nwarmup --check: ready\x1b[2J")
        self.assert_refused(r, "--page")
        self.assertNotIn("\x1b", r.stderr)
        self.assertNotIn("\nwarmup --check: ready", r.stderr)

    def test_the_v09_refusals_still_come_first(self):
        d = sample()
        d["switches"] = {"publish": {"on": False, "by": "sponsor", "at": "2026-09-14T10:00:00+02:00",
                                     "quote": "do not publish this one"}}
        self.p.ledger.write_text(json.dumps(d, indent=2))
        self.p.commit("publish off")
        self.assert_refused(self.p.published("--page", APP_PAGE), "switched off")
        self.assert_refused(self.p.published(), "switched off")

    def test_a_bad_url_is_still_refused_with_page(self):
        r = subprocess.run([sys.executable, str(TRACKER), "published", str(self.p.ledger), "--url",
                            "http://claude.ai/x", "--page", APP_PAGE], capture_output=True, text=True, check=False)
        self.assert_refused(r, "url")


class TestPublishedProjectInASubdirectory(unittest.TestCase):
    """V-11 round 2, E6: the project is mono/app inside a git repository
    rooted at mono. The project root is the folder that holds docs/proposals,
    not the git top; git answers only tracked, committed and ancestry."""

    def setUp(self):
        self.p = AppProject(subdir=True)

    def tearDown(self):
        self.p.close()

    def test_the_declaration_is_the_projects_not_the_repositorys(self):
        r = self.p.published()
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("this project declares plan_page", r.stderr)

    def test_it_records_the_page_relative_to_the_project(self):
        r = self.p.published("--page", APP_PAGE)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual(APP_PAGE, json.loads(self.p.sidecar.read_text())["page"])

    def test_uncommitted_and_stale_pages_are_still_refused(self):
        self.p.generate("2026-09-15")
        r = self.p.published("--page", APP_PAGE)
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("uncommitted", r.stderr)
        self.p.git("checkout", "-q", "--", "app/" + APP_PAGE)
        self.p.move_the_ledger()
        self.p.commit("ledger moved")
        r = self.p.published("--page", APP_PAGE)
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("was last committed before the ledger changed", r.stderr)
        self.assertFalse(self.p.sidecar.exists())


class TestPublishedTrackerPageInAGitProject(unittest.TestCase):
    """V-11: without a declared plan_page, the tracker-page flow is unchanged
    -- the same refusals, the same digest -- and the record gains
    ledger_digest."""

    def setUp(self):
        self.p = AppProject(declaration={"read_order": ["README.md"]})
        (self.p.root / "README.md").write_text("seed\n")
        self.p.commit("readme")

    def tearDown(self):
        self.p.close()

    def test_a_stale_tracker_page_is_still_refused(self):
        r = self.p.published()
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("missing", r.stderr)
        self.assertFalse(self.p.sidecar.exists())

    def test_it_records_the_tracker_page_and_the_ledger_digest(self):
        import hashlib
        subprocess.run([sys.executable, str(TRACKER), "render", str(self.p.ledger)], check=True, capture_output=True)
        r = self.p.published()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        record = json.loads(self.p.sidecar.read_text())
        self.assertEqual({"url", "digest", "at", "by", "ledger_digest"}, set(record))
        tracker_page = self.p.proposals / "tracker" / "70-r9-delivery-plan.html"
        self.assertEqual(hashlib.sha256(tracker_page.read_bytes()).hexdigest(), record["digest"])
        self.assertEqual(hashlib.sha256(self.p.ledger.read_bytes()).hexdigest(), record["ledger_digest"])

    def test_unrelated_declaration_problems_do_not_block_the_tracker_page(self):
        """V-11 round 2, E2/E3, the V-09 flow: no plan_page, other problems."""
        subprocess.run([sys.executable, str(TRACKER), "render", str(self.p.ledger)], check=True, capture_output=True)
        for name, decl in (("read_order names a missing file", {"read_order": ["MISSING.md"]}),
                           ("safety_rules not FILE#heading", {"safety_rules": 5}),
                           ("a bad quick gate", {"gates": {"quick": "a\nb"}})):
            with self.subTest(declaration=name):
                (self.p.root / ".common-rules.json").write_text(json.dumps(decl))
                self.p.commit(name)
                r = self.p.published()
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                self.assertNotIn("page", json.loads(self.p.sidecar.read_text()))
                self.p.sidecar.unlink()


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
