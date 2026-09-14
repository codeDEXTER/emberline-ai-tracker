"""The ledger contract every tracker command builds on (proposal 19, W-00).

The strongest test here is the real one: the PhotoVault engine's proposal 71
ledger -- 39 items, 58 commits in one day -- must load and validate unchanged,
because the standard is lifted from it. When that file is not on this machine
the test says so and skips rather than passing vacuously.

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
sys.path.insert(0, str(ROOT))

from tools.tracker import ledger  # noqa: E402

ENGINE_71 = Path("/Users/the-sponsor/apps/PhotoVault/engine/docs/proposals/71-engine-1-3-programme.json")
TRACKER = ROOT / "bin" / "tracker"


def minimal(**over):
    d = {
        "proposal": 19, "title": "t", "status": "accepted",
        "phases": [{"id": "W", "name": "build"}],
        "items": [
            {"id": "W-01", "phase": "W", "cx": "C2", "title": "a", "status": "done",
             "log": [{"at": "2026-09-13T20:00:00+02:00", "event": "merged", "by": "lead", "evidence": "abc123"}]},
            {"id": "W-02", "phase": "W", "cx": "C3", "title": "b", "status": "not started", "depends": "W-01"},
            {"id": "W-03", "phase": "W", "cx": "C2", "title": "c", "status": "not started", "depends": ["W-02"]},
        ],
        "asks": [{"id": "A-01", "at": "2026-09-13", "kind": "research", "quote": "look into it",
                  "became": None, "state": "open"}],
    }
    d.update(over)
    return d


class TestShape(unittest.TestCase):

    def test_a_well_formed_ledger_has_no_problems(self):
        self.assertEqual([], ledger.validate(minimal()))

    def test_both_spellings_of_a_list_are_read(self):
        self.assertEqual(["R-01", "R-02"], ledger.as_list("R-01 R-02"))
        self.assertEqual(["a.py", "b.py"], ledger.as_list("a.py, b.py"))
        self.assertEqual(["x"], ledger.as_list(["x", " "]))
        self.assertEqual([], ledger.as_list(""))
        self.assertEqual([], ledger.as_list(None))

    def test_counts_always_carry_all_four_states_in_order(self):
        c = ledger.counts(minimal())
        self.assertEqual(["done", "in progress", "blocked", "not started"], list(c))
        self.assertEqual("1 done / 0 in progress / 0 blocked / 2 not started", ledger.status_line(minimal()))

    def test_unblocked_means_every_dependency_is_done(self):
        self.assertEqual(["W-02"], [i["id"] for i in ledger.unblocked(minimal())])

    def test_open_asks_are_found(self):
        self.assertEqual(["A-01"], [a["id"] for a in ledger.open_asks(minimal())])


class TestProblemsAreNamed(unittest.TestCase):

    def problems(self, d):
        return "\n".join(ledger.validate(d))

    def test_a_status_outside_the_vocabulary(self):
        d = minimal(); d["items"][1]["status"] = "wip"
        self.assertIn("W-02: status 'wip'", self.problems(d))

    def test_a_duplicate_id(self):
        d = minimal(); d["items"][2]["id"] = "W-02"
        self.assertIn("W-02: id appears more than once", self.problems(d))

    def test_a_dependency_on_nothing(self):
        d = minimal(); d["items"][1]["depends"] = "W-99"
        self.assertIn("W-02: depends on W-99", self.problems(d))

    def test_done_with_no_log_is_a_claim_without_evidence(self):
        d = minimal(); d["items"][0]["log"] = []
        self.assertIn("W-01: done with an empty log", self.problems(d))

    def test_discovered_from_must_resolve(self):
        d = minimal(); d["items"][2]["discovered_from"] = "X-09"
        self.assertIn("discovered_from X-09", self.problems(d))
        d["items"][2]["discovered_from"] = "A-01"
        self.assertNotIn("discovered_from", self.problems(d))

    def test_an_ask_without_the_sponsors_words(self):
        d = minimal(); d["asks"][0]["quote"] = ""
        self.assertIn("A-01: no `quote`", self.problems(d))

    def test_an_ask_that_became_nothing(self):
        d = minimal(); d["asks"][0]["state"] = "became-item"
        self.assertIn("A-01: became-item but `became` names nothing", self.problems(d))


class TestFind(unittest.TestCase):

    def test_find_skips_json_that_is_not_a_ledger(self):
        """Found by running warm-up read-only on the PhotoVault engine, 13 Sep:
        docs/proposals/56-proposal-the-sample-sheet.sidecar.json matches the
        NN-*.json name and is a data file, so every tool built on find() --
        warm-up, the checkpoint hook -- printed "Proposal None · 0 done".
        A file that does not parse is still returned: a broken ledger must be
        reported, and only its contents can say it is not one."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "docs" / "proposals"
            d.mkdir(parents=True)
            (d / "71-programme.json").write_text(json.dumps(minimal(proposal=71)))
            (d / "56-proposal-the-sample-sheet.sidecar.json").write_text(json.dumps({"sheet": [1, 2]}))
            (d / "57-broken.json").write_text("{nope")
            self.assertEqual(["57-broken.json", "71-programme.json"], [p.name for p in ledger.find(tmp)])


class TestTheRealLedger(unittest.TestCase):

    @unittest.skipUnless(ENGINE_71.exists(), f"{ENGINE_71} is not on this machine")
    def test_the_engine_ledger_the_standard_was_lifted_from_validates(self):
        d = ledger.load(ENGINE_71)
        self.assertEqual([], ledger.validate(d), "the loader rejects the ledger it was modelled on")
        self.assertGreaterEqual(len(ledger.items(d)), 30)


class TestTheCommand(unittest.TestCase):

    def run_tracker(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(TRACKER), *args], capture_output=True,
                              text=True, cwd=cwd, check=False)

    def test_validate_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "19-x.json"; good.write_text(json.dumps(minimal()))
            bad_d = minimal(); bad_d["items"][0]["status"] = "wip"
            bad = Path(tmp) / "20-y.json"; bad.write_text(json.dumps(bad_d))
            self.assertEqual(0, self.run_tracker("validate", str(good)).returncode)
            r = self.run_tracker("validate", str(bad))
            self.assertEqual(1, r.returncode)
            self.assertIn("status 'wip'", r.stdout)
            broken = Path(tmp) / "21-z.json"; broken.write_text("{nope")
            self.assertEqual(2, self.run_tracker("validate", str(broken)).returncode)

    def test_checkpoint_is_routed_by_the_dispatcher(self):
        """W-07 built tools/tracker/checkpoint.py; the lead wires the command.
        A project with no open ledger is an ordinary shape: exit 0, a note."""
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_tracker("checkpoint", "--project", tmp)
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertIn("no open ledger", r.stdout)
            self.assertFalse((Path(tmp) / "docs" / "handovers").exists())

    def test_an_unknown_command_says_so_rather_than_crashing(self):
        """This used `import` as its example of an unbuilt command until W-09
        built it; every listed command now exists. What stays worth pinning is
        that a mistyped one exits 2 with a sentence, not a traceback."""
        r = self.run_tracker("frobnicate")
        self.assertEqual(2, r.returncode)
        self.assertIn("unknown command", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


APP_70 = Path("/Users/the-sponsor/apps/PhotoVault/app/docs/proposals/70-r9-delivery-plan.json")


def v2(**over):
    """A ledger using proposal 20's optional contract additions."""
    d = minimal()
    d["tiers"] = {"C2": {"tier": "medium", "model": "sonnet"}, "C3": {"tier": "high", "model": "opus"}}
    d["items"][0]["model"] = "sonnet"
    d["items"][1]["model"] = "opus"
    d.update(over)
    return d


class TestRouting(unittest.TestCase):
    """D2: one routing table, and a row's model agrees with it."""

    def problems(self, d):
        return "\n".join(ledger.validate(d))

    def test_a_row_whose_model_disagrees_with_its_class_is_named(self):
        d = v2(); d["items"][0]["model"] = "opus"
        self.assertIn("W-01: model 'opus' disagrees with tiers C2 (sonnet)", self.problems(d))

    def test_a_reason_allows_the_override(self):
        d = v2(); d["items"][0]["model"] = "opus"; d["items"][0]["model_override_reason"] = "needs design"
        self.assertEqual([], ledger.validate(d))

    def test_no_tiers_means_no_routing_check(self):
        d = minimal(); d["items"][0]["model"] = "anything"
        self.assertEqual([], ledger.validate(d))


class TestOwner(unittest.TestCase):
    """D4: blocked rows and decisions say whose call they are."""

    def test_the_three_owner_shapes_are_accepted(self):
        d = minimal()
        d["items"][1]["status"] = "blocked"; d["items"][1]["owner"] = "sponsor"
        d["items"][2]["owner"] = "session:PhotoVault Engine"
        d["asks"][0]["owner"] = "lead"
        self.assertEqual([], ledger.validate(d))

    def test_an_unknown_owner_is_named(self):
        d = minimal(); d["items"][1]["owner"] = "boss"
        self.assertIn("W-02: owner 'boss' is not sponsor, lead or session:<name>", "\n".join(ledger.validate(d)))

    def test_waiting_on_lists_blocked_rows_and_open_asks_by_owner(self):
        d = minimal()
        d["items"][1]["status"] = "blocked"; d["items"][1]["owner"] = "sponsor"
        d["items"][2]["status"] = "blocked"; d["items"][2]["owner"] = "session:PhotoVault Engine"
        d["asks"][0]["owner"] = "sponsor"
        self.assertEqual(["W-02", "A-01"], ledger.waiting_on(d, "sponsor"))
        self.assertEqual(["W-03"], ledger.waiting_on(d, "session:PhotoVault Engine"))


class TestSwitches(unittest.TestCase):
    """D5: a project turns a part of the standard off, on the record."""

    def test_a_recorded_switch_is_honoured(self):
        d = minimal(switches={"issues": {"on": False, "by": "sponsor", "at": "2026-09-13T16:03", "quote": "skip GitHub issues for now"}})
        self.assertEqual([], ledger.validate(d))
        self.assertFalse(ledger.switch_on(d, "issues"))
        self.assertTrue(ledger.switch_on(d, "publish"))
        self.assertTrue(ledger.switch_on(minimal(), "issues"))

    def test_a_misspelt_switch_is_a_problem_not_silently_ignored(self):
        d = minimal(switches={"isues": {"on": False, "by": "sponsor", "at": "x"}})
        self.assertIn("switches: 'isues' is not one of issues, publish, ruflo", "\n".join(ledger.validate(d)))

    def test_off_without_who_is_a_problem(self):
        d = minimal(switches={"issues": {"on": False}})
        self.assertIn("switches.issues: off without `by` and `at`", "\n".join(ledger.validate(d)))


class TestRequests(unittest.TestCase):
    """D7: requests between sessions are rows both sides can read."""

    def req(self, **over):
        r = {"id": "RQ-01", "at": "2026-09-14", "from": "session:PhotoVault App", "to": "session:PhotoVault Engine",
             "what": "Runner data mode", "unblocks": ["W-02", "all VL5 receipts after W-02"], "state": "open"}
        r.update(over)
        return r

    def test_a_request_is_well_formed(self):
        d = minimal(requests=[self.req()])
        self.assertEqual([], ledger.validate(d))
        self.assertEqual(["RQ-01"], [r["id"] for r in ledger.open_requests(d)])

    def test_request_problems_are_named(self):
        d = minimal(requests=[self.req(id="R1"), self.req(state="waiting"), self.req(unblocks=["W-99"]),
                              self.req(id="RQ-02", state="answered")])
        text = "\n".join(ledger.validate(d))
        self.assertIn("R1: request id is not RQ-NN", text)
        self.assertIn("RQ-01: state 'waiting'", text)
        self.assertIn("unblocks W-99, which is not an item", text)
        self.assertIn("RQ-02: answered without `answered_by`", text)


class TestEvidenceAndVerify(unittest.TestCase):
    """D6: done needs evidence, and a row names its verification level."""

    def test_a_verify_level_must_be_on_the_ladder(self):
        d = minimal(verification_ladder=[{"level": "VL1"}, {"level": "VL5"}])
        d["items"][1]["verify"] = "VL5"
        self.assertEqual([], ledger.validate(d))
        d["items"][1]["verify"] = "VL9"
        self.assertIn("W-02: verify 'VL9' is not a level on the verification ladder", "\n".join(ledger.validate(d)))

    def test_done_without_declared_evidence_is_refused(self):
        d = minimal(evidence_rule={"keys": ["tests", "review"]})
        d["items"][0]["evidence"] = {"tests": True, "review": "n/a"}
        self.assertEqual([], ledger.validate(d))
        d["items"][0]["evidence"] = {"tests": True, "review": False}
        self.assertIn("W-01: done without evidence: review", "\n".join(ledger.validate(d)))
        del d["items"][0]["evidence"]
        self.assertIn("W-01: done without evidence: tests, review", "\n".join(ledger.validate(d)))

    def test_without_an_evidence_rule_nothing_is_required(self):
        self.assertEqual([], ledger.validate(minimal()))


class TestGatesFloorsReceiptsReadiness(unittest.TestCase):
    """D8: gates, floors and receipts are data; readiness is computed."""

    def test_shapes_are_checked(self):
        d = minimal(gates=[{"id": "G0", "title": "Foundation", "passed": "yes"}],
                    quality_floors=[{"title": "lint", "command": "x", "met": 1}],
                    receipts=[{"item": "Z9", "commit": "abc"}])
        text = "\n".join(ledger.validate(d))
        self.assertIn("G0: `passed` must be true or false", text)
        self.assertIn("quality_floors[0]: `met` must be true or false", text)
        self.assertIn("receipts[0]: item Z9 is neither an item id nor a `was` id", text)

    def test_a_receipt_may_name_an_old_id_through_was(self):
        d = minimal(receipts=[{"item": "F5", "commit": "abc"}])
        d["items"][0]["was"] = "F5"
        self.assertEqual([], ledger.validate(d))

    def test_merged_holds_a_commit_and_not_started_cannot_be_merged(self):
        d = minimal()
        d["items"][0]["merged"] = "4ad60f5"
        d["items"][1]["status"] = "in progress"; d["items"][1]["merged"] = "bc948a8"
        self.assertEqual([], ledger.validate(d))
        self.assertEqual(["W-02"], ledger.merged_waiting(d))
        d["items"][2]["merged"] = "e4595f9"
        self.assertIn("W-03: merged but not started", "\n".join(ledger.validate(d)))

    def test_readiness_is_none_without_declared_weights(self):
        self.assertIsNone(ledger.readiness(minimal()))

    def test_readiness_is_computed_from_the_declared_weights(self):
        d = minimal(readiness_weights={"work": 70, "gates": 15, "floors": 10, "receipts": 5},
                    gates=[{"id": "G0", "title": "a", "passed": True}, {"id": "G1", "title": "b", "passed": False}],
                    quality_floors=[{"title": "lint", "command": "x", "met": True}],
                    native_receipts={"library": True, "albums": False})
        d["items"][1]["status"] = "in progress"; d["items"][1]["evidence"] = {"tests": True}
        r = ledger.readiness(d)
        # work: done 1 + in progress with passing tests 0.5 of 3 rows = 0.5 -> 35.0; gates 1/2 -> 7.5; floors 1/1 -> 10; receipts 1/2 -> 2.5
        self.assertEqual({"work": 35.0, "gates": 7.5, "floors": 10.0, "receipts": 2.5, "readiness": 55}, r)


class TestTheRealLedgersUnderV2(unittest.TestCase):

    @unittest.skipUnless(APP_70.exists(), f"{APP_70} is not on this machine")
    def test_the_apps_converted_ledger_validates(self):
        self.assertEqual([], ledger.validate(ledger.load(APP_70)))


if __name__ == "__main__":
    unittest.main()


class TestReadinessMatchesTheAppsOwnScore(unittest.TestCase):
    """The app's tools/build_plan.py is the reference readiness; the ledger module must agree with it."""

    BUILD_PLAN = APP_70.parent.parent.parent / "tools" / "build_plan.py"

    def test_merged_code_earns_nothing_until_done(self):
        d = minimal(readiness_weights={"work": 100, "gates": 0, "floors": 0, "receipts": 0})
        d["items"][1]["status"] = "in progress"
        before = ledger.readiness(d)
        d["items"][1]["merged"] = "bc948a8"
        self.assertEqual(before, ledger.readiness(d))
        self.assertEqual(["W-02"], ledger.merged_waiting(d))

    def test_size_weights_and_primary_surfaces(self):
        d = minimal(readiness_weights={"work": 70, "gates": 15, "floors": 10, "receipts": 5},
                    size_weights={"S": 1, "M": 2, "L": 4, "XL": 8},
                    primary_surfaces=["library", "albums"],
                    native_receipts={"library": True, "albums": False, "elsewhere": True})
        for i, size in zip(d["items"], ("S", "XL", "M")):
            i["size"] = size
        d["items"][0]["status"] = "done"
        r = ledger.readiness(d)
        # work 70 * 1/11 = 6.4; receipts 5 * 1/2 over the declared surfaces only = 2.5
        self.assertEqual(6.4, r["work"])
        self.assertEqual(2.5, r["receipts"])

    @unittest.skipUnless(APP_70.exists() and BUILD_PLAN.exists(), "PhotoVault app not on this machine")
    def test_the_app_ledger_scores_the_same_as_build_plan(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("pv_build_plan", self.BUILD_PLAN)
        bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)
        plan = json.loads(APP_70.read_text())
        for i in plan["items"]:
            i.setdefault("model", bp.MODEL_FOR[i["complexity"]])
        want = bp.score(plan)
        d = dict(plan, readiness_weights={"work": 70, "gates": 15, "floors": 10, "receipts": len(bp.PRIMARY_SURFACES)},
                 size_weights=bp.SIZE_WEIGHT, primary_surfaces=list(bp.PRIMARY_SURFACES))
        got = ledger.readiness(d)
        self.assertEqual((want["work"], want["gate_pts"], want["floor_pts"], float(want["native_pts"]), want["readiness"]),
                         (got["work"], got["gates"], got["floors"], got["receipts"], got["readiness"]))



class TestDeclaredNumbersAndShapes(unittest.TestCase):
    """A hand-typed weight that is not a number is a named problem, never a traceback."""

    def weighted(self, **extra):
        return minimal(**{"readiness_weights": {"work": 70, "gates": 15, "floors": 10, "receipts": 5}, **extra})

    def test_non_numeric_weights_are_problems_and_readiness_is_none(self):
        cases = [
            (self.weighted(readiness_weights={"work": "seventy", "gates": 15, "floors": 10, "receipts": 5}),
             "readiness_weights.work: 'seventy' is not a number"),
            (self.weighted(size_weights={"S": "one"}), "size_weights.S: 'one' is not a number"),
            (self.weighted(readiness_weights={"work": True, "gates": 15, "floors": 10, "receipts": 5}),
             "readiness_weights.work: True is not a number"),
        ]
        for d, problem in cases:
            with self.subTest(problem=problem):
                self.assertIn(problem, "\n".join(ledger.validate(d)))
                self.assertIsNone(ledger.readiness(d))
        d = self.weighted()
        d["items"][0]["weight"] = "not-a-number"
        self.assertIn("W-01: weight 'not-a-number' is not a number", "\n".join(ledger.validate(d)))
        self.assertIsNone(ledger.readiness(d))

    def test_gates_floors_requests_must_be_lists_and_receipts_an_object(self):
        d = minimal(gates={"G0": {"title": "x", "passed": True}}, quality_floors="all", requests={},
                    native_receipts=["library"])
        text = "\n".join(ledger.validate(d))
        for problem in ("gates: must be a list", "quality_floors: must be a list",
                        "requests: must be a list", "native_receipts: must be an object"):
            self.assertIn(problem, text)


class TestNonFiniteAndNegativeWeights(unittest.TestCase):
    """Review round 2: json.loads accepts NaN and Infinity, and they crashed readiness()."""

    def test_nan_infinity_and_negative_weights_are_problems_and_readiness_is_none(self):
        for body, problem in (
            ('{"work": NaN, "gates": 15, "floors": 10, "receipts": 5}', "readiness_weights.work: nan is not a number"),
            ('{"work": 70, "gates": 15, "floors": 10, "receipts": Infinity}', "readiness_weights.receipts: inf is not a number"),
            ('{"work": -70, "gates": 15, "floors": 10, "receipts": 5}', "readiness_weights.work: -70 is negative"),
        ):
            with self.subTest(problem=problem):
                d = minimal(readiness_weights=json.loads(body))
                self.assertIn(problem, "\n".join(ledger.validate(d)))
                self.assertIsNone(ledger.readiness(d))
        d = minimal(readiness_weights={"work": 70, "gates": 15, "floors": 10, "receipts": 5})
        d["items"][0]["weight"] = json.loads("-Infinity")
        self.assertIn("W-01: weight -inf is not a number", "\n".join(ledger.validate(d)))
        self.assertIsNone(ledger.readiness(d))


class TestPrintedFieldsAreOneLine(unittest.TestCase):
    """V-02 review: the card prints ids, owners, switch by/at and request from/to.
    A trailing newline passed the ^...$ patterns, and by/at/from/to were only
    checked for truthiness, so a value could forge a line on the card."""

    def test_a_trailing_newline_does_not_pass_the_id_and_owner_patterns(self):
        for pattern, value in ((ledger.ITEM_ID, "Z-01\n"), (ledger.ASK_ID, "A-01\n"),
                               (ledger.REQUEST_ID, "RQ-01\n"), (ledger.OWNER, "sponsor\n"),
                               (ledger.OWNER, "session:app\nwarmup --check: ready")):
            with self.subTest(value=value):
                self.assertIsNone(pattern.match(value))

    def test_switch_and_request_text_must_be_one_line(self):
        d = minimal(switches={"issues": {"on": False, "by": "attacker\nwarmup --check: ready",
                                         "at": "2026-09-14T08:00:00+02:00"}},
                    requests=[{"id": "RQ-01", "from": "atk\x1b[2J", "to": "session:engine", "state": "open"},
                              {"id": "RQ-02", "from": "session:app", "to": "x\udc80", "state": "open"}])
        text = "\n".join(ledger.validate(d))
        self.assertIn("switches.issues: `by` must be one line of text", text)
        self.assertIn("RQ-01: `from` must be one line of text", text)
        self.assertIn("RQ-02: `to` must be one line of text", text)
