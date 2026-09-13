"""The ledger: one JSON object per numbered proposal, the source of truth for
its plan (proposal 19, section B).

Shape, as the PhotoVault engine's proposal 71 already writes it, plus `asks`:

    {
      "proposal": 71, "title": "...", "status": "accepted", "updated": "2026-09-13",
      "tiers":  {"C1": {"tier": "low", "model": "haiku", "effort": "low", "rule": "..."}, ...},
      "phases": [{"id": "R", "name": "...", "goal": "...", "exit": "..."}],
      "items":  [{"id": "R-01", "phase": "R", "cx": "C3", "title": "...",
                  "what": "...", "files": "...", "tests": "...", "done": "...",
                  "depends": "R-01 R-02", "status": "done",
                  "tier": "high", "model": "opus", "tag": "[ruflo · high · opus]",
                  "issue": 229, "discovered_from": "X-03",
                  "log": [{"at": "...", "event": "...", "by": "...", "evidence": "..."}]}],
      "asks":   [{"id": "A-07", "at": "...", "kind": "research", "quote": "...",
                  "became": null, "state": "open"}],
      "proposed_changes": [...], "priority": {...}, "execution": {"ruflo_route": "..."}
    }

Deliberately tolerant of the engine's existing spellings: `files`, `tests` and
`depends` may be a list or one string (space- or comma-separated). The loader
never rewrites a ledger to normalise it -- a tool that silently reformats the
source of truth produces diffs nobody asked for, and the engine commits its
ledger 58 times a day.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

STATUSES = ("not started", "in progress", "blocked", "done")
ASK_KINDS = ("research", "feature", "defect", "decision", "question")
ASK_STATES = ("open", "answered", "became-item", "declined")
CLASSES = ("C1", "C2", "C3", "C4")

# An item id is a phase letter-group and a number: R-01, E1-09, X-03, W-10.
ITEM_ID = re.compile(r"^[A-Z][A-Z0-9]*-\d{2,}$")
ASK_ID = re.compile(r"^A-\d{2,}$")

REQUIRED_ITEM_KEYS = ("id", "phase", "cx", "title", "status")


def load(path) -> dict:
    """Read a ledger. Raises ValueError naming the file when it is not JSON."""
    p = Path(path)
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{p}: not valid JSON ({exc})") from None


def as_list(value) -> list[str]:
    """`files`, `tests`, `depends` in either spelling, as a list of strings."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v for v in re.split(r"[,\s]+", str(value)) if v]


def items(ledger: dict) -> list[dict]:
    return list(ledger.get("items") or [])


def by_id(ledger: dict) -> dict[str, dict]:
    return {i["id"]: i for i in items(ledger) if "id" in i}


def counts(ledger: dict) -> dict[str, int]:
    """done / in progress / blocked / not started, always all four keys, in
    that order -- the one status vocabulary the card, the checkpoint and the
    render share (D7)."""
    c = {"done": 0, "in progress": 0, "blocked": 0, "not started": 0}
    for i in items(ledger):
        s = i.get("status")
        if s in c:
            c[s] += 1
    return c


def status_line(ledger: dict) -> str:
    c = counts(ledger)
    return f'{c["done"]} done / {c["in progress"]} in progress / {c["blocked"]} blocked / {c["not started"]} not started'


def unblocked(ledger: dict) -> list[dict]:
    """Not-started items whose dependencies are all done, in ledger order."""
    ids = by_id(ledger)
    out = []
    for i in items(ledger):
        if i.get("status") != "not started":
            continue
        deps = [d for d in as_list(i.get("depends")) if d in ids]
        if all(ids[d].get("status") == "done" for d in deps):
            out.append(i)
    return out


def open_asks(ledger: dict) -> list[dict]:
    return [a for a in (ledger.get("asks") or []) if a.get("state") == "open"]


def validate(ledger: dict) -> list[str]:
    """Every problem, as a sentence naming the item. Empty means well-formed.

    Checks what a reader relies on and nothing stylistic: ids are unique and
    shaped, every status and class is from the vocabulary, dependencies and
    `discovered_from` point at something that exists, asks are shaped.
    """
    problems: list[str] = []
    if not isinstance(ledger.get("proposal"), int):
        problems.append("top level: `proposal` must be the proposal number, an integer")
    seen: set[str] = set()
    phases = {p.get("id") for p in (ledger.get("phases") or [])}
    ids = {i.get("id") for i in items(ledger)}
    ask_ids = {a.get("id") for a in (ledger.get("asks") or [])}
    for n, i in enumerate(items(ledger)):
        name = i.get("id") or f"items[{n}]"
        for k in REQUIRED_ITEM_KEYS:
            if not i.get(k):
                problems.append(f"{name}: missing `{k}`")
        iid = i.get("id")
        if iid:
            if not ITEM_ID.match(iid):
                problems.append(f"{iid}: id is not PHASE-NN (e.g. R-01, E1-09)")
            if iid in seen:
                problems.append(f"{iid}: id appears more than once")
            seen.add(iid)
        if i.get("status") and i["status"] not in STATUSES:
            problems.append(f"{name}: status {i['status']!r} is not one of {', '.join(STATUSES)}")
        if i.get("cx") and i["cx"] not in CLASSES:
            problems.append(f"{name}: class {i['cx']!r} is not one of {', '.join(CLASSES)}")
        if phases and i.get("phase") and i["phase"] not in phases:
            problems.append(f"{name}: phase {i['phase']!r} is not declared in `phases`")
        for d in as_list(i.get("depends")):
            if d not in ids:
                problems.append(f"{name}: depends on {d}, which is not an item")
        src = i.get("discovered_from")
        if src and src not in ids and src not in ask_ids:
            problems.append(f"{name}: discovered_from {src}, which is neither an item nor an ask")
        if i.get("status") == "done" and not i.get("log"):
            problems.append(f"{name}: done with an empty log -- nothing says how")
    seen_asks: set[str] = set()
    for n, a in enumerate(ledger.get("asks") or []):
        name = a.get("id") or f"asks[{n}]"
        if not a.get("id") or not ASK_ID.match(a["id"]):
            problems.append(f"{name}: ask id is not A-NN")
        elif a["id"] in seen_asks:
            problems.append(f"{name}: ask id appears more than once")
        else:
            seen_asks.add(a["id"])
        if a.get("kind") not in ASK_KINDS:
            problems.append(f"{name}: kind {a.get('kind')!r} is not one of {', '.join(ASK_KINDS)}")
        if a.get("state") not in ASK_STATES:
            problems.append(f"{name}: state {a.get('state')!r} is not one of {', '.join(ASK_STATES)}")
        if not a.get("quote"):
            problems.append(f"{name}: no `quote` -- an ask is recorded in the sponsor's words")
        if a.get("state") == "became-item" and not a.get("became"):
            problems.append(f"{name}: became-item but `became` names nothing")
    return problems


def find(project) -> list[Path]:
    """Every ledger under a project's docs/proposals, sorted by number."""
    root = Path(project) / "docs" / "proposals"
    return sorted(root.glob("[0-9][0-9]*-*.json"), key=lambda p: int(p.name.split("-")[0]))
