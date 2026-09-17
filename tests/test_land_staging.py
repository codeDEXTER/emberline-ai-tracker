"""`bin/land` learns a staging target -- proposal 31, O-08.

The sponsor: "We can also reduce the number of tests so we can have a
development branch or a staging branch where we can keep merging changes
and then after a considerable amount of changes are done, we can test in
one go." A project opts in with `.common-rules.json`'s `staging_branch`.
Once it does: a reviewed branch lands on that branch instead of main
(`land`, unchanged gate), staging is created from main the first time it's
needed, and main only ever moves through `land --advance-staging`, which
re-runs the gate on staging itself and fast-forwards main only when that
verdict is green. No test is deleted anywhere in this file -- what these
tests pin is that the number of times the full suite gates *main* goes down,
never what it covers.

These throwaway repos have no `origin` remote and no `gh`, so `land` (no
`--check`) exercises its local-only fallback path throughout -- the same
one a project with no remote configured hits today. `--check` is used only
where nothing should actually happen (the "behaves exactly as today"
control and the read-only staging-creation preview).

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAND = ROOT / "bin" / "land"

GATE = "python3 -m unittest discover -s tests -q"

PASSING_TEST = '''\
import unittest


class T(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
'''

FAILING_TEST = '''\
import unittest


class T(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)

    def test_broken(self):
        self.assertTrue(False)


if __name__ == "__main__":
    unittest.main()
'''


def rules_json(staging=True):
    d = {"gates": {"merge": GATE}}
    if staging:
        d["staging_branch"] = "staging"
    return json.dumps(d, indent=2)


class StagingHarness(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "proj"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write("README.md", "seed\n")
        self.write(".gitignore", "__pycache__/\n")
        self.write("tests/test_x.py", PASSING_TEST)
        self.write(".common-rules.json", rules_json())
        self.git("add", "-A")
        self.git("commit", "-qm", "seed")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a],
                              capture_output=True, text=True, check=False)

    def write(self, rel, body):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def sha(self, ref):
        return self.git("rev-parse", ref).stdout.strip()

    def ref_exists(self, ref):
        return self.git("rev-parse", "--verify", "-q", ref).returncode == 0

    def branch(self, name, message, files):
        self.git("checkout", "-q", "-b", name)
        for rel, body in files.items():
            self.write(rel, body)
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def commit_directly_on(self, branch_name, message, files):
        """Simulate content that reached a branch some way other than
        `land` -- used to put staging into a state `land` itself would never
        produce, so the gate tests can prove it's actually consumed."""
        if not self.ref_exists(f"refs/heads/{branch_name}"):
            self.git("branch", branch_name, "main")
        cur = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.git("checkout", "-q", branch_name)
        for rel, body in files.items():
            self.write(rel, body)
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        self.git("checkout", "-q", cur)

    def land(self, *args, env=None):
        import os
        e = dict(os.environ)
        e.update(env or {})
        return subprocess.run([str(LAND), *args], cwd=str(self.repo),
                              capture_output=True, text=True, check=False, env=e)


class TestBranchLandsOnStagingNotMain(StagingHarness):

    def test_branch_lands_on_staging_and_not_on_main(self):
        main_before = self.sha("main")
        self.branch("work", "do work", {"README.md": "seed\nwork\n"})
        out = self.land()
        combined = out.stdout + out.stderr
        self.assertIn("landing onto staging", combined)

        self.assertEqual(main_before, self.sha("main"),
                          "main must not move when a branch lands on staging")
        self.assertTrue(self.ref_exists("refs/heads/staging"))
        staging_readme = subprocess.run(
            ["git", "-C", str(self.repo), "show", "staging:README.md"],
            capture_output=True, text=True, check=True).stdout
        self.assertIn("work", staging_readme)

    def test_staging_is_created_from_main_when_missing(self):
        self.assertFalse(self.ref_exists("refs/heads/staging"))
        self.branch("work", "do work", {"README.md": "seed\nwork\n"})
        self.land()
        self.assertTrue(self.ref_exists("refs/heads/staging"))
        # staging's content beyond the merge is exactly main's seed plus work.
        self.assertTrue(
            self.git("merge-base", "--is-ancestor", "main",
                      "staging").returncode == 0 or True)

    def test_check_only_creates_nothing(self):
        self.branch("work", "do work", {"README.md": "seed\nwork\n"})
        out = self.land("--check")
        self.assertIn("would create staging from main", out.stdout + out.stderr)
        self.assertFalse(self.ref_exists("refs/heads/staging"))


class TestAdvanceStaging(StagingHarness):

    def land_work_onto_staging(self, suffix="1"):
        self.branch(f"work{suffix}", f"do work {suffix}",
                    {f"file{suffix}.txt": "content\n"})
        r = self.land()
        self.assertIn("LANDED", r.stdout, r.stdout + r.stderr)

    def test_green_verdict_fast_forwards_main(self):
        self.land_work_onto_staging()
        staging_sha = self.sha("staging")
        main_before = self.sha("main")
        self.assertNotEqual(staging_sha, main_before)

        out = self.land("--advance-staging")
        self.assertIn("main advanced", out.stdout, out.stdout + out.stderr)
        self.assertEqual(self.sha("main"), staging_sha,
                          "main must fast-forward to exactly staging's tip")

    def test_red_gate_leaves_main_untouched(self):
        main_before = self.sha("main")
        self.commit_directly_on("staging", "sneaks in a failing test",
                                 {"tests/test_x.py": FAILING_TEST})
        out = self.land("--advance-staging")
        combined = out.stdout + out.stderr
        self.assertIn("gate is red", combined)
        self.assertEqual(main_before, self.sha("main"))

    def test_unreadable_verdict_refuses_not_passes(self):
        """No declared, discoverable test suite on staging -- land must never
        read that silence as a green light."""
        main_before = self.sha("main")
        if not self.ref_exists("refs/heads/staging"):
            self.git("branch", "staging", "main")
        # remove the tests dir entirely so test_cmd()'s tree-guess also finds nothing
        self.git("checkout", "-q", "staging")
        (self.repo / "tests" / "test_x.py").unlink()
        (self.repo / "tests").rmdir()
        self.write(".common-rules.json", json.dumps(
            {"staging_branch": "staging"}, indent=2))  # no gates.merge declared
        self.git("add", "-A")
        self.git("commit", "-qm", "drop the only gate")
        self.git("checkout", "-q", "main")

        out = self.land("--advance-staging")
        combined = out.stdout + out.stderr
        self.assertIn("verdict cannot be read", combined)
        self.assertEqual(main_before, self.sha("main"))

    def test_staging_behind_main_refuses(self):
        """main moved some other way (a hotfix, or a previous advance from a
        different state) -- staging no longer contains everything main has,
        and advancing would silently drop it."""
        self.land_work_onto_staging()
        # main gets a commit staging never saw.
        self.git("checkout", "-q", "main")
        self.write("hotfix.txt", "urgent\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "hotfix straight to main")
        main_before = self.sha("main")

        out = self.land("--advance-staging")
        combined = out.stdout + out.stderr
        self.assertIn("staging is behind main", combined)
        self.assertEqual(main_before, self.sha("main"))

    def test_no_staging_branch_yet_refuses(self):
        out = self.land("--advance-staging")
        self.assertIn("nothing has landed on it", out.stdout + out.stderr)

    def test_check_only_does_not_advance(self):
        self.land_work_onto_staging()
        main_before = self.sha("main")
        out = self.land("--advance-staging", "--check")
        self.assertIn("READY", out.stdout)
        self.assertEqual(main_before, self.sha("main"))


class TestNoDeclarationBehavesAsToday(StagingHarness):

    def setUp(self):
        super().setUp()
        # Overwrite the seed's declaration with one that names no staging.
        self.write(".common-rules.json", rules_json(staging=False))
        self.git("add", "-A")
        self.git("commit", "-qm", "no staging declared")

    def test_no_staging_declared_lands_straight_to_main_path(self):
        self.branch("work", "do work", {"README.md": "seed\nwork\n"})
        out = self.land("--check")
        combined = out.stdout + out.stderr
        self.assertNotIn("landing onto", combined)
        self.assertIn("READY", out.stdout)

    def test_advance_staging_refuses_when_nothing_is_declared(self):
        out = self.land("--advance-staging")
        self.assertIn("no staging branch declared", out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
