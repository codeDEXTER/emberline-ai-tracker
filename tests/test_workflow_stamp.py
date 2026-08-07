"""The workflow.html version stamp must not drift from the rules it describes.

`docs/README.md` says any PR changing the shared rules updates `workflow.html`
and its stamp in the same PR. That was maintained by memory, and by 2026-08-07
the page claimed **version 62** while the rules were at **102** — forty versions
of drift on a page whose own README says a drifted bird's-eye view is worse than
none, because it is trusted at a glance.

This is that rule made checkable.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "workflow.html"
RULES = "CLAUDE-workflow.md"


def git(*args) -> str:
    exe = "/Library/Developer/CommandLineTools/usr/bin/git"
    if not Path(exe).exists():
        exe = "git"
    return subprocess.run([exe, "-C", str(ROOT), *args],
                          capture_output=True, text=True, check=False).stdout.strip()


def stamped_version() -> int:
    m = re.search(r"rules version (\d+)", PAGE.read_text())
    if not m:
        raise AssertionError("docs/workflow.html carries no 'rules version N' stamp")
    return int(m.group(1))


def rules_version() -> int:
    """Commit count at the last commit that touched CLAUDE-workflow.md.

    Deliberately not `rev-list --count HEAD`. A stamp written inside the commit
    it counts can never name itself — it would always be one behind, and every
    fix would introduce the same off-by-one again. Pinning it to the last
    *rules* change makes a commit that only edits the page a no-op for this
    check, which is what stops the regress.
    """
    sha = git("log", "-1", "--format=%H", "--", RULES)
    return int(git("rev-list", "--count", sha))


class TestWorkflowStamp(unittest.TestCase):

    def test_page_is_not_older_than_the_rules_it_describes(self):
        stamped, required = stamped_version(), rules_version()
        self.assertGreaterEqual(
            stamped, required,
            f"docs/workflow.html says rules version {stamped}, but "
            f"{RULES} last changed at version {required}. The page has drifted "
            f"behind the rules — regenerate it and update the stamp.")

    def test_stamp_is_not_from_the_future(self):
        stamped, head = stamped_version(), int(git("rev-list", "--count", "HEAD"))
        # One ahead is legitimate: a stamp is written for the commit it lands
        # as, which does not exist yet at the time it is typed. More than that
        # is a typo or a guess.
        self.assertLessEqual(
            stamped, head + 1,
            f"stamp claims rules version {stamped}, but HEAD is only at {head}")

    def test_the_png_beside_it_is_not_stale(self):
        png = ROOT / "docs" / "workflow.png"
        self.assertTrue(png.exists(), "docs/workflow.png is missing")
        page_at = git("log", "-1", "--format=%ct", "--", "docs/workflow.html")
        png_at = git("log", "-1", "--format=%ct", "--", "docs/workflow.png")
        if page_at and png_at:
            self.assertGreaterEqual(
                int(png_at), int(page_at),
                "docs/workflow.png was committed before the last change to "
                "workflow.html — regenerate it (see docs/README.md)")


if __name__ == "__main__":
    unittest.main()
