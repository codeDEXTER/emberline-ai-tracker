"""The project declaration: `.common-rules.json` (proposal 20, D9).

The standard used to assume every project reads HANDOFF.md first, keeps its
prohibitions under a HANDOFF heading containing "prohibition", and has one
test gate. The PhotoVault app does none of that -- CLAUDE.md is its entry
point, its safety rules sit under "## Hard safety rules", and it has a quick
gate and a merge gate -- so its warm card said "Prohibitions: none found" over
five NEVER rules, and its warm-up pointer contradicted its own read order. A
project now says where its entry points are, and the tools read that.

THE FILE -- `.common-rules.json` at the project root, beside
`.common-rules-version`. A JSON object. Every key is optional, and a key this
module does not know is ignored, because later proposals add keys.

  "read_order":   ["CLAUDE.md", "SPONSOR-CONSTRAINTS.md"]
      Files a session reads first, in order, relative to the root.
      Default: ["HANDOFF.md", "docs/OPERATING-RULES.md"].
  "safety_rules": "CLAUDE.md#Hard safety rules"     (or a list of these)
      FILE#heading: the `## ` section of FILE whose heading text contains
      `heading`, case-insensitive. Its list items and bold-numbered lines are
      the card's prohibitions, verbatim. Split at the first "#".
      Default: "HANDOFF.md#prohibition".
  "gates":        {"quick": "<cmd>", "merge": "<cmd>"}
      merge is what bin/land runs before it lands; quick is the gate an agent
      runs. Default: {}. With no gates.merge here, the first non-blank,
      non-comment line of `.common-rules-test` is gates.merge -- that file
      keeps working. A blank or null command counts as not declared.
  "plan_check":   "<cmd>"   the project's own plan checker. Default: None.
  "plan_page":    "<cmd>"   the project's own page generator. Default: None.

WHO READS IT
  bin/land test_cmd()  gates.merge, else .common-rules-test, else a guess from
                       the tree. It is bash and must stay self-contained, so it
                       carries its own few lines of json reading; test_command()
                       below is its twin, and tests pin the two equal.
  bin/warmup           read_order, safety_rules, gates, and problems().
  tools/migrate.py     read_order, for the pointer it writes into CLAUDE.md.

A BROKEN DECLARATION. load() never raises: a file that is not valid JSON, or
not an object, gives the defaults, and a value of the wrong type leaves that
key's default standing. problems() names each one, and warm-up's --check
fails on them. land does not fall back: a declaration it cannot read runs
`false  # .common-rules.json is not valid JSON` and refuses, because falling
back would silently run a gate nobody declared.

  load(project)      -> dict       the declaration merged over the defaults
  declared(project)  -> dict       only the keys the file validly declares
  problems(project)  -> list[str]  what is wrong with the declaration
  test_command(project) -> str     what bin/land's test_cmd() answers
"""
from __future__ import annotations

import copy
import glob
import json
from pathlib import Path

FILE = ".common-rules.json"
TEST_FILE = ".common-rules-test"
GATES = ("quick", "merge")
COMMANDS = ("plan_check", "plan_page")

DEFAULTS: dict = {
    "read_order": ["HANDOFF.md", "docs/OPERATING-RULES.md"],
    "safety_rules": "HANDOFF.md#prohibition",
    "gates": {},
    "plan_check": None,
    "plan_page": None,
}

INVALID, NOT_OBJECT = "invalid", "not an object"


def _raw(project: Path) -> tuple[dict | None, str | None]:
    """(the parsed object, None) · (None, INVALID | NOT_OBJECT) · (None, None) when there is no file."""
    path = Path(project) / FILE
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_bytes())
    except (OSError, ValueError):  # UnicodeDecodeError is a ValueError
        return None, INVALID
    if not isinstance(data, dict):
        return None, NOT_OBJECT
    return data, None


def _is_path(value) -> bool:
    # A path is one line: the value is printed on the card and written into
    # CLAUDE.md, where a newline would let it become a line of its own.
    return isinstance(value, str) and bool(value.strip()) and not any(ord(c) < 32 for c in value)


def _command(value) -> tuple[str | None, bool]:
    """(the command or None when not declared, whether the value was well-typed)."""
    if value is None:
        return None, True
    if isinstance(value, str):
        return (value.strip() or None), True
    return None, False


def _checked(data: dict) -> tuple[dict, list[str]]:
    ok: dict = {}
    bad: list[str] = []
    if "read_order" in data:
        v = data["read_order"]
        if isinstance(v, list) and all(_is_path(x) for x in v):
            ok["read_order"] = list(v)
        else:
            bad.append(f"{FILE}: read_order must be a list of file paths, relative to the project root")
    if "safety_rules" in data:
        v = data["safety_rules"]
        if isinstance(v, str) or (isinstance(v, list) and all(isinstance(x, str) for x in v)):
            ok["safety_rules"] = copy.deepcopy(v)
        else:
            bad.append(f'{FILE}: safety_rules must be "FILE#heading", or a list of them')
    if "gates" in data:
        v = data["gates"]
        if not isinstance(v, dict):
            bad.append(f'{FILE}: gates must be an object, like {{"quick": "<cmd>", "merge": "<cmd>"}}')
        else:
            gates = {}
            for name in GATES:
                cmd, typed = _command(v.get(name))
                if not typed:
                    bad.append(f"{FILE}: gates.{name} must be a command string")
                elif cmd:
                    gates[name] = cmd
            ok["gates"] = gates
    for key in COMMANDS:
        if key in data:
            cmd, typed = _command(data[key])
            if not typed:
                bad.append(f"{FILE}: {key} must be a command string")
            elif cmd:
                ok[key] = cmd
    return ok, bad


def declared(project: Path) -> dict:
    """Only what the file validly declares; {} when there is no usable file."""
    data, _why = _raw(project)
    return _checked(data)[0] if data is not None else {}


def test_file_command(project: Path) -> str | None:
    """The first non-blank, non-comment line of .common-rules-test, stripped."""
    path = Path(project) / TEST_FILE
    if not path.is_file():
        return None
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def load(project: Path) -> dict:
    d = copy.deepcopy(DEFAULTS)
    d.update(declared(project))
    if not d["gates"].get("merge"):
        merge = test_file_command(project)
        if merge:
            d["gates"]["merge"] = merge
    return d


def safety_sources(value) -> list[tuple[str, str]]:
    """(file, heading) for each well-formed FILE#heading in a safety_rules value."""
    specs = [value] if isinstance(value, str) else [s for s in (value or []) if isinstance(s, str)]
    out = []
    for spec in specs:
        rel, sep, heading = spec.partition("#")
        if sep and rel.strip() and heading.strip():
            out.append((rel.strip(), heading.strip()))
    return out


def problems(project: Path) -> list[str]:
    data, why = _raw(project)
    if why == INVALID:
        return [f"{FILE} is not valid JSON -- fix it; until then the defaults apply and land refuses"]
    if why == NOT_OBJECT:
        return [f"{FILE} is not a JSON object -- fix it; until then the defaults apply and land refuses"]
    if data is None:
        return []
    ok, bad = _checked(data)
    root = Path(project)
    for rel in ok.get("read_order", []):
        if not (root / rel).is_file():
            bad.append(f"{FILE}: read_order names {rel}, which does not exist")
    if "safety_rules" in ok:
        v = ok["safety_rules"]
        for spec in ([v] if isinstance(v, str) else v):
            found = safety_sources(spec)
            if not found:
                bad.append(f"{FILE}: safety_rules entry {spec!r} is not FILE#heading")
            elif not (root / found[0][0]).is_file():
                bad.append(f"{FILE}: safety_rules names {found[0][0]}, which does not exist")
    return bad


def test_command(project: Path) -> str:
    """bin/land's test_cmd(), in the same order: gates.merge from
    .common-rules.json, then .common-rules-test, then the guess from the tree.
    A declaration that cannot be read is a refusal, never a fall-back."""
    root = Path(project)
    _data, why = _raw(root)
    if why == INVALID:
        return f"false  # {FILE} is not valid JSON"
    if why == NOT_OBJECT:
        return f"false  # {FILE} is not a JSON object"
    merge = declared(root).get("gates", {}).get("merge") or test_file_command(root)
    if merge:
        return merge
    if (root / "tests").is_dir() and glob.glob(str(root / "tests" / "*.py")):
        return "python3 -m unittest discover -s tests -q"
    pkg = root / "package.json"
    if pkg.is_file() and '"test"' in pkg.read_text(errors="replace"):
        return "npm test --silent"
    return ""
