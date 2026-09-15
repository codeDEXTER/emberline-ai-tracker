"""Stop, PreCompact and SessionStart hooks, and the checkpoint writer they
share (proposal 19, W-07 / D8). A compaction can only lose what lived
nowhere but the chat (proposal 19, section K) -- these hooks are the write
side: the checkpoint is written from the ledger, on disk, before the summary
is made, and a fresh session is pointed back at the ledger rather than the
summary it just lost context to.

Every hook is exercised the way Claude Code actually calls it: JSON on
stdin, subprocess, in a scratch project (its own git repo, its own
docs/proposals ledger) so nothing here ever touches a real project.

Run:  python3 -m unittest discover -s tests -p 'test_hooks.py' -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import checkpoint, ledger  # noqa: E402

HOOKS = ROOT / "hooks"
PRECOMPACT = HOOKS / "precompact"
STOP = HOOKS / "stop"
SESSIONSTART = HOOKS / "sessionstart"
POSTTOOLUSE_AGENT = HOOKS / "posttooluse-agent"


def minimal(**over) -> dict:
    d = {
        "proposal": 19, "title": "Warm-up", "status": "accepted",
        "phases": [{"id": "W", "name": "build"}],
        "items": [
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "done",
             "tag": "[ruflo · medium · sonnet]",
             "log": [{"at": "2026-09-13T20:00:00+02:00", "event": "merged", "by": "lead", "evidence": "abc123"}]},
            {"id": "W-02", "phase": "W", "cx": "C3", "title": "render", "status": "in progress",
             "tag": "[ruflo · high · opus]", "depends": "W-01",
             "log": [{"at": "2026-09-13T21:00:00+02:00", "event": "started", "by": "lead", "evidence": "branch p19-x"}]},
            {"id": "W-03", "phase": "W", "cx": "C2", "title": "sync", "status": "blocked",
             "tag": "[ruflo · medium · sonnet]", "depends": ["W-01"],
             "log": [{"at": "2026-09-13T21:10:00+02:00", "event": "blocked", "by": "lead", "evidence": "needs gh token"}]},
            {"id": "W-04", "phase": "W", "cx": "C2", "title": "recall", "status": "not started",
             "tag": "[ruflo · medium · sonnet]", "depends": ["W-01"]},
        ],
        "asks": [{"id": "A-01", "at": "2026-09-13", "kind": "decision", "quote": "ruflo mandatory",
                  "became": None, "state": "open"}],
    }
    d.update(over)
    return d


def all_done() -> dict:
    d = minimal()
    for i in d["items"]:
        i["status"] = "done"
        i["log"] = [{"at": "2026-09-13T20:00:00+02:00", "event": "merged", "by": "lead", "evidence": "x"}]
    return d


class ScratchProject(unittest.TestCase):
    """A throwaway project: its own git repo, its own docs/proposals ledger.
    Nothing here ever writes outside `self.proj`."""

    LEDGER = minimal()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        (self.proj / "docs" / "proposals").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)
        subprocess.run(["git", "-C", str(self.proj), "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.proj), "config", "user.name", "t"], check=True)
        self.write_ledger(self.LEDGER)
        (self.proj / "README.md").write_text("scratch\n")
        subprocess.run(["git", "-C", str(self.proj), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.proj), "commit", "-q", "-m", "init"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write_ledger(self, data: dict):
        (self.proj / "docs" / "proposals" / "19-x.json").write_text(json.dumps(data))

    def checkpoint_path(self, date="2026-09-13") -> Path:
        found = list((self.proj / "docs" / "handovers").glob("*-checkpoint.md"))
        self.assertEqual(1, len(found), found)
        return found[0]

    def run_hook(self, hook: Path, payload: dict | None, cwd=None, raw_stdin: str | None = None, env=None):
        stdin = raw_stdin if raw_stdin is not None else json.dumps(payload or {})
        run_env = {**os.environ, **env} if env else None
        return subprocess.run([sys.executable, str(hook)], input=stdin, capture_output=True,
                              text=True, cwd=cwd, timeout=15, check=False, env=run_env)


class TestCheckpointContent(ScratchProject):

    def test_sections_in_order(self):
        rc = checkpoint.main(["--project", str(self.proj), "--reason", "manual"])
        self.assertEqual(0, rc)
        text = self.checkpoint_path().read_text()
        order = [
            "# Checkpoint —", "Reason: manual", "<!-- ledger-digest:",
            "## Proposal 19 · Warm-up", "### In progress", "### Blocked, and why",
            "### Open asks", "### Next unblocked", "## Exact next action",
        ]
        positions = [text.index(m) for m in order]
        self.assertEqual(positions, sorted(positions), text)
        self.assertIn("W-02", text)  # in progress
        self.assertIn("W-03", text)  # blocked
        self.assertIn("A-01", text)  # open ask
        self.assertIn("W-04", text)  # next unblocked
        self.assertIn("needs gh token", text)  # blocked item's last log evidence
        self.assertIn("started", text)  # in-progress item's last log event

    def test_nothing_written_when_all_items_done(self):
        self.write_ledger(all_done())
        rc = checkpoint.main(["--project", str(self.proj), "--reason", "manual"])
        self.assertEqual(0, rc)
        self.assertFalse((self.proj / "docs" / "handovers").exists())

    def test_if_changed_skips_an_unchanged_ledger(self):
        checkpoint.main(["--project", str(self.proj), "--reason", "stop", "--if-changed"])
        path = self.checkpoint_path()
        original = path.read_text()
        path.write_text(original + "\n<!-- marker: untouched -->\n")
        rc = checkpoint.main(["--project", str(self.proj), "--reason", "stop", "--if-changed"])
        self.assertEqual(0, rc)
        self.assertIn("marker: untouched", path.read_text())

    def test_if_changed_rewrites_a_changed_ledger(self):
        checkpoint.main(["--project", str(self.proj), "--reason", "stop", "--if-changed"])
        path = self.checkpoint_path()
        path.write_text(path.read_text() + "\n<!-- marker: stale -->\n")
        changed = minimal()
        changed["items"][3]["status"] = "in progress"
        changed["items"][3]["log"] = [{"at": "2026-09-13T22:00:00+02:00", "event": "started", "by": "lead", "evidence": "y"}]
        self.write_ledger(changed)
        rc = checkpoint.main(["--project", str(self.proj), "--reason", "stop", "--if-changed"])
        self.assertEqual(0, rc)
        self.assertNotIn("marker: stale", path.read_text())

    def test_outside_git_head_is_unknown(self):
        no_git = Path(tempfile.mkdtemp())
        (no_git / "docs" / "proposals").mkdir(parents=True)
        (no_git / "docs" / "proposals" / "19-x.json").write_text(json.dumps(minimal()))
        rc = checkpoint.main(["--project", str(no_git), "--reason", "manual"])
        self.assertEqual(0, rc)
        found = list((no_git / "docs" / "handovers").glob("*-checkpoint.md"))
        self.assertEqual(1, len(found))
        self.assertIn("HEAD unknown", found[0].read_text())


class TestPrecompactHook(ScratchProject):

    def test_writes_a_checkpoint(self):
        r = self.run_hook(PRECOMPACT, {"cwd": str(self.proj), "trigger": "auto"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())
        self.checkpoint_path()  # exists, asserts exactly one

    def test_malformed_stdin_and_missing_cwd_exit_zero(self):
        r = self.run_hook(PRECOMPACT, None, cwd=str(self.proj), raw_stdin="not json{{{")
        self.assertEqual(0, r.returncode, r.stderr)
        self.checkpoint_path()  # still ran, using cwd fallback


class TestStopHook(ScratchProject):

    def test_stop_hook_active_writes_nothing(self):
        r = self.run_hook(STOP, {"cwd": str(self.proj), "stop_hook_active": True})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertFalse((self.proj / "docs" / "handovers").exists())

    def test_stop_twice_writes_once(self):
        r1 = self.run_hook(STOP, {"cwd": str(self.proj)})
        self.assertEqual(0, r1.returncode, r1.stderr)
        path = self.checkpoint_path()
        path.write_text(path.read_text() + "\n<!-- marker: first-write-only -->\n")
        r2 = self.run_hook(STOP, {"cwd": str(self.proj)})
        self.assertEqual(0, r2.returncode, r2.stderr)
        self.assertIn("marker: first-write-only", path.read_text())

    def test_malformed_stdin_and_missing_cwd_exit_zero(self):
        r = self.run_hook(STOP, None, cwd=str(self.proj), raw_stdin="{not valid")
        self.assertEqual(0, r.returncode, r.stderr)
        self.checkpoint_path()

    def _warmup_module(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("warmup_for_test_hooks", str(ROOT / "bin" / "warmup"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    def test_rules_moved_prints_the_notice(self):
        """Proposal 28, R-03. A state file recording a rules HEAD that is not
        the checkout's current one (never faked by actually moving the real
        checkout -- only the state file's own recorded value) makes the Stop
        hook print one line."""
        W = self._warmup_module()
        state_path = W.default_state_path(self.proj)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"rules_head": "0" * 40}))
        r = self.run_hook(STOP, {"cwd": str(self.proj)})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("rules moved -- run /reheat", r.stdout)

    def test_no_state_file_prints_nothing_extra(self):
        r = self.run_hook(STOP, {"cwd": str(self.proj)})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotIn("rules moved", r.stdout)

    def test_a_matching_rules_head_prints_nothing(self):
        W = self._warmup_module()
        state_path = W.default_state_path(self.proj)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        current = W.git(W.RULES_DIR, "rev-parse", "HEAD")
        state_path.write_text(json.dumps({"rules_head": current}))
        r = self.run_hook(STOP, {"cwd": str(self.proj)})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotIn("rules moved", r.stdout)

    def test_rules_moved_check_timeout_never_fails_the_hook(self):
        W = self._warmup_module()
        state_path = W.default_state_path(self.proj)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"rules_head": "0" * 40}))
        r = self.run_hook(STOP, {"cwd": str(self.proj)}, env={"COMMON_RULES_HOOK_TIMEOUT": "0.0001"})
        self.assertEqual(0, r.returncode, r.stderr)


class TestSessionStartHook(ScratchProject):
    """Proposal 28, R-03: startup runs bin/warmup's plain card; compact and
    resume run --reheat. Every dispatch passes --no-pull (this hook is
    read-only) and is bounded by WARMUP_TIMEOUT; a failure or timeout falls
    back to the pre-R-03 one-line-per-ledger summary, never to a failed hook.
    """

    def test_compact_prints_the_rewarm_reminder_then_reheats(self):
        r = self.run_hook(SESSIONSTART, {"cwd": str(self.proj), "source": "compact"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("Context was compacted.", r.stdout)
        self.assertIn("the ledger is the record", r.stdout)
        self.assertIn("Quote rulings from disk, never from the summary.", r.stdout)
        # No saved warmup state yet in this scratch project, so --reheat
        # falls back to printing the full card.
        self.assertIn("WARM ·", r.stdout)
        self.assertIn("HANDOFF.md", r.stdout)
        self.assertIn("OPERATING-RULES.md", r.stdout)
        self.assertIn("19-x.json", r.stdout)
        self.assertIn("Proposal 19 ·", r.stdout)

    def test_startup_runs_the_plain_card(self):
        r = self.run_hook(SESSIONSTART, {"cwd": str(self.proj), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("WARM ·", r.stdout)
        self.assertIn("Proposal 19 ·", r.stdout)
        self.assertNotIn("compacted", r.stdout)
        # A hook never writes: no --queue, so nothing is added to the ledger.
        self.assertNotIn("queue", r.stdout.lower())

    def test_resume_reheats(self):
        r = self.run_hook(SESSIONSTART, {"cwd": str(self.proj), "source": "resume"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("WARM ·", r.stdout)  # no saved state yet -- full card
        self.assertNotIn("compacted", r.stdout)

    def test_clear_source_keeps_the_plain_one_line_fallback(self):
        r = self.run_hook(SESSIONSTART, {"cwd": str(self.proj), "source": "clear"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, len([ln for ln in r.stdout.splitlines() if ln.strip()]))
        self.assertIn("Proposal 19:", r.stdout)
        self.assertIn("run /warmup", r.stdout)

    def test_a_warmup_timeout_falls_back_to_the_one_line_summary(self):
        r = self.run_hook(SESSIONSTART, {"cwd": str(self.proj), "source": "startup"},
                          env={"COMMON_RULES_HOOK_TIMEOUT": "0.0001"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotIn("WARM ·", r.stdout)
        self.assertIn("Proposal 19:", r.stdout)
        self.assertIn("run /warmup", r.stdout)

    def test_no_open_ledger_prints_nothing(self):
        self.write_ledger(all_done())
        r = self.run_hook(SESSIONSTART, {"cwd": str(self.proj), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_malformed_stdin_and_missing_cwd_exit_zero(self):
        r = self.run_hook(SESSIONSTART, None, cwd=str(self.proj), raw_stdin="")
        self.assertEqual(0, r.returncode, r.stderr)


class TestSessionStartParentFolder(unittest.TestCase):
    """A session started above its projects (PhotoVault/ holds app/ and
    engine/) still gets a card: hooks/sessionstart looks one level down when
    the start folder itself has no open ledger of its own (proposal 21, S-05).
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name) / "PhotoVault"
        self.parent.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def make_child(self, name: str, ledger_data: dict | None) -> Path:
        child = self.parent / name
        (child / "docs" / "proposals").mkdir(parents=True)
        if ledger_data is not None:
            (child / "docs" / "proposals" / "19-x.json").write_text(json.dumps(ledger_data))
        return child

    def run_at(self, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SESSIONSTART)], input=json.dumps(payload),
                              capture_output=True, text=True, cwd=str(self.parent), timeout=15, check=False)

    def test_two_children_print_both_lines_and_commands(self):
        self.make_child("app", minimal())
        self.make_child("engine", minimal())
        r = self.run_at({"cwd": str(self.parent), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn(
            "This folder holds 2 projects on the common-rules standard; warm up the one you work on.",
            r.stdout)
        self.assertIn(f"/warmup --project {self.parent / 'app'}", r.stdout)
        self.assertIn(f"/warmup --project {self.parent / 'engine'}", r.stdout)
        self.assertIn("app: 1 open ledger ·", r.stdout)
        self.assertIn("engine: 1 open ledger ·", r.stdout)
        self.assertIn("1 done / 1 in progress / 1 blocked / 1 not started", r.stdout)

    def test_compact_source_uses_the_compact_wording(self):
        self.make_child("app", minimal())
        r = self.run_at({"cwd": str(self.parent), "source": "compact"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("Context was compacted. The summary above is a paraphrase; the ledger is the record.",
                       r.stdout)
        self.assertIn("re-read", r.stdout.lower())
        self.assertIn("checkpoint", r.stdout.lower())
        self.assertIn("This folder holds 1 project ", r.stdout)
        self.assertIn("app: 1 open ledger ·", r.stdout)

    def test_a_parent_with_no_child_projects_prints_nothing(self):
        (self.parent / "notes").mkdir()  # a plain directory, not a project
        r = self.run_at({"cwd": str(self.parent), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_a_folder_with_its_own_ledger_is_unchanged(self):
        (self.parent / "docs" / "proposals").mkdir(parents=True)
        (self.parent / "docs" / "proposals" / "19-x.json").write_text(json.dumps(minimal()))
        self.make_child("app", minimal())
        r = self.run_at({"cwd": str(self.parent), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("Proposal 19:", r.stdout)
        self.assertIn("run /warmup", r.stdout)
        self.assertNotIn("This folder holds", r.stdout)

    def test_control_characters_in_a_child_name_are_escaped(self):
        bad_name = "app\x07bad"
        self.make_child(bad_name, minimal())
        r = self.run_at({"cwd": str(self.parent), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotIn("\x07", r.stdout)
        self.assertIn("\\x07", r.stdout)

    def test_a_declared_project_with_no_open_ledger_is_still_listed(self):
        child = self.make_child("done-project", None)
        (child / ".common-rules.json").write_text("{}")
        r = self.run_at({"cwd": str(self.parent), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("done-project: 0 open ledgers ·", r.stdout)
        self.assertIn(f"/warmup --project {child}", r.stdout)

    def test_an_unreadable_sibling_does_not_hide_the_rest(self):
        """Round 2, item 1: a chmod 000 sibling raises PermissionError inside
        Path.is_file() -- that must not take the whole card down with it."""
        self.make_child("app", minimal())
        unreadable = self.parent / "locked"
        unreadable.mkdir()
        os.chmod(unreadable, 0)
        try:
            r = self.run_at({"cwd": str(self.parent), "source": "startup"})
        finally:
            os.chmod(unreadable, 0o755)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("app: 1 open ledger ·", r.stdout)
        self.assertIn(f"/warmup --project {self.parent / 'app'}", r.stdout)
        self.assertIn("This folder holds 1 project ", r.stdout)

    def test_resume_source_is_a_plain_list(self):
        self.make_child("app", minimal())
        r = self.run_at({"cwd": str(self.parent), "source": "resume"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("This folder holds 1 project ", r.stdout)
        self.assertIn("app: 1 open ledger ·", r.stdout)
        self.assertNotIn("compacted", r.stdout.lower())
        self.assertNotIn("Re-read that project's ledger", r.stdout)

    def test_clear_source_is_a_plain_list(self):
        self.make_child("app", minimal())
        r = self.run_at({"cwd": str(self.parent), "source": "clear"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("This folder holds 1 project ", r.stdout)
        self.assertNotIn("compacted", r.stdout.lower())
        self.assertNotIn("Re-read that project's ledger", r.stdout)

    def test_missing_source_is_a_plain_list(self):
        self.make_child("app", minimal())
        r = self.run_at({"cwd": str(self.parent)})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("This folder holds 1 project ", r.stdout)
        self.assertNotIn("compacted", r.stdout.lower())
        self.assertNotIn("Re-read that project's ledger", r.stdout)

    def test_more_than_ten_children_are_capped(self):
        """Round 2, item 3: a folder with many projects below it (the worst
        case -- every project on the machine) prints at most 10 line pairs,
        sorted by name, then a `+N more` line."""
        names = [f"proj{n:02d}" for n in range(12)]
        for name in names:
            self.make_child(name, minimal())
        r = self.run_at({"cwd": str(self.parent), "source": "startup"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("This folder holds 12 projects ", r.stdout)
        shown, hidden = sorted(names)[:10], sorted(names)[10:]
        self.assertEqual(2, len(hidden))
        for name in shown:
            self.assertIn(f"/warmup --project {self.parent / name}", r.stdout)
        for name in hidden:
            self.assertNotIn(f"/warmup --project {self.parent / name}", r.stdout)
        self.assertIn("+2 more -- /warmup --project <dir> for yours", r.stdout)

    def test_malformed_stdin_and_missing_cwd_exit_zero(self):
        r = self.run_hook_raw(raw_stdin="not json{{{")
        self.assertEqual(0, r.returncode, r.stderr)

    def run_hook_raw(self, raw_stdin: str):
        return subprocess.run([sys.executable, str(SESSIONSTART)], input=raw_stdin,
                              capture_output=True, text=True, cwd=str(self.parent), timeout=15, check=False)


class TestPostToolUseAgentHook(ScratchProject):
    """PostToolUse hook for the Agent/Task tool (proposal 20, V-05 / PC-01).
    Leads kept spawning agents whose briefs dropped the tier and model scope;
    this reminds the lead with the correct tag right after an untagged spawn,
    reading only the first non-blank line of the prompt. It never blocks --
    PostToolUse can only add context, never allow/deny/ask."""

    def agent_call(self, prompt: str, tool_name="Agent", cwd=None):
        payload = {"tool_name": tool_name, "tool_input": {"prompt": prompt}, "cwd": cwd or str(self.proj)}
        return self.run_hook(POSTTOOLUSE_AGENT, payload)

    def test_tagged_prompt_is_silent(self):
        r = self.agent_call("[ruflo · high · opus] W-02 render pass\n\nDo the render work.")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_tagged_prompt_accepts_hyphen_and_pipe_separators(self):
        for tag in ("[ruflo-high-opus]", "[ruflo | high | opus]", "[ ruflo · high · opus ]"):
            with self.subTest(tag=tag):
                r = self.agent_call(f"{tag} W-02 render pass")
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertEqual("", r.stdout.strip())

    def test_untagged_known_id_prints_reminder_with_that_rows_tag(self):
        r = self.agent_call("W-02 render pass, no tag on this one")
        self.assertEqual(0, r.returncode, r.stderr)
        out = json.loads(r.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual("PostToolUse", out["hookSpecificOutput"]["hookEventName"])
        self.assertIn("W-02", ctx)
        self.assertIn("[ruflo · high · opus]", ctx)

    def test_untagged_id_without_a_tag_field_builds_one_from_tier_and_model(self):
        built = minimal()
        built["items"][1].pop("tag", None)
        built["items"][1]["tier"] = "high"
        built["items"][1]["model"] = "opus"
        self.write_ledger(built)
        r = self.agent_call("W-02 render pass, no tag on this one")
        self.assertEqual(0, r.returncode, r.stderr)
        out = json.loads(r.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("W-02", ctx)
        self.assertIn("[ruflo · high · opus]", ctx)

    def test_untagged_unknown_id_is_silent(self):
        r = self.agent_call("Z-99 a task that is not in any ledger")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_untagged_with_no_id_at_all_is_silent(self):
        r = self.agent_call("Please go fix the flaky test.")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_task_tool_name_is_treated_like_agent(self):
        r = self.agent_call("W-02 render pass, no tag on this one", tool_name="Task")
        self.assertEqual(0, r.returncode, r.stderr)
        out = json.loads(r.stdout)
        self.assertIn("W-02", out["hookSpecificOutput"]["additionalContext"])

    def test_other_tool_names_are_silent(self):
        for name in ("Bash", "Read", "Edit", None):
            with self.subTest(tool_name=name):
                r = self.agent_call("W-02 render pass, no tag", tool_name=name)
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertEqual("", r.stdout.strip())

    def test_no_ledger_under_cwd_is_silent(self):
        no_ledger = Path(tempfile.mkdtemp())
        r = self.run_hook(POSTTOOLUSE_AGENT,
                           {"tool_name": "Agent", "tool_input": {"prompt": "W-02 render pass"}, "cwd": str(no_ledger)})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_garbage_stdin_is_silent_exit_zero(self):
        r = self.run_hook(POSTTOOLUSE_AGENT, None, cwd=str(self.proj), raw_stdin="not json{{{")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_missing_tool_input_or_prompt_is_silent(self):
        for payload in ({"tool_name": "Agent"}, {"tool_name": "Agent", "tool_input": {}},
                         {"tool_name": "Agent", "tool_input": {"prompt": 12345}}):
            with self.subTest(payload=payload):
                r = self.run_hook(POSTTOOLUSE_AGENT, payload, cwd=str(self.proj))
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertEqual("", r.stdout.strip())

    def test_never_exits_non_zero(self):
        # Belt and braces on top of the garbage-stdin case above: the hook must
        # never fail the tool call it is observing.
        r = self.run_hook(POSTTOOLUSE_AGENT, None, cwd=str(self.proj), raw_stdin="")
        self.assertEqual(0, r.returncode, r.stderr)


if __name__ == "__main__":
    unittest.main()
