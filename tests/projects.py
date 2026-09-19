"""Where this checkout's sibling projects live.

Shared by every test that reads a *real* project rather than a fixture --
`test_proposal_lifecycle` and `test_rulecheck` both do. It is one module
rather than a copy in each because two copies of a path rule is how the two
drift, and this exact rule has already been got wrong three times in two days:
`bin/rulecheck`'s hardcoded default (#116), `bin/milestones`' `RULES.parent`,
and the real-project checks in both modules named above.

Not named `test_*.py`, so `unittest discover -s tests` does not collect it.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Command Line Tools git, because a pending Xcode licence breaks plain `git`.
GIT = next((g for g in ("/Library/Developer/CommandLineTools/usr/bin/git",
                        "/usr/bin/git") if Path(g).exists()), "git")


def apps_dir(start: Path | None = None) -> Path | None:
    """Where this checkout's sibling projects live, read at runtime.

    These checks used to resolve them as `ROOT.parent`, which is
    `apps` only from the main checkout. From a task worktree
    (`<apps>/common-rules/.worktrees/<name>`) it is `.worktrees/`, which holds
    no projects -- so every real-project check found nothing and passed. That
    is both places the suite is actually run: `bin/land` tests the branch
    worktree, and CI checks out a repo with no siblings at all. The checks
    could only ever fail in the one place nobody runs them.

    Same class as `bin/rulecheck`'s hardcoded rules path (#116) and
    `bin/milestones`' `RULES.parent` -- a path derived from an assumption
    about the layout rather than from something true at runtime, and invisible
    precisely where it was wrong.

    `git rev-parse --git-common-dir` names the *main* checkout's `.git` from
    inside a worktree as readily as from the checkout itself, so the answer is
    read rather than assumed. It is the corrected form of what `ROOT.parent`
    was reaching for, not a new policy: `bin/milestones` and `bin/pulse` name
    `apps` outright, and rightly -- `--all` has to find every
    project on this Mac, which is a claim about the machine. A test only needs
    the projects beside *this* checkout, which is a fact about the repo.

    Returns None when there is no git repository to ask.
    """
    start = Path(start or ROOT)
    r = subprocess.run([GIT, "-C", str(start), "rev-parse", "--git-common-dir"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    common = Path(r.stdout.strip())
    if not common.is_absolute():
        common = (start / common).resolve()
    return common.parent.parent
