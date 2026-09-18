"""tracker board -- a project's one tracker page (proposal 22, T-01).

  tracker board [--project DIR] [--check] [--out PATH] [--name NAME]

The sponsor asked (proposal 22, A-01) for "per project, there should be one
tracker", readable at a glance: filters across the top and the work shown as
blocks. So this renders every ledger in DIR/docs/proposals into one page,

  docs/proposals/tracker/index.html

beside the per-proposal pages `tracker render` writes, which it never
touches. The page has, top to bottom: the project's totals; one block per
proposal, which filters the page to that proposal when clicked; a filter bar
(search, status, owner, tier, Board or List); open asks and requests; the
board, one column per status; the list; and the answered asks.

Every number comes from tools/tracker/ledger.py, never recomputed here. The
filters run in the page's own inline script, with no external script, and
the page is readable without it: every block is in the markup.

Like `tracker render`, the output is deterministic (no generation clock)
and carries each ledger's digest. `--check` compares those digests, so
editing, adding or removing a ledger makes the page stale.

Exit codes: 0 rendered / fresh, 1 stale or an invalid ledger, 2 unreadable
or no ledgers.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from tools.tracker import cluster as CLUSTER
from tools.tracker import history as HIST
from tools.tracker import lanes as LANES
from tools.tracker import ledger as L
from tools.tracker import parts as PARTS
from tools.tracker import render as R
from tools.tracker import rescore as RS

OUT_NAME = "index.html"
PUBLISHED_NAME = "index.published.json"
# Attention order: what is moving, what is elsewhere waiting (C-06), what is
# stuck, what is next, what is done.
COLUMNS = ("in progress", "in review", "in testing", "blocked", "not started", "done")
LABEL = {"in progress": "In progress", "in review": "In review", "in testing": "In testing",
         "blocked": "Blocked", "not started": "Not started", "done": "Done"}


def e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def b(value) -> str:
    """Escaped free text inside <bdi>, for text that sits inline beside other
    text: a bidi override in a ledger value then reorders only itself (round 2)."""
    return f"<bdi>{e(value)}</bdi>"


def slug(status: str) -> str:
    return "s-" + str(status).replace(" ", "-")


def when(at) -> str:
    return str(at or "")[:16].replace("T", " ")


def default_out(project: Path) -> Path:
    return project / "docs" / "proposals" / "tracker" / OUT_NAME


def project_name(project: Path) -> str:
    """The name a reader knows the project by, the same from every worktree:
    the main checkout's folder when the project is a repository's top, else
    the project's own folder (an app kept in a subdirectory of its repo)."""
    def git(*args):
        try:
            r = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True, timeout=10)
        except (subprocess.SubprocessError, OSError):
            return None
        return r.stdout.strip() if r.returncode == 0 else None
    top = git("rev-parse", "--show-toplevel")
    if top and Path(top).resolve() == project.resolve():
        common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
        if common and Path(common).name == ".git":
            return Path(common).parent.name
    return project.resolve().name


def digests(paths: list[Path]) -> str:
    """Each ledger's name and sha256, as JSON in file-name order. Round 1: the
    order is fixed here, not by the caller (the render sorted by proposal and
    --check by name, so 99 and 100 read stale straight after a render), and a
    JSON string cannot be forged by a file name holding ; or =."""
    return json.dumps([[p.name, hashlib.sha256(p.read_bytes()).hexdigest()]
                       for p in sorted(paths, key=lambda p: p.name)], ensure_ascii=True, separators=(",", ":"))


def page_digests(page: Path) -> str | None:
    """The ledger digests the page itself carries, or None when there is no
    page or it is not one this tool wrote (proposal 22, T-03). `tracker
    published --project` records exactly this string, so the record says which
    ledgers the published page showed, and nothing re-derives the markup."""
    try:
        text = Path(page).read_text(errors="replace")
    except OSError:
        return None
    m = re.search(r'<meta name="ledger-digests" content="([^"]*)">', text)
    return html.unescape(m.group(1)) if m else None


def freshness(paths: list[Path], page: Path) -> str:
    if not page.exists():
        return "missing"
    carried = page_digests(page)
    return "ok" if carried is not None and carried == digests(paths) else "stale"


def published_path(project) -> Path:
    """The project page's publish record, beside the page (proposal 22, T-03)."""
    return default_out(Path(project)).with_name(PUBLISHED_NAME)


def ledger_paths(project: Path) -> list[Path]:
    """The ledgers the project page is rendered from, in file-name order."""
    return sorted(L.find(project), key=lambda p: p.name)


def project_page_state(project: Path) -> tuple[str, Path]:
    """("none" | "ok" | "missing" | "stale", the project page). "none": the
    project has no ledger, so it has no page to check (proposal 22, T-02 --
    one answer for bin/warmup, bin/conformance and bin/new-proposal)."""
    page = default_out(Path(project))
    paths = ledger_paths(Path(project))
    if not paths:
        return "none", page
    return freshness(paths, page), page


# ---------------------------------------------------------------------------
# pieces

def mini_bar(counts: dict) -> str:
    total = sum(counts.values())
    if not total:
        return '<span class="bar"><span class="seg s-empty" style="width:100%"></span></span>'
    segs = "".join(f'<span class="seg {slug(s)}" style="width:{counts[s] * 100 / total:.2f}%"></span>'
                   for s in ("done", "in progress", "in review", "in testing", "blocked", "not started") if counts[s])
    return f'<span class="bar">{segs}</span>'


def search_text(*parts) -> str:
    """One lowercase line the page's search box matches. Round 1: the card and
    the list row carry the same string, so board and list find the same items."""
    return re.sub(r"\s+", " ", " ".join(str(p) for p in parts if p not in (None, ""))).strip().lower()


def item_search(item: dict, number) -> str:
    log = [f'{x.get("event") or ""} {x.get("by") or ""} {x.get("evidence") or ""}'
           for x in (item.get("log") or []) if isinstance(x, dict)]
    return search_text(item.get("id"), f"p{number}", item.get("title"), item.get("status"), item.get("owner"),
                       item.get("tier"), item.get("tag") or item.get("cx"),
                       f'#{item["issue"]}' if item.get("issue") else None, *log)


def log_entries(item: dict) -> list[dict]:
    """The item's log entries that are objects. ledger.validate lets a string
    through, and the page must not crash on one (round 2)."""
    return [x for x in (item.get("log") or []) if isinstance(x, dict)]


def last_entry(item: dict) -> dict:
    log = log_entries(item)
    return log[-1] if log else {}


def item_card(item: dict, number, repo) -> str:
    status = item.get("status", "")
    last = last_entry(item)
    deps = L.as_list(item.get("depends"))
    owner = item.get("owner") or ""
    meta = [f'<span class="tag">{e(item.get("tag") or item.get("cx"))}</span>']
    if deps:
        meta.append(f'<span class="dep">after {e(" ".join(deps))}</span>')
    if owner:
        meta.append(f'<span class="owner">{e(owner)}</span>')
    if item.get("issue"):
        meta.append(f'<span class="issue">{R.issue_cell(item.get("issue"), repo)}</span>')
    reason = (f'<p class="why">{e(last.get("evidence"))}</p>'
              if status == "blocked" and last.get("evidence") else "")
    lastline = (f'<p class="last"><span class="event">{b(last.get("event"))}</span> '
                f'<time>{e(when(last.get("at")))}</time></p>' if last else '<p class="last dim">no entries yet</p>')
    log = log_entries(item)
    entries = "".join(
        f'<li><time>{e(when(x.get("at")))}</time> <b>{b(x.get("event"))}</b> <span class="by">{b(x.get("by"))}</span>'
        f'{"<p>" + e(x.get("evidence")) + "</p>" if x.get("evidence") else ""}</li>'
        for x in log)
    details = (f'<details><summary>Log · {len(log)} {"entry" if len(log) == 1 else "entries"}</summary>'
               f'<ol class="log">{entries}</ol></details>' if log else "")
    group = PARTS.group(item)
    hidden = ' hidden' if group == "done" else ""
    explicit_parts = PARTS.parts(item)
    pct_line = ""
    if explicit_parts:
        nxt = PARTS.next_part(item)
        next_text = f'next: {e(nxt.get("id"))} · {e(nxt.get("title"))}' if nxt else "all parts done"
        parts_rows = "".join(part_sub_row(p) for p in explicit_parts)
        pct_line = (f'<p class="pct">{PARTS.completion(item)}% <span class="fbar">{feature_bar(item)}</span> '
                    f'<span class="next dim">{next_text}</span></p>'
                    f'<details class="parts-details"><summary>Parts · {len(explicit_parts)}</summary>'
                    f'<div class="fparts">{parts_rows}</div></details>')
    return (f'<article class="card" data-item data-id="{e(item.get("id"))}" data-proposal="{e(number)}" '
            f'data-status="{e(status)}" data-owner="{e(owner)}" data-tier="{e(item.get("tier") or "")}" '
            f'data-group="{e(group)}"{hidden} '
            f'data-search="{e(item_search(item, number))}">'
            f'<header><span class="id">{e(item.get("id"))}</span><span class="pnum">P{e(number)}</span></header>'
            f'<h3>{e(item.get("title"))}</h3>{pct_line}'
            f'<p class="meta">{"".join(meta)}</p>{reason}{lastline}{details}</article>')


def item_row(item: dict, number, repo) -> str:
    status = item.get("status", "")
    last = last_entry(item)
    owner = item.get("owner") or ""
    # No data-search here (round 2): the page's script gives each row its
    # card's string, so the text is stored once and the views cannot drift.
    group = PARTS.group(item)
    hidden = ' hidden' if group == "done" else ""
    return (f'<tr class="row" data-item data-id="{e(item.get("id"))}" data-proposal="{e(number)}" '
            f'data-status="{e(status)}" data-owner="{e(owner)}" data-tier="{e(item.get("tier") or "")}" '
            f'data-group="{e(group)}"{hidden}>'
            f'<td class="id">{e(item.get("id"))}</td><td class="pnum">P{e(number)}</td>'
            f'<td>{e(item.get("title"))}</td>'
            f'<td><span class="pill {slug(status)}">{e(status)}</span></td>'
            f'<td class="mono">{e(owner) or "—"}</td>'
            f'<td class="mono">{e(item.get("tag") or item.get("cx"))}</td>'
            f'<td class="mono">{R.issue_cell(item.get("issue"), repo)}</td>'
            f'<td class="mono">{b(last.get("event") or "—")} <span class="dim">{e(when(last.get("at")))}</span></td></tr>')


def ask_row(ask: dict, number) -> str:
    owner = ask.get("owner") or ""
    became = f' <span class="dim">→ {b(ask.get("became"))}</span>' if ask.get("became") else ""
    search = search_text(ask.get("id"), f"p{number}", ask.get("kind"), ask.get("quote"), owner, ask.get("became"))
    return (f'<li class="ask" data-ask="{e(ask.get("id"))}" data-proposal="{e(number)}" '
            f'data-owner="{e(owner)}" data-search="{e(search)}">'
            f'<span class="id">{e(ask.get("id"))}</span><span class="pnum">P{e(number)}</span>'
            f'<span class="kind">{e(ask.get("kind"))}</span>'
            f'<q>{e(ask.get("quote"))}</q>'
            f'<span class="asked">{e(when(ask.get("at")))}{" · owner " + b(owner) if owner else ""}{became}</span></li>')


def request_row(req: dict, number) -> str:
    unblocks = L.as_list(req.get("unblocks"))
    search = search_text(req.get("id"), f"p{number}", "request", req.get("from"), req.get("to"),
                         req.get("state"), *unblocks)
    return (f'<li class="ask" data-request="{e(req.get("id"))}" data-proposal="{e(number)}" '
            f'data-owner="" data-search="{e(search)}">'
            f'<span class="id">{e(req.get("id"))}</span><span class="pnum">P{e(number)}</span>'
            f'<span class="kind">request</span>'
            f'<q>{e(req.get("from"))} → {e(req.get("to"))}</q>'
            f'<span class="asked">{e(req.get("state"))}'
            f'{" · unblocks " + e(" ".join(unblocks)) if unblocks else ""}</span></li>')


LANE_ORDER = ("Now", "Daily", "Weekly", "When touched")


def lane_state(ledgers: list[tuple[Path, dict]], project, today: datetime.date | None = None) -> dict:
    """Every ledger's items in one shared `tracker lanes` run (proposal 26,
    C-02, unchanged), each sized row also carrying whether it is overdue --
    `next_check` in the past (proposal 26, C-04) -- read from the item's own
    ledger row, since lanes.lanes()'s own rows never carry that field.
    `today` defaults to the real date; a caller (a test) can pin it."""
    combined: list[dict] = []
    by_id: dict[str, dict] = {}
    for _, data in ledgers:
        for it in L.items(data):
            combined.append(it)
            if it.get("id"):
                by_id[it["id"]] = it
    result = LANES.lanes(combined, project)
    today = today or datetime.date.today()
    for row in result["items"]:
        it = by_id.get(row["id"])
        row["overdue"] = bool(it and RS.overdue(it, today))
        row["next_check"] = (it or {}).get("next_check")
    return result


def cluster_state(ledgers: list[tuple[Path, dict]]) -> dict:
    """Every ledger's not-yet-taken items and findings, file-overlap clustered
    (proposal 25, Z-06)."""
    rows: list[dict] = []
    for _, data in ledgers:
        rows.extend(CLUSTER.not_taken_rows(data))
    return CLUSTER.file_overlap_clusters(rows)


def lane_slug(lane: str) -> str:
    return "lane-" + lane.lower().replace(" ", "-")


def lane_row(r: dict) -> str:
    overdue = r.get("overdue")
    badge = f' <span class="badge-overdue">overdue since {e(r.get("next_check"))}</span>' if overdue else ""
    alone = ' <span class="badge-alone">alone</span>' if r.get("alone") else ""
    return (f'<li class="lane-item{" overdue" if overdue else ""}" data-id="{e(r["id"])}">'
            f'<span class="id">{e(r["id"])}</span> {b(r["title"])} '
            f'<span class="share dim">{r["share"] * 100:.1f}% · cum {r["cumulative"] * 100:.1f}%'
            f'{" · risk " + e(r["risk"]) if r.get("risk") is not None else ""}</span>{alone}{badge}</li>')


def lanes_block(result: dict) -> str:
    """Lane groups in order, with the 80% cut line marked once, between the
    last `Now` row and the first tail row (proposal 26, C-04)."""
    groups: dict[str, list[dict]] = {}
    for r in result["items"]:
        groups.setdefault(r["lane"], []).append(r)
    parts, cut_marked = [], False
    for lane in LANE_ORDER:
        rows = groups.get(lane, [])
        if lane != "Now" and not cut_marked:
            parts.append('<div class="cut-line" role="separator" aria-label="80% cut">'
                         '<span>80% cut -- tail lanes below, re-checked on their own schedule</span></div>')
            cut_marked = True
        if not rows:
            continue
        parts.append(f'<section class="lane {lane_slug(lane)}"><h3>{e(lane)} '
                     f'<span class="n">{len(rows)}</span></h3><ul>{"".join(lane_row(r) for r in rows)}</ul>'
                     f'</section>')
    if result["unsized"]:
        rows = "".join(f'<li class="lane-item" data-id="{e(u["id"])}"><span class="id">{e(u["id"])}</span> '
                       f'{b(u["title"])}</li>' for u in result["unsized"])
        parts.append(f'<section class="lane lane-unsized"><h3>Unsized <span class="n">{len(result["unsized"])}</span>'
                     f'</h3><ul>{rows}</ul></section>')
    return "".join(parts)


def cluster_member_row(m: dict) -> str:
    return f'<li><span class="id">{e(m["id"])}</span> {b(m["title"])}</li>'


def clusters_section(c: dict) -> str:
    if not c["clusters"] and not c["singles"]:
        return ""
    cards = "".join(
        f'<article class="cluster"><h3>{e(g["id"])} <span class="n">{len(g["items"])}</span></h3>'
        f'<p class="files">{", ".join(e(f) for f in g["files"])}</p>'
        f'<ul>{"".join(cluster_member_row(m) for m in g["items"])}</ul>'
        f'</article>'
        for g in c["clusters"])
    singles = "".join(cluster_member_row(s) for s in c["singles"])
    singles_block = (f'<details class="cluster-singles"><summary>Not clustered · {len(c["singles"])}</summary>'
                     f'<ul>{singles}</ul></details>' if c["singles"] else "")
    return (f'<section class="clusters" id="clusters"><h2>Not taken, clustered by files touched '
           f'<span class="n">{len(c["clusters"])}</span></h2><div class="cluster-cards">{cards}</div>'
           f'{singles_block}</section>')


def lanes_section(result: dict) -> str:
    """D5: the old share/cumulative Lanes view, kept as a folded "advanced"
    section -- a closed <details>, not deleted (the sponsor's ask replaces
    what he reads, not the routing math proposal 25/26 still use)."""
    if not result["items"] and not result["unsized"]:
        return ""
    return (f'<details class="lanes" id="lanes"><summary>Advanced · Lanes '
           f'<span class="n">{len(result["items"])}</span></summary>'
           f'{lanes_block(result)}</details>')


# ---------------------------------------------------------------------------
# proposal 30: the completion overview (P-03). Every rule -- completion,
# grouping, what counts as waiting -- comes from tools/tracker/parts.py;
# nothing here recomputes them.

GROUP_LABEL = {"finish now": "Finish now", "back burner": "Back burner", "waiting": "Waiting", "done": "Done"}
GROUP_RULE = {
    "finish now": "under 80% done, or an open part is high risk",
    "back burner": "80% or more done, the rest is low or medium risk",
    "waiting": "owned by another project, or waiting for a date",
}
OVERVIEW_GROUPS = ("finish now", "back burner", "waiting")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def short_date(value: str) -> str:
    d = datetime.date.fromisoformat(value)
    return f"{d.day} {_MONTHS[d.month - 1]}"


def display_parts(item: dict) -> list[dict]:
    """Every part to show in a feature's sub-rows: the item's real parts, or
    one implicit part standing for the whole item (P-01: an item without
    parts is one part worth 100, carrying the item's own status)."""
    ps = PARTS.parts(item)
    if ps:
        return ps
    part = {"id": item.get("id"), "title": item.get("title"), "share": 100,
            "status": item.get("status") or "not started"}
    if item.get("owner"):
        part["owner"] = item["owner"]
    return [part]


def part_pill(p: dict) -> tuple[str, str, str | None]:
    """(css class, label, title attribute) for one part's status pill."""
    status = p.get("status")
    if status == "done":
        return "done", "done", None
    owner = p.get("owner")
    if isinstance(owner, str) and owner.startswith("session:"):
        return "other", "other project", None
    wait = p.get("waiting_until")
    if isinstance(wait, str):
        try:
            datetime.date.fromisoformat(wait)
        except ValueError:
            pass
        else:
            return "waiting", short_date(wait), None
    if p.get("risk") == "high":
        return "risk", "risk high", p.get("risk_reason")
    return slug(status), str(status or ""), None


def part_bar_class(p: dict) -> str:
    """done green / in progress blue / waiting amber / not started empty --
    the four buckets the segmented bar shows, widths as the part's share."""
    if p.get("status") == "done":
        return "seg-done"
    if PARTS.is_waiting(p):
        return "seg-waiting"
    if p.get("status") == "not started":
        return "seg-empty"
    return "seg-running"


def feature_bar(item: dict) -> str:
    return "".join(f'<span class="{part_bar_class(p)}" style="width:{p.get("share", 0)}%"></span>'
                   for p in display_parts(item))


def part_sub_row(p: dict) -> str:
    cls, label, title = part_pill(p)
    title_attr = f' title="{e(title)}"' if title else ""
    muted = " muted" if p.get("status") == "done" else ""
    return (f'<div class="prow{muted}"><span class="pid">{e(p.get("id"))}</span>'
            f'<span class="ptitle" title="{e(p.get("title"))}">{e(p.get("title"))}</span>'
            f'<span class="pshare">{p.get("share", 0)}%</span>'
            f'<span class="pill p-{cls}"{title_attr}>{e(label)}</span></div>')


def feature_overview_row(item: dict, number) -> str:
    pct = PARTS.completion(item)
    prows = "".join(part_sub_row(p) for p in display_parts(item))
    return (f'<details class="frow" data-feature data-id="{e(item.get("id"))}" data-proposal="{e(number)}" '
            f'data-group="{e(PARTS.group(item))}" data-owner="{e(item.get("owner") or "")}">'
            f'<summary class="fhead"><span class="fid">{e(item.get("id"))}</span>'
            f'<span class="ftitle" title="{e(item.get("title"))}">{e(item.get("title"))}</span>'
            f'<span class="fpct">{pct}%</span>'
            f'<span class="fbar">{feature_bar(item)}</span></summary>'
            f'<div class="fparts">{prows}</div></details>')


def completion_tiles(entries) -> str:
    total = len(entries)
    counts = {"finish now": 0, "back burner": 0, "waiting": 0, "done": 0}
    for _, item, _, _ in entries:
        counts[PARTS.group(item)] += 1
    tiles = [
        ("done", f'{counts["done"]} of {total}', "features finished"),
        ("finish", str(counts["finish now"]), "finish now"),
        ("back", str(counts["back burner"]), "back burner"),
        ("wait", str(counts["waiting"]), "waiting"),
    ]
    return "".join(f'<div class="tile t-{cls}"><span class="n">{e(n)}</span><span class="l">{e(label)}</span></div>'
                   for cls, n, label in tiles)


def completion_groups(entries) -> str:
    buckets: dict[str, list[tuple[dict, object]]] = {g: [] for g in OVERVIEW_GROUPS}
    for _, item, number, _ in entries:
        g = PARTS.group(item)
        if g in buckets:
            buckets[g].append((item, number))
    sections = []
    for g in OVERVIEW_GROUPS:
        rows = buckets[g]
        body = ("".join(feature_overview_row(item, number) for item, number in rows) if rows
                else '<p class="empty-note">nothing here right now.</p>')
        sections.append(f'<section class="cgroup" data-group="{e(g)}">'
                        f'<h3>{e(GROUP_LABEL[g])} · {e(GROUP_RULE[g])} <span class="n">{len(rows)}</span></h3>'
                        f'{body}</section>')
    return "".join(sections)


def completion_legend() -> str:
    items = "".join(f'<span class="litem"><span class="sw {cls}"></span>{e(label)}</span>' for cls, label in (
        ("seg-done", "done"), ("seg-running", "in progress"), ("seg-waiting", "waiting"), ("seg-empty", "not started")))
    return f'<div class="clegend">{items}</div>'


_HISTORY_BUDGET = 10.0  # seconds -- P-08's "keep the page's generation time sane"


def progress_block(project) -> str:
    """P-08: history.series(project)'s two charts, server-rendered SVG, no
    JS and no external resources. Quietly omitted when the project has no
    git history yet or series() cannot be computed (a plain directory, a
    shallow clone, git missing) -- a graph nobody can trust is worse than no
    graph. If a first, uncached run takes over ~10s, a second call bounded
    to the last 60 days is used instead -- the sponsor asked for "a progress
    graph over time", not a slow tracker page."""
    if project is None:
        return ""
    try:
        started = time.monotonic()
        rows = HIST.series(project)
        if time.monotonic() - started > _HISTORY_BUDGET:
            since = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
            rows = HIST.series(project, since=since)
    except Exception:
        return ""
    if not rows:
        return ""
    return (f'<section class="progress" id="progress"><h3>Progress over time</h3>'
            f'<div class="charts">{HIST.svg(rows)}</div></section>')


def completion_top(entries, project=None) -> str:
    """The top of the page (proposal 30, P-09): the four tiles and the
    Progress block (P-08) only. The sponsor's own proposal tree (P-08's
    drill-down, promoted by P-09) follows immediately after this, with the
    old finish-now/back-burner/waiting grouping folded below that -- the
    first thing he sees is his proposals, not items sorted by urgency."""
    if not entries:
        return ""
    return ('<section class="completion" id="completion"><h2>Completion</h2>'
            f'<div class="tiles">{completion_tiles(entries)}</div>'
            f'{progress_block(project)}</section>')


def completion_groups_section(entries) -> str:
    """P-09: the old finish-now/back-burner/waiting overview, folded into a
    closed <details> below the proposal tree -- same pattern as the Lanes
    "Advanced" block (`lanes_section`), not a new one invented for this."""
    if not entries:
        return ""
    return (f'<details class="cgroups" id="cgroups"><summary>By urgency '
            f'<span class="n">{len(entries)}</span></summary>'
            f'{completion_groups(entries)}{completion_legend()}</details>')


# ---------------------------------------------------------------------------
# proposal 30, P-08: the feature-level drill-down. One row per proposal (the
# feature), expanding to its items, each expanding to its parts, to any
# depth parts.tree() carries -- pure <details>/<summary>, so it works with
# the page's script disabled. Every rule (completion, grouping, the "next"
# part, the pill) still comes from tools/tracker/parts.py; this only walks
# and renders what that module already computed.

def feature_children(item: dict) -> list[dict]:
    """The item's parts as parts.tree() nodes -- or, when it has none, one
    implicit node standing for the whole item, using the same convention as
    the completion overview's `display_parts()` above, so the two sections
    agree on what an item without parts looks like."""
    ps = PARTS.parts(item)
    if ps:
        return [PARTS.tree(p) for p in ps]
    node = dict(display_parts(item)[0])
    node["completion"] = 100 if node.get("status") == "done" else 0
    node["parts"] = []
    return [node]


def feature_node_row(node: dict) -> str:
    """One part (or sub-part, at any depth) as a row -- a <details> when it
    has its own sub-parts (recursing to any depth parts.tree() carries), a
    plain row otherwise."""
    cls, label, title = part_pill(node)
    title_attr = f' title="{e(title)}"' if title else ""
    share = node.get("share")
    share_html = f'<span class="pshare">{share}%</span>' if share is not None else ""
    completion = node.get("completion")
    compl_html = f'<span class="pcompl">{completion}%</span>' if completion is not None else ""
    summary = (f'<span class="pid">{e(node.get("id"))}</span>'
               f'<span class="ptitle" title="{e(node.get("title"))}">{e(node.get("title"))}</span>'
               f'{share_html}{compl_html}'
               f'<span class="pill p-{cls}"{title_attr}>{e(label)}</span>')
    children = node.get("parts") or []
    if children:
        body = "".join(feature_node_row(c) for c in children)
        return (f'<details class="prow-details"><summary class="prow">{summary}</summary>'
                f'<div class="fparts">{body}</div></details>')
    return f'<div class="prow">{summary}</div>'


def feature_item_row(item: dict, number) -> str:
    """One item under a feature (proposal) row: its own completion %, bar,
    group pill and next part, expanding to its parts."""
    pct = PARTS.completion(item)
    grp = PARTS.group(item)
    nxt = PARTS.next_part(item)
    next_text = f'next: {e(nxt.get("id"))} · {e(nxt.get("title"))}' if nxt else "all parts done"
    body = "".join(feature_node_row(c) for c in feature_children(item))
    return (f'<details class="item-row" data-item data-id="{e(item.get("id"))}" data-proposal="{e(number)}">'
            f'<summary class="ihead"><span class="iid">{e(item.get("id"))}</span>'
            f'<span class="ititle" title="{e(item.get("title"))}">{e(item.get("title"))}</span>'
            f'<span class="ipct">{pct}%</span>'
            f'<span class="ibar fbar">{feature_bar(item)}</span>'
            f'<span class="pill g-{slug(grp)}">{e(GROUP_LABEL.get(grp, grp))}</span>'
            f'<span class="inext dim">{next_text}</span></summary>'
            f'<div class="fitems">{body}</div></details>')


def proposal_feature_row(number, data, counts) -> str:
    items = L.items(data)
    total = len(items)
    done = sum(1 for it in items if PARTS.group(it) == "done")
    pct = round(sum(PARTS.completion(it) for it in items) / total) if total else 0
    rows = "".join(feature_item_row(it, number) for it in items)
    return (f'<details class="feature-row" data-proposal="{e(number)}">'
            f'<summary class="fphead"><span class="fpn">P{e(number)}</span>'
            f'<span class="fptitle" title="{e(data.get("title"))}">{e(data.get("title"))}</span>'
            f'<span class="fppct">{pct}%</span>'
            f'<span class="fpbar">{mini_bar(counts)}</span>'
            f'<span class="fpcount">{done}/{total} items done</span></summary>'
            f'<div class="fitems">{rows}</div></details>')


def features_section(ledgers: list[tuple[Path, dict]]) -> str:
    """P-08: "at the end of the day there can be a feature level ... graph
    where I can drop down and it can show me what sub action items and
    action items are there ... top level feature graph ... what is the
    completion for each thing and ... once I expand the drop down then it
    can show me what sub items are there and if there are more sub sub
    items". One row per proposal, collapsed by default."""
    if not ledgers:
        return ""
    rows = "".join(proposal_feature_row(data.get("proposal"), data, L.counts(data)) for _, data in ledgers)
    return ('<section class="features" id="features"><h2>Features</h2>'
            '<p class="fnote dim">Completion % is the average of each item’s completion, '
            'weighted equally per item.</p>'
            f'<div class="frows">{rows}</div></section>')


def column_order(status: str, entries: list) -> list:
    """Cards inside a column: newest activity first where there is activity;
    not-started work by newest proposal, then ledger order."""
    if status == "not started":
        return sorted(entries, key=lambda t: (-t[0], t[3]))
    return sorted(entries, key=lambda t: (str(last_entry(t[1]).get("at") or ""), -t[3]), reverse=True)


# ---------------------------------------------------------------------------
# proposal 30, P-10: the Kanban view -- one column per ledger status (the
# statuses module's own order, never written out twice), one card per item.
# A card whose item carries parts shows "N of M parts done" and expands in
# place to list them; an item with no parts behaves as before, one implicit
# part worth 100 (the same convention `display_parts()` already uses).

def kanban_card(item: dict, number) -> str:
    pct = PARTS.completion(item)
    title = item.get("title")
    parts = PARTS.parts(item)
    body = ""
    if parts:
        done = sum(1 for p in parts if p.get("status") == "done")
        rows = "".join(part_sub_row(p) for p in parts)
        body = (f'<details class="kparts"><summary>{done} of {len(parts)} parts done</summary>'
                f'<div class="fparts">{rows}</div></details>')
    return (f'<article class="kcard" data-item data-id="{e(item.get("id"))}" data-proposal="{e(number)}" '
            f'data-status="{e(item.get("status") or "")}">'
            f'<header><span class="kid">{e(item.get("id"))}</span><span class="pnum">P{e(number)}</span></header>'
            f'<h3 class="ktitle" title="{e(title)}">{e(title)}</h3>'
            f'<p class="kpct">{pct}% <span class="fbar kbar">{feature_bar(item)}</span></p>'
            f'{body}</article>')


def kanban_section(entries) -> str:
    """One column per `tools/tracker/ledger.py` status, in that module's own
    order -- a column with no cards still renders, with a count of 0, so
    the board's shape does not jump around as work moves between columns."""
    if not entries:
        return ""
    by_status: dict[str, list] = {s: [] for s in L.STATUSES}
    for _, item, number, _ in entries:
        by_status.setdefault(item.get("status") or "not started", []).append((item, number))
    cols = []
    for status in L.STATUSES:
        rows = by_status.get(status) or []
        cards = "".join(kanban_card(item, number) for item, number in rows)
        cols.append(f'<section class="kcol {slug(status)}" data-column="{e(status)}">'
                    f'<h3><span class="dot {slug(status)}"></span>{LABEL.get(status, status)} '
                    f'<span class="n">{len(rows)}</span></h3>'
                    f'<div class="kcards">{cards}</div></section>')
    return (f'<section class="kanban" id="kanban"><h2>Kanban</h2>'
            f'<div class="kanban-scroll"><div class="kboard">{"".join(cols)}</div></div></section>')


# ---------------------------------------------------------------------------

def render(ledgers: list[tuple[Path, dict]], name: str, repo, project=None) -> str:
    totals = {s: 0 for s in L.STATUSES}
    proposals, entries, open_asks, answered, requests = [], [], [], [], []
    owners, tiers = set(), set()
    for path, data in ledgers:
        number = data.get("proposal")
        counts = L.counts(data)
        for s in totals:
            totals[s] += counts[s]
        proposals.append((number, data, counts))
        for index, item in enumerate(L.items(data)):
            entries.append((int(number) if str(number).isdigit() else 0, item, number, index))
            if item.get("owner"):
                owners.add(item["owner"])
            if item.get("tier"):
                tiers.add(item["tier"])
        for ask in data.get("asks") or []:
            if ask.get("state") == "open":
                open_asks.append((number, ask))
                if ask.get("owner"):
                    owners.add(ask["owner"])
            else:
                answered.append((number, ask))
        for req in L.open_requests(data):
            requests.append((number, req))

    total = sum(totals.values())
    updated = max((str(d.get("updated") or "") for _, d in ledgers), default="")
    status_line = " / ".join(f"{totals[s]} {s}" for s in ("done", "in progress", "blocked", "not started"))
    extra_line = [f"{totals[s]} {s}" for s in ("in review", "in testing") if totals[s]]
    if extra_line:
        status_line += " / " + " / ".join(extra_line)

    blocks = "".join(
        f'<button class="proposal" type="button" data-proposal="{e(n)}" aria-pressed="false">'
        f'<span class="pn">{e(n)}</span>'
        f'<span class="pt">{e(d.get("title"))}</span>'
        f'<span class="ps">{b(d.get("status"))} · {c["done"]}/{sum(c.values())} done'
        f'{" · " + str(c["blocked"]) + " blocked" if c["blocked"] else ""}</span>'
        f'{mini_bar(c)}</button>'
        for n, d, c in proposals)

    chips = "".join(
        f'<button class="chip" data-filter="status" data-value="{e(s)}" aria-pressed="false" type="button">'
        f'<span class="dot {slug(s)}"></span>{LABEL[s]} <span class="n">{totals[s]}</span></button>'
        for s in COLUMNS)
    owner_opts = '<option value="">Anyone</option>' + "".join(
        f'<option value="{e(o)}">{e(o)}</option>' for o in sorted(owners))
    tier_opts = '<option value="">Any tier</option>' + "".join(
        f'<option value="{e(t)}">{e(t)}</option>' for t in sorted(tiers))
    group_opts = '<option value="">Any group</option>' + "".join(
        f'<option value="{e(g)}">{e(GROUP_LABEL[g])}</option>' for g in ("finish now", "back burner", "waiting", "done"))

    completion_top_block = completion_top(entries, project)
    features = features_section(ledgers)
    completion_groups_block = completion_groups_section(entries)
    kanban = kanban_section(entries)

    attention = ""
    if open_asks or requests:
        rows = "".join(ask_row(a, n) for n, a in open_asks) + "".join(request_row(r, n) for n, r in requests)
        attention = (f'<section class="attention" id="attention"><h2>Waiting for an answer '
                     f'<span class="n" id="attention-n">{len(open_asks) + len(requests)}</span></h2>'
                     f'<ul class="asks">{rows}</ul></section>')

    # Proposal 25 Z-06 and proposal 26 C-04: not-yet-taken work clustered by
    # files touched, and every open item's lane with the 80% cut marked --
    # both computed only when a project is given (render() stays callable
    # without one, as it always has been, for a caller with no lanes/risk
    # context to offer).
    clusters = clusters_section(cluster_state(ledgers)) if project is not None else ""
    lanes = lanes_section(lane_state(ledgers, project)) if project is not None else ""

    columns = []
    for status in COLUMNS:
        its = column_order(status, [t for t in entries if t[1].get("status") == status])
        cards = "".join(item_card(item, number, repo) for _, item, number, _ in its)
        columns.append(
            f'<section class="col {slug(status)}" data-column="{e(status)}">'
            f'<h2><span class="dot {slug(status)}"></span>{LABEL[status]} <span class="n">{len(its)}</span></h2>'
            f'<div class="cards">{cards}</div></section>')

    list_rows = "".join(item_row(item, number, repo)
                        for _, item, number, _ in sorted(entries, key=lambda t: (-t[0], t[3])))

    answered_block = ""
    if answered:
        rows = "".join(ask_row(a, n) for n, a in sorted(answered, key=lambda t: str(t[1].get("at") or ""),
                                                        reverse=True))
        answered_block = (f'<details class="answered" id="answered"><summary>Answered asks · '
                          f'<span id="answered-n">{len(answered)}</span></summary>'
                          f'<ul class="asks">{rows}</ul></details>')

    title = f"{name} tracker"
    return (
        "<!doctype html>\n"
        '<meta charset="utf-8">\n'
        f"<!-- generated by bin/tracker board from every ledger in docs/proposals -- edit the ledgers, not this page -->\n"
        f"<title>{e(title)}</title>\n"
        f'<meta name="ledger-digests" content="{e(digests([p for p, _ in ledgers]))}">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600'
        '&amp;family=IBM+Plex+Sans:wght@400;500;600;700&amp;display=swap">\n'
        f"<style>{CSS}</style>\n"
        '<main class="wrap">'
        f'<header class="top"><p class="eyebrow">{b(name)} · {len(ledgers)} '
        f'{"proposal" if len(ledgers) == 1 else "proposals"} · {total} items · updated {e(updated)}</p>'
        f'<h1>Tracker</h1>'
        f'<section class="totals" data-done="{totals["done"]}" data-in-progress="{totals["in progress"]}" '
        f'data-blocked="{totals["blocked"]}" data-not-started="{totals["not started"]}" '
        f'data-in-review="{totals["in review"]}" data-in-testing="{totals["in testing"]}">'
        f'<p class="line">{e(status_line)}</p>{mini_bar(totals)}</section></header>'
        f'{completion_top_block}'
        f'<div id="view-tree">{features}{completion_groups_block}</div>'
        f'<div id="view-kanban">{kanban}</div>'
        f'<nav class="proposals" aria-label="Proposals">{blocks}</nav>'
        '<h2 id="details">Details</h2>'
        '<div class="filters" role="search">'
        '<div class="views topview" role="group" aria-label="Top view">'
        '<button type="button" data-topview="tree" aria-pressed="true">Tree</button>'
        '<button type="button" data-topview="kanban" aria-pressed="false">Kanban</button></div>'
        f'<label class="sel"><span>Group</span><select id="group">{group_opts}</select></label>'
        '<input type="search" id="q" placeholder="Search ids, titles, tags, logs" aria-label="Search">'
        f'<div class="chips" role="group" aria-label="Status">{chips}</div>'
        f'<label class="sel"><span>Owner</span><select id="owner">{owner_opts}</select></label>'
        f'<label class="sel"><span>Tier</span><select id="tier">{tier_opts}</select></label>'
        '<div class="views" role="group" aria-label="View">'
        '<button type="button" data-view="board" aria-pressed="true">Board</button>'
        '<button type="button" data-view="list" aria-pressed="false">List</button></div>'
        '<label class="toggle"><input type="checkbox" id="show-finished"><span>Show finished</span></label>'
        '<button type="button" class="clear" id="clear">Clear</button>'
        '<p class="shown" id="shown" aria-live="polite"></p></div>'
        f'{attention}'
        f'{clusters}'
        f'{lanes}'
        f'<div class="board" id="board">{"".join(columns)}</div>'
        '<div class="list" id="list" hidden><div class="scroll"><table><thead><tr>'
        '<th>ID</th><th>Proposal</th><th>Item</th><th>Status</th><th>Owner</th><th>Tag</th><th>Issue</th><th>Last</th>'
        f'</tr></thead><tbody>{list_rows}</tbody></table></div></div>'
        '<p class="none" id="none" hidden>Nothing matches these filters. <button type="button" id="clear2">Clear filters</button></p>'
        f'{answered_block}'
        "</main>\n"
        f"<script>{SCRIPT}</script>\n"
    )


CSS = """
:root{--ground:#ECEFF3;--surface:#FAFBFC;--raise:#FFFFFF;--ink:#14181D;--dim:#5F6A76;--rule:#D3D9E0;
--accent:#2E5BA8;--accent-soft:#E1E9F6;
--done:#2F855A;--prog:#C9531D;--block:#B23A48;--todo:#8A96A3;--block-soft:#F8E6E8;--review:#6B4FBB;--test:#1D7A96;
--waiting:#B4790E;--risk:#B23A48;
--sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
--mono:"IBM Plex Mono","SF Mono",ui-monospace,Menlo,monospace;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ground:#101418;--surface:#171D23;--raise:#1C232A;
--ink:#E4E8EC;--dim:#94A0AB;--rule:#2A333C;--accent:#86A9E6;--accent-soft:#1D2A3D;
--done:#5FB58A;--prog:#EE7A45;--block:#DB7480;--todo:#6F7B87;--block-soft:#2E1C20;--review:#A992E8;--test:#5FC2DE;
--waiting:#E3A83E;--risk:#DB7480;color-scheme:dark}}
:root[data-theme="dark"]{--ground:#101418;--surface:#171D23;--raise:#1C232A;
--ink:#E4E8EC;--dim:#94A0AB;--rule:#2A333C;--accent:#86A9E6;--accent-soft:#1D2A3D;
--done:#5FB58A;--prog:#EE7A45;--block:#DB7480;--todo:#6F7B87;--block-soft:#2E1C20;--review:#A992E8;--test:#5FC2DE;
--waiting:#E3A83E;--risk:#DB7480;color-scheme:dark}
*{box-sizing:border-box}
[hidden]{display:none!important}
.card h3,.card .why,.card .meta,.log p,.ask q,td,.proposal .pt{unicode-bidi:isolate}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.5 var(--sans)}
.wrap{max-width:1360px;margin:0 auto;padding:32px 24px 96px;display:flex;flex-direction:column;gap:22px}
button,input,select{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.dim{color:var(--dim)}
.eyebrow{font:500 12px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--dim);margin:0}
h1{font:600 34px/1.1 var(--sans);letter-spacing:-.015em;margin:4px 0 0;text-wrap:balance}
.totals{margin-top:14px;max-width:560px}
.line{font:500 14px var(--mono);margin:0 0 8px;font-variant-numeric:tabular-nums}
.bar{display:flex;height:8px;background:var(--rule);border-radius:2px;overflow:hidden}
.totals .bar{height:12px}
.seg{display:block;height:100%}
.seg.s-done,.dot.s-done{background:var(--done)}.seg.s-in-progress,.dot.s-in-progress{background:var(--prog)}
.seg.s-blocked,.dot.s-blocked{background:var(--block)}.seg.s-not-started,.dot.s-not-started{background:var(--todo)}
.seg.s-in-review,.dot.s-in-review{background:var(--review)}.seg.s-in-testing,.dot.s-in-testing{background:var(--test)}
.seg.s-empty{background:var(--rule)}
.dot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:7px;flex:none}
.proposals{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.proposal{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;align-items:baseline;text-align:left;
background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:12px 14px 13px;cursor:pointer}
.proposal:hover{border-color:var(--dim)}
.proposal[aria-pressed="true"]{border-color:var(--accent);background:var(--accent-soft)}
.proposal .pn{grid-row:span 2;font:600 28px/1 var(--mono);color:var(--dim);font-variant-numeric:tabular-nums}
.proposal[aria-pressed="true"] .pn{color:var(--accent)}
.proposal .pt{font-weight:600;line-height:1.3}
.proposal .ps{font:12px var(--mono);color:var(--dim)}
.proposal .bar{grid-column:1/-1;margin-top:9px;height:5px}
.filters{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;
padding:10px 12px;margin:0 -12px;background:var(--ground);border-bottom:1px solid var(--rule)}
.filters input[type=search]{flex:1 1 220px;min-width:180px;padding:7px 10px;border:1px solid var(--rule);
border-radius:5px;background:var(--raise)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-flex;align-items:center;padding:5px 10px;border:1px solid var(--rule);border-radius:5px;
background:var(--raise);cursor:pointer;font-size:13.5px}
.chip .n,.col h2 .n,.attention h2 .n{font:500 12px var(--mono);color:var(--dim);margin-left:6px;font-variant-numeric:tabular-nums}
.chip[aria-pressed="true"]{border-color:var(--accent);background:var(--accent-soft)}
.sel{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.05em}
.sel select{text-transform:none;letter-spacing:0;font-size:13.5px;color:var(--ink);padding:5px 8px;
border:1px solid var(--rule);border-radius:5px;background:var(--raise)}
.views{display:inline-flex;border:1px solid var(--rule);border-radius:5px;overflow:hidden}
.views button{border:0;background:var(--raise);padding:5px 12px;cursor:pointer;font-size:13.5px}
.views button+button{border-left:1px solid var(--rule)}
.views button[aria-pressed="true"]{background:var(--ink);color:var(--ground)}
.clear{border:0;background:none;color:var(--accent);cursor:pointer;font-size:13.5px;padding:5px 4px}
.shown{margin:0 0 0 auto;font:12px var(--mono);color:var(--dim);font-variant-numeric:tabular-nums}
.attention{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:14px 16px}
.clusters,.lanes{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:14px 16px}
.cluster-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;margin-top:10px}
.cluster{background:var(--raise);border:1px solid var(--rule);border-radius:6px;padding:10px 12px}
.cluster h3{font:600 13.5px var(--sans);margin:0}
.cluster .files{font:12px var(--mono);color:var(--dim);margin:4px 0 6px;overflow-wrap:anywhere}
.cluster ul,.cluster-singles ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:3px}
.cluster li,.cluster-singles li{font:13px var(--sans)}
.cluster-singles{margin-top:10px}
.cluster-singles summary{font:12px var(--mono);color:var(--dim);cursor:pointer}
.lane{margin-top:12px}
.lane:first-child{margin-top:10px}
.lane h3{font:600 12px var(--sans);letter-spacing:.04em;text-transform:uppercase;color:var(--dim);margin:0 0 6px}
.lane ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.lane-item{font:13.5px/1.4 var(--sans);padding:4px 8px;border-radius:4px;background:var(--raise);
border:1px solid var(--rule);display:flex;flex-wrap:wrap;align-items:baseline;gap:6px}
.lane-item .id{font:600 12px var(--mono)}
.lane-item .share{font:12px var(--mono);margin-left:auto}
.lane-item.overdue{border-color:color-mix(in srgb,var(--block) 45%,var(--rule));
background:var(--block-soft)}
.badge-overdue{font:600 11px var(--mono);color:var(--block);border:1px solid currentColor;
border-radius:9px;padding:0 6px}
.badge-alone{font:500 11px var(--mono);color:var(--dim);border:1px solid var(--rule);border-radius:9px;padding:0 6px}
.cut-line{display:flex;align-items:center;gap:10px;margin:14px 0;color:var(--dim);
font:500 11.5px var(--mono);text-transform:uppercase;letter-spacing:.05em}
.cut-line::before,.cut-line::after{content:"";flex:1;height:1px;background:var(--rule)}
.lane-unsized .lane-item{opacity:.75}
h2{font:600 13px var(--sans);letter-spacing:.06em;text-transform:uppercase;margin:0;display:flex;align-items:center}
.asks{list-style:none;margin:10px 0 0;padding:0;display:flex;flex-direction:column;gap:8px}
.ask{display:grid;grid-template-columns:auto auto auto 1fr;gap:2px 10px;align-items:baseline}
.ask q{grid-column:4;quotes:"\\201C" "\\201D";max-width:90ch}
.ask .asked{grid-column:4;font:12px var(--mono);color:var(--dim)}
.ask .kind{font:12px var(--mono);color:var(--dim)}
.id{font:600 13px var(--mono);font-variant-numeric:tabular-nums}
.pnum{font:500 11.5px var(--mono);color:var(--dim);border:1px solid var(--rule);border-radius:3px;padding:0 4px}
.board{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:14px;align-items:start}
@media (max-width:1400px){.board{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:1100px){.board{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.board{grid-template-columns:1fr}.shown{margin-left:0}}
.col h2{padding:4px 2px 10px}
.cards{display:flex;flex-direction:column;gap:8px}
.card{background:var(--raise);border:1px solid var(--rule);border-radius:6px;padding:10px 12px 11px;display:flex;flex-direction:column;gap:5px}
.card header{display:flex;align-items:center;justify-content:space-between;gap:8px}
.card h3{font:500 14.5px/1.35 var(--sans);margin:0;text-wrap:pretty}
.card .meta{display:flex;flex-wrap:wrap;gap:4px 10px;margin:0;font:12px var(--mono);color:var(--dim)}
.card .owner{color:var(--ink)}
.card .owner::before{content:"owner ";color:var(--dim)}
.card .issue a{color:var(--accent)}
.card .last{margin:0;font:12px var(--mono);color:var(--dim)}
.card .last .event{color:var(--ink)}
.card .why{margin:2px 0 0;font-size:13px;line-height:1.4;color:var(--block)}
.card[data-status="blocked"]{background:var(--block-soft);border-color:color-mix(in srgb,var(--block) 35%,var(--rule))}
.card[data-status="done"]{padding:7px 12px 8px;gap:3px;background:var(--surface)}
.card[data-status="done"] h3{font-size:13.5px;color:var(--dim)}
.card[data-status="done"] .meta{display:none}
details summary{cursor:pointer;font:12px var(--mono);color:var(--dim);list-style-position:inside}
details summary:hover{color:var(--ink)}
.log{margin:6px 0 0;padding:0 0 0 2px;list-style:none;display:flex;flex-direction:column;gap:6px;
border-top:1px solid var(--rule);padding-top:8px}
.log li{font:12px/1.45 var(--mono);color:var(--dim)}
.log li b{color:var(--ink);font-weight:600}
.log li p{margin:2px 0 0;font:12.5px/1.45 var(--sans);color:var(--ink);overflow-wrap:anywhere}
.scroll{overflow-x:auto;background:var(--raise);border:1px solid var(--rule);border-radius:6px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font:600 11px var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--dim);
padding:9px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
td{padding:8px 10px;border-top:1px solid var(--rule);vertical-align:top}
td.id,td.mono,td.pnum{font-family:var(--mono);font-size:12.5px;white-space:nowrap}
td.pnum{border-radius:0;border-left:0;border-right:0;border-bottom:0}
td.mono a{color:var(--accent)}
.pill{display:inline-block;font:500 11.5px var(--mono);padding:1px 7px;border-radius:9px;border:1px solid currentColor;white-space:nowrap}
.pill.s-done{color:var(--done)}.pill.s-in-progress{color:var(--prog)}.pill.s-blocked{color:var(--block)}.pill.s-not-started{color:var(--dim)}
.pill.s-in-review{color:var(--review)}.pill.s-in-testing{color:var(--test)}
.none{margin:0;padding:18px;text-align:center;color:var(--dim);background:var(--surface);border:1px dashed var(--rule);border-radius:6px}
.none button{border:0;background:none;color:var(--accent);cursor:pointer;padding:0}
.answered summary{font:600 13px var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--dim);padding:6px 0}
.answered .asks{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:12px 14px}
.toggle{display:inline-flex;align-items:center;gap:6px;font-size:13.5px;color:var(--dim);cursor:pointer}
.toggle input{cursor:pointer}
/* -- proposal 30: completion overview -- */
.completion{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:14px 16px}
.completion h2{margin:0 0 12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:16px}
.tile{background:var(--raise);border:1px solid var(--rule);border-radius:6px;padding:10px 14px}
.tile .n{display:block;font:600 24px var(--mono);font-variant-numeric:tabular-nums}
.tile .l{display:block;font:12px var(--sans);color:var(--dim);text-transform:uppercase;letter-spacing:.05em;margin-top:2px}
.tile.t-finish .n{color:var(--accent)}.tile.t-back .n{color:var(--waiting)}
.tile.t-wait .n{color:var(--dim)}.tile.t-done .n{color:var(--done)}
.cgroup{margin-top:14px}
.cgroup:first-of-type{margin-top:0}
.cgroup h3{font:600 13px var(--sans);margin:0 0 8px;color:var(--ink)}
.cgroup h3 .n{font:500 12px var(--mono);color:var(--dim);margin-left:6px;font-variant-numeric:tabular-nums}
.cgroup .empty-note{color:var(--dim);font-size:13px;font-style:italic;padding:6px 0}
.frow{background:var(--raise);border:1px solid var(--rule);border-radius:6px;margin-top:6px;overflow:hidden}
.frow:first-child{margin-top:0}
.fhead{display:grid;grid-template-columns:auto 1fr auto;grid-template-rows:auto 5px;row-gap:6px;
column-gap:10px;align-items:center;padding:8px 12px;cursor:pointer;list-style:none}
.fhead::-webkit-details-marker{display:none}
.fhead .fid{font:600 12.5px var(--mono);color:var(--dim)}
.fhead .ftitle{font:14px var(--sans);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
overflow:hidden;max-height:2.8em;white-space:normal;overflow-wrap:anywhere}
.fhead .fpct{font:600 12.5px var(--mono);color:var(--dim);font-variant-numeric:tabular-nums}
.fhead .fbar{grid-column:1/-1;height:5px;display:flex;overflow:hidden;border-radius:2px}
.fbar span,.fparts .pshare{display:block}
.fbar span{height:100%}
.seg-done{background:var(--done)}.seg-running{background:var(--accent)}
.seg-waiting{background:var(--waiting)}.seg-empty{background:var(--rule)}
.fparts{border-top:1px solid var(--rule);background:var(--ground)}
.prow{display:grid;grid-template-columns:90px 1fr 50px 130px;gap:10px;align-items:center;
padding:6px 12px 6px 22px;font-size:12.5px;border-top:1px solid var(--rule)}
.prow:first-child{border-top:none}
.prow.muted{opacity:.65}
.prow .pid{font-family:var(--mono);color:var(--dim)}
.prow .ptitle{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
max-height:2.6em;white-space:normal;overflow-wrap:anywhere}
.prow .pshare{font-family:var(--mono);color:var(--dim);text-align:right}
.pill.p-done{color:var(--done);border-color:var(--done)}
.pill.p-other{color:var(--dim)}
.pill.p-waiting{color:var(--waiting);border-color:var(--waiting)}
.pill.p-risk{color:var(--risk);border-color:var(--risk);cursor:help;border-style:dashed}
.clegend{display:flex;gap:16px;font-size:12px;color:var(--dim);margin-top:12px;flex-wrap:wrap}
.clegend .litem{display:inline-flex;align-items:center;gap:5px}
.clegend .sw{display:inline-block;width:10px;height:10px;border-radius:2px}
.parts-details{margin-top:4px}
.parts-details summary{font-size:11.5px}
.card .pct{margin:0;font:600 12.5px var(--mono);display:flex;align-items:center;gap:8px}
.card .pct .fbar{width:60px;height:5px;display:inline-flex;border-radius:2px;overflow:hidden}
.card .pct .next{font:12px var(--sans);font-weight:400}
/* -- proposal 30, P-08: progress charts and the feature drill-down -- */
.progress{margin-top:16px}
.progress h3{font:600 13px var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--dim);margin:0 0 8px}
.charts{display:flex;flex-direction:column;gap:16px}
.charts svg{display:block;width:100%;height:auto;color:var(--dim)}
.features{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:14px 16px}
.features h2{margin:0 0 6px}
.fnote{margin:0 0 10px;font-size:12.5px}
.frows{display:flex;flex-direction:column;gap:6px}
.feature-row{background:var(--raise);border:1px solid var(--rule);border-radius:6px;overflow:hidden}
.fphead{display:grid;grid-template-columns:auto 1fr auto auto auto;gap:10px;align-items:center;
padding:9px 12px;cursor:pointer;list-style:none}
.fphead::-webkit-details-marker{display:none}
.fphead .fpn{font:600 12.5px var(--mono);color:var(--dim)}
.fphead .fptitle{font:14px var(--sans);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
overflow:hidden;max-height:2.8em;white-space:normal;overflow-wrap:anywhere}
.fphead .fppct{font:600 12.5px var(--mono);font-variant-numeric:tabular-nums}
.fphead .fpbar{width:90px;height:6px}
.fphead .fpcount{font:12px var(--mono);color:var(--dim);white-space:nowrap}
.fitems{border-top:1px solid var(--rule);background:var(--ground);padding:4px 0}
.item-row{margin:2px 8px}
.item-row .ihead{display:grid;grid-template-columns:auto 1fr auto 70px auto auto;gap:10px;align-items:center;
padding:6px 8px;cursor:pointer;list-style:none;font-size:13px}
.item-row .ihead::-webkit-details-marker{display:none}
.item-row .iid{font:600 12px var(--mono);color:var(--dim)}
.item-row .ititle{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
max-height:2.6em;white-space:normal;overflow-wrap:anywhere}
.item-row .ipct{font:600 12px var(--mono);font-variant-numeric:tabular-nums}
.item-row .ibar{height:5px}
.item-row .inext{font-size:11.5px;white-space:nowrap}
.pill.g-s-finish-now,.pill.g-s-back-burner,.pill.g-s-waiting,.pill.g-s-done{border-color:var(--rule);color:var(--dim)}
.prow-details,.item-row .fitems .prow{margin-left:14px}
.prow-details>summary.prow,.fitems>.prow{list-style:none;cursor:pointer}
.prow-details>summary.prow::-webkit-details-marker{display:none}
.prow{display:grid;grid-template-columns:90px 1fr 50px 50px 130px;gap:10px;align-items:center;
padding:4px 8px;font-size:12px;color:var(--ink)}
.prow .pid{font-family:var(--mono);color:var(--dim)}
.prow .pshare,.prow .pcompl{font-family:var(--mono);color:var(--dim);text-align:right}
.prow-details .fparts{margin-left:14px;border-left:1px solid var(--rule)}
/* -- proposal 30, P-10: the Tree/Kanban top view and the Kanban board -- */
.topview{margin-right:4px}
#view-kanban{margin-top:0}
.kanban{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:14px 16px}
.kanban h2{margin:0 0 12px}
.kanban-scroll{overflow-x:auto;overflow-y:hidden;margin:0 -4px;padding:0 4px}
.kboard{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(240px,280px);gap:12px;align-items:start}
.kcol{background:var(--raise);border:1px solid var(--rule);border-radius:6px;padding:10px}
.kcol>h3{font:600 12px var(--sans);letter-spacing:.04em;text-transform:uppercase;color:var(--dim);
margin:0 0 8px;display:flex;align-items:center}
.kcol>h3 .n{font:500 12px var(--mono);color:var(--dim);margin-left:6px;font-variant-numeric:tabular-nums}
.kcards{display:flex;flex-direction:column;gap:8px}
.kcard{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:9px 11px 10px;
display:flex;flex-direction:column;gap:5px}
.kcard header{display:flex;align-items:center;justify-content:space-between;gap:8px}
.kcard .kid{font:600 12px var(--mono);color:var(--dim)}
.ktitle{margin:0;font:500 13.5px/1.35 var(--sans);display:-webkit-box;-webkit-line-clamp:2;
-webkit-box-orient:vertical;overflow:hidden;max-height:2.6em;white-space:normal;overflow-wrap:anywhere}
.kpct{margin:0;font:600 12px var(--mono);display:flex;align-items:center;gap:8px}
.kbar{width:100%;height:5px;display:inline-flex;border-radius:2px;overflow:hidden}
.kparts{margin-top:2px}
.kparts summary{font-size:11.5px}
@media (prefers-reduced-motion:no-preference){.card,.proposal,.chip{transition:border-color .12s,background-color .12s}}
"""

SCRIPT = r"""
(function(){
  var $ = function(s, r){ return (r || document).querySelector(s); };
  var $$ = function(s, r){ return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var state = {proposal: "", statuses: [], owner: "", tier: "", group: "", q: "", view: "board", showFinished: false,
               topview: "tree"};
  try { var v = localStorage.getItem("tracker-view"); if (v === "list" || v === "board") state.view = v; } catch (e) {}
  try { var tv = localStorage.getItem("tracker-topview"); if (tv === "tree" || tv === "kanban") state.topview = tv; }
  catch (e) {}
  var items = $$("[data-item]");
  var searchById = {};
  $$("article[data-item]").forEach(function(card){ searchById[card.dataset.id] = card.dataset.search || ""; });
  var rows = $$("tr[data-item]");
  rows.forEach(function(row){ row.dataset.search = searchById[row.dataset.id] || ""; });
  function match(el, ignoreStatus, ignoreFinished){
    var d = el.dataset;
    if (state.proposal && d.proposal !== state.proposal) return false;
    if (!ignoreStatus && state.statuses.length && state.statuses.indexOf(d.status) < 0) return false;
    if (state.owner && d.owner !== state.owner) return false;
    if (state.tier && d.tier !== state.tier) return false;
    if (state.group && d.group !== state.group) return false;
    if (!ignoreFinished && !state.showFinished && d.group === "done" && state.group !== "done") return false;
    if (state.q && (d.search || "").indexOf(state.q) < 0) return false;
    return true;
  }
  function apply(){
    var shown = 0, total = 0, byStatus = {};
    var counted = state.view === "list" ? "TR" : "ARTICLE";
    items.forEach(function(el){
      var ok = match(el, false, false);
      el.hidden = !ok;
      if (el.tagName === counted) {
        total++;
        if (ok) shown++;
        // The chip count is the true count of each status among the other
        // filters (proposal/owner/tier/group/search) -- never zeroed out by
        // the show-finished toggle, or "Done" would misreport as 0 (D4).
        if (match(el, true, true)) byStatus[el.dataset.status] = (byStatus[el.dataset.status] || 0) + 1;
      }
    });
    $$(".col").forEach(function(col){
      var n = $$("[data-item]", col).filter(function(el){ return !el.hidden; }).length;
      $(".n", col).textContent = n;
      col.hidden = state.statuses.length > 0 && state.statuses.indexOf(col.dataset.column) < 0;
    });
    $$('.chip[data-filter="status"]').forEach(function(c){
      c.setAttribute("aria-pressed", state.statuses.indexOf(c.dataset.value) >= 0 ? "true" : "false");
      $(".n", c).textContent = byStatus[c.dataset.value] || 0;
    });
    $$(".proposal").forEach(function(b){
      b.setAttribute("aria-pressed", b.dataset.proposal === state.proposal ? "true" : "false");
    });
    $$("[data-ask],[data-request]").forEach(function(el){
      var d = el.dataset;
      el.hidden = (!!state.proposal && d.proposal !== state.proposal) || (!!state.owner && d.owner !== state.owner)
        || (!!state.q && (d.search || "").indexOf(state.q) < 0);
    });
    var visible = function(list){ return list.filter(function(el){ return !el.hidden; }).length; };
    var attention = $("#attention");
    if (attention) {
      var waiting = visible($$("[data-ask],[data-request]", attention));
      $("#attention-n").textContent = waiting;
      attention.hidden = waiting === 0;
    }
    var answered = $("#answered");
    if (answered) {
      var done = visible($$("[data-ask]", answered));
      $("#answered-n").textContent = done;
      answered.hidden = done === 0;
    }
    $$("[data-view]").forEach(function(b){ b.setAttribute("aria-pressed", b.dataset.view === state.view ? "true" : "false"); });
    $("#board").hidden = state.view !== "board";
    $("#list").hidden = state.view !== "list";
    $("#none").hidden = shown > 0 || total === 0;
    var filtered = state.proposal || state.statuses.length || state.owner || state.tier || state.q;
    $("#shown").textContent = filtered ? shown + " of " + total + " items" : total + " items";
    $("#clear").hidden = !filtered;
  }
  function clear(){
    state.proposal = ""; state.statuses = []; state.owner = ""; state.tier = ""; state.group = ""; state.q = "";
    state.showFinished = false;
    $("#q").value = ""; $("#owner").value = ""; $("#tier").value = ""; $("#group").value = "";
    var sf = $("#show-finished"); if (sf) sf.checked = false;
    apply();
  }
  $$(".proposal").forEach(function(b){ b.addEventListener("click", function(){
    state.proposal = state.proposal === b.dataset.proposal ? "" : b.dataset.proposal; apply(); }); });
  $$('.chip[data-filter="status"]').forEach(function(c){ c.addEventListener("click", function(){
    var i = state.statuses.indexOf(c.dataset.value);
    if (i >= 0) state.statuses.splice(i, 1); else state.statuses.push(c.dataset.value);
    apply(); }); });
  $("#owner").addEventListener("change", function(ev){ state.owner = ev.target.value; apply(); });
  $("#tier").addEventListener("change", function(ev){ state.tier = ev.target.value; apply(); });
  $("#group").addEventListener("change", function(ev){ state.group = ev.target.value; apply(); });
  var showFinished = $("#show-finished");
  if (showFinished) showFinished.addEventListener("change", function(ev){ state.showFinished = ev.target.checked; apply(); });
  $("#q").addEventListener("input", function(ev){ state.q = ev.target.value.trim().toLowerCase(); apply(); });
  $$("[data-view]").forEach(function(b){ b.addEventListener("click", function(){
    state.view = b.dataset.view;
    try { localStorage.setItem("tracker-view", state.view); } catch (e) {}
    apply(); }); });
  $("#clear").addEventListener("click", clear);
  $("#clear2").addEventListener("click", clear);
  function applyTopview(){
    $$("[data-topview]").forEach(function(b){
      b.setAttribute("aria-pressed", b.dataset.topview === state.topview ? "true" : "false"); });
    var t = $("#view-tree"); if (t) t.hidden = state.topview !== "tree";
    var k = $("#view-kanban"); if (k) k.hidden = state.topview !== "kanban";
  }
  $$("[data-topview]").forEach(function(b){ b.addEventListener("click", function(){
    state.topview = b.dataset.topview;
    try { localStorage.setItem("tracker-topview", state.topview); } catch (e) {}
    applyTopview(); }); });
  applyTopview();
  apply();
})();
"""


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker board", description=__doc__.splitlines()[0])
    ap.add_argument("--project", type=Path, default=Path.cwd(),
                    help="the project root, holding docs/proposals (default: the current directory)")
    ap.add_argument("--out", type=Path, help=f"where to write (default: docs/proposals/tracker/{OUT_NAME})")
    ap.add_argument("--name", help="the project's name on the page (default: its main checkout's folder)")
    ap.add_argument("--repo", help="owner/name for issue links (default: the ledgers' git remote)")
    ap.add_argument("--check", action="store_true", help="exit 1 if the page is missing or stale; write nothing")
    args = ap.parse_args(argv)

    project = args.project
    paths = sorted(L.find(project), key=lambda p: p.name)
    if not paths:
        print(f"tracker board: no ledgers under {project / 'docs' / 'proposals'} -- nothing written",
              file=sys.stderr)
        return 2
    out = args.out or default_out(project)

    if args.check:
        fresh = freshness(paths, out)
        if fresh == "missing":
            print(f"stale: {out} is missing -- run: tracker board --project {project}")
            return 1
        if fresh == "stale":
            print(f"stale: {out} was rendered from different ledgers -- run: tracker board --project {project}")
            return 1
        print(f"ok {out} matches {len(paths)} ledger(s)")
        return 0

    ledgers, bad = [], 0
    for path in paths:
        try:
            data = L.load(path)
        except (OSError, ValueError) as exc:
            print(f"tracker board: {path} could not be read ({type(exc).__name__}) -- nothing written",
                  file=sys.stderr)
            return 2
        problems = L.validate(data)
        if problems:
            bad += 1
            print(f"tracker board: {path} is not well-formed:", file=sys.stderr)
            for p in problems:
                print(f"  {p}", file=sys.stderr)
        ledgers.append((path, data))
    if bad:
        print("tracker board: a page of these ledgers would show numbers nobody can trust -- nothing written",
              file=sys.stderr)
        return 1

    ledgers.sort(key=lambda t: (int(t[1].get("proposal")) if str(t[1].get("proposal")).isdigit() else 0, t[0].name))
    repo = args.repo or R.infer_repo(paths[0])
    text = render(ledgers, args.name or project_name(project), repo, project)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_text() != text:
        out.write_text(text)
    totals = {s: 0 for s in L.STATUSES}
    for _, data in ledgers:
        for s, n in L.counts(data).items():
            totals[s] += n
    line = " / ".join(f"{totals[s]} {s}" for s in ("done", "in progress", "blocked", "not started"))
    extra = [f"{totals[s]} {s}" for s in ("in review", "in testing") if totals[s]]
    if extra:
        line += " / " + " / ".join(extra)
    print(f"rendered {out} · " + line)
    return 0
