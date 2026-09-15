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

import glob
import json
import os

PROJECTS = os.path.expanduser("~/.claude/projects")

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
