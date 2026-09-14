"""bin/land runs the test command a project declares (proposal 18 B, found in proposal 19's pilot).

land's test_cmd() used to guess from the tree: tests/*.py meant unittest,
package.json meant npm test. The PhotoVault engine's merge gate is pytest with
markers, so land -- and the warm card, which reports land's answer -- would run
the wrong gate there. A project now declares its gate in `.common-rules-test`
at its root, beside `.common-rules-version`: the first line that is neither
blank nor a comment. With no such line, land guesses as before.

These drive land itself, not the extracted function: the declared command
must be the one that runs, so `false` declared must refuse the landing.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAND = ROOT / "bin" / "land"


class LandHarness(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "proj"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.repo / "README.md").write_text("seed\n")
        self.git("add", "-A"); self.git("commit", "-qm", "seed")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a], capture_output=True, text=True, check=False)

    def branch_declaring(self, declared: str):
        self.git("checkout", "-q", "-b", "work")
        (self.repo / ".common-rules-test").write_text(declared)
        (self.repo / "README.md").write_text("seed\nwork\n")
        self.git("add", "-A"); self.git("commit", "-qm", "declare the gate")

    def land(self):
        return subprocess.run([str(LAND), "--check"], cwd=str(self.repo), capture_output=True,
                              text=True, check=False, env=dict(os.environ))


class TestTheDeclaredCommandRuns(LandHarness):

    def test_a_failing_declared_gate_refuses(self):
        self.branch_declaring("# merge gate\nfalse\n")
        out = self.land()
        self.assertIn("running: false", out.stdout)
        self.assertIn("tests are not green", out.stdout + out.stderr)
        self.assertNotIn("READY", out.stdout)

    def test_a_passing_declared_gate_lands(self):
        self.branch_declaring("\n# merge gate\ntrue\n")
        out = self.land()
        self.assertIn("running: true", out.stdout)
        self.assertIn("READY", out.stdout)


class TestTheJsonDeclaration(LandHarness):
    """Proposal 20, D9: `.common-rules.json` gates.merge is the gate, ahead of
    `.common-rules-test`, and a declaration land cannot read refuses loudly --
    falling back to the guess would silently run a gate nobody declared."""

    def branch_with(self, files: dict):
        self.git("checkout", "-q", "-b", "work")
        for rel, body in files.items():
            (self.repo / rel).write_text(body)
        (self.repo / "README.md").write_text("seed\nwork\n")
        self.git("add", "-A"); self.git("commit", "-qm", "declare the gates")

    def test_a_failing_declared_merge_gate_refuses(self):
        self.branch_with({".common-rules.json": '{"gates": {"quick": "true", "merge": "false"}}'})
        out = self.land()
        self.assertIn("running: false", out.stdout)
        self.assertIn("tests are not green", out.stdout + out.stderr)
        self.assertNotIn("READY", out.stdout)

    def test_a_passing_declared_merge_gate_lands(self):
        self.branch_with({".common-rules.json": '{"gates": {"quick": "false", "merge": "true"}}'})
        out = self.land()
        self.assertIn("running: true", out.stdout)
        self.assertIn("READY", out.stdout)

    def test_the_json_merge_gate_wins_over_the_test_file(self):
        self.branch_with({".common-rules.json": '{"gates": {"merge": "true"}}', ".common-rules-test": "false\n"})
        out = self.land()
        self.assertIn("running: true", out.stdout)
        self.assertIn("READY", out.stdout)

    def test_a_declaration_without_a_merge_gate_uses_the_test_file(self):
        self.branch_with({".common-rules.json": '{"read_order": ["README.md"], "gates": {"quick": "true"}}',
                          ".common-rules-test": "false\n"})
        out = self.land()
        self.assertIn("running: false", out.stdout)
        self.assertNotIn("READY", out.stdout)

    def test_malformed_json_refuses_even_with_a_passing_test_file(self):
        self.branch_with({".common-rules.json": '{"gates": {"merge": "true"}', ".common-rules-test": "true\n"})
        out = self.land()
        self.assertIn(".common-rules.json is not valid JSON", out.stdout)
        self.assertIn("tests are not green", out.stdout + out.stderr)
        self.assertNotIn("READY", out.stdout)

    def test_a_merge_gate_with_shell_metacharacters_runs_as_declared(self):
        """The declared string is the project's own command, run as written --
        read by json, never pieced together by a shell."""
        self.branch_with({".common-rules.json": json.dumps({"gates": {"merge": "test \"$(printf 'a b')\" = 'a b' && echo ok"}}),
                          ".common-rules-test": "false\n"})
        out = self.land()
        self.assertIn("READY", out.stdout, out.stdout + out.stderr)

    # Lead ruling on V-00, 14 Sep: a gate the project declared but land cannot
    # use refuses. Every case below carries a passing .common-rules-test, so
    # falling back -- what ab2fb7a did -- lands, and the test goes red.

    def assert_refused_with(self, out, reason):
        self.assertIn(f"running: false  # .common-rules.json {reason}", out.stdout, out.stdout + out.stderr)
        self.assertIn("tests are not green", out.stdout + out.stderr)
        self.assertNotIn("READY", out.stdout)

    def test_a_merge_gate_that_is_a_number_refuses(self):
        self.branch_with({".common-rules.json": '{"gates": {"merge": 3}}', ".common-rules-test": "true\n"})
        self.assert_refused_with(self.land(), "gates.merge is not a string")

    def test_a_merge_gate_that_is_null_refuses(self):
        self.branch_with({".common-rules.json": '{"gates": {"merge": null}}', ".common-rules-test": "true\n"})
        self.assert_refused_with(self.land(), "gates.merge is not a string")

    def test_an_empty_merge_gate_refuses(self):
        self.branch_with({".common-rules.json": '{"gates": {"merge": ""}}', ".common-rules-test": "true\n"})
        self.assert_refused_with(self.land(), "gates.merge is not a string")

    def test_a_whitespace_merge_gate_refuses(self):
        self.branch_with({".common-rules.json": '{"gates": {"merge": "  \\t "}}', ".common-rules-test": "true\n"})
        self.assert_refused_with(self.land(), "gates.merge is not a string")

    def test_a_quick_gate_of_the_wrong_type_refuses(self):
        self.branch_with({".common-rules.json": '{"gates": {"quick": ["sh", "tools/gate.sh"]}}',
                          ".common-rules-test": "true\n"})
        self.assert_refused_with(self.land(), "gates.quick is not a string")

    def test_gates_that_are_not_an_object_refuse(self):
        self.branch_with({".common-rules.json": '{"gates": "true"}', ".common-rules-test": "true\n"})
        self.assert_refused_with(self.land(), "gates is not an object")


class TestADeclaredCommandIsPrintedVerbatim(LandHarness):
    """`echo "$declared"` swallowed a command that bash's echo reads as its own
    flag: `-e` or `-n` came out empty, land found "no test suite", and landed
    on the gate alone. printf '%s\\n' prints it as written."""

    def test_a_test_file_command_that_looks_like_an_echo_flag_runs(self):
        for flag in ("-e", "-n"):
            with self.subTest(flag=flag):
                self.git("checkout", "-q", "main")
                self.git("branch", "-q", "-D", "work")
                self.branch_declaring(f"# merge gate\n{flag}\n")
                out = self.land()
                self.assertIn(f"running: {flag}", out.stdout, out.stdout + out.stderr)
                self.assertNotIn("READY", out.stdout)

    def test_a_json_command_that_looks_like_an_echo_flag_runs(self):
        self.git("checkout", "-q", "-b", "work")
        (self.repo / ".common-rules.json").write_text('{"gates": {"merge": "-n"}}')
        (self.repo / "README.md").write_text("seed\nwork\n")
        self.git("add", "-A"); self.git("commit", "-qm", "declare")
        out = self.land()
        self.assertIn("running: -n", out.stdout, out.stdout + out.stderr)
        self.assertNotIn("READY", out.stdout)


if __name__ == "__main__":
    unittest.main()
