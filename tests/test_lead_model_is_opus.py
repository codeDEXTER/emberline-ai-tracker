"""The lead runs on Opus, at low or medium effort (proposal 23, A-22).

The sponsor's ruling on 2026-09-16, with the reason he gave in the same
breath: "and i think leads should be atleact Opus with low of medium effort"
/ "we are finding too many gaps if sonnet is the lead".

This is the counterpart to, not a contradiction of, HANDOFF.md's older rule
that no subagent a lead dispatches uses Opus: the subagents stay Haiku and
Sonnet by tier, the lead session doing the planning, merging, reconciling
and closing runs on Opus.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import glob
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def ledgers() -> list[tuple[str, dict]]:
    out = []
    for p in sorted(glob.glob(str(ROOT / "docs" / "proposals" / "[0-9]*.json"))):
        try:
            out.append((Path(p).name, json.loads(Path(p).read_text())))
        except ValueError:
            continue
    return out


class TestTemplateC4(unittest.TestCase):

    def test_the_template_routes_c4_to_opus(self):
        """A new proposal created from the template inherits the ruling --
        this is the row every later ledger is copied from."""
        t = json.loads((ROOT / "templates" / "ledger.json").read_text())
        c4 = t["tiers"]["C4"]
        self.assertEqual("opus", c4["model"])
        self.assertEqual("low or medium", c4["effort"])

    def test_the_template_does_not_route_c4_to_sonnet_or_a_placeholder(self):
        """Guards the two shapes this row has actually had: the stale
        'sonnet' that C3 still legitimately carries, and the 'lead model'
        placeholder that named no model at all."""
        c4 = json.loads((ROOT / "templates" / "ledger.json").read_text())["tiers"]["C4"]
        self.assertNotIn(c4["model"], ("sonnet", "haiku", "lead model", "lead"))


class TestEveryLedgerAgrees(unittest.TestCase):

    def test_no_ledger_still_routes_c4_anywhere_but_opus(self):
        bad = []
        for name, d in ledgers():
            c4 = (d.get("tiers") or {}).get("C4")
            if c4 is not None and c4.get("model") != "opus":
                bad.append(f"{name}: C4 model {c4.get('model')!r}")
        self.assertEqual([], bad)

    def test_no_c4_item_carries_a_non_opus_model(self):
        """An item's own model must agree with its tier -- the validator
        enforces that, but only against whatever the tier happens to say, so
        pin the actual value here too."""
        bad = []
        for name, d in ledgers():
            for it in d.get("items") or []:
                if it.get("cx") == "C4" and it.get("model") not in (None, "opus"):
                    if not it.get("model_override_reason"):
                        bad.append(f"{name}: {it['id']} model {it.get('model')!r}")
        self.assertEqual([], bad)


class TestTheRuleIsWrittenDown(unittest.TestCase):
    """A tier table nobody can trace back to a ruling is a number without a
    reason; the ruling and its why live in HANDOFF.md."""

    def setUp(self):
        self.handoff = (ROOT / "HANDOFF.md").read_text()

    def test_handoff_states_the_lead_runs_on_opus(self):
        self.assertIn("Opus", self.handoff)
        self.assertRegex(self.handoff, r"lead.{0,80}Opus|Opus.{0,80}lead")

    def test_handoff_keeps_the_sponsors_own_words_and_his_reason(self):
        self.assertIn("too many gaps if sonnet is the lead", self.handoff)

    def test_the_subagent_rule_is_not_lost_to_this_one(self):
        """The older no-Opus-for-subagents ruling still stands; this test
        fails if a later edit resolves the apparent tension by deleting it."""
        self.assertIn("No subagent this lead session dispatches uses Opus", self.handoff)


if __name__ == "__main__":
    unittest.main()
