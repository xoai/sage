#!/usr/bin/env python3
"""
test_release.py — tests for runtime/tools/release.py (30-verification §4).

Builds throwaway fixture trees in a temp dir and runs release.py against them
with --repo-root, so the real repo is never touched.

Usage:  python3 develop/validators/tools/test_release.py
Exit:   0 = all pass   |   1 = a test failed

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
RELEASE_PY = REPO_ROOT / "runtime" / "tools" / "release.py"

PLUGIN_JSON = """{
  "name": "sage",
  "version": "%s",
  "description": "test fixture"
}
"""

MARKETPLACE_JSON = """{
  "name": "sage",
  "plugins": [
    {
      "name": "sage",
      "version": "%s"
    }
  ]
}
"""

CHANGELOG = """# Changelog

## [%s] — Test entry

- something
"""


def build_tree(root: pathlib.Path, version="1.2.3", plugin_version=None,
               changelog_version=None, extra=None):
    plugin_version = plugin_version or version
    changelog_version = changelog_version or version

    (root / "VERSION").write_text(version + "\n")
    (root / "CHANGELOG.md").write_text(CHANGELOG % changelog_version)
    for rel in (".claude-plugin", "tools/sage-claude-plugin/.claude-plugin"):
        d = root / rel
        d.mkdir(parents=True, exist_ok=True)
        (d / "plugin.json").write_text(PLUGIN_JSON % plugin_version)
        (d / "marketplace.json").write_text(MARKETPLACE_JSON % plugin_version)
    if extra:
        for rel, text in extra.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)


def run(root: pathlib.Path, *args):
    proc = subprocess.run(
        [sys.executable, str(RELEASE_PY), "--repo-root", str(root), *args],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


class ReleaseToolTest(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    # ── --check ──
    def test_check_green_on_consistent_tree(self):
        build_tree(self.dir)
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 0, out)
        self.assertIn("1.2.3", out)

    def test_check_detects_mutated_plugin_version(self):
        build_tree(self.dir)
        target = self.dir / ".claude-plugin" / "plugin.json"
        target.write_text(target.read_text().replace("1.2.3", "9.9.9"))
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 1, out)
        self.assertIn(".claude-plugin/plugin.json", out)

    def test_check_detects_mutated_mirror_version(self):
        build_tree(self.dir)
        target = self.dir / "tools/sage-claude-plugin/.claude-plugin/plugin.json"
        target.write_text(target.read_text().replace("1.2.3", "0.0.1"))
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 1, out)
        self.assertIn("tools/sage-claude-plugin", out)

    def test_check_detects_changelog_mismatch(self):
        build_tree(self.dir, changelog_version="1.0.0")
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 1, out)
        self.assertIn("CHANGELOG.md", out)

    def test_check_detects_hardcoded_literal_in_docs(self):
        build_tree(self.dir, extra={"README.md": 'sage-version: "1.1.8"\n'})
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 1, out)
        self.assertIn("hard-coded version", out)

    def test_check_allows_placeholder_in_docs(self):
        build_tree(self.dir, extra={"README.md": 'sage-version: "<stamped by sage init>"\n'})
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 0, out)

    def test_check_ignores_changelog_history(self):
        build_tree(self.dir)
        changelog = self.dir / "CHANGELOG.md"
        changelog.write_text(changelog.read_text() + '\nsage-version: "1.0.9"\n')
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 0, out)

    def test_check_fails_without_version_file(self):
        build_tree(self.dir)
        (self.dir / "VERSION").unlink()
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 1, out)
        self.assertIn("VERSION", out)

    def test_check_rejects_non_semver(self):
        build_tree(self.dir)
        (self.dir / "VERSION").write_text("v1.2\n")
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 1, out)
        self.assertIn("semver", out)

    def test_check_detects_mutated_marketplace_version(self):
        build_tree(self.dir)
        target = self.dir / ".claude-plugin" / "marketplace.json"
        target.write_text(target.read_text().replace("1.2.3", "9.9.9"))
        rc, out = run(self.dir, "--check")
        self.assertEqual(rc, 1, out)
        self.assertIn("marketplace.json", out)

    # ── --sync ──
    def test_sync_propagates_to_every_manifest(self):
        build_tree(self.dir, version="2.0.0", plugin_version="1.0.0",
                   changelog_version="2.0.0")
        rc, out = run(self.dir, "--sync")
        self.assertEqual(rc, 0, out)
        for rel in (".claude-plugin/plugin.json",
                    ".claude-plugin/marketplace.json",
                    "tools/sage-claude-plugin/.claude-plugin/plugin.json",
                    "tools/sage-claude-plugin/.claude-plugin/marketplace.json"):
            self.assertIn('"version": "2.0.0"', (self.dir / rel).read_text())
        self.assertEqual(run(self.dir, "--check")[0], 0)

    # ── --bump ──
    def test_bump_patch_round_trip(self):
        # The changelog entry must exist first — that is the guard below.
        build_tree(self.dir, version="1.2.3", changelog_version="1.2.4")
        rc, out = run(self.dir, "--bump", "patch")
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.dir / "VERSION").read_text().strip(), "1.2.4")
        for rel in (".claude-plugin/plugin.json",
                    "tools/sage-claude-plugin/.claude-plugin/plugin.json"):
            self.assertIn('"version": "1.2.4"', (self.dir / rel).read_text())
        self.assertEqual(run(self.dir, "--check")[0], 0)

    def test_bump_minor_and_major_reset_lower_components(self):
        build_tree(self.dir, version="1.2.3", changelog_version="1.3.0")
        self.assertEqual(run(self.dir, "--bump", "minor")[0], 0)
        self.assertEqual((self.dir / "VERSION").read_text().strip(), "1.3.0")

        build_tree(self.dir, version="1.2.3", changelog_version="2.0.0")
        self.assertEqual(run(self.dir, "--bump", "major")[0], 0)
        self.assertEqual((self.dir / "VERSION").read_text().strip(), "2.0.0")

    def test_bump_refuses_without_matching_changelog_entry(self):
        build_tree(self.dir, version="1.2.3", changelog_version="1.2.3")
        rc, out = run(self.dir, "--bump", "patch")
        self.assertEqual(rc, 1, out)
        self.assertIn("1.2.4", out)
        # …and it wrote nothing.
        self.assertEqual((self.dir / "VERSION").read_text().strip(), "1.2.3")
        self.assertIn('"version": "1.2.3"',
                      (self.dir / ".claude-plugin/plugin.json").read_text())

    # ── invocation ──
    def test_requires_a_mode(self):
        build_tree(self.dir)
        rc, _ = run(self.dir)
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
