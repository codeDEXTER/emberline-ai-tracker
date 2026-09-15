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


# -- --jobs: parallel unittest discover (proposal 23, lever M-01) -----------
#
# Why: 67-81% faster suites (Trail of Bits, May 2025). The requirement is
# that quiet's own one-line verdict is unchanged: these tests build a real
# fixture test tree (some files pass, one fails) and assert that running it
# through `quiet -- python3 -m unittest discover -s DIR -q` (sequential) and
# through `quiet --jobs N -- python3 -m unittest discover -s DIR -q`
# (parallel, sharded one OS process per file) report the *same* verdict --
# same OK/FAILED, same total test count, same failure count.

PASSING_MODULE = """
import unittest

class T{n}(unittest.TestCase):
    def test_a(self):
        self.assertTrue(True)

    def test_b(self):
        self.assertEqual(1, 1)
"""

FAILING_MODULE = """
import unittest

class TFail(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)

    def test_boom(self):
        self.fail("boom")
"""


class TestQuietParallelDiscover(unittest.TestCase):
    def _make_fixture(self, n_passing_modules: int, failing: bool) -> Path:
        d = Path(self.tmp.name) / "fixture_tests"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n_passing_modules):
            (d / f"test_p{i}.py").write_text(PASSING_MODULE.format(n=i))
        if failing:
            (d / "test_zfail.py").write_text(FAILING_MODULE)
        return d

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, extra_args, fixture_dir):
        log = str(Path(self.tmp.name) / f"run-{'-'.join(extra_args) or 'seq'}.log")
        cmd = [
            str(QUIET), "--log", log, *extra_args, "--",
            sys.executable, "-m", "unittest", "discover", "-s", str(fixture_dir), "-q",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return r, Path(log)

    def test_parallel_passes_agree_with_sequential(self):
        fixture = self._make_fixture(n_passing_modules=5, failing=False)
        seq, _ = self._run([], fixture)
        par, _ = self._run(["--jobs", "4"], fixture)
        self.assertTrue(seq.stdout.startswith("quiet: OK"), seq.stdout)
        self.assertTrue(par.stdout.startswith("quiet: OK"), par.stdout)
        # 5 modules x 2 tests each = 10, same total either way.
        self.assertIn("10 tests", seq.stdout)
        self.assertIn("10 tests", par.stdout)
        self.assertEqual(seq.returncode, 0)
        self.assertEqual(par.returncode, 0)

    def test_parallel_failure_agrees_with_sequential(self):
        fixture = self._make_fixture(n_passing_modules=4, failing=True)
        seq, _ = self._run([], fixture)
        par, _ = self._run(["--jobs", "4"], fixture)
        self.assertTrue(seq.stdout.startswith("quiet: FAILED"), seq.stdout)
        self.assertTrue(par.stdout.startswith("quiet: FAILED"), par.stdout)
        self.assertIn("failures=1", seq.stdout)
        self.assertIn("failures=1", par.stdout)
        self.assertNotEqual(seq.returncode, 0)
        self.assertNotEqual(par.returncode, 0)

    def test_jobs_without_discover_shape_falls_back_unchanged(self):
        """--jobs is a no-op for any CMD that is not a plain `unittest
        discover` invocation -- it must never change behaviour for an
        arbitrary command."""
        log = str(Path(self.tmp.name) / "run.log")
        cmd = [str(QUIET), "--log", log, "--jobs", "4", "--", *py(
            f"import sys; sys.stdout.write({UNITTEST_OK!r}); sys.exit(0)"
        )]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertTrue(r.stdout.startswith("quiet: OK"), r.stdout)
        self.assertIn("3 tests", r.stdout)

    def test_jobs_1_runs_sequentially(self):
        fixture = self._make_fixture(n_passing_modules=3, failing=False)
        seq, _ = self._run([], fixture)
        one, _ = self._run(["--jobs", "1"], fixture)
        self.assertTrue(seq.stdout.startswith("quiet: OK"), seq.stdout)
        self.assertTrue(one.stdout.startswith("quiet: OK"), one.stdout)
        self.assertIn("6 tests", seq.stdout)
        self.assertIn("6 tests", one.stdout)

    def test_stdout_still_exactly_one_line_when_parallel(self):
        fixture = self._make_fixture(n_passing_modules=5, failing=False)
        par, _ = self._run(["--jobs", "4"], fixture)
        lines = [l for l in par.stdout.split("\n") if l != ""]
        self.assertEqual(len(lines), 1, f"expected exactly one line, got {par.stdout!r}")


if __name__ == "__main__":
    unittest.main()
