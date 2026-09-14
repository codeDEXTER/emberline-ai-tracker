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
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path

from tools.tracker import ledger as L
from tools.tracker import render as R

OUT_NAME = "index.html"
# Attention order: what is moving, what is stuck, what is next, what is done.
COLUMNS = ("in progress", "blocked", "not started", "done")
LABEL = {"in progress": "In progress", "blocked": "Blocked", "not started": "Not started", "done": "Done"}


def e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


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
    return ";".join(f"{p.name}={hashlib.sha256(p.read_bytes()).hexdigest()}" for p in paths)


def freshness(paths: list[Path], page: Path) -> str:
    if not page.exists():
        return "missing"
    m = re.search(r'<meta name="ledger-digests" content="([^"]*)">', page.read_text(errors="replace"))
    return "ok" if m and html.unescape(m.group(1)) == digests(paths) else "stale"


# ---------------------------------------------------------------------------
# pieces

def mini_bar(counts: dict) -> str:
    total = sum(counts.values())
    if not total:
        return '<span class="bar"><span class="seg s-empty" style="width:100%"></span></span>'
    segs = "".join(f'<span class="seg {slug(s)}" style="width:{counts[s] * 100 / total:.2f}%"></span>'
                   for s in ("done", "in progress", "blocked", "not started") if counts[s])
    return f'<span class="bar">{segs}</span>'


def last_entry(item: dict) -> dict:
    log = item.get("log") or []
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
    lastline = (f'<p class="last"><span class="event">{e(last.get("event"))}</span> '
                f'<time>{e(when(last.get("at")))}</time></p>' if last else '<p class="last dim">no entries yet</p>')
    log = item.get("log") or []
    entries = "".join(
        f'<li><time>{e(when(x.get("at")))}</time> <b>{e(x.get("event"))}</b> <span class="by">{e(x.get("by"))}</span>'
        f'{"<p>" + e(x.get("evidence")) + "</p>" if x.get("evidence") else ""}</li>'
        for x in log)
    details = (f'<details><summary>Log · {len(log)} {"entry" if len(log) == 1 else "entries"}</summary>'
               f'<ol class="log">{entries}</ol></details>' if log else "")
    return (f'<article class="card" data-item data-id="{e(item.get("id"))}" data-proposal="{e(number)}" '
            f'data-status="{e(status)}" data-owner="{e(owner)}" data-tier="{e(item.get("tier") or "")}">'
            f'<header><span class="id">{e(item.get("id"))}</span><span class="pnum">P{e(number)}</span></header>'
            f'<h3>{e(item.get("title"))}</h3>'
            f'<p class="meta">{"".join(meta)}</p>{reason}{lastline}{details}</article>')


def item_row(item: dict, number, repo) -> str:
    status = item.get("status", "")
    last = last_entry(item)
    owner = item.get("owner") or ""
    return (f'<tr class="row" data-item data-id="{e(item.get("id"))}" data-proposal="{e(number)}" '
            f'data-status="{e(status)}" data-owner="{e(owner)}" data-tier="{e(item.get("tier") or "")}">'
            f'<td class="id">{e(item.get("id"))}</td><td class="pnum">P{e(number)}</td>'
            f'<td>{e(item.get("title"))}</td>'
            f'<td><span class="pill {slug(status)}">{e(status)}</span></td>'
            f'<td class="mono">{e(owner) or "—"}</td>'
            f'<td class="mono">{e(item.get("tag") or item.get("cx"))}</td>'
            f'<td class="mono">{R.issue_cell(item.get("issue"), repo)}</td>'
            f'<td class="mono">{e(last.get("event") or "—")} <span class="dim">{e(when(last.get("at")))}</span></td></tr>')


def ask_row(ask: dict, number) -> str:
    owner = ask.get("owner") or ""
    became = f' <span class="dim">→ {e(ask.get("became"))}</span>' if ask.get("became") else ""
    return (f'<li class="ask" data-ask="{e(ask.get("id"))}" data-proposal="{e(number)}">'
            f'<span class="id">{e(ask.get("id"))}</span><span class="pnum">P{e(number)}</span>'
            f'<span class="kind">{e(ask.get("kind"))}</span>'
            f'<q>{e(ask.get("quote"))}</q>'
            f'<span class="asked">{e(when(ask.get("at")))}{" · owner " + e(owner) if owner else ""}{became}</span></li>')


def request_row(req: dict, number) -> str:
    return (f'<li class="ask" data-request="{e(req.get("id"))}" data-proposal="{e(number)}">'
            f'<span class="id">{e(req.get("id"))}</span><span class="pnum">P{e(number)}</span>'
            f'<span class="kind">request</span>'
            f'<q>{e(req.get("from"))} → {e(req.get("to"))}</q>'
            f'<span class="asked">{e(req.get("state"))}'
            f'{" · unblocks " + e(" ".join(req.get("unblocks") or [])) if req.get("unblocks") else ""}</span></li>')


def column_order(status: str, entries: list) -> list:
    """Cards inside a column: newest activity first where there is activity;
    not-started work by newest proposal, then ledger order."""
    if status == "not started":
        return sorted(entries, key=lambda t: (-t[0], t[3]))
    return sorted(entries, key=lambda t: (str(last_entry(t[1]).get("at") or ""), -t[3]), reverse=True)


# ---------------------------------------------------------------------------

def render(ledgers: list[tuple[Path, dict]], name: str, repo) -> str:
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

    blocks = "".join(
        f'<button class="proposal" type="button" data-proposal="{e(n)}" aria-pressed="false">'
        f'<span class="pn">{e(n)}</span>'
        f'<span class="pt">{e(d.get("title"))}</span>'
        f'<span class="ps">{e(d.get("status"))} · {c["done"]}/{sum(c.values())} done'
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

    attention = ""
    if open_asks or requests:
        rows = "".join(ask_row(a, n) for n, a in open_asks) + "".join(request_row(r, n) for n, r in requests)
        attention = (f'<section class="attention"><h2>Waiting for an answer '
                     f'<span class="n">{len(open_asks) + len(requests)}</span></h2><ul class="asks">{rows}</ul></section>')

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
        answered_block = (f'<details class="answered"><summary>Answered asks · {len(answered)}</summary>'
                          f'<ul class="asks">{rows}</ul></details>')

    title = f"{name} tracker"
    return (
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
        f'<header class="top"><p class="eyebrow">{e(name)} · {len(ledgers)} '
        f'{"proposal" if len(ledgers) == 1 else "proposals"} · {total} items · updated {e(updated)}</p>'
        f'<h1>Tracker</h1>'
        f'<section class="totals" data-done="{totals["done"]}" data-in-progress="{totals["in progress"]}" '
        f'data-blocked="{totals["blocked"]}" data-not-started="{totals["not started"]}">'
        f'<p class="line">{e(status_line)}</p>{mini_bar(totals)}</section></header>'
        f'<nav class="proposals" aria-label="Proposals">{blocks}</nav>'
        '<div class="filters" role="search">'
        '<input type="search" id="q" placeholder="Search ids, titles, tags, logs" aria-label="Search">'
        f'<div class="chips" role="group" aria-label="Status">{chips}</div>'
        f'<label class="sel"><span>Owner</span><select id="owner">{owner_opts}</select></label>'
        f'<label class="sel"><span>Tier</span><select id="tier">{tier_opts}</select></label>'
        '<div class="views" role="group" aria-label="View">'
        '<button type="button" data-view="board" aria-pressed="true">Board</button>'
        '<button type="button" data-view="list" aria-pressed="false">List</button></div>'
        '<button type="button" class="clear" id="clear">Clear</button>'
        '<p class="shown" id="shown" aria-live="polite"></p></div>'
        f'{attention}'
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
--done:#2F855A;--prog:#C9531D;--block:#B23A48;--todo:#8A96A3;--block-soft:#F8E6E8;
--sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
--mono:"IBM Plex Mono","SF Mono",ui-monospace,Menlo,monospace;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ground:#101418;--surface:#171D23;--raise:#1C232A;
--ink:#E4E8EC;--dim:#94A0AB;--rule:#2A333C;--accent:#86A9E6;--accent-soft:#1D2A3D;
--done:#5FB58A;--prog:#EE7A45;--block:#DB7480;--todo:#6F7B87;--block-soft:#2E1C20;color-scheme:dark}}
:root[data-theme="dark"]{--ground:#101418;--surface:#171D23;--raise:#1C232A;
--ink:#E4E8EC;--dim:#94A0AB;--rule:#2A333C;--accent:#86A9E6;--accent-soft:#1D2A3D;
--done:#5FB58A;--prog:#EE7A45;--block:#DB7480;--todo:#6F7B87;--block-soft:#2E1C20;color-scheme:dark}
*{box-sizing:border-box}
[hidden]{display:none!important}
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
h2{font:600 13px var(--sans);letter-spacing:.06em;text-transform:uppercase;margin:0;display:flex;align-items:center}
.asks{list-style:none;margin:10px 0 0;padding:0;display:flex;flex-direction:column;gap:8px}
.ask{display:grid;grid-template-columns:auto auto auto 1fr;gap:2px 10px;align-items:baseline}
.ask q{grid-column:4;quotes:"\\201C" "\\201D";max-width:90ch}
.ask .asked{grid-column:4;font:12px var(--mono);color:var(--dim)}
.ask .kind{font:12px var(--mono);color:var(--dim)}
.id{font:600 13px var(--mono);font-variant-numeric:tabular-nums}
.pnum{font:500 11.5px var(--mono);color:var(--dim);border:1px solid var(--rule);border-radius:3px;padding:0 4px}
.board{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;align-items:start}
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
.none{margin:0;padding:18px;text-align:center;color:var(--dim);background:var(--surface);border:1px dashed var(--rule);border-radius:6px}
.none button{border:0;background:none;color:var(--accent);cursor:pointer;padding:0}
.answered summary{font:600 13px var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--dim);padding:6px 0}
.answered .asks{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:12px 14px}
@media (prefers-reduced-motion:no-preference){.card,.proposal,.chip{transition:border-color .12s,background-color .12s}}
"""

SCRIPT = r"""
(function(){
  var $ = function(s, r){ return (r || document).querySelector(s); };
  var $$ = function(s, r){ return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var state = {proposal: "", statuses: [], owner: "", tier: "", q: "", view: "board"};
  try { var v = localStorage.getItem("tracker-view"); if (v === "list" || v === "board") state.view = v; } catch (e) {}
  var items = $$("[data-item]");
  var text = new Map(items.map(function(el){ return [el, el.textContent.toLowerCase()]; }));
  function match(el, ignoreStatus){
    var d = el.dataset;
    if (state.proposal && d.proposal !== state.proposal) return false;
    if (!ignoreStatus && state.statuses.length && state.statuses.indexOf(d.status) < 0) return false;
    if (state.owner && d.owner !== state.owner) return false;
    if (state.tier && d.tier !== state.tier) return false;
    if (state.q && text.get(el).indexOf(state.q) < 0) return false;
    return true;
  }
  function apply(){
    var shown = 0, total = 0, byStatus = {};
    items.forEach(function(el){
      var ok = match(el, false);
      el.hidden = !ok;
      if (el.tagName === "ARTICLE") {
        total++;
        if (ok) shown++;
        if (match(el, true)) byStatus[el.dataset.status] = (byStatus[el.dataset.status] || 0) + 1;
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
      el.hidden = !!state.proposal && el.dataset.proposal !== state.proposal;
    });
    $$("[data-view]").forEach(function(b){ b.setAttribute("aria-pressed", b.dataset.view === state.view ? "true" : "false"); });
    $("#board").hidden = state.view !== "board";
    $("#list").hidden = state.view !== "list";
    $("#none").hidden = shown > 0;
    var filtered = state.proposal || state.statuses.length || state.owner || state.tier || state.q;
    $("#shown").textContent = filtered ? shown + " of " + total + " items" : total + " items";
    $("#clear").hidden = !filtered;
  }
  function clear(){
    state.proposal = ""; state.statuses = []; state.owner = ""; state.tier = ""; state.q = "";
    $("#q").value = ""; $("#owner").value = ""; $("#tier").value = "";
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
  $("#q").addEventListener("input", function(ev){ state.q = ev.target.value.trim().toLowerCase(); apply(); });
  $$("[data-view]").forEach(function(b){ b.addEventListener("click", function(){
    state.view = b.dataset.view;
    try { localStorage.setItem("tracker-view", state.view); } catch (e) {}
    apply(); }); });
  $("#clear").addEventListener("click", clear);
  $("#clear2").addEventListener("click", clear);
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
    text = render(ledgers, args.name or project_name(project), repo)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_text() != text:
        out.write_text(text)
    totals = {s: 0 for s in L.STATUSES}
    for _, data in ledgers:
        for s, n in L.counts(data).items():
            totals[s] += n
    print(f"rendered {out} · " + " / ".join(f"{totals[s]} {s}" for s in ("done", "in progress", "blocked", "not started")))
    return 0
