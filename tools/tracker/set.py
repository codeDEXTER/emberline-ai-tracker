"""tracker set -- one-line ledger updates, in place of an inline `python3 -`
script that loads a ledger, changes one item and dumps it back (proposal 23,
lever L4, L-04).

  tracker set LEDGER ITEM_ID [--status S] [--owner O] [--field KEY=VALUE ...]
                              [--event TEXT [--evidence TEXT]]
                              [--by NAME] [--at ISO8601]

Changes only what is given. `--field` values parse as JSON when the value is
valid JSON (so `--field weight=2` writes the number 2, `--field flag=true`
writes true), else they are stored as the string given; `--field` may not
touch `id`, `log` or `phase` -- those are this command's own business, or an
identity nothing should rewrite.

`--status` without `--event` appends a log entry whose event is the new
status; `--event` (with or without `--status`) appends a log entry with that
text instead. `--by` names who logged it (default "lead"); `--at` is the
log entry's own time, ISO 8601 with an offset (default: now, local, seconds
precision).

The ledger is validated with the change already applied, before anything is
written: on any problem the problems are printed and the file is untouched
(exit 1). An unknown item id is the same -- exit 1, nothing written. On
success the ledger is written (indent=2, ensure_ascii=False, trailing
newline -- the format the engine's own ledgers already use), `updated` moves
to today, and the page is re-rendered with tools/tracker/render.py so the
page never falls behind the ledger it was set from.

Exit codes: 0 written, 1 a finding (or nothing to check against), 2 could
not read the ledger.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from tools.tracker import ledger as L
from tools.tracker import render as R

FORBIDDEN_FIELDS = frozenset({"id", "log", "phase"})


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_field(raw: str) -> tuple[str, object, str] | None:
    """"KEY=VALUE" -> (key, parsed value, the value text as given), or None
    when there is no `=`."""
    if "=" not in raw:
        return None
    key, _, value = raw.partition("=")
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        parsed = value
    return key, parsed, value


def _render(data: dict, path: Path) -> None:
    out = R.default_out(path)
    repo = R.infer_repo(path)
    text = R.render(data, path, repo)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_text() != text:
        out.write_text(text)


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker set", description=__doc__.splitlines()[0])
    ap.add_argument("ledger", type=Path)
    ap.add_argument("item_id")
    ap.add_argument("--status")
    ap.add_argument("--owner")
    ap.add_argument("--field", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--event")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--by", default="lead")
    ap.add_argument("--at")
    args = ap.parse_args(argv)
    say = "tracker set:"

    fields: list[tuple[str, object, str]] = []
    for raw in args.field:
        parsed = _parse_field(raw)
        if parsed is None:
            print(f"{say} --field {raw!r} is not KEY=VALUE -- nothing written", file=sys.stderr)
            return 1
        key, value, shown = parsed
        if key in FORBIDDEN_FIELDS:
            print(f"{say} --field may not set {key!r} -- nothing written", file=sys.stderr)
            return 1
        fields.append((key, value, shown))

    try:
        data = L.load(args.ledger)
    except (OSError, ValueError) as exc:
        print(f"{say} {exc}", file=sys.stderr)
        return 2

    item = L.by_id(data).get(args.item_id)
    if item is None:
        print(f"{say} {args.item_id} is not an item in {args.ledger} -- nothing written", file=sys.stderr)
        return 1

    parts = []
    if args.status is not None:
        item["status"] = args.status
        parts.append(f"status {args.status}")
    if args.owner is not None:
        item["owner"] = args.owner
        parts.append(f"owner {args.owner}")
    for key, value, shown in fields:
        item[key] = value
        parts.append(f"field {key}={shown}")

    event_text = args.event if args.event is not None else args.status
    if event_text is not None:
        item.setdefault("log", []).append({
            "at": args.at or _now(),
            "event": event_text,
            "by": args.by,
            "evidence": args.evidence,
        })
        parts.append(f'log "{event_text}"')

    data["updated"] = datetime.date.today().isoformat()

    problems = L.validate(data)
    if problems:
        print(f"{say} {args.ledger} would not be well-formed after this change -- nothing written:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    args.ledger.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    _render(data, args.ledger)
    parts.append("page rendered")
    print(f"{say} {args.item_id} " + " · ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
