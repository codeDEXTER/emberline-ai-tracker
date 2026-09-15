"""Shared transcript-reading primitives for `bin/spend` and `bin/worklog`
(common-rules proposal 27).

Both tools read the same on-disk shape -- session transcripts under
`~/.claude/projects/<project>/<session>.jsonl`, plus subagent transcripts at
`<project>/<session>/subagents/*.jsonl` that `spend` never read before this
module existed, so a session's real cost never included what its subagents
did. This module is the one place that knows that shape, so a fix to either
detail (the subagent path, or the streamed-record dedupe below) only has to
be made once.

Streamed responses write the same `message.id` several times as usage grows
-- roughly 3.6 records per message, measured 2026-08-07 -- so anything that
sums `usage` across every record overstates token counts by about that
factor. `dedupe_messages` collapses that to one record per `message.id`,
keeping the last (largest, final) usage seen.

Nothing here ever returns transcript prose. Callers that need an item id
from a user prompt (`bin/worklog`) do that extraction themselves, from a
single line already read via `iter_records` -- this module does not retain
or forward message text.
"""
from __future__ import annotations

import datetime
import glob
import html
import json
import os
import re

PROJECTS = os.path.expanduser("~/.claude/projects")
COMMON_RULES_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(COMMON_RULES_ROOT, "worklog")
ACTIVE_GAP_MAX_SECONDS = 5 * 60

# List price, USD per million tokens. Anthropic's pricing changes
# independently of this file -- edit the numbers here when it does.
PRICES = {
    "opus":   {"in": 15.0, "cache_write": 18.75, "cache_read": 1.50, "out": 75.0},
    "sonnet": {"in": 3.0,  "cache_write": 3.75,  "cache_read": 0.30, "out": 15.0},
    "haiku":  {"in": 1.0,  "cache_write": 1.25,  "cache_read": 0.10, "out": 5.0},
}


def price_family(model):
    """Which row of PRICES a model string falls under. Unknown models are
    priced as sonnet -- the mid-tier -- rather than raising, since a model
    name can change shape before this table is updated."""
    m = (model or "").lower()
    if "opus" in m:
        return "opus"
    if "haiku" in m:
        return "haiku"
    return "sonnet"


def list_transcripts(projects=None):
    """Yield (project_dir_name, session_id, path) for every transcript on
    this machine -- main-session files and subagent files alike.

    Subagent transcripts live at `<project>/<session>/subagents/*.jsonl`,
    one file per subagent invocation, named by an agent id rather than the
    session id -- so `session_id` here is the *parent* session's id, taken
    from the directory structure, not the filename.
    """
    root = projects or PROJECTS
    for path in glob.glob(os.path.join(root, "*", "*.jsonl")):
        session = os.path.splitext(os.path.basename(path))[0]
        yield os.path.basename(os.path.dirname(path)), session, path
    for path in glob.glob(os.path.join(root, "*", "*", "subagents", "*.jsonl")):
        parts = path.split(os.sep)
        # .../<project>/<session>/subagents/<file>.jsonl
        yield parts[-4], parts[-3], path


def iter_records(path):
    """Yield parsed JSON records from one transcript, skipping bad lines."""
    with open(path, errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def dedupe_messages(records):
    """Collapse streamed records to one per `message.id`, last write wins.

    Yields (record, message, usage) triples, in first-seen order of each
    id. Records without a `message.id` (older transcripts, or non-usage
    records) are each kept as their own entry rather than dropped, keyed by
    their position -- so they never collide with a real id.
    """
    order = []
    latest = {}
    for i, rec in enumerate(records):
        msg = rec.get("message")
        if not isinstance(msg, dict):
            continue
        usage = msg.get("usage")
        if not usage:
            continue
        mid = msg.get("id") or f"__noid_{i}"
        if mid not in latest:
            order.append(mid)
        latest[mid] = (rec, msg, usage)
    for mid in order:
        yield latest[mid]


def usage_tokens(usage):
    """(input, cache_write, cache_read, output) from one usage dict."""
    return (
        usage.get("input_tokens", 0) or 0,
        usage.get("cache_creation_input_tokens", 0) or 0,
        usage.get("cache_read_input_tokens", 0) or 0,
        usage.get("output_tokens", 0) or 0,
    )


def list_price(model, inp, cache_write, cache_read, out):
    """List price in USD for one message's usage. See PRICES above."""
    p = PRICES[price_family(model)]
    return (inp * p["in"] + cache_write * p["cache_write"]
            + cache_read * p["cache_read"] + out * p["out"]) / 1_000_000


# ---------------------------------------------------------------------------
# `bin/worklog collect` -- W-02.
#
# Sponsor decisions (proposal 27, D1-D4, D6): a folder revisioned under
# common-rules holding daily JSON-lines files, updated incrementally, task
# named from the brief tag then the branch then the session, active time
# with gaps over five minutes left out.
# ---------------------------------------------------------------------------

GROUP_FIELDS = ("day", "project", "session", "agent", "model", "item")

# A brief tag line like `[ruflo · C2 · sonnet] W-01 ...`, or a bare item id
# (`X-NN`) opening the prompt. Only ever matched against the first user
# record already parsed by `iter_records` -- the match (a handful of
# characters) is the only thing kept; the rest of the prompt is discarded
# with the record it came from.
_TAG_ITEM_RE = re.compile(r"^\[[^\]]*\]\s*([A-Za-z][A-Za-z0-9]*-\d+)")
_LEADING_ITEM_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*-\d+)\b")


def _first_user_text(records):
    """The first user-role prompt in `records`, as plain text, or None.

    Only ever called to look for a leading item tag -- the string is never
    stored or returned beyond that regex match.
    """
    for rec in records:
        msg = rec.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text") or ""
        return None
    return None


def derive_item_id(records, branch=None, session=None):
    """Which task a transcript's tokens belong to.

    First a brief tag or bare item id at the very start of the first user
    prompt, else the git branch recorded on any of its records, else the
    session id. Never the prompt text itself -- see `_first_user_text`.
    """
    text = _first_user_text(records)
    if text:
        stripped = text.strip()
        m = _TAG_ITEM_RE.match(stripped) or _LEADING_ITEM_RE.match(stripped)
        if m:
            return m.group(1)
    if branch:
        return branch
    return session or "unknown"


def _parse_ts(ts):
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None


def _gap_seconds(prev_ts, ts):
    a, b = _parse_ts(prev_ts), _parse_ts(ts)
    if a is None or b is None:
        return None
    return (b - a).total_seconds()


def _default_state_path(out_dir):
    return os.path.join(out_dir, ".state.json")


def load_state(state_path):
    if os.path.exists(state_path):
        try:
            with open(state_path) as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            state = {}
    else:
        state = {}
    state.setdefault("transcripts", {})
    state.setdefault("messages", {})
    state.setdefault("groups", {})
    return state


def save_state(state_path, state):
    os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
    tmp = state_path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    os.replace(tmp, state_path)


def _row_key(day, project, session, agent, model, item):
    return "\x01".join((day, project, session, agent, model, item))


def _load_day_file(path):
    rows = {}
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                key = _row_key(*(row.get(f, "") for f in GROUP_FIELDS))
                rows[key] = row
    return rows


def _write_day_file(path, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    ordered = sorted(
        rows.values(),
        key=lambda r: (r["project"], r["session"], r["agent"], r["item"]))
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        for row in ordered:
            out_row = {f: row[f] for f in GROUP_FIELDS}
            out_row["input_tokens"] = row["input_tokens"]
            out_row["cache_write_tokens"] = row["cache_write_tokens"]
            out_row["cache_read_tokens"] = row["cache_read_tokens"]
            out_row["output_tokens"] = row["output_tokens"]
            out_row["active_seconds"] = row["active_seconds"]
            out_row["cost_usd"] = round(list_price(
                row["model"], row["input_tokens"], row["cache_write_tokens"],
                row["cache_read_tokens"], row["output_tokens"]), 6)
            fh.write(json.dumps(out_row, sort_keys=True) + "\n")
    os.replace(tmp, path)


def collect(projects=None, out=None, state_file=None):
    """Read every transcript's new lines since the last run, and merge their
    token usage and active time into `<out>/<day>.jsonl`.

    Incremental by byte offset per transcript (`state["transcripts"]`), and
    by `message.id` within a transcript (`state["messages"]`) -- a message
    already contributed once, that grows across two collector runs (a
    streamed response mid-write when `collect` last ran), contributes only
    the *delta* the second time, so a re-run never double-counts. Re-running
    with no new bytes anywhere changes nothing on disk.

    Returns {"days": [...], "lines": n, "transcripts": n} -- never any
    transcript text.
    """
    projects_dir = projects or PROJECTS
    out_dir = out or DEFAULT_OUT
    state_path = state_file or _default_state_path(out_dir)
    state = load_state(state_path)
    tstate, mstate, gstate = state["transcripts"], state["messages"], state["groups"]

    day_deltas = {}   # day -> gkey -> {"group": (...), "input":.., ...}
    touched_days = set()
    transcripts_seen = 0

    for project, session, path in list_transcripts(projects_dir):
        kind = "subagent" if (os.sep + "subagents" + os.sep) in path else "main"
        rec_path = os.path.realpath(path)
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        info = tstate.get(rec_path, {})
        offset = info.get("offset", 0)
        if size < offset:
            offset = 0
        if size <= offset:
            continue

        with open(path, "rb") as fh:
            fh.seek(offset)
            chunk = fh.read()
        last_nl = chunk.rfind(b"\n")
        if last_nl == -1:
            continue  # no complete line written since the last run yet
        usable = chunk[:last_nl + 1]
        new_offset = offset + len(usable)

        records = []
        for line in usable.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue

        transcripts_seen += 1
        branch = info.get("branch")
        agent = info.get("agent")
        model_hint = info.get("model")
        for rec in records:
            branch = branch or rec.get("gitBranch")
            agent = agent or rec.get("attributionAgent")

        item = info.get("item")
        if item is None:
            # Derived only on the transcript's first-ever batch (offset 0):
            # that is the only time the first user record is guaranteed to
            # be in `records`. A transcript whose state was lost mid-way
            # falls back to the session id rather than mis-scanning later
            # records for a tag that was never meant for them.
            item = (derive_item_id(records, branch=branch, session=session)
                    if offset == 0 else session)

        if not records:
            tstate[rec_path] = {"offset": new_offset, "item": item,
                                 "branch": branch, "agent": agent,
                                 "model": model_hint}
            continue

        agent_final = agent or ("lead" if kind == "main" else "subagent")

        for rec, msg, usage in dedupe_messages(records):
            mid = msg.get("id")
            model = msg.get("model") or model_hint or "unknown"
            model_hint = model_hint or model
            i, cw, cr, o = usage_tokens(usage)
            ts = rec.get("timestamp") or ""
            day = ts[:10] if ts else "unknown"
            group = (day, project, session, agent_final, model, item)
            gkey = _row_key(*group)

            prev = mstate.get(mid) if mid else None
            if prev is None:
                di, dcw, dcr, do = i, cw, cr, o
            else:
                di = i - prev.get("i", 0)
                dcw = cw - prev.get("cw", 0)
                dcr = cr - prev.get("cr", 0)
                do = o - prev.get("o", 0)

            bucket = day_deltas.setdefault(day, {}).setdefault(
                gkey, {"group": group, "input": 0, "cache_write": 0,
                       "cache_read": 0, "output": 0, "active": 0.0})
            bucket["input"] += di
            bucket["cache_write"] += dcw
            bucket["cache_read"] += dcr
            bucket["output"] += do
            touched_days.add(day)

            if mid:
                mstate[mid] = {"i": i, "cw": cw, "cr": cr, "o": o}

            if ts:
                g = gstate.setdefault(gkey, {})
                last_ts = g.get("last_ts")
                if last_ts:
                    gap = _gap_seconds(last_ts, ts)
                    if gap is not None and 0 < gap <= ACTIVE_GAP_MAX_SECONDS:
                        bucket["active"] += gap
                g["last_ts"] = ts

        tstate[rec_path] = {"offset": new_offset, "item": item,
                             "branch": branch, "agent": agent,
                             "model": model_hint}

    lines_written = 0
    for day in sorted(touched_days):
        day_file = os.path.join(out_dir, f"{day}.jsonl")
        existing = _load_day_file(day_file)
        for gkey, delta in day_deltas[day].items():
            group = delta["group"]
            row = existing.get(gkey)
            if row is None:
                row = {f: v for f, v in zip(GROUP_FIELDS, group)}
                row.update(input_tokens=0, cache_write_tokens=0,
                           cache_read_tokens=0, output_tokens=0,
                           active_seconds=0)
                existing[gkey] = row
            row["input_tokens"] += delta["input"]
            row["cache_write_tokens"] += delta["cache_write"]
            row["cache_read_tokens"] += delta["cache_read"]
            row["output_tokens"] += delta["output"]
            row["active_seconds"] += int(round(delta["active"]))
        _write_day_file(day_file, existing)
        lines_written += len(existing)

    save_state(state_path, state)
    return {"days": sorted(touched_days), "lines": lines_written,
            "transcripts": transcripts_seen}


# ---------------------------------------------------------------------------
# `bin/worklog day` / `yesterday-line` -- W-04 (page part).
# ---------------------------------------------------------------------------

def load_day(out_dir, date):
    """Every row recorded for one date, or [] if nothing was collected."""
    path = os.path.join(out_dir, f"{date}.jsonl")
    rows = []
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
    return rows


def day_summary(rows):
    """Aggregate figures for one day's rows -- what both the page and the
    one-line /warmup summary are built from."""
    def total(rs):
        return sum(r["input_tokens"] + r["cache_write_tokens"]
                   + r["cache_read_tokens"] + r["output_tokens"] for r in rs)
    lead_rows = [r for r in rows if r.get("agent") == "lead"]
    agent_rows = [r for r in rows if r.get("agent") != "lead"]
    return {
        "tokens": total(rows),
        "cost": sum(r.get("cost_usd", 0) for r in rows),
        "active_seconds": sum(r.get("active_seconds", 0) for r in rows),
        "tasks": sorted({r["item"] for r in rows}),
        "sessions": sorted({r["session"] for r in rows}),
        "projects": sorted({r["project"] for r in rows}),
        "lead_tokens": total(lead_rows),
        "agent_tokens": total(agent_rows),
    }


def format_yesterday_line(rows):
    s = day_summary(rows)
    hours = s["active_seconds"] / 3600
    return (f"yesterday: {s['tokens']:,} tokens · ${s['cost']:.2f} · "
            f"{hours:.1f}h active · {len(s['tasks'])} tasks")


def format_day_text(date, rows):
    s = day_summary(rows)
    hours = s["active_seconds"] / 3600
    lines = [
        f"worklog {date}",
        f"  tokens: {s['tokens']:,} (lead {s['lead_tokens']:,} / "
        f"agents {s['agent_tokens']:,})",
        f"  cost: ${s['cost']:.2f} (list price)",
        f"  active: {hours:.1f}h",
        f"  projects: {len(s['projects'])}  sessions: {len(s['sessions'])}  "
        f"tasks: {len(s['tasks'])}",
    ]
    return "\n".join(lines)


def render_day_html(date, rows):
    """A self-contained HTML page for one day -- tasks, sessions, projects,
    lead vs agent split, the four token kinds, cost, active time.

    Every value that reaches this markup ultimately traces back to a
    transcript -- a git branch name, a session id, a brief tag -- none of
    it is trusted. Every field is `html.escape`d at the point it is
    written, never assembled by string concatenation first.
    """
    s = day_summary(rows)
    hours = s["active_seconds"] / 3600

    def esc(v):
        return html.escape(str(v), quote=True)

    by_task = {}
    for r in rows:
        by_task.setdefault(r["item"], []).append(r)

    task_rows = []
    for item in sorted(by_task):
        rs = by_task[item]
        tokens = sum(r["input_tokens"] + r["cache_write_tokens"]
                     + r["cache_read_tokens"] + r["output_tokens"] for r in rs)
        cost = sum(r.get("cost_usd", 0) for r in rs)
        active = sum(r.get("active_seconds", 0) for r in rs) / 3600
        sessions = {r["session"] for r in rs}
        task_rows.append(
            f"<tr><td>{esc(item)}</td><td>{esc(rs[0]['project'])}</td>"
            f"<td>{len(sessions)}</td><td>{tokens:,}</td>"
            f"<td>${cost:.2f}</td><td>{active:.1f}h</td></tr>")

    row_rows = []
    for r in sorted(rows, key=lambda r: (r["project"], r["session"], r["agent"], r["item"])):
        row_rows.append(
            "<tr>"
            f"<td>{esc(r['project'])}</td><td>{esc(r['session'])}</td>"
            f"<td>{esc(r['agent'])}</td><td>{esc(r['model'])}</td>"
            f"<td>{esc(r['item'])}</td>"
            f"<td>{r['input_tokens']:,}</td><td>{r['cache_read_tokens']:,}</td>"
            f"<td>{r['cache_write_tokens']:,}</td><td>{r['output_tokens']:,}</td>"
            f"<td>${r.get('cost_usd', 0):.2f}</td>"
            f"<td>{r.get('active_seconds', 0) / 3600:.2f}h</td>"
            "</tr>")

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>worklog {esc(date)}</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ text-align: left; padding: 4px 10px 4px 0; border-bottom: 1px solid #ddd; }}
th {{ color: #666; font-size: 0.8em; text-transform: uppercase; }}
h1 {{ margin-bottom: 0.2em; }}
.summary {{ color: #444; margin-bottom: 1.5em; }}
</style>
</head>
<body>
<h1>worklog &middot; {esc(date)}</h1>
<p class="summary">
{s['tokens']:,} tokens (lead {s['lead_tokens']:,} / agents {s['agent_tokens']:,})
&middot; ${s['cost']:.2f} list price
&middot; {hours:.1f}h active
&middot; {len(s['projects'])} project(s), {len(s['sessions'])} session(s),
{len(s['tasks'])} task(s)
</p>
<h2>by task</h2>
<table>
<tr><th>task</th><th>project</th><th>sessions</th><th>tokens</th><th>cost</th><th>active</th></tr>
{''.join(task_rows)}
</table>
<h2>every request group</h2>
<table>
<tr><th>project</th><th>session</th><th>agent</th><th>model</th><th>task</th>
<th>input</th><th>cache-r</th><th>cache-w</th><th>output</th><th>cost</th><th>active</th></tr>
{''.join(row_rows)}
</table>
</body>
</html>
"""
    return html_doc
