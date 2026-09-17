"""tools/ruflo.py -- the one Ruflo binary/namespace resolver, shared by
bin/ruflo-item, bin/warmup and bin/conformance (RF-01).

Never calls a real Ruflo binary: PATH is scrubbed of claude-flow/ruflo in
every case here, and the npx cache is a fake tree under a scratch $HOME.

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def RU():
    from tools import ruflo
    return ruflo


class Scratch(unittest.TestCase):
    """A scratch $HOME (for the npx cache) and a scrubbed $PATH/$RUFLO/
    $RUFLO_NAMESPACE, restored in tearDown."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self._env = dict(os.environ)
        os.environ["HOME"] = str(self.home)
        os.environ["PATH"] = "/usr/bin:/bin"  # no claude-flow, no ruflo
        os.environ.pop("RUFLO", None)
        os.environ.pop("RUFLO_NAMESPACE", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self.tmp.cleanup()

    def cache_binary(self, ns_hash: str, version: str, pkg_name: str = "claude-flow",
                     bin_name: str = "claude-flow") -> Path:
        """A fake `~/.npm/_npx/<ns_hash>/node_modules/<pkg_name>` package at
        `version`, with `.bin/<bin_name>` symlinked into its own bin/cli.js --
        the real cache's own shape."""
        pkg_dir = self.home / ".npm" / "_npx" / ns_hash / "node_modules" / pkg_name
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "package.json").write_text(json.dumps({"name": pkg_name, "version": version}))
        (pkg_dir / "bin").mkdir()
        cli = pkg_dir / "bin" / "cli.js"
        cli.write_text("#!/usr/bin/env node\n")
        cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
        bindir = self.home / ".npm" / "_npx" / ns_hash / "node_modules" / ".bin"
        bindir.mkdir(parents=True, exist_ok=True)
        link = bindir / bin_name
        link.symlink_to(Path("..") / pkg_name / "bin" / "cli.js")
        return link


class TestCacheDiscovery(Scratch):

    def test_picks_the_highest_version_not_glob_or_mtime_order(self):
        # Written in an order that would mislead a glob-order or mtime pick:
        # the lowest version is created last (newest mtime), and its hash
        # sorts before the highest version's hash alphabetically.
        low = self.cache_binary("aaa-low", "3.38.21")
        high = self.cache_binary("zzz-high", "3.41.4")
        argv, err = RU().resolve_binary()
        self.assertIsNone(err, err)
        self.assertEqual(argv, [str(high)])
        self.assertNotEqual(argv, [str(low)])

    def test_a_candidate_with_unreadable_version_is_skipped_not_crashed(self):
        good = self.cache_binary("good", "3.41.4")
        broken_dir = self.home / ".npm" / "_npx" / "broken" / "node_modules" / "claude-flow"
        broken_dir.mkdir(parents=True)
        (broken_dir / "package.json").write_text("{not valid json")
        (broken_dir / "bin").mkdir()
        (broken_dir / "bin" / "cli.js").write_text("x")
        bindir = self.home / ".npm" / "_npx" / "broken" / "node_modules" / ".bin"
        bindir.mkdir(parents=True)
        (bindir / "claude-flow").symlink_to(Path("..") / "claude-flow" / "bin" / "cli.js")
        argv, err = RU().resolve_binary()
        self.assertIsNone(err, err)
        self.assertEqual(argv, [str(good)])

    def test_the_ruflo_named_binary_is_also_found(self):
        link = self.cache_binary("hash1", "3.41.4", pkg_name="ruflo", bin_name="ruflo")
        argv, err = RU().resolve_binary()
        self.assertIsNone(err, err)
        self.assertEqual(argv, [str(link)])

    def test_no_cache_and_nothing_on_path_names_all_three_places(self):
        argv, err = RU().resolve_binary()
        self.assertIsNone(argv)
        self.assertIn("$RUFLO", err)
        self.assertIn("PATH", err)
        self.assertIn("npx", err.lower())
        self.assertIn("claude-flow", err)


class TestRufloEnvWins(Scratch):

    def test_ruflo_env_wins_over_cache(self):
        self.cache_binary("hash1", "9.9.9")
        fake = self.home / "my-ruflo"
        fake.write_text("#!/bin/sh\nexit 0\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        os.environ["RUFLO"] = str(fake)
        argv, err = RU().resolve_binary()
        self.assertIsNone(err, err)
        self.assertEqual(argv, [str(fake)])

    def test_ruflo_env_wins_over_path(self):
        fake_path_dir = self.home / "fakebin"
        fake_path_dir.mkdir()
        path_fake = fake_path_dir / "claude-flow"
        path_fake.write_text("#!/bin/sh\nexit 0\n")
        path_fake.chmod(path_fake.stat().st_mode | stat.S_IEXEC)
        os.environ["PATH"] = f"{fake_path_dir}:/usr/bin:/bin"

        env_fake = self.home / "env-ruflo"
        env_fake.write_text("#!/bin/sh\nexit 0\n")
        env_fake.chmod(env_fake.stat().st_mode | stat.S_IEXEC)
        os.environ["RUFLO"] = str(env_fake)

        argv, err = RU().resolve_binary()
        self.assertIsNone(err, err)
        self.assertEqual(argv, [str(env_fake)])

    def test_a_nonexistent_ruflo_word_refuses_naming_it(self):
        os.environ["RUFLO"] = "/no/such/ruflo-binary --flag"
        argv, err = RU().resolve_binary()
        self.assertIsNone(argv)
        self.assertIn("/no/such/ruflo-binary", err)
        self.assertIn("is not an executable", err)

    def test_path_wins_over_cache(self):
        self.cache_binary("hash1", "9.9.9")
        fake_path_dir = self.home / "fakebin"
        fake_path_dir.mkdir()
        path_fake = fake_path_dir / "claude-flow"
        path_fake.write_text("#!/bin/sh\nexit 0\n")
        path_fake.chmod(path_fake.stat().st_mode | stat.S_IEXEC)
        os.environ["PATH"] = f"{fake_path_dir}:/usr/bin:/bin"
        argv, err = RU().resolve_binary()
        self.assertIsNone(err, err)
        self.assertEqual(argv, [str(path_fake)])


class TestNamespace(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self._env = dict(os.environ)
        os.environ.pop("RUFLO_NAMESPACE", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self.tmp.cleanup()

    def write_declaration(self, ns):
        (self.root / ".common-rules.json").write_text(json.dumps({"ruflo_namespace": ns}))

    def test_defaults_to_directory_name(self):
        self.assertEqual("proj", RU().namespace_for(self.root))

    def test_declared_namespace_is_read(self):
        self.write_declaration("patterns")
        self.assertEqual("patterns", RU().namespace_for(self.root))

    def test_env_var_wins_over_declaration(self):
        self.write_declaration("patterns")
        os.environ["RUFLO_NAMESPACE"] = "from-env"
        self.assertEqual("from-env", RU().namespace_for(self.root))

    def test_explicit_wins_over_everything(self):
        self.write_declaration("patterns")
        os.environ["RUFLO_NAMESPACE"] = "from-env"
        self.assertEqual("from-flag", RU().namespace_for(self.root, "from-flag"))

    def test_a_malformed_declaration_falls_back_to_the_directory_name(self):
        (self.root / ".common-rules.json").write_text("{not valid json")
        self.assertEqual("proj", RU().namespace_for(self.root))


if __name__ == "__main__":
    unittest.main()
