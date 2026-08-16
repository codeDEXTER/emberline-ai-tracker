"""A commit that names no issue must not kill `land`.

Reported 2026-08-16 by a finance-tracker session that hit it twice in one
night: `land` printed "tests green" and then simply stopped — no error, no
message, never reaching the push or the PR. Every branch whose commit message
is plain description rather than "Fixes #N" hit it.

The cause is not where it was reported. `grep` exits 1 when it matches
nothing, which is the *common* case; under `set -euo pipefail` that failed the
pipeline, which failed the `closes="$(closes_trailer …)"` assignment, which
killed the script. The report named the `[ -n "$closes" ] && …` line below it —
but bash exempts a failing command in a `&&` list from `set -e`, and a minimal
repro of that line exits 0. Fixing the reported line would have left the bug
in place and looked like it had worked.

Why the existing land tests missed it: they all drive `land --check`, which
returns before this code runs. This exercises the function directly.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAND = ROOT / "bin" / "land"


def closes_trailer(message: str):
    """Call the real function out of bin/land, under land's own shell flags.

    `set -euo pipefail` is reproduced deliberately: without it the bug is
    invisible, because the failing pipeline is harmless on its own.
    """
    script = f"""
    set -euo pipefail
    eval "$(sed -n '/^closes_trailer()/,/^}}/p' {LAND})"
    closes="$(closes_trailer "$1")"
    printf '%s' "$closes"
    """
    r = subprocess.run(["bash", "-c", script, "bash", message],
                       capture_output=True, text=True, check=False)
    return r.returncode, r.stdout


class TestClosesTrailer(unittest.TestCase):

    def test_a_message_naming_no_issue_does_not_kill_the_script(self):
        """The regression. Exit 0 and empty output, not a silent death."""
        code, out = closes_trailer("Number every proposal, lead with the number")
        self.assertEqual(code, 0,
                         "land dies on any commit that does not name an issue")
        self.assertEqual(out, "")

    def test_an_issue_is_still_picked_up(self):
        code, out = closes_trailer("Fixes #42 — the thing was broken")
        self.assertEqual(code, 0)
        self.assertIn("Closes #42", out)

    def test_several_issues_are_deduplicated_and_ordered(self):
        code, out = closes_trailer("Closes #7\nAlso fixes #3 and closes #7 again")
        self.assertEqual(code, 0)
        self.assertEqual(out.split("\n"), ["Closes #3", "Closes #7"])

    def test_a_bare_pr_style_reference_is_still_not_matched(self):
        """Deliberate existing behaviour: a trailing "(#N)" is usually the PR
        number, so keying on it closes an unrelated issue most of the time.
        Guarding it here so the || true fix cannot loosen it by accident."""
        code, out = closes_trailer("Number every proposal (#102)")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_an_empty_message_is_survivable(self):
        code, out = closes_trailer("")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
