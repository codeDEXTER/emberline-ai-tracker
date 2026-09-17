"""`tracker history` -- progress over time, from the ledgers' own git
history, no AI updates (proposal 30, P-07).

The sponsor asked for a graph of tickets finished, tickets added, and the
degree of completion over time, computed automatically in the background,
never hand-edited by AI. These tests build a small throwaway git repo,
commit ledgers on backdated days (some days get no commit at all, to check
carry-forward), and pin: daily counts, added/closed (including a same-day
add-and-close, which a plain before/after total would hide), carry-forward
on days without a commit, nested parts counted as their own tickets, cache
reuse (a rerun re-reads no ledger already seen), and that the SVG helper
renders two charts with no external URLs.

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

from tools.tracker import history  # noqa: E402

TRACKER = ROOT / "bin" / "tracker"


def _iso(day: datetime.date, hour: int = 10) -> str:
    return f"{day.isoformat()}T{hour:02d}:00:00+01:00"


class Repo:
    """A throwaway git repo with ledgers committed on chosen days."""

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
        when = _iso(day)
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
        self.git("commit", "-qm", f"update {name}", env=env)


def item(iid, status, parts=None, **extra):
    row = {"id": iid, "phase": "W", "cx": "C2", "title": iid, "status": status}
    if parts is not None:
        row["parts"] = parts
    row.update(extra)
    return row


def ledger19(items):
    return {"proposal": 19, "title": "Warm-up", "status": "accepted", "updated": "2026-09-14",
            "items": list(items)}


class TestHistorySeries(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Repo(Path(self._tmp.name) / "proj")

        today = datetime.datetime.now(history.TZ).date()
        self.day_a = today - datetime.timedelta(days=4)
        self.day_b = self.day_a + datetime.timedelta(days=1)
        self.day_c = self.day_a + datetime.timedelta(days=2)  # no commit
        self.day_d = self.day_a + datetime.timedelta(days=3)
        self.today = today

        # Day A: two items, one done, one not.
        self.repo.commit_ledger("19-warmup.json", ledger19([
            item("W-01", "done"),
            item("W-02", "not started"),
        ]), self.day_a)

        # Day B: W-02 closes, W-03 is added and already done (same-day
        # add-and-close for W-03 would need its own day -- here it just
        # exercises `added`).
        self.repo.commit_ledger("19-warmup.json", ledger19([
            item("W-01", "done"),
            item("W-02", "done"),
            item("W-03", "not started"),
        ]), self.day_b)

        # Day C: no commit at all -- must carry Day B forward.

        # Day D: W-04 arrives with nested parts -- itself plus A, B, B.1,
        # B.2 all count as tickets; A and B.1 are done.
        self.repo.commit_ledger("19-warmup.json", ledger19([
            item("W-01", "done"),
            item("W-02", "done"),
            item("W-03", "not started"),
            item("W-04", "in progress", parts=[
                {"id": "W-04.A", "title": "A", "share": 50, "status": "done"},
                {"id": "W-04.B", "title": "B", "share": 50, "status": "in progress", "parts": [
                    {"id": "W-04.B.1", "title": "B1", "share": 50, "status": "done"},
                    {"id": "W-04.B.2", "title": "B2", "share": 50, "status": "not started"},
                ]},
            ]),
        ]), self.day_d)

    def by_date(self, rows):
        return {r["date"]: r for r in rows}

    def test_one_row_per_calendar_day_from_first_commit_to_today(self):
        rows = history.series(self.repo.root)
        expected_days = (self.today - self.day_a).days + 1
        self.assertEqual(len(rows), expected_days)
        self.assertEqual(rows[0]["date"], self.day_a.isoformat())
        self.assertEqual(rows[-1]["date"], self.today.isoformat())

    def test_day_a_counts(self):
        rows = self.by_date(history.series(self.repo.root))
        r = rows[self.day_a.isoformat()]
        self.assertEqual(r["tickets_total"], 2)
        self.assertEqual(r["tickets_done"], 1)

    def test_day_b_added_and_closed(self):
        rows = self.by_date(history.series(self.repo.root))
        r = rows[self.day_b.isoformat()]
        self.assertEqual(r["tickets_total"], 3)
        self.assertEqual(r["tickets_done"], 2)
        self.assertEqual(r["added"], 1)          # 3 - 2
        self.assertEqual(r["added_ids"], 1)      # W-03
        self.assertEqual(r["closed"], 1)         # W-02 became done
        self.assertEqual(r["closed_ids"], 1)

    def test_day_c_carries_day_b_forward(self):
        rows = self.by_date(history.series(self.repo.root))
        b, c = rows[self.day_b.isoformat()], rows[self.day_c.isoformat()]
        self.assertEqual(c["tickets_total"], b["tickets_total"])
        self.assertEqual(c["tickets_done"], b["tickets_done"])
        self.assertEqual(c["completion_pct"], b["completion_pct"])
        self.assertEqual(c["added"], 0)
        self.assertEqual(c["closed"], 0)

    def test_day_d_counts_nested_parts_as_tickets(self):
        rows = self.by_date(history.series(self.repo.root))
        r = rows[self.day_d.isoformat()]
        # W-01, W-02, W-03 (3 tickets, 2 done) + W-04, .A, .B, .B.1, .B.2
        # (5 tickets, 2 done: .A and .B.1) = 8 tickets, 4 done.
        self.assertEqual(r["tickets_total"], 8)
        self.assertEqual(r["tickets_done"], 4)
        self.assertEqual(r["added_ids"], 5)
        self.assertEqual(r["closed_ids"], 2)

    def test_day_d_completion_pct_uses_parts_completion_per_item(self):
        rows = self.by_date(history.series(self.repo.root))
        r = rows[self.day_d.isoformat()]
        # W-01=100, W-02=100, W-03=0, W-04=75: its A (50) is done, and its B
        # (50) is half done through its own sub-parts -- completion rolls up
        # through nested parts (proposal 30, the sponsor's "sub sub items").
        self.assertAlmostEqual(r["completion_pct"], 68.8)

    def test_by_proposal_matches_overall_when_theres_one_proposal(self):
        rows = self.by_date(history.series(self.repo.root))
        r = rows[self.day_d.isoformat()]
        self.assertIn("19", r["by_proposal"])
        bp = r["by_proposal"]["19"]
        self.assertEqual(bp["tickets_total"], r["tickets_total"])
        self.assertEqual(bp["tickets_done"], r["tickets_done"])
        self.assertAlmostEqual(bp["completion_pct"], r["completion_pct"])

    def test_since_filters_rows(self):
        rows = history.series(self.repo.root, since=self.day_d.isoformat())
        self.assertTrue(all(r["date"] >= self.day_d.isoformat() for r in rows))
        self.assertEqual(rows[0]["date"], self.day_d.isoformat())

    def test_cache_reuse_reads_no_git_show_for_old_shas(self):
        history.series(self.repo.root)  # populates the cache

        calls = []
        real_git = history._git

        def counting_git(repo, *args):
            calls.append(args)
            return real_git(repo, *args)

        history._git = counting_git
        try:
            history.series(self.repo.root)
        finally:
            history._git = real_git

        show_calls = [a for a in calls if a and a[0] == "show"]
        self.assertEqual(show_calls, [], f"expected no `git show` on a cached rerun, got {show_calls}")

    def test_cache_file_is_written_and_not_inside_the_repo_unless_ignored(self):
        history.series(self.repo.root)
        cache_path = history._cache_path(self.repo.root)
        self.assertTrue(cache_path.is_file())
        # This throwaway repo's .gitignore (it has none) does not ignore
        # .cache/, so the cache must land outside the repo entirely.
        self.assertFalse(str(cache_path).startswith(str(self.repo.root)))

    def test_cli_table(self):
        r = subprocess.run([sys.executable, str(TRACKER), "history", "--project", str(self.repo.root)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(self.day_a.isoformat(), r.stdout)
        self.assertIn(self.today.isoformat(), r.stdout)

    def test_cli_json(self):
        r = subprocess.run([sys.executable, str(TRACKER), "history", "--project", str(self.repo.root), "--json"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data[0]["date"], self.day_a.isoformat())


class TestHistorySvg(unittest.TestCase):
    def test_two_charts_no_external_urls(self):
        rows = [
            {"date": "2026-09-01", "tickets_total": 2, "tickets_done": 1, "completion_pct": 50.0,
             "added": 2, "closed": 0, "added_ids": 2, "closed_ids": 0, "by_proposal": {}},
            {"date": "2026-09-02", "tickets_total": 3, "tickets_done": 2, "completion_pct": 66.7,
             "added": 1, "closed": 1, "added_ids": 1, "closed_ids": 1, "by_proposal": {}},
        ]
        out = history.svg(rows)
        self.assertEqual(out.count("<svg"), 2)
        self.assertEqual(out.count("</svg>"), 2)
        # No fetched resource: no <script>, and the only URL allowed is the
        # SVG xmlns declaration itself (a namespace, not a network fetch).
        self.assertNotIn("<script", out)
        self.assertNotIn("href=", out)
        self.assertNotIn('src="http', out)
        non_xmlns_urls = [line for line in out.splitlines()
                          if ("http://" in line or "https://" in line) and "xmlns=" not in line]
        self.assertEqual(non_xmlns_urls, [])
        self.assertIn("var(--tracker-line-total", out)
        self.assertIn("var(--tracker-line-completion", out)

    def test_empty_series_still_renders_two_empty_charts(self):
        out = history.svg([])
        self.assertEqual(out.count("<svg"), 2)
        self.assertNotIn("polyline", out)


def _rows_for_chart_content():
    """Five days of a spread-out series, so the axes have real ticks to
    check and the first/last dates differ (proposal 30, P-08 round 2 --
    the sponsor's "17%, I don't have the formula in my mind" complaint,
    repeated by a scaleless line)."""
    dates = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-05"]
    totals = [2, 3, 4, 5, 6]
    dones = [1, 1, 2, 3, 5]
    completion = [10.0, 20.0, 40.0, 70.0, 90.0]
    return [
        {"date": d, "tickets_total": t, "tickets_done": dn, "completion_pct": c,
         "added": 0, "closed": 0, "added_ids": 0, "closed_ids": 0, "by_proposal": {}}
        for d, t, dn, c in zip(dates, totals, dones, completion)
    ]


class TestHistorySvgContent(unittest.TestCase):
    """P-08 round 2 (the coordinator's own review of the first chart
    render): a labelled y-axis, a labelled x-axis, a legend, an
    end-of-line value per series, a visible title, and a responsive
    (width=100% + viewBox) svg -- on both the counts chart and the
    completion chart."""

    def setUp(self):
        self.rows = _rows_for_chart_content()
        self.out = history.svg(self.rows)
        self.counts, self.pct = self.out.split("</svg>", 1)

    def test_responsive_viewbox(self):
        self.assertEqual(self.out.count('width="100%"'), 2)
        self.assertEqual(self.out.count("viewBox="), 2)

    def test_visible_titles(self):
        self.assertIn(">Tickets over time<", self.out)
        self.assertIn(">Completion over time<", self.out)

    def test_y_axis_ticks_are_values_the_line_actually_reaches(self):
        # The counts chart spans both `total` and `done`: 1..6.
        for tv in history._nice_ticks(1, 6, 4):
            self.assertIn(f">{history._fmt_count(tv)}<", self.counts)
        # The completion chart spans its own data: 10..90, never a fixed
        # 0-100 the line rarely reaches.
        for tv in history._nice_ticks(10.0, 90.0, 4):
            self.assertIn(f">{history._fmt_percent(tv)}<", self.pct)

    def test_x_axis_shows_first_and_last_date_not_iso(self):
        self.assertIn(">1 Sep<", self.counts)
        self.assertIn(">5 Sep<", self.counts)
        self.assertNotIn("2026-09-01", self.out)
        self.assertNotIn("2026-09-05", self.out)

    def test_legend_has_an_entry_per_series(self):
        self.assertIn('data-legend="total"', self.counts)
        self.assertIn('data-legend="done"', self.counts)
        self.assertIn('data-legend="completion"', self.pct)

    def test_end_of_line_labels_carry_the_final_value(self):
        self.assertIn('data-endlabel="total">6<', self.counts)
        self.assertIn('data-endlabel="done">5<', self.counts)
        self.assertIn('data-endlabel="completion">90%<', self.pct)

    def test_gridlines_and_axis_text_use_theme_tokens(self):
        self.assertIn("var(--tracker-chart-axis", self.out)
        self.assertIn("var(--tracker-chart-grid", self.out)
        self.assertIn("var(--tracker-chart-title", self.out)

    def test_charts_stay_separate(self):
        self.assertEqual(self.out.count("<svg"), 2)

    def test_no_external_urls_or_script_still_holds(self):
        self.assertNotIn("<script", self.out)
        self.assertNotIn("href=", self.out)
        self.assertNotIn('src="http', self.out)
        non_xmlns_urls = [line for line in self.out.splitlines()
                          if ("http://" in line or "https://" in line) and "xmlns=" not in line]
        self.assertEqual(non_xmlns_urls, [])


if __name__ == "__main__":
    unittest.main()
