"""The resolution the real-project checks depend on.

`tests/projects.py` answers "where do this checkout's sibling projects live",
for the two modules that read real projects rather than fixtures. It is the
third place in two days to get that question wrong (#113, #116), so the answer
is pinned here rather than trusted.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from projects import GIT, apps_dir  # noqa: E402


class TheRealProjectChecksAreNotVacuous(unittest.TestCase):
    """The checks above are the only ones that read real documents. If they
    resolve to a directory with no projects in it they skip, silently, and
    the suite stays green while checking nothing -- which is exactly what
    happened everywhere the suite is actually run. These pin the resolution
    itself, so a regression fails loudly instead of going quiet."""

    def test_no_project_is_resolved_as_root_parent(self):
        """Structural guard, in the shape of #116's 'no home directory is
        baked into the default'. Asserting that the real-project checks pass
        proves nothing -- they pass hardest when they are skipping. What can
        be asserted is that the broken expression is not in the file."""
        # Assembled, so this guard's own text is not a hit for itself.
        # Prose may still name the expression in backticks -- the docstrings
        # here explain the bug and would otherwise trip their own guard.
        forbidden = "ROOT" + ".parent"
        offenders = [f"{f.name}:{n}: {line.strip()}"
                     for f in sorted(Path(__file__).resolve().parent.glob("*.py"))
                     for n, line in enumerate(f.read_text().splitlines(), 1)
                     if forbidden in line and f"`{forbidden}`" not in line]
        self.assertEqual(
            offenders, [],
            f"real projects must be resolved with apps_dir(), not {forbidden} -- "
            "the latter is '.worktrees/' from a task worktree, which is where "
            "bin/land runs this suite. Every test module, not just one.")

    def test_apps_dir_finds_the_projects_from_inside_a_worktree(self):
        """Hermetic: builds its own <apps>/<repo>/.worktrees/<name> layout
        rather than depending on this Mac having one. A regression test that
        needs the real machine stops testing the moment it runs anywhere
        else -- which is the bug it is guarding against."""
        with tempfile.TemporaryDirectory() as tmp:
            apps = (Path(tmp) / "apps").resolve()
            repo = apps / "common-rules"
            (apps / "finance-tracker").mkdir(parents=True)
            repo.mkdir(parents=True)

            def git(*args, cwd=repo):
                r = subprocess.run([GIT, "-C", str(cwd), *args],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "T")
            (repo / "README.md").write_text("x\n")
            git("add", "-A")
            git("commit", "-qm", "init")
            wt = repo / ".worktrees" / "task"
            git("worktree", "add", "-q", "-b", "task", str(wt))

            self.assertEqual(apps_dir(repo), apps,
                             "wrong answer from the main checkout")
            self.assertEqual(apps_dir(wt), apps,
                             "wrong answer from a worktree -- the whole bug")
            # The expression this replaces, and what it would have said here.
            self.assertEqual(wt.parent, repo / ".worktrees")
            self.assertFalse((wt.parent / "finance-tracker").exists())

    def test_apps_dir_is_none_outside_a_git_repository(self):
        """No repository to ask means no answer, not a wrong one. The callers
        skip on None rather than resolving something arbitrary."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(apps_dir(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
