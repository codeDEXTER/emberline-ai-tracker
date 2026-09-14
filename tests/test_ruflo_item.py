"""bin/ruflo-item -- the mandatory Ruflo loop around one plan item (proposal
20, D11; ledger row V-06).

Every case here drives a *fake* Ruflo on PATH -- a small POSIX-sh script that
appends each call's cwd and argv to a log file, and can be told to fail on a
call matching a substring via $FAKE_RUFLO_FAIL. The real CLI is never run:
tests assert call order and cwd from the fake's log, never anything about
Ruflo's own subcommands, which is why the exact flags ruflo-item passes (not
the real CLI's) are what these tests pin.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import os
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
        self.env.pop("FAKE_RUFLO_FAIL", None)

    def tearDown(self):
        self.tmp.cleanup()

    # -- helpers ----------------------------------------------------------

    def run_item(self, *args, cwd=None, env=None):
        full_args = [sys.executable, str(RUFLO_ITEM), *args]
        if "--project" not in args:
            full_args = [sys.executable, str(RUFLO_ITEM), "--project", str(self.proj), *args]
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

    def test_never_shells_out_to_npx(self):
        self.run_item("recall", "keywords")
        # A behavioural check would require intercepting npx too, which is
        # exactly the tool this rule says never to invoke. Instead: no
        # quoted "npx"/'npx' literal exists anywhere in the source -- the
        # word appears only in prose explaining why not (asserted below).
        src = RUFLO_ITEM.read_text()
        self.assertNotIn('"npx"', src)
        self.assertNotIn("'npx'", src)
        prose_only = [ln for ln in src.splitlines() if "npx" in ln]
        self.assertTrue(prose_only)
        self.assertTrue(all(ln.strip().startswith(("#", '"""')) or ln.strip().startswith("on PATH")
                             or "`npx`" in ln for ln in prose_only),
                         prose_only)


class TestStart(RufloItemCase):

    def test_call_order_is_pretask_then_search_then_route(self):
        r = self.run_item("start", "V-06", "bin/ruflo-item (D11)")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]  # drop cwd column
        self.assertEqual(calls, [
            ["hooks", "pre-task", "--description", "V-06: bin/ruflo-item (D11)"],
            ["memory", "search", "--query", "V-06", "--namespace", "proj"],
            ["hooks", "route", "--task", "V-06: bin/ruflo-item (D11)"],
            ["daemon", "stop"],
        ])

    def test_prints_what_it_recorded(self):
        r = self.run_item("start", "V-06", "bin/ruflo-item (D11)")
        self.assertIn("V-06", r.stdout)
        self.assertIn("pre-task", r.stdout)
        self.assertIn("route", r.stdout)

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
                           ["hooks", "route"], ["daemon", "stop"]])


class TestDone(RufloItemCase):

    def test_green_gate_runs_before_post_task_and_store(self):
        self.declare_gate("true")
        r = self.run_item("done", "V-06", "shipped, 12 OK")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls[0], ["hooks", "post-task", "--task-id", "V-06",
                                     "--success", "true", "--store-results", "true"])
        self.assertEqual(calls[1][:4], ["memory", "store", "--namespace", "proj"])
        self.assertIn("item:V-06:done", " ".join(calls[1]))
        self.assertEqual(calls[-1], ["daemon", "stop"])

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

    def test_daemon_stop_is_last_even_when_a_call_fails_after_a_green_gate(self):
        self.declare_gate("true")
        env = dict(self.env)
        env["FAKE_RUFLO_FAIL"] = "post-task"
        r = self.run_item("done", "V-06", "shipped", env=env)
        calls = [c[1:] for c in self.log_lines()]
        self.assertEqual(calls[-1], ["daemon", "stop"])
        self.assertEqual(calls[0][:2], ["hooks", "post-task"])

    def test_gate_runs_with_project_root_as_cwd(self):
        self.declare_gate(f"pwd > {self.proj}/gate-cwd.txt")
        self.run_item("done", "V-06", "shipped")
        seen = (self.proj / "gate-cwd.txt").read_text().strip()
        self.assertEqual(seen, str(self.proj.resolve()))


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
        key_i = store.index("--key") + 1
        key = store[key_i]
        self.assertTrue(key.startswith("item:V-06:note:"), key)
        ts = int(key.rsplit(":", 1)[-1])
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after + 1)
        value_i = store.index("--value") + 1
        self.assertIn("chose epoch keys", store[value_i])


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
        env["FAKE_RUFLO_FAIL"] = "hooks"  # matches both pre-task and route
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
