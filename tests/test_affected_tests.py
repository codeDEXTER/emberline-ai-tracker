"""tools/affected_tests.py -- map changed files to the test files that
touch them (common-rules proposal 23, lever M-02).

Why: a builder's own gate should run only the tests touching its changed
files; the full suite runs once per bundle at integration (bin/land,
bin/quiet). Research: ~50% test time (Instawork).

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "affected_tests.py"

sys.path.insert(0, str(ROOT))
from tools.affected_tests import find_affected_tests  # noqa: E402


class TestFindAffectedTestsPureMapping(unittest.TestCase):
    """The mapping logic itself, no git involved -- a small fixture tree
    of source and test files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "tests").mkdir()
        (self.root / "bin").mkdir()
        (self.root / "tools").mkdir()

        # Direct-name convention: bin/quiet <-> tests/test_quiet.py
        (self.root / "bin" / "quiet").write_text("#!/usr/bin/env python3\n")
        (self.root / "tests" / "test_quiet.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_x(self): pass\n"
        )

        # Content-search convention: tools/widget.py imported by test_other.py
        (self.root / "tools" / "widget.py").write_text("def build():\n    return 1\n")
        (self.root / "tests" / "test_other.py").write_text(
            "from tools import widget\nimport unittest\n"
            "class T(unittest.TestCase):\n    def test_x(self): widget.build()\n"
        )

        # An orphan test that references nothing changed.
        (self.root / "tests" / "test_orphan.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_x(self): pass\n"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_direct_name_convention(self):
        affected = find_affected_tests(["bin/quiet"], self.root / "tests")
        self.assertIn(self.root / "tests" / "test_quiet.py", affected)
        self.assertNotIn(self.root / "tests" / "test_orphan.py", affected)

    def test_content_search_convention(self):
        affected = find_affected_tests(["tools/widget.py"], self.root / "tests")
        self.assertIn(self.root / "tests" / "test_other.py", affected)
        self.assertNotIn(self.root / "tests" / "test_orphan.py", affected)

    def test_changed_test_file_maps_to_itself(self):
        affected = find_affected_tests(["tests/test_orphan.py"], self.root / "tests")
        self.assertEqual(affected, [self.root / "tests" / "test_orphan.py"])

    def test_unrelated_change_matches_nothing(self):
        (self.root / "tools" / "unrelated.py").write_text("x = 1\n")
        affected = find_affected_tests(["tools/unrelated.py"], self.root / "tests")
        self.assertEqual(affected, [])

    def test_multiple_changed_files_union(self):
        affected = find_affected_tests(["bin/quiet", "tools/widget.py"], self.root / "tests")
        self.assertEqual(
            affected,
            sorted([self.root / "tests" / "test_quiet.py", self.root / "tests" / "test_other.py"]),
        )


class TestAffectedTestsCliOnFixtureRepo(unittest.TestCase):
    """The CLI end to end, reading real changed files from a real (tiny,
    throwaway) git repository -- proposal 23 M-02's own 'done' line asks
    for this to be tested on a fixture repo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self._git("init", "-q")
        self._git("config", "user.email", "fixture@example.com")
        self._git("config", "user.name", "Fixture")

        (self.repo / "tests").mkdir()
        (self.repo / "tools").mkdir()
        (self.repo / "tools" / "widget.py").write_text("def build():\n    return 1\n")
        (self.repo / "tests" / "test_widget.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_x(self): pass\n"
        )
        (self.repo / "tests" / "test_orphan.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_x(self): pass\n"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "initial")

    def tearDown(self):
        self.tmp.cleanup()

    def _git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True)

    def _run_tool(self, extra_args):
        proc = subprocess.run(
            [sys.executable, str(TOOL), *extra_args],
            cwd=self.repo, capture_output=True, text=True,
        )
        return proc

    def test_unstaged_change_is_picked_up(self):
        (self.repo / "tools" / "widget.py").write_text("def build():\n    return 2\n")
        proc = self._run_tool([])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("test_widget.py", proc.stdout)
        self.assertNotIn("test_orphan.py", proc.stdout)

    def test_base_ref_diff_is_picked_up(self):
        (self.repo / "tools" / "widget.py").write_text("def build():\n    return 3\n")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "widget: change return value")
        proc = self._run_tool(["--base", "HEAD~1"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("test_widget.py", proc.stdout)

    def test_no_changes_exits_1(self):
        proc = self._run_tool([])
        self.assertEqual(proc.returncode, 1)

    def test_explicit_files_bypass_git(self):
        proc = self._run_tool(["tools/widget.py"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("test_widget.py", proc.stdout)

    def test_outside_git_repo_without_files_is_usage_error(self):
        outside = Path(tempfile.mkdtemp())
        try:
            (outside / "tests").mkdir()
            proc = subprocess.run(
                [sys.executable, str(TOOL)], cwd=outside, capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 2)
        finally:
            import shutil
            shutil.rmtree(outside, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
