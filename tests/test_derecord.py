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

import datetime
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DERECORD = ROOT / "bin" / "derecord"
SHARED = ROOT / "gitattributes-for-projects"
TEMPLATES = ROOT / "templates"
TODAY = datetime.date.today().isoformat()

# (seeded path relative to the project, other-placeholder that must survive
# untouched -- proof only {{PROJECT}}/{{DATE}} were filled, has-a-date-token)
SEEDED_FILES = [
    ("HANDOFF.md", "{{ORIENTATION}}", True),
    ("docs/OPERATING-RULES.md", "{{MERGE_RULE_1}}", True),
    ("docs/handovers/lead-prompt.md", "{{SPONSOR_OWNED_BLOCKERS}}", False),
]

HOOK_EVENTS = [("precompact", "PreCompact"), ("stop", "Stop"), ("sessionstart", "SessionStart")]


def settings_in(path: Path) -> dict:
    return json.loads((path / ".claude" / "settings.json").read_text())


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


class TestDerecordSeeding(DerecordCase):
    """Step 4: derecord seeds the project-owned prose (proposal 19, W-08)."""

    def test_the_three_files_are_seeded_with_project_and_date_filled(self):
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel, other_placeholder, has_date in SEEDED_FILES:
            dest = self.proj / rel
            self.assertTrue(dest.exists(), f"{rel} was not seeded")
            text = dest.read_text()
            self.assertIn("proj", text, f"{{{{PROJECT}}}} not filled in {rel}")
            self.assertNotIn("{{PROJECT}}", text, f"{{{{PROJECT}}}} left unfilled in {rel}")
            self.assertNotIn("{{DATE}}", text, f"{{{{DATE}}}} left unfilled in {rel}")
            if has_date:
                self.assertIn(TODAY, text, f"{{{{DATE}}}} not filled with today's date in {rel}")
            self.assertIn(other_placeholder, text,
                           f"an unrelated placeholder was touched in {rel}")
            self.assertIn(f"  seeded {rel}", r.stdout)

    def test_a_second_run_is_byte_identical(self):
        self.run_derecord()
        before = {rel: (self.proj / rel).read_text() for rel, _p, _d in SEEDED_FILES}
        before_settings = (self.proj / ".claude" / "settings.json").read_text()
        second = self.run_derecord()
        for rel, _p, _d in SEEDED_FILES:
            self.assertEqual(before[rel], (self.proj / rel).read_text(),
                              f"{rel} changed on a second run")
            self.assertIn(f"{rel} exists, left alone", second.stdout)
        self.assertEqual(before_settings, (self.proj / ".claude" / "settings.json").read_text(),
                          "settings.json changed on a second, no-op run")

    def test_a_pre_existing_handoff_is_left_byte_identical(self):
        (self.proj / "HANDOFF.md").write_text("# hand-written, keep me\n")
        r = self.run_derecord()
        self.assertEqual((self.proj / "HANDOFF.md").read_text(), "# hand-written, keep me\n")
        self.assertIn("HANDOFF.md exists, left alone", r.stdout)


    def test_an_existing_dated_lead_prompt_is_not_joined_by_a_generic_one(self):
        """The PhotoVault engine's review, 13 Sep: it already keeps
        docs/handovers/2026-09-13-proposal-71-lead-prompt.md, and a generic
        docs/handovers/lead-prompt.md beside it would leave a later session two
        lead prompts to choose between."""
        existing = self.proj / "docs" / "handovers" / "2026-09-13-proposal-71-lead-prompt.md"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("# the real one\n")
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.proj / "docs" / "handovers" / "lead-prompt.md").exists())
        self.assertIn("2026-09-13-proposal-71-lead-prompt.md", r.stdout)
        self.assertEqual("# the real one\n", existing.read_text())


    def test_a_lead_prompt_kept_elsewhere_under_docs_is_found_too(self):
        """The PhotoVault app keeps docs/proposals/70-lead-prompt.md and has no
        docs/handovers/ at all; looking only in handovers/ would have seeded a
        second lead prompt there (found in its migration dry run, 13 Sep)."""
        existing = self.proj / "docs" / "proposals" / "70-lead-prompt.md"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("# the app's own\n")
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.proj / "docs" / "handovers" / "lead-prompt.md").exists())
        self.assertIn("70-lead-prompt.md", r.stdout)


class TestDerecordSkill(DerecordCase):
    """Step 6: derecord installs the /warmup skill (proposal 19, W-11).

    The skill lives once, at skills/warmup/SKILL.md in common-rules. A project
    must not keep a divergent copy: this matches, not merely adds -- same
    principle as the .gitattributes and hooks steps above.
    """

    SKILL_SRC = ROOT / "skills" / "warmup" / "SKILL.md"
    SKILL_REL = Path(".claude") / "skills" / "warmup" / "SKILL.md"

    def test_missing_skill_is_installed_byte_identical(self):
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        dest = self.proj / self.SKILL_REL
        self.assertTrue(dest.exists(), "skill was not installed")
        self.assertEqual(dest.read_bytes(), self.SKILL_SRC.read_bytes())
        self.assertIn(f"  {self.SKILL_REL}: installed", r.stdout)

    def test_a_second_run_leaves_it_byte_identical_and_says_so(self):
        self.run_derecord()
        before = (self.proj / self.SKILL_REL).read_bytes()
        second = self.run_derecord()
        self.assertEqual(before, (self.proj / self.SKILL_REL).read_bytes())
        self.assertIn(f"  {self.SKILL_REL}: already current", second.stdout)

    def test_a_stale_copy_is_corrected_to_the_source(self):
        dest = self.proj / self.SKILL_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("stale copy, not what common-rules has\n")
        r = self.run_derecord()
        self.assertEqual(dest.read_bytes(), self.SKILL_SRC.read_bytes())
        self.assertIn(f"  {self.SKILL_REL}: corrected", r.stdout)

    def test_a_sibling_skill_survives_byte_identical(self):
        sibling = self.proj / ".claude" / "skills" / "other" / "SKILL.md"
        sibling.parent.mkdir(parents=True, exist_ok=True)
        sibling.write_text("unrelated skill, do not touch\n")
        self.run_derecord()
        self.assertEqual(sibling.read_text(), "unrelated skill, do not touch\n")


class TestDerecordHooks(DerecordCase):
    """Step 5: derecord installs the checkpoint hooks (proposal 19, D8 / W-08)."""

    def test_settings_gains_exactly_one_entry_per_hook(self):
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        d = settings_in(self.proj)
        for name, event in HOOK_EVENTS:
            entries = d["hooks"].get(event, [])
            matches = [
                h for e in entries for h in e.get("hooks", [])
                if h.get("command", "").endswith(f"/hooks/{name}")
            ]
            self.assertEqual(len(matches), 1, f"{event}/{name} did not gain exactly one entry")
            self.assertEqual(matches[0]["command"], f"{ROOT}/hooks/{name}")
            self.assertIn("installed", r.stdout)

    def test_rulecheck_and_an_unrelated_hook_survive(self):
        settings_path = self.proj / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"hooks": [{"type": "command",
                                              "command": f"{ROOT}/bin/rulecheck --quiet"}]}],
                "PostToolUse": [{"hooks": [{"type": "command", "command": "/some/other/hook"}]}],
            }
        }))
        self.run_derecord()
        d = settings_in(self.proj)
        session_commands = [h["command"] for e in d["hooks"]["SessionStart"]
                             for h in e["hooks"]]
        self.assertIn(f"{ROOT}/bin/rulecheck --quiet", session_commands)
        self.assertEqual(
            d["hooks"]["PostToolUse"][0]["hooks"][0]["command"], "/some/other/hook")

    def test_a_stale_hook_path_is_corrected(self):
        settings_path = self.proj / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({
            "hooks": {"Stop": [{"hooks": [{"type": "command",
                                            "command": "/old/rules/hooks/stop"}]}]}
        }))
        r = self.run_derecord()
        d = settings_in(self.proj)
        stop_commands = [h["command"] for e in d["hooks"]["Stop"] for h in e["hooks"]]
        self.assertEqual(stop_commands, [f"{ROOT}/hooks/stop"],
                          "stale hook path was not corrected in place")
        self.assertIn("corrected", r.stdout)

    def test_running_hooks_install_twice_changes_nothing_the_second_time(self):
        self.run_derecord()
        before = settings_in(self.proj)
        second = self.run_derecord()
        self.assertEqual(before, settings_in(self.proj))
        for _name, event in HOOK_EVENTS:
            self.assertIn("already present", second.stdout)


if __name__ == "__main__":
    unittest.main()
