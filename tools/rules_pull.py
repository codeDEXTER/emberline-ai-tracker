"""Fast-forward a shared rules checkout when it is behind (proposal 28, R-05).

check_and_pull(rules_dir, no_pull) looks at `rules_dir` -- the common-rules
checkout warmup reads its own rules from -- and, only when it is safe, moves
it forward with `git pull --ff-only`:

  * on branch `main` (not a worktree of some other branch, not detached)
  * no tracked changes (`git status --porcelain` empty)
  * `git fetch` reaches `origin` inside a short timeout
  * `origin/main` is strictly ahead of HEAD (HEAD is its merge-base, not a
    divergent history)

Any other case -- dirty, diverged, not on main, no `origin` remote, a fetch
that fails or times out -- is left alone and named on the one line returned;
nothing here ever merges, rebases, stashes or resets. `no_pull=True` skips
the whole check (the `--no-pull` flag, and every hook, which is read-only by
its own contract).

Testable in isolation: every call takes rules_dir explicitly, so a test
exercises this against a temp clone, never against the real checkout warmup
is running from.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

FETCH_TIMEOUT = 5.0


def _git(rules_dir: Path, *args: str, timeout: float = 3.0) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(rules_dir), *args], capture_output=True,
                           text=True, timeout=timeout, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def check_and_pull(rules_dir: Path, no_pull: bool = False, fetch_timeout: float = FETCH_TIMEOUT) -> str:
    """One line: what happened, or why nothing did. Never raises."""
    rules_dir = Path(rules_dir)
    if no_pull:
        return "rules pull: skipped (--no-pull)"

    branch = _git(rules_dir, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        return f"rules pull: not pulled -- not on main (on {branch or 'unknown branch'})"

    status = _git(rules_dir, "status", "--porcelain")
    if status is None:
        return "rules pull: not pulled -- could not read git status"
    if status.strip():
        return "rules pull: not pulled -- checkout has tracked changes"

    try:
        fetched = subprocess.run(["git", "-C", str(rules_dir), "fetch", "--quiet", "origin", "main"],
                                 capture_output=True, text=True, timeout=fetch_timeout, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return "rules pull: not pulled -- fetch timed out or failed"
    if fetched.returncode != 0:
        return "rules pull: not pulled -- fetch failed"

    local = _git(rules_dir, "rev-parse", "HEAD")
    remote = _git(rules_dir, "rev-parse", "origin/main")
    if local is None or remote is None:
        return "rules pull: not pulled -- could not resolve refs"
    if local == remote:
        return "rules pull: already up to date"

    base = _git(rules_dir, "merge-base", "HEAD", "origin/main")
    if base != local:
        return "rules pull: not pulled -- diverged from origin/main"

    pulled = subprocess.run(["git", "-C", str(rules_dir), "pull", "--ff-only", "--quiet"],
                            capture_output=True, text=True, timeout=fetch_timeout, check=False)
    if pulled.returncode != 0:
        return "rules pull: not pulled -- ff-only pull failed"
    return f"rules pull: fast-forwarded {local[:8]} → {remote[:8]}"
