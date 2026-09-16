"""tracker import -- an existing milestone plan becomes a ledger (proposal 19, W-09).

  tracker import --project DIR --proposal N --title TITLE [--out PATH] [--at ISO] [--dry-run]

The focus projects already have plans, and the standard must not ask anyone to
retype one. pockets keeps a `## Milestones` table in CLAUDE-checklist.md;
finance-tracker keeps its rows in CLAUDE-milestones.json and generates the table
from it, so when both exist the JSON is read.

ONE READER. Table rows come from bin/milestones' own parse(), and states are
classed with its STATE_CLASS. That table already has one reader and one
vocabulary; the second copy of a vocabulary is how two readers of it once got
the same case wrong (bin/milestones, hands_something_over).

WHAT IMPORT DECIDES, and why:
  * Tracks become phases, in the order the plan introduces them. A phase id is
    the track's initial, extended by a letter when two tracks share one.
  * "built" becomes IN PROGRESS. A built milestone is awaiting sign-off; calling
    it done erases exactly the gap finance-tracker's chips exist to show. The
    source state is kept verbatim in the row's log, so nothing is lost.
  * Every row is C4, the lead's. A milestone is a planning row that the lead
    decomposes into C1-C3 items; import does not guess a class it cannot know.
  * It never overwrites a file, never takes a proposal number that already has
    a ledger, and never writes a ledger that fails validation.

Exit codes: 0 imported (or --dry-run), 1 refused, 2 no plan to import.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.machinery
import importlib.util
import json
import re
import sys
from pathlib import Path

from tools.tracker import ledger as L

RULES_DIR = Path(__file__).resolve().parent.parent.parent

LEDGER_STATUS = {"done": "done", "built": "in progress", "now": "in progress",
                 "next": "not started", "later": "not started", "blocked": "blocked"}

DEFAULT_TIERS = {
    "C1": {"tier": "low", "model": "haiku", "effort": "low", "rule": "Mechanical, one owned file, fully specified"},
    "C2": {"tier": "medium", "model": "sonnet", "effort": "medium", "rule": "Bounded implementation or tests, one or two owned files"},
    "C3": {"tier": "high", "model": "sonnet", "effort": "high", "rule": "Cross-module design; wrong loses data or trust"},
    "C4": {"tier": "lead", "model": "opus", "effort": "low or medium", "rule": "Planning, merging, reconciling, a sponsor decision"},
}


def milestones_module():
    """bin/milestones, loaded as a module so its parse() and STATE_CLASS are
    used rather than copied. Its main() is behind a __main__ guard."""
    path = RULES_DIR / "bin" / "milestones"
    loader = importlib.machinery.SourceFileLoader("common_rules_bin_milestones", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def plain(text) -> str:
    return re.sub(r"\*\*|__", "", str(text or "")).strip()


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "plan"


def phase_ids(tracks: list[str]) -> dict[str, str]:
    """{track: id}, allocated in order of first appearance."""
    taken: set[str] = set()
    out: dict[str, str] = {}
    for n, track in enumerate(tracks, 1):
        letters = re.sub(r"[^A-Z]", "", (track or "Milestones").upper()) or f"T{n}"
        for width in range(1, len(letters) + 1):
            candidate = letters[:width]
            if candidate not in taken:
                break
        else:
            candidate = f"{letters}{n}"
        taken.add(candidate)
        out[track] = candidate
    return out


def rows_from_json(path: Path, mod) -> list[dict]:
    data = json.loads(path.read_text())
    rows = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"{path.name}: no `rows` list")
    out = []
    for i, r in enumerate(rows, 1):
        raw = str(r.get("st") or "").strip().strip("*").lower()
        cls = next((v for k, v in mod.STATE_CLASS.items() if k in raw), None)
        if cls is None:
            cls = "done" if r.get("done") is True else "next"
        out.append({"n": r.get("n") or i, "t": r.get("t"), "pv": r.get("pv"), "gt": r.get("gt"),
                    "tr": plain(r.get("tr")), "s": cls, "raw": raw or ("done" if r.get("done") else "")})
    return out


def rows_from_table(path: Path, mod) -> list[dict] | None:
    rows = mod.parse(path)
    if not rows:
        return None
    return [{"n": i, **r} for i, r in enumerate(rows, 1)]


def build(rows: list[dict], source: str, proposal: int, title: str, at: str) -> dict:
    tracks: list[str] = []
    for r in rows:
        if r.get("tr", "") not in tracks:
            tracks.append(r.get("tr", ""))
    ids = phase_ids(tracks)
    counters = {t: 0 for t in tracks}
    items = []
    for r in rows:
        track = r.get("tr", "")
        counters[track] += 1
        # Verbatim for CLAUDE-milestones.json, whose rows carry the state text.
        # A table row carries only bin/milestones' class: parse() does not
        # return the raw cell, and adding it would change the digest of every
        # project's docs/milestones.html (digest() hashes whole rows), turning
        # land's milestone-page gate against all of them at once.
        if r.get("raw"):
            state = f"state '{r['raw']}'"
        else:
            state = f"state class '{r['s']}' (bin/milestones)"
        evidence = f"{source} row {r['n']}: {state}" + (f"; track '{track}'" if track else "")
        items.append({
            "id": f"{ids[track]}-{counters[track]:02d}", "phase": ids[track], "cx": "C4",
            "title": plain(r.get("t")),
            "what": f"Proves: {plain(r.get('pv'))}. You get: {plain(r.get('gt'))}.",
            "files": [], "tests": [], "done": plain(r.get("pv")), "depends": [],
            "status": LEDGER_STATUS.get(r["s"], "not started"),
            "tier": "lead", "model": "opus", "tag": "[ruflo · lead · opus]", "issue": None,
            "log": [{"at": at, "event": "imported", "by": "tracker import", "evidence": evidence}],
        })
    tiers = DEFAULT_TIERS
    template = RULES_DIR / "templates" / "ledger.json"
    try:
        tiers = json.loads(template.read_text()).get("tiers") or DEFAULT_TIERS
    except (OSError, ValueError):
        pass
    return {
        "proposal": proposal, "title": title, "status": "accepted", "updated": at[:10],
        "tiers": tiers,
        "phases": [{"id": ids[t], "name": t or "Milestones"} for t in tracks],
        "items": items, "asks": [], "proposed_changes": [],
        "execution": {"ruflo_route": "", "imported_from": source},
    }


def dumps(ledger: dict) -> str:
    """One item per line, the shape the hand-kept ledgers use -- so the
    byte-minimal edits `tracker sync` makes find each row's own text."""
    keys = list(ledger)
    lines = ["{"]
    for k in keys:
        v = ledger[k]
        if k in ("phases", "items", "asks", "proposed_changes") and isinstance(v, list) and v:
            body = "[\n" + ",\n".join("    " + json.dumps(x, ensure_ascii=False) for x in v) + "\n  ]"
        else:
            body = json.dumps(v, ensure_ascii=False)
        lines.append(f"  {json.dumps(k)}: {body}" + ("," if k != keys[-1] else ""))
    return "\n".join(lines + ["}"]) + "\n"


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker import", description=__doc__.splitlines()[0])
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("--proposal", type=int, required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--at", default=datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    project = args.project
    mod = milestones_module()

    source_json = project / "CLAUDE-milestones.json"
    source_table = project / "CLAUDE-checklist.md"
    try:
        if source_json.is_file():
            rows, source = rows_from_json(source_json, mod), source_json.name
        elif source_table.is_file() and (rows := rows_from_table(source_table, mod)):
            source = source_table.name
        else:
            rows = None
    except (OSError, ValueError) as exc:
        print(f"tracker import: could not read the plan -- {exc}", file=sys.stderr)
        return 2
    if not rows:
        print(f"tracker import: no milestone plan in {project} "
              f"(CLAUDE-milestones.json, or a ## Milestones table in CLAUDE-checklist.md)")
        return 2

    number = f"{args.proposal:02d}"
    for existing in L.find(project):
        try:
            claimed = json.loads(existing.read_text()).get("proposal")
        except (OSError, ValueError, AttributeError):
            claimed = None
        if existing.name.startswith(f"{number}-") or claimed == args.proposal:
            print(f"tracker import: proposal {args.proposal} already has a ledger: {existing} -- pick the next number")
            return 1

    out = args.out or project / "docs" / "proposals" / f"{number}-{slug(args.title)}.json"
    if out.exists():
        print(f"tracker import: refusing to overwrite {out}")
        return 1

    ledger = build(rows, source, args.proposal, args.title, args.at)
    problems = L.validate(ledger)
    if problems:
        print(f"tracker import: the imported ledger would not validate; nothing written:")
        for p in problems:
            print(f"  {p}")
        return 1

    if args.dry_run:
        print(f"would import {len(rows)} rows from {source} into {out} · {L.status_line(ledger)}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(ledger))
    print(f"imported {len(rows)} rows from {source} into {out} · {L.status_line(ledger)}")
    return 0
