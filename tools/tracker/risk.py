"""Risk class from the paths an item touches (proposal 25, Z-04).

  classify(project, paths) -> (standard | elevated | restricted, why)

The project declares, in `.common-rules.json` (tools/project.py checks it):

  "risk_paths":  {"restricted": [glob, ...], "elevated": [glob, ...]}
  "risk_always": "restricted"

A glob is matched against the path relative to the project root with
fnmatch, so `*` also crosses `/`: `finance_data/*` covers the whole book.
The highest class any path reaches wins. `risk_always` sets a floor that no
path can lower -- common-rules declares "restricted", because every change
to the shared rules is (proposal 25, D4). Nothing declared: standard.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

from tools import project as P

ORDER = ("standard", "elevated", "restricted")


def classify(project, paths) -> tuple[str, str]:
    declared = P.load(Path(project))
    always = declared.get("risk_always")
    if always == "restricted":
        return "restricted", "risk_always: restricted in .common-rules.json"
    level, why = "standard", "no declared risk path matched"
    table = declared.get("risk_paths") or {}
    for path in paths or []:
        for cls in ("restricted", "elevated"):
            if ORDER.index(cls) <= ORDER.index(level):
                break
            glob = next((g for g in table.get(cls, []) if fnmatch.fnmatchcase(path, g)), None)
            if glob:
                level, why = cls, f"{path} matches {cls} path {glob}"
                break
    if always and ORDER.index(always) > ORDER.index(level):
        return always, f"risk_always: {always} in .common-rules.json"
    return level, why
