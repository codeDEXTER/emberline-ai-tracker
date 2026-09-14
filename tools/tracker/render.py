"""tracker render -- a ledger's page, generated (proposal 19, W-02).

  tracker render LEDGER.json [--out PATH] [--repo OWNER/NAME]
  tracker render LEDGER.json --check
  tracker published LEDGER.json --url URL [--by NAME]   (proposal 20, V-09; see published_main)

Writes docs/proposals/tracker/<ledger stem>.html beside the ledger. Two
reasons it is a subdirectory and not the proposal page itself:

  * the proposal page is authored prose -- decisions, reasoning, pictures --
    and a generator that owns it would erase exactly what makes it a
    proposal. The ledger page is the other half: the numbers, always current.
  * every checker that reads proposals globs docs/proposals/*.html:
    common-rules' proposalcheck (one number, one document), and the engine's
    build_proposal_index.py and check_proposals.py. A second file claiming the
    same number at that level would fail the first and pollute the other two.

The page carries a digest of the ledger's bytes, and `--check` compares that
rather than modification times: a checkout or a rebase resets mtimes, so a
timestamp test passes on a page rendered from a different ledger.

Output is deterministic -- no "generated at" clock -- so rendering an
unchanged ledger produces an unchanged file and a diff means something moved.

Exit codes: 0 rendered / fresh, 1 stale or invalid ledger, 2 unreadable.
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

STATUS_ORDER = ("done", "in progress", "blocked", "not started")


def e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def slug(status: str) -> str:
    return "s-" + status.replace(" ", "-")


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def default_out(ledger_path: Path) -> Path:
    return ledger_path.parent / "tracker" / f"{ledger_path.stem}.html"


def infer_repo(ledger_path: Path) -> str | None:
    """owner/name from the ledger's own git remote, or None. Never guessed."""
    try:
        url = subprocess.run(["git", "-C", str(ledger_path.parent), "remote", "get-url", "origin"],
                             capture_output=True, text=True, check=True, timeout=5).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else None


def bar(counts: dict, cls: str) -> str:
    total = sum(counts.values())
    if not total:
        return f'<div class="{cls}"><span class="seg s-empty" style="width:100%"></span></div>'
    segs = []
    for s in STATUS_ORDER:
        if counts[s]:
            segs.append(f'<span class="seg {slug(s)}" style="width:{counts[s] * 100 / total:.2f}%" '
                        f'title="{counts[s]} {e(s)}"></span>')
    return f'<div class="{cls}">{"".join(segs)}</div>'


def issue_cell(number, repo) -> str:
    if not number:
        return '<span class="dim">—</span>'
    if repo:
        return f'<a href="https://github.com/{e(repo)}/issues/{e(number)}">#{e(number)}</a>'
    return f"#{e(number)}"


def last_log(item: dict) -> str:
    """The last log entry: event and time, with its evidence on hover -- and
    in full when the item is blocked, because "blocked" without the reason
    is the one status a reader cannot act on."""
    log = item.get("log") or []
    if not log:
        return '<span class="dim">no entries</span>'
    last = log[-1]
    when = str(last.get("at", ""))[:16].replace("T", " ")
    evidence = last.get("evidence") or ""
    cell = f'<span title="{e(evidence)}">{e(last.get("event"))}</span> <span class="dim">{e(when)}</span>'
    if item.get("status") == "blocked" and evidence:
        cell += f'<div class="why">{e(evidence)}</div>'
    return cell


def item_row(item: dict, repo, merged_waiting_ids=frozenset()) -> str:
    status = item.get("status", "")
    deps = L.as_list(item.get("depends"))
    dep = f'<div class="dep">after {e(" ".join(deps))}</div>' if deps else ""
    found = f'<div class="dep">from {e(item["discovered_from"])}</div>' if item.get("discovered_from") else ""
    owner = (f'<div class="dep">owner: {e(item.get("owner"))}</div>'
             if status == "blocked" and item.get("owner") else "")
    merged = ('<div class="dep">merged, awaiting evidence</div>'
              if item.get("id") in merged_waiting_ids else "")
    return (f'<tr class="item" data-id="{e(item.get("id"))}" data-status="{e(status)}">'
            f'<td class="id">{e(item.get("id"))}</td>'
            f'<td>{e(item.get("title"))}{dep}{found}{owner}{merged}</td>'
            f'<td class="tag">{e(item.get("tag") or item.get("cx"))}</td>'
            f'<td><span class="pill {slug(status)}">{e(status)}</span></td>'
            f'<td class="issue">{issue_cell(item.get("issue"), repo)}</td>'
            f'<td class="last">{last_log(item)}</td></tr>')


def phase_section(phase: dict, its_items: list, repo, merged_waiting_ids=frozenset()) -> str:
    counts = {s: 0 for s in STATUS_ORDER}
    for i in its_items:
        if i.get("status") in counts:
            counts[i["status"]] += 1
    head = (f'<section class="phase" data-phase="{e(phase.get("id"))}">'
            f'<h2>{e(phase.get("id"))} · {e(phase.get("name"))} '
            f'<span class="count">{counts["done"]}/{len(its_items)}</span></h2>')
    goal = f'<p class="goal">{e(phase.get("goal"))}</p>' if phase.get("goal") else ""
    exit_ = f'<p class="goal"><b>Exit:</b> {e(phase.get("exit"))}</p>' if phase.get("exit") else ""
    rows = "".join(item_row(i, repo, merged_waiting_ids) for i in its_items)
    table = ('<div class="scroll"><table class="items"><thead><tr><th>ID</th><th>Item</th><th>Tag</th>'
             f'<th>Status</th><th>Issue</th><th>Last</th></tr></thead><tbody>{rows}</tbody></table></div>'
             if its_items else '<p class="empty">No items in this phase.</p>')
    return head + goal + exit_ + bar(counts, "bar") + table + "</section>"


def asks_section(asks: list) -> str:
    if not asks:
        return ""
    rows = []
    for a in asks:
        owner = (f'<div class="dep">owner: {e(a.get("owner"))}</div>'
                 if a.get("state") == "open" and a.get("owner") else "")
        rows.append(
            f'<tr class="ask" data-id="{e(a.get("id"))}" data-state="{e(a.get("state"))}">'
            f'<td class="id">{e(a.get("id"))}</td><td>{e(a.get("kind"))}</td>'
            f'<td>“{e(a.get("quote"))}”</td><td>{e(a.get("became") or "—")}</td>'
            f'<td><span class="pill a-{e(str(a.get("state", "")).replace(" ", "-"))}">{e(a.get("state"))}</span>'
            f'{owner}</td></tr>')
    open_n = sum(1 for a in asks if a.get("state") == "open")
    return (f'<section class="asks"><h2>Asks <span class="count">{open_n} open</span></h2>'
            '<div class="scroll"><table class="items"><thead><tr><th>ID</th><th>Kind</th><th>In his words</th>'
            f'<th>Became</th><th>State</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')


def readiness_section(r: dict | None) -> str:
    """Readiness (D8) as the page's headline number, its four parts --
    work/gates/floors/receipts -- beneath it (proposal 20, V-09; it was small
    grey text beside its label). Only when the ledger declares
    readiness_weights (L.readiness returns None otherwise), and never
    recomputed: r is exactly what L.readiness(ledger) gave."""
    if r is None:
        return ""
    parts = "".join(f"<li>{name} {e(r[name])}</li>" for name in ("work", "gates", "floors", "receipts"))
    return (f'<section class="readiness"><h2>Readiness</h2>'
            f'<p class="headline">{e(r["readiness"])}<span class="unit">%</span></p>'
            f'<ul class="parts">{parts}</ul></section>')


def gates_section(gates: list) -> str:
    if not gates:
        return ""
    rows = "".join(
        f'<tr><td class="id">{e(g.get("id"))}</td><td>{e(g.get("title") or g.get("name"))}</td>'
        f'<td><span class="pill {"s-done" if g.get("passed") else "s-not-started"}">'
        f'{"passed" if g.get("passed") else "not passed"}</span></td></tr>'
        for g in gates if isinstance(g, dict))
    return ('<section class="gates"><h2>Gates</h2><div class="scroll"><table class="items"><thead><tr>'
            '<th>ID</th><th>Gate</th><th>Passed</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></section>')


def floors_section(floors: list) -> str:
    if not floors:
        return ""
    rows = "".join(
        f'<tr><td>{e(f.get("title"))}</td><td><span class="pill {"s-done" if f.get("met") else "s-not-started"}">'
        f'{"met" if f.get("met") else "not met"}</span></td></tr>'
        for f in floors if isinstance(f, dict))
    return ('<section class="floors"><h2>Quality floors</h2><div class="scroll"><table class="items"><thead><tr>'
            '<th>Floor</th><th>Met</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></section>')


def requests_section(requests: list) -> str:
    """Open requests, both directions (D7) -- exactly L.open_requests(ledger),
    which already keeps only the open/in-progress ones."""
    if not requests:
        return ""
    rows = "".join(
        f'<tr class="request" data-id="{e(r.get("id"))}" data-state="{e(r.get("state"))}">'
        f'<td class="id">{e(r.get("id"))}</td><td>{e(r.get("from"))}</td><td>{e(r.get("to"))}</td>'
        f'<td><span class="pill">{e(r.get("state"))}</span></td>'
        f'<td>{e(" ".join(r.get("unblocks") or []))}</td></tr>'
        for r in requests)
    return ('<section class="requests"><h2>Open requests</h2><div class="scroll"><table class="items"><thead><tr>'
            '<th>ID</th><th>From</th><th>To</th><th>State</th><th>Unblocks</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></section>')


def waiting_section(ledger: dict) -> str:
    """Who is blocking whom (D4): every owner named on a blocked row or an
    open ask, with what L.waiting_on(ledger, owner) says they are waiting on."""
    owners = sorted({i.get("owner") for i in L.items(ledger)
                      if i.get("status") == "blocked" and i.get("owner")} |
                     {a.get("owner") for a in (ledger.get("asks") or [])
                      if a.get("state") == "open" and a.get("owner")})
    if not owners:
        return ""
    rows = "".join(
        f'<tr><td class="id">{e(owner)}</td><td>{e(", ".join(L.waiting_on(ledger, owner)))}</td></tr>'
        for owner in owners)
    return ('<section class="waiting"><h2>Waiting on</h2><div class="scroll"><table class="items"><thead><tr>'
            '<th>Owner</th><th>Items and asks</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></section>')


def switches_section(ledger: dict) -> str:
    """Switches the ledger records off (D5) -- on is the default and not
    worth a row; L.switch_on(ledger, name) decides off, never re-derived."""
    switches = ledger.get("switches")
    if not isinstance(switches, dict):
        return ""
    off = [name for name in L.SWITCHES if name in switches and not L.switch_on(ledger, name)]
    if not off:
        return ""
    rows = "".join(
        f'<tr><td class="id">{e(name)}</td><td>{e(switches[name].get("by"))}</td>'
        f'<td>{e(str(switches[name].get("at", ""))[:16].replace("T", " "))}</td></tr>'
        for name in off)
    return ('<section class="switches"><h2>Switches off</h2><div class="scroll"><table class="items"><thead><tr>'
            '<th>Switch</th><th>By</th><th>At</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></section>')


def changes_section(changes: list) -> str:
    if not changes:
        return ""
    rows = "".join(
        f'<tr><td class="last">{e(str(c.get("at", ""))[:16].replace("T", " "))}</td><td>{e(c.get("from"))}</td>'
        f'<td class="id">{e(c.get("item"))}</td><td>{e(c.get("change"))}</td><td>{e(c.get("state"))}</td></tr>'
        for c in changes)
    return ('<section class="changes"><h2>Proposed changes</h2><div class="scroll"><table class="items"><thead><tr>'
            '<th>At</th><th>From</th><th>Item</th><th>Change</th><th>State</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></section>')


def tiers_section(tiers: dict) -> str:
    if not tiers:
        return ""
    rows = "".join(
        f'<tr><td class="id">{e(k)}</td><td>{e(v.get("tier"))}</td><td>{e(v.get("model"))}</td>'
        f'<td>{e(v.get("effort", ""))}</td><td>{e(v.get("rule"))}</td></tr>'
        for k, v in tiers.items())
    return ('<section class="tiers"><h2>Classes</h2><div class="scroll"><table class="items"><thead><tr><th>Class</th>'
            '<th>Tier</th><th>Model</th><th>Effort</th><th>Rule</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></section>')


def priority_section(priority: dict) -> str:
    if not priority or not priority.get("order"):
        return ""
    order = " → ".join(e(x) for x in priority.get("order", []))
    who = e(priority.get("by", ""))
    return (f'<section class="changes"><h2>Priority</h2><p class="goal">{e(priority.get("instruction", ""))}</p>'
            f'<p class="goal"><b>Order:</b> {order} <span class="dim">· set by {who}</span></p></section>')


CSS = """
:root{--ground:#EEF0F2;--surface:#FAFBFC;--ink:#161A1E;--dim:#67707A;--rule:#CDD3D9;
--done:#2F855A;--prog:#D4531F;--block:#B23A48;--todo:#C3CAD1;
--mono:"SF Mono",ui-monospace,Menlo,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ground:#121619;--surface:#1A1F24;--ink:#E5E8EB;
--dim:#909AA4;--rule:#2E363E;--done:#5FB58A;--prog:#F0733E;--block:#D06A77;--todo:#3A434C}}
:root[data-theme="dark"]{--ground:#121619;--surface:#1A1F24;--ink:#E5E8EB;--dim:#909AA4;--rule:#2E363E;
--done:#5FB58A;--prog:#F0733E;--block:#D06A77;--todo:#3A434C}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.5 var(--sans)}
.wrap{max-width:1120px;margin:0 auto;padding:36px 22px 80px}
.head h1{font-size:30px;margin:4px 0 0;letter-spacing:-.01em;text-wrap:balance}
.eyebrow{font:12px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--dim);margin:0}
.status{margin-top:18px}
.line{font:600 15px var(--mono);margin:0 0 8px;font-variant-numeric:tabular-nums}
.overall,.bar{display:flex;height:10px;background:var(--todo);overflow:hidden;border-radius:2px}
.overall{height:14px}
.bar{margin:10px 0 12px}
.seg{display:block;height:100%}
.seg.s-done{background:var(--done)}.seg.s-in-progress{background:var(--prog)}
.seg.s-blocked{background:var(--block)}.seg.s-not-started{background:var(--todo)}.seg.s-empty{background:var(--todo)}
section{margin-top:34px}
h2{font-size:18px;margin:0}
.count{font:500 13px var(--mono);color:var(--dim);margin-left:6px}
.goal{color:var(--dim);margin:6px 0 0;max-width:80ch}
.scroll{overflow-x:auto}
.items{width:100%;border-collapse:collapse;background:var(--surface);font-size:14px}
.items th{text-align:left;font:600 11px var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--dim);
padding:8px 10px;border-bottom:1px solid var(--ink)}
.items td{padding:8px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
.id,.tag,.issue,.last{font-family:var(--mono);font-size:12.5px;white-space:nowrap}
.issue a{color:var(--prog)}
.dep{font:12px var(--mono);color:var(--dim);margin-top:2px}
.why{font:12px var(--sans);color:var(--block);white-space:normal;max-width:48ch;margin-top:3px}
.dim{color:var(--dim)}
.empty{color:var(--dim);font-style:italic}
.pill{display:inline-block;font:600 11.5px var(--mono);padding:1px 7px;border-radius:9px;border:1px solid currentColor;white-space:nowrap}
.pill.s-done,.pill.a-became-item,.pill.a-answered{color:var(--done)}
.pill.s-in-progress,.pill.a-open{color:var(--prog)}
.pill.s-blocked{color:var(--block)}
.pill.s-not-started,.pill.a-declined{color:var(--dim)}
.asks,.changes,.tiers,.phase{display:block}
"""

# Appended to CSS only on a page whose ledger declares readiness, so a page
# without it stays byte for byte what it was (tests/test_tracker_render.py
# TestBackwardCompatibility pins that).
READINESS_CSS = """.readiness{margin-top:22px;padding:18px 20px 16px;background:var(--surface);border-top:3px solid var(--done)}
.readiness h2{font:600 12px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--dim)}
.readiness .headline{font:700 72px/1 var(--sans);letter-spacing:-.02em;margin:6px 0 0;font-variant-numeric:tabular-nums}
.readiness .unit{font-size:36px;font-weight:600;color:var(--dim);margin-left:2px}
.readiness .parts{display:flex;flex-wrap:wrap;gap:4px 22px;list-style:none;padding:0;margin:12px 0 0;
font:500 14px var(--mono);color:var(--dim);font-variant-numeric:tabular-nums}
"""


def render(data: dict, source: Path, repo: str | None) -> str:
    counts = L.counts(data)
    phases = list(data.get("phases") or [])
    known = {p.get("id") for p in phases}
    loose = [i for i in L.items(data) if i.get("phase") not in known]
    if loose:
        phases.append({"id": "", "name": "Unphased"})
    merged_waiting_ids = set(L.merged_waiting(data))
    sections = []
    for p in phases:
        its = [i for i in L.items(data) if (i.get("phase") == p.get("id")) or (p.get("id") == "" and i in loose)]
        sections.append(phase_section(p, its, repo, merged_waiting_ids))
    n, status, title = data.get("proposal"), data.get("status", ""), data.get("title", "")
    readiness = L.readiness(data)
    return (
        f"<!-- generated by bin/tracker render from {e(source.name)} -- edit the ledger, not this page -->\n"
        f"<title>{e(n)} · {e(status)} · {e(title)} · tracker</title>\n"
        f'<meta name="ledger-source" content="{e(source.name)}">\n'
        f'<meta name="ledger-digest" content="{digest(source)}">\n'
        f"<style>{CSS}{READINESS_CSS if readiness is not None else ''}</style>\n"
        '<main class="wrap">'
        f'<header class="head"><p class="eyebrow">Proposal {e(n)} · {e(status)} · updated {e(data.get("updated", ""))}</p>'
        f"<h1>{e(title)}</h1></header>"
        + readiness_section(readiness)
        + f'<section class="status" data-done="{counts["done"]}" data-in-progress="{counts["in progress"]}" '
        f'data-blocked="{counts["blocked"]}" data-not-started="{counts["not started"]}">'
        f'<p class="line">{e(L.status_line(data))}</p>{bar(counts, "overall")}</section>'
        + "".join(sections)
        + asks_section(data.get("asks") or [])
        + gates_section(data.get("gates") or [])
        + floors_section(data.get("quality_floors") or [])
        + requests_section(L.open_requests(data))
        + waiting_section(data)
        + priority_section(data.get("priority") or {})
        + changes_section(data.get("proposed_changes") or [])
        + tiers_section(data.get("tiers") or {})
        + switches_section(data)
        + "</main>\n"
    )


def freshness(ledger_path: Path, page: Path) -> str:
    """"ok", "missing", or "stale": does the page carry this ledger's digest?"""
    if not page.exists():
        return "missing"
    m = re.search(r'<meta name="ledger-digest" content="([0-9a-f]{64})">', page.read_text(errors="replace"))
    return "ok" if m and m.group(1) == digest(ledger_path) else "stale"


# ---------------------------------------------------------------------------
# tracker published (proposal 20, V-09, D1)
#
# An artifact is published only through a Claude session's Artifact tool; no
# hook or script can call it. So nothing here publishes. The session
# publishes the page, then runs `tracker published` to record what went out:
# a committed sidecar beside the page,
#
#   docs/proposals/tracker/<ledger stem>.published.json
#   {"at": "<real clock, with offset>", "by": "<name>" | null,
#    "digest": "<sha256 of the page file as published>", "url": "https://..."}
#
# and bin/warmup names the page when its bytes no longer match that digest.
# The digest is of the page, not the ledger: a page that changed because the
# renderer did is also a page the published copy no longer matches.

def published_path(ledger_path: Path) -> Path:
    return default_out(ledger_path).with_name(f"{ledger_path.stem}.published.json")


def _one_line_utf8(s: str) -> bool:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:           # a lone surrogate
        return False
    return not any(ord(c) < 32 or 127 <= ord(c) < 160 for c in s)


def url_problem(url) -> str | None:
    """None for one line of https://host..., else what is wrong -- never
    echoing the value, which is untrusted and may carry a forged line."""
    if not isinstance(url, str) or not url:
        return "url must be a non-empty string"
    if not _one_line_utf8(url) or any(c.isspace() for c in url):
        return "url must be one line of UTF-8 with no spaces or control characters"
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return "url is not a URL"
    if parts.scheme != "https" or not host:
        return "url must be https://<host>/..."
    return None


def published_problems(record) -> list[str]:
    """What is wrong with a sidecar's contents, without echoing any value."""
    if not isinstance(record, dict):
        return ["not a JSON object"]
    out = []
    for key in ("url", "digest", "at", "by"):
        if key not in record:
            out.append(f"no {key!r}")
    if "url" in record and url_problem(record["url"]):
        out.append(url_problem(record["url"]))
    if "digest" in record and not (isinstance(record["digest"], str)
                                   and re.fullmatch(r"[0-9a-f]{64}", record["digest"])):
        out.append("digest must be 64 lowercase hex characters")
    if "at" in record:
        import datetime
        at = record["at"]
        try:
            ok = (isinstance(at, str) and _one_line_utf8(at)
                  and datetime.datetime.fromisoformat(at).tzinfo is not None)
        except ValueError:
            ok = False
        if not ok:
            out.append("at must be an ISO 8601 time with its offset")
    if "by" in record and record["by"] is not None and not (
            isinstance(record["by"], str) and record["by"].strip() and _one_line_utf8(record["by"])):
        out.append("by must be null or a one-line name")
    return out


def published_main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker published",
                                 description="record the page a session just published with its Artifact tool")
    ap.add_argument("ledger", type=Path)
    ap.add_argument("--url", required=True, help="the artifact's URL, https, one line")
    ap.add_argument("--by", help="who published it (default: recorded as null)")
    args = ap.parse_args(argv)
    say = "tracker published:"

    try:
        data = L.load(args.ledger)
    except (OSError, ValueError) as exc:
        print(f"{say} {exc!r}", file=sys.stderr)
        return 2
    if not L.switch_on(data, "publish"):
        sw = data["switches"]["publish"]
        print(f"{say} publish is switched off in {args.ledger.name} by {sw.get('by')!r} at {sw.get('at')!r} "
              "-- nothing recorded, and nothing should have been published", file=sys.stderr)
        return 1
    problem = url_problem(args.url)
    if problem:
        print(f"{say} {problem} (got {args.url!r}) -- nothing recorded", file=sys.stderr)
        return 1
    if args.by is not None and not (args.by.strip() and _one_line_utf8(args.by)):
        print(f"{say} --by must be a one-line name (got {args.by!r}) -- nothing recorded", file=sys.stderr)
        return 1
    page = default_out(args.ledger)
    fresh = freshness(args.ledger, page)
    if fresh != "ok":
        print(f"{say} {page} is {fresh} against {args.ledger.name} -- render first: tracker render {args.ledger}, "
              "publish that page, then record it", file=sys.stderr)
        return 1

    import datetime
    record = {"url": args.url, "digest": digest(page),
              "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "by": args.by}
    sidecar = published_path(args.ledger)
    sidecar.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"recorded {sidecar} · {args.url} · commit it")
    return 0


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker render", description=__doc__.splitlines()[0])
    ap.add_argument("ledger", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--repo", help="owner/name for issue links (default: the ledger's git remote)")
    ap.add_argument("--check", action="store_true", help="exit 1 if the page is missing or stale; write nothing")
    args = ap.parse_args(argv)

    try:
        data = L.load(args.ledger)
    except (OSError, ValueError) as exc:
        print(f"tracker render: {exc}", file=sys.stderr)
        return 2
    out = args.out or default_out(args.ledger)

    if args.check:
        fresh = freshness(args.ledger, out)
        if fresh == "missing":
            print(f"stale: {out} is missing -- run: tracker render {args.ledger}")
            return 1
        if fresh == "stale":
            print(f"stale: {out} was rendered from a different {args.ledger.name} -- run: tracker render {args.ledger}")
            return 1
        print(f"ok {out} matches {args.ledger.name}")
        return 0

    problems = L.validate(data)
    if problems:
        print(f"tracker render: {args.ledger} is not well-formed; a page of it would show numbers nobody can trust:",
              file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    repo = args.repo or infer_repo(args.ledger)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = render(data, args.ledger, repo)
    if not out.exists() or out.read_text() != text:
        out.write_text(text)
    print(f"rendered {out} · {L.status_line(data)}")
    return 0
