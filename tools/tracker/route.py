"""tracker route -- how one item is reviewed and bundled (proposal 25, Z-02).

  tracker route LEDGER ITEM_ID [--project DIR] [--json]

  restricted                              separate reviewer, the sponsor sees the result; never bundled
  elevated, or value high with points >=5 separate reviewer; own branch
  otherwise                               gate and tests only; points 1-3 bundle by cluster, else own branch

Risk is the item's own `risk`, else tools/tracker/risk.py on its `files`.
Value is the item's own, else its cluster's default (tools/tracker/sizing.py).
Points are the lead's or the scout's and are never put in a builder's brief
(D3). The route never changes a model (proposal 23, D8).

--project defaults to the ledger's project: the folder holding docs/proposals.

Exit codes: 0 printed, 1 no such item, 2 could not read the ledger.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools import project as P
from tools.tracker import ledger as L
from tools.tracker import risk as RISK
from tools.tracker import sizing


def project_of(ledger_path: Path) -> Path:
    p = Path(ledger_path).resolve()
    if p.parent.name == "proposals" and p.parent.parent.name == "docs":
        return p.parent.parent.parent
    return p.parent


def route(item: dict, project) -> dict:
    notes = []
    if item.get("risk") in L.RISKS:
        risk, risk_why = item["risk"], "item"
        floor, floor_why = RISK.classify(project, [])
        if RISK.ORDER.index(floor) > RISK.ORDER.index(risk):
            risk, risk_why = floor, floor_why
    else:
        risk, risk_why = RISK.classify(project, L.as_list(item.get("files")))
    value, value_source = sizing.effective_value(item, P.load(Path(project)).get("value_defaults") or {})
    points = item.get("points")
    cluster = item.get("cluster")
    if value is None:
        notes.append("value unsized")
    if points is None:
        notes.append("points unsized")

    if risk == "restricted":
        review, bundle = "separate reviewer, the sponsor sees the result", "never bundled"
    elif risk == "elevated" or (value == "high" and isinstance(points, int) and points >= 5):
        review, bundle = "separate reviewer", "own branch"
    else:
        review = "gate and tests only"
        if isinstance(points, int) and points <= 3:
            bundle = f"bundle by cluster {cluster}" if cluster else "own branch (no cluster)"
        else:
            bundle = "own branch"
    return {"id": item.get("id"), "risk": risk, "risk_why": risk_why, "value": value,
            "value_source": value_source, "points": points, "cluster": cluster,
            "review": review, "bundle": bundle, "notes": notes}


def line(r: dict) -> str:
    size = f"value {r['value'] or '?'} · {r['points'] if r['points'] is not None else '?'} pts"
    text = f"{r['id']} · risk {r['risk']} · {size} · {r['review']} · {r['bundle']}"
    if r["notes"]:
        text += f" · {', '.join(r['notes'])}"
    return f"{text}\n  risk: {r['risk_why']} · value: {r['value_source']}"


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker route", description=__doc__.splitlines()[0])
    ap.add_argument("ledger", type=Path)
    ap.add_argument("item_id")
    ap.add_argument("--project", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        data = L.load(args.ledger)
    except (OSError, ValueError) as exc:
        print(f"tracker route: {exc}", file=sys.stderr)
        return 2
    item = L.by_id(data).get(args.item_id)
    if item is None:
        print(f"tracker route: {args.item_id} is not an item in {args.ledger}", file=sys.stderr)
        return 1
    r = route(item, args.project or project_of(args.ledger))
    print(json.dumps(r, ensure_ascii=False) if args.json else line(r))
    return 0
