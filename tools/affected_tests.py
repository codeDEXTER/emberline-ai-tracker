#!/usr/bin/env python3
"""tools/affected_tests.py -- map changed files to the test files that
touch them (common-rules proposal 23, lever M-02).

  python3 tools/affected_tests.py [--base REF] [--tests-dir DIR] [FILE...]

Prints, one per line, paths of test files under DIR (default "tests")
that plausibly exercise the given files, so a builder's own gate can run
just those instead of the full suite -- the full suite still runs once
per bundle at integration (see bin/land / bin/quiet). Research: ~50% test
time (Instawork). Pairs with proposal 26 C-03.

Where the changed files come from:
  - FILE arguments, if given, are used as-is;
  - otherwise, with `--base REF`, changed files are
    `git diff --name-only REF...HEAD`;
  - otherwise, changed files are today's working tree: the union of
    `git diff --name-only` (unstaged) and `git diff --name-only --cached`
    (staged).
Running with no FILE arguments outside a git repository (or before any
commit) is a usage error (exit 2) -- pass FILE arguments explicitly
instead of guessing.

Matching, deliberately generous -- a false positive costs a few extra
seconds of a builder's own gate; a false negative hides a break the full
suite would have caught until integration:
  - a changed file that is itself a test file maps to itself;
  - `path/to/<stem>.py` (or an extensionless script like `bin/quiet`) maps
    to `DIR/test_<stem>.py` when that file exists;
  - any test file under DIR whose text contains the changed file's stem,
    or its dotted import path built from the path relative to the repo
    root, as a whole word is included too -- this is a plain text search,
    not an AST walk, so it catches both `from tools.tracker import stage`
    and a bare `import stage` without needing to resolve either.

Exit codes: 0 some tests found (printed, one per line); 1 no test file
matched anything changed (nothing to run -- the caller should fall back
to the full suite); 2 bad usage.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _git_diff_names(args: list[str]) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", *args],
            capture_output=True, text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return [line for line in proc.stdout.splitlines() if line.strip()]


def changed_files_from_git(base: str | None) -> list[str] | None:
    """Return changed file paths, de-duplicated and order-preserved, or
    None when git could not answer (not a repository, bad ref, ...)."""
    if base:
        names = _git_diff_names([f"{base}...HEAD"])
        return names
    unstaged = _git_diff_names([])
    staged = _git_diff_names(["--cached"])
    if unstaged is None or staged is None:
        return None
    seen: dict[str, None] = {}
    for name in [*staged, *unstaged]:
        seen.setdefault(name, None)
    return list(seen)


def _dotted_module(path: Path) -> str:
    return ".".join(path.with_suffix("").parts)


def find_affected_tests(changed: list[str], tests_dir: Path) -> list[Path]:
    all_tests = sorted(p for p in tests_dir.glob("test_*.py") if p.is_file())
    affected: set[Path] = set()

    for raw in changed:
        cp = Path(raw)

        # A changed test file maps to itself.
        if cp.name.startswith("test_") and cp.suffix == ".py":
            candidate = tests_dir / cp.name
            if candidate.exists():
                affected.add(candidate)
            continue

        stem = cp.stem
        if not stem:
            continue

        # Direct naming convention: bin/quiet, tools/x/stage.py -> test_quiet.py, test_stage.py
        direct = tests_dir / f"test_{stem}.py"
        if direct.exists():
            affected.add(direct)

        # Content search: whole-word stem, or the full dotted module path
        # when it differs from the bare stem (e.g. tools.tracker.stage).
        stem_re = re.compile(r"\b" + re.escape(stem) + r"\b")
        dotted = _dotted_module(cp)
        dotted_re = re.compile(re.escape(dotted)) if dotted and dotted != stem else None

        for t in all_tests:
            if t in affected:
                continue
            try:
                text = t.read_text(errors="ignore")
            except OSError:
                continue
            if stem_re.search(text) or (dotted_re and dotted_re.search(text)):
                affected.add(t)

    return sorted(affected)


def _parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=None,
                     help="compare against this ref instead of the working tree")
    ap.add_argument("--tests-dir", default="tests")
    ap.add_argument("files", nargs="*", metavar="FILE")
    return ap.parse_args(argv)


def main(argv):
    args = _parse_args(argv)
    tests_dir = Path(args.tests_dir)

    if args.files:
        changed = args.files
    else:
        changed = changed_files_from_git(args.base)
        if changed is None:
            print("affected-tests: not a git repository (or bad --base) -- "
                  "pass FILE arguments explicitly", file=sys.stderr)
            return 2
        if not changed:
            print("affected-tests: nothing changed", file=sys.stderr)
            return 1

    affected = find_affected_tests(changed, tests_dir)
    if not affected:
        print("affected-tests: no test file matched -- run the full suite", file=sys.stderr)
        return 1

    for t in affected:
        print(t)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
