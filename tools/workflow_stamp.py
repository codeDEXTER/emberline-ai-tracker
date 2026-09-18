"""Shared logic for docs/workflow.html's version stamp (proposal 31, O-12).

Imported by both `bin/workflow-stamp` (writes the stamp, regenerates the
png, and can just --check the two) and `tests/test_workflow_stamp.py` (the
gate that caught main going red on 17 Sep). One implementation, not two: a
tool and a test computing "the required stamp" independently is exactly how
they end up disagreeing, and nobody can then tell which one is right.

ROOT normally resolves to this checkout of common-rules -- the same repo
`docs/workflow.html` and `CLAUDE-workflow.md` live in. `WORKFLOW_STAMP_ROOT`
overrides it, read once at import time, the same way `commit-if-green`
reads `COMMON_RULES_DIR` -- so `bin/workflow-stamp`'s own tests can point
the whole module at a throwaway fixture repo instead of writing into the
real checkout that is running the test suite.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(os.environ.get("WORKFLOW_STAMP_ROOT")
            or Path(__file__).resolve().parent.parent)
PAGE = ROOT / "docs" / "workflow.html"
PNG = ROOT / "docs" / "workflow.png"
RULES_FILE = "CLAUDE-workflow.md"
STAMP_RE = re.compile(r"rules version (\d+)(?: · (\d{4}-\d{2}-\d{2}))?")


def git(*args: str) -> str:
    exe = "/Library/Developer/CommandLineTools/usr/bin/git"
    if not Path(exe).exists():
        exe = "git"
    return subprocess.run([exe, "-C", str(ROOT), *args],
                          capture_output=True, text=True, check=False).stdout.strip()


def stamped_version() -> int:
    """The 'rules version N' the page currently claims. Raises ValueError
    (not AssertionError -- this module is used outside of tests too) when
    the page is missing or carries no stamp at all."""
    if not PAGE.exists():
        raise ValueError(f"{PAGE} does not exist")
    m = STAMP_RE.search(PAGE.read_text())
    if not m:
        raise ValueError(f"{PAGE} carries no 'rules version N' stamp")
    return int(m.group(1))


def rules_version() -> int:
    """Commit count at the last commit that touched CLAUDE-workflow.md.

    Deliberately not `rev-list --count HEAD`. A stamp written inside the commit
    it counts can never name itself — it would always be one behind, and every
    fix would introduce the same off-by-one again. Pinning it to the last
    *rules* change makes a commit that only edits the page a no-op for this
    check, which is what stops the regress.
    """
    sha = git("log", "-1", "--format=%H", "--", RULES_FILE)
    if not sha:
        raise ValueError(f"no commit in this repo has ever touched {RULES_FILE}")
    return int(git("rev-list", "--count", sha))


def rules_date() -> str:
    """Committer date (YYYY-MM-DD) of the same commit rules_version() counts
    at -- the date printed beside the number in the stamp."""
    sha = git("log", "-1", "--format=%H", "--", RULES_FILE)
    return git("show", "-s", "--format=%cs", sha)


def head_version() -> int:
    """Commit count at HEAD -- used only as the 'not from the future' bound
    (a stamp is written for the commit it lands as, one ahead of HEAD at
    write time), never as the stamp's own definition."""
    return int(git("rev-list", "--count", "HEAD"))


def png_is_stale() -> bool:
    """True when docs/workflow.png was last committed before the last
    change to docs/workflow.html (mirrors what
    test_the_png_beside_it_is_not_stale checks). False -- not stale -- when
    either file has no commit history yet, since there is then nothing to
    compare (a brand-new fixture repo, for instance)."""
    page_at = git("log", "-1", "--format=%ct", "--", "docs/workflow.html")
    png_at = git("log", "-1", "--format=%ct", "--", "docs/workflow.png")
    if not page_at or not png_at:
        return False
    return int(png_at) < int(page_at)


def write_stamp(version: int, date: str) -> None:
    """Rewrite the 'rules version N · YYYY-MM-DD' stamp in place. Refuses
    (ValueError) rather than writing nothing back, the same way
    stamped_version() refuses to read one that isn't there."""
    text = PAGE.read_text()
    new_text, n = STAMP_RE.subn(f"rules version {version} · {date}", text, count=1)
    if n == 0:
        raise ValueError(f"{PAGE} carries no 'rules version N' stamp to rewrite")
    PAGE.write_text(new_text)
