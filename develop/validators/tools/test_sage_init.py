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

import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SAGE_BIN = REPO_ROOT / "bin" / "sage"

ANSI = re.compile(r"\x1b\[")
# A YAML line that is not blank, not a comment, and not indented continuation.
TOP_LEVEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:")


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
            ["bash", str(SAGE_BIN), "init", "--preset", "base"],
            cwd=cls.proj, capture_output=True, text=True,
            stdin=subprocess.DEVNULL,
            env={**__import__("os").environ, "SAGE_HOME": str(home)},
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
