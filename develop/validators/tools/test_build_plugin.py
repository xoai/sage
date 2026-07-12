#!/usr/bin/env python3
"""
test_build_plugin.py — tests for runtime/tools/build_plugin.py (30-§4).

The committed mirror is gone (P3-T2b), so `--check` no longer diffs against a
second copy — it audits the built artifact against its contract. These tests
pin that contract by building the real tree and then breaking each property in
a synthetic copy, proving the audit actually catches it.

Usage:  python3 develop/validators/tools/test_build_plugin.py
Exit:   0 = all pass | 1 = a test failed

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import importlib.util
import json
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
    """The real build satisfies the contract."""

    def test_check_is_green(self):
        self.assertEqual(build_plugin.check(), 0)

    def test_build_substitutes_version(self):
        out = self._build()
        version = build_plugin.read_version()
        for name in ("plugin.json", "marketplace.json"):
            text = (out / ".claude-plugin" / name).read_text()
            self.assertNotIn(build_plugin.VERSION_PLACEHOLDER, text)
        self.assertIn(f'"version": "{version}"',
                      (out / ".claude-plugin" / "plugin.json").read_text())

    def test_build_ships_every_declared_skill(self):
        out = self._build()
        for name in build_plugin.PLUGIN_SKILLS:
            self.assertTrue((out / "skills" / name / "SKILL.md").is_file(),
                            f"{name} declared in PLUGIN_SKILLS but not shipped")

    def test_build_omits_excluded_skills(self):
        out = self._build()
        for name in build_plugin.SKILLS_NOT_IN_PLUGIN:
            self.assertFalse((out / "skills" / name).exists(),
                             f"{name} is excluded but shipped anyway")

    def test_gate_scripts_are_identical_to_their_sources(self):
        """A mis-wired FILE_MAP would ship a stale gate — the Gate 4 failure mode."""
        out = self._build()
        for plugin_rel, src_rel in build_plugin.FILE_MAP.items():
            self.assertEqual((out / plugin_rel).read_bytes(),
                             (REPO_ROOT / src_rel).read_bytes(),
                             f"{plugin_rel} != {src_rel}")

    def test_marketplace_pins_the_dist_branch(self):
        """Without a ref the source resolves to main, which has no plugin tree."""
        out = self._build()
        entries = json.loads((out / ".claude-plugin" / "marketplace.json").read_text())
        for entry in entries["plugins"]:
            self.assertEqual(entry["source"].get("ref"), build_plugin.DIST_REF)
            self.assertNotIn("version", entry)

    # ── the audit catches each violation ──
    def test_audit_catches_unsubstituted_placeholder(self):
        out = self._build()
        (out / "README.md").write_text(f"version {build_plugin.VERSION_PLACEHOLDER}\n")
        self.assertProblem(out, "unsubstituted")

    def test_audit_catches_version_disagreeing_with_VERSION(self):
        out = self._build()
        self._patch_json(out / ".claude-plugin" / "plugin.json", version="9.9.9")
        self.assertProblem(out, "!= VERSION")

    def test_audit_catches_missing_dist_ref(self):
        path = (out := self._build()) / ".claude-plugin" / "marketplace.json"
        data = json.loads(path.read_text())
        del data["plugins"][0]["source"]["ref"]
        path.write_text(json.dumps(data))
        self.assertProblem(out, "carries no plugin tree")

    def test_audit_catches_a_version_pinned_in_the_marketplace(self):
        path = (out := self._build()) / ".claude-plugin" / "marketplace.json"
        data = json.loads(path.read_text())
        data["plugins"][0]["version"] = "1.2.0"
        path.write_text(json.dumps(data))
        self.assertProblem(out, "single authority")

    def test_audit_catches_a_gate_script_that_drifted_from_its_source(self):
        out = self._build()
        (out / "hooks" / "scripts" / "sage-verify.sh").write_text("#!/bin/sh\nexit 0\n")
        self.assertProblem(out, "differs from its source")

    def test_audit_catches_a_registered_hook_that_does_not_ship(self):
        out = self._build()
        (out / "hooks" / "scripts" / "sage-spec-gate.sh").unlink()
        self.assertProblem(out, "does not ship")

    # ── build inputs must be visible to more than just this machine ──
    def test_every_build_input_is_tracked_by_git(self):
        """.gitignore's unanchored `sage/` rule hid the /sage router for an entire
        program: on disk for every developer, absent from every clean checkout."""
        self.assertEqual(build_plugin.untracked_inputs(), [])

    def test_build_inputs_include_the_router_that_was_hidden(self):
        overlay_router = build_plugin.OVERLAY / "skills" / "sage" / "SKILL.md"
        self.assertIn(overlay_router, build_plugin.build_inputs())

    def test_untracked_input_is_reported(self):
        """Simulate the bug: an input git cannot see must fail the audit."""
        out = self._build()
        ghost = build_plugin.OVERLAY / "skills" / "sage" / ".ghost.md"
        ghost.write_text("untracked\n")
        self.addCleanup(ghost.unlink)
        problems = build_plugin.audit(out)
        self.assertTrue(any("not tracked by git" in p for p in problems), problems)

    # ── the tree differ (used to prove the build is reproducible) ──
    def test_diff_reports_a_modified_file(self):
        a, b = self._tmp(), self._tmp()
        (a / "sub").mkdir()
        (b / "sub").mkdir()
        (a / "sub" / "f.md").write_text("one\n")
        (b / "sub" / "f.md").write_text("two\n")
        drift = []
        build_plugin._diff(a, b, "", drift)
        self.assertTrue(any("sub/f.md" in d and "differs" in d for d in drift), drift)

    def test_diff_reports_extra_and_missing_files(self):
        a, b = self._tmp(), self._tmp()
        (a / "only_a.md").write_text("x")
        (b / "only_b.md").write_text("y")
        drift = []
        build_plugin._diff(a, b, "", drift)
        self.assertTrue(any("only_a.md" in d for d in drift), drift)
        self.assertTrue(any("only_b.md" in d for d in drift), drift)

    # ── helpers ──
    def _tmp(self) -> pathlib.Path:
        d = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    def _build(self) -> pathlib.Path:
        out = self._tmp() / "plugin"
        build_plugin.build(out)
        return out

    def _patch_json(self, path: pathlib.Path, **fields):
        data = json.loads(path.read_text())
        data.update(fields)
        path.write_text(json.dumps(data))

    def assertProblem(self, tree: pathlib.Path, needle: str):
        problems = build_plugin.audit(tree)
        self.assertTrue(any(needle in p for p in problems),
                        f"audit did not report {needle!r}; got: {problems}")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class NavigatorIsGeneratedTest(unittest.TestCase):
    """The navigator drifted for two releases. It cannot again.

    A plugin cannot install a CLAUDE.md, so sage-navigator IS the eager layer for
    plugin users. It used to be a 441-line file maintained by hand next to the real
    eager body, and it shipped a routing table a release out of date — /analyze,
    /qa, /design-review, /status, all folded into other commands in v1.2.0.

    Nothing compared the two copies. These tests are what compares them.
    """

    def test_navigator_is_generated_from_the_eager_body(self):
        import subprocess as sp
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "p"
            build_plugin.build(out)
            nav = (out / "skills" / "sage-navigator" / "SKILL.md").read_text()

        body = sp.run(
            ["bash", "-c",
             'source "%s"; emit_instructions_body' % build_plugin.INSTRUCTIONS_BODY],
            capture_output=True, text=True).stdout

        # A distinctive line from the eager body must appear verbatim in the
        # navigator. If someone reintroduces a hand-written copy, this breaks.
        marker = "## Skill check — before ANY response"
        self.assertIn(marker, body)
        self.assertIn(marker, nav)

    def test_the_navigator_carries_no_stale_routes(self):
        """The exact bug that shipped: routes folded in v1.2.0, still being served."""
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "p"
            build_plugin.build(out)
            nav = (out / "skills" / "sage-navigator" / "SKILL.md").read_text()

        # These may appear as KEYWORDS ("audit/evaluate/assess/analyze/...") and in
        # the documented one-cycle deprecation line. They must never appear as a
        # ROUTE TARGET — `→ /analyze`.
        for dead in ("/analyze", "/qa", "/design-review", "/status", "/map"):
            self.assertNotIn("→ %s\n" % dead, nav,
                             "%s is folded; the navigator must not route to it" % dead)

    def test_no_unsubstituted_placeholder_ships(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "p"
            build_plugin.build(out)
            nav = (out / "skills" / "sage-navigator" / "SKILL.md").read_text()
        self.assertNotIn("__CONSTITUTION_PLACEHOLDER__", nav)
        self.assertIn("Engineering Principles", nav)

    def test_there_is_no_hand_written_navigator_left(self):
        """The overlay copy is the bug. It must stay deleted."""
        self.assertFalse(
            (build_plugin.OVERLAY / "skills" / "sage-navigator" / "SKILL.md").exists(),
            "a hand-maintained navigator is back in the overlay — it will drift")
