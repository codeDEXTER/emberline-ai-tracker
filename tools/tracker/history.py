"""Progress over time, computed from the ledgers' own git history -- no AI
updates (proposal 30, P-07).

The sponsor's words: "there should be a tracker which should plot a graph
over time of how many tickets are getting finished, how many tickets are
added ... This should not be manually updated by AI. So AI should be just
adding one log file or whatever and everything else should be handled by
backend scripts."

So this module never writes anything: it replays the ledgers as git already
recorded them. `series()` walks every calendar day from the first commit
that touched a ledger to today, and for a day with commits reads every
ledger JSON as of that day's *last* commit (`git show <sha>:<path>`) --
days without a commit carry the previous day's snapshot forward rather than
showing a false dip to zero.

A ticket is an item, or -- proposal 30 -- any of its lettered parts, at any
depth (a part with its own `parts` counts itself AND its parts; a nested
part such as W-10.A.1 counts too). `tools.tracker.parts` does not yet walk
nested parts for `completion()`, so per-item completion here is exactly
`parts.completion(item)`, unchanged: once that module learns to recurse,
this one follows without edits.

Two counters beyond the totals-per-day diff: `added_ids`/`closed_ids` count
by comparing the day's ticket-id set against the previous day's, so a
ticket added and closed on the same day is not invisible to a plain
before/after total (which would show 0 net change).

Dates are calendar days in a fixed Europe offset (CET, UTC+1, no DST) --
deliberately not the system zoneinfo database, so the same commit always
lands on the same day on every machine this runs on, and the per-commit
cache (keyed only by sha) never needs to be invalidated because someone's
laptop crossed a DST boundary differently.

Cache: `.cache/tracker-history.json` under the project root, if the
project's own .gitignore already ignores `.cache` -- else a file under the
system temp dir, keyed by the repo's absolute path, so nothing lands in the
repo uninvited. Keyed by commit sha; a rerun only computes new shas.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.tracker import parts as P

# A fixed Europe offset, not a zoneinfo lookup -- see the module docstring.
TZ = datetime.timezone(datetime.timedelta(hours=1), "CET")

LEDGER_GLOB = "[0-9][0-9]*-*.json"


# ---------------------------------------------------------------- git -----

def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def _repo_root(project: Path) -> Path:
    return Path(_git(project, "rev-parse", "--show-toplevel").strip())


def _ledger_commits(repo: Path) -> list[tuple[str, datetime.date]]:
    """(sha, Europe-local calendar date), oldest first, for every commit that
    touched a ledger file directly under docs/proposals."""
    out = _git(repo, "log", "--format=%H%x1f%cI", "--reverse", "--", f"docs/proposals/{LEDGER_GLOB}")
    commits = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        sha, iso = line.split("\x1f")
        when = datetime.datetime.fromisoformat(iso).astimezone(TZ)
        commits.append((sha, when.date()))
    return commits


def _ledger_paths_at(repo: Path, sha: str) -> list[str]:
    """Ledger file names (not full paths) directly under docs/proposals at
    `sha`, matching the same NN-*.json shape `ledger.find` uses -- a data
    file that happens to share the shape is filtered out below, once its
    contents are read, exactly as `ledger.find` does for the working tree."""
    try:
        out = _git(repo, "ls-tree", "--name-only", f"{sha}:docs/proposals")
    except RuntimeError:
        return []  # docs/proposals did not exist yet at this commit
    return [name for name in (line.strip() for line in out.splitlines() if line.strip())
            if fnmatch.fnmatch(name, LEDGER_GLOB)]


# ------------------------------------------------------------ tickets -----

def _tickets(node: dict):
    """Yield (id, done) for `node` and, recursively, every dict in its
    `parts` list at any depth. A part with its own `parts` is itself a
    ticket AND its parts are tickets (proposal 30): W-10 with parts W-10.A,
    W-10.B, and W-10.A itself split further into W-10.A.1, W-10.A.2, counts
    five tickets in total."""
    yield node.get("id"), node.get("status") == "done"
    for part in node.get("parts") or []:
        if isinstance(part, dict):
            yield from _tickets(part)


def _snapshot_at(repo: Path, sha: str) -> list[dict]:
    """Every item across every ledger at `sha`, as
    {"proposal": N, "completion": 0-100, "tickets": [[id, done], ...]}.
    One `git show` per ledger file found at that commit."""
    items = []
    for name in _ledger_paths_at(repo, sha):
        path = f"docs/proposals/{name}"
        try:
            text = _git(repo, "show", f"{sha}:{path}")
            data = json.loads(text)
        except (RuntimeError, ValueError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            continue
        proposal = data.get("proposal")
        for item in data["items"]:
            if not isinstance(item, dict):
                continue
            items.append({
                "proposal": proposal,
                "completion": P.completion(item),
                "tickets": [[tid, done] for tid, done in _tickets(item)],
            })
    return items


def _summarize(items: list[dict]) -> dict:
    """items -> {tickets_total, tickets_done, completion_pct, by_proposal,
    ids_all, ids_done}. `ids_all`/`ids_done` are internal -- callers use them
    to diff against the previous day and strip them before the row is
    returned."""
    total = 0
    done = 0
    comp_sum = 0.0
    ids_all: set = set()
    ids_done: set = set()
    by_proposal: dict = {}
    for it in items:
        comp_sum += it["completion"]
        prop = str(it["proposal"])
        agg = by_proposal.setdefault(prop, {"tickets_total": 0, "tickets_done": 0, "_comp": []})
        agg["_comp"].append(it["completion"])
        for tid, tdone in it["tickets"]:
            total += 1
            agg["tickets_total"] += 1
            if tid is not None:
                ids_all.add(tid)
            if tdone:
                done += 1
                agg["tickets_done"] += 1
                if tid is not None:
                    ids_done.add(tid)
    for agg in by_proposal.values():
        comps = agg.pop("_comp")
        agg["completion_pct"] = round(sum(comps) / len(comps), 1) if comps else 0.0
    completion_pct = round(comp_sum / len(items), 1) if items else 0.0
    return {
        "tickets_total": total, "tickets_done": done, "completion_pct": completion_pct,
        "by_proposal": by_proposal, "ids_all": ids_all, "ids_done": ids_done,
    }


# -------------------------------------------------------------- cache -----

def _gitignores(root: Path, rel: str) -> bool:
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return False
    for line in gitignore.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped in (rel, rel.rstrip("/"), rel.rstrip("/") + "/"):
            return True
    return False


def _cache_path(project: Path) -> Path:
    root = _repo_root(project)
    if _gitignores(root, ".cache/"):
        return root / ".cache" / "tracker-history.json"
    key = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "common-rules-tracker-history" / f"{key}.json"


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, sort_keys=True))
    tmp.replace(path)


def _snapshot_for(repo: Path, sha: str, cache: dict) -> list[dict]:
    cached = cache.get(sha)
    if cached is not None:
        return cached
    snap = _snapshot_at(repo, sha)
    cache[sha] = snap
    return snap


# ------------------------------------------------------------- series -----

def _as_date(value) -> datetime.date | None:
    if value is None:
        return None
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(value)


def series(project, since=None) -> list[dict]:
    """One row per calendar day from the first commit that touched a ledger
    to today, carrying forward days without a ledger-touching commit."""
    project = Path(project)
    repo = _repo_root(project)
    commits = _ledger_commits(repo)
    if not commits:
        return []

    last_sha_of_day: dict[datetime.date, str] = {}
    for sha, day in commits:
        last_sha_of_day[day] = sha  # ascending order -> last write wins

    cache_path = _cache_path(project)
    cache = _load_cache(cache_path)
    dirty = False

    start_day = commits[0][1]
    today = datetime.datetime.now(TZ).date()

    rows: list[dict] = []
    prev_ids_all: set = set()
    prev_ids_done: set = set()
    prev_total = 0
    last_summary: dict | None = None

    day = start_day
    while day <= today:
        sha = last_sha_of_day.get(day)
        if sha is not None:
            if sha not in cache:
                dirty = True
            items = _snapshot_for(repo, sha, cache)
            summary = _summarize(items)
            ids_all, ids_done = summary.pop("ids_all"), summary.pop("ids_done")
            added_ids = len(ids_all - prev_ids_all)
            closed_ids = len(ids_done - prev_ids_done)
            row = {
                "date": day.isoformat(),
                "tickets_total": summary["tickets_total"],
                "tickets_done": summary["tickets_done"],
                "added": max(0, summary["tickets_total"] - prev_total),
                "closed": closed_ids,
                "added_ids": added_ids,
                "closed_ids": closed_ids,
                "completion_pct": summary["completion_pct"],
                "by_proposal": summary["by_proposal"],
            }
            prev_ids_all, prev_ids_done = ids_all, ids_done
            prev_total = summary["tickets_total"]
            last_summary = row
        else:
            assert last_summary is not None  # start_day always has a commit
            row = dict(last_summary)
            row["date"] = day.isoformat()
            row["added"] = row["closed"] = row["added_ids"] = row["closed_ids"] = 0
        rows.append(row)
        day += datetime.timedelta(days=1)

    if dirty:
        _save_cache(cache_path, cache)

    since_date = _as_date(since)
    if since_date is not None:
        rows = [r for r in rows if datetime.date.fromisoformat(r["date"]) >= since_date]
    return rows


# ---------------------------------------------------------------- svg -----

def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _polyline(values: list[float], width: int, height: int, pad: int, y_range=None) -> str:
    if not values:
        return ""
    lo, hi = y_range if y_range is not None else (min(values), max(values))
    if hi == lo:
        hi = lo + 1
    n = len(values)
    span = max(n - 1, 1)

    def x(i):
        return pad + (width - 2 * pad) * (i / span)

    def y(v):
        return height - pad - (height - 2 * pad) * ((v - lo) / (hi - lo))

    return " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))


def _line_chart(width: int, height: int, series_list, title: str, y_range=None) -> str:
    """One inline <svg> line chart with one polyline per (label, values,
    color) in `series_list`. Colors are CSS custom properties with a
    fallback, so the chart follows whatever page it is embedded in, in
    light or dark mode, with no external stylesheet or script."""
    pad = 24
    parts_svg = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{_esc(title)}" '
        f'class="tracker-history-chart">',
        f'<title>{_esc(title)}</title>',
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="var(--tracker-chart-bg, transparent)"/>',
        f'<line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" '
        f'stroke="var(--tracker-chart-axis, currentColor)" stroke-opacity="0.35" stroke-width="1"/>',
    ]
    for label, values, color in series_list:
        points = _polyline(values, width, height, pad, y_range=y_range)
        if points:
            parts_svg.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" '
                f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round" '
                f'data-series="{_esc(label)}"/>')
    parts_svg.append("</svg>")
    return "\n".join(parts_svg)


def svg(series_rows: list[dict], width: int = 640, height: int = 200) -> str:
    """Two small inline SVG line charts from `series()`'s rows: ticket
    counts (total vs done) and completion percent -- kept as two charts
    rather than one dual-scale chart, since a shared axis for counts and a
    percent misleads at a glance. No external libraries or URLs."""
    totals = [r["tickets_total"] for r in series_rows]
    dones = [r["tickets_done"] for r in series_rows]
    completion = [r["completion_pct"] for r in series_rows]
    counts = _line_chart(
        width, height,
        [("total", totals, "var(--tracker-line-total, #4C6FFF)"),
         ("done", dones, "var(--tracker-line-done, #2FB170)")],
        title="Tickets over time (total vs. done)")
    pct = _line_chart(
        width, height,
        [("completion", completion, "var(--tracker-line-completion, #B15EFF)")],
        title="Completion over time (%)", y_range=(0, 100))
    return counts + "\n" + pct


# ---------------------------------------------------------------- CLI -----

def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker history", add_help=True)
    ap.add_argument("--project", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--since")
    args = ap.parse_args(argv)

    try:
        rows = series(Path(args.project), since=args.since)
    except RuntimeError as exc:
        print(f"tracker history: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    if not rows:
        print("tracker history: no ledger commits found")
        return 0

    print(f"{'date':10}  {'total':>5}  {'done':>5}  {'added':>5}  {'closed':>6}  {'compl%':>7}")
    for r in rows:
        print(f"{r['date']:10}  {r['tickets_total']:5d}  {r['tickets_done']:5d}  "
              f"{r['added']:5d}  {r['closed']:6d}  {r['completion_pct']:7.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
