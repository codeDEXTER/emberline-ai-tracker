"""Lettered parts of an item (proposal 30, P-01).

An item that cannot reach 100% in one go is split into parts named after it:
W-10.A, W-10.B, ... Each part is a tracked sub-ticket with its own status and
a share of the item. The sponsor's words: "I like the naming convention with
ABC. That should be standardized as the standard approach. And each ticket
should be tracked in the tracker or sub-ticket."

A part:
  {"id": "W-10.A", "title": "...", "share": 20, "status": "done",
   "owner": "lead" | "sponsor" | "session:<name>",       optional
   "waiting_until": "YYYY-MM-DD",                         optional
   "risk": "high" | "medium" | "low", "risk_reason": "...",  optional, reason required with risk
   "log": [{"at", "event", "by", "evidence", "status"?}]}  optional

Rules, decided 2026-09-17 ("go with your recommendations", D1-D5):
  completion  the sum of the done parts' shares; an item with no parts is one
              part worth 100 carrying the item's own status.
  groups      done         every part done;
              waiting      every open part is owned by another project's
                           session or waits for a date after today;
              finish now   under 80% complete, or an open part is high risk;
              back burner  80% or more complete, no open part high risk.
  risk        the lead's call, with a stated reason (D3).
Shares are whole percents set by the lead when splitting (D2) and add up to
100. Letters run in order from A and are never reused.
"""
from __future__ import annotations

import datetime
import re

STATUSES = ("not started", "in progress", "in review", "in testing", "blocked", "done")
RISKS = ("high", "medium", "low")
CUT = 80
GROUPS = ("finish now", "back burner", "waiting", "done")
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def parts(item: dict) -> list[dict]:
    value = item.get("parts")
    return [p for p in value if isinstance(p, dict)] if isinstance(value, list) else []


def validate_parts(item: dict) -> list[str]:
    """Every problem with `item`'s parts, as sentences naming the part."""
    value = item.get("parts")
    if value is None:
        return []
    iid = item.get("id") or "item"
    if not isinstance(value, list) or not value:
        return [f"{iid}: `parts` must be a non-empty list"]
    problems: list[str] = []
    total = 0
    for n, p in enumerate(value):
        if not isinstance(p, dict):
            problems.append(f"{iid}: parts[{n}] is not an object")
            continue
        expected = f"{iid}.{_LETTERS[n]}" if n < len(_LETTERS) else None
        pid = p.get("id")
        name = pid or f"{iid} parts[{n}]"
        if pid != expected:
            problems.append(f"{name}: part {n + 1} must be named {expected} (letters in order from A)")
        if not isinstance(p.get("title"), str) or not p["title"].strip():
            problems.append(f"{name}: missing `title`")
        share = p.get("share")
        if type(share) is not int or not 1 <= share <= 100:
            problems.append(f"{name}: `share` must be a whole percent from 1 to 100")
        else:
            total += share
        if p.get("status") not in STATUSES:
            problems.append(f"{name}: status {p.get('status')!r} is not one of {', '.join(STATUSES)}")
        owner = p.get("owner")
        if owner is not None and (not isinstance(owner, str) or not owner.strip()):
            problems.append(f"{name}: `owner` must be a non-empty string")
        wait = p.get("waiting_until")
        if wait is not None and not _is_date(wait):
            problems.append(f"{name}: `waiting_until` must be a YYYY-MM-DD date")
        risk = p.get("risk")
        if risk is not None:
            if risk not in RISKS:
                problems.append(f"{name}: risk {risk!r} is not one of {', '.join(RISKS)}")
            if not isinstance(p.get("risk_reason"), str) or not p["risk_reason"].strip():
                problems.append(f"{name}: a risk needs a `risk_reason`")
        if p.get("log") is not None and not isinstance(p["log"], list):
            problems.append(f"{name}: `log` must be a list")
    if not problems and total != 100:
        problems.append(f"{iid}: part shares add up to {total}, not 100")
    if item.get("status") == "done" and any(p.get("status") != "done" for p in parts(item)):
        problems.append(f"{iid}: status done while a part is still open")
    return problems


def completion(item: dict) -> int:
    """Percent complete: the done parts' shares, or 100/0 for an item without parts."""
    ps = parts(item)
    if not ps:
        return 100 if item.get("status") == "done" else 0
    return sum(p.get("share", 0) for p in ps if p.get("status") == "done" and type(p.get("share")) is int)


def open_parts(item: dict) -> list[dict]:
    ps = parts(item)
    if not ps:
        return [] if item.get("status") == "done" else [_implicit(item)]
    return [p for p in ps if p.get("status") != "done"]


def next_part(item: dict) -> dict | None:
    """The first open part, in letter order."""
    ops = open_parts(item)
    return ops[0] if ops else None


def is_waiting(part: dict, today: datetime.date | None = None) -> bool:
    """Owned by another project's session, or waiting for a date after today."""
    today = today or datetime.date.today()
    owner = part.get("owner")
    if isinstance(owner, str) and owner.startswith("session:"):
        return True
    wait = part.get("waiting_until")
    return _is_date(wait) and datetime.date.fromisoformat(wait) > today


def group(item: dict, today: datetime.date | None = None) -> str:
    """One of GROUPS, by the rules in this module's docstring."""
    ops = open_parts(item)
    if not ops:
        return "done"
    if all(is_waiting(p, today) for p in ops):
        return "waiting"
    if completion(item) < CUT or any(p.get("risk") == "high" for p in ops):
        return "finish now"
    return "back burner"


def _implicit(item: dict) -> dict:
    """An item without parts, seen as its one part worth 100."""
    part = {"id": item.get("id"), "title": item.get("title"), "share": 100,
            "status": item.get("status") or "not started"}
    if item.get("owner"):
        part["owner"] = item["owner"]
    return part


def _is_date(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True
