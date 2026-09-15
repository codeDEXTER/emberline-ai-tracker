"""warmup --queue's ledger writer (proposal 28, R-01).

Records each non-holding conformance item and each pending mandatory Standard
change as a ledger item -- owner `lead`, status `not started` -- so what
warmup already prints on the card also lands somewhere a lead works from,
instead of being re-discovered every session. Idempotent: `queue()` checks a
`queue_source` key nothing else writes, so a second `warmup --queue` run adds
nothing for a source already queued.

Deliberately not `tracker set` (which only changes an existing item): this
adds a new one, at the front of the ledger's own `items` list -- the least
invasive way to put it first without inventing an ordering field the rest of
the ledger tooling (board, checkpoint, the card) does not already understand.
Every reader that walks `items()` in list order sees it first for free.
"""
from __future__ import annotations

import contextlib
import datetime
import io
import json
import re
from pathlib import Path

from tools.tracker import ledger as L

PHASE_ID = "Q"
PHASE = {"id": PHASE_ID, "name": "Queued from warmup",
        "goal": "standard and rules items warmup --queue found pending",
        "exit": "each item done, or reassigned to where it belongs"}
DEFAULT_CX = "C2"
_NUM = re.compile(rf"^{PHASE_ID}-(\d+)\Z")


def _next_number(data: dict) -> int:
    n = 0
    for i in L.items(data):
        m = _NUM.match(i.get("id") or "")
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def _ensure_phase(data: dict) -> None:
    """Only when the ledger already declares `phases`: an undeclared-phases
    ledger accepts any phase string (ledger.validate() only checks membership
    when `phases` is non-empty), so nothing needs to be added there."""
    phases = data.get("phases")
    if not isinstance(phases, list) or not phases:
        return
    if not any(isinstance(p, dict) and p.get("id") == PHASE_ID for p in phases):
        phases.append(dict(PHASE))


def queue(ledger_path: Path, title: str, source_key: str, by: str = "warmup") -> bool:
    """Add one item for `source_key` unless it is already queued. Returns
    True when the ledger changed (and was written to disk)."""
    try:
        data = L.load(ledger_path)
    except (OSError, ValueError):
        return False
    for i in L.items(data):
        if i.get("queue_source") == source_key:
            return False
    _ensure_phase(data)
    n = _next_number(data)
    item = {
        "id": f"{PHASE_ID}-{n:02d}",
        "phase": PHASE_ID,
        "cx": DEFAULT_CX,
        "title": title,
        "status": "not started",
        "owner": "lead",
        "queue_source": source_key,
        "log": [{"at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                "event": "queued by warmup --queue", "by": by, "evidence": ""}],
    }
    items = data.setdefault("items", [])
    items.insert(0, item)
    data["updated"] = datetime.date.today().isoformat()
    problems = L.validate(data)
    if problems:
        # A ledger shape this helper cannot safely extend -- leave it
        # untouched rather than write something invalid.
        return False
    Path(ledger_path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    _rerender(Path(ledger_path))
    return True


def _rerender(ledger_path: Path) -> None:
    """Re-render this ledger's own page (if it has one) and the project's one
    tracker page, the same way `tracker set` and the pre-commit hook already
    do -- otherwise the write above stales the page against the ledger it was
    just taken from, and a conformance re-check queues that staleness right
    back (round 1 finding: a second `--queue` run was not a no-op)."""
    from tools.tracker import board as B
    from tools.tracker import render as R
    try:
        data = L.load(ledger_path)
    except (OSError, ValueError):
        return
    if L.own_tracker(data):
        out = R.default_out(ledger_path)
        repo = R.infer_repo(ledger_path)
        text = R.render(data, ledger_path, repo)
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists() or out.read_text() != text:
            out.write_text(text)
    # ledger_path is <project>/docs/proposals/NN-x.json.
    project = ledger_path.resolve().parent.parent.parent
    with contextlib.suppress(Exception), contextlib.redirect_stdout(io.StringIO()):
        B.main(["--project", str(project)])
