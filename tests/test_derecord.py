"""derecord must make a project MATCH the shared rules, not merely not-duplicate.

Issue #57: the installer asked "is there a line for this path?" and nothing
more, so once a pattern was present its value was frozen. Changing a rule
upstream silently failed to reach every already-adopted project, and the script
reported success while doing it.

It bit for real: `AGENT-LOG.md` moved from `merge=union` to `merge=ours` when
the log became generated output, and pockets kept union-merging it.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DERECORD = ROOT / "bin" / "derecord"
SHARED = ROOT / "gitattributes-for-projects"


def shared_rules() -> dict[str, str]:
    out = {}
    for line in SHARED.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        out[parts[0]] = " ".join(parts[1:])
    return out


def attributes_in(path: Path) -> dict[str, str]:
    out = {}
    for line in (path / ".gitattributes").read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        out[parts[0]] = " ".join(parts[1:])
    return out


class DerecordCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        self.proj.mkdir()
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_derecord(self):
        return subprocess.run([str(DERECORD), str(self.proj)],
                              capture_output=True, text=True, check=False)


class TestDerecord(DerecordCase):

    def test_a_stale_value_is_corrected(self):
        """The #57 regression. A project frozen on an old value must be updated."""
        pat = "AGENT-LOG.md"
        self.assertIn(pat, shared_rules(), "shared rules no longer mention AGENT-LOG.md")
        (self.proj / ".gitattributes").write_text(f"{pat}      merge=union\n")

        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            attributes_in(self.proj)[pat], shared_rules()[pat],
            "derecord left a stale merge strategy in place — this is issue #57")
        self.assertIn("corrected", r.stdout)

    def test_missing_rules_are_still_added(self):
        (self.proj / ".gitattributes").write_text("")
        self.run_derecord()
        got = attributes_in(self.proj)
        for pat, attrs in shared_rules().items():
            self.assertEqual(got.get(pat), attrs, f"{pat} not installed")

    def test_local_rules_we_say_nothing_about_survive(self):
        (self.proj / ".gitattributes").write_text(
            "*.png binary\ndocs/*.html linguist-documentation\n")
        self.run_derecord()
        got = attributes_in(self.proj)
        self.assertEqual(got.get("*.png"), "binary")
        self.assertEqual(got.get("docs/*.html"), "linguist-documentation")

    def test_running_twice_changes_nothing_the_second_time(self):
        self.run_derecord()
        before = (self.proj / ".gitattributes").read_text()
        second = self.run_derecord()
        self.assertEqual(before, (self.proj / ".gitattributes").read_text())
        self.assertIn("already matches", second.stdout)

    def test_it_says_so_rather_than_claiming_success_silently(self):
        """The other half of #57: reporting 'done' while having changed nothing."""
        (self.proj / ".gitattributes").write_text("AGENT-LOG.md      merge=union\n")
        out = self.run_derecord().stdout
        self.assertNotIn("0 record rule(s) added", out,
                         "the old wording reported success on a no-op correction")


if __name__ == "__main__":
    unittest.main()
