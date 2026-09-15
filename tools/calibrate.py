"""Point-class cost calibration -- `bin/spend calibrate` (common-rules
proposal 25, Z-05).

Every 20 closed (done) items across every ledger under a project, this
groups their measured cost (from `tools/worklog.py`'s transcript-derived
totals, keyed by item id -- the same numbers `bin/worklog day` renders,
never transcript prose) by the item's `points` class (proposal 25's Z-01
field: one of `tools.tracker.ledger.POINTS`), computes each class's median
cost, and flags any item whose own cost is over twice its class's median.

State: `<out>/.calibration-state.json` records `last_calibrated_at`, the
closed-item count as of the last run -- the same directory, atomic-write
(`os.replace` over a `.tmp` file) shape `tools/worklog.py`'s own
`.state.json` already uses for `collect`'s incremental offsets. A run only
does anything once the closed-item count has crossed a multiple of 20 since
that count (`force=True` bypasses the wait, for testing and for a sponsor
who wants a calibration right now).

A flagged run is a fact worth keeping even when nobody is looking at the
moment: `<out>/calibration-log.jsonl` gets one line per run, append-only,
naming every item flagged, its class median and its own cost. Kept
alongside the state file rather than staged into any ledger's own log --
this tool runs unattended (from `bin/spend calibrate`, possibly by any
session, on any of several ledgers owned by other bundles at once) and the
ledger is single-writer (proposal 23, M-04): auto-staging a change into
every flagged item's own ledger on every session's behalf is a heavier
claim than a read-only measurement should make on its own. A lead who acts
on a flagged item stages that decision itself, quoting this log.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import statistics
from pathlib import Path

from tools import worklog
from tools.tracker import ledger as L

CALIBRATE_EVERY = 20
FLAG_MULTIPLE = 2.0


def _state_path(out_dir) -> str:
    return os.path.join(out_dir, ".calibration-state.json")


def _log_path(out_dir) -> str:
    return os.path.join(out_dir, "calibration-log.jsonl")


def load_state(out_dir) -> dict:
    """{"last_calibrated_at": int}. A missing or corrupt state file starts
    from 0 -- unlike `collect`'s `.state.json`, losing this only risks one
    redundant (idempotent) recomputation, never a doubled figure, so there
    is nothing here worth refusing over."""
    path = _state_path(out_dir)
    if not os.path.exists(path):
        return {"last_calibrated_at": 0}
    try:
        with open(path) as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return {"last_calibrated_at": 0}
    if not isinstance(state, dict):
        return {"last_calibrated_at": 0}
    state.setdefault("last_calibrated_at", 0)
    return state


def save_state(out_dir, state: dict) -> None:
    path = _state_path(out_dir)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)


def closed_items(project) -> list[tuple[Path, dict]]:
    """(ledger_path, item) for every `status: "done"` item across every
    ledger `tools.tracker.ledger.find` sees under `project` -- an item in a
    still-open ledger counts too; only the item's own status matters. A
    ledger that fails to parse is skipped, like `checkpoint.open_ledgers`
    does, rather than aborting every other ledger's count."""
    out: list[tuple[Path, dict]] = []
    for path in L.find(project):
        try:
            data = L.load(path)
        except (OSError, ValueError):
            continue
        for item in data.get("items", []):
            if item.get("status") == "done":
                out.append((path, item))
    return out


def tokens_by_item(worklog_out=None) -> dict[str, int]:
    """item id -> total tokens (all four kinds, every day file in
    `worklog_out`) that `bin/worklog collect` has recorded for it. Reads
    only the day files' own numeric fields -- never transcript text, the
    same guarantee `tools/worklog.py` itself carries."""
    out_dir = worklog_out or worklog.DEFAULT_OUT
    totals: dict[str, int] = {}
    for path in sorted(glob.glob(os.path.join(out_dir, "*.jsonl"))):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                item = row.get("item")
                if not item:
                    continue
                tokens = (row.get("input_tokens", 0) + row.get("cache_write_tokens", 0)
                          + row.get("cache_read_tokens", 0) + row.get("output_tokens", 0))
                totals[item] = totals.get(item, 0) + tokens
    return totals


def calibrate(project=".", worklog_out=None, out=None, force=False) -> dict:
    """One calibration pass, only actually computed once the closed-item
    count has crossed a multiple of `CALIBRATE_EVERY` since the last run
    (`force=True` runs regardless -- testing, or a sponsor who wants one
    now).

    Returns:
      {"ran": bool, "closed": N, "last_calibrated_at": N,
       "flagged": [{"item", "ledger", "points", "tokens", "class_median",
                     "multiple"}, ...],
       "medians": {points: median}, "skipped_no_data": [item_id, ...]}

    `skipped_no_data` -- a closed item with no `points`, or no worklog rows
    yet (a task nothing has ever collected tokens for) -- is not silently
    counted as zero cost; excluded from its class's median rather than
    dragging it down.
    """
    out_dir = out or worklog_out or worklog.DEFAULT_OUT
    state = load_state(out_dir)
    last = state["last_calibrated_at"]

    items = closed_items(project)
    n = len(items)

    if not force and (n // CALIBRATE_EVERY) <= (last // CALIBRATE_EVERY):
        return {"ran": False, "closed": n, "last_calibrated_at": last,
                "flagged": [], "medians": {}, "skipped_no_data": []}

    # `worklog_out` (where `bin/worklog collect` writes) and `out` (where
    # this calibration's own state/log live) default to the same directory
    # -- only pass them separately when the two genuinely diverge.
    totals = tokens_by_item(worklog_out or out_dir)

    by_class: dict[int, list[int]] = {}
    item_costs: list[tuple[Path, str, int, int]] = []
    skipped: list[str] = []
    for path, item in items:
        item_id = item.get("id")
        points = item.get("points")
        tokens = totals.get(item_id) if item_id else None
        if not isinstance(points, int) or tokens is None:
            if item_id:
                skipped.append(item_id)
            continue
        by_class.setdefault(points, []).append(tokens)
        item_costs.append((path, item_id, points, tokens))

    medians = {points: statistics.median(costs) for points, costs in by_class.items()}

    flagged = []
    for path, item_id, points, tokens in item_costs:
        median = medians[points]
        if median > 0 and tokens > FLAG_MULTIPLE * median:
            flagged.append({
                "item": item_id, "ledger": str(path), "points": points,
                "tokens": tokens, "class_median": median,
                "multiple": round(tokens / median, 2),
            })

    state["last_calibrated_at"] = n
    save_state(out_dir, state)

    record = {
        "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "closed_items": n,
        "classes": {str(points): median for points, median in medians.items()},
        "flagged": flagged, "skipped": skipped,
    }
    log_path = _log_path(out_dir)
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a") as fh:
        fh.write(json.dumps(record) + "\n")

    return {"ran": True, "closed": n, "last_calibrated_at": n,
            "flagged": flagged, "medians": medians, "skipped_no_data": skipped}
