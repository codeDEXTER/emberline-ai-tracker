"""Risk class from the paths an item touches (proposal 25, Z-04).

A project declares `risk_paths` in `.common-rules.json`:
  {"restricted": [glob, ...], "elevated": [glob, ...]}
Any path matching a restricted glob makes the item restricted; else any
matching an elevated glob makes it elevated; else standard. A project that
declares `"risk_always": "restricted"` -- common-rules does (D4) -- is
restricted whatever the paths.

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
from tools.tracker import risk  # noqa: E402

# Shaped after the real projects: finance-tracker's book, the PhotoVault
# library code, auth and release paths.
FIXTURE = {
    "risk_paths": {
        "restricted": ["finance_data/*", "src/money/*", "*/auth/*", "release/*", "Sources/Library/*"],
        "elevated": ["shared/*", "tools/common/*"],
    }
}


class Project(unittest.TestCase):
    def project(self, declaration) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / P.FILE).write_text(json.dumps(declaration))
        return root


class TestClassify(Project):
    def test_restricted_paths(self):
        root = self.project(FIXTURE)
        for path in ("finance_data/book.json", "src/money/fx.py", "app/auth/login.swift",
                     "release/notes.md", "Sources/Library/Store.swift"):
            self.assertEqual(risk.classify(root, [path])[0], "restricted", path)

    def test_elevated_paths(self):
        root = self.project(FIXTURE)
        for path in ("shared/format.py", "tools/common/io.py"):
            self.assertEqual(risk.classify(root, [path])[0], "elevated", path)

    def test_everything_else_is_standard(self):
        root = self.project(FIXTURE)
        self.assertEqual(risk.classify(root, ["docs/README.md", "ui/Button.swift"])[0], "standard")

    def test_the_highest_class_wins(self):
        root = self.project(FIXTURE)
        self.assertEqual(risk.classify(root, ["docs/a.md", "shared/b.py", "finance_data/c"])[0], "restricted")
        self.assertEqual(risk.classify(root, ["docs/a.md", "shared/b.py"])[0], "elevated")

    def test_the_reason_names_the_path_and_glob(self):
        root = self.project(FIXTURE)
        level, why = risk.classify(root, ["finance_data/book.json"])
        self.assertIn("finance_data/book.json", why)
        self.assertIn("finance_data/*", why)

    def test_no_declaration_is_standard(self):
        root = self.project({})
        self.assertEqual(risk.classify(root, ["finance_data/book.json"])[0], "standard")

    def test_risk_always_wins(self):
        root = self.project({"risk_always": "restricted"})
        level, why = risk.classify(root, ["docs/README.md"])
        self.assertEqual(level, "restricted")
        self.assertIn("risk_always", why)
        self.assertEqual(risk.classify(root, [])[0], "restricted")

    def test_common_rules_is_always_restricted(self):
        for paths in ([], ["README.md"], ["tests/test_x.py"], ["bin/tracker"]):
            self.assertEqual(risk.classify(ROOT, paths)[0], "restricted", paths)


class TestDeclaration(Project):
    def test_well_formed_is_clean(self):
        self.assertEqual(P.problems(self.project(FIXTURE)), [])
        self.assertEqual(P.problems(self.project({"risk_always": "elevated"})), [])

    def test_bad_declarations_are_named(self):
        for bad in ({"risk_paths": ["x"]}, {"risk_paths": {"high": ["x"]}},
                    {"risk_paths": {"restricted": "x"}}, {"risk_paths": {"restricted": [""]}},
                    {"risk_paths": {"restricted": ["a\nb"]}}, {"risk_always": "high"}):
            problems = P.problems(self.project(bad))
            self.assertTrue(any("risk_" in p for p in problems), (bad, problems))


if __name__ == "__main__":
    unittest.main()
