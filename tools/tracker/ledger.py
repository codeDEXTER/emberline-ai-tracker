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

import datetime
import json
import math
import re
from pathlib import Path

STATUSES = ("not started", "in progress", "blocked", "done")
ASK_KINDS = ("research", "feature", "defect", "decision", "question")
ASK_STATES = ("open", "answered", "became-item", "declined")
CLASSES = ("C1", "C2", "C3", "C4")

# An item id is a phase letter-group and a number: R-01, E1-09, X-03, W-10.
ITEM_ID = re.compile(r"^[A-Z][A-Z0-9]*-\d{2,}\Z")
ASK_ID = re.compile(r"^A-\d{2,}\Z")

REQUIRED_ITEM_KEYS = ("id", "phase", "cx", "title", "status")

# Proposal 20 additions. Every one is optional: a ledger that declares none of
# them validates exactly as before, which is how the PhotoVault engine's and
# app's ledgers stay valid while they adopt the pieces they want.
OWNER = re.compile(r"^(sponsor|lead|session:[^\x00-\x1f\x7f-\x9f]+)\Z")          # D4
SWITCHES = ("issues", "publish", "ruflo")                     # D5
REQUEST_ID = re.compile(r"^RQ-\d{2,}\Z")                       # D7
REQUEST_STATES = ("open", "in progress", "answered", "declined")


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
    number = ledger.get("proposal")
    # A bool is an int in Python: `"proposal": true` passed until T-02 (the
    # T-01 review found it).
    if isinstance(number, bool) or not isinstance(number, int) or number < 0:
        problems.append("top level: `proposal` must be the proposal number, a non-negative integer")
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
        # T-02, from the T-01 review: a string log entry passed, and the board
        # had to learn to skip it.
        if "log" in i and not isinstance(i["log"], list):
            problems.append(f"{name}: `log` must be a list of entries")
        else:
            for k, entry in enumerate(i.get("log") or []):
                if not isinstance(entry, dict):
                    problems.append(f"{name}: log[{k}] is not an object {{at, event, by, evidence}}")
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
    problems.extend(_validate_v2(ledger, ids, ask_ids))
    problems.extend(_validate_tracker(ledger))
    # A message can quote a malformed id; every problem is printed as one line
    # (V-02 final review: "Z-01\\nwarmup --check: ready" split a problem in two).
    return [_printable(p) for p in problems]


_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _printable(text: str) -> str:
    """Control characters as visible escapes, lone surrogates as U+FFFD."""
    out = []
    for ch in text:
        cp = ord(ch)
        if ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif cp < 0x20 or 0x7f <= cp <= 0x9f:
            out.append(f"\\x{cp:02x}")
        elif 0xD800 <= cp <= 0xDFFF:
            out.append("\ufffd")
        else:
            out.append(ch)
    return "".join(out)


def _one_line(value) -> bool:
    """A string with no control character and no lone surrogate: safe to print
    as part of one card or page line (\\Z, not $, so a trailing newline fails)."""
    if not isinstance(value, str) or _CONTROL.search(value):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _number(value) -> bool:
    """A finite, non-negative int or float -- not a bool (JSON true is not a
    weight), and not NaN or Infinity, which json.loads accepts."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def _not_a_number(value) -> str:
    finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    return "is negative" if finite and value < 0 else "is not a number"


def _evident(value) -> bool:
    """The PhotoVault app's rule (tools/build_plan.py): true, or a declared "n/a"."""
    return value is True or value == "n/a"


def _validate_v2(ledger: dict, ids: set, ask_ids: set) -> list[str]:
    """Proposal 20's contract additions, each checked only when declared."""
    problems: list[str] = []
    for key in ("gates", "quality_floors", "requests"):
        if key in ledger and not isinstance(ledger[key], list):
            problems.append(f"{key}: must be a list")
    if "native_receipts" in ledger and not isinstance(ledger["native_receipts"], dict):
        problems.append("native_receipts: must be an object")
    for key in ("readiness_weights", "size_weights"):
        table = ledger.get(key)
        if table is None:
            continue
        if not isinstance(table, dict):
            problems.append(f"{key}: must be an object")
            continue
        for name, value in table.items():
            if not _number(value):
                problems.append(f"{key}.{name}: {value!r} {_not_a_number(value)}")
    for n, i in enumerate(items(ledger)):
        if "weight" in i and not _number(i["weight"]):
            problems.append(f"{i.get('id') or f'items[{n}]'}: weight {i['weight']!r} {_not_a_number(i['weight'])}")
    tiers = ledger.get("tiers") if isinstance(ledger.get("tiers"), dict) else {}
    was_ids = {i.get("was") for i in items(ledger) if i.get("was")}
    ladder = {l.get("level") for l in (ledger.get("verification_ladder") or []) if isinstance(l, dict)}
    rule = ledger.get("evidence_rule") if isinstance(ledger.get("evidence_rule"), dict) else {}
    keys = list(rule.get("keys") or [])

    for n, i in enumerate(items(ledger)):
        name = i.get("id") or f"items[{n}]"
        cx, model = i.get("cx"), i.get("model")
        want = (tiers.get(cx) or {}).get("model") if isinstance(tiers.get(cx), dict) else None
        if want and model and model != want and not i.get("model_override_reason"):         # D2
            problems.append(f"{name}: model {model!r} disagrees with tiers {cx} ({want}) and has no model_override_reason")
        if "owner" in i and not (isinstance(i["owner"], str) and OWNER.match(i["owner"])):  # D4
            problems.append(f"{name}: owner {i.get('owner')!r} is not sponsor, lead or session:<name>")
        if ladder and i.get("verify") is not None and i["verify"] not in ladder:              # D6
            problems.append(f"{name}: verify {i['verify']!r} is not a level on the verification ladder")
        if keys and i.get("status") == "done":                                                # D6
            ev = i.get("evidence") if isinstance(i.get("evidence"), dict) else {}
            missing = [k for k in keys if not _evident(ev.get(k))]
            if missing:
                problems.append(f"{name}: done without evidence: {', '.join(missing)}")
        if i.get("merged") not in (None, False, "") and i.get("status") == "not started":     # D8
            problems.append(f"{name}: merged but not started")

    for n, a in enumerate(ledger.get("asks") or []):                                           # D4
        if "owner" in a and not (isinstance(a["owner"], str) and OWNER.match(a["owner"])):
            problems.append(f"{a.get('id') or f'asks[{n}]'}: owner {a.get('owner')!r} is not sponsor, lead or session:<name>")

    switches = ledger.get("switches")                                                          # D5
    if switches is not None:
        if not isinstance(switches, dict):
            problems.append("switches: must be an object of name -> {on, by, at, quote}")
        else:
            for sname, sw in switches.items():
                if sname not in SWITCHES:
                    problems.append(f"switches: {sname!r} is not one of {', '.join(SWITCHES)}")
                    continue
                if not isinstance(sw, dict) or not isinstance(sw.get("on"), bool):
                    problems.append(f"switches.{sname}: `on` must be true or false")
                elif sw["on"] is False and not (sw.get("by") and sw.get("at")):
                    problems.append(f"switches.{sname}: off without `by` and `at`")
                else:
                    for field in ("by", "at", "quote"):
                        if field in sw and not _one_line(sw[field]):
                            problems.append(f"switches.{sname}: `{field}` must be one line of text")

    seen: set[str] = set()                                                                     # D7
    for n, r in enumerate(ledger.get("requests") or []):
        rid = r.get("id") if isinstance(r, dict) else None
        name = rid or f"requests[{n}]"
        if not isinstance(r, dict):
            problems.append(f"{name}: a request must be an object")
            continue
        if not rid or not REQUEST_ID.match(rid):
            problems.append(f"{name}: request id is not RQ-NN")
        elif rid in seen:
            problems.append(f"{name}: request id appears more than once")
        else:
            seen.add(rid)
        if r.get("state") not in REQUEST_STATES:
            problems.append(f"{name}: state {r.get('state')!r} is not one of {', '.join(REQUEST_STATES)}")
        for side in ("from", "to"):
            if not r.get(side):
                problems.append(f"{name}: no `{side}`")
            elif not _one_line(r[side]):
                problems.append(f"{name}: `{side}` must be one line of text")
        for u in r.get("unblocks") or []:
            if isinstance(u, str) and ITEM_ID.match(u) and u not in ids:
                problems.append(f"{name}: unblocks {u}, which is not an item")
        if r.get("state") == "answered" and not r.get("answered_by"):
            problems.append(f"{name}: answered without `answered_by`")

    for n, g in enumerate(ledger.get("gates") or []):                                          # D8
        if isinstance(g, dict) and not isinstance(g.get("passed"), bool):
            problems.append(f"{g.get('id') or f'gates[{n}]'}: `passed` must be true or false")
    for n, f in enumerate(ledger.get("quality_floors") or []):
        if isinstance(f, dict) and not isinstance(f.get("met"), bool):
            problems.append(f"quality_floors[{n}]: `met` must be true or false")
    for n, rc in enumerate(ledger.get("receipts") or []):
        item = rc.get("item") if isinstance(rc, dict) else None
        if item and item not in ids and item not in was_ids:
            problems.append(f"receipts[{n}]: item {item} is neither an item id nor a `was` id")
    return problems


def waiting_on(ledger: dict, owner: str) -> list[str]:
    """Blocked rows, then open asks, whose owner is `owner` (D4)."""
    rows = [i["id"] for i in items(ledger) if i.get("status") == "blocked" and i.get("owner") == owner]
    asks = [a["id"] for a in (ledger.get("asks") or []) if a.get("state") == "open" and a.get("owner") == owner]
    return rows + asks


def switch_on(ledger: dict, name: str) -> bool:
    """False only when the ledger records the switch off (D5); on by default."""
    sw = (ledger.get("switches") or {}).get(name) if isinstance(ledger.get("switches"), dict) else None
    return not (isinstance(sw, dict) and sw.get("on") is False)


TRACKER_FIELDS = ("by", "at", "quote")
# ISO 8601 date and time: the pieces are read here and the ranges checked
# with datetime, so the rule does not move with the Python version's own
# fromisoformat (3.11 widened it).
_AT = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?(Z|[+-]\d{2}:\d{2})?")


def _at_problem(value: str) -> str | None:
    m = _AT.fullmatch(value)
    bad = "`at` is not an ISO 8601 date and time (e.g. 2026-09-14T21:00:00+02:00)"
    if not m:
        return bad
    year, month, day, hour, minute, second, offset = m.groups()
    try:
        datetime.date(int(year), int(month), int(day))
        datetime.time(int(hour or 0), int(minute or 0), int(second or 0))
    except ValueError:
        return bad
    if offset is None:
        return "`at` has no offset (e.g. 2026-09-14T21:00:00+02:00) -- the time he asked, with its zone"
    if hour is None or (offset != "Z" and (int(offset[1:3]) > 23 or int(offset[4:6]) > 59)):
        return bad
    return None


def _validate_tracker(ledger: dict) -> list[str]:
    """Proposal 22, T-02. `tracker` is declared only when the sponsor asked
    for this proposal's own tracker page: {"own": true, "by", "at", "quote"},
    each one line, `at` with its offset -- the same record a switch keeps."""
    if "tracker" not in ledger:
        return []
    t = ledger["tracker"]
    if not isinstance(t, dict):
        return ["tracker: must be an object {own: true, by, at, quote} -- declared only when the sponsor "
                "asks for this proposal's own tracker"]
    problems = []
    if t.get("own") is not True:
        problems.append("tracker: `own` must be true -- a proposal without its own tracker has no `tracker` key")
    for field in TRACKER_FIELDS:
        value = t.get(field)
        if value is None or value == "":
            problems.append(f"tracker: no `{field}`" + (" -- in the sponsor's words" if field == "quote" else ""))
        elif not _one_line(value):
            problems.append(f"tracker: `{field}` must be one line of text")
        elif field == "at":
            at = _at_problem(value)
            if at:
                problems.append(f"tracker: {at}")
    return problems


def own_tracker(ledger: dict) -> bool:
    """True when the sponsor asked for this proposal's own tracker page
    (proposal 22, T-02): `tracker.own` is exactly true. Otherwise the
    proposal is on the project's one page only."""
    t = ledger.get("tracker") if isinstance(ledger, dict) else None
    return isinstance(t, dict) and t.get("own") is True


def open_requests(ledger: dict) -> list[dict]:
    return [r for r in (ledger.get("requests") or []) if isinstance(r, dict) and r.get("state") in ("open", "in progress")]


def merged_waiting(ledger: dict) -> list[str]:
    """Rows merged but not yet done: awaiting their evidence (D8)."""
    return [i["id"] for i in items(ledger) if i.get("merged") not in (None, False, "") and i.get("status") != "done"]


def readiness(ledger: dict) -> dict | None:
    """Readiness from the ledger's declared weights (D8), or None when it declares none.

    The PhotoVault app's tools/build_plan.py score(), generalised:
      work      a done row earns its weight; a row in progress earns half only
                when its focused tests pass (evidence.tests is true). Merged
                code earns nothing until it is done: merged_waiting() shows it.
                A row's weight is size_weights[size] when the ledger declares
                size_weights, else its own `weight`, else 1. Dropped rows are
                left out.
      gates     the share passed; floors the share met (rounded to 0.1 before
                the total, as the app does).
      receipts  the share of native_receipts recorded, over primary_surfaces
                when declared, else over every receipt key.
    Never typed: computed each time from the rows. None, too, when a declared
    weight is not a number; validate() names it.
    """
    w = ledger.get("readiness_weights")
    if not isinstance(w, dict) or not all(_number(v) for v in w.values()):
        return None                      # validate() names the bad value
    sizes = ledger.get("size_weights") if isinstance(ledger.get("size_weights"), dict) else None
    if sizes is not None and not all(_number(v) for v in sizes.values()):
        return None
    if any("weight" in i and not _number(i["weight"]) for i in items(ledger)):
        return None

    def weight(i: dict) -> float:
        if sizes is not None and i.get("size") in sizes:
            return float(sizes[i["size"]])
        return float(i.get("weight", 1))

    rows = [i for i in items(ledger) if i.get("status") != "dropped"]
    total = sum(weight(i) for i in rows) or 1.0
    earned = 0.0
    for i in rows:
        ev = i.get("evidence") if isinstance(i.get("evidence"), dict) else {}
        if i.get("status") == "done":
            earned += weight(i)
        elif i.get("status") == "in progress" and ev.get("tests") is True:
            earned += weight(i) / 2
    gates = [g for g in (ledger.get("gates") or []) if isinstance(g, dict)]
    floors = [f for f in (ledger.get("quality_floors") or []) if isinstance(f, dict)]
    native = ledger.get("native_receipts") if isinstance(ledger.get("native_receipts"), dict) else {}
    surfaces = ledger.get("primary_surfaces") if isinstance(ledger.get("primary_surfaces"), list) else list(native)
    work = float(w.get("work", 0)) * earned / total
    gate = float(w.get("gates", 0)) * sum(1 for g in gates if g.get("passed") is True) / (len(gates) or 1)
    floor = round(float(w.get("floors", 0)) * sum(1 for f in floors if f.get("met") is True) / (len(floors) or 1), 1)
    receipt = float(w.get("receipts", 0)) * sum(1 for s in surfaces if native.get(s)) / (len(surfaces) or 1)
    return {"work": round(work, 1), "gates": round(gate, 1), "floors": floor,
            "receipts": round(receipt, 1), "readiness": round(work + gate + floor + receipt)}


def find(project) -> list[Path]:
    """Every ledger under a project's docs/proposals, sorted by number.

    A file named NN-*.json is a ledger only if it is one: a JSON object with an
    `items` list. docs/proposals also holds data files with the same name shape
    -- the PhotoVault engine's 56-proposal-the-sample-sheet.sidecar.json -- and
    every tool built on this function printed "Proposal None · 0 done" for it
    (found running warm-up read-only on the engine, 13 September 2026). A file
    that does not parse is kept, so validate can report it: only its contents
    could say it is not a ledger.
    """
    root = Path(project) / "docs" / "proposals"
    found = []
    for p in root.glob("[0-9][0-9]*-*.json"):
        try:
            data = json.loads(p.read_text())
        except (OSError, ValueError):
            found.append(p)
            continue
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            found.append(p)
    return sorted(found, key=lambda p: int(p.name.split("-")[0]))
