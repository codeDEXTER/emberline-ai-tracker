"""tools/ruflo.py -- Ruflo binary discovery and memory namespace, shared by
bin/ruflo-item, bin/warmup and bin/conformance (RF-01).

Before this module the two tools that needed to find the Ruflo binary each
carried their own copy: bin/ruflo-item's resolve_binary() looked at $RUFLO
then PATH; bin/warmup's ruflo_cli() looked at PATH then the npx cache,
picking by mtime. Neither alone was the full story, PATH never had
`claude-flow` or `ruflo` on it (Ruflo lives only in npm's npx cache on this
machine), and every ruflo-item call since 15 Sep exited 2 "no Ruflo binary
found" while warmup's card kept printing a path -- so the mandatory loop
never actually ran. One function, in one place, importable by every tool
that needs an answer.

BINARY RESOLUTION ORDER
  1. $RUFLO, if set -- a full command line, split with shlex (so
     RUFLO="npx -y ruflo@latest" works, the app's own wrapper's call); its
     first word must resolve to something executable (shutil.which), or
     resolution refuses, naming the word.
  2. `claude-flow` on PATH, then `ruflo` on PATH.
  3. The npx cache: every `~/.npm/_npx/<hash>/node_modules/.bin/{claude-flow,
     ruflo}`, picking the HIGHEST version, never mtime or glob order --
     several versions accumulate there over time (3.38.21, 3.41.4, ...) and
     the newest one is the one to run. A candidate's version is read from the
     nearest package.json walking up from where its symlink resolves,
     without leaving that candidate's own npx-cache directory (so a same-
     named but unrelated package -- some other tool's `claude-flow` bin
     living in a differently-scoped package inside the same npx dir --
     still gets read from ITS OWN nearest package.json, never a neighbour's).
     A candidate whose version cannot be read or parsed is skipped, never
     crashes discovery.
  Only $RUFLO may ever name `npx` itself -- this module never invokes it on
  its own initiative, since a bare `npx` call downloads a package and
  auto-starts Ruflo's daemon on its own.

No binary resolves: (None, a message naming all three places searched, so
the fix -- setting $RUFLO -- is never a guess).

NAMESPACE RESOLUTION ORDER
  1. `explicit` (a session's --namespace flag), if given.
  2. $RUFLO_NAMESPACE.
  3. `.common-rules.json`'s `ruflo_namespace` (tools/project.py validates it:
     a non-empty, one-line string).
  4. The project directory's own name -- unchanged from before this module
     existed, so a project that has never declared a namespace keeps reading
     and writing the one it always has.
"""
from __future__ import annotations

import glob
import json
import os
import shlex
import shutil
from pathlib import Path
from typing import NamedTuple

from tools import project as P

BIN_NAMES = ("claude-flow", "ruflo")


class Resolved(NamedTuple):
    argv: list[str]
    source: str  # "RUFLO" | "PATH" | "cache"


def _cache_root() -> Path:
    # Read $HOME at call time, not import time, so a test that points HOME at
    # a scratch directory sees its own fake cache.
    home = os.environ.get("HOME")
    return Path(home) if home else Path.home()


def _parse_version(value) -> tuple[int, ...] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    out = []
    for part in value.strip().split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        out.append(int(digits))
    return tuple(out) if out else None


def _version_of(bin_path: Path, npx_dir: Path) -> tuple[int, ...] | None:
    """The version in the nearest package.json walking up from where
    `bin_path` resolves, never leaving `npx_dir` (the candidate's own
    `~/.npm/_npx/<hash>` directory) -- a resolved target outside it, or no
    package.json found before reaching it, answers None."""
    try:
        target = bin_path.resolve()
        npx_dir = npx_dir.resolve()
    except OSError:
        return None
    try:
        target.relative_to(npx_dir)
    except ValueError:
        return None
    d = target.parent if target.is_file() else target
    while True:
        pkg = d / "package.json"
        if pkg.is_file():
            try:
                data = json.loads(pkg.read_text())
            except (OSError, ValueError):
                return None
            return _parse_version(data.get("version")) if isinstance(data, dict) else None
        if d == npx_dir:
            return None
        d = d.parent


def _cache_candidates() -> list[tuple[Path, tuple[int, ...]]]:
    """(bin path, version) for every usable cached binary, in a stable order."""
    root = _cache_root() / ".npm" / "_npx"
    out = []
    for name in BIN_NAMES:
        for p in sorted(glob.glob(str(root / "*" / "node_modules" / ".bin" / name))):
            path = Path(p)
            # .../<hash>/node_modules/.bin/<name> -- parents[2] is <hash>.
            npx_dir = path.parents[2]
            version = _version_of(path, npx_dir)
            if version is not None:
                out.append((path, version))
    return out


def resolve_binary() -> tuple[list[str] | None, str | None]:
    """(argv prefix, None) on success; (None, the message to print) when
    nothing usable resolves."""
    env = os.environ.get("RUFLO", "").strip()
    if env:
        try:
            parts = shlex.split(env)
        except ValueError as e:
            return None, f"$RUFLO could not be parsed as a command ({e})"
        if not parts:
            return None, "$RUFLO is empty"
        word = parts[0]
        if not shutil.which(word):
            return None, f"$RUFLO names {word!r}, which is not an executable"
        return parts, None
    for name in BIN_NAMES:
        found = shutil.which(name)
        if found:
            return [found], None
    candidates = _cache_candidates()
    if candidates:
        candidates.sort(key=lambda c: c[1], reverse=True)
        return [str(candidates[0][0])], None
    return None, (
        "no Ruflo binary found -- searched $RUFLO, claude-flow/ruflo on PATH, and the npx cache "
        f'({_cache_root() / ".npm" / "_npx"}/*/node_modules/.bin/{{claude-flow,ruflo}}) -- '
        'set RUFLO, e.g. RUFLO="npx -y ruflo@latest"'
    )


def namespace_for(project: Path, explicit: str | None = None) -> str:
    """--namespace NS when given; else $RUFLO_NAMESPACE; else
    .common-rules.json's `ruflo_namespace`; else the project directory's own
    name."""
    if explicit:
        return explicit
    env = os.environ.get("RUFLO_NAMESPACE", "").strip()
    if env:
        return env
    declared = P.declared(Path(project)).get("ruflo_namespace")
    if declared:
        return declared
    return Path(project).name
