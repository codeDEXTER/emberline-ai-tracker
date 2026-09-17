"""bin/commit-if-green -- gate, commit and push in one call, only on green
(common-rules proposal 31, D4 -> O-04).

The interesting behaviour is what it refuses to do. HANDOFF.md's operating
rules (folded in from the old docs/OPERATING-RULES.md, S3) record a
`grep ... && git commit` chain that once shipped a failing test because grep
exits 0 on a line containing "FAILED" -- these tests pin that the verdict
check runs in code, against bin/quiet's own line and exit code, not against
a naive read of the gate's raw output.

Every scenario here runs against a throwaway git repo (tempfile.mkdtemp) and
a fake "gate" passed via --gate, never the real project's suite and never
the real checkout this file lives in.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMIT_IF_GREEN = ROOT / "bin" / "commit-if-green"


def py(code: str) -> list[str]:
    """A fake gate: an inline python3 -c script."""
    return [sys.executable, "-c", code]


GATE_OK = py(
    "print('test_a (t.T) ... ok'); "
    "print('Ran 3 tests in 0.001s'); "
    "print(); print('OK')"
)

GATE_FAILED = py(
    "print('FAIL: test_b (t.T)'); "
    "print('Ran 3 tests in 0.001s'); "
    "print(); print('FAILED (failures=1)'); "
    "import sys; sys.exit(1)"
)

# The exact incident this tool exists to prevent: a well-formed unittest
# FAILED summary, but the process exits 0 anyway (as a `grep ... && git
# commit` chain would see it). bin/quiet must catch this from the summary
# text, not the exit code -- and commit-if-green must trust that call.
GATE_FAILED_EXIT_ZERO = py(
    "print('FAIL: test_b (t.T)'); "
    "print('Ran 3 tests in 0.001s'); "
    "print(); print('FAILED (failures=1)')"
)


class Repo:
    """A throwaway repo with a seeded main branch."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "proj"
        self.path.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.path / "README.md").write_text("seed\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "seed")
        # A remote to push against -- a bare repo beside it.
        self.remote = Path(self.tmp.name) / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-q", "origin", "main")

    def cleanup(self):
        self.tmp.cleanup()

    def git(self, *a, check=True):
        return subprocess.run(["git", "-C", str(self.path), *a],
                              capture_output=True, text=True, check=check)

    def write(self, rel: str, body: str):
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.strip()

    def run(self, *extra, env=None):
        e = dict(os.environ)
        e.pop("COMMON_RULES_DIR", None)
        e.update(env or {})
        return subprocess.run(
            [str(COMMIT_IF_GREEN), "--project", str(self.path), *extra],
            capture_output=True, text=True, env=e,
        )


class CommitIfGreenTests(unittest.TestCase):

    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.cleanup()

    # -- green: commits ----------------------------------------------------

    def test_commits_on_a_green_gate(self):
        self.repo.write("app.py", "x = 1\n")
        before = self.repo.head()
        out = self.repo.run("--message", "add app.py", "--gate", *GATE_OK)
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        after = self.repo.head()
        self.assertNotEqual(before, after, "a commit should have been made")
        log = self.repo.git("log", "-1", "--format=%B").stdout
        self.assertIn("add app.py", log)
        self.assertIn("Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>", log)

    def test_stages_untracked_files_too(self):
        """The tool replaces git add + commit + push -- an untracked file
        should be picked up, not just already-staged content."""
        self.repo.write("new_file.py", "y = 2\n")
        out = self.repo.run("--message", "add new_file.py", "--gate", *GATE_OK)
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        show = self.repo.git("show", "--stat", "HEAD").stdout
        self.assertIn("new_file.py", show)

    # -- red: commits nothing -----------------------------------------------

    def test_commits_nothing_on_a_red_gate(self):
        self.repo.write("app.py", "x = 1\n")
        before = self.repo.head()
        out = self.repo.run("--message", "add app.py", "--gate", *GATE_FAILED)
        self.assertEqual(1, out.returncode, out.stdout + out.stderr)
        self.assertEqual(before, self.repo.head(), "nothing should be committed")

    def test_refuses_when_the_gate_prints_failed_but_exits_zero(self):
        """The grep-trap scenario HANDOFF.md S3 describes."""
        self.repo.write("app.py", "x = 1\n")
        before = self.repo.head()
        out = self.repo.run("--message", "add app.py", "--gate", *GATE_FAILED_EXIT_ZERO)
        self.assertEqual(1, out.returncode, out.stdout + out.stderr)
        self.assertEqual(before, self.repo.head())
        self.assertIn("FAILED", out.stdout)

    def test_refuses_on_an_unrecognised_or_empty_verdict(self):
        """quiet's own verdict line, not the gate's raw output, is what is
        checked -- fed here via a stub bin/quiet that prints something that
        is not quiet's shape at all."""
        stub_rules = Path(tempfile.mkdtemp())
        (stub_rules / "bin").mkdir()
        stub_quiet = stub_rules / "bin" / "quiet"
        stub_quiet.write_text("#!/usr/bin/env python3\nprint('not a verdict line')\n")
        stub_quiet.chmod(0o755)
        try:
            self.repo.write("app.py", "x = 1\n")
            before = self.repo.head()
            out = self.repo.run(
                "--message", "add app.py", "--gate", *GATE_OK,
                env={"COMMON_RULES_DIR": str(stub_rules)},
            )
            self.assertEqual(1, out.returncode, out.stdout + out.stderr)
            self.assertEqual(before, self.repo.head())
        finally:
            import shutil
            shutil.rmtree(stub_rules)

    # -- refusals before anything runs (exit 2) ------------------------------

    def test_refuses_with_nothing_staged_and_nothing_to_stage(self):
        before = self.repo.head()
        out = self.repo.run("--message", "nothing to do", "--gate", *GATE_OK)
        self.assertEqual(2, out.returncode, out.stdout + out.stderr)
        self.assertEqual(before, self.repo.head())

    def test_refuses_mid_rebase(self):
        (self.repo.path / ".git" / "rebase-merge").mkdir()
        self.repo.write("app.py", "x = 1\n")
        before = self.repo.head()
        out = self.repo.run("--message", "add app.py", "--gate", *GATE_OK)
        self.assertEqual(2, out.returncode, out.stdout + out.stderr)
        self.assertEqual(before, self.repo.head())

    def test_refuses_mid_merge(self):
        (self.repo.path / ".git" / "MERGE_HEAD").write_text("deadbeef\n")
        self.repo.write("app.py", "x = 1\n")
        out = self.repo.run("--message", "add app.py", "--gate", *GATE_OK)
        self.assertEqual(2, out.returncode, out.stdout + out.stderr)

    def test_refuses_to_push_to_main(self):
        """main is the checked-out branch by construction here (Repo seeds
        on main); --push must refuse before the gate ever runs."""
        self.repo.write("app.py", "x = 1\n")
        before = self.repo.head()
        out = self.repo.run("--message", "add app.py", "--push", "--gate", *GATE_OK)
        self.assertEqual(2, out.returncode, out.stdout + out.stderr)
        self.assertEqual(before, self.repo.head(), "must not even commit")

    def test_refuses_bad_usage_no_message(self):
        self.repo.write("app.py", "x = 1\n")
        out = self.repo.run("--gate", *GATE_OK)
        self.assertEqual(2, out.returncode, out.stdout + out.stderr)

    def test_refuses_both_message_and_message_file(self):
        self.repo.write("app.py", "x = 1\n")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("from file")
            msg_file = f.name
        try:
            out = self.repo.run("--message", "m", "--message-file", msg_file, "--gate", *GATE_OK)
            self.assertEqual(2, out.returncode, out.stdout + out.stderr)
        finally:
            os.unlink(msg_file)

    # -- attribution ----------------------------------------------------------

    def test_attribution_added_once_not_twice(self):
        self.repo.write("app.py", "x = 1\n")
        msg = ("manual message\n\n"
               "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n")
        out = self.repo.run("--message", msg, "--gate", *GATE_OK)
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        log = self.repo.git("log", "-1", "--format=%B").stdout
        self.assertEqual(
            1, log.count("Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"))

    # -- push -----------------------------------------------------------------

    def test_push_new_branch_uses_dash_u(self):
        self.repo.git("checkout", "-q", "-b", "feature")
        self.repo.write("app.py", "x = 1\n")
        out = self.repo.run("--message", "add app.py", "--push", "--gate", *GATE_OK)
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        remote_heads = subprocess.run(
            ["git", "-C", str(self.repo.remote), "branch", "--list", "feature"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("feature", remote_heads)

    def test_push_tracking_branch_uses_force_with_lease(self):
        self.repo.git("checkout", "-q", "-b", "feature")
        self.repo.git("push", "-q", "-u", "origin", "feature")
        self.repo.write("app.py", "x = 1\n")
        out = self.repo.run("--message", "add app.py", "--push", "--gate", *GATE_OK)
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        remote_log = subprocess.run(
            ["git", "-C", str(self.repo.remote), "log", "-1", "--format=%s", "feature"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("add app.py", remote_log)

    # -- timeout ----------------------------------------------------------------

    def test_timeout_refuses_and_commits_nothing(self):
        self.repo.write("app.py", "x = 1\n")
        before = self.repo.head()
        slow_gate = py("import time; time.sleep(5)")
        out = self.repo.run("--message", "add app.py", "--timeout", "0.2", "--gate", *slow_gate)
        self.assertEqual(1, out.returncode, out.stdout + out.stderr)
        self.assertEqual(before, self.repo.head())
        self.assertIn("did not finish within", out.stdout + out.stderr)
        self.assertIn("log", out.stdout + out.stderr)

    # -- default gate ---------------------------------------------------------

    def test_default_gate_falls_back_to_full_suite_when_nothing_affected(self):
        """No --gate given, and affected_tests.py finds nothing plausible to
        run for a change outside tests/ with no matching test file -- the
        default gate must still run *something* (the full suite discover in
        an empty tests/ dir), not silently skip the check."""
        (self.repo.path / "tests").mkdir()
        self.repo.write("tests/test_something_else.py",
                        "import unittest\n\n"
                        "class T(unittest.TestCase):\n"
                        "    def test_ok(self):\n"
                        "        self.assertTrue(True)\n")
        self.repo.git("add", "-A")
        self.repo.git("commit", "-qm", "seed a passing test")
        self.repo.git("push", "-q", "origin", "main")
        self.repo.write("unrelated_thing.py", "z = 3\n")
        before = self.repo.head()
        out = self.repo.run("--message", "add unrelated_thing.py")
        # Nothing in tests/ mentions unrelated_thing.py, so affected_tests.py
        # finds no match (exit 1) and the default gate falls back to the
        # full suite discover, which does find test_something_else.py.
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        self.assertNotEqual(before, self.repo.head())


if __name__ == "__main__":
    unittest.main()
