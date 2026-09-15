"""tracker rescore -- 14-day next_check dates for tail-lane items (proposal
26, C-04; A-07: "P26 D6" answered "B - 14 days").

A "tail" item is one tools/tracker/lanes.py's 80% cut already puts in Daily,
Weekly or When touched (never Now, and never Unscored -- an item with no
risk has nothing to schedule a re-check against). Each such item carries
`next_check`, an ISO date 14 days out from when it *entered* that lane:

  assign(ledger, project, today) -> [item ids changed]

    sets `next_check` = today + 14 days on a tail item that does not already
    carry one (so re-running rescore after the date has passed does not keep
    pushing it out -- the date is fixed at entry, not renewed on every run);
    clears `next_check` on an item that has left the tail (back to Now,
    finished, or no longer scored) so a stale date does not outlive its lane.

  overdue(item, today) -> bool
  overdue_items(ledger, today) -> [item, ...]

    an item whose `next_check` has passed -- read by tools/tracker/board.py
    (the lane groups) and bin/warmup (the warm card), neither of which
    re-derives the date logic; both call this module.

  tracker rescore LEDGER [--project DIR] [--at DATE] [--json]
    writes next_check as `assign` computes it (the same direct-write shape
    as tools/tracker/findings.py's add/decide/defer/decline -- a write
    primitive for a project's dispatcher to run, distinct from the
    forbidden-to-an-item-lead `tracker set`/`tracker ask`).

Exit codes: 0 written/printed, 2 could not read/write the ledger.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from tools.tracker import lanes as LANES
from tools.tracker import ledger as L
from tools.tracker import render as R

TAIL_LANES = ("Daily", "Weekly", "When touched")
DAYS_OUT = 14


def tail_lane(lane: str | None) -> bool:
    return lane in TAIL_LANES


def assign(ledger: dict, project, today: datetime.date) -> list[str]:
    """Mutates `ledger`'s items in place; returns the ids changed."""
    result = LANES.lanes(L.items(ledger), project)
    lane_by_id = {r["id"]: r["lane"] for r in result["items"]}
    changed = []
    for item in L.items(ledger):
        lane = lane_by_id.get(item.get("id"))
        if tail_lane(lane):
            if not item.get("next_check"):
                item["next_check"] = (today + datetime.timedelta(days=DAYS_OUT)).isoformat()
                changed.append(item["id"])
        elif item.get("next_check"):
            del item["next_check"]
            changed.append(item["id"])
    return changed


def overdue(item: dict, today: datetime.date) -> bool:
    nc = item.get("next_check")
    if not isinstance(nc, str):
        return False
    try:
        due = datetime.date.fromisoformat(nc)
    except ValueError:
        return False
    return due < today


def overdue_items(ledger: dict, today: datetime.date) -> list[dict]:
    return [i for i in L.items(ledger) if overdue(i, today)]


# ---------------------------------------------------------------------------
# CLI

def _write(ledger_path: Path, data: dict) -> None:
    data["updated"] = datetime.date.today().isoformat()
    out = R.default_out(ledger_path)
    repo = R.infer_repo(ledger_path)
    text = R.render(data, ledger_path, repo)
    ledger_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_text() != text:
        out.write_text(text)


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker rescore", description=__doc__.splitlines()[0])
    ap.add_argument("ledger", type=Path)
    ap.add_argument("--project", type=Path)
    ap.add_argument("--at", help="the date rescore runs as (default: today)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    say = "tracker rescore:"

    try:
        data = L.load(args.ledger)
    except (OSError, ValueError) as exc:
        print(f"{say} {exc}", file=sys.stderr)
        return 2

    today = datetime.date.fromisoformat(args.at) if args.at else datetime.date.today()
    from tools.tracker import route as ROUTE
    project = args.project or ROUTE.project_of(args.ledger)
    changed = assign(data, project, today)

    problems = L.validate(data)
    if problems:
        print(f"{say} {args.ledger} would not be well-formed after this change -- nothing written:",
              file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 2

    if changed:
        _write(args.ledger, data)
    if args.json:
        print(json.dumps({"changed": changed}, ensure_ascii=False))
    else:
        print(f"{say} {len(changed)} item(s) changed" + (f": {', '.join(changed)}" if changed else "")
              + (" · page rendered" if changed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
