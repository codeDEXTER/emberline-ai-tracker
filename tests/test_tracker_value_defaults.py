"""Value defaults per surface (proposal 25, Z-03).

`.common-rules.json` may declare `value_defaults`: {cluster: high|medium|low}.
An item with no `value` of its own takes its cluster's default; an item's own
value always wins.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import project as P  # noqa: E402
from tools.tracker import sizing as S  # noqa: E402


class DeclaredProject(unittest.TestCase):
    def project(self, declaration) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / P.FILE).write_text(json.dumps(declaration))
        return root


class TestDeclaration(DeclaredProject):
    def test_well_formed_defaults_are_declared(self):
        root = self.project({"value_defaults": {"tracker": "high", "docs": "low"}})
        self.assertEqual(P.problems(root), [])
        self.assertEqual(P.load(root)["value_defaults"], {"tracker": "high", "docs": "low"})

    def test_default_is_empty(self):
        root = self.project({})
        self.assertEqual(P.load(root)["value_defaults"], {})

    def test_bad_declarations_are_named(self):
        for bad in (["tracker"], {"tracker": "urgent"}, {"tracker": 3}, {"": "high"}, {"a\nb": "low"}):
            root = self.project({"value_defaults": bad})
            problems = P.problems(root)
            self.assertTrue(any("value_defaults" in p for p in problems), (bad, problems))
            self.assertEqual(P.load(root)["value_defaults"], {}, bad)

    def test_common_rules_declares_its_own(self):
        declared = P.declared(ROOT)
        self.assertIn("value_defaults", declared)
        self.assertEqual(P.problems(ROOT), [])


class TestEffectiveValue(unittest.TestCase):
    DEFAULTS = {"tracker": "high", "docs": "low"}

    def test_cluster_default_applies(self):
        self.assertEqual(S.effective_value({"cluster": "docs"}, self.DEFAULTS), ("low", "default for docs"))

    def test_own_value_overrides_the_default(self):
        self.assertEqual(S.effective_value({"cluster": "docs", "value": "high"}, self.DEFAULTS), ("high", "item"))

    def test_no_value_and_no_default_is_none(self):
        self.assertEqual(S.effective_value({"cluster": "other"}, self.DEFAULTS), (None, "unsized"))
        self.assertEqual(S.effective_value({}, self.DEFAULTS), (None, "unsized"))


if __name__ == "__main__":
    unittest.main()
