"""tools/itemfacts.py -- facts assembled once for `bin/pr-body` and
`bin/item-notes` (proposal 31, O-05/O-06).

WHY. Three times per item a lead re-composes prose it has already read: the
PR body, the `ruflo-item done` summary, and the `tracker set --event` text --
each time from the same handful of facts (the ledger item, the diff against
main, the branch's commits). Gathering those facts is identical work whether
the draft becomes a PR body or a done note, so it lives once here rather than
twice over in `bin/pr-body` and `bin/item-notes`. Two copies would drift --
the PR quoting one file count and the ledger event another -- which is worse
than either script alone.

THE LINE THIS MODULE DOES NOT CROSS (proposal 31's Decided section, D4):
these are facts, read off the ledger and off git, never a verdict. Nothing
here decides whether an item is done, whether to merge, or what tier it is.
A function below answers "what changed" and "what does the ledger say" --
never "is this good enough". That judgment stays with the model reading the
draft these facts feed.

Uses `tools/tracker/ledger.py` to find and load ledgers rather than
re-parsing `docs/proposals/*.json` by hand, and `tools/tracker/parts.py` for
an item's lettered parts, for the same reason ledger.py itself gives for
never re-parsing JSON: one place that knows the ledger's shape.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from tools.tracker import ledger as L
from tools.tracker import parts as PARTS


class ItemNotFound(ValueError):
    """No ledger under the project's docs/proposals declares this item id."""


@dataclass(frozen=True)
class FileChange:
    path: str
    insertions: int | None  # None for a binary file, where git reports "-"
    deletions: int | None

    @property
    def is_test(self) -> bool:
        p = Path(self.path)
        return p.name.startswith("test_") or "tests" in p.parts


@dataclass(frozen=True)
class DiffFacts:
    base: str
    files: list[FileChange]

    @property
    def test_file_count(self) -> int:
        return sum(1 for f in self.files if f.is_test)

    @property
    def total_insertions(self) -> int:
        return sum(f.insertions or 0 for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions or 0 for f in self.files)


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str


@dataclass(frozen=True)
class BranchFacts:
    branch: str
    base: str
    commits: list[Commit]


@dataclass(frozen=True)
class ItemFacts:
    ledger_path: Path
    item: dict
    parts: list[dict]


def _git(project: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r.stdout


def find_ledger_for_item(project: Path, item_id: str) -> Path:
    """Which ledger under `project`'s docs/proposals declares `item_id`.
    Raises ItemNotFound, naming the id, when none does -- callers print that
    and exit non-zero rather than silently drafting an empty skeleton."""
    for path in L.find(project):
        data = L.load(path)
        if item_id in L.by_id(data):
            return path
    raise ItemNotFound(item_id)


def load_item(project: Path, item_id: str, ledger_arg: str | None = None) -> ItemFacts:
    """The item (and its parts, if any) as recorded in the ledger. Resolves
    the ledger from the item id when `ledger_arg` is not given. Raises
    ItemNotFound (naming the id) when the item is not in the given ledger,
    or in none under the project."""
    path = Path(ledger_arg) if ledger_arg else find_ledger_for_item(project, item_id)
    data = L.load(path)
    item = L.by_id(data).get(item_id)
    if item is None:
        raise ItemNotFound(item_id)
    return ItemFacts(ledger_path=path, item=item, parts=PARTS.parts(item))


def diff_facts(project: Path, base: str) -> DiffFacts:
    """Files changed between `base` and HEAD, with insertion/deletion
    counts, from `git diff --numstat base...HEAD` -- the three-dot form, so a
    base that has moved past the branch's fork point does not pull in
    unrelated commits from the other side."""
    out = _git(project, "diff", "--numstat", f"{base}...HEAD")
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        ins, dele, path = line.split("\t", 2)
        files.append(FileChange(
            path=path,
            insertions=None if ins == "-" else int(ins),
            deletions=None if dele == "-" else int(dele),
        ))
    return DiffFacts(base=base, files=files)


def branch_facts(project: Path, base: str) -> BranchFacts:
    """The current branch's name and its commits not on `base`, oldest
    first (the order a reader would want to walk them in)."""
    branch = _git(project, "rev-parse", "--abbrev-ref", "HEAD").strip()
    log = _git(project, "log", "--reverse", "--format=%h%x09%s", f"{base}..HEAD")
    commits = []
    for line in log.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        commits.append(Commit(sha=sha, subject=subject))
    return BranchFacts(branch=branch, base=base, commits=commits)


def project_root(explicit: str | None) -> Path:
    """--project DIR when given; otherwise `git rev-parse --show-toplevel`
    of the current directory, falling back to the current directory itself
    when that fails (matches bin/ruflo-item's own project_root())."""
    if explicit:
        return Path(explicit).resolve()
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip()).resolve()
    return Path.cwd().resolve()
