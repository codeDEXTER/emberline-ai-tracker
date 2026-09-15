"""tracker ask -- record a sponsor ask as A-nn, in place of an inline
`python3 -` script that loads a ledger, appends an ask and dumps it back
(proposal 23, lever L4, L-04).

  tracker ask LEDGER --kind KIND --quote TEXT [--state STATE] [--by NAME]
                      [--at ISO8601] [--owner O] [--became ITEM]
                      [--source TEXT] [--note TEXT]

Every sponsor message that is not an answer becomes an ask (docs/OPERATING-
RULES.md section 1), quoting his words exactly -- `--quote` is stored as
given, with no trimming beyond a single trailing newline, typos and quote
marks and all.

The new id is the next free A-nn, zero-padded to the width the ledger's
existing asks already use (or two digits, for the first one). `--state`
defaults to "open", `--by` to "sponsor".

Validated with the new ask already appended, before anything is written: on
any problem the problems are printed and the file is untouched (exit 1). On
success the ledger is written (indent=2, ensure_ascii=False, trailing
newline) and its page is re-rendered.

Exit codes: 0 written, 1 a finding, 2 could not read the ledger.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

from tools.tracker import ledger as L
from tools.tracker import render as R

ASK_NUM = re.compile(r"^A-(\d+)\Z")


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _next_id(data: dict) -> str:
    asks = data.get("asks") or []
    nums = []
    width = 2
    for a in asks:
        m = ASK_NUM.match(str(a.get("id", "")))
        if m:
            nums.append(int(m.group(1)))
            width = max(width, len(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    return f"A-{n:0{width}d}"


def _render(data: dict, path: Path) -> None:
    out = R.default_out(path)
    repo = R.infer_repo(path)
    text = R.render(data, path, repo)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_text() != text:
        out.write_text(text)


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker ask", description=__doc__.splitlines()[0])
    ap.add_argument("ledger", type=Path)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--quote", required=True)
    ap.add_argument("--state", default="open")
    ap.add_argument("--by", default="sponsor")
    ap.add_argument("--at")
    ap.add_argument("--owner")
    ap.add_argument("--became")
    ap.add_argument("--source")
    ap.add_argument("--note")
    args = ap.parse_args(argv)
    say = "tracker ask:"

    try:
        data = L.load(args.ledger)
    except (OSError, ValueError) as exc:
        print(f"{say} {exc}", file=sys.stderr)
        return 2

    quote = args.quote[:-1] if args.quote.endswith("\n") else args.quote

    new_id = _next_id(data)
    ask = {
        "id": new_id,
        "at": args.at or _now(),
        "by": args.by,
        "kind": args.kind,
        "quote": quote,
        "became": args.became,
        "state": args.state,
    }
    if args.owner is not None:
        ask["owner"] = args.owner
    if args.source is not None:
        ask["source"] = args.source
    if args.note is not None:
        ask["note"] = args.note

    asks = list(data.get("asks") or [])
    asks.append(ask)
    data["asks"] = asks
    data["updated"] = datetime.date.today().isoformat()

    problems = L.validate(data)
    if problems:
        print(f"{say} {args.ledger} would not be well-formed after this change -- nothing written:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    args.ledger.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    _render(data, args.ledger)
    print(f"{say} {new_id} {args.kind} {args.state}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
