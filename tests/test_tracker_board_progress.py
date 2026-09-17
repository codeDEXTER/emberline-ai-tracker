"""`tracker board`'s Progress charts and Features drill-down (proposal 30,
P-08).

The sponsor asked for "a tracker which should plot a graph over time of how
many tickets are getting finished, how many tickets are added" -- computed
automatically, never hand-updated by AI (P-07, tools/tracker/history.py) --
and, separately, "a feature level graph where I can drop down and it can show
me what sub action items and action items are there ... once I expand the
drop down then it can show me what sub items are there and if there are more
sub sub items".

These tests pin:
  * the Progress block appears when the project has ledger-touching git
    history, and is quietly omitted when it does not (no git repo at all, or
    series() raising);
  * the Features block has one row per proposal, with a completion % and a
    done/total item count;
  * every row is collapsed by default (`<details>` with no bare `open`);
  * nested expansion reaches three depths (item -> part -> sub-part), using
    parts.tree()'s own recursion;
  * the markup is correct with the page's inline <script> never having run.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import board  # noqa: E402


def ledger(number, items, title="a proposal"):
    return {"proposal": number, "title": title, "status": "accepted", "updated": "2026-09-17",
            "phases": [{"id": "W", "name": "Build", "goal": "g", "exit": "e"}],
            "items": items, "asks": []}


def part(pid, title, share, status, **extra):
    row = {"id": pid, "title": title, "share": share, "status": status}
    row.update(extra)
    return row


def item(iid, status="not started", title=None, parts=None, **extra):
    row = {"id": iid, "phase": "W", "cx": "C2", "title": title or iid, "status": status,
           "tier": "medium", "model": "sonnet", "tag": "[ruflo]", "issue": None}
    if parts is not None:
        row["parts"] = parts
    row.update(extra)
    return row


def write(root: Path, number, data) -> Path:
    path = root / f"{number}-x.json"
    path.write_text(json.dumps(data))
    return path


class Repo:
    """A throwaway git repo with a ledger committed on a chosen day --
    same shape as test_tracker_history.py's helper, kept local here since
    this file must not import or edit tools/tracker/history.py's own tests."""

    def __init__(self, root: Path):
        self.root = root
        (root / "docs" / "proposals").mkdir(parents=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (root / "README.md").write_text("seed\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "seed")

    def git(self, *args, env=None):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, text=True, check=True, env=env)

    def commit_ledger(self, name: str, data: dict, day: datetime.date):
        path = self.root / "docs" / "proposals" / name
        path.write_text(json.dumps(data, indent=2) + "\n")
        self.git("add", "-A")
        env = dict(os.environ)
        when = f"{day.isoformat()}T10:00:00+01:00"
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
        self.git("commit", "-qm", f"update {name}", env=env)


class ProgressChartsCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_charts_present_with_git_history(self):
        repo = Repo(self.root / "proj")
        repo.commit_ledger("30-x.json", ledger(30, [item("A-01", status="done")]), datetime.date.today())
        led = ledger(30, [item("A-01", status="done")])
        path = repo.root / "docs" / "proposals" / "30-x.json"
        text = board.render([(path, led)], "demo", None, repo.root)
        self.assertIn('<section class="progress" id="progress">', text)
        self.assertEqual(text.count("<svg"), 2)
        self.assertIn("Progress over time", text)

    def test_charts_omitted_without_git_history(self):
        # self.root is a plain directory, never `git init`-ed -- history.series()
        # raises, and the block must be omitted quietly, not crash the page.
        (self.root / "docs" / "proposals").mkdir(parents=True)
        led = ledger(30, [item("A-01")])
        path = write(self.root / "docs" / "proposals", 30, led)
        text = board.render([(path, led)], "demo", None, self.root)
        self.assertNotIn('id="progress"', text)
        self.assertNotIn("tracker-history-chart", text)

    def test_charts_omitted_when_project_is_none(self):
        led = ledger(30, [item("A-01")])
        path = write(self.root, 30, led)
        text = board.render([(path, led)], "demo", None, None)
        self.assertNotIn('id="progress"', text)

    def test_progress_sits_between_tiles_and_groups(self):
        repo = Repo(self.root / "proj")
        repo.commit_ledger("30-x.json", ledger(30, [item("A-01", status="done")]), datetime.date.today())
        led = ledger(30, [item("A-01", status="done")])
        path = repo.root / "docs" / "proposals" / "30-x.json"
        text = board.render([(path, led)], "demo", None, repo.root)
        tiles_at = text.index('<div class="tiles">')
        progress_at = text.index('<section class="progress"')
        groups_at = text.index('<section class="cgroup"')
        self.assertTrue(tiles_at < progress_at < groups_at)


class FeaturesDrilldownCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def render(self, items, number=30, title="a proposal"):
        led = ledger(number, items, title=title)
        path = write(self.root, number, led)
        return board.render([(path, led)], "demo", None, self.root)

    def test_one_row_per_proposal_with_number_title_and_completion(self):
        text = self.render([item("A-01", status="done"), item("A-02", status="not started")], title="Widgets")
        self.assertIn('<section class="features" id="features">', text)
        self.assertIn('<details class="feature-row" data-proposal="30">', text)
        self.assertIn('<span class="fpn">P30</span>', text)
        self.assertIn('<span class="fptitle">Widgets</span>', text)
        # A-01 is 100% (done, no parts), A-02 is 0% -- average 50%.
        self.assertIn('<span class="fppct">50%</span>', text)
        self.assertIn('<span class="fpcount">1/2 items done</span>', text)

    def test_feature_row_collapsed_by_default(self):
        text = self.render([item("A-01")])
        self.assertNotRegex(text, r'<details class="feature-row"[^>]*\bopen\b')
        self.assertNotRegex(text, r'<details class="item-row"[^>]*\bopen\b')

    def test_says_completion_is_averaged_per_item(self):
        text = self.render([item("A-01")])
        self.assertIn("average of each item", text)

    def test_item_row_shows_completion_bar_group_and_next_part(self):
        text = self.render([
            item("A-01", parts=[part("A-01.A", "first", 60, "done"), part("A-01.B", "second", 40, "in progress")]),
        ])
        self.assertIn('<details class="item-row" data-item data-id="A-01" data-proposal="30">', text)
        self.assertIn('<span class="ipct">60%</span>', text)
        self.assertIn("next: A-01.B", text)
        self.assertIn('class="pill g-s-finish-now"', text)

    def test_item_without_parts_shows_one_implicit_part(self):
        text = self.render([item("I-01", status="in progress", title="no parts yet")])
        # Inside the features block (after the Features heading), the implicit
        # part row for I-01 carries a 100% share, same convention as the
        # completion overview above.
        block = text.split('<section class="features"', 1)[1]
        self.assertIn('<span class="pid">I-01</span>', block)
        self.assertIn('<span class="pshare">100%</span>', block)

    def test_nested_expansion_reaches_three_depths(self):
        text = self.render([
            item("W-10", status="in progress", parts=[
                part("W-10.A", "first half", 50, "done"),
                part("W-10.B", "second half", 50, "in progress", parts=[
                    part("W-10.B.1", "b sub 1", 50, "done"),
                    part("W-10.B.2", "b sub 2", 50, "in progress", parts=[
                        part("W-10.B.2.a", "b.2 leaf a", 50, "done"),
                        part("W-10.B.2.b", "b.2 leaf b", 50, "not started"),
                    ]),
                ]),
            ]),
        ])
        for pid in ("W-10.A", "W-10.B", "W-10.B.1", "W-10.B.2", "W-10.B.2.a", "W-10.B.2.b"):
            self.assertIn(f'<span class="pid">{pid}</span>', text)
        # A part with sub-parts is itself a <details> that expands further.
        self.assertIn('<details class="prow-details">', text)
        # None of the nested <details> is open by default.
        self.assertNotRegex(text, r'<details class="prow-details"[^>]*\bopen\b')

    def test_counts_done_items_by_group_not_raw_status(self):
        # A-01 is "done" outright; A-02 has all its parts done (group "done")
        # even though its own top-level status is "in progress" -- the same
        # rule the completion overview already uses (parts.group()).
        text = self.render([
            item("A-01", status="done"),
            item("A-02", status="in progress", parts=[part("A-02.A", "a", 100, "done")]),
            item("A-03", status="not started"),
        ])
        self.assertIn('<span class="fpcount">2/3 items done</span>', text)

    def test_no_javascript_required(self):
        text = self.render([
            item("A-01", parts=[part("A-01.A", "a", 100, "done")]),
            item("A-02", status="done"),
        ])
        body = text.split("<script>", 1)[0]
        self.assertIn('<section class="features"', body)
        self.assertIn('<span class="fpn">P30</span>', body)
        self.assertIn('<span class="pid">A-01.A</span>', body)

    def test_omitted_when_there_are_no_ledgers(self):
        self.assertEqual(board.features_section([]), "")


if __name__ == "__main__":
    unittest.main()
