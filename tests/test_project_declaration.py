"""A project declares its own entry points: `.common-rules.json` (proposal 20, V-00, D9).

The standard assumed every project reads HANDOFF.md first, keeps its
prohibitions under a HANDOFF heading containing "prohibition", and has one
test gate. The PhotoVault app does none of that: CLAUDE.md is its entry point,
its safety rules sit under "## Hard safety rules" in CLAUDE.md, and it has a
quick gate and a merge gate. Its warm card said "Prohibitions: none found"
over five NEVER rules and told the session to read a file marked Historical.

What these tests hold the declaration to:

  * tools/project.py's load() is the declaration merged over the defaults,
    with `.common-rules-test` still feeding gates.merge; problems() names a
    malformed file, a wrong type, and a declared file that does not exist.
    Malformed JSON never raises.
  * an app-shaped project -- CLAUDE.md first, SPONSOR-CONSTRAINTS.md, no
    HANDOFF.md -- gets a card whose prohibitions, read order and gates are its
    own, and --check reads ready.
  * a broken declaration fails --check, naming the file.

land's side (the declared merge gate runs, a malformed file refuses) is in
tests/test_land_declared_test_command.py; the migrate pointer in
tests/test_warmup_migrate.py.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WARMUP = ROOT / "bin" / "warmup"
TRACKER = ROOT / "bin" / "tracker"
LAND = ROOT / "bin" / "land"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_warmup import LEDGER, ledger_data  # noqa: E402

DEFAULT_READ_ORDER = ["HANDOFF.md", "docs/OPERATING-RULES.md"]


def P():
    # Imported per test, not at module load: before tools/project.py exists
    # every case fails on its own rather than the module erroring once.
    from tools import project
    return project


class Scratch(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body if isinstance(body, str) else json.dumps(body))


class TestLoad(Scratch):

    def test_no_declaration_is_the_defaults(self):
        d = P().load(self.root)
        self.assertEqual(DEFAULT_READ_ORDER, d["read_order"])
        self.assertEqual("HANDOFF.md#prohibition", d["safety_rules"])
        self.assertEqual({}, d["gates"])
        self.assertEqual([], P().problems(self.root))

    def test_the_test_file_is_the_merge_gate(self):
        self.write(".common-rules-test", "# the merge gate\n\n  python3 -m pytest -q  \n")
        self.assertEqual({"merge": "python3 -m pytest -q"}, P().load(self.root)["gates"])

    def test_a_declared_merge_gate_wins_over_the_test_file(self):
        self.write(".common-rules-test", "false\n")
        self.write(".common-rules.json", {"gates": {"merge": "sh tools/gate.sh"}})
        self.assertEqual("sh tools/gate.sh", P().load(self.root)["gates"]["merge"])

    def test_a_declaration_without_a_merge_gate_takes_the_test_file(self):
        self.write(".common-rules-test", "sh tools/gate.sh\n")
        self.write(".common-rules.json", {"gates": {"quick": "sh tools/gate.sh --quick"}})
        self.assertEqual({"quick": "sh tools/gate.sh --quick", "merge": "sh tools/gate.sh"},
                         P().load(self.root)["gates"])

    def test_a_declaration_overrides_only_what_it_declares(self):
        self.write("CLAUDE.md", "# app\n")
        self.write(".common-rules.json", {"read_order": ["CLAUDE.md"]})
        d = P().load(self.root)
        self.assertEqual(["CLAUDE.md"], d["read_order"])
        self.assertEqual("HANDOFF.md#prohibition", d["safety_rules"])
        self.assertEqual({}, d["gates"])

    def test_every_documented_key_is_read(self):
        self.write("CLAUDE.md", "# app\n")
        self.write("SPONSOR-CONSTRAINTS.md", "# rulings\n")
        decl = {"read_order": ["CLAUDE.md", "SPONSOR-CONSTRAINTS.md"],
                "safety_rules": "CLAUDE.md#Hard safety rules",
                "gates": {"quick": "sh tools/gate.sh --quick", "merge": "sh tools/gate.sh"},
                "plan_check": "python3 tools/build_plan.py --check", "plan_page": "python3 tools/build_plan.py"}
        self.write(".common-rules.json", decl)
        d = P().load(self.root)
        for key, value in decl.items():
            self.assertEqual(value, d[key], key)
        self.assertEqual([], P().problems(self.root))

    def test_unknown_keys_are_ignored(self):
        self.write(".common-rules.json", {"switches": {"issues": False}, "routing": []})
        d = P().load(self.root)
        self.assertNotIn("switches", d)
        self.assertEqual(DEFAULT_READ_ORDER, d["read_order"])
        self.assertEqual([], P().problems(self.root))

    def test_a_safety_rules_list_is_accepted(self):
        self.write("CLAUDE.md", "# app\n")
        self.write("SAFETY.md", "# safety\n")
        self.write(".common-rules.json", {"safety_rules": ["CLAUDE.md#Hard safety rules", "SAFETY.md#never"]})
        self.assertEqual(["CLAUDE.md#Hard safety rules", "SAFETY.md#never"], P().load(self.root)["safety_rules"])
        self.assertEqual([], P().problems(self.root))


class TestProblems(Scratch):

    def test_malformed_json_returns_the_defaults_and_is_named(self):
        self.write(".common-rules-test", "python3 -m pytest -q\n")
        self.write(".common-rules.json", '{"read_order": ["CLAUDE.md",]')
        d = P().load(self.root)  # must not raise
        self.assertEqual(DEFAULT_READ_ORDER, d["read_order"])
        self.assertEqual({"merge": "python3 -m pytest -q"}, d["gates"])
        found = P().problems(self.root)
        self.assertEqual(1, len(found), found)
        self.assertIn(".common-rules.json", found[0])
        self.assertIn("not valid JSON", found[0])

    def test_invalid_utf8_is_malformed_not_a_crash(self):
        (self.root / ".common-rules.json").write_bytes(b'{"read_order": ["\xff"]}')
        self.assertEqual(DEFAULT_READ_ORDER, P().load(self.root)["read_order"])
        self.assertIn("not valid JSON", " ".join(P().problems(self.root)))

    def test_a_value_that_is_not_an_object_is_named(self):
        self.write(".common-rules.json", '["CLAUDE.md"]')
        self.assertEqual(DEFAULT_READ_ORDER, P().load(self.root)["read_order"])
        found = P().problems(self.root)
        self.assertEqual(1, len(found), found)
        self.assertIn("object", found[0])

    def test_each_wrong_type_is_named_and_the_default_stands(self):
        self.write(".common-rules.json", {"read_order": "CLAUDE.md", "safety_rules": 5,
                                          "gates": {"merge": 3, "quick": ["x"]}, "plan_check": [],
                                          "plan_page": {"cmd": "x"}})
        d = P().load(self.root)
        self.assertEqual(DEFAULT_READ_ORDER, d["read_order"])
        self.assertEqual("HANDOFF.md#prohibition", d["safety_rules"])
        self.assertEqual({}, d["gates"])
        found = "\n".join(P().problems(self.root))
        for key in ("read_order", "safety_rules", "gates.merge", "gates.quick", "plan_check", "plan_page"):
            self.assertIn(key, found)

    def test_gates_that_are_not_an_object_are_named(self):
        self.write(".common-rules.json", {"gates": "sh tools/gate.sh"})
        self.assertEqual({}, P().load(self.root)["gates"])
        self.assertIn("gates", " ".join(P().problems(self.root)))

    def test_a_declared_read_order_file_that_is_missing_is_named(self):
        self.write("CLAUDE.md", "# app\n")
        self.write(".common-rules.json", {"read_order": ["CLAUDE.md", "SPONSOR-CONSTRAINTS.md"]})
        found = P().problems(self.root)
        self.assertEqual(1, len(found), found)
        self.assertIn("SPONSOR-CONSTRAINTS.md", found[0])
        self.assertIn("read_order", found[0])

    def test_a_declared_safety_rules_file_that_is_missing_is_named(self):
        self.write(".common-rules.json", {"safety_rules": "RULES.md#never"})
        found = P().problems(self.root)
        self.assertEqual(1, len(found), found)
        self.assertIn("RULES.md", found[0])

    def test_a_safety_rule_without_a_heading_is_named(self):
        self.write("CLAUDE.md", "# app\n")
        self.write(".common-rules.json", {"safety_rules": "CLAUDE.md"})
        self.assertIn("FILE#heading", " ".join(P().problems(self.root)))

    def test_the_defaults_are_never_the_declarations_problem(self):
        """HANDOFF.md missing is warm-up's to report, with derecord's remedy --
        not a fault in a declaration that does not exist."""
        self.assertEqual([], P().problems(self.root))


APP_CLAUDE = """# app — working rules for every session

Read this first, then SPONSOR-CONSTRAINTS.md.

## Authorities, in order

1. `SPONSOR-CONSTRAINTS.md` — verified sponsor rulings.

## Hard safety rules

- NEVER read-write, move, reset or overwrite the real library.
- NEVER kill processes by name pattern (`pkill -f`, `killall`).

## How work is done

- **The plan is the queue.** Pick the next item.
"""

APP_DECLARATION = {
    "read_order": ["CLAUDE.md", "SPONSOR-CONSTRAINTS.md"],
    "safety_rules": "CLAUDE.md#Hard safety rules",
    "gates": {"quick": "sh tools/gate.sh --quick", "merge": "sh tools/gate.sh"},
    "plan_check": "python3 tools/build_plan.py --check",
    "plan_page": "python3 tools/build_plan.py",
}


class AppProject(unittest.TestCase):
    """CLAUDE.md first with "## Hard safety rules", SPONSOR-CONSTRAINTS.md, a
    declaration, a current ledger, page and checkpoint -- and no HANDOFF.md."""

    declaration = APP_DECLARATION

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "app"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write("CLAUDE.md", APP_CLAUDE)
        self.write("SPONSOR-CONSTRAINTS.md", "# Sponsor constraints\n\n- One copy of the app.\n")
        self.write(".common-rules.json", json.dumps(self.declaration, indent=2))
        self.write(LEDGER, json.dumps(ledger_data(), indent=2))
        subprocess.run([sys.executable, str(TRACKER), "render", str(self.root / LEDGER)], capture_output=True, check=True)
        subprocess.run([sys.executable, str(TRACKER), "checkpoint", "--project", str(self.root)],
                       capture_output=True, check=True)
        self.commit("app-shaped seed")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.root), *a], capture_output=True, text=True, check=False)

    def write(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-qm", msg)

    def warmup(self, *args):
        return subprocess.run([sys.executable, str(WARMUP), "--project", str(self.root), "--no-recall", *args],
                              capture_output=True, text=True, check=False)

    def state(self):
        r = self.warmup("--json")
        self.assertEqual(0, r.returncode, r.stderr)
        return json.loads(r.stdout)

    def land_test_cmd(self):
        script = f'cd "{self.root}"\neval "$(sed -n \'/^test_cmd()/,/^}}/p\' "{LAND}")"\ntest_cmd\n'
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False).stdout.strip()


class TestAnAppShapedCard(AppProject):

    def test_check_reads_ready_with_no_handoff(self):
        r = self.warmup("--check")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("ready", r.stdout)
        self.assertNotIn("HANDOFF.md", r.stdout)
        self.assertNotIn("OPERATING-RULES.md is missing", r.stdout)

    def test_prohibitions_come_from_the_declared_section_verbatim(self):
        out = self.warmup().stdout
        self.assertIn("- NEVER read-write, move, reset or overwrite the real library.", out)
        self.assertIn("- NEVER kill processes by name pattern (`pkill -f`, `killall`).", out)
        self.assertIn("Prohibitions (CLAUDE.md, verbatim):\n  - NEVER read-write", out,
                      "the prohibitions heading names where they came from")
        self.assertNotIn("The plan is the queue", out, "the next section was swallowed")
        self.assertNotIn("verified sponsor rulings", out, "an earlier section was read")
        self.assertNotIn("Prohibitions: none found", out)

    def test_read_order_starts_with_the_declared_files(self):
        out = self.warmup().stdout
        line = next(l for l in out.splitlines() if l.startswith("Read in order: "))
        self.assertTrue(line.startswith(f"Read in order: CLAUDE.md → SPONSOR-CONSTRAINTS.md → {LEDGER}"), line)
        self.assertNotIn("HANDOFF.md", line)
        self.assertTrue(line.endswith("CLAUDE-workflow.md"), line)

    def test_both_gates_are_on_the_card(self):
        out = self.warmup().stdout
        tools = out.split("Tools:", 1)[1]
        self.assertRegex(tools, r"quick gate\s+sh tools/gate\.sh --quick")
        self.assertRegex(tools, r"merge gate\s+sh tools/gate\.sh(\s|$)")

    def test_the_json_test_command_is_lands_and_the_quick_gate_is_added(self):
        s = self.state()
        self.assertEqual("sh tools/gate.sh", s["test_command"])
        self.assertEqual(self.land_test_cmd(), s["test_command"])
        self.assertEqual("sh tools/gate.sh --quick", s["quick_gate"])

    def test_unfilled_placeholders_are_checked_in_the_declared_files(self):
        self.write("SPONSOR-CONSTRAINTS.md", "# Sponsor constraints\n\n{{RULINGS}}\n")
        self.commit("half-seeded")
        r = self.warmup("--check")
        self.assertEqual(1, r.returncode, r.stdout)
        self.assertIn("SPONSOR-CONSTRAINTS.md has 1 unfilled placeholder(s): {{RULINGS}}", r.stdout)

    def test_a_declared_file_that_is_missing_is_a_named_problem(self):
        (self.root / "SPONSOR-CONSTRAINTS.md").unlink()
        self.commit("lost the constraints")
        r = self.warmup("--check")
        self.assertEqual(1, r.returncode, r.stdout)
        self.assertIn("SPONSOR-CONSTRAINTS.md", r.stdout)
        self.assertRegex(r.stdout, r"1 problem\(s\)")

    def test_a_change_to_a_declared_file_shows_in_the_delta(self):
        state = self.root / ".claude" / "warmup" / "last.json"
        self.warmup("--state", str(state))
        self.write("CLAUDE.md", APP_CLAUDE + "\n- NEVER write to /Volumes/.\n")
        self.commit("a new rule")
        self.assertIn("CLAUDE.md changed since the last warm-up", self.warmup("--since", str(state)).stdout)


class TestAReadOrderNamingTheLedger(AppProject):
    declaration = dict(APP_DECLARATION, read_order=["CLAUDE.md", LEDGER, "SPONSOR-CONSTRAINTS.md"])

    def test_nothing_is_read_twice(self):
        order = self.state()["read_order"]
        self.assertEqual(1, order.count(LEDGER), order)
        self.assertEqual(["CLAUDE.md", LEDGER, "SPONSOR-CONSTRAINTS.md"], order[:3])


class TestABrokenDeclaration(AppProject):

    def test_malformed_json_fails_check_naming_the_file(self):
        self.write(".common-rules.json", '{"read_order": ["CLAUDE.md"')
        self.commit("broke it")
        r = self.warmup("--check")
        self.assertEqual(1, r.returncode, r.stdout)
        self.assertIn(".common-rules.json is not valid JSON", r.stdout)

    def test_malformed_json_card_reports_lands_refusal(self):
        self.write(".common-rules.json", "{")
        self.commit("broke it")
        s = self.state()
        self.assertEqual(self.land_test_cmd(), s["test_command"])
        self.assertTrue(s["test_command"].startswith("false"), s["test_command"])

    def test_a_wrong_type_fails_check(self):
        self.write(".common-rules.json", json.dumps(dict(APP_DECLARATION, read_order="CLAUDE.md")))
        self.commit("wrong type")
        r = self.warmup("--check")
        self.assertEqual(1, r.returncode, r.stdout)
        self.assertIn("read_order", r.stdout)


if __name__ == "__main__":
    unittest.main()
