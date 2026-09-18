"""Refresh a project's generated tracker after a work cycle.

The Claude and Codex Stop hooks call this small, best-effort writer after each
assistant cycle. It keeps the page current even when a cycle changed source,
tests, or notes rather than a ledger directly; the pre-commit hook remains the
staging guard when a ledger is committed.

This module never stages or commits. A failed or non-project refresh is
reported only through the return value so a hook can never block the session.
"""
from __future__ import annotations

import argparse
import contextlib
import io
from pathlib import Path

from tools.tracker import board
from tools.tracker import ledger


def update(project) -> bool:
    """Render the project's shared board, returning whether it was attempted."""
    project = Path(project)
    try:
        if not ledger.find(project):
            return False
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = board.main(["--project", str(project)])
        return result == 0
    except Exception:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tracker auto-update")
    ap.add_argument("--project", type=Path, default=Path.cwd())
    args = ap.parse_args(argv)
    return 0 if update(args.project) else 1


if __name__ == "__main__":
    raise SystemExit(main())
