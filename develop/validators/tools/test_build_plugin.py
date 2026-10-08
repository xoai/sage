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

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
BUILD_PY = REPO_ROOT / "runtime" / "tools" / "build_plugin.py"
HERMES_TOPOLOGY = (
    REPO_ROOT
    / "runtime"
    / "platforms"
    / "community"
    / "hermes"
    / "setup"
    / "topology.json"
)

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

    OVERLAY_SKILL_NAMES = frozenset(
        p.name for p in (REPO_ROOT / "runtime" / "plugin-overlay"
                         / "skills").iterdir()
        if (p / "SKILL.md").is_file())

    def test_build_omits_excluded_skills(self):
        out = self._build()
        for name in build_plugin.SKILLS_NOT_IN_PLUGIN:
            built = out / "skills" / name / "SKILL.md"
            sources = (
                build_plugin.OVERLAY / "skills" / name / "SKILL.md",
                build_plugin.SYSTEM_SKILLS / name / "SKILL.md",
            )
            canonical = next((p for p in sources if p.is_file()), None)
            if canonical is not None:
                self.assertTrue(built.is_file(),
                                f"canonical replacement for {name} should ship")
                self.assertEqual(built.read_bytes(), canonical.read_bytes(),
                                 f"{name} must come from its canonical replacement")
            else:
                self.assertFalse(built.exists(),
                                 f"{name} is excluded but shipped anyway")

    def test_collision_names_ship_the_canonical_source_not_the_mirror(self):
        """The Gate-4 duplication lesson as a tripwire: for names that
        exist both as hermes mirrors (skills/) and as system skills or
        overlay skills, the plugin must ship the CANONICAL source — if
        an edit lands there and the plugin starts shipping the stale
        mirror, this fails."""
        out = self._build()
        for name in (build_plugin.SKILLS_NOT_IN_PLUGIN
                     & build_plugin.SYSTEM_SKILL_NAMES
                     - self.OVERLAY_SKILL_NAMES):
            shipped = (out / "skills" / name / "SKILL.md").read_bytes()
            system = (REPO_ROOT / "core" / "system-skills" / name
                      / "SKILL.md").read_bytes()
            self.assertEqual(shipped, system,
                             f"{name}: shipped bytes are not the "
                             f"system-skill source")
        for name in (build_plugin.SKILLS_NOT_IN_PLUGIN
                     & self.OVERLAY_SKILL_NAMES):
            shipped = (out / "skills" / name / "SKILL.md").read_bytes()
            overlay = (REPO_ROOT / "runtime" / "plugin-overlay" / "skills"
                       / name / "SKILL.md").read_bytes()
            self.assertEqual(shipped, overlay,
                             f"{name}: shipped bytes are not the "
                             f"overlay source")

    def test_gate_scripts_are_identical_to_their_sources(self):
        """A mis-wired FILE_MAP would ship a stale gate — the Gate 4 failure mode."""
        out = self._build()
        for plugin_rel, src_rel in build_plugin.FILE_MAP.items():
            self.assertEqual((out / plugin_rel).read_bytes(),
                             (REPO_ROOT / src_rel).read_bytes(),
                             f"{plugin_rel} != {src_rel}")

    def test_sourced_siblings_ship_with_their_scripts(self):
        """A mapped script that sources a sibling — `. "$(... dirname
        BASH_SOURCE ...)/x.sh"` — ships BROKEN unless the sibling rides
        the same FILE_MAP directory. `--check` cannot see this class: it
        verifies mapped sources exist, not that their sourced
        dependencies ship (found live: sage-verify.sh sourcing
        sage-bounded.sh, mapped alone)."""
        import re
        for plugin_rel, src_rel in build_plugin.FILE_MAP.items():
            if not src_rel.endswith(".sh"):
                continue
            text = (REPO_ROOT / src_rel).read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped.startswith(". ") or "BASH_SOURCE" not in stripped:
                    continue
                m = re.search(r'/([A-Za-z0-9._-]+\.sh)"?\s*$', stripped)
                if not m:
                    continue
                sibling = m.group(1)
                want = str(pathlib.PurePosixPath(plugin_rel).parent
                           / sibling)
                self.assertIn(
                    want, build_plugin.FILE_MAP,
                    f"{src_rel} sources sibling {sibling}; the plugin "
                    f"ships {plugin_rel} without {want} — the gate would "
                    f"break on install")
    def test_overlay_copy_preserves_lf_and_crlf_source_bytes(self):
        """Overlay packaging must not let the host text mode rewrite newlines."""
        version = "9.8.7"
        for label, newline in (("lf", b"\n"), ("crlf", b"\r\n")):
            with self.subTest(checkout=label):
                root = self._tmp() / label
                skills = root / "skills"
                overlay = root / "overlay"
                system_skills = root / "system-skills"
                skills.mkdir(parents=True)
                overlay.mkdir()
                system_skills.mkdir()
                source = overlay / "overlay.md"
                source_bytes = newline.join(
                    (
                        b"version={{VERSION}}",
                        b"canonical overlay bytes",
                        b"",
                    )
                )
                source.write_bytes(source_bytes)
                expected = source_bytes.replace(
                    build_plugin.VERSION_PLACEHOLDER.encode("utf-8"),
                    version.encode("utf-8"),
                )
                out = root / "artifact"

                with mock.patch.multiple(
                    build_plugin,
                    REPO_ROOT=root,
                    SKILLS=skills,
                    OVERLAY=overlay,
                    SYSTEM_SKILLS=system_skills,
                    PLUGIN_SKILLS=frozenset(),
                    SKILLS_NOT_IN_PLUGIN=frozenset(),
                    SYSTEM_SKILL_NAMES=frozenset(),
                    FILE_MAP={},
                ), mock.patch.object(
                    build_plugin,
                    "read_version",
                    return_value=version,
                ), mock.patch.object(
                    build_plugin,
                    "build_navigator",
                    return_value="navigator\n",
                ):
                    build_plugin._build_claude(out)

                self.assertEqual(expected, (out / "overlay.md").read_bytes())

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


class HermesBuildPluginTest(unittest.TestCase):
    """The Hermes target is a complete Sage framework plus native projections."""

    SUPPORTED_CLASSIFICATIONS = {
        "hermes_shell_hook",
        "hermes_plugin_callback",
        "workflow_on_demand_gate",
    }

    def test_explicit_claude_target_matches_the_default_build(self):
        default = self._tmp() / "default"
        explicit = self._tmp() / "explicit"
        build_plugin.build(default)
        build_plugin.build(explicit, target="claude")
        drift = []
        build_plugin._diff(default, explicit, "", drift)
        self.assertEqual([], drift)

    def test_hermes_build_contains_only_canonical_and_topology_owned_targets(self):
        out = self._build()
        expected = set(self._manifest_file_map()) | {
            "plugins/sage/" + build_plugin.HERMES_FRAMEWORK_MANIFEST_NAME
        }
        self.assertEqual(expected, self._built_files(out))

    def test_hermes_build_contains_every_canonical_profile_hook(self):
        out = self._build()
        canonical_hooks = {
            path.name
            for path in (
                REPO_ROOT / "runtime" / "platforms" / "claude-code" / "hooks"
            ).glob("sage-*.sh")
        }
        expected = canonical_hooks | {"sage-hermes-gate.sh"}
        actual = {path.name for path in (out / "hooks").glob("sage-*.sh")}
        self.assertEqual(expected, actual)

    def test_hermes_build_bytes_match_topology_sources(self):
        out = self._build()
        actual = {
            target: (out / target).read_bytes()
            for target in self._manifest_file_map()
        }
        expected = {
            target: build_plugin.canonical_hermes_source_bytes(REPO_ROOT / source)
            for target, source in self._manifest_file_map().items()
        }
        self.assertEqual(expected, actual)

    def test_claude_adapter_files_stay_inside_the_canonical_framework(self):
        forbidden = {
            path
            for path in self._built_files(self._build())
            if not path.startswith("plugins/sage/")
            if any(
                part.startswith(".claude")
                for part in pathlib.PurePosixPath(path).parts
            )
            or pathlib.PurePosixPath(path).name == "CLAUDE.md"
        }
        self.assertEqual(set(), forbidden)
        self.assertIn(
            "plugins/sage/.claude-plugin/plugin.json",
            self._built_files(self._build()),
        )

    def test_hermes_build_omits_workspace_soul(self):
        self.assertNotIn("workspace/SOUL.md", self._built_files(self._build()))

    def test_skills_excluded_from_the_claude_mirror_remain_in_the_framework_only(self):
        built = self._built_files(self._build())
        for name in build_plugin.SKILLS_NOT_IN_PLUGIN:
            self.assertFalse(any(path.startswith(f"skills/{name}/") for path in built))
            source = REPO_ROOT / "skills" / name / "SKILL.md"
            if source.is_file():
                self.assertIn(f"plugins/sage/skills/{name}/SKILL.md", built)

    def test_hermes_audit_rejects_an_unmanifested_file(self):
        out = self._build()
        (out / "plugins" / "sage" / "ghost.py").write_text("unowned\n")
        problems = build_plugin.audit(out, target="hermes")
        self.assertTrue(any("unmanifested" in problem for problem in problems), problems)

    def test_hermes_manifest_rejects_a_windows_drive_escape(self):
        with self.assertRaises(build_plugin.BuildError):
            build_plugin._relative_manifest_path("C:/outside", "package_source")

    def test_hermes_build_rejects_a_stale_manifest_hash(self):
        topology = json.loads(HERMES_TOPOLOGY.read_text(encoding="utf-8"))
        topology["adapter"]["source_sha256"] = "0" * 64
        stale = self._tmp() / "topology.json"
        stale.write_text(json.dumps(topology), encoding="utf-8")
        with mock.patch.object(build_plugin, "HERMES_TOPOLOGY", stale):
            with self.assertRaisesRegex(build_plugin.BuildError, "hash"):
                build_plugin.hermes_file_map()

    def test_hermes_build_uses_index_lf_bytes_when_worktree_is_crlf(self):
        """A Windows checkout and a Linux checkout must build identical bytes."""
        repo = self._tmp() / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "--quiet", str(repo)],
            check=True,
            capture_output=True,
        )
        source = repo / "source.sh"
        canonical = b"#!/usr/bin/env bash\nprintf 'stable\\n'\n"
        source.write_bytes(canonical)
        subprocess.run(
            ["git", "-C", str(repo), "add", "source.sh"],
            check=True,
            capture_output=True,
        )
        index_bytes = subprocess.run(
            ["git", "-C", str(repo), "show", ":source.sh"],
            check=True,
            capture_output=True,
        ).stdout
        self.assertEqual(canonical, index_bytes)
        source.write_bytes(canonical.replace(b"\n", b"\r\n"))

        topology_path = repo / "topology.json"
        topology_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "platform": "hermes",
                    "source_byte_policy": build_plugin.HERMES_SOURCE_BYTE_POLICY,
                    "adapter": {
                        "source": "source.sh",
                        "source_sha256": hashlib.sha256(index_bytes).hexdigest(),
                        "hash_policy": "source_sha256_byte_identity",
                        "build_owner": "runtime/tools/build_plugin.py",
                        "package_target": "hooks/source.sh",
                    },
                    "plugin_files": [],
                    "hooks": [],
                }
            ),
            encoding="utf-8",
        )
        out = self._tmp() / "hermes"
        with mock.patch.multiple(
            build_plugin,
            REPO_ROOT=repo,
            HERMES_TOPOLOGY=topology_path,
            HERMES_OVERLAY=repo / "missing-overlay",
        ):
            build_plugin.build(out, target="hermes")

        self.assertEqual(index_bytes, (out / "hooks" / "source.sh").read_bytes())

    def test_hermes_build_rejects_lone_cr_outside_git_lf_semantics(self):
        repo = self._tmp() / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "--quiet", str(repo)],
            check=True,
            capture_output=True,
        )
        source = repo / "source.sh"
        source.write_bytes(b"first\rsecond\n")
        subprocess.run(
            ["git", "-C", str(repo), "add", "source.sh"],
            check=True,
            capture_output=True,
        )
        index_bytes = subprocess.run(
            ["git", "-C", str(repo), "show", ":source.sh"],
            check=True,
            capture_output=True,
        ).stdout
        self.assertEqual(source.read_bytes(), index_bytes)
        topology_path = self._write_minimal_topology(
            repo,
            source,
            source_hash=hashlib.sha256(index_bytes).hexdigest(),
        )

        with mock.patch.multiple(
            build_plugin,
            REPO_ROOT=repo,
            HERMES_TOPOLOGY=topology_path,
            HERMES_OVERLAY=repo / "missing-overlay",
        ):
            with self.assertRaisesRegex(build_plugin.BuildError, "lone CR"):
                build_plugin.build(self._tmp() / "hermes", target="hermes")

    def test_hermes_build_rejects_a_git_tracked_symlink_source(self):
        repo = self._tmp() / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "--quiet", str(repo)],
            check=True,
            capture_output=True,
        )
        source = repo / "source.sh"
        source.write_bytes(b"untracked referent bytes\n")
        link_blob = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
            input=b"untracked-target.sh",
            check=True,
            capture_output=True,
        ).stdout.decode("ascii").strip()
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "update-index",
                "--add",
                "--cacheinfo",
                f"120000,{link_blob},source.sh",
            ],
            check=True,
            capture_output=True,
        )
        stage = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--stage", "--", "source.sh"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertTrue(stage.startswith("120000 "), stage)
        topology_path = self._write_minimal_topology(repo, source)

        with mock.patch.multiple(
            build_plugin,
            REPO_ROOT=repo,
            HERMES_TOPOLOGY=topology_path,
            HERMES_OVERLAY=repo / "missing-overlay",
        ):
            with self.assertRaisesRegex(build_plugin.BuildError, "symlink"):
                build_plugin.build(self._tmp() / "hermes", target="hermes")

    def test_hermes_build_rejects_an_in_repo_filesystem_symlink_source(self):
        repo = self._tmp() / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "--quiet", str(repo)],
            check=True,
            capture_output=True,
        )
        referent = repo / "referent.sh"
        referent.write_bytes(b"tracked referent bytes\n")
        source = repo / "source.sh"
        try:
            source.symlink_to(referent.name)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"file symlinks unavailable: {exc}")
        subprocess.run(
            ["git", "-C", str(repo), "add", "referent.sh", "source.sh"],
            check=True,
            capture_output=True,
        )
        topology_path = self._write_minimal_topology(repo, source)

        with mock.patch.multiple(
            build_plugin,
            REPO_ROOT=repo,
            HERMES_TOPOLOGY=topology_path,
            HERMES_OVERLAY=repo / "missing-overlay",
        ):
            with self.assertRaisesRegex(build_plugin.BuildError, "symlink"):
                build_plugin.build(self._tmp() / "hermes", target="hermes")

    def test_hermes_manifest_enforces_every_package_hash_policy(self):
        selectors = (
            ("adapter", lambda data: data["adapter"]),
            ("plugin file", lambda data: data["plugin_files"][0]),
            (
                "shell hook",
                lambda data: next(
                    row
                    for row in data["hooks"]
                    if row["classification"] == "hermes_shell_hook"
                ),
            ),
            (
                "plugin callback",
                lambda data: next(
                    row
                    for row in data["hooks"]
                    if row["classification"] == "hermes_plugin_callback"
                ),
            ),
            (
                "workflow on-demand gate",
                lambda data: next(
                    row
                    for row in data["hooks"]
                    if row["classification"] == "workflow_on_demand_gate"
                ),
            ),
        )
        for label, select in selectors:
            for value in (None, "wrong_policy"):
                with self.subTest(row=label, value=value):
                    topology = self._topology()
                    row = select(topology)
                    if value is None:
                        row.pop("hash_policy", None)
                    else:
                        row["hash_policy"] = value
                    with self._patched_topology(topology):
                        with self.assertRaisesRegex(
                            build_plugin.BuildError,
                            "hash_policy",
                        ):
                            build_plugin.load_hermes_topology()
                    with self._patched_topology(topology):
                        with self.assertRaisesRegex(
                            build_plugin.BuildError,
                            "hash_policy",
                        ):
                            build_plugin.hermes_file_map()
                    with self._patched_topology(topology):
                        with self.assertRaisesRegex(
                            build_plugin.BuildError,
                            "hash_policy",
                        ):
                            build_plugin.build(
                                self._tmp() / "hermes",
                                target="hermes",
                            )
                    with self._patched_topology(topology):
                        problems = build_plugin.audit(
                            self._tmp() / "hermes",
                            target="hermes",
                        )
                    self.assertTrue(
                        any("hash_policy" in problem for problem in problems),
                        problems,
                    )

    def test_hermes_manifest_rejects_an_unsupported_schema_version(self):
        topology = self._topology()
        topology["schema_version"] = 2
        with self._patched_topology(topology):
            with self.assertRaisesRegex(build_plugin.BuildError, "schema_version"):
                build_plugin.hermes_file_map()

    def test_hermes_manifest_rejects_a_wrong_source_byte_policy(self):
        topology = self._topology()
        topology["source_byte_policy"] = "raw_worktree_bytes"
        with self._patched_topology(topology):
            with self.assertRaisesRegex(build_plugin.BuildError, "source_byte_policy"):
                build_plugin.hermes_file_map()

    def test_hermes_manifest_rejects_a_wrong_build_owner(self):
        topology = self._topology()
        topology["adapter"]["build_owner"] = "bin/sage"
        with self._patched_topology(topology):
            with self.assertRaisesRegex(build_plugin.BuildError, "build_owner"):
                build_plugin.hermes_file_map()

    def test_hermes_manifest_rejects_a_casefold_target_collision(self):
        topology = self._topology()
        topology["hooks"][0]["package_target"] = topology["adapter"][
            "package_target"
        ].upper()
        out = self._tmp() / "hermes"
        with self._patched_topology(topology):
            with mock.patch.object(build_plugin, "copy_hermes_source") as copy:
                with self.assertRaisesRegex(build_plugin.BuildError, "collid"):
                    build_plugin.build(out, target="hermes")
        copy.assert_not_called()
        self.assertFalse(out.exists())

    def test_hermes_manifest_rejects_windows_unsafe_targets_before_copy(self):
        unsafe_targets = (
            "hooks/x.",
            "hooks/x ",
            "hooks/CON",
            "hooks/CON.txt",
            "hooks/base:ads",
        )
        for target in unsafe_targets:
            with self.subTest(target=target):
                topology = self._topology()
                topology["adapter"]["package_target"] = target
                out = self._tmp() / "hermes"
                with self._patched_topology(topology):
                    with mock.patch.object(
                        build_plugin,
                        "copy_hermes_source",
                    ) as copy:
                        with self.assertRaisesRegex(
                            build_plugin.BuildError,
                            "Windows|unsafe|reserved|trailing|colon",
                        ):
                            build_plugin.build(out, target="hermes")
                copy.assert_not_called()
                self.assertFalse(out.exists())

    def test_hermes_manifest_rejects_non_identity_git_attributes(self):
        cases = (
            ("filter", "source.sh filter=manifest-test-filter\n"),
            (
                "working-tree-encoding",
                "source.sh working-tree-encoding=UTF-16\n",
            ),
        )
        for attribute, rule in cases:
            with self.subTest(attribute=attribute):
                repo = self._tmp() / attribute
                repo.mkdir()
                subprocess.run(
                    ["git", "init", "--quiet", str(repo)],
                    check=True,
                    capture_output=True,
                )
                source = repo / "source.sh"
                source.write_bytes(b"canonical source bytes\n")
                subprocess.run(
                    ["git", "-C", str(repo), "add", "source.sh"],
                    check=True,
                    capture_output=True,
                )
                topology_path = self._write_minimal_topology(repo, source)
                (repo / ".git" / "info" / "attributes").write_text(
                    rule,
                    encoding="utf-8",
                )

                with mock.patch.multiple(
                    build_plugin,
                    REPO_ROOT=repo,
                    HERMES_TOPOLOGY=topology_path,
                    HERMES_OVERLAY=repo / "missing-overlay",
                ):
                    with self.assertRaisesRegex(
                        build_plugin.BuildError,
                        attribute,
                    ):
                        build_plugin.hermes_file_map()

    def test_hermes_manifest_allows_an_installed_non_git_release_tree(self):
        """Release installs are canonical archive bytes, not Git worktrees."""
        repo = self._tmp() / "installed-framework"
        repo.mkdir()
        source = repo / "source.py"
        source.write_bytes(b"canonical release bytes\n")
        topology_path = self._write_minimal_topology(repo, source)

        with mock.patch.multiple(
            build_plugin,
            REPO_ROOT=repo,
            HERMES_TOPOLOGY=topology_path,
            HERMES_OVERLAY=repo / "missing-overlay",
        ):
            self.assertEqual(
                build_plugin.hermes_file_map(),
                {"hooks/sage-hermes-gate.sh": "source.py"},
            )

    def test_hermes_manifest_rejects_a_source_resolving_outside_the_repo(self):
        root = self._tmp()
        repo = root / "repo"
        repo.mkdir()
        outside = root / "outside.py"
        outside.write_text("outside\n", encoding="utf-8")
        source = repo / "source.py"
        try:
            source.symlink_to(outside)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"file symlinks unavailable: {exc}")
        topology_path = self._write_minimal_topology(repo, source)

        with mock.patch.multiple(
            build_plugin,
            REPO_ROOT=repo,
            HERMES_TOPOLOGY=topology_path,
            HERMES_OVERLAY=repo / "missing-overlay",
        ):
            with self.assertRaisesRegex(build_plugin.BuildError, "outside.*repository"):
                build_plugin.hermes_file_map()

    def test_hermes_check_rejects_a_git_untracked_declared_source(self):
        repo = self._tmp() / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "--quiet", str(repo)],
            check=True,
            capture_output=True,
        )
        source = repo / "source.py"
        source.write_text("untracked\n", encoding="utf-8")
        (repo / "VERSION").write_text("1.3.18\n", encoding="utf-8")
        topology_path = self._write_minimal_topology(repo, source)
        stderr = io.StringIO()

        with mock.patch.multiple(
            build_plugin,
            REPO_ROOT=repo,
            HERMES_TOPOLOGY=topology_path,
            HERMES_OVERLAY=repo / "missing-overlay",
        ), mock.patch.object(
            sys,
            "argv",
            ["build_plugin.py", "--target", "hermes", "--check"],
        ), contextlib.redirect_stderr(stderr):
            result = build_plugin.main()

        self.assertEqual(
            (1, True),
            (result, "not tracked by git" in stderr.getvalue()),
        )

    def test_hermes_plugin_contains_the_complete_canonical_framework_tree(self):
        """The installed Hermes plugin is Sage itself, not a thin adapter export."""
        state_parts = {
            ".git",
            ".sage",
            ".sage-memory",
            ".serena",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".tox",
            ".nox",
            "__pycache__",
            "dist",
            "htmlcov",
            "node_modules",
            "target",
        }
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "-z"],
            check=True,
            capture_output=True,
        )
        canonical = set()
        for path in proc.stdout.split(b"\0"):
            if not path:
                continue
            relative = pathlib.PurePosixPath(os.fsdecode(path))
            if any(part in state_parts for part in relative.parts):
                continue
            if relative.suffix in (".pyc", ".pyo"):
                continue
            canonical.add(relative.as_posix())

        out = self._build()
        plugin_root = out / "plugins" / "sage"
        installed = self._built_files(plugin_root)

        self.assertFalse(
            canonical - installed,
            "canonical Sage files missing from plugins/sage: %s"
            % sorted(canonical - installed),
        )
        for required in (
            "plugin.yaml",
            "__init__.py",
            "bin/sage",
            "core/gates/_config/gate-modes.yaml",
            "runtime/tools/build_plugin.py",
            "skills/sage/SKILL.md",
            "hooks/sage-session/HOOK.yaml",
            "install.sh",
            "VERSION",
            ".sage-framework-manifest.json",
        ):
            self.assertIn(required, installed)
        generated_state = {
            relative
            for relative in installed
            if any(
                part in state_parts
                for part in pathlib.PurePosixPath(relative).parts
            )
            or pathlib.PurePosixPath(relative).suffix in (".pyc", ".pyo")
        }
        self.assertFalse(
            generated_state,
            "generated local state leaked into plugins/sage: %s"
            % sorted(generated_state),
        )
        self.assertFalse(
            any(
                ".git" in pathlib.PurePosixPath(path).parts
                or ".serena" in pathlib.PurePosixPath(path).parts
                for path in installed
            ),
            sorted(installed),
        )

    def test_cli_builds_the_explicit_hermes_target(self):
        out = self._tmp() / "hermes"
        proc = subprocess.run(
            [
                sys.executable,
                str(BUILD_PY),
                "--target",
                "hermes",
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("full Sage framework as a Hermes plugin", proc.stdout)

    def _manifest_file_map(self):
        topology = json.loads(HERMES_TOPOLOGY.read_text(encoding="utf-8"))
        file_map = {
            topology["adapter"]["package_target"]: topology["adapter"]["source"]
        }
        framework = topology.get("framework_package")
        if framework is not None:
            package_root = framework["package_target"].rstrip("/")
            file_map.update(
                {
                    f"{package_root}/{source}": source
                    for source in build_plugin._hermes_framework_source_paths()
                }
            )
        file_map.update(
            {
                row["package_target"]: row["source"]
                for row in topology["plugin_files"]
            }
        )
        file_map.update(
            {
                row["package_target"]: row["package_source"]
                for row in topology["hooks"]
                if row["classification"] in self.SUPPORTED_CLASSIFICATIONS
            }
        )
        return file_map

    @staticmethod
    def _built_files(root):
        return {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }

    def _build(self):
        out = self._tmp() / "hermes"
        build_plugin.build(out, target="hermes")
        return out

    @staticmethod
    def _topology():
        return json.loads(HERMES_TOPOLOGY.read_text(encoding="utf-8"))

    def _patched_topology(self, topology):
        path = self._tmp() / "topology.json"
        path.write_text(json.dumps(topology), encoding="utf-8")
        return mock.patch.object(build_plugin, "HERMES_TOPOLOGY", path)

    @staticmethod
    def _write_minimal_topology(repo, source, source_hash=None):
        topology_path = repo / "topology.json"
        topology_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "platform": "hermes",
                    "source_byte_policy": build_plugin.HERMES_SOURCE_BYTE_POLICY,
                    "adapter": {
                        "source": source.relative_to(repo).as_posix(),
                        "source_sha256": source_hash
                        or hashlib.sha256(
                            build_plugin.canonical_hermes_source_bytes(source)
                        ).hexdigest(),
                        "hash_policy": "source_sha256_byte_identity",
                        "build_owner": "runtime/tools/build_plugin.py",
                        "package_target": "hooks/sage-hermes-gate.sh",
                    },
                    "plugin_files": [],
                    "hooks": [],
                }
            ),
            encoding="utf-8",
        )
        return topology_path

    def _tmp(self):
        root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root


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
            [build_plugin.BASH, "-c",
             'source "%s"; emit_instructions_body'
             % build_plugin.bash_path(build_plugin.INSTRUCTIONS_BODY)],
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
