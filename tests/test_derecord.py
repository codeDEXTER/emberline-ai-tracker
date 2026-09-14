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
import hashlib
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

HOOK_EVENTS = [("precompact", "PreCompact"), ("stop", "Stop"), ("sessionstart", "SessionStart"),
               ("posttooluse-agent", "PostToolUse")]


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


class TestDerecordPostToolUseAgentMatcher(DerecordCase):
    """D13, part 2: the V-05 hook gets matcher Agent|Task, since the Agent
    tool's own hook name is undocumented and the hook itself filters."""

    def _entries(self, d):
        return [e for e in d["hooks"].get("PostToolUse", [])
                 for h in e.get("hooks", [])
                 if h.get("command", "").endswith("/hooks/posttooluse-agent")]

    def test_the_installed_entry_carries_the_matcher(self):
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        d = settings_in(self.proj)
        entries = [e for e in d["hooks"]["PostToolUse"]
                   if any(h.get("command", "").endswith("/hooks/posttooluse-agent")
                          for h in e.get("hooks", []))]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get("matcher"), "Agent|Task")

    def test_a_stale_matcher_is_corrected_in_place(self):
        settings_path = self.proj / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({
            "hooks": {"PostToolUse": [{"matcher": "Task",
                                        "hooks": [{"type": "command",
                                                    "command": f"{ROOT}/hooks/posttooluse-agent"}]}]}
        }))
        r = self.run_derecord()
        d = settings_in(self.proj)
        entries = [e for e in d["hooks"]["PostToolUse"]
                   if any(h.get("command", "").endswith("/hooks/posttooluse-agent")
                          for h in e.get("hooks", []))]
        self.assertEqual(entries[0].get("matcher"), "Agent|Task")
        self.assertIn("corrected", r.stdout)

    def test_an_unrelated_posttooluse_entry_survives(self):
        settings_path = self.proj / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({
            "hooks": {"PostToolUse": [{"matcher": "Bash",
                                        "hooks": [{"type": "command", "command": "/some/other/hook"}]}]}
        }))
        self.run_derecord()
        d = settings_in(self.proj)
        entries = d["hooks"]["PostToolUse"]
        self.assertTrue(any(e.get("matcher") == "Bash"
                             and e["hooks"][0]["command"] == "/some/other/hook" for e in entries))
        self.assertTrue(any(e.get("matcher") == "Agent|Task" for e in entries))

    def test_running_twice_changes_nothing_the_second_time(self):
        self.run_derecord()
        before = settings_in(self.proj)
        second = self.run_derecord()
        self.assertEqual(before, settings_in(self.proj))
        self.assertIn("already present", second.stdout)


class TestDerecordIgnoreRuflo(DerecordCase):
    """D13, part 1: derecord ignores Ruflo's runtime state only. Reuses the
    lines PR #149 (ignore-ruflo-state) already named for this checkout, minus
    the blanket `.claude-flow/` -- shared Ruflo config must stay tracked."""

    RUNTIME_PATHS = [
        ".claude-flow/data/foo.json",
        ".claude-flow/logs/bar.log",
        ".claude-flow/sessions/baz.json",
        ".swarm/db.sqlite",
        "ruvector.db",
        ".claude/memory.db",
        ".claude/proven-config.json",
        ".claude/.proven-config-version",
    ]
    CONFIG_PATHS = [".claude-flow/config.json", ".claude-flow/config.yaml", "claude-flow.config.json"]

    def is_ignored(self, rel: str) -> bool:
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=self.proj)
        return r.returncode == 0

    def test_runtime_state_is_ignored(self):
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel in self.RUNTIME_PATHS:
            self.assertTrue(self.is_ignored(rel), f"{rel} should be ignored")

    def test_ruflo_config_stays_tracked(self):
        self.run_derecord()
        for rel in self.CONFIG_PATHS:
            self.assertFalse(self.is_ignored(rel), f"{rel} should stay tracked")

    def test_existing_gitignore_lines_survive(self):
        (self.proj / ".gitignore").write_text("*.log\n")
        self.run_derecord()
        text = (self.proj / ".gitignore").read_text()
        self.assertIn("*.log", text)

    def test_running_twice_does_not_duplicate_lines(self):
        self.run_derecord()
        first = (self.proj / ".gitignore").read_text()
        second_result = self.run_derecord()
        self.assertEqual(first, (self.proj / ".gitignore").read_text())
        self.assertIn("already present", second_result.stdout)


class LedgerCommitHelpers:
    """Shared by every TestCase below that stages and commits a ledger.
    Not a TestCase itself -- mixed in, so its methods are never collected
    and re-run as tests under more than one class name."""

    def setUp(self):
        super().setUp()
        subprocess.run(["git", "-C", str(self.proj), "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.proj), "config", "user.name", "Test"], check=True)

    def write_ledger(self, rel="docs/proposals/42-thing.json", **overrides):
        path = self.proj / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "proposal": 42, "title": "Thing", "status": "accepted",
            "items": [{"id": "X-01", "phase": "X", "cx": "C2", "title": "t",
                       "status": "not started"}],
        }
        data.update(overrides)
        path.write_text(json.dumps(data, indent=2))
        return path

    def git(self, *args, check=True):
        return subprocess.run(["git", "-C", str(self.proj), *args],
                              capture_output=True, text=True, check=check)

    def commit(self, *paths):
        subprocess.run(["git", "-C", str(self.proj), "add", *[str(p) for p in paths]], check=True)
        return subprocess.run(["git", "-C", str(self.proj), "commit", "-m", "test"],
                              capture_output=True, text=True, cwd=self.proj)

    def committed_files(self):
        r = subprocess.run(["git", "-C", str(self.proj), "show", "--stat", "--pretty=", "HEAD"],
                           capture_output=True, text=True, check=True)
        return r.stdout


class TestDerecordPreCommitLedger(LedgerCommitHelpers, DerecordCase):
    """D12: a staged ledger regenerates and stages its tracker page and the
    checkpoint, alongside the existing conflict-marker guard."""

    def test_a_staged_ledger_gets_its_page_and_checkpoint_committed_alongside(self):
        self.run_derecord()
        ledger_path = self.write_ledger()
        r = self.commit(ledger_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.proj / "docs" / "proposals" / "tracker" / "42-thing.html"
        self.assertTrue(page.exists(), "tracker page was not regenerated")
        checkpoint_dir = self.proj / "docs" / "handovers"
        checkpoints = list(checkpoint_dir.glob("*-checkpoint.md")) if checkpoint_dir.is_dir() else []
        self.assertTrue(checkpoints, "checkpoint was not written")
        files = self.committed_files()
        self.assertIn("42-thing.html", files)
        self.assertIn("checkpoint.md", files)

    def test_an_invalid_ledger_fails_the_commit_with_trackers_message(self):
        self.run_derecord()
        ledger_path = self.write_ledger(rel="docs/proposals/43-bad.json",
                                         items=[{"id": "not-an-id", "phase": "X", "cx": "C2",
                                                 "title": "t", "status": "nonsense-status"}])
        r = self.commit(ledger_path)
        self.assertNotEqual(r.returncode, 0, "commit of an invalid ledger should have been refused")
        self.assertIn("not well-formed", r.stderr + r.stdout)

    def test_a_commit_with_no_ledger_does_no_tracker_work(self):
        self.run_derecord()
        # step 4 seeds docs/handovers/lead-prompt.md on every project, so the
        # directory existing proves nothing here -- a checkpoint file would.
        before_checkpoints = set((self.proj / "docs" / "handovers").glob("*-checkpoint.md"))
        plain = self.proj / "README.md"
        plain.write_text("hello\n")
        r = self.commit(plain)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.proj / "docs" / "proposals" / "tracker").exists())
        after_checkpoints = set((self.proj / "docs" / "handovers").glob("*-checkpoint.md"))
        self.assertEqual(before_checkpoints, after_checkpoints, "checkpoint was written with no ledger staged")

    def test_a_non_ledger_json_file_matching_the_glob_is_left_alone(self):
        """docs/proposals also holds data files shaped like NN-*.json that are
        not ledgers -- the PhotoVault engine's own sidecar file. No `items`
        list means no tracker work, per tools/tracker/ledger.find's rule."""
        self.run_derecord()
        sidecar = self.proj / "docs" / "proposals" / "56-sample-sheet.sidecar.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps({"rows": [1, 2, 3]}))
        r = self.commit(sidecar)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.proj / "docs" / "proposals" / "tracker").exists())

    def test_conflict_marker_guard_still_runs_first(self):
        self.run_derecord()
        bad = self.proj / "conflicted.py"
        bad.write_text("<<<<<<< HEAD\nx = 1\n=======\nx = 2\n>>>>>>> branch\n")
        r = self.commit(bad)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unresolved conflict markers", r.stderr)

    def test_a_pre_existing_project_hook_is_preserved_and_chained(self):
        hooks_dir = self.proj / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        marker = self.proj / "local-hook-ran"
        custom = hooks_dir / "pre-commit"
        custom.write_text(f"#!/usr/bin/env bash\ntouch '{marker}'\nexit 1\n")
        custom.chmod(0o755)

        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        local = hooks_dir / "pre-commit.local"
        self.assertTrue(local.exists(), "the project's own pre-commit hook was lost")
        self.assertIn("touch", local.read_text())

        plain = self.proj / "README.md"
        plain.write_text("hello\n")
        result = self.commit(plain)
        self.assertNotEqual(result.returncode, 0, "the chained local hook should have failed the commit")
        self.assertTrue(marker.exists(), "the project's own pre-commit hook was never run")

    def test_running_derecord_twice_does_not_move_the_local_hook_again(self):
        hooks_dir = self.proj / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        custom = hooks_dir / "pre-commit"
        custom.write_text("#!/usr/bin/env bash\nexit 0\n")
        custom.chmod(0o755)

        self.run_derecord()
        local = hooks_dir / "pre-commit.local"
        before = local.read_text()
        self.run_derecord()
        self.assertEqual(before, local.read_text())

    def test_hook_resolves_common_rules_from_the_install_time_path_not_cwd(self):
        """The regenerating pre-commit hook must find common-rules the same
        way the other installed hooks do: baked in at install time, not by
        looking at the commit's cwd."""
        self.run_derecord()
        content = (self.proj / ".git" / "hooks" / "pre-commit").read_text()
        self.assertIn(str(ROOT), content)


class TestDerecordSettingsGuard(DerecordCase):
    """V-07 round 2, finding 2: a malformed .claude/settings.json must be
    refused, not silently replaced with {} -- checked before any step writes,
    so a broken settings file leaves the whole run a no-op."""

    def write_settings(self, text):
        path = self.proj / ".claude" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_invalid_json_refuses_and_changes_nothing(self):
        self.write_settings("{not valid json")
        r = self.run_derecord()
        self.assertNotEqual(r.returncode, 0, "a malformed settings.json should refuse the whole run")
        self.assertIn("derecord: .claude/settings.json is not valid JSON; fix it and run again (nothing changed)",
                       r.stderr + r.stdout)
        self.assertFalse((self.proj / ".gitattributes").exists(), "gitattributes step ran despite the refusal")
        self.assertFalse((self.proj / ".git" / "hooks" / "pre-commit").exists(),
                          "pre-commit was installed despite the refusal")
        self.assertFalse((self.proj / ".gitignore").exists(), "gitignore step ran despite the refusal")

    def test_valid_json_that_is_not_an_object_refuses(self):
        self.write_settings("[1, 2, 3]")
        r = self.run_derecord()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("is not valid JSON", r.stderr + r.stdout)
        self.assertFalse((self.proj / ".gitattributes").exists())

    def test_a_missing_settings_json_still_starts_from_an_empty_object(self):
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        d = settings_in(self.proj)
        self.assertIn("hooks", d)


class TestDerecordPreCommitUnstagedGuard(LedgerCommitHelpers, DerecordCase):
    """V-07 round 2, finding 1: the page must never carry text that was
    never staged. A ledger, its page, or the checkpoint with unstaged edits
    refuses the commit rather than rendering from the working tree."""

    def test_a_ledger_with_unstaged_edits_after_staging_refuses(self):
        self.run_derecord()
        ledger_path = self.write_ledger()
        self.git("add", str(ledger_path))
        # Edit again without re-staging -- the reviewer's exact reproduction.
        ledger_path.write_text(ledger_path.read_text().replace("Thing", "Something else entirely"))
        r = subprocess.run(["git", "-C", str(self.proj), "commit", "-m", "test"],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, "a ledger with unstaged edits must not be committed")
        self.assertIn("has unstaged changes", r.stderr + r.stdout)
        self.assertIn("docs/proposals/42-thing.json", r.stderr + r.stdout)
        page = self.proj / "docs" / "proposals" / "tracker" / "42-thing.html"
        self.assertFalse(page.exists(), "the page must not be rendered from the never-staged text")

    def test_the_committed_page_never_carries_never_staged_text(self):
        """Even if the guard above did not exist, the page that does get
        committed must reflect only the staged content."""
        self.run_derecord()
        ledger_path = self.write_ledger(title="Original Title")
        r = self.commit(ledger_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.proj / "docs" / "proposals" / "tracker" / "42-thing.html"
        self.assertIn("Original Title", page.read_text())

    def test_a_page_with_unstaged_edits_refuses_the_next_ledger_commit(self):
        self.run_derecord()
        ledger_path = self.write_ledger()
        r = self.commit(ledger_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = self.proj / "docs" / "proposals" / "tracker" / "42-thing.html"
        # A local, unstaged hand-edit to the generated page.
        page.write_text(page.read_text() + "\n<!-- local note -->\n")

        self.write_ledger(title="Thing v2")
        r = self.commit(ledger_path)
        self.assertNotEqual(r.returncode, 0, "an unstaged edit to the page must refuse the commit")
        self.assertIn("has unstaged changes", r.stderr + r.stdout)
        self.assertIn("42-thing.html", r.stderr + r.stdout)

    def test_a_checkpoint_with_unstaged_edits_refuses_the_next_ledger_commit(self):
        self.run_derecord()
        ledger_path = self.write_ledger()
        r = self.commit(ledger_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        checkpoints = list((self.proj / "docs" / "handovers").glob("*-checkpoint.md"))
        self.assertTrue(checkpoints)
        checkpoint = checkpoints[0]
        checkpoint.write_text(checkpoint.read_text() + "\nlocal note\n")

        self.write_ledger(title="Thing v3")
        r = self.commit(ledger_path)
        self.assertNotEqual(r.returncode, 0, "an unstaged edit to the checkpoint must refuse the commit")
        self.assertIn("has unstaged changes", r.stderr + r.stdout)
        self.assertIn("checkpoint.md", r.stderr + r.stdout)


class TestDerecordCheckpointPathFromStdout(LedgerCommitHelpers, DerecordCase):
    """V-07 round 2, finding 4: the checkpoint path is whatever tracker
    itself reports having written, not recomputed a second time from today's
    date -- the two can disagree across midnight."""

    def test_the_commit_that_closes_the_last_open_item_is_not_refused(self):
        """Lead, after round 2: tracker prints "checkpoint: no open ledger" and
        exits 0 when the staged ledger has nothing left open. Refusing that
        meant the commit finishing a proposal could never be made."""
        self.run_derecord()
        ledger_path = self.write_ledger(items=[{
            "id": "X-01", "phase": "X", "cx": "C2", "title": "t", "status": "done",
            "log": [{"at": "2026-09-14T00:00:00+00:00", "event": "done", "by": "lead", "evidence": "e"}],
        }])
        r = self.commit(ledger_path)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([], [f for f in self.committed_files() if f.endswith("-checkpoint.md")])

    def test_the_staged_checkpoint_path_matches_what_tracker_reported(self):
        self.run_derecord()
        ledger_path = self.write_ledger()
        r = self.commit(ledger_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        checkpoints = list((self.proj / "docs" / "handovers").glob("*-checkpoint.md"))
        self.assertEqual(len(checkpoints), 1)
        self.assertIn(checkpoints[0].name, self.committed_files())


class TestDerecordPreCommitHookIdentity(LedgerCommitHelpers, DerecordCase):
    """V-07 round 2, finding 3: "ours" is a `# derecord-body-sha256: <hex>`
    line whose value equals the sha256 of the hook body after that line --
    never a text match, since coincidental text should not be mistaken for
    ours."""

    def hooks_dir(self):
        return self.proj / ".git" / "hooks"

    def test_an_unmarked_v1_hook_is_treated_as_foreign_and_chained(self):
        """The PhotoVault app and engine have exactly this today: an older
        derecord-installed hook with prose but no sha256 marker."""
        hooks = self.hooks_dir()
        hooks.mkdir(parents=True, exist_ok=True)
        v1 = hooks / "pre-commit"
        v1.write_text("#!/usr/bin/env bash\n"
                       "# derecord: managed pre-commit hook -- edit bin/derecord in common-rules, not this file\n"
                       "exit 0\n")
        v1.chmod(0o755)
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        local = hooks / "pre-commit.local"
        self.assertTrue(local.exists(), "the unmarked v1 hook was not preserved as foreign")
        self.assertIn("derecord: managed pre-commit hook", local.read_text())
        new_hook = (hooks / "pre-commit").read_text()
        self.assertIn("derecord-body-sha256:", new_hook)

    def test_a_hook_with_coincidental_marker_text_but_wrong_hash_is_foreign(self):
        hooks = self.hooks_dir()
        hooks.mkdir(parents=True, exist_ok=True)
        fake_body = "echo not really ours\nexit 1\n"
        fake = hooks / "pre-commit"
        fake.write_text(f"#!/usr/bin/env bash\n# derecord-body-sha256: {'0' * 64}\n{fake_body}")
        fake.chmod(0o755)
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        local = hooks / "pre-commit.local"
        self.assertTrue(local.exists(), "a hook with a non-matching hash must be treated as foreign")
        self.assertIn(fake_body, local.read_text())

    def test_our_own_hook_is_corrected_in_place_without_touching_local(self):
        self.run_derecord()
        hooks = self.hooks_dir()
        local = hooks / "pre-commit.local"
        self.assertFalse(local.exists())
        first = (hooks / "pre-commit").read_text()
        self.run_derecord()
        self.assertFalse(local.exists(), "our own, unchanged hook must never be chained to itself")
        self.assertEqual(first, (hooks / "pre-commit").read_text())

    def test_the_marker_hash_actually_matches_the_body_that_follows_it(self):
        self.run_derecord()
        content = (self.hooks_dir() / "pre-commit").read_text()
        lines = content.split("\n")
        idx = next(i for i, l in enumerate(lines) if l.startswith("# derecord-body-sha256: "))
        claimed = lines[idx].split(": ", 1)[1]
        body = "\n".join(lines[idx + 1:])
        self.assertEqual(hashlib.sha256(body.encode()).hexdigest(), claimed)

    def test_when_pre_commit_local_already_exists_a_foreign_hook_refuses_and_changes_nothing(self):
        hooks = self.hooks_dir()
        hooks.mkdir(parents=True, exist_ok=True)
        local = hooks / "pre-commit.local"
        local.write_text("#!/usr/bin/env bash\n# unrelated, pre-existing local hook\nexit 0\n")
        local.chmod(0o755)
        foreign = hooks / "pre-commit"
        foreign.write_text("#!/usr/bin/env bash\n# some foreign hook, not ours\nexit 0\n")
        foreign.chmod(0o755)
        before_foreign, before_local = foreign.read_text(), local.read_text()

        r = self.run_derecord()
        self.assertNotEqual(r.returncode, 0, "a foreign hook with an existing pre-commit.local must refuse")
        self.assertIn("pre-commit", r.stderr + r.stdout)
        self.assertIn("pre-commit.local", r.stderr + r.stdout)
        self.assertEqual(before_foreign, foreign.read_text(), "the foreign hook must be left untouched")
        self.assertEqual(before_local, local.read_text(), "the pre-existing local hook must be left untouched")


class TestDerecordIgnoreDoesNotUntrack(LedgerCommitHelpers, DerecordCase):
    """V-07 round 2, finding 5: the ignore lines cannot untrack a file
    already committed. derecord must say so and never run git rm itself."""

    def test_an_already_tracked_runtime_file_is_reported_not_untracked(self):
        tracked = self.proj / ".claude-flow" / "data" / "state.json"
        tracked.parent.mkdir(parents=True, exist_ok=True)
        tracked.write_text("{}")
        self.git("add", str(tracked))
        subprocess.run(["git", "-C", str(self.proj), "commit", "-m", "pre-existing runtime file"], check=True)

        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("already tracked", r.stdout)
        self.assertIn("git rm -r --cached", r.stdout)
        tracked_files = self.git("ls-files").stdout
        self.assertIn(".claude-flow/data/state.json", tracked_files, "derecord must never untrack the file itself")

    def test_no_warning_when_nothing_tracked_matches(self):
        r = self.run_derecord()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("already tracked", r.stdout)


class TestDerecordParent(unittest.TestCase):
    """`derecord --parent DIR` (proposal 21, S-05): a start folder above
    several projects, itself not a git repo, gets only the SessionStart entry
    for hooks/sessionstart -- nothing else this file installs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name) / "PhotoVault"
        self.parent.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def make_child_project(self, name: str) -> Path:
        """A minimal child that qualifies as a project: its own git repo and
        its own .common-rules.json (S-05's own test for project-hood)."""
        child = self.parent / name
        child.mkdir()
        subprocess.run(["git", "init", "-q", str(child)], check=True)
        (child / ".common-rules.json").write_text("{}")
        return child

    def run_parent(self):
        return subprocess.run([str(DERECORD), "--parent", str(self.parent)],
                              capture_output=True, text=True, check=False)

    def session_start_commands(self) -> list[str]:
        d = json.loads((self.parent / ".claude" / "settings.json").read_text())
        return [h["command"] for e in d.get("hooks", {}).get("SessionStart", [])
                for h in e.get("hooks", [])]

    def test_installs_the_sessionstart_entry_once(self):
        self.make_child_project("app")
        self.make_child_project("engine")
        r = self.run_parent()
        self.assertEqual(0, r.returncode, r.stderr)
        commands = self.session_start_commands()
        matches = [c for c in commands if c.endswith("/hooks/sessionstart")]
        self.assertEqual([f"{ROOT}/hooks/sessionstart"], matches)
        self.assertIn("installed", r.stdout)

    def test_a_second_run_changes_nothing(self):
        self.make_child_project("app")
        self.run_parent()
        before = (self.parent / ".claude" / "settings.json").read_text()
        r2 = self.run_parent()
        self.assertEqual(0, r2.returncode, r2.stderr)
        self.assertEqual(before, (self.parent / ".claude" / "settings.json").read_text())
        self.assertIn("already present", r2.stdout)

    def test_other_settings_survive(self):
        self.make_child_project("app")
        settings_path = self.parent / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({
            "hooks": {"PostToolUse": [{"hooks": [{"type": "command", "command": "/some/other/hook"}]}]},
            "unrelatedTopLevelKey": "kept",
        }))
        r = self.run_parent()
        self.assertEqual(0, r.returncode, r.stderr)
        d = json.loads(settings_path.read_text())
        self.assertEqual("kept", d.get("unrelatedTopLevelKey"))
        self.assertEqual("/some/other/hook", d["hooks"]["PostToolUse"][0]["hooks"][0]["command"])

    def test_a_stale_command_is_corrected_in_place(self):
        self.make_child_project("app")
        settings_path = self.parent / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "/old/rules/hooks/sessionstart"}]}]}
        }))
        r = self.run_parent()
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual([f"{ROOT}/hooks/sessionstart"], self.session_start_commands())
        self.assertIn("corrected", r.stdout)

    def test_malformed_settings_json_is_refused(self):
        self.make_child_project("app")
        settings_path = self.parent / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("{not valid json")
        before = settings_path.read_text()
        r = self.run_parent()
        self.assertNotEqual(0, r.returncode)
        self.assertIn("not valid JSON", r.stderr + r.stdout)
        self.assertEqual(before, settings_path.read_text())

    def test_a_git_repo_is_refused(self):
        self.make_child_project("app")
        subprocess.run(["git", "init", "-q", str(self.parent)], check=True)
        r = self.run_parent()
        self.assertNotEqual(0, r.returncode)
        self.assertIn("is a git repository", r.stderr + r.stdout)
        self.assertFalse((self.parent / ".claude" / "settings.json").exists())

    def test_no_children_is_refused(self):
        (self.parent / "notes").mkdir()
        r = self.run_parent()
        self.assertNotEqual(0, r.returncode)
        self.assertIn("no child project", r.stderr + r.stdout)
        self.assertFalse((self.parent / ".claude" / "settings.json").exists())

    def test_a_child_with_only_an_open_ledger_also_qualifies(self):
        """Project-hood via an open ledger under docs/proposals/, not just
        .common-rules.json -- the same second marker the hook itself uses."""
        child = self.parent / "engine"
        (child / "docs" / "proposals").mkdir(parents=True)
        (child / "docs" / "proposals" / "19-x.json").write_text(json.dumps({
            "proposal": 19, "title": "x", "status": "accepted",
            "items": [{"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "not started"}],
        }))
        r = self.run_parent()
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("installed", r.stdout)

    def test_installs_nothing_else(self):
        self.make_child_project("app")
        r = self.run_parent()
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertFalse((self.parent / ".gitattributes").exists())
        self.assertFalse((self.parent / ".gitignore").exists())
        self.assertFalse((self.parent / "HANDOFF.md").exists())
        d = json.loads((self.parent / ".claude" / "settings.json").read_text())
        self.assertEqual(["SessionStart"], list(d.get("hooks", {}).keys()))


if __name__ == "__main__":
    unittest.main()
