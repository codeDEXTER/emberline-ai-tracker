"""bin/tracker sync -- GitHub issues mirror the ledger one way (proposal 19, W-04).

Every `gh` call goes through the module-level `run_gh`, so these tests never
touch the network or the real repository -- they replace `run_gh` with a fake
that records every call and answers from a small script.

Run:  python3 -m unittest discover -s tests -p 'test_tracker_sync.py' -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import sync  # noqa: E402


def make_ledger(**over):
    d = {
        "proposal": 99,
        "title": "t",
        "status": "accepted",
        "phases": [{"id": "W", "name": "build"}],
        "items": [
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "creates an issue",
             "status": "in progress", "tier": "medium", "issue": None, "log": []},
            {"id": "W-02", "phase": "W", "cx": "C3", "title": "closes an issue",
             "status": "done", "tier": "high", "issue": 50,
             "log": [{"at": "2026-09-13T20:00:00+02:00", "event": "merged", "by": "lead",
                       "evidence": "commit abc123"}]},
            {"id": "W-03", "phase": "W", "cx": "C2", "title": "issue vanished",
             "status": "blocked", "tier": "medium", "issue": 51, "log": []},
            {"id": "W-04", "phase": "W", "cx": "C2", "title": "issue closed early",
             "status": "in progress", "tier": "medium", "issue": 52, "log": []},
            {"id": "W-05", "phase": "W", "cx": "C2", "title": "not started, no issue",
             "status": "not started", "tier": "medium", "issue": None, "log": []},
        ],
        "asks": [],
    }
    d.update(over)
    return d


ISSUE_LIST_JSON = json.dumps([
    {"number": 50, "state": "OPEN", "title": "W-02 closes an issue"},
    {"number": 52, "state": "CLOSED", "title": "W-04 issue closed early"},
])


def write_ledger(tmp: str, data: dict) -> Path:
    p = Path(tmp) / "99-t.json"
    p.write_text(json.dumps(data, indent=2))
    return p


class FakeGh:
    """Records every call; answers `issue list` and `issue create`."""

    def __init__(self, list_json=ISSUE_LIST_JSON, fail_on=None, created_number=145):
        self.calls: list[list[str]] = []
        self.list_json = list_json
        self.fail_on = fail_on  # a callable(args) -> bool
        self.created_number = created_number

    def __call__(self, args: list[str]) -> str:
        self.calls.append(list(args))
        if self.fail_on and self.fail_on(args):
            raise subprocess.CalledProcessError(1, ["gh", *args], output="boom")
        if args[:2] == ["issue", "list"]:
            return self.list_json
        if args[:2] == ["issue", "create"]:
            return f"https://github.com/o/r/issues/{self.created_number}\n"
        return ""

    def calls_matching(self, *prefix):
        return [c for c in self.calls if c[:len(prefix)] == list(prefix)]


class TestCreateAndWriteback(unittest.TestCase):

    def test_creates_issue_and_writes_back_byte_minimally(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_ledger()
            path = write_ledger(tmp, data)
            original_text = path.read_text()
            fake = FakeGh(created_number=145)
            with mock.patch.object(sync, "run_gh", fake):
                rc = sync.main([str(path)])
            # created W-01, closed W-02 (done, issue open), drift for W-03 and W-04
            self.assertEqual(1, rc, "drift was reported so exit code is 1")
            creates = fake.calls_matching("issue", "create")
            self.assertEqual(1, len(creates))
            self.assertIn("W-01 creates an issue", creates[0])
            new_text = path.read_text()
            expected = original_text.replace(
                '"issue": null', '"issue": 145', 1
            )
            self.assertEqual(expected, new_text,
                              "only W-01's `\"issue\": null` should change; "
                              "W-05's must stay null and every other byte identical")
            # W-05's null must still be present (untouched)
            self.assertIn('"id": "W-05"', new_text)
            self.assertEqual(1, new_text.count('"issue": null'))

    def test_label_create_called_once_per_distinct_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(tmp, make_ledger())
            fake = FakeGh()
            with mock.patch.object(sync, "run_gh", fake):
                sync.main([str(path)])
            label_calls = fake.calls_matching("label", "create")
            names = [c[2] for c in label_calls]
            self.assertEqual(sorted(names), sorted(set(names)), "no label created twice")
            self.assertIn("proposal:99", names)
            self.assertIn("tier:medium", names)
            self.assertIn("tier:high", names)
            for c in label_calls:
                self.assertIn("--force", c)


class TestClose(unittest.TestCase):

    def test_closes_done_item_with_open_issue_and_a_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(tmp, make_ledger())
            fake = FakeGh()
            with mock.patch.object(sync, "run_gh", fake):
                sync.main([str(path)])
            closes = fake.calls_matching("issue", "close")
            self.assertEqual(1, len(closes))
            call = closes[0]
            self.assertEqual("50", call[2])
            self.assertIn("--comment", call)
            comment = call[call.index("--comment") + 1]
            self.assertIn("W-02", comment)
            self.assertIn("done", comment)
            self.assertIn(str(path), comment)
            self.assertIn("commit abc123", comment, "names the last log entry's evidence")


class TestDrift(unittest.TestCase):

    def test_both_drift_directions_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(tmp, make_ledger())
            fake = FakeGh()
            with mock.patch.object(sync, "run_gh", fake):
                with mock.patch("builtins.print") as mock_print:
                    rc = sync.main([str(path)])
            self.assertEqual(1, rc)
            printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
            self.assertIn("DRIFT W-03 #51: no such issue with label proposal:99", printed)
            self.assertIn("DRIFT W-04 #52: issue closed, ledger says in progress", printed)
            # never reopened
            self.assertEqual(0, len(fake.calls_matching("issue", "reopen")))

    def test_summary_line_reports_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(tmp, make_ledger())
            fake = FakeGh()
            with mock.patch.object(sync, "run_gh", fake):
                with mock.patch("builtins.print") as mock_print:
                    sync.main([str(path)])
            printed = [str(c.args[0]) for c in mock_print.call_args_list if c.args]
            summary = [line for line in printed if line.startswith(f"sync {path}:")]
            self.assertEqual(1, len(summary))
            self.assertEqual(f"sync {path}: created 1 · closed 1 · drift 2", summary[0])


class TestDryRun(unittest.TestCase):

    def test_dry_run_makes_no_mutating_calls_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(tmp, make_ledger())
            original_text = path.read_text()
            fake = FakeGh()
            with mock.patch.object(sync, "run_gh", fake):
                with mock.patch("builtins.print") as mock_print:
                    rc = sync.main([str(path), "--dry-run"])
            self.assertEqual(1, rc, "drift is still reported in a dry run")
            self.assertEqual(0, len(fake.calls_matching("issue", "create")))
            self.assertEqual(0, len(fake.calls_matching("issue", "close")))
            self.assertEqual(0, len(fake.calls_matching("label", "create")))
            self.assertEqual(original_text, path.read_text(), "dry run never writes the ledger")
            printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
            self.assertIn("would create", printed)
            self.assertIn("would close", printed)


class TestLimitAndRepo(unittest.TestCase):

    def test_list_calls_always_pass_limit_1000(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(tmp, make_ledger())
            fake = FakeGh()
            with mock.patch.object(sync, "run_gh", fake):
                sync.main([str(path)])
            list_calls = fake.calls_matching("issue", "list")
            self.assertEqual(1, len(list_calls))
            call = list_calls[0]
            self.assertIn("--limit", call)
            self.assertEqual("1000", call[call.index("--limit") + 1])

    def test_repo_is_threaded_through_every_gh_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(tmp, make_ledger())
            fake = FakeGh()
            with mock.patch.object(sync, "run_gh", fake):
                sync.main([str(path), "--repo", "acme/widgets"])
            self.assertTrue(fake.calls, "expected at least one gh call")
            for call in fake.calls:
                self.assertIn("--repo", call)
                self.assertEqual("acme/widgets", call[call.index("--repo") + 1])


class TestFailureModes(unittest.TestCase):

    def test_invalid_ledger_exits_2_and_calls_no_gh(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = make_ledger()
            bad["items"][0]["status"] = "wip"  # not in STATUSES
            path = write_ledger(tmp, bad)
            fake = FakeGh()
            with mock.patch.object(sync, "run_gh", fake):
                rc = sync.main([str(path)])
            self.assertEqual(2, rc)
            self.assertEqual([], fake.calls, "an invalid ledger must never reach gh")

    def test_unreadable_ledger_exits_2(self):
        rc = sync.main(["/no/such/ledger.json"])
        self.assertEqual(2, rc)

    def test_malformed_json_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "99-broken.json"
            path.write_text("{nope")
            rc = sync.main([str(path)])
            self.assertEqual(2, rc)

    def test_gh_failure_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(tmp, make_ledger())
            fake = FakeGh(fail_on=lambda args: args[:2] == ["issue", "list"])
            with mock.patch.object(sync, "run_gh", fake):
                rc = sync.main([str(path)])
            self.assertEqual(2, rc)

    def test_writeback_pattern_missing_exits_1_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_ledger()
            # Sabotage: give W-01 an already-set issue number so its `"issue": null`
            # text is gone, but keep it eligible for "create" by clearing status
            # rules would not normally allow this; instead we directly corrupt the
            # text after serialising so the span search fails to find the pattern.
            path = write_ledger(tmp, data)
            text = path.read_text()
            # Remove the literal `"issue": null` for W-01 by tightening the spacing,
            # so the exact-match search fails inside that item's span.
            corrupted = text.replace('"issue": null', '"issue":null', 1)
            path.write_text(corrupted)
            original_text = path.read_text()
            fake = FakeGh(created_number=999)
            with mock.patch.object(sync, "run_gh", fake):
                rc = sync.main([str(path)])
            self.assertEqual(1, rc)
            self.assertEqual(original_text, path.read_text(), "a failed write-back must not touch the file")


class TestCLIExitCodeIsSyncedWhenNothingToDo(unittest.TestCase):

    def test_fully_in_sync_ledger_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_ledger(items=[
                {"id": "W-01", "phase": "W", "cx": "C2", "title": "already open",
                 "status": "in progress", "tier": "medium", "issue": 50, "log": []},
            ])
            path = write_ledger(tmp, data)
            fake = FakeGh(list_json=json.dumps([{"number": 50, "state": "OPEN", "title": "x"}]))
            with mock.patch.object(sync, "run_gh", fake):
                rc = sync.main([str(path)])
            self.assertEqual(0, rc)
            self.assertEqual(0, len(fake.calls_matching("issue", "create")))
            self.assertEqual(0, len(fake.calls_matching("issue", "close")))


if __name__ == "__main__":
    unittest.main()
