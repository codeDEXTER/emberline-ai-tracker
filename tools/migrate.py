"""warmup --migrate -- a running project moves onto the standard (proposal 19, W-12).

  warmup --project DIR --migrate [--dry-run] [--at ISO]

Reheat, in proposal 19's words: a session already running on its own rules is
moved onto the standard without a restart. The rules live on disk and
CLAUDE.md is reloaded every turn, so what has to change is the disk.

In order, and each step says what it did:

  1. derecord -- seeds HANDOFF.md, the operating rules and the lead prompt
     where missing, installs the checkpoint hooks and the /warmup skill.
  2. tracker import -- when the project has no ledger, its milestone plan
     becomes one, under the next free proposal number.
  3. supersede -- each rule the standard replaces moves, verbatim, into a
     dated block under `## Superseded` in docs/OPERATING-RULES.md. A rule is
     moved only when its bold lead matches templates/supersedes.json; nothing
     is guessed, and nothing is deleted.
  4. CLAUDE.md -- the warm-up pointer, between markers. CLAUDE.md is reserved
     for the sponsor (land will not land a branch touching it), so this says it
     changed and leaves the commit to him.

Migrate commits nothing. A second run changes nothing. --dry-run writes
nothing -- it does not run derecord at all -- and lists what it would do.

Exit codes: 0 migrated (or nothing to do, or a dry run), 1 a step failed,
2 not a git repository.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RULES_DIR))

from tools.tracker import ledger as L  # noqa: E402

BEGIN, END = "<!-- common-rules:warmup -->", "<!-- /common-rules:warmup -->"
BULLET = re.compile(r"^- \*\*(.+?)\*\*")
SUPERSEDED_INTRO = ("Rules this project followed that a later standard replaced. Moved here verbatim and "
                    "dated, never deleted: a session that still remembers one can see what replaced it, and why.")


def git(project: Path, *args: str) -> str | None:
    r = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True, check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def supersedes() -> list[dict]:
    try:
        return json.loads((RULES_DIR / "templates" / "supersedes.json").read_text())["rules"]
    except (OSError, ValueError, KeyError):
        return []


def rule_blocks(lines: list[str]) -> list[tuple[int, int, str, str]]:
    """(start, end, lead, section) for every `- **lead**` rule outside
    ## Superseded. A rule runs on through indented lines, and through blank
    lines when the next non-blank line is still indented -- so a rule with a
    second paragraph moves whole, never split."""
    out, section, retired, i, n = [], "", False, 0, len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("## "):
            section = line[3:].strip()
            retired = line.strip().lower().startswith("## superseded")
            i += 1
            continue
        m = BULLET.match(line)
        if m and not retired:
            j = i + 1
            while j < n:
                if lines[j].strip() and lines[j][:1] in (" ", "\t"):
                    j += 1
                    continue
                if not lines[j].strip():
                    k = j
                    while k < n and not lines[k].strip():
                        k += 1
                    if k < n and lines[k][:1] in (" ", "\t"):
                        j = k
                        continue
                break
            out.append((i, j, m.group(1), section))
            i = j
            continue
        i += 1
    return out


def supersede(text: str, rules: list[dict], date: str) -> tuple[str, list[tuple[str, str, dict]]]:
    lines = text.splitlines()
    chosen = []
    for start, end, lead, section in rule_blocks(lines):
        rule = next((r for r in rules if re.search(r["match"], lead.strip())), None)
        if rule:
            chosen.append((start, end, lead, section, rule))
    if not chosen:
        return text, []

    # The rule as it stands now goes where the old one stood, so a project
    # that already has its own OPERATING-RULES keeps what still holds. Moving
    # the whole rule and leaving only a one-line replaced_by in a heading cost
    # the PhotoVault engine "never scrap old content" and "green is merged with
    # its tests run" -- found by that engine reviewing the dry run, 13 Sep,
    # before anything was written.
    removed = {i for start, end, *_ in chosen for i in range(start, end)}
    starts = {start: rule for start, _end, _lead, _section, rule in chosen}
    keep = []
    for i, l in enumerate(lines):
        if i in starts and starts[i].get("replacement"):
            keep += starts[i]["replacement"].splitlines()
            keep.append(f"  (Replaced {date} under common-rules proposal 19; the earlier wording is under Superseded, below.)")
        if i not in removed:
            keep.append(l)
    while keep and not keep[-1].strip():
        keep.pop()

    entries: list[str] = []
    for start, end, lead, section, rule in chosen:
        name = lead.strip().rstrip(".,;:")
        entries += ["", f"### {date} · superseded by proposal 19: “{name}” → {rule['replaced_by']}", "",
                    f"Was in “{section}”. Why: {rule['reason']}.", ""] + lines[start:end]

    head = next((i for i, l in enumerate(keep) if l.strip().lower().startswith("## superseded")), None)
    if head is None:
        keep += ["", "## Superseded", "", SUPERSEDED_INTRO] + entries
    else:
        stop = next((i for i in range(head + 1, len(keep)) if keep[i].startswith("## ")), len(keep))
        while stop > head + 1 and not keep[stop - 1].strip():
            stop -= 1
        keep[stop:stop] = entries
    return "\n".join(keep) + "\n", [(lead.strip(), section, rule) for _, _, lead, section, rule in chosen]


def pointer_block() -> str:
    return "\n".join([
        BEGIN,
        "## Warm-up (common-rules proposal 19)",
        "",
        "Start every session with `/warmup`, and run it again after a compaction. Read, in order: HANDOFF.md → "
        "docs/OPERATING-RULES.md → the ledger(s) in docs/proposals/NN-*.json → the latest "
        "docs/handovers/*-checkpoint.md → common-rules' CLAUDE-workflow.md.",
        "",
        "The ledger is the record. A compaction summary is a paraphrase: quote rulings from disk.",
        END,
    ])


def claude_md(path: Path, dry_run: bool) -> str:
    block = pointer_block()
    text = path.read_text() if path.is_file() else ""
    if BEGIN in text and END in text:
        a, b = text.index(BEGIN), text.index(END) + len(END)
        if text[a:b] == block:
            return "CLAUDE.md: warm-up pointer already current"
        new = text[:a] + block + text[b:]
        verb = "updated"
    else:
        new = (text.rstrip("\n") + "\n\n" if text.strip() else "") + block + "\n"
        verb = "added"
    if dry_run:
        return f"CLAUDE.md: would have the warm-up pointer {verb} -- CLAUDE.md is reserved for the sponsor"
    path.write_text(new)
    return (f"CLAUDE.md: warm-up pointer {verb} -- CLAUDE.md is reserved for the sponsor (land will not land it): "
            f"review the change and commit it yourself")


def next_number(project: Path) -> int:
    nums = [int(m.group(1)) for p in (project / "docs" / "proposals").glob("*")
            if p.is_file() and (m := re.match(r"^(\d+)-", p.name))]
    return max(nums, default=0) + 1


def migrate(project: Path, at: str, dry_run: bool) -> int:
    top = git(project, "rev-parse", "--show-toplevel")
    if top is None:
        print(f"warmup --migrate: {project} is not inside a git repository", file=sys.stderr)
        return 2
    project = Path(top)
    would = "would " if dry_run else ""
    out = [f"MIGRATE · {project.name} onto proposal 19" + (" -- dry run, nothing written" if dry_run else "")]
    code = 0

    # 1. derecord
    if dry_run:
        out.append("1 derecord: would run (seed HANDOFF.md, operating rules and lead prompt where missing; "
                   "checkpoint hooks; /warmup skill)")
    else:
        r = subprocess.run([str(RULES_DIR / "bin" / "derecord"), str(project)],
                           capture_output=True, text=True, check=False)
        out.append("1 derecord:")
        out += [f"  {l.strip()}" for l in r.stdout.splitlines() if l.strip()]
        if r.returncode != 0:
            out.append(f"  derecord exited {r.returncode}: {r.stderr.strip()}")
            code = 1

    # 2. import
    existing = L.find(project)
    if existing:
        out.append(f"2 import: a ledger is already here ({', '.join(p.name for p in existing)}) -- nothing to import")
    else:
        n = next_number(project)
        cmd = [str(RULES_DIR / "bin" / "tracker"), "import", "--project", str(project),
               "--proposal", str(n), "--title", "Milestone plan", "--at", at] + (["--dry-run"] if dry_run else [])
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        said = (r.stdout.strip() or r.stderr.strip())
        if r.returncode == 2:
            out.append("2 import: no plan to import -- start a ledger from common-rules' templates/ledger.json")
        elif r.returncode == 0:
            out.append(f"2 import: {said}")
        else:
            out.append(f"2 import failed: {said}")
            code = 1

    # 3. supersede
    rules_path = project / "docs" / "OPERATING-RULES.md"
    if not rules_path.is_file():
        out.append("3 supersede: no docs/OPERATING-RULES.md yet -- nothing to supersede")
    else:
        text = rules_path.read_text()
        new, moved = supersede(text, supersedes(), at[:10])
        if not moved:
            out.append("3 supersede: nothing to supersede (templates/supersedes.json matches no rule here)")
        else:
            out.append(f"3 supersede: {would}move {len(moved)} rule(s) into ## Superseded, verbatim and dated:")
            for lead, section, rule in moved:
                out.append(f"  “{lead}” (from “{section}”) → {rule['replaced_by']}")
                m = re.match(r"^- \*\*(.+?)\*\*", rule.get("replacement", ""))
                out.append(f"    {'would be ' if dry_run else ''}replaced in place by “{m.group(1)}”" if m
                           else "    no replacement rule in supersedes.json -- only the replaced_by sentence remains")
            if not dry_run:
                rules_path.write_text(new)

    # 4. CLAUDE.md
    out.append("4 " + claude_md(project / "CLAUDE.md", dry_run))
    out.append("Nothing committed. Review with `git status`, and commit what you keep." if not dry_run
               else "Run again without --dry-run to apply.")
    print("\n".join(out))
    return code
