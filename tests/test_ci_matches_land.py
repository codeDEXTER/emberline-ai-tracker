"""CI and `bin/land` must run the same command, forever.

The point of "tests an agent writes are reused by CI with no extra effort" is
that there is exactly ONE command. The moment CI runs something `land` does
not — a different discovery path, an extra flag, a different directory — a
test can pass locally and fail in CI, or worse, pass in CI and never run
locally. Then they are two suites wearing one name.

This is the guard. It reads the command out of `bin/land` and out of the
workflow file and asserts they are the same string.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAND = ROOT / "bin" / "land"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def land_test_command() -> str:
    """What land's test_cmd() emits for this repo — asked, not guessed.

    Sourcing the function is deliberate: parsing the string out of the file
    would pass even if the surrounding `if` picked a different branch.
    """
    script = f"""
    set -e
    cd {ROOT}
    # pull test_cmd() out of land without running the rest of it
    eval "$(sed -n '/^test_cmd()/,/^}}/p' {LAND})"
    test_cmd
    """
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(script)
        path = fh.name
    out = subprocess.run(["bash", path], capture_output=True, text=True, check=False)
    return out.stdout.strip()


def workflow_test_command() -> str:
    text = WORKFLOW.read_text()
    m = re.search(r"name:\s*Run test suite\s*\n\s*run:\s*(.+)", text)
    if not m:
        raise AssertionError("no 'Run test suite' step with a run: line in ci.yml")
    return m.group(1).strip()


class TestOneCommand(unittest.TestCase):

    def test_the_workflow_exists_at_all(self):
        """128 tests with no CI is how main stayed red for two days."""
        self.assertTrue(WORKFLOW.exists(), f"{WORKFLOW} is missing")

    def test_ci_runs_exactly_what_land_runs(self):
        land, ci = land_test_command(), workflow_test_command()
        self.assertTrue(land, "land's test_cmd() returned nothing for this repo")
        self.assertEqual(
            ci, land,
            "CI and bin/land run different commands — a test can then pass in "
            "one and never run in the other. Change both or neither.")

    def test_ci_runs_on_both_push_and_pull_request(self):
        """A push-only workflow lets a red merge land before anyone looks;
        a PR-only workflow never notices main going red on its own."""
        text = WORKFLOW.read_text()
        self.assertRegex(text, r"pull_request:", "CI does not run on pull requests")
        self.assertRegex(text, r"push:", "CI does not run on pushes to main")


if __name__ == "__main__":
    unittest.main()
