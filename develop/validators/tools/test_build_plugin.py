#!/usr/bin/env python3
"""
test_build_plugin.py — tests for runtime/tools/build_plugin.py (30-§4).

Two checks:
  1. `--check` is green — the generator reproduces the committed mirror.
  2. the drift reporter flags a divergence with the offending file named.

The drift reporter is unit-tested against synthetic temp trees so the test
never mutates the real repo.

Usage:  python3 develop/validators/tools/test_build_plugin.py
Exit:   0 = all pass | 1 = a test failed

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
BUILD_PY = REPO_ROOT / "runtime" / "tools" / "build_plugin.py"

spec = importlib.util.spec_from_file_location("build_plugin", BUILD_PY)
build_plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_plugin)


class BuildPluginTest(unittest.TestCase):
    def test_check_is_green(self):
        """The generator reproduces tools/sage-claude-plugin/ exactly."""
        self.assertEqual(build_plugin.check(), 0)

    def test_real_build_substitutes_version(self):
        out = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        build_plugin.build(out)
        version = build_plugin.read_version()
        for name in ("plugin.json", "marketplace.json"):
            text = (out / ".claude-plugin" / name).read_text()
            self.assertIn(f'"version": "{version}"', text)
            self.assertNotIn(build_plugin.VERSION_PLACEHOLDER, text)

    def test_diff_reports_a_modified_file(self):
        a = pathlib.Path(tempfile.mkdtemp())
        b = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, a, ignore_errors=True)
        self.addCleanup(shutil.rmtree, b, ignore_errors=True)
        (a / "sub").mkdir()
        (b / "sub").mkdir()
        (a / "sub" / "f.md").write_text("one\n")
        (b / "sub" / "f.md").write_text("two\n")  # differs
        drift = []
        build_plugin._diff(a, b, "", drift)
        self.assertTrue(any("sub/f.md" in d and "differs" in d for d in drift), drift)

    def test_diff_reports_extra_and_missing_files(self):
        a = pathlib.Path(tempfile.mkdtemp())
        b = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, a, ignore_errors=True)
        self.addCleanup(shutil.rmtree, b, ignore_errors=True)
        (a / "only_generated.md").write_text("x")
        (b / "only_mirror.md").write_text("y")
        drift = []
        build_plugin._diff(a, b, "", drift)
        self.assertTrue(any("only in generated" in d and "only_generated.md" in d for d in drift), drift)
        self.assertTrue(any("only in mirror" in d and "only_mirror.md" in d for d in drift), drift)


if __name__ == "__main__":
    unittest.main(verbosity=2)
