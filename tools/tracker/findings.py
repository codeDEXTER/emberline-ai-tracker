"""tracker findings -- findings-as-ledger-rows, sharing C-01/C-02's share and
risk formula with items, with a catalogue -> decided -> deferred/declined
lifecycle and triage into batches (proposal 26, C-05).

A finding -- from a review (quality-manager, any reviewer) or from testing
(test-engineer bug reports, a failing/red-first test not yet fixed) -- is a
row in a ledger's own top-level `findings` array, not only prose in a report
or a chat message:

    {"id": "F-01", "source": "review", "file": "tools/x.py", "line": 42,
     "severity": "low", "state": "catalogued",
     "value": "low", "points": 2, "impact": 1, "likelihood": 1,
     "cluster": "tools", "cause": null, "fix": null, "duplicate_of": null,
     "log": [...]}

`findings` is its own top-level array, not `items` (proposal 26 C-05's OWNS
note: one more file per finding would fragment the record the ledger
already is; validated by tools/tracker/ledger.py's `_validate_findings`,
which this module reuses through `ledger.findings()`/`findings_by_id()`).

  tracker findings add LEDGER --source S --file F [--line N] --severity SEV
                        [--title T] (--value V --points N | --unsized)
                        [--impact N] [--likelihood N] [--cluster C] [--risk R]
                        [--by NAME] [--at ISO8601]
                        --value and --points are both required unless
                        --unsized is passed instead -- otherwise a finding
                        lands unsized with nothing recording that it was
                        meant to (proposal 26 C-05's own F-01).
  tracker findings decide LEDGER FINDING_ID --quote TEXT [--value V] [--points N]
                        [--impact N] [--likelihood N] [--risk R] [--cluster C]
                        [--by NAME] [--at ISO8601]
  tracker findings defer LEDGER FINDING_ID --quote TEXT [--by NAME] [--at ISO8601]
  tracker findings decline LEDGER FINDING_ID --quote TEXT [--duplicate-of ID]
                        [--by NAME] [--at ISO8601]
  tracker findings lanes LEDGER... [--project DIR] [--json]
                        items and findings, in one shared queue, sorted by
                        tools/tracker/lanes.py's share/risk/80% cut (C-02) --
                        a parallel command to `tracker lanes` rather than a
                        change to lanes.py itself (lanes.py is C-02's, merged
                        and unowned by this item; this module only builds the
                        combined queue lanes.lanes() already knows how to
                        sort, findings shaped exactly like an item row). A
                        finding's id in this queue is proposal-qualified
                        (`26/F-01`), since a bare `F-01` is only unique
                        inside its own ledger and this command's whole point
                        is to mix ledgers; an item's id is untouched -- it
                        already avoids the collision.
  tracker findings triage LEDGER --batch ID [ID ...] [--json]
                        group a batch of decided-small findings by their
                        shared `cause` before it is worked; a finding with no
                        `cause` is its own group, named by its id; a
                        `declined` finding (a duplicate) is dropped from the
                        count.

`add`/`decide`/`defer`/`decline` write straight to the ledger, validated
before the write and re-rendered after -- the same direct-write shape as
`tracker set` and `tracker ask`. That pair is what proposal 23's M-04 points
an item lead or a builder away from, in favour of `tracker stage`; this
module is the write primitive for a new kind of row the same way `set`/`ask`
already are for items and asks, run by whoever the project has recording
findings (its own dispatcher-side use, same as `set`/`ask`).

Light path (proposal 23, M-05, built in a parallel bundle -- referenced by
name here, not depended on for its exact wording): a `decided` finding is
light when tools/tracker/lanes.py's row for it is not alone (risk 9+, or
restricted) and its points are 1-3 (`is_light`). A restricted or high-risk
finding, from either source, is never light and never batched -- the same
alone rule as C-02.

Exit codes: 0 printed/written, 1 a bad input or unknown id (nothing
written), 2 could not read/write the ledger.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from tools.tracker import ledger as L
from tools.tracker import lanes as LANES
from tools.tracker import render as R

REQUIRED_FINDING_KEYS = ("source", "file", "severity")


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def next_id(ledger: dict) -> str:
    nums = [int(fid.split("-", 1)[1]) for fid in L.findings_by_id(ledger)
            if L.FINDING_ID.match(fid) and fid.split("-", 1)[1].isdigit()]
    return f"F-{(max(nums) + 1) if nums else 1:02d}"


def _append_log(finding: dict, event: str, by: str, at: str, evidence: str = "") -> None:
    finding.setdefault("log", []).append({"at": at, "event": event, "by": by, "evidence": evidence})


# ---------------------------------------------------------------------------
# Lifecycle: pure functions on an already-loaded ledger dict, mirroring
# tools/tracker/set.py's apply_change() -- return value on success, None when
# the id names nothing, so a caller (the CLI, or a test) decides how to
# report it.

def add(ledger: dict, *, source: str, file: str, severity: str, line: int | None = None,
        title: str | None = None, value: str | None = None, points: int | None = None,
        impact: int | None = None, likelihood: int | None = None, risk: str | None = None,
        cluster: str | None = None, unsized: bool = False, by: str = "lead", at: str | None = None) -> str:
    """Catalogue a new finding. Its `state` starts `catalogued` -- visible,
    not worked -- until the sponsor decides it.

    `unsized` records that leaving `value`/`points` off was a deliberate
    choice -- the CLI (`_cmd_add`) is what actually refuses an unsized add
    unless this is set (proposal 26 C-05's own F-01: "every finding lands
    unsized" when nothing enforces it); this pure function stays permissive
    so `decide` remains the normal place a catalogued-but-not-yet-sized
    finding picks up its size."""
    at = at or _now()
    fid = next_id(ledger)
    finding: dict = {"id": fid, "source": source, "file": file, "severity": severity, "state": "catalogued"}
    for key, val in (("line", line), ("title", title), ("value", value), ("points", points),
                      ("impact", impact), ("likelihood", likelihood), ("risk", risk), ("cluster", cluster)):
        if val is not None:
            finding[key] = val
    if unsized:
        finding["unsized"] = True
    _append_log(finding, "catalogued", by, at)
    ledger.setdefault("findings", []).append(finding)
    return fid


def decide(ledger: dict, finding_id: str, *, quote: str, value: str | None = None, points: int | None = None,
           impact: int | None = None, likelihood: int | None = None, risk: str | None = None,
           cluster: str | None = None, by: str = "lead", at: str | None = None) -> dict | None:
    """catalogued|deferred -> decided: the sponsor has ruled on it (an ask,
    quoted). Sizing fields may be set or corrected here too, since a
    catalogued finding often has none yet."""
    f = L.findings_by_id(ledger).get(finding_id)
    if f is None:
        return None
    f["state"] = "decided"
    for key, val in (("value", value), ("points", points), ("impact", impact),
                      ("likelihood", likelihood), ("risk", risk), ("cluster", cluster)):
        if val is not None:
            f[key] = val
    _append_log(f, "decided", by, at or _now(), evidence=quote)
    return f


def defer(ledger: dict, finding_id: str, *, quote: str, by: str = "lead", at: str | None = None) -> dict | None:
    """catalogued|decided -> deferred: acknowledged, explicitly put off --
    still visible, still not lost, distinct from a still-open `catalogued`."""
    f = L.findings_by_id(ledger).get(finding_id)
    if f is None:
        return None
    f["state"] = "deferred"
    _append_log(f, "deferred", by, at or _now(), evidence=quote)
    return f


def decline(ledger: dict, finding_id: str, *, quote: str, duplicate_of: str | None = None,
            by: str = "lead", at: str | None = None) -> dict | None:
    """Any state -> declined: not a real finding, or -- with `duplicate_of`
    naming the survivor -- the same finding already caught elsewhere."""
    f = L.findings_by_id(ledger).get(finding_id)
    if f is None:
        return None
    f["state"] = "declined"
    if duplicate_of is not None:
        f["duplicate_of"] = duplicate_of
    _append_log(f, "declined", by, at or _now(), evidence=quote)
    return f


# ---------------------------------------------------------------------------
# Shared queue: a finding, shaped like an item row, so tools/tracker/lanes.py
# sorts both by the one share/risk formula without any change to lanes.py.

def as_queue_row(finding: dict) -> dict:
    """A finding, item-shaped, for tools/tracker/lanes.py and
    tools/tracker/route.py: `status` "done" only for a `declined` finding (a
    duplicate, or otherwise not real) -- lanes.lanes() already skips a
    `status: done` row, the same way it skips a done item. Every other state
    -- catalogued, decided, deferred -- stays in the queue, so a catalogued
    finding gets a lane and survives a `tracker lanes` run unworked, visible,
    until it is decided."""
    title = finding.get("title") or (
        f"{finding.get('source', 'finding')}: {finding.get('file', '?')}"
        + (f":{finding['line']}" if finding.get("line") is not None else ""))
    row: dict = {
        "id": finding.get("id"),
        "title": title,
        "kind": "finding",
        "source": finding.get("source"),
        "finding_state": finding.get("state"),
        "status": "done" if finding.get("state") == "declined" else None,
    }
    for key in ("value", "points", "risk", "impact", "likelihood", "cluster"):
        if finding.get(key) is not None:
            row[key] = finding[key]
    if finding.get("file"):
        row["files"] = [finding["file"]]
    return row


def queue(ledger: dict) -> list[dict]:
    """Items and findings, item-shaped, for one shared `tracker lanes` run
    (proposal 26 C-05's `done`: "a catalogued finding of either kind
    survives a tracker lanes run unworked until decided")."""
    rows = []
    for item in L.items(ledger):
        row = dict(item)
        row["kind"] = "item"
        rows.append(row)
    for finding in L.findings(ledger):
        rows.append(as_queue_row(finding))
    return rows


def lanes(ledgers: list[dict], project) -> dict:
    """Every ledger's items and findings, in one shared queue, sorted into
    lanes by tools/tracker/lanes.py's share/risk/80% cut -- unchanged.

    A finding's id is proposal-qualified here (`26/F-01`), since this is the
    cross-ledger queue the feature exists to provide and `F-01` alone is
    only unique inside its own ledger -- four ledgers each with their own
    catalogued `F-01` would otherwise render as four indistinguishable rows.
    An item's id is left as-is; it already avoids the collision. Callers
    that need the bare finding id back (`light_eligible`) unqualify it
    themselves against the same ledger."""
    combined: list[dict] = []
    for data in ledgers:
        for row in queue(data):
            if row.get("kind") == "finding":
                row["id"] = L.qualify_finding_id(data, row["id"])
            combined.append(row)
    return LANES.lanes(combined, project)


# ---------------------------------------------------------------------------
# Light path and triage (proposal 23 M-05; C-05's own batching and triage).

def light_eligible(ledger: dict, project) -> list[str]:
    """Decided-small findings from either source, not alone: eligible for
    one light-path batch (proposal 23 M-05). Computed from the same shared
    `lanes()` run everything else uses, never a second formula."""
    result = lanes([ledger], project)
    by_id = L.findings_by_id(ledger)
    qualified_to_bare = {L.qualify_finding_id(ledger, fid): fid for fid in by_id}
    out = []
    for row in result["items"]:
        fid = qualified_to_bare.get(row["id"])
        f = by_id.get(fid) if fid is not None else None
        if f is None:
            continue
        if f.get("state") == "decided" and not row.get("alone") and isinstance(row.get("points"), int) \
                and row["points"] <= 3:
            out.append(fid)
    return out


def triage(finding_ids: list[str], ledger: dict) -> list[dict]:
    """Group a batch of finding ids by their shared `cause`: findings naming
    the same cause land in one group -- {"cause", "findings": [ids], "fix"}
    -- with the fix carried by whichever member of the group names one
    first. A finding with no `cause` is its own singleton group, named by
    its id. A `declined` finding (a duplicate, or not real) is dropped --
    "excluded from the count" -- before grouping."""
    by_id = L.findings_by_id(ledger)
    groups: dict[str, dict] = {}
    order: list[str] = []
    for fid in finding_ids:
        f = by_id.get(fid)
        if f is None or f.get("state") == "declined":
            continue
        cause = f.get("cause") or f"{fid} (no shared cause)"
        if cause not in groups:
            groups[cause] = {"cause": cause, "findings": [], "fix": ""}
            order.append(cause)
        groups[cause]["findings"].append(fid)
        if not groups[cause]["fix"] and f.get("fix"):
            groups[cause]["fix"] = f["fix"]
    return [groups[c] for c in order]


def triage_log_lines(groups: list[dict]) -> list[str]:
    """One line per group -- the batch's log entry, as C-05's `done` asks
    for: the cause, the findings it covers, and the fix."""
    return [f"{g['cause']}: {', '.join(g['findings'])} -> {g['fix'] or 'fix TBD'}" for g in groups]


# ---------------------------------------------------------------------------
# CLI

def _load(path: Path) -> dict | None:
    try:
        return L.load(path)
    except (OSError, ValueError) as exc:
        print(f"tracker findings: {exc}", file=sys.stderr)
        return None


def _write(ledger_path: Path, data: dict) -> None:
    data["updated"] = datetime.date.today().isoformat()
    out = R.default_out(ledger_path)
    repo = R.infer_repo(ledger_path)
    text = R.render(data, ledger_path, repo)
    ledger_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_text() != text:
        out.write_text(text)


def _validated_write(say: str, path: Path, data: dict, fid: str) -> int:
    problems = L.validate(data)
    if problems:
        print(f"{say} {path} would not be well-formed after this change -- nothing written:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    _write(path, data)
    print(f"{say} {fid} written · page rendered")
    return 0


def _cmd_add(args) -> int:
    say = "tracker findings add:"
    if not args.unsized and (args.value is None or args.points is None):
        missing = " and ".join(f for f, v in (("--value", args.value), ("--points", args.points)) if v is None)
        print(f"{say} needs {missing} -- a finding lands unsized and lane ranking can't place it -- "
              f"or pass --unsized to record that leaving it unsized was deliberate", file=sys.stderr)
        return 1
    data = _load(args.ledger)
    if data is None:
        return 2
    fid = add(data, source=args.source, file=args.file, severity=args.severity, line=args.line,
              title=args.title, value=args.value, points=args.points, impact=args.impact,
              likelihood=args.likelihood, risk=args.risk, cluster=args.cluster, unsized=args.unsized,
              by=args.by, at=args.at)
    return _validated_write(say, args.ledger, data, fid)


def _cmd_decide(args) -> int:
    say = "tracker findings decide:"
    data = _load(args.ledger)
    if data is None:
        return 2
    f = decide(data, args.finding_id, quote=args.quote, value=args.value, points=args.points,
               impact=args.impact, likelihood=args.likelihood, risk=args.risk, cluster=args.cluster,
               by=args.by, at=args.at)
    if f is None:
        print(f"{say} {args.finding_id} is not a finding in {args.ledger} -- nothing written", file=sys.stderr)
        return 1
    return _validated_write(say, args.ledger, data, args.finding_id)


def _cmd_defer(args) -> int:
    say = "tracker findings defer:"
    data = _load(args.ledger)
    if data is None:
        return 2
    f = defer(data, args.finding_id, quote=args.quote, by=args.by, at=args.at)
    if f is None:
        print(f"{say} {args.finding_id} is not a finding in {args.ledger} -- nothing written", file=sys.stderr)
        return 1
    return _validated_write(say, args.ledger, data, args.finding_id)


def _cmd_decline(args) -> int:
    say = "tracker findings decline:"
    data = _load(args.ledger)
    if data is None:
        return 2
    f = decline(data, args.finding_id, quote=args.quote, duplicate_of=args.duplicate_of, by=args.by, at=args.at)
    if f is None:
        print(f"{say} {args.finding_id} is not a finding in {args.ledger} -- nothing written", file=sys.stderr)
        return 1
    return _validated_write(say, args.ledger, data, args.finding_id)


def _cmd_lanes(args) -> int:
    queues = []
    for path in args.ledgers:
        try:
            queues.append(L.load(path))
        except (OSError, ValueError) as exc:
            print(f"tracker findings lanes: {exc}", file=sys.stderr)
            return 2
    from tools.tracker import route as ROUTE
    project = args.project or ROUTE.project_of(args.ledgers[0])
    result = lanes(queues, project)
    print(json.dumps(result, ensure_ascii=False) if args.json else LANES.table(result))
    return 0


def _cmd_triage(args) -> int:
    say = "tracker findings triage:"
    try:
        data = L.load(args.ledger)
    except (OSError, ValueError) as exc:
        print(f"{say} {exc}", file=sys.stderr)
        return 2
    known = L.findings_by_id(data)
    missing = [fid for fid in args.batch if fid not in known]
    if missing:
        print(f"{say} not a finding in {args.ledger}: {', '.join(missing)}", file=sys.stderr)
        return 1
    groups = triage(args.batch, data)
    if args.json:
        print(json.dumps(groups, ensure_ascii=False))
    else:
        for line in triage_log_lines(groups):
            print(line)
    return 0


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker findings", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="action", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("ledger", type=Path)
    p_add.add_argument("--source", required=True, choices=L.FINDING_SOURCES)
    p_add.add_argument("--file", required=True)
    p_add.add_argument("--line", type=int)
    p_add.add_argument("--severity", required=True, choices=L.FINDING_SEVERITIES)
    p_add.add_argument("--title")
    p_add.add_argument("--value", choices=L.VALUES)
    p_add.add_argument("--points", type=int)
    p_add.add_argument("--impact", type=int)
    p_add.add_argument("--likelihood", type=int)
    p_add.add_argument("--risk", choices=L.RISKS)
    p_add.add_argument("--cluster")
    p_add.add_argument("--unsized", action="store_true",
                        help="record that leaving value/points off is deliberate")
    p_add.add_argument("--by", default="lead")
    p_add.add_argument("--at")
    p_add.set_defaults(func=_cmd_add)

    p_decide = sub.add_parser("decide")
    p_decide.add_argument("ledger", type=Path)
    p_decide.add_argument("finding_id")
    p_decide.add_argument("--quote", required=True)
    p_decide.add_argument("--value", choices=L.VALUES)
    p_decide.add_argument("--points", type=int)
    p_decide.add_argument("--impact", type=int)
    p_decide.add_argument("--likelihood", type=int)
    p_decide.add_argument("--risk", choices=L.RISKS)
    p_decide.add_argument("--cluster")
    p_decide.add_argument("--by", default="lead")
    p_decide.add_argument("--at")
    p_decide.set_defaults(func=_cmd_decide)

    p_defer = sub.add_parser("defer")
    p_defer.add_argument("ledger", type=Path)
    p_defer.add_argument("finding_id")
    p_defer.add_argument("--quote", required=True)
    p_defer.add_argument("--by", default="lead")
    p_defer.add_argument("--at")
    p_defer.set_defaults(func=_cmd_defer)

    p_decline = sub.add_parser("decline")
    p_decline.add_argument("ledger", type=Path)
    p_decline.add_argument("finding_id")
    p_decline.add_argument("--quote", required=True)
    p_decline.add_argument("--duplicate-of", dest="duplicate_of")
    p_decline.add_argument("--by", default="lead")
    p_decline.add_argument("--at")
    p_decline.set_defaults(func=_cmd_decline)

    p_lanes = sub.add_parser("lanes")
    p_lanes.add_argument("ledgers", type=Path, nargs="+")
    p_lanes.add_argument("--project", type=Path)
    p_lanes.add_argument("--json", action="store_true")
    p_lanes.set_defaults(func=_cmd_lanes)

    p_triage = sub.add_parser("triage")
    p_triage.add_argument("ledger", type=Path)
    p_triage.add_argument("--batch", nargs="+", required=True, metavar="FINDING_ID")
    p_triage.add_argument("--json", action="store_true")
    p_triage.set_defaults(func=_cmd_triage)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
