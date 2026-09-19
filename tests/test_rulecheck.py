"""rulecheck must only ever ask the adoption question of projects that adopt.

Not every folder under apps/ follows these rules. `idea-lab` deliberately does
not — it is v2, and its own LAB-RULES.md says "no gates, no worktrees, no issues
here". rulecheck used to treat every directory as an adopter, so it reported
idea-lab as "NEVER recorded a rules version" forever: a false alarm every
session had to re-derive and dismiss, whose only offered remedy (`--align`)
would have written a stamp asserting something untrue.

The stamp is load-bearing precisely because it is trusted without re-checking —
the next session inherits it and skips reading the rules. So a wrong stamp is
worse than a missing one, and refusing to write one is the behaviour under test.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import os
import shutil
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULECHECK = ROOT / "bin" / "rulecheck"

# Resolving the real projects lives in one place -- see tests/projects.py for
# why it is read from git rather than derived from this file's location.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from projects import apps_dir  # noqa: E402
STAMP = ".common-rules-version"
POINTER = "Shared workflow rules: ../common-rules/CLAUDE-workflow.md — read it.\n"


def run(project: Path, *args, rules_dir: Path | None = None):
    env = {**os.environ, "COMMON_RULES_DIR": str(rules_dir or ROOT)}
    return subprocess.run([sys.executable, str(RULECHECK), "--project", str(project), *args],
                          capture_output=True, text=True, env=env, check=False)


# rulecheck prints its verdict, then (for a stale project) quotes the changelog
# under this heading. See bin/rulecheck, "What changed since (N changelog lines)".
DUMP_MARKER = "What changed since"


def verdict(stdout: str) -> str:
    """rulecheck's own words, with the changelog it quotes cut off.

    A stale project's report quotes the changelog, and the changelog is prose
    *about these rules* -- including the line "common-rules does not adopt
    itself." Asserting against raw stdout therefore searches the verdict and
    its evidence as one string, so a phrase occurring in the evidence reads as
    a verdict.

    That is exactly what broke RealProjectsStillCheck on `main` from the day
    that changelog entry was written: pockets, pip and mac-explorer were
    correctly recognised as adopting and correctly reported stale, and the test
    called them skipped because the changelog it was shown contained the words
    it was grepping for. The projects were fine. The assertion was reading the
    wrong half of the output.

    Same failure the render tests already guard against -- see
    test_tower_render.test_no_forecast_in_the_data_rows, which scopes its
    search to the data rows precisely because the page's own disclaimer
    contains the forecast words it bans.

    Harmless for a non-adopting project: rulecheck returns before printing any
    dump, so there is no marker and the whole of stdout is the verdict.
    """
    return stdout.split(DUMP_MARKER, 1)[0]



class AdoptionIsRead(unittest.TestCase):
    """Adoption comes from the project's own declaration, never from assumption."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def project(self, name, claude_md=None, stamp=None):
        p = self.tmp / name
        p.mkdir()
        if claude_md is not None:
            (p / "CLAUDE.md").write_text(claude_md)
        if stamp is not None:
            (p / STAMP).write_text(stamp + "\n")
        return p

    def test_non_adopting_project_is_not_reported_as_behind(self):
        """The idea-lab case: a CLAUDE.md that names common-rules to disown it.

        The mention alone must not count, or the fix would not fix anything —
        idea-lab's CLAUDE.md says it is "deliberately separate from
        ../common-rules/", which is the opposite of adopting them.
        """
        p = self.project("idea-lab",
                         "This is v2, deliberately separate from ../common-rules/.\n"
                         "No gates, no worktrees, no issues here.\n")
        r = run(p)
        # Not 0: exit 0 means "verified aligned", and nothing was verified here
        # -- there is no version to be aligned or behind on. Not 1 either: 1
        # means "verified, and stale", which is also not what happened. This is
        # its own outcome, "could not check", and it gets its own status (2).
        self.assertEqual(r.returncode, 2, f"expected 'could not check' (2), got:\n{r.stdout}{r.stderr}")
        self.assertIn("does not adopt", verdict(r.stdout))
        self.assertNotIn("NEVER recorded", verdict(r.stdout))

    def test_align_refuses_to_stamp_a_non_adopting_project(self):
        p = self.project("idea-lab", "Deliberately separate from ../common-rules/.\n")
        r = run(p, "--align")
        self.assertEqual(r.returncode, 2)
        self.assertFalse((p / STAMP).exists(),
                         "wrote a stamp claiming adoption into a project that does not adopt")
        self.assertIn("not stamping it", r.stderr)

    def test_pointer_in_claude_md_is_what_makes_a_project_adopt(self):
        p = self.project("finance-tracker", POINTER)
        r = run(p)
        self.assertEqual(r.returncode, 1, "an adopting project with no stamp is behind")
        self.assertIn("NEVER recorded", r.stdout)

    def test_existing_stamp_counts_as_adoption_on_its_own(self):
        """Rewording a CLAUDE.md must not silently un-adopt a project."""
        p = self.project("pockets", "No pointer here any more.\n", stamp="1-deadbee")
        r = run(p)
        self.assertNotIn("does not adopt", verdict(r.stdout),
                         "a project that has aligned before was treated as never having adopted")

    def test_a_project_with_no_claude_md_at_all_does_not_adopt(self):
        p = self.project("scratch")
        r = run(p)
        self.assertEqual(r.returncode, 2)
        self.assertIn("does not adopt", verdict(r.stdout))

    def test_quiet_says_nothing_for_a_non_adopting_project(self):
        """--quiet is for the SessionStart hook; a non-adopter must not print.

        The hook does not read the exit code (a SessionStart hook's exit
        status does not stop the session), so this only pins the *output*
        contract -- the exit code is pinned separately, below.
        """
        p = self.project("idea-lab", "Deliberately separate.\n")
        r = run(p, "--quiet")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), "")


class TheRulesDoNotAdoptThemselves(unittest.TestCase):

    def test_common_rules_itself_is_not_an_adopter(self):
        r = run(ROOT)
        # This is the exact case that motivated giving "could not check" its
        # own status: a session run from inside common-rules used to get exit
        # 0 here -- indistinguishable from "checked, and aligned" -- and
        # treated a vacuous run as a pass.
        self.assertEqual(r.returncode, 2)
        self.assertIn("the rules themselves", r.stdout)
        self.assertNotIn("NEVER recorded", r.stdout)

    def test_common_rules_never_acquires_a_stamp(self):
        r = run(ROOT, "--align")
        self.assertFalse((ROOT / STAMP).exists(),
                         "common-rules stamped itself with its own version")


class CannotCheckIsItsOwnStatus(unittest.TestCase):
    """0 = verified aligned. 1 = verified, and stale. 2 = nothing was verified.

    Before this, "could not check" shared exit 0 with "aligned" in both cases
    it can happen -- common-rules itself, and a non-adopting project -- so a
    caller that only looked at the exit code could not tell a real pass from
    "there was nothing to check". That is what let a session tick the box
    after running rulecheck from inside common-rules and reading exit 0 as a
    pass.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_could_not_check_is_distinct_from_both_aligned_and_stale(self):
        non_adopter = self.tmp / "scratch"
        non_adopter.mkdir()
        r_non_adopter = run(non_adopter)
        r_common_rules = run(ROOT)
        for r, label in ((r_non_adopter, "non-adopter"), (r_common_rules, "common-rules")):
            self.assertEqual(r.returncode, 2, f"{label}: expected 2, got {r.returncode}")
            self.assertNotEqual(r.returncode, 0, f"{label}: 2 must not collide with aligned")
            self.assertNotEqual(r.returncode, 1, f"{label}: 2 must not collide with stale")


class RealProjectsStillCheck(unittest.TestCase):
    """Guard against a fix that quietly stops checking everything."""

    def test_the_adopting_projects_are_still_recognised(self):
        apps = apps_dir()
        for name in ("finance-tracker", "pockets", "pip", "mac-explorer"):
            # Inside the subTest, so a project that is genuinely absent skips
            # only itself. Outside it, the first miss aborted the whole test
            # and the remaining three were never looked at even when present.
            with self.subTest(project=name):
                p = apps / name if apps else None
                if p is None or not p.exists():
                    self.skipTest(f"{name} not present beside {apps}")
                r = run(p)
                self.assertNotIn("does not adopt", verdict(r.stdout),
                                 f"{name} adopts the rules but was skipped")


class RulecheckLocatesItselfRatherThanGuessing(unittest.TestCase):
    """`rulecheck --version` must work from any checkout, on any machine.

    The default for RULES was the literal string
    "common-rules" -- correct on exactly one machine. On a
    CI runner that path does not exist, so `git -C <missing>` fails,
    current_version() returns None, and `--version` exits 2, erroring every
    gate test that asks for the current version (11 of them, on every CI run
    since CI existed).

    THE SHAPE OF THIS TEST IS THE POINT. Asserting that `--version` merely
    succeeds proves nothing here: run on the developer's Mac, the hardcoded
    path resolves and the broken version passes too. So this runs a COPY of
    the script from a DIFFERENT repository and asserts it reports THAT
    repository's version -- something only a self-located default can do. A
    hardcoded default reports the real repo's version and fails the second
    assertion.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = Path(self.tmp.name) / "elsewhere"
        (self.fake / "bin").mkdir(parents=True)
        shutil.copy2(RULECHECK, self.fake / "bin" / "rulecheck")
        for a in (("init", "-q", "-b", "main"), ("config", "user.email", "t@e.com"),
                  ("config", "user.name", "t")):
            subprocess.run(["git", "-C", str(self.fake), *a], capture_output=True)
        # Two commits, so this repo's count cannot coincide with the real one's.
        for i in range(2):
            (self.fake / f"f{i}.txt").write_text("x\n")
            subprocess.run(["git", "-C", str(self.fake), "add", "-A"], capture_output=True)
            subprocess.run(["git", "-C", str(self.fake), "commit", "-qm", f"c{i}"],
                           capture_output=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _run_without_the_env_var(self):
        env = {k: v for k, v in os.environ.items() if k != "COMMON_RULES_DIR"}
        return subprocess.run([str(self.fake / "bin" / "rulecheck"), "--version"],
                              capture_output=True, text=True, env=env, cwd=str(self.fake))

    def test_version_is_read_from_the_checkout_the_script_lives_in(self):
        r = self._run_without_the_env_var()
        self.assertEqual(r.returncode, 0, f"exit {r.returncode}: {r.stdout}{r.stderr}")
        sha = subprocess.run(["git", "-C", str(self.fake), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(r.stdout.strip(), f"2-{sha}",
                         "did not read the repository it was run from")

    def test_it_does_not_report_some_other_checkouts_version(self):
        """The assertion a hardcoded default fails. Without it, this whole
        class passes on the one machine where the old default resolved."""
        r = self._run_without_the_env_var()
        real = subprocess.run([str(RULECHECK), "--version"], capture_output=True,
                              text=True, check=True).stdout.strip()
        self.assertNotEqual(r.stdout.strip(), real,
                            "reported the real repo's version -- the path is still hardcoded")

    def test_the_env_var_still_overrides(self):
        """Projects and tests point rulecheck at a specific rules checkout;
        self-location must not take that away."""
        env = dict(os.environ, COMMON_RULES_DIR=str(ROOT))
        r = subprocess.run([str(self.fake / "bin" / "rulecheck"), "--version"],
                           capture_output=True, text=True, env=env)
        real = subprocess.run([str(RULECHECK), "--version"], capture_output=True,
                              text=True, check=True).stdout.strip()
        self.assertEqual(r.stdout.strip(), real)

    def test_no_home_directory_is_baked_into_the_default(self):
        """A structural guard, because the failure mode is silent on the only
        machine anyone runs this on. Scoped to rulecheck's RULES default --
        bin/pulse names an apps root deliberately, which is a different thing:
        a machine-local location it reports ON, not the repo it lives IN."""
        line = next(l for l in RULECHECK.read_text().splitlines()
                    if l.startswith("RULES = "))
        self.assertNotIn("/Users/", line, "a home directory is hardcoded again")


class TheChangelogIsEvidenceNotVerdict(unittest.TestCase):
    """The bug RealProjectsStillCheck actually had, pinned so it cannot return.

    Hermetic on purpose: this builds its own two-commit rules repo whose
    changelog delta contains the poisoned phrase, rather than relying on the
    real CHANGELOG.md still containing "common-rules does not adopt itself."
    A regression test that depends on the prose it is guarding against stops
    testing the moment someone rewords a changelog entry.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rules = Path(self.tmp.name) / "rules"
        self.rules.mkdir()
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")
        (self.rules / "CLAUDE-workflow.md").write_text("# rules\n")
        (self.rules / "CHANGELOG.md").write_text("# Changelog\n\n## Old entry\n\nnothing here.\n")
        self._git("add", "-A"); self._git("commit", "-qm", "seed")
        self.old_sha = self._git("rev-parse", "--short", "HEAD").stdout.strip()

        # the entry that poisons the dump -- prose about a project NOT adopting
        (self.rules / "CHANGELOG.md").write_text(
            "# Changelog\n\n## A newer entry\n\n"
            "- **common-rules does not adopt itself.** Running rulecheck inside\n"
            "  this repo checks nothing, so it must not read as a pass.\n\n"
            "## Old entry\n\nnothing here.\n")
        self._git("add", "-A"); self._git("commit", "-qm", "add the entry")

        self.proj = Path(self.tmp.name) / "pockets"
        self.proj.mkdir()
        (self.proj / "CLAUDE.md").write_text(POINTER)
        (self.proj / STAMP).write_text(f"1-{self.old_sha}\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _git(self, *a):
        return subprocess.run(["git", "-C", str(self.rules), *a],
                              capture_output=True, text=True, check=False)

    def test_a_stale_project_is_not_called_a_non_adopter_by_its_own_changelog(self):
        """An adopting project, correctly reported stale, whose evidence quotes
        the words "does not adopt". It is stale, not un-adopted, and the two
        must not be confused by a substring search."""
        r = run(self.proj, rules_dir=self.rules)
        self.assertEqual(r.returncode, 1, f"expected stale (1):\n{r.stdout}{r.stderr}")
        self.assertIn("does not adopt", r.stdout,
                      "precondition: the dump must carry the phrase, or this proves nothing")
        self.assertNotIn("does not adopt", verdict(r.stdout),
                         "the changelog it quotes was read as rulecheck's own verdict")

    def test_the_marker_that_splits_verdict_from_evidence_still_exists(self):
        """verdict() cuts on a heading bin/rulecheck prints. If that wording
        changes, verdict() silently stops cutting and every assertion above
        goes back to searching the whole dump -- passing, and testing nothing."""
        r = run(self.proj, rules_dir=self.rules)
        self.assertIn(DUMP_MARKER, r.stdout,
                      "bin/rulecheck no longer prints this heading -- update verdict()")


# --- Proposal 21, S-09: unimplemented Standard changes ----------------------

MARKER = "**Standard change (mandatory):**"


class FakeRules:
    """A throwaway rules repo whose CHANGELOG a test writes one entry at a time.

    Hermetic for the same reason as TheChangelogIsEvidenceNotVerdict: a test
    that read the real CHANGELOG would change meaning every time an entry is
    written. tests/test_warmup.py imports this too."""

    SEED = "## 2026-01-01 · Seed\n\nNothing here.\n"

    def __init__(self, parent: Path):
        self.root = Path(parent) / "rules"
        self.root.mkdir()
        for a in (("init", "-q", "-b", "main"), ("config", "user.email", "t@example.com"),
                  ("config", "user.name", "t")):
            self.git(*a)
        (self.root / "CLAUDE-workflow.md").write_text("# rules\n")
        self.blocks: list[str] = []          # newest first
        self.seed = self.SEED
        self._write()
        self.commit("seed")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.root), *a], capture_output=True, text=True, check=False)

    def commit(self, msg="entry"):
        self.git("add", "-A")
        self.git("commit", "-qm", msg)

    def _write(self):
        (self.root / "CHANGELOG.md").write_text("# Changelog\n\n" + "".join(self.blocks) + self.seed)

    def add(self, heading: str, mandatory: str | None = None, body: str = "Why it changed.\n") -> str:
        block = f"## {heading}\n\n{body}\n"
        if mandatory is not None:
            block += f"{MARKER} {mandatory}\n\n"
        self.blocks.insert(0, block)
        self._write()
        self.commit()
        return self.version()

    def write_raw(self, raw: bytes) -> str:
        (self.root / "CHANGELOG.md").write_bytes(raw)
        self.commit()
        return self.version()

    def rewrite(self) -> str:
        """Commit self.blocks (and self.seed) as edited in place by a test."""
        self._write()
        self.commit()
        return self.version()

    def version(self) -> str:
        count = self.git("rev-list", "--count", "HEAD").stdout.strip()
        sha = self.git("rev-parse", "--short", "HEAD").stdout.strip()
        return f"{count}-{sha}"

    def full_sha(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.strip()

    def ahead(self, heading: str, mandatory: str | None = None) -> str:
        """A version on a branch the rules checkout has not got: commit an entry
        on `future`, then return to main as it was."""
        saved = list(self.blocks)
        self.git("checkout", "-q", "-b", "future")
        version = self.add(heading, mandatory)
        self.git("checkout", "-q", "main")
        self.blocks = saved
        return version


def load_rulecheck():
    """bin/rulecheck as a module -- how bin/warmup and bin/conformance use it."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("rulecheck_under_test", str(RULECHECK))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def raw_controls(text: str) -> list[str]:
    """Characters that must never reach a terminal raw: C0 other than the
    newline that ends a line, DEL, C1, and the bidi/invisible set."""
    return [c for c in text if (ord(c) < 0x20 and c != "\n") or 0x7F <= ord(c) <= 0x9F
            or c in "\u202e\u200b\u2066\ufeff"]


class MandatoryStandardChanges(unittest.TestCase):
    """`rulecheck --mandatory`: the CHANGELOG entries since the stamp that carry
    a `**Standard change (mandatory):**` line. The sponsor ruled (P21, A-03)
    that each is implemented before the stamp moves; this is what makes one
    visible. Exit 0 nothing to do, 1 pending, 2 could not check."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.rules = FakeRules(self.tmp)
        self.proj = self.tmp / "app"
        self.proj.mkdir()
        (self.proj / "CLAUDE.md").write_text(POINTER)

    def stamp(self, version: str):
        (self.proj / STAMP).write_text(version + "\n")

    def mandatory(self, *extra):
        return run(self.proj, "--mandatory", *extra, rules_dir=self.rules.root)

    def test_a_stamp_before_one_mandatory_entry_is_pending_and_named(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat in every project")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("1 mandatory Standard change(s)", r.stdout)
        self.assertIn("2026-09-14 · Reheat is mandatory", r.stdout)
        self.assertIn("run derecord --reheat in every project", r.stdout)

    def test_a_stamp_before_only_informational_entries_has_nothing_to_do(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · A wording fix")
        self.rules.add("2026-09-14 · Another note", body=f"Mentions `{MARKER}` in passing.\n")
        r = self.mandatory()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no mandatory Standard change", r.stdout)
        self.assertNotIn("A wording fix", r.stdout)

    def test_aligned_past_the_entry_has_nothing_to_do(self):
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        self.stamp(self.rules.version())
        r = self.mandatory()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Reheat is mandatory", r.stdout)

    def test_an_informational_entry_after_the_aligned_one_stays_informational(self):
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        self.stamp(self.rules.version())
        self.rules.add("2026-09-15 · A wording fix")
        r = self.mandatory()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Reheat is mandatory", r.stdout)

    def test_two_mandatory_entries_count_two(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · First", "do one")
        self.rules.add("2026-09-14 · Informational")
        self.rules.add("2026-09-15 · Second", "do two")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("2 mandatory Standard change(s)", r.stdout)
        rc = load_rulecheck()
        pending = rc.mandatory_pending(self.proj, rules=self.rules.root)
        self.assertEqual(pending.state, "behind")
        self.assertEqual([e.heading for e in pending.entries], ["2026-09-15 · Second", "2026-09-14 · First"])
        self.assertEqual(pending.entries[0].line, f"{MARKER} do two")

    def test_a_marker_added_to_an_older_entry_counts_under_that_heading(self):
        self.stamp(self.rules.version())
        self.rules.seed = FakeRules.SEED + f"\n{MARKER} added later\n"
        self.rules.add("2026-09-14 · Unrelated")
        pending = load_rulecheck().mandatory_pending(self.proj, rules=self.rules.root)
        self.assertEqual([(e.heading, e.line) for e in pending.entries],
                         [("2026-01-01 · Seed", f"{MARKER} added later")])

    def test_a_wrapped_standard_change_is_quoted_whole(self):
        """The real CHANGELOG wraps the paragraph: the first run on the
        PhotoVault app quoted "...the standard reads" and cut off what the
        project must do. The line runs to the next blank line or heading."""
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Wrapped", "a project that has adopted the standard reads\n"
                                                "the entries since its stamp at each /warmup.\n"
                                                "## 2026-09-14 · Next heading, not part of it")
        pending = load_rulecheck().mandatory_pending(self.proj, rules=self.rules.root)
        self.assertEqual([e.line for e in pending.entries],
                         [f"{MARKER} a project that has adopted the standard reads "
                          "the entries since its stamp at each /warmup."])
        r = self.mandatory()
        self.assertIn("the entries since its stamp at each /warmup.", r.stdout)
        self.assertNotIn("Next heading, not part of it", r.stdout.split("Wrapped", 1)[1])

    def test_only_a_line_that_starts_with_the_marker_counts(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Examples", body=f"  {MARKER} indented, an example\n"
                                                     f"> {MARKER} quoted\n"
                                                     f"a line that ends with {MARKER}\n")
        r = self.mandatory()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_malformed_changelogs_never_traceback(self):
        cases = {
            "not utf-8, with a NUL": b"\xff\xfe\x00garbage\n## \xc3(\n" + MARKER.encode() + b" broken bytes\n",
            "marker before any heading": MARKER.encode() + b" no heading at all\n",
            "crlf line endings": b"# Changelog\r\n\r\n## CRLF\r\n\r\n" + MARKER.encode() + b" crlf\r\n",
            "empty": b"",
            "no trailing newline": b"## Last\n\n" + MARKER.encode() + b" eof",
            "a lone heading marker": b"## \n##\n#\n",
        }
        for name, raw in cases.items():
            with self.subTest(case=name):
                self.stamp(self.rules.version())
                self.rules.write_raw(raw)
                r = self.mandatory()
                self.assertNotIn("Traceback", r.stderr, r.stderr)
                self.assertIn(r.returncode, (0, 1, 2))
                if name in ("marker before any heading", "crlf line endings", "no trailing newline",
                            "not utf-8, with a NUL"):
                    self.assertEqual(r.returncode, 1, f"{name}: the marker line was missed\n{r.stdout}")
        with self.subTest(case="CHANGELOG deleted"):
            self.stamp(self.rules.version())
            self.rules.git("rm", "-q", "CHANGELOG.md")
            self.rules.commit()
            r = self.mandatory()
            self.assertNotIn("Traceback", r.stderr, r.stderr)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # A stamp that cannot be resolved is no longer "could not check" (P21
        # S-09 round 2): see test_an_unresolvable_stamp_counts_every_mandatory_entry.
        # Exit 2 is kept for the rules repo or its CHANGELOG being unreadable,
        # which is this case: the CHANGELOG is gone, whatever the stamp says.
        with self.subTest(case="CHANGELOG deleted, unresolvable stamp"):
            self.stamp("3-deadbee")
            r = self.mandatory()
            self.assertNotIn("Traceback", r.stderr, r.stderr)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_a_heading_with_control_characters_is_escaped(self):
        self.stamp(self.rules.version())
        heading = "2026-09-14 · evil\x1b[31m\x0bforged\x0c\u202eend\x85 \x7f"
        self.rules.add(heading, "line\x1b[2Jtwo")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(raw_controls(r.stdout), [], repr(r.stdout))
        self.assertIn("evil\\x1b[31m\\x0bforged\\x0c\\u202eend\\x85 \\x7f", r.stdout)
        self.assertEqual(sum("evil" in line for line in r.stdout.splitlines()), 1)

    def test_rulecheck_escapes_exactly_as_the_card_does(self):
        """Two escapers would drift; this pins bin/rulecheck's to warmup's shown()."""
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("warmup_under_test", str(ROOT / "bin" / "warmup"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        warmup = importlib.util.module_from_spec(spec)
        loader.exec_module(warmup)
        rc = load_rulecheck()
        for s in ("plain · text → ok", "a\nb\rc\td", "\x00\x1b\x7f\x85\x9f", "\u202e\u200b\u2066\ufeff",
                  "\ud800 lone", "ZWJ \u200d stays", None, 7):
            with self.subTest(value=repr(s)):
                self.assertEqual(rc.shown(s), warmup.shown(s))

    def test_mandatory_writes_nothing(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")

        def snapshot():
            # Every file, the rules repo's .git included, by content and mtime.
            # No `git status` here: it can refresh .git/index itself.
            return {str(p.relative_to(self.tmp)): (p.stat().st_mtime_ns, p.read_bytes())
                    for p in self.tmp.rglob("*") if p.is_file()}
        before = snapshot()
        self.mandatory()
        self.mandatory("--quiet")
        self.assertEqual(before, snapshot())

    def test_a_stamp_that_is_not_a_sha_is_never_handed_to_git(self):
        """A stamp is a committed file in someone else's project. Its sha part
        went into `git diff <sha>..HEAD` unchecked, so a stamp of
        `1---output=<path>` made rulecheck -- a read-only check -- create a file."""
        target = self.tmp / "pwned"
        self.stamp(f"1---output={target}")
        for args in ((), ("--mandatory",)):
            with self.subTest(args=args):
                r = run(self.proj, *args, rules_dir=self.rules.root)
                # 1, not 2: an unresolvable stamp gets no pass (round 2, item 1).
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual(sorted(p.name for p in self.tmp.iterdir() if p.name.startswith("pwned")), [])

    def test_align_refuses_a_pending_mandatory_entry_and_writes_nothing(self):
        """P21 F-01: --align used to write the stamp unconditionally, so nothing
        technically stopped a session aligning past an unimplemented mandatory
        Standard change. Now it refuses by itself."""
        before = self.rules.version()
        self.stamp(before)
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        r = run(self.proj, "--align", rules_dir=self.rules.root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Reheat is mandatory", r.stdout)
        self.assertIn("--implemented", r.stdout)
        self.assertEqual((self.proj / STAMP).read_text().strip(), before,
                          "align must write nothing while a mandatory entry is pending")

    def test_align_implemented_aligns_and_names_what_it_declared(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        cur = self.rules.version()
        r = run(self.proj, "--align", "--implemented", rules_dir=self.rules.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.proj / STAMP).read_text().strip(), cur)
        self.assertIn("aligned past 1 mandatory change(s)", r.stdout)
        self.assertIn("declared implemented", r.stdout)
        self.assertIn("Reheat is mandatory", r.stdout)

    def test_align_with_only_informational_entries_needs_no_flag(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · A wording fix")
        cur = self.rules.version()
        r = run(self.proj, "--align", rules_dir=self.rules.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.proj / STAMP).read_text().strip(), cur)
        self.assertNotIn("declared implemented", r.stdout)

    def test_align_already_aligned_needs_no_flag(self):
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        self.stamp(self.rules.version())
        r = run(self.proj, "--align", rules_dir=self.rules.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_align_with_no_stamp_and_a_pending_entry_refuses_too(self):
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        r = run(self.proj, "--align", rules_dir=self.rules.root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertFalse((self.proj / STAMP).exists())
        self.assertIn("Reheat is mandatory", r.stdout)

    def test_align_refuses_on_an_unresolvable_stamp_without_implemented(self):
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        self.stamp("3-deadbee")
        r = run(self.proj, "--align", rules_dir=self.rules.root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("cannot be resolved", r.stdout + r.stderr)
        self.assertIn("--align --implemented", r.stdout + r.stderr)
        self.assertEqual((self.proj / STAMP).read_text().strip(), "3-deadbee")

    def test_implemented_repairs_an_unresolvable_stamp(self):
        """A squash merge can drop the stamp's commit from the rules history;
        aligning is the only repair, so the declaration must get through."""
        self.rules.add("2026-09-14 · Reheat is mandatory", "run derecord --reheat")
        self.stamp("3-deadbee")
        r = run(self.proj, "--align", "--implemented", rules_dir=self.rules.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("declared implemented: 2026-09-14 · Reheat is mandatory", r.stdout)
        self.assertEqual((self.proj / STAMP).read_text().strip(), self.rules.version())

    def test_implemented_without_align_is_an_error(self):
        r = run(self.proj, "--implemented", rules_dir=self.rules.root)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_align_refuses_when_it_could_not_check_even_with_implemented(self):
        self.stamp(self.rules.version())
        self.rules.git("rm", "-q", "CHANGELOG.md")
        self.rules.commit()
        for args in (("--align",), ("--align", "--implemented")):
            with self.subTest(args=args):
                r = run(self.proj, *args, rules_dir=self.rules.root)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("could not check", r.stdout + r.stderr)

    def test_no_stamp_lists_every_mandatory_entry_in_the_changelog(self):
        self.rules.add("2026-09-14 · First", "do one")
        self.rules.add("2026-09-15 · Second", "do two")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("2 mandatory Standard change(s)", r.stdout)
        pending = load_rulecheck().mandatory_pending(self.proj, rules=self.rules.root)
        self.assertEqual((pending.state, len(pending.entries)), ("no stamp", 2))

    # --- round 2 (reviewer fix-first on a040c1e) ---------------------------

    def test_an_uppercase_sha_stamp_resolves(self):
        """Item 1: `2-1B412F1` is the same commit as `2-1b412f1`."""
        self.rules.add("2026-09-13 · Old", "already done")
        count, sha = self.rules.version().split("-", 1)
        self.stamp(f"{count}-{sha.upper()}")
        self.rules.add("2026-09-14 · New", "do the new thing")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("1 mandatory Standard change(s)", r.stdout)
        self.assertIn("2026-09-14 · New", r.stdout)
        self.assertNotIn("2026-09-13 · Old", r.stdout)
        self.assertNotIn("cannot be resolved", r.stdout)

    def test_an_unresolvable_stamp_counts_every_mandatory_entry(self):
        """Item 1: a stamp that names no commit here -- bad form, or a commit a
        force-push removed -- got a project past the gate as "could not check".
        Now it counts every mandatory entry in the CHANGELOG, and exits 1."""
        self.rules.add("2026-09-13 · Old", "do the old thing")
        self.rules.add("2026-09-13 · Informational")
        # A real commit, then gone: reset away, reflog expired, pruned.
        gone = self.rules.add("2026-09-14 · Doomed")
        self.rules.git("reset", "-q", "--hard", "HEAD~1")
        self.rules.blocks.pop(0)
        self.rules.git("reflog", "expire", "--expire=now", "--all")
        self.rules.git("gc", "-q", "--prune=now")
        self.rules.add("2026-09-14 · New", "do the new thing")
        rc = load_rulecheck()
        for bad in (gone, "3-deadbee", "7-NOTASHA", "", "garbage", "1-", "1-zzzzzzz",
                    "1-" + "a" * 41, "-\x1b[2J"):
            with self.subTest(stamp=bad):
                self.stamp(bad)
                r = self.mandatory()
                self.assertNotIn("Traceback", r.stderr, r.stderr)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(f"stamp {rc.shown(bad)} cannot be resolved -- every mandatory "
                              f"Standard change counts", r.stdout)
                self.assertIn("2 mandatory Standard change(s)", r.stdout)
                self.assertIn("2026-09-13 · Old", r.stdout)
                self.assertIn("2026-09-14 · New", r.stdout)
                self.assertEqual(raw_controls(r.stdout + r.stderr), [])
                pending = rc.mandatory_pending(self.proj, rules=self.rules.root)
                self.assertEqual((pending.state, len(pending.entries)), ("unresolvable", 2))

    def test_an_unresolvable_stamp_fails_even_with_no_mandatory_entry(self):
        self.stamp("3-deadbee")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("stamp 3-deadbee cannot be resolved", r.stdout)

    def test_rewording_what_a_standard_change_asks_is_pending(self):
        """Item 2: an added line anywhere in the requirement paragraph -- the
        marker line to the next blank line or heading -- counts."""
        self.rules.add("2026-09-14 · Reheat", "run derecord --reheat\nin every project, weekly.")
        self.stamp(self.rules.version())
        self.rules.blocks[0] = self.rules.blocks[0].replace("in every project, weekly.",
                                                            "in every project, daily.")
        self.rules.rewrite()
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("2026-09-14 · Reheat", r.stdout)
        self.assertIn("run derecord --reheat in every project, daily.", r.stdout)

    def test_an_edit_outside_the_requirement_paragraph_is_not_pending(self):
        self.rules.add("2026-09-14 · Reheat", "run derecord --reheat",
                       body="Why it changed.\n")
        self.stamp(self.rules.version())
        self.rules.blocks[0] = self.rules.blocks[0].replace("Why it changed.", "Why it changed, reworded.")
        self.rules.blocks[0] += "A note added after the requirement.\n\n"
        self.rules.rewrite()
        r = self.mandatory()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_marker_inside_a_fenced_code_block_is_not_a_standard_change(self):
        """Item 3: an informational entry showing the format is not one."""
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · The format, backticks",
                       body=f"Write it like this:\n\n```markdown\n{MARKER} what each project must do\n```\n")
        self.rules.add("2026-09-14 · The format, tildes",
                       body=f"~~~~\n{MARKER} inside a tilde fence\n~~~~\n")
        r = self.mandatory()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rc = load_rulecheck()
        self.assertEqual(rc.mandatory_in_changelog(self.rules.root), ())

    def test_a_heading_inside_a_fence_is_not_a_heading_and_quoting_stops_at_a_fence(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Real", body="```\n## Fake heading\n```\n")
        self.rules.blocks[0] += f"{MARKER} the real requirement\n```\ncode, not requirement\n```\n\n"
        self.rules.rewrite()
        pending = load_rulecheck().mandatory_pending(self.proj, rules=self.rules.root)
        self.assertEqual([(e.heading, e.line) for e in pending.entries],
                         [("2026-09-14 · Real", f"{MARKER} the real requirement")])

    def test_an_unclosed_fence_does_not_hide_a_later_standard_change(self):
        """A fence that never closes is malformed, and fails closed: it opens
        nothing, so a real marker after it still counts."""
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Broken", body="```\nnever closed\n")
        self.rules.add("2026-09-15 · Real", "do it")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("2026-09-15 · Real", r.stdout)

    def test_a_moved_entry_is_not_pending(self):
        """Item 4: moving an entry above or below another, otherwise unchanged,
        is not a new requirement. The informational entry is long so that git
        shows the short mandatory entry as the one that moved."""
        long_body = "".join(f"line {i} of a long informational entry.\n" for i in range(30))
        for direction in ("above", "below"):
            with self.subTest(direction=direction):
                self.setUp()
                if direction == "above":
                    self.rules.add("2026-09-14 · Mandatory", "do it")
                    self.rules.add("2026-09-15 · Long", body=long_body)
                else:
                    self.rules.add("2026-09-15 · Long", body=long_body)
                    self.rules.add("2026-09-14 · Mandatory", "do it")
                self.stamp(self.rules.version())
                self.rules.blocks.reverse()
                self.rules.rewrite()
                diff = self.rules.git("diff", "-U0", "HEAD~1..HEAD", "--", "CHANGELOG.md").stdout
                self.assertIn(f"+{MARKER} do it", diff, "precondition: git must show the mandatory entry moving")
                r = self.mandatory()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_moved_and_reworded_entry_is_pending(self):
        long_body = "".join(f"line {i} of a long informational entry.\n" for i in range(30))
        self.rules.add("2026-09-14 · Mandatory", "do it")
        self.rules.add("2026-09-15 · Long", body=long_body)
        self.stamp(self.rules.version())
        self.rules.blocks.reverse()
        self.rules.blocks[0] = self.rules.blocks[0].replace("do it", "do it twice")
        self.rules.rewrite()
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_a_full_sha_or_longer_prefix_stamp_is_aligned(self):
        """Item 5: the sha identifies the version; a longer form of it is the same one."""
        self.rules.add("2026-09-14 · Reheat", "do it")
        count, short = self.rules.version().split("-", 1)
        full = self.rules.full_sha()
        for sha in (full, full[:len(short) + 3], full.upper()):
            with self.subTest(sha=sha):
                self.stamp(f"{count}-{sha}")
                r = self.mandatory()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("is aligned", r.stdout)
                plain = run(self.proj, rules_dir=self.rules.root)
                self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)
                self.assertIn("is aligned", plain.stdout)

    def test_a_prefix_shorter_than_the_short_sha_is_not_aligned(self):
        self.rules.add("2026-09-14 · Reheat", "do it")
        count, short = self.rules.version().split("-", 1)
        self.stamp(f"{count}-{short[:4]}")
        plain = run(self.proj, rules_dir=self.rules.root)
        self.assertNotIn("is aligned", plain.stdout)

    def test_a_stamp_ahead_of_the_rules_checkout_is_not_behind(self):
        """Item 5: the project aligned with rules this checkout has not pulled."""
        self.rules.add("2026-09-14 · Here", "already here")
        self.stamp(self.rules.ahead("2026-09-15 · Future", "not here yet"))
        r = self.mandatory()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ahead of this rules checkout -- update common-rules", r.stdout)
        self.assertNotIn("behind", r.stdout)
        pending = load_rulecheck().mandatory_pending(self.proj, rules=self.rules.root)
        self.assertEqual((pending.state, pending.entries), ("ahead", ()))

    def test_a_stamp_on_a_diverged_branch_is_behind_not_ahead(self):
        """S-09 final review (A, probe f1): a stamp on a side branch was called
        "ahead", hiding a mandatory entry main added since."""
        self.rules.add("2026-09-14 · Here", "already here")
        self.stamp(self.rules.ahead("2026-09-15 · Side", "only on a side branch"))
        self.rules.add("2026-09-16 · New on main", "do the new thing")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("2026-09-16 · New on main", r.stdout)
        self.assertNotIn("ahead of this rules checkout", r.stdout)
        self.assertEqual(load_rulecheck().mandatory_pending(self.proj, rules=self.rules.root).state, "behind")
        plain = run(self.proj, rules_dir=self.rules.root)
        self.assertEqual(plain.returncode, 1, plain.stdout + plain.stderr)
        self.assertNotIn("ahead of this rules checkout", plain.stdout)

    def test_a_rebased_away_stamp_still_counts_what_main_added(self):
        """S-09 final review (A, probe f2): the stamp's commit is unreachable but
        its object is still present."""
        self.rules.add("2026-09-14 · A", "do a")
        self.stamp(self.rules.version())
        self.rules.git("reset", "-q", "--hard", "HEAD~1")
        self.rules.blocks.pop(0)
        self.rules.add("2026-09-15 · B", "do b")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("2026-09-15 · B", r.stdout)
        self.assertNotIn("ahead", r.stdout)

    def test_a_truly_ahead_stamp_exits_0_in_plain_rulecheck(self):
        """Judgement call: ahead is not a problem, and bin/land's advice to
        align would move the stamp backwards."""
        self.rules.add("2026-09-14 · Here", "already here")
        self.stamp(self.rules.ahead("2026-09-15 · Future", "not here yet"))
        plain = run(self.proj, rules_dir=self.rules.root)
        self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)
        self.assertIn("ahead of this rules checkout", plain.stdout)

    def test_an_unclosed_fence_does_not_hide_its_own_requirement_when_an_older_fence_follows(self):
        """S-09 final review (B, probe k3): the new entry's unclosed fence paired
        with an older entry's fence and hid the new requirement."""
        self.rules.add("2026-09-13 · Older", body="```\nold code\n```\n")
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · New", "do the new thing", body="```md\nthe fence was never closed\n")
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("2026-09-14 · New", r.stdout)

    def test_deleting_a_line_of_a_requirement_is_pending(self):
        """S-09 final review (D, probe b4): 'do not / delete the vault.' losing
        its second line changes what the entry asks."""
        self.rules.add("2026-09-14 · Vault", "do not\ndelete the vault.")
        self.stamp(self.rules.version())
        self.rules.blocks[0] = self.rules.blocks[0].replace("do not\ndelete the vault.", "do not")
        self.rules.rewrite()
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("2026-09-14 · Vault", r.stdout)

    def test_a_deleted_body_line_next_to_an_unchanged_requirement_is_not_pending(self):
        self.rules.add("2026-09-14 · Vault", "do the thing", body="First reason.\nSecond reason.\n")
        self.stamp(self.rules.version())
        self.rules.blocks[0] = self.rules.blocks[0].replace("Second reason.\n", "")
        self.rules.rewrite()
        r = self.mandatory()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_crlf_changelog_entry_is_read(self):
        self.stamp(self.rules.version())
        raw = ("# Changelog\r\n\r\n## 2026-09-14 · Crlf\r\n\r\nWhy.\r\n\r\n" + MARKER
               + " do it\r\n\r\n" + FakeRules.SEED).encode()
        self.rules.write_raw(raw)
        r = self.mandatory()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("2026-09-14 · Crlf", r.stdout)

    def test_a_blockquoted_marker_is_not_a_standard_change(self):
        self.stamp(self.rules.version())
        self.rules.add("2026-09-14 · Quoted", body="> " + MARKER + " quoted, not a requirement\n")
        r = self.mandatory()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_non_adopting_project_could_not_check(self):
        (self.proj / "CLAUDE.md").write_text("Deliberately separate.\n")
        r = self.mandatory()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("does not adopt", r.stdout)


if __name__ == "__main__":
    unittest.main()


class TestVersionFlagIsAMachineContract(unittest.TestCase):
    """`rulecheck --version` is parsed by `bin/land`, so its shape is a
    contract, not a display choice.

    V-01 made it print the pretty label. `bin/land` compares that output
    against the project's stamp file, so it saw "0.9.0 (589-5f88754)"
    against a stamp of "589-5f88754" and told every project it was not
    aligned -- 21 tests on main, and every real `land` would have refused.
    The semver belongs in the lines a person reads.
    """

    def run_rulecheck(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "bin" / "rulecheck"), *args],
                              capture_output=True, text=True, cwd=str(ROOT))

    def test_version_prints_the_bare_count_and_sha(self):
        out = self.run_rulecheck("--version").stdout.strip()
        self.assertRegex(out, r"^\d+-[0-9a-f]{7,}$",
                         "--version must stay the bare <count>-<sha> bin/land compares")

    def test_the_semver_is_available_but_only_when_asked_for(self):
        out = self.run_rulecheck("--version", "--semver").stdout.strip()
        self.assertRegex(out, r"^\d+\.\d+\.\d+ \(\d+-[0-9a-f]{7,}\)$")

    def test_what_land_compares_matches_what_align_would_write(self):
        """The two sides of land's own equality check, compared directly."""
        version = self.run_rulecheck("--version").stdout.strip()
        stamp_shape = re.compile(r"^\d+-[0-9a-f]{7,}$")
        self.assertRegex(version, stamp_shape,
                         "land reads the stamp file and this flag; both must be this shape")
