#!/usr/bin/env python3
"""
test_sage_init.py — `sage init` produces a project a machine can actually read.

Nothing checked what `sage init` WROTE. It is the single most-run command in the
framework, and it was emitting a `.sage/config.yaml` that no YAML parser accepts.

The heredoc that writes it, `cat > "$sage_dir/config.yaml" << YAML`, has an
unquoted delimiter, and a comment inside it contained backticks around
`sage worktree`. In an unquoted heredoc, backticks are command substitution — so
bash EXECUTED `sage worktree` while initializing the project and spliced its
ANSI-coloured usage text into the config. Every Sage project on earth has one.

It went unnoticed because the only consumers read config.yaml with line regexes
rather than a YAML parser, so the corruption was invisible until something tried
to parse it. These tests make sure the next one is caught by a machine.

Usage:  python3 develop/validators/tools/test_sage_init.py
Exit:   0 = all pass | 1 = a test failed

Python 3.8+, stdlib only (PyYAML is used for a real parse when available, and its
absence never turns a failure into a pass — the structural checks always run).
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SAGE_BIN = REPO_ROOT / "bin" / "sage"
BASH = shutil.which("bash") or "bash"

ANSI = re.compile(r"\x1b\[")
# A YAML line that is not blank, not a comment, and not indented continuation.
TOP_LEVEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:")


def bash_path(path: pathlib.Path) -> str:
    """Return a path Bash can consume on both POSIX and Windows hosts."""
    return str(path).replace("\\", "/")


class SageInitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="sage-init-test-"))
        home = cls.tmp / "home"
        (home).mkdir(parents=True)
        # A framework root the way install.sh lays one out.
        shutil.copytree(REPO_ROOT, home / "framework",
                        ignore=shutil.ignore_patterns(".git", "node_modules",
                                                      "__pycache__", "dist", ".sage"))
        cls.proj = cls.tmp / "proj"
        cls.proj.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=cls.proj, check=True)

        proc = subprocess.run(
            [BASH, bash_path(SAGE_BIN), "init", "--preset", "base"],
            cwd=cls.proj, capture_output=True, text=True,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "SAGE_HOME": bash_path(home)},
        )
        cls.rc, cls.out = proc.returncode, proc.stdout + proc.stderr
        cls.config = cls.proj / ".sage" / "config.yaml"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_init_succeeds(self):
        self.assertEqual(self.rc, 0, self.out[-2000:])

    def test_config_was_written(self):
        self.assertTrue(self.config.is_file(), self.out[-1000:])

    def test_config_has_no_terminal_escape_codes(self):
        """ANSI in a config file means some command's coloured output leaked in."""
        text = self.config.read_text()
        self.assertIsNone(ANSI.search(text),
                          "ANSI escape sequence in .sage/config.yaml — a command "
                          "substituted its output into the heredoc")

    def test_config_did_not_execute_a_subcommand(self):
        """`sage worktree` was really being RUN during init, not quoted."""
        text = self.config.read_text()
        for leak in ("Usage: sage", "sage worktree remove <"):
            self.assertNotIn(leak, text,
                             f"{leak!r} in config.yaml — a backtick inside the "
                             f"unquoted heredoc ran as a command")

    def test_config_is_parseable_yaml(self):
        text = self.config.read_text()
        try:
            import yaml
        except ImportError:
            # No parser here — fall back to a structural check rather than
            # skipping, so a missing library can never read as a pass.
            for i, line in enumerate(text.splitlines(), 1):
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if line[0].isspace():
                    continue          # a continuation / nested mapping
                self.assertRegex(line, TOP_LEVEL,
                                 f"line {i} is neither blank, comment, nor key: {line!r}")
            return
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as exc:
            self.fail(f".sage/config.yaml is not valid YAML: "
                      f"{str(exc).splitlines()[0]}")

    def test_version_is_stamped_from_the_VERSION_file(self):
        """Not a literal. bin/sage hardcoded 1.0.0 here while VERSION said 1.2.0,
        so every project misreported the Sage it was running."""
        version = (REPO_ROOT / "VERSION").read_text().strip()
        self.assertIn(f'sage-version: "{version}"', self.config.read_text())


class SageHermesPlatformTest(unittest.TestCase):
    """Hermes is a real Sage CLI platform, not a manual generator path."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="sage-hermes-init-test-"))
        home = cls.tmp / "home"
        home.mkdir(parents=True)
        shutil.copytree(REPO_ROOT, home / "framework",
                        ignore=shutil.ignore_patterns(".git", "node_modules",
                                                      "__pycache__", "dist", ".sage"))
        cls.hermes_home = cls.tmp / "hermes"
        cls.hermes_home.mkdir()
        fake_bin = cls.tmp / "bin"
        fake_bin.mkdir()
        fake_hermes = fake_bin / "hermes"
        fake_hermes.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        fake_hermes.chmod(0o755)

        cls.proj = cls.tmp / "proj"
        cls.proj.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=cls.proj, check=True)
        cls.env = {
            **os.environ,
            "SAGE_HOME": bash_path(home),
            "HERMES_HOME": bash_path(cls.hermes_home),
            "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
        }
        cls.init = subprocess.run(
            [BASH, bash_path(SAGE_BIN), "init", "--preset", "base",
             "--no-memory", "--platform", "hermes"],
            cwd=cls.proj, capture_output=True, text=True,
            stdin=subprocess.DEVNULL, env=cls.env,
        )
        cls.help = subprocess.run(
            [BASH, bash_path(SAGE_BIN), "help"],
            capture_output=True, text=True, env=cls.env,
        )
        cls.config = cls.proj / ".sage" / "config.yaml"
        cls.profile_config = cls.hermes_home / "config.yaml"
        cls.first_profile_config = (
            cls.profile_config.read_text(encoding="utf-8")
            if cls.profile_config.is_file() else ""
        )
        cls.installed_plugin = cls.hermes_home / "plugins" / "sage"
        (cls.installed_plugin / "__init__.py").write_text(
            "STALE_ADAPTER\n", encoding="utf-8"
        )
        (cls.installed_plugin / "plugin.yaml").write_text(
            "name: stale\n", encoding="utf-8"
        )
        cls.installed_deep_plugin_file = (
            cls.installed_plugin / "runtime" / "tools" / "skill_manager.py"
        )
        cls.installed_deep_plugin_file.write_text(
            "STALE_DEEP_PLUGIN\n", encoding="utf-8"
        )
        cls.update = subprocess.run(
            [BASH, bash_path(SAGE_BIN), "update", "--no-memory",
             "--platform", "hermes"],
            cwd=cls.proj, capture_output=True, text=True,
            stdin=subprocess.DEVNULL, env=cls.env,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_init_accepts_hermes(self):
        self.assertEqual(self.init.returncode, 0,
                         (self.init.stdout + self.init.stderr)[-4000:])

    def test_help_lists_hermes_as_a_platform(self):
        self.assertEqual(self.help.returncode, 0, self.help.stderr)
        self.assertRegex(self.help.stdout, r"--platform .*\bhermes\b")

    def test_selection_is_persisted(self):
        self.assertTrue(self.config.is_file())
        self.assertIn('platforms: ["hermes"]', self.config.read_text())

    def test_hermes_generator_is_dispatched(self):
        self.assertTrue((self.proj / "SOUL.md").is_file())
        self.assertTrue((self.hermes_home / "plugins" / "sage" /
                         "plugin.yaml").is_file())
        self.assertIn("sage-hermes-gate.sh", self.first_profile_config)

    def test_init_emits_no_internal_command_or_path_errors(self):
        errors = self.init.stderr + self.update.stderr
        self.assertNotIn("command not found", errors)
        self.assertNotIn("can't open file", errors)
        self.assertNotIn("tr: warning", errors)

    def test_update_accepts_hermes_and_is_idempotent(self):
        self.assertEqual(self.update.returncode, 0,
                         (self.update.stdout + self.update.stderr)[-4000:])
        updated = self.profile_config.read_text(encoding="utf-8")
        entry = re.compile(r"sage-hermes-gate\.sh\\?\"?\s+sage-[\w-]+\.sh")
        self.assertEqual(len(entry.findall(updated)), 11, updated)

    def test_update_refreshes_existing_plugin_from_framework(self):
        self.assertEqual(
            (self.installed_plugin / "__init__.py").read_bytes(),
            (REPO_ROOT / "__init__.py").read_bytes(),
        )
        self.assertEqual(
            (self.installed_plugin / "plugin.yaml").read_bytes(),
            (REPO_ROOT / "plugin.yaml").read_bytes(),
        )
        self.assertEqual(
            self.installed_deep_plugin_file.read_bytes(),
            (REPO_ROOT / "runtime" / "tools" / "skill_manager.py").read_bytes(),
        )

    def test_update_refuses_stale_git_managed_plugin(self):
        git_marker = self.installed_plugin / ".git"
        deep_file = self.installed_deep_plugin_file
        original = deep_file.read_bytes()
        git_marker.mkdir()
        deep_file.write_text("STALE_DEEP_PLUGIN\n", encoding="utf-8")
        try:
            update = subprocess.run(
                [BASH, bash_path(SAGE_BIN), "update", "--no-memory",
                 "--platform", "hermes"],
                cwd=self.proj, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, env=self.env, check=False,
            )
            output = update.stdout + update.stderr
            self.assertNotEqual(update.returncode, 0, output[-4000:])
            self.assertEqual(deep_file.read_text(encoding="utf-8"),
                             "STALE_DEEP_PLUGIN\n")
            self.assertIn("Refusing to overwrite Git-managed plugin", output)
        finally:
            shutil.rmtree(git_marker, ignore_errors=True)
            deep_file.write_bytes(original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
