"""bin/ruflo-item -- the mandatory Ruflo loop around one plan item (proposal
20, D11; ledger row V-06).

Every case here drives a *fake* Ruflo on PATH -- a small POSIX-sh script that
appends each call's cwd and argv to a log file, and can be told to fail on a
call matching a substring via $FAKE_RUFLO_FAIL. The real CLI is never run:
tests assert call order and cwd from the fake's log, never anything about
Ruflo's own subcommands, which is why the exact flags ruflo-item passes (not
the real CLI's) are what these tests pin.

Round 2 additions (report-only reviewer, round 2 of 2, on 950f59e): $RUFLO as
a full command line split with shlex; --namespace / $RUFLO_NAMESPACE /
project-dir-name resolution, printed on every run; `start` also stores
item:<ID>:start; SIGTERM/SIGHUP handling that terminates the gate's process
group before the daemon stops; the gate's output streams live rather than
being captured; `done` dispatches the testgaps worker, best-effort, after its
store.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUFLO_ITEM = ROOT / "bin" / "ruflo-item"

FAKE_RUFLO = """#!/bin/sh
# Appends this call's cwd and argv (tab-separated) as one line to
# $FAKE_RUFLO_LOG, then exits 0 -- unless $FAKE_RUFLO_FAIL is set and is a
# substring of this call's argv, in which case it exits 7.
{
  printf '%s\\t' "$PWD"
  for a in "$@"; do
    printf '%s\\t' "$a"
  done
  printf '\\n'
} >> "$FAKE_RUFLO_LOG"
if [ -n "${FAKE_RUFLO_FAIL:-}" ]; then
  if printf '%s' "$*" | grep -qF "$FAKE_RUFLO_FAIL"; then
    exit 7
  fi
fi
exit 0
"""

FAKE_NPX = """#!/bin/sh
# A decoy npx: if this is ever called, something reached for it that
# shouldn't have. Logs to $FAKE_NPX_LOG so a test can assert it stayed empty.
printf '%s\\n' "$*" >> "$FAKE_NPX_LOG"
exit 0
"""


def flag(argv: list[str], name: str) -> str:
    return argv[argv.index(name) + 1]


class RufloItemCase(unittest.TestCase):
    """A scratch git project, a fake `claude-flow` on PATH, and a helper to
    run `bin/ruflo-item` against them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)

        self.proj = base / "proj"
        self.proj.mkdir()
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)

        self.fake_bin_dir = base / "fakebin"
        self.fake_bin_dir.mkdir()
        fake = self.fake_bin_dir / "claude-flow"
        fake.write_text(FAKE_RUFLO)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        self.log = base / "ruflo.log"

        self.env = dict(os.environ)
        self.env["PATH"] = f"{self.fake_bin_dir}:{self.env.get('PATH', '')}"
        self.env["FAKE_RUFLO_LOG"] = str(self.log)
        self.env.pop("RUFLO", None)
        self.env.pop("RUFLO_NAMESPACE", None)
        self.env.pop("FAKE_RUFLO_FAIL", None)

    def tearDown(self):
        self.tmp.cleanup()

    # -- helpers ----------------------------------------------------------

    def run_item(self, *args, cwd=None, env=None, project=None, namespace=None):
        project = self.proj if project is None else project
        full_args = [sys.executable, str(RUFLO_ITEM), "--project", str(project)]
        if namespace is not None:
            full_args += ["--namespace", namespace]
        full_args += list(args)
        return subprocess.run(full_args, cwd=str(cwd or self.proj),
                               capture_output=True, text=True, env=env or self.env)

    def log_lines(self) -> list[list[str]]:
        """Each logged call as [cwd, arg0, arg1, ...]."""
        if not self.log.exists():
            return []
        out = []
        for line in self.log.read_text().splitlines():
            if line == "":
                continue
            out.append(line.split("\t")[:-1])  # drop the trailing empty field from the final \t
        return out

    def declare_gate(self, merge_cmd: str):
        (self.proj / ".common-rules.json").write_text(json.dumps({"gates": {"merge": merge_cmd}}))


class TestBinaryResolution(RufloItemCase):

    def test_missing_binary_exits_2_with_message(self):
        env = dict(self.env)
        env["PATH"] = str(self.fake_bin_dir.parent)  # no claude-flow, no ruflo
        env.pop("RUFLO", None)
        r = self.run_item("recall", "keywords", env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("no Ruflo binary found", r.stdout + r.stderr)
        self.assertIn("RUFLO=", r.stdout + r.stderr, "the message must name the fix")
        self.assertFalse(self.log.exists(), "no binary means no daemon stop call either")

    def test_ruflo_env_var_wins_over_path(self):
        # A second fake, not on PATH, named by $RUFLO -- must be the one called.
        other_log = self.log.parent / "other.log"
        other = self.log.parent / "other-ruflo"
        other.write_text(FAKE_RUFLO)
        other.chmod(other.stat().st_mode | stat.S_IEXEC)
        env = dict(self.env)
        env["RUFLO"] = str(other)
        env["FAKE_RUFLO_LOG"] = str(other_log)
        self.declare_gate("true")
        r = self.run_item("start", "V-06", "wire it up", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.log.exists(), "the PATH fake must not have been called")
        self.assertTrue(other_log.exists(), "$RUFLO must win over PATH")

    def test_ruflo_env_var_is_a_command_line_split_with_shlex(self):
        """The app's own wrapper calls `npx -y ruflo@latest` -- $RUFLO must
        support that shape, with every extra word carried on every call."""
        fake = str(self.fake_bin_dir / "claude-flow")
        env = dict(self.env)
        env["RUFLO"] = f"{fake} --extra-flag"
        r = self.run_item("recall", "keywords", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertTrue(calls, "no calls were logged")
        for call in calls:
            self.assertEqual(call[0], "--extra-flag", call)

    def test_ruflo_env_var_naming_a_nonexistent_word_refuses_cleanly(self):
        """Previously: a traceback and exit 1. Now: a named refusal, exit 2,
        no daemon stop attempted (there is nothing proven to call it with)."""
        env = dict(self.env)
        env["RUFLO"] = "/no/such/ruflo-binary -y ruflo@latest"
        r = self.run_item("recall", "keywords", env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("/no/such/ruflo-binary", r.stdout + r.stderr)
        self.assertIn("is not an executable", r.stdout + r.stderr)
        self.assertFalse(self.log.exists())

    def test_never_shells_out_to_npx_on_its_own_initiative(self):
        npx_log = Path(self.tmp.name) / "npx.log"
        npx = self.fake_bin_dir / "npx"
        npx.write_text(FAKE_NPX)
        npx.chmod(npx.stat().st_mode | stat.S_IEXEC)
        env = dict(self.env)
        env["FAKE_NPX_LOG"] = str(npx_log)
        # claude-flow is also on PATH (from setUp) and must be preferred.
        r = self.run_item("recall", "keywords", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(npx_log.exists(),
                          "ruflo-item must never invoke npx unless $RUFLO names it")


class TestNamespace(RufloItemCase):

    def test_flag_wins(self):
        r = self.run_item("recall", "keywords", namespace="from-flag")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        for call in calls[:-1]:  # every call but daemon stop carries --namespace
            self.assertEqual(flag(call, "--namespace"), "from-flag")
        self.assertIn("namespace: from-flag", r.stdout)

    def test_env_var_used_when_no_flag(self):
        env = dict(self.env)
        env["RUFLO_NAMESPACE"] = "from-env"
        r = self.run_item("recall", "keywords", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        for call in calls[:-1]:
            self.assertEqual(flag(call, "--namespace"), "from-env")
        self.assertIn("namespace: from-env", r.stdout)

    def test_defaults_to_project_directory_name(self):
        r = self.run_item("recall", "keywords")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        for call in calls[:-1]:
            self.assertEqual(flag(call, "--namespace"), "proj")
        self.assertIn("namespace: proj", r.stdout)

    def test_flag_wins_over_env_var(self):
        env = dict(self.env)
        env["RUFLO_NAMESPACE"] = "from-env"
        r = self.run_item("recall", "keywords", env=env, namespace="from-flag")
        calls = [c[1:] for c in self.log_lines()]
        for call in calls[:-1]:
            self.assertEqual(flag(call, "--namespace"), "from-flag")


class TestStart(RufloItemCase):

    def test_call_order_is_pretask_search_route_then_store(self):
        r = self.run_item("start", "V-06", "bin/ruflo-item (D11)")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(len(calls), 5, calls)
        self.assertEqual(calls[0], ["hooks", "pre-task", "--description", "V-06: bin/ruflo-item (D11)"])
        self.assertEqual(calls[1], ["memory", "search", "--query", "V-06", "--namespace", "proj"])
        self.assertEqual(calls[2], ["hooks", "route", "--task", "V-06: bin/ruflo-item (D11)"])
        self.assertEqual(calls[3][:4], ["memory", "store", "--namespace", "proj"])
        self.assertEqual(flag(calls[3], "--key"), "item:V-06:start")
        self.assertIn("bin/ruflo-item (D11)", flag(calls[3], "--value"))
        self.assertEqual(calls[4], ["daemon", "stop"])

    def test_prints_what_it_recorded(self):
        r = self.run_item("start", "V-06", "bin/ruflo-item (D11)")
        self.assertIn("V-06", r.stdout)
        self.assertIn("pre-task", r.stdout)
        self.assertIn("route", r.stdout)
        self.assertIn("item:V-06:start", r.stdout)

    def test_cwd_for_every_call_is_the_project_root(self):
        self.run_item("start", "V-06", "text")
        for cwd, *_ in self.log_lines():
            self.assertEqual(cwd, str(self.proj.resolve()))

    def test_a_failing_pretask_does_not_stop_the_rest_of_start(self):
        env = dict(self.env)
        env["FAKE_RUFLO_FAIL"] = "pre-task"
        r = self.run_item("start", "V-06", "text", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual([c[0:2] for c in calls],
                          [["hooks", "pre-task"], ["memory", "search"],
                           ["hooks", "route"], ["memory", "store"], ["daemon", "stop"]])


class TestDone(RufloItemCase):

    def test_green_gate_runs_post_task_store_then_testgaps(self):
        self.declare_gate("true")
        r = self.run_item("done", "V-06", "shipped, 12 OK")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls[0], ["hooks", "post-task", "--task-id", "V-06",
                                     "--success", "true", "--store-results", "true"])
        self.assertEqual(calls[1][:4], ["memory", "store", "--namespace", "proj"])
        self.assertEqual(flag(calls[1], "--key"), "item:V-06:done")
        self.assertEqual(calls[2], ["hooks", "worker", "dispatch", "--trigger", "testgaps"])
        self.assertEqual(calls[-1], ["daemon", "stop"])
        self.assertEqual(len(calls), 4)

    def test_failing_gate_skips_post_task_and_exits_nonzero(self):
        self.declare_gate("exit 3")
        r = self.run_item("done", "V-06", "shipped")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.log_lines()
        self.assertEqual([c[1:] for c in calls], [["daemon", "stop"]],
                          "a failing gate must call nothing but daemon stop")
        self.assertIn("gate failed", r.stdout + r.stderr)

    def test_a_refusal_from_a_broken_declaration_is_treated_as_failure(self):
        (self.proj / ".common-rules.json").write_text("{not valid json")
        r = self.run_item("done", "V-06", "shipped")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls, [["daemon", "stop"]])
        self.assertIn("not valid JSON", r.stdout + r.stderr)

    def test_a_declared_but_unusable_gate_refuses_rather_than_falling_back(self):
        (self.proj / ".common-rules.json").write_text(json.dumps({"gates": {"merge": 3}}))
        (self.proj / ".common-rules-test").write_text("true\n")
        r = self.run_item("done", "V-06", "shipped")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls, [["daemon", "stop"]])
        self.assertIn("is not a string", r.stdout + r.stderr)

    def test_no_gate_declared_and_none_guessable_refuses_like_land(self):
        # An empty project: no .common-rules.json, no .common-rules-test, no
        # tests/ dir, no package.json -- test_command() answers "".
        r = self.run_item("done", "V-06", "shipped")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls, [["daemon", "stop"]],
                          "no gate means no post-task call, but the daemon still stops")
        self.assertIn("no merge gate declared", r.stdout + r.stderr)

    def test_daemon_stop_is_last_and_store_plus_testgaps_still_run_after_a_failed_post_task(self):
        self.declare_gate("true")
        env = dict(self.env)
        env["FAKE_RUFLO_FAIL"] = "post-task"
        r = self.run_item("done", "V-06", "shipped", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls[0][:2], ["hooks", "post-task"])
        self.assertEqual(calls[1][:2], ["memory", "store"])
        self.assertEqual(calls[2], ["hooks", "worker", "dispatch", "--trigger", "testgaps"])
        self.assertEqual(calls[3], ["daemon", "stop"])
        self.assertEqual(len(calls), 4)

    def test_gate_runs_with_project_root_as_cwd(self):
        self.declare_gate(f"pwd > {self.proj}/gate-cwd.txt")
        self.run_item("done", "V-06", "shipped")
        seen = (self.proj / "gate-cwd.txt").read_text().strip()
        self.assertEqual(seen, str(self.proj.resolve()))

    def test_gate_output_streams_live_not_captured(self):
        self.declare_gate("echo GATE-MARKER-OUTPUT")
        r = self.run_item("done", "V-06", "shipped")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("GATE-MARKER-OUTPUT", r.stdout)


class TestNote(RufloItemCase):

    def test_stores_under_the_items_key_with_a_real_timestamp(self):
        before = int(time.time())
        r = self.run_item("note", "V-06", "chose epoch keys, matching the app wrapper")
        after = int(time.time())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(len(calls), 2)  # memory store, then daemon stop
        store = calls[0]
        self.assertEqual(store[:4], ["memory", "store", "--namespace", "proj"])
        key = flag(store, "--key")
        self.assertTrue(key.startswith("item:V-06:note:"), key)
        ts = int(key.rsplit(":", 1)[-1])
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after + 1)
        self.assertIn("chose epoch keys", flag(store, "--value"))


class TestRecall(RufloItemCase):

    def test_lists_keys_before_searching(self):
        r = self.run_item("recall", "ruflo item wrapper")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls, [
            ["memory", "list", "--namespace", "proj"],
            ["memory", "search", "--query", "ruflo item wrapper", "--namespace", "proj"],
            ["daemon", "stop"],
        ])


class TestDaemonStopEveryExit(RufloItemCase):

    def test_start_stops_the_daemon_even_when_every_call_fails(self):
        env = dict(self.env)
        env["FAKE_RUFLO_FAIL"] = "hooks"  # matches pre-task and route, not memory store
        r = self.run_item("start", "V-06", "text", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls[-1], ["daemon", "stop"])

    def test_recall_stops_the_daemon_even_when_every_call_fails(self):
        env = dict(self.env)
        env["FAKE_RUFLO_FAIL"] = "memory"
        r = self.run_item("recall", "keywords", env=env)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls[-1], ["daemon", "stop"])


class TestSignals(RufloItemCase):
    """SIGTERM/SIGHUP during a running gate: the gate's whole process group
    must die, and daemon stop must still be the last call, before ruflo-item
    exits 128+signum."""

    def _run_and_signal(self, sig: signal.Signals, expected_exit: int):
        pidfile = self.proj / "gate.pid"
        # `exec` is deliberately avoided: the pidfile write must land before
        # the long-running child starts, and both share the process group
        # start_new_session gives the whole `bash -c` invocation.
        self.declare_gate(f"echo $$ > {pidfile} && sleep 30")
        full_args = [sys.executable, str(RUFLO_ITEM), "--project", str(self.proj), "done", "V-06", "text"]
        proc = subprocess.Popen(full_args, cwd=str(self.proj), env=self.env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(200):
                if pidfile.exists() and pidfile.read_text().strip():
                    break
                time.sleep(0.05)
            else:
                proc.kill()
                self.fail("gate never started")
            gate_pid = int(pidfile.read_text().strip())

            proc.send_signal(sig)
            stdout, stderr = proc.communicate(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

        self.assertEqual(proc.returncode, expected_exit, stdout + stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls[-1], ["daemon", "stop"], calls)

        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                os.kill(gate_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            self.fail(f"gate process {gate_pid} survived ruflo-item's exit")

    def test_sigterm_kills_the_gate_group_before_daemon_stop_and_exits_143(self):
        self._run_and_signal(signal.SIGTERM, 143)

    def test_sighup_kills_the_gate_group_before_daemon_stop_and_exits_129(self):
        self._run_and_signal(signal.SIGHUP, 129)


class TestProjectResolution(RufloItemCase):

    def test_default_project_is_git_toplevel_of_cwd(self):
        sub = self.proj / "nested" / "dir"
        sub.mkdir(parents=True)
        full_args = [sys.executable, str(RUFLO_ITEM), "recall", "keywords"]
        r = subprocess.run(full_args, cwd=str(sub), capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.log_lines()
        self.assertTrue(calls, "no calls were logged")
        for cwd, *_ in calls:
            self.assertEqual(cwd, str(self.proj.resolve()))


if __name__ == "__main__":
    unittest.main()
