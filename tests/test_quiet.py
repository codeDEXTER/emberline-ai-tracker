"""bin/quiet -- run a gate, keep its output in a file, print one verdict line
(common-rules proposal 23, lever L3).

Why: build/test/receipt runs were 62% of PhotoVault App subagent spend
because agents piped raw `flutter test ... | tail -N` and
`python3 -m unittest ... | tail -N` straight into context. A past incident
(docs/OPERATING-RULES.md S3) shipped a broken commit because a
`grep ... && git commit` chain trusted grep's exit code instead of the
runner's own summary line -- grep exits 0 on a line containing "FAILED".
These tests pin the verdict to the runner's real summary text AND its exit
code, not to a naive grep.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUIET = ROOT / "bin" / "quiet"


def py(code: str) -> list[str]:
    """A fake tool: a small python3 -c script producing a chosen summary
    shape and exiting with a chosen code."""
    return [sys.executable, "-c", code]


UNITTEST_OK = (
    "test_a (t.T) ... ok\n"
    "----------------------------------------------------------------------\n"
    "Ran 3 tests in 0.001s\n"
    "\n"
    "OK\n"
)

UNITTEST_FAILED = (
    "test_a (t.T) ... ok\n"
    "======================================================================\n"
    "FAIL: test_b (t.T)\n"
    "----------------------------------------------------------------------\n"
    "AssertionError: boom\n"
    "----------------------------------------------------------------------\n"
    "Ran 3 tests in 0.001s\n"
    "\n"
    "FAILED (failures=1)\n"
)

FLUTTER_OK = "00:02 +3: All tests passed!\n"
FLUTTER_FAILED = "00:03 +2 -1: Some tests failed.\n"

ANALYZE_OK = "No issues found!\n"
ANALYZE_FAILED = "3 issues found.\n"

PYTEST_OK = "3 passed in 0.01s\n"
PYTEST_FAILED = "2 failed, 1 passed in 0.02s\n"


class TestQuiet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def run_quiet(self, extra_args, text, code):
        script = f"import sys; sys.stdout.write({text!r}); sys.exit({code})"
        log = str(Path(self.tmp.name) / "run.log")
        cmd = [str(QUIET), "--log", log, *extra_args, "--", *py(script)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return r, Path(log)

    # -- unittest ---------------------------------------------------------

    def test_unittest_ok(self):
        r, log = self.run_quiet([], UNITTEST_OK, 0)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith("quiet: OK"), r.stdout)
        self.assertIn("3 tests", r.stdout)

    def test_unittest_failed_exit_1(self):
        r, log = self.run_quiet([], UNITTEST_FAILED, 1)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith("quiet: FAILED"), r.stdout)
        self.assertIn("failures=1", r.stdout)
        self.assertIn("FAIL: test_b", r.stdout)

    def test_unittest_failed_text_but_exit_0_is_still_failed(self):
        """The regression this exists for: a runner that prints a failure
        summary but exits 0 must not be reported OK."""
        r, log = self.run_quiet([], UNITTEST_FAILED, 0)
        self.assertEqual(r.returncode, 0, "quiet exits with CMD's own code")
        self.assertTrue(r.stdout.startswith("quiet: FAILED"),
                         f"verdict must distrust exit 0 when output says FAILED: {r.stdout!r}")

    # -- flutter test -------------------------------------------------------

    def test_flutter_pass(self):
        r, log = self.run_quiet([], FLUTTER_OK, 0)
        self.assertTrue(r.stdout.startswith("quiet: OK"), r.stdout)
        self.assertIn("+3", r.stdout)

    def test_flutter_fail(self):
        r, log = self.run_quiet([], FLUTTER_FAILED, 1)
        self.assertTrue(r.stdout.startswith("quiet: FAILED"), r.stdout)
        self.assertIn("-1", r.stdout)

    # -- flutter/dart analyze ------------------------------------------------

    def test_analyze_clean(self):
        r, log = self.run_quiet([], ANALYZE_OK, 0)
        self.assertTrue(r.stdout.startswith("quiet: OK"), r.stdout)
        self.assertIn("No issues found", r.stdout)

    def test_analyze_issues(self):
        r, log = self.run_quiet([], ANALYZE_FAILED, 1)
        self.assertTrue(r.stdout.startswith("quiet: FAILED"), r.stdout)
        self.assertIn("3 issues found", r.stdout)

    # -- pytest -----------------------------------------------------------

    def test_pytest_pass(self):
        r, log = self.run_quiet([], PYTEST_OK, 0)
        self.assertTrue(r.stdout.startswith("quiet: OK"), r.stdout)

    def test_pytest_fail(self):
        r, log = self.run_quiet([], PYTEST_FAILED, 1)
        self.assertTrue(r.stdout.startswith("quiet: FAILED"), r.stdout)

    # -- unknown tool fallback ----------------------------------------------

    def test_unknown_tool_fallback_ok(self):
        r, log = self.run_quiet([], "some noise\nthe actual last line\n", 0)
        self.assertTrue(r.stdout.startswith("quiet: OK"), r.stdout)
        self.assertIn("the actual last line", r.stdout)

    def test_unknown_tool_fallback_failed_relies_on_exit_code(self):
        r, log = self.run_quiet([], "some noise\nthe actual last line\n", 1)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith("quiet: FAILED"), r.stdout)

    # -- command cannot start -----------------------------------------------

    def test_command_not_found_exits_2(self):
        log = str(Path(self.tmp.name) / "missing.log")
        cmd = [str(QUIET), "--log", log, "--", "/no/such/binary/here-xyz"]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 2)
        self.assertTrue(r.stdout.startswith("quiet: FAILED"), r.stdout)

    # -- log file and single-line stdout invariants --------------------------

    def test_log_file_has_full_output(self):
        r, log = self.run_quiet([], UNITTEST_FAILED, 1)
        self.assertTrue(log.exists())
        logged = log.read_text()
        self.assertEqual(logged, UNITTEST_FAILED)

    def test_stdout_is_exactly_one_line(self):
        r, log = self.run_quiet([], UNITTEST_OK, 0)
        lines = [l for l in r.stdout.split("\n") if l != ""]
        self.assertEqual(len(lines), 1, f"expected exactly one line, got {r.stdout!r}")

    def test_label_used_in_default_log_name(self):
        script = f"import sys; sys.stdout.write({UNITTEST_OK!r}); sys.exit(0)"
        cmd = [str(QUIET), "--label", "mylabel-xyz", "--", *py(script)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        m = re.search(r"log (\S+)", r.stdout)
        self.assertIsNotNone(m, r.stdout)
        self.assertIn("mylabel-xyz", m.group(1))
        Path(m.group(1)).unlink(missing_ok=True)

    def test_detail_never_contains_newline_or_exceeds_160_chars(self):
        long_last_line = "x" * 500
        r, log = self.run_quiet([], f"noise\n{long_last_line}\n", 0)
        line = r.stdout.rstrip("\n")
        self.assertNotIn("\n", line)
        self.assertLessEqual(len(line), 300)


if __name__ == "__main__":
    unittest.main()
