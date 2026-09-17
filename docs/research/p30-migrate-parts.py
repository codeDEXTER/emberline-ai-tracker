"""Structural migration (proposal 30, P-05): write the lead's lettered-part
split onto five open items across three ledgers.

This bypasses `tracker set --parts` (proposal 30, P-02), which is being built
in parallel and is not available yet. That is the documented exception in
tools/tracker/parts.py's own rules: a structural migration may write `parts`
directly, provided the result still passes ledger.validate() -- which this
script checks before writing anything.

Idempotent: an item that already carries a `parts` list is left untouched,
so re-running this script after P-02 lands (or after a partial run) is safe.

Usage: python3 docs/research/p30-migrate-parts.py
"""
from __future__ import annotations

import copy
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.tracker import ledger as LEDGER  # noqa: E402

NOW = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

LOG_ENTRY = {
    "at": NOW,
    "event": "split into lettered parts (proposal 30, P-05)",
    "by": "lead",
    "evidence": "docs/research/p30-migrate-parts.py",
}

# path -> {item id -> parts list (without id/title -- filled in from the item)}
PLAN = {
    "docs/proposals/19-proposal-warmup.json": {
        "W-10": [
            {"title": "warm-up --check passes in all four focus projects", "share": 20,
             "status": "not started", "owner": "session:PhotoVault Engine"},
            {"title": "tracker render works for the engine and pockets", "share": 20,
             "status": "in progress", "owner": "session:PhotoVault Engine"},
            {"title": "land refuses an unrecorded item", "share": 20, "status": "done"},
            {"title": "every sponsor message has an ask row", "share": 20,
             "status": "not started", "waiting_until": "2026-09-21"},
            {"title": "every brief has the five headings", "share": 20,
             "status": "not started", "waiting_until": "2026-09-21"},
        ],
    },
    "docs/proposals/23-eight-levers-for-token-spend.json": {
        "L-02": [
            {"title": "rule and brief template changed", "share": 60, "status": "done"},
            {"title": "review/fix agents under 10% of subagent spend", "share": 30,
             "status": "in testing", "waiting_until": "2026-09-23"},
            {"title": "no rise in defects after merge", "share": 10,
             "status": "in testing", "waiting_until": "2026-09-23"},
        ],
        "L-07": [
            {"title": "brief MUST lines name the right tool", "share": 80, "status": "done"},
            {"title": "mining rerun shows each cluster halved", "share": 20,
             "status": "in testing", "waiting_until": "2026-09-23"},
        ],
    },
    "docs/proposals/21-standard-is-mandatory.json": {
        "S-07": [
            {"title": "12 of 12 conformance items hold for PhotoVault app/engine",
             "share": 100, "status": "not started", "owner": "session:PhotoVault App"},
        ],
        "S-08": [
            {"title": "12 of 12 conformance items hold for PhotoVault app/engine",
             "share": 100, "status": "not started", "owner": "session:PhotoVault Engine"},
        ],
    },
}

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def build_parts(item_id: str, spec: list[dict]) -> list[dict]:
    out = []
    for n, p in enumerate(spec):
        part = {"id": f"{item_id}.{_LETTERS[n]}", "title": p["title"], "share": p["share"],
                "status": p["status"]}
        if "owner" in p:
            part["owner"] = p["owner"]
        if "waiting_until" in p:
            part["waiting_until"] = p["waiting_until"]
        out.append(part)
    return out


def migrate_file(rel_path: str, items_plan: dict) -> list[str]:
    path = ROOT / rel_path
    data = LEDGER.load(path)
    original = copy.deepcopy(data)
    by_id = LEDGER.by_id(data)
    changed_ids = []
    for item_id, spec in items_plan.items():
        item = by_id.get(item_id)
        if item is None:
            raise SystemExit(f"{rel_path}: item {item_id} not found")
        if item.get("parts"):
            continue  # idempotent: already migrated
        item["parts"] = build_parts(item_id, spec)
        item.setdefault("log", [])
        item["log"].append(dict(LOG_ENTRY))
        changed_ids.append(item_id)

    if not changed_ids:
        return []

    problems = LEDGER.validate(data)
    if problems:
        raise SystemExit(f"{rel_path}: validate() failed after migration, nothing written:\n" +
                          "\n".join(f"  - {p}" for p in problems))

    if data == original:
        return []

    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return changed_ids


def main() -> int:
    any_changed = False
    for rel_path, items_plan in PLAN.items():
        changed = migrate_file(rel_path, items_plan)
        if changed:
            any_changed = True
            print(f"{rel_path}: parts written for {', '.join(changed)}")
        else:
            print(f"{rel_path}: nothing to do (already migrated)")
    if not any_changed:
        print("idempotent run: no ledger changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
