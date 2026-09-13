"""tracker check -- did the ledger move with the code? (proposal 19, W-03)

  tracker check [--project DIR] [--base REF] [--head REF]      default: main, HEAD

A branch whose commits name a ledger item must also move that item's row.
The rule existed as prose in the PhotoVault engine ("after every state change
of any item you update its status ... and commit the ledger") and was kept on
its best day, 58 ledger commits on 13 September -- which is exactly what a
prose rule looks like when someone is watching. Prose rules measured 1-in-7
compliance in common-rules; this makes it the same on a day nobody is.

WHAT "MOVED" MEANS. The item's JSON object differs between the merge-base and
the branch tip: a new row, a new log entry, a status change. It is read from
git with `git show <ref>:<ledger>`, never from the working tree and never from
a timestamp -- a date an agent typed into a log is a claim, the diff is the
evidence. Only ids that exist in a ledger on either side count, so "SHA-256"
in a commit message is never taken for an item.

Exit codes: 0 every named item moved (or none named, or no ledger), 1 at least
one did not, 2 could not check (not a git repo, a ref that does not exist).
`bin/land` consumes exit 1 and nothing else, like its sibling gates.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ID_SHAPE = re.compile(r"\b([A-Z][A-Z0-9]*-\d{2,})\b")
# Top level of docs/proposals only -- the same namespace ledger.find() reads,
# so docs/proposals/tracker/ (generated pages) can never be mistaken for one.
LEDGER_PATH = re.compile(r"^docs/proposals/\d+-[^/]+\.json$")


class GitError(Exception):
    pass


def git(project: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise GitError((r.stderr or r.stdout).strip() or f"git {' '.join(args)} failed")
    return r.stdout


def ledgers_at(project: Path, ref: str) -> list[str]:
    try:
        names = git(project, "ls-tree", "-r", "--name-only", ref, "--", "docs/proposals").splitlines()
    except GitError:
        return []
    return sorted(n for n in names if LEDGER_PATH.match(n))


def rows_at(project: Path, ref: str, paths: list[str]) -> dict[str, dict[str, str]]:
    """{ledger path: {item id: canonical JSON of the item}} at `ref`. A ledger
    absent at `ref`, or not parseable there, contributes no rows."""
    out: dict[str, dict[str, str]] = {}
    for path in paths:
        try:
            data = json.loads(git(project, "show", f"{ref}:{path}"))
        except (GitError, json.JSONDecodeError):
            continue
        # docs/proposals holds data files with a ledger's name shape. One whose
        # JSON is an array crashed here, and land reads Python's exit 1 as "the
        # row did not move" -- a refusal with a traceback for its reason.
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            continue
        out[path] = {i["id"]: json.dumps(i, sort_keys=True)
                     for i in data["items"] if isinstance(i, dict) and "id" in i}
    return out


def named_items(project: Path, base: str, head: str) -> dict[str, str]:
    """{item-shaped id: subject of the first commit in base..head naming it}."""
    raw = git(project, "log", "--reverse", "--format=%h %s%x00%B%x1e", f"{base}..{head}")
    found: dict[str, str] = {}
    for record in raw.split("\x1e"):
        if not record.strip():
            continue
        subject, _, body = record.strip().partition("\x00")
        for iid in ID_SHAPE.findall(subject + "\n" + body):
            found.setdefault(iid, subject)
    return found


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="tracker check", description=__doc__.splitlines()[0])
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("--base", default="main")
    ap.add_argument("--head", default="HEAD")
    args = ap.parse_args(argv)
    project = args.project

    try:
        for ref in (args.base, args.head):
            git(project, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        mb = git(project, "merge-base", args.base, args.head).strip()
        named = named_items(project, mb, args.head)
    except GitError as exc:
        print(f"tracker check: could not check -- {exc}", file=sys.stderr)
        return 2

    paths = sorted(set(ledgers_at(project, args.head)) | set(ledgers_at(project, mb)))
    if not paths:
        print(f"tracker check: no ledger under docs/proposals at {args.head} -- nothing to check")
        return 0

    head_rows = rows_at(project, args.head, paths)
    base_rows = rows_at(project, mb, paths)
    known = {iid for rows in (*head_rows.values(), *base_rows.values()) for iid in rows}
    named = {iid: subj for iid, subj in named.items() if iid in known}
    if not named:
        print(f"tracker check: no ledger item named in {mb[:7]}..{args.head}")
        return 0

    stuck = []
    for iid in sorted(named):
        moved_in = [p for p in paths
                    if (iid in head_rows.get(p, {}) or iid in base_rows.get(p, {}))
                    and head_rows.get(p, {}).get(iid) != base_rows.get(p, {}).get(iid)]
        if moved_in:
            print(f"  {iid} moved in {', '.join(Path(p).name for p in moved_in)}")
        else:
            where = ", ".join(Path(p).name for p in paths if iid in head_rows.get(p, {}))
            print(f"  {iid} did not move -- named in \"{named[iid]}\", its row in {where} "
                  f"is unchanged since {mb[:7]}")
            stuck.append(iid)

    print(f"tracker check: {len(named)} named, {len(named) - len(stuck)} moved, {len(stuck)} did not move")
    return 1 if stuck else 0
