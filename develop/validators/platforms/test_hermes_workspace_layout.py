#!/usr/bin/env python3
"""Behavioral contract for the Hermes bound-workspace layout.

The tests use disposable profiles only.  They deliberately exercise staging,
replacement, stale-file pruning, durable-state preservation, Git ownership,
and link/reparse escapes rather than treating file presence as installation
proof.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, fields, replace
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[3]
SETUP = ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup"
sys.path.insert(0, os.fspath(SETUP))

from profile_binding import ProfileBinding  # noqa: E402
import workspace_layout as workspace_layout_module  # noqa: E402
from workspace_layout import LayoutError, WorkspaceLayout  # noqa: E402


def _write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def _digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_variant(path: pathlib.Path) -> pathlib.Path:
    native = os.fspath(path)
    for index in range(len(native) - 1, -1, -1):
        character = native[index]
        if character.isalpha():
            replacement = character.upper() if character.islower() else character.lower()
            return pathlib.Path(native[:index] + replacement + native[index + 1 :])
    raise AssertionError("test path has no alphabetic character to case-vary")


def _windows_namespace_variant(path: pathlib.Path) -> pathlib.Path:
    native = os.fspath(path).replace("/", "\\")
    if native.startswith("\\\\"):
        return pathlib.Path("\\\\?\\UNC\\" + native[2:])
    return pathlib.Path("\\\\?\\" + native)


class HermesWorkspaceLayoutTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="sage-hermes-layout-")
        self.root = pathlib.Path(self._temp.name).resolve()
        self.collection = self.root / "hermes"
        self.profile = self.collection / "profiles" / "alpha"
        self.workspace = self.profile / "workspace"
        self.workspace.mkdir(parents=True)
        self.soul = self.profile / "SOUL.md"
        _write(self.soul, "alpha identity\n")

        self.framework = self.root / "framework"
        self._make_framework("v1")
        self.binding = ProfileBinding.from_explicit(
            collection_root=self.collection,
            profile_id="alpha",
            profile_root=self.profile,
            workspace_root=self.workspace,
        )
        self.layout = WorkspaceLayout.from_binding(self.binding)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def _make_framework(self, marker: str) -> None:
        instruction_source = """#!/usr/bin/env bash
emit_instructions_body() {
  cat <<'INSTRUCTIONS_EOF'
# Sage current instructions %s

__CONSTITUTION_PLACEHOLDER__
INSTRUCTIONS_EOF
}
""" % marker
        _write(
            self.framework
            / "runtime"
            / "platforms"
            / "_shared"
            / "instructions-body.sh",
            instruction_source,
        )
        _write(
            self.framework
            / "runtime"
            / "platforms"
            / "_shared"
            / "constitution.sh",
            """#!/usr/bin/env bash
build_constitution_section() {
  local core="$1"
  local project_sage="$2"
  printf '## Constitution from canonical emitter %s\\n\\n' '%s'
  if [ -f "$project_sage/constitution.md" ]; then
    sed -n '/^## Project Additions/,$ { /^## Project/d; /^$/d; /^(/d; p; }' \
      "$project_sage/constitution.md"
  fi
}
""" % (marker, marker),
        )
        _write(self.framework / "runtime" / "tools" / "current.py", marker + "\n")
        _write(self.framework / "core" / "gates" / "scripts" / "gate.sh", marker + "\n")
        _write(
            self.framework
            / "core"
            / "constitution"
            / "presets"
            / "startup.constitution.md",
            "# Startup\n\n## Additions\n1. Ship the smallest useful slice\n",
        )
        _write(self.framework / "skills" / "sage-routing" / "SKILL.md", marker + "\n")
        _write(self.framework / "bin" / "sage", "#!/usr/bin/env bash\n# %s\n" % marker)
        _write(self.framework / "__init__.py", "# %s\n" % marker)
        _write(self.framework / "plugin.yaml", "name: sage\n")
        _write(self.framework / "LICENSE", "test license\n")
        _write(self.framework / "VERSION", "9.9.%s\n" % ("1" if marker == "v1" else "2"))
        _write(self.framework / "develop" / "must-not-ship.txt", "developer-only\n")

    def _seed_durable_state(self) -> dict:
        _write(
            self.workspace / ".sage" / "constitution.md",
            "---\nextends: startup\n---\n\n## Project Additions\nKeep each profile isolated\n",
        )
        _write(self.workspace / ".sage" / "config.yaml", "owner: alpha\n")
        _write(self.workspace / ".sage" / "decisions.md", "# Alpha decisions\n")
        _write(
            self.workspace / ".sage" / "work" / "initiative" / "manifest.md",
            "status: active\n",
        )
        _write(self.workspace / ".sage-memory" / "memory.db", "alpha memory\n")
        _write(self.workspace / "notes.txt", "user-authored\n")
        paths = (
            self.soul,
            self.workspace / ".sage" / "constitution.md",
            self.workspace / ".sage" / "config.yaml",
            self.workspace / ".sage" / "decisions.md",
            self.workspace / ".sage" / "work" / "initiative" / "manifest.md",
            self.workspace / ".sage-memory" / "memory.db",
            self.workspace / "notes.txt",
        )
        return {path: _digest(path) for path in paths}

    def test_exact_durable_homes_are_derived_only_from_binding(self) -> None:
        homes = self.layout.homes
        self.assertEqual(homes.instructions_path, self.workspace / ".hermes.md")
        self.assertEqual(homes.runtime_root, self.workspace / "sage")
        self.assertEqual(homes.state_root, self.binding.state_root)
        self.assertEqual(homes.config_path, self.binding.state_root / "config.yaml")
        self.assertEqual(homes.gates_root, self.binding.state_root / "gates")
        self.assertEqual(homes.session_lock_path, self.binding.state_root / ".session-lock")
        self.assertEqual(
            homes.session_pickup_path,
            self.binding.state_root / "gates" / "session-pickup.md",
        )
        self.assertEqual(
            homes.verification_state_path,
            self.binding.state_root / "tmp" / "verify-state",
        )
        self.assertEqual(homes.decisions_path, self.binding.state_root / "decisions.md")
        self.assertEqual(homes.pack_lock_path, self.binding.pack_lock_path)
        self.assertEqual(homes.receipt_path, self.binding.receipt_path)
        self.assertEqual(homes.runs_root, self.binding.runs_root)
        self.assertEqual(homes.memory_root, self.binding.memory_root)
        self.assertEqual(homes.memory_db_path, self.binding.memory_db_path)

        initiative = self.layout.initiative_homes("20260810-alpha")
        expected = self.binding.state_root / "work" / "20260810-alpha"
        self.assertEqual(initiative.root, expected)
        self.assertEqual(initiative.manifest_path, expected / "manifest.md")
        self.assertEqual(initiative.mode_state_path, expected / "manifest.md")
        self.assertEqual(initiative.goal_state_path, expected / "manifest.md")
        self.assertEqual(initiative.decisions_path, expected / "decisions.md")
        self.assertEqual(initiative.review_ledger_path, expected / "review-ledger.json")
        self.assertEqual(initiative.autoresearch_log_path, expected / "autoresearch.jsonl")
        self.assertEqual(initiative.autonomy_log_path, expected / "autonomy.jsonl")
        with self.assertRaises(LayoutError):
            self.layout.initiative_homes("../beta")

    def test_stage_then_commit_refreshes_managed_surfaces_and_preserves_state(self) -> None:
        preserved = self._seed_durable_state()
        _write(self.workspace / ".hermes.md", "old instructions\n")
        _write(self.workspace / "sage" / "runtime" / "tools" / "current.py", "old\n")
        _write(self.workspace / "sage" / "stale-managed.txt", "remove me\n")

        staged = self.layout.stage_from_framework(self.framework)
        try:
            self.assertEqual((self.workspace / ".hermes.md").read_text(), "old instructions\n")
            self.assertTrue((self.workspace / "sage" / "stale-managed.txt").exists())
            self.assertTrue(staged.instructions_candidate.is_file())
            self.assertTrue(staged.runtime_candidate.is_dir())

            result = staged.commit()
        finally:
            staged.cleanup()

        prompt = (self.workspace / ".hermes.md").read_text(encoding="utf-8")
        self.assertIn("Sage current instructions v1", prompt)
        self.assertIn("Constitution from canonical emitter v1", prompt)
        self.assertIn("Keep each profile isolated", prompt)
        self.assertEqual(
            (self.workspace / "sage" / "runtime" / "tools" / "current.py").read_text(),
            "v1\n",
        )
        self.assertFalse((self.workspace / "sage" / "stale-managed.txt").exists())
        self.assertFalse((self.workspace / "sage" / "develop").exists())
        self.assertIn("sage/stale-managed.txt", result.stale_paths)
        self.assertIn(".hermes.md", {entry.relative_path for entry in result.managed_files})
        self.assertIn(
            "sage/runtime/tools/current.py",
            {entry.relative_path for entry in result.managed_files},
        )
        for path, digest in preserved.items():
            self.assertEqual(_digest(path), digest, os.fspath(path))

        self.assertTrue(self.binding.runs_root.is_dir())
        self.assertTrue(self.binding.memory_root.is_dir())
        self.assertFalse((self.workspace / "CLAUDE.md").exists())
        self.assertFalse((self.workspace / "SOUL.md").exists())
        self.assertFalse((self.workspace / ".claude").exists())
        self.assertFalse((self.workspace / ".agent" / "hooks").exists())
        self.assertFalse((self.profile / "hooks" / "sage" / "HOOK.yaml").exists())

    def test_runtime_candidate_excludes_python_bytecode_caches(self) -> None:
        cache = self.framework / "runtime" / "tools" / "__pycache__"
        _write(cache / "generated.cpython-314.pyc", "machine-local bytecode\n")
        _write(self.framework / "runtime" / "tools" / "generated.pyo", "optimized bytecode\n")

        staged = self.layout.stage_from_framework(self.framework)
        try:
            relative_paths = {entry.relative_path for entry in staged.managed_files}
            self.assertFalse((staged.runtime_candidate / "runtime" / "tools" / "__pycache__").exists())
            self.assertFalse((staged.runtime_candidate / "runtime" / "tools" / "generated.pyo").exists())
            self.assertFalse(
                any(
                    "__pycache__" in pathlib.PurePosixPath(relative).parts
                    or relative.endswith((".pyc", ".pyo"))
                    for relative in relative_paths
                ),
                sorted(relative_paths),
            )
        finally:
            staged.cleanup()

    def test_second_refresh_replaces_current_prompt_and_runtime_without_state_drift(self) -> None:
        preserved = self._seed_durable_state()
        self.layout.refresh_from_framework(self.framework)
        self._make_framework("v2")
        _write(self.workspace / "sage" / "obsolete.py", "stale\n")

        result = self.layout.refresh_from_framework(self.framework)

        self.assertIn(
            "Sage current instructions v2",
            (self.workspace / ".hermes.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "Constitution from canonical emitter v2",
            (self.workspace / ".hermes.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            (self.workspace / "sage" / "runtime" / "tools" / "current.py").read_text(),
            "v2\n",
        )
        self.assertFalse((self.workspace / "sage" / "obsolete.py").exists())
        self.assertIn("sage/obsolete.py", result.stale_paths)
        for path, digest in preserved.items():
            self.assertEqual(_digest(path), digest, os.fspath(path))

    def test_only_bound_managed_or_durable_targets_are_writable(self) -> None:
        accepted = (
            self.workspace / ".hermes.md",
            self.workspace / "sage" / "runtime" / "tool.py",
            self.binding.state_root / "work" / "x" / "manifest.md",
            self.binding.memory_root / "memory.db",
        )
        for path in accepted:
            self.assertEqual(self.layout.assert_writable_target(path), path)

        rejected = (
            self.profile / "SOUL.md",
            self.profile / "config.yaml",
            self.collection / "global.txt",
            self.root / "unrelated" / ".sage" / "config.yaml",
            self.workspace / "notes.txt",
        )
        for path in rejected:
            with self.subTest(path=path):
                with self.assertRaises(LayoutError):
                    self.layout.assert_writable_target(path)

    def test_invalid_framework_fails_before_replacing_existing_bytes(self) -> None:
        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "original runtime\n")
        original_prompt = _digest(self.workspace / ".hermes.md")
        original_runtime = _digest(self.workspace / "sage" / "original.txt")
        (self.framework / "plugin.yaml").unlink()

        with self.assertRaises(LayoutError):
            self.layout.stage_from_framework(self.framework)

        self.assertEqual(_digest(self.workspace / ".hermes.md"), original_prompt)
        self.assertEqual(_digest(self.workspace / "sage" / "original.txt"), original_runtime)

    def test_candidate_tamper_is_rejected_before_replacing_existing_bytes(self) -> None:
        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "original runtime\n")
        prompt_digest = _digest(self.workspace / ".hermes.md")
        runtime_digest = _digest(self.workspace / "sage" / "original.txt")
        staged = self.layout.stage_from_framework(self.framework)
        _write(staged.runtime_candidate / "runtime" / "tools" / "current.py", "tampered\n")
        try:
            with self.assertRaisesRegex(LayoutError, "candidate bytes changed"):
                staged.commit()
        finally:
            staged.cleanup()

        self.assertEqual(_digest(self.workspace / ".hermes.md"), prompt_digest)
        self.assertEqual(_digest(self.workspace / "sage" / "original.txt"), runtime_digest)

    def test_candidate_prompt_hardlink_swap_after_initial_check_is_rejected(self) -> None:
        """A staged leaf cannot change identity between validation and publish."""

        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "original runtime\n")
        prompt_digest = _digest(self.workspace / ".hermes.md")
        runtime_digest = _digest(self.workspace / "sage" / "original.txt")
        staged = self.layout.stage_from_framework(self.framework)
        outside = self.root / "outside-identical-prompt.md"
        shutil.copyfile(staged.instructions_candidate, outside)
        outside_digest = _digest(outside)
        real_fingerprints = workspace_layout_module._instruction_input_fingerprints
        swapped = [False]

        def swap_after_initial_check(*args: object, **kwargs: object):
            result = real_fingerprints(*args, **kwargs)
            if not swapped[0]:
                staged.instructions_candidate.unlink()
                os.link(outside, staged.instructions_candidate)
                swapped[0] = True
            return result

        try:
            with mock.patch.object(
                workspace_layout_module,
                "_instruction_input_fingerprints",
                side_effect=swap_after_initial_check,
            ):
                with self.assertRaisesRegex(
                    LayoutError, "hardlink|identity|candidate"
                ):
                    staged.commit()
        finally:
            # Keep the hostile inode out of fixture teardown on both the RED
            # path (where old code published it) and the fixed pre-publish
            # rejection path.
            if os.path.lexists(staged.instructions_candidate):
                if os.path.samefile(staged.instructions_candidate, outside):
                    staged.instructions_candidate.unlink()
            published = self.workspace / ".hermes.md"
            if os.path.lexists(published) and os.path.samefile(published, outside):
                published.unlink()
                _write(published, "original prompt\n")
            staged.cleanup()

        self.assertTrue(swapped[0])
        self.assertEqual(_digest(self.workspace / ".hermes.md"), prompt_digest)
        self.assertEqual(_digest(self.workspace / "sage" / "original.txt"), runtime_digest)
        self.assertEqual(_digest(outside), outside_digest)
        self.assertEqual(outside.stat().st_nlink, 1)

    def test_published_prompt_hardlink_swap_before_return_is_rejected(self) -> None:
        """A published prompt swapped to a hardlink is rejected and rolled back.

        The multi-link case trips the nlink rule inside the final publication
        bytes check (``_candidate_manifest.measured``); the alias cases that
        only the return-window identity re-check can catch are covered by the
        identical-content swap probes below.
        """

        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "original runtime\n")
        prompt_digest = _digest(self.workspace / ".hermes.md")
        runtime_digest = _digest(self.workspace / "sage" / "original.txt")
        staged = self.layout.stage_from_framework(self.framework)
        outside = self.root / "outside-identical-published-prompt.md"
        outside_digest = [""]
        real_manifest = workspace_layout_module._candidate_manifest
        swapped = [False]

        def swap_published_prompt(*args: pathlib.Path, **kwargs: object):
            # The final publication bytes check is the last hook point before
            # the return-path identity re-check; swap to an identical-content
            # hardlink there so only the identity guard can catch it.
            if (
                len(args) >= 2
                and args[1] == self.layout.homes.instructions_path
                and not swapped[0]
            ):
                shutil.copyfile(self.layout.homes.instructions_path, outside)
                outside_digest[0] = _digest(outside)
                self.layout.homes.instructions_path.unlink()
                os.link(outside, self.layout.homes.instructions_path)
                swapped[0] = True
            return real_manifest(*args, **kwargs)

        try:
            with mock.patch.object(
                workspace_layout_module,
                "_candidate_manifest",
                side_effect=swap_published_prompt,
            ):
                with self.assertRaisesRegex(
                    LayoutError, "single-link regular local candidate"
                ):
                    staged.commit()
        finally:
            # Keep the hostile inode out of fixture teardown on both the RED
            # path (where an unguarded return published it) and the fixed
            # post-publish rejection path that moved it into staging.
            published = self.workspace / ".hermes.md"
            if (
                os.path.lexists(outside)
                and os.path.lexists(published)
                and os.path.samefile(published, outside)
            ):
                published.unlink()
                _write(published, "original prompt\n")
            failed = staged.staging_root / "failed-hermes.md"
            if (
                os.path.lexists(outside)
                and os.path.lexists(failed)
                and os.path.samefile(failed, outside)
            ):
                failed.unlink()
            staged.cleanup()

        self.assertTrue(swapped[0])
        self.assertEqual(_digest(self.workspace / ".hermes.md"), prompt_digest)
        self.assertEqual(_digest(self.workspace / "sage" / "original.txt"), runtime_digest)
        self.assertEqual(_digest(outside), outside_digest[0])
        self.assertEqual(outside.stat().st_nlink, 1)

    def test_published_runtime_alias_swap_before_return_is_rejected(self) -> None:
        """An identical-bytes runtime leaf with a fresh inode is still an alias."""

        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "original runtime\n")
        prompt_digest = _digest(self.workspace / ".hermes.md")
        runtime_digest = _digest(self.workspace / "sage" / "original.txt")
        staged = self.layout.stage_from_framework(self.framework)
        published_leaf = (
            self.layout.homes.runtime_root / "runtime" / "tools" / "current.py"
        )
        real_manifest = workspace_layout_module._candidate_manifest
        swapped = [False]

        def swap_published_runtime_leaf(*args: pathlib.Path, **kwargs: object):
            if (
                len(args) >= 2
                and args[1] == self.layout.homes.instructions_path
                and not swapped[0]
            ):
                alias = published_leaf.parent / (published_leaf.name + ".alias-tmp")
                shutil.copyfile(published_leaf, alias)
                os.replace(os.fspath(alias), os.fspath(published_leaf))
                swapped[0] = True
            return real_manifest(*args, **kwargs)

        try:
            with mock.patch.object(
                workspace_layout_module,
                "_candidate_manifest",
                side_effect=swap_published_runtime_leaf,
            ):
                with self.assertRaisesRegex(
                    LayoutError, "identity changed before return"
                ):
                    staged.commit()
        finally:
            staged.cleanup()

        self.assertTrue(swapped[0])
        self.assertEqual(_digest(self.workspace / ".hermes.md"), prompt_digest)
        self.assertEqual(_digest(self.workspace / "sage" / "original.txt"), runtime_digest)

    def test_published_prompt_alias_swap_before_return_is_rejected(self) -> None:
        """An identical-bytes published prompt with a fresh inode is still an alias."""

        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "original runtime\n")
        prompt_digest = _digest(self.workspace / ".hermes.md")
        runtime_digest = _digest(self.workspace / "sage" / "original.txt")
        staged = self.layout.stage_from_framework(self.framework)
        published = self.layout.homes.instructions_path
        real_manifest = workspace_layout_module._candidate_manifest
        swapped = [False]

        def swap_published_prompt_leaf(*args: pathlib.Path, **kwargs: object):
            if (
                len(args) >= 2
                and args[1] == self.layout.homes.instructions_path
                and not swapped[0]
            ):
                alias = published.parent / (published.name + ".alias-tmp")
                shutil.copyfile(published, alias)
                os.replace(os.fspath(alias), os.fspath(published))
                swapped[0] = True
            return real_manifest(*args, **kwargs)

        try:
            with mock.patch.object(
                workspace_layout_module,
                "_candidate_manifest",
                side_effect=swap_published_prompt_leaf,
            ):
                with self.assertRaisesRegex(
                    LayoutError, "identity changed before return"
                ):
                    staged.commit()
        finally:
            staged.cleanup()

        self.assertTrue(swapped[0])
        self.assertEqual(_digest(self.workspace / ".hermes.md"), prompt_digest)
        self.assertEqual(_digest(self.workspace / "sage" / "original.txt"), runtime_digest)

    def test_injected_commit_failure_restores_both_prior_managed_surfaces(self) -> None:
        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "original runtime\n")
        prompt_digest = _digest(self.workspace / ".hermes.md")
        runtime_digest = _digest(self.workspace / "sage" / "original.txt")
        staged = self.layout.stage_from_framework(self.framework)
        real_replace = workspace_layout_module.os.replace
        calls = [0]

        def fail_candidate_prompt_once(source: str, target: str) -> None:
            calls[0] += 1
            if calls[0] == 4:
                raise OSError("injected prompt commit failure")
            real_replace(source, target)

        try:
            with mock.patch.object(
                workspace_layout_module.os,
                "replace",
                side_effect=fail_candidate_prompt_once,
            ):
                with self.assertRaisesRegex(LayoutError, "prior managed bytes were restored"):
                    staged.commit()
        finally:
            staged.cleanup()

        self.assertEqual(_digest(self.workspace / ".hermes.md"), prompt_digest)
        self.assertEqual(_digest(self.workspace / "sage" / "original.txt"), runtime_digest)

    def test_double_failure_preserves_only_prior_runtime_and_recovery_staging(self) -> None:
        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "only prior runtime\n")
        captured = []
        original_stage = WorkspaceLayout.stage_from_framework
        real_replace = workspace_layout_module.os.replace

        def capture_stage(layout: WorkspaceLayout, framework_root: pathlib.Path):
            staged = original_stage(layout, framework_root)
            captured.append(staged)
            return staged

        def fail_commit_and_runtime_rollback(source: str, target: str) -> None:
            source_path = pathlib.Path(source)
            target_path = pathlib.Path(target)
            staged = captured[0]
            if source_path == staged.instructions_candidate and target_path == self.layout.homes.instructions_path:
                raise OSError("injected prompt commit failure")
            if (
                source_path == staged.staging_root / "backup" / "sage"
                and target_path == self.layout.homes.runtime_root
            ):
                raise OSError("injected runtime rollback failure")
            real_replace(source, target)

        with mock.patch.object(WorkspaceLayout, "stage_from_framework", new=capture_stage):
            with mock.patch.object(
                workspace_layout_module.os,
                "replace",
                side_effect=fail_commit_and_runtime_rollback,
            ):
                with self.assertRaises(LayoutError) as caught:
                    self.layout.refresh_from_framework(self.framework)

        staged = captured[0]
        self.assertIn("RECOVERY REQUIRED", str(caught.exception))
        self.assertTrue(staged.recovery_required)
        self.assertTrue(staged.staging_root.is_dir())
        recovery_runtime = staged.staging_root / "backup" / "sage" / "original.txt"
        self.assertEqual(recovery_runtime.read_text(), "only prior runtime\n")
        self.assertIn(staged.staging_root / "backup" / "sage", staged.recovery_paths)
        self.assertTrue((staged.staging_root / "RECOVERY_REQUIRED.txt").is_file())
        self.assertEqual(
            list(staged.staging_root.glob(".RECOVERY_REQUIRED.txt.*.tmp")), []
        )
        with self.assertRaisesRegex(LayoutError, "recovery"):
            staged.cleanup()
        shutil.rmtree(staged.staging_root)

    def test_recovery_marker_symlink_cannot_escape_staging(self) -> None:
        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "only prior runtime\n")
        outside = self.root / "outside-recovery-marker.txt"
        _write(outside, "outside must remain byte-identical\n")
        outside_digest = _digest(outside)
        captured = []
        original_stage = WorkspaceLayout.stage_from_framework
        real_replace = workspace_layout_module.os.replace

        def capture_stage(layout: WorkspaceLayout, framework_root: pathlib.Path):
            staged = original_stage(layout, framework_root)
            marker = staged.staging_root / "RECOVERY_REQUIRED.txt"
            try:
                marker.symlink_to(outside)
            except OSError as exc:
                staged.cleanup()
                self.skipTest("file symlink creation unavailable: %s" % exc)
            captured.append(staged)
            return staged

        def fail_commit_and_runtime_rollback(source: str, target: str) -> None:
            source_path = pathlib.Path(source)
            target_path = pathlib.Path(target)
            staged = captured[0]
            if source_path == staged.instructions_candidate and target_path == self.layout.homes.instructions_path:
                raise OSError("injected prompt commit failure")
            if (
                source_path == staged.staging_root / "backup" / "sage"
                and target_path == self.layout.homes.runtime_root
            ):
                raise OSError("injected runtime rollback failure")
            real_replace(source, target)

        with mock.patch.object(WorkspaceLayout, "stage_from_framework", new=capture_stage):
            with mock.patch.object(
                workspace_layout_module.os,
                "replace",
                side_effect=fail_commit_and_runtime_rollback,
            ):
                with self.assertRaises(LayoutError) as caught:
                    self.layout.refresh_from_framework(self.framework)

        staged = captured[0]
        marker = staged.staging_root / "RECOVERY_REQUIRED.txt"
        self.assertIn("RECOVERY REQUIRED", str(caught.exception))
        self.assertIn("recovery marker", str(caught.exception))
        self.assertEqual(_digest(outside), outside_digest)
        self.assertTrue((staged.staging_root / "backup" / "sage" / "original.txt").is_file())
        self.assertTrue(staged.recovery_required)
        self.assertEqual(staged.recovery_marker_path, marker)
        with self.assertRaises(AttributeError):
            setattr(staged, "recovery_marker_path", outside)
        self.assertTrue(marker.is_symlink())
        self.assertNotIn(outside.resolve(), tuple(path.resolve() for path in staged.recovery_paths))
        if marker.is_symlink():
            marker.unlink()
        shutil.rmtree(staged.staging_root)

    def test_recovery_marker_post_publish_hardlink_swap_is_not_reported(self) -> None:
        _write(self.workspace / ".hermes.md", "original prompt\n")
        _write(self.workspace / "sage" / "original.txt", "only prior runtime\n")
        outside = self.root / "outside-hardlink-target.txt"
        _write(outside, "outside hardlink fixture must remain byte-identical\n")
        outside_digest = _digest(outside)
        captured = []
        swap_count = [0]
        original_stage = WorkspaceLayout.stage_from_framework
        real_replace = workspace_layout_module.os.replace

        def capture_stage(layout: WorkspaceLayout, framework_root: pathlib.Path):
            staged = original_stage(layout, framework_root)
            captured.append(staged)
            return staged

        def fail_commit_rollback_then_swap_marker(source: str, target: str) -> None:
            source_path = pathlib.Path(source)
            target_path = pathlib.Path(target)
            staged = captured[0]
            marker = staged.recovery_marker_path
            if source_path == staged.instructions_candidate and target_path == self.layout.homes.instructions_path:
                raise OSError("injected prompt commit failure")
            if (
                source_path == staged.staging_root / "backup" / "sage"
                and target_path == self.layout.homes.runtime_root
            ):
                raise OSError("injected runtime rollback failure")
            if target_path == marker and source_path.name.startswith(
                ".RECOVERY_REQUIRED.txt."
            ):
                real_replace(source, target)
                marker.unlink()
                os.link(outside, marker)
                swap_count[0] += 1
                return
            real_replace(source, target)

        with mock.patch.object(WorkspaceLayout, "stage_from_framework", new=capture_stage):
            with mock.patch.object(
                workspace_layout_module.os,
                "replace",
                side_effect=fail_commit_rollback_then_swap_marker,
            ):
                with self.assertRaises(LayoutError) as caught:
                    self.layout.refresh_from_framework(self.framework)

        staged = captured[0]
        marker = staged.recovery_marker_path
        backup_runtime = staged.staging_root / "backup" / "sage"
        self.assertIn("RECOVERY REQUIRED", str(caught.exception))
        self.assertEqual(swap_count[0], 1)
        self.assertEqual(_digest(outside), outside_digest)
        self.assertEqual(marker.stat().st_nlink, 2)
        self.assertNotIn(marker, staged.recovery_paths)
        self.assertIn(backup_runtime, staged.recovery_paths)
        self.assertIn(staged.staging_root, staged.recovery_paths)
        self.assertEqual(
            (backup_runtime / "original.txt").read_text(encoding="utf-8"),
            "only prior runtime\n",
        )
        marker.unlink()
        shutil.rmtree(staged.staging_root)

    def test_constitution_is_emitted_by_and_tracks_canonical_shell_source(self) -> None:
        self._seed_durable_state()
        first = self.layout.refresh_from_framework(self.framework)
        first_prompt = (self.workspace / ".hermes.md").read_text(encoding="utf-8")
        first_inputs = {item.relative_path: item.sha256 for item in first.instruction_inputs}
        constitution_key = "framework:runtime/platforms/_shared/constitution.sh"
        self.assertIn("Constitution from canonical emitter v1", first_prompt)
        self.assertIn(constitution_key, first_inputs)

        constitution = (
            self.framework
            / "runtime"
            / "platforms"
            / "_shared"
            / "constitution.sh"
        )
        constitution.write_text(
            constitution.read_text(encoding="utf-8").replace(
                "canonical emitter v1", "canonical emitter drifted"
            ),
            encoding="utf-8",
        )
        second = self.layout.refresh_from_framework(self.framework)
        second_prompt = (self.workspace / ".hermes.md").read_text(encoding="utf-8")
        second_inputs = {item.relative_path: item.sha256 for item in second.instruction_inputs}
        self.assertIn("Constitution from canonical emitter drifted", second_prompt)
        self.assertNotEqual(first_inputs[constitution_key], second_inputs[constitution_key])

    def test_staging_copy_failure_restores_fresh_workspace_zero_write_state(self) -> None:
        soul_digest = _digest(self.soul)
        with mock.patch.object(
            workspace_layout_module.shutil,
            "copytree",
            side_effect=OSError("injected copy failure"),
        ):
            with self.assertRaises(LayoutError):
                self.layout.stage_from_framework(self.framework)

        self.assertEqual(_digest(self.soul), soul_digest)
        self.assertFalse((self.workspace / ".sage").exists())
        self.assertFalse((self.workspace / ".sage-memory").exists())
        self.assertFalse((self.workspace / ".hermes.md").exists())
        self.assertFalse((self.workspace / "sage").exists())

    def test_framework_source_must_not_overlap_bound_workspace(self) -> None:
        overlap = self.workspace / "framework-source"
        shutil.copytree(self.framework, overlap)
        staged = None
        try:
            staged = self.layout.stage_from_framework(overlap)
        except LayoutError as exc:
            self.assertIn("overlap", str(exc).lower())
        else:
            self.fail("overlapping framework source was accepted")
        finally:
            if staged is not None:
                staged.cleanup()
        self.assertFalse((self.workspace / ".sage").exists())
        self.assertFalse((self.workspace / ".sage-memory").exists())

        ancestor = self.root / "ancestor-framework"
        shutil.copytree(self.framework, ancestor)
        nested_collection = ancestor / "hermes"
        nested_profile = nested_collection / "profiles" / "nested"
        nested_workspace = nested_profile / "workspace"
        nested_workspace.mkdir(parents=True)
        nested_binding = ProfileBinding.from_explicit(
            collection_root=nested_collection,
            profile_id="nested",
            profile_root=nested_profile,
            workspace_root=nested_workspace,
        )
        nested_layout = WorkspaceLayout.from_binding(nested_binding)
        with self.assertRaisesRegex(LayoutError, "overlap"):
            nested_layout.stage_from_framework(ancestor)
        self.assertFalse((nested_workspace / ".sage").exists())
        self.assertFalse((nested_workspace / ".sage-memory").exists())

    def test_forbidden_hermes_host_artifacts_are_rejected_recursively(self) -> None:
        cases = {
            "soul": (("runtime", "nested", "SOUL.md"),),
            "claude-file": (("runtime", "nested", "CLAUDE.md"),),
            "claude-dir": (("runtime", "nested", ".claude", "settings.json"),),
            "agent-hooks": (("runtime", "nested", "agent-hooks", "hook.sh"),),
            "gateway-bundle": (
                ("runtime", "nested", "gateway", "HOOK.yaml"),
                ("runtime", "nested", "gateway", "handler.py"),
            ),
        }
        for label, relatives in cases.items():
            with self.subTest(label=label):
                source = self.root / ("framework-forbidden-" + label)
                shutil.copytree(self.framework, source)
                for relative in relatives:
                    _write(source.joinpath(*relative), "forbidden\n")
                staged = None
                try:
                    staged = self.layout.stage_from_framework(source)
                except LayoutError as exc:
                    self.assertIn("forbidden", str(exc).lower())
                else:
                    self.fail("forbidden runtime artifact was accepted: %s" % label)
                finally:
                    if staged is not None:
                        staged.cleanup()

    def test_forbidden_artifact_injected_into_candidate_is_rejected(self) -> None:
        original_copy = workspace_layout_module._copy_runtime

        def inject_after_copy(framework_root: pathlib.Path, candidate: pathlib.Path) -> None:
            original_copy(framework_root, candidate)
            _write(candidate / "runtime" / "late" / "SOUL.md", "injected\n")

        staged = None
        with mock.patch.object(
            workspace_layout_module,
            "_copy_runtime",
            side_effect=inject_after_copy,
        ):
            try:
                staged = self.layout.stage_from_framework(self.framework)
            except LayoutError as exc:
                self.assertIn("forbidden", str(exc).lower())
            else:
                self.fail("forbidden candidate artifact was accepted")
            finally:
                if staged is not None:
                    staged.cleanup()
        self.assertFalse((self.workspace / ".sage").exists())
        self.assertFalse((self.workspace / ".sage-memory").exists())

    def test_layout_authority_is_immutable_and_all_homes_are_exact(self) -> None:
        with self.assertRaises((AttributeError, FrozenInstanceError)):
            self.layout.binding = object()
        with self.assertRaises((AttributeError, FrozenInstanceError)):
            self.layout.homes = self.layout.homes

        home_fields = fields(self.layout.homes)
        self.assertEqual(len(home_fields), 19)
        for field in home_fields:
            with self.subTest(field=field.name):
                layout = WorkspaceLayout.from_binding(self.binding)
                redirected = self.binding.state_root / "redirected" / field.name
                object.__setattr__(
                    layout,
                    "homes",
                    replace(layout.homes, **{field.name: redirected}),
                )
                with self.assertRaisesRegex(LayoutError, field.name):
                    layout.assert_exact_homes()

    @unittest.skipUnless(os.name == "nt", "Windows hardlink identity proof")
    def test_every_derived_file_target_rejects_hardlink_aliases(self) -> None:
        initiative = self.layout.initiative_homes("hardlink-initiative")
        targets = {
            "instructions": self.layout.homes.instructions_path,
            "config": self.layout.homes.config_path,
            "session_lock": self.layout.homes.session_lock_path,
            "session_pickup": self.layout.homes.session_pickup_path,
            "session_log": self.layout.homes.session_log_path,
            "gate_blocks": self.layout.homes.gate_blocks_log_path,
            "verification_state": self.layout.homes.verification_state_path,
            "decisions": self.layout.homes.decisions_path,
            "pack_lock": self.layout.homes.pack_lock_path,
            "receipt": self.layout.homes.receipt_path,
            "memory_db": self.layout.homes.memory_db_path,
            "constitution": self.layout.homes.state_root / "constitution.md",
            "run_journal": self.binding.run_journal_path("hardlink-run"),
            "initiative_manifest": initiative.manifest_path,
            "initiative_decisions": initiative.decisions_path,
            "initiative_review": initiative.review_ledger_path,
            "initiative_autoresearch": initiative.autoresearch_log_path,
            "initiative_autonomy": initiative.autonomy_log_path,
            "initiative_scope": initiative.scope_journal_path,
        }
        outside_root = self.root / "outside-hardlink-targets"
        outside_root.mkdir()

        for label, target in targets.items():
            with self.subTest(target=label):
                target.parent.mkdir(parents=True, exist_ok=True)
                outside = outside_root / (label + ".txt")
                _write(outside, "outside bytes for %s\n" % label)
                outside_digest = _digest(outside)
                os.link(outside, target)
                try:
                    with self.assertRaisesRegex(LayoutError, "hardlink|link count|alias"):
                        self.layout.assert_writable_target(target)
                    with self.assertRaisesRegex(LayoutError, "hardlink|link count|alias"):
                        self.layout.assert_exact_homes()
                    self.assertEqual(_digest(outside), outside_digest)
                finally:
                    target.unlink()

        beta_profile = self.collection / "profiles" / "beta"
        beta_workspace = beta_profile / "workspace"
        beta_workspace.mkdir(parents=True)
        beta_binding = ProfileBinding.from_explicit(
            collection_root=self.collection,
            profile_id="beta",
            profile_root=beta_profile,
            workspace_root=beta_workspace,
        )
        beta_layout = WorkspaceLayout.from_binding(beta_binding)
        shared_outside = outside_root / "shared-a-b-outside.txt"
        _write(shared_outside, "shared outside bytes\n")
        shared_digest = _digest(shared_outside)
        alpha_target = self.layout.homes.instructions_path
        beta_target = beta_layout.homes.instructions_path
        os.link(shared_outside, alpha_target)
        os.link(shared_outside, beta_target)
        try:
            for layout, target in (
                (self.layout, alpha_target),
                (beta_layout, beta_target),
            ):
                with self.subTest(profile=layout.binding.profile_id):
                    with self.assertRaisesRegex(LayoutError, "hardlink|link count|alias"):
                        layout.assert_writable_target(target)
                    with self.assertRaisesRegex(LayoutError, "hardlink|link count|alias"):
                        layout.assert_exact_homes()
            self.assertEqual(_digest(shared_outside), shared_digest)
        finally:
            alpha_target.unlink()
            beta_target.unlink()

    @unittest.skipUnless(os.name == "nt", "Windows exact-spelling authority proof")
    def test_all_19_homes_reject_case_and_namespace_authority_aliases(self) -> None:
        home_fields = fields(self.layout.homes)
        self.assertEqual(len(home_fields), 19)

        for home_field in home_fields:
            expected = getattr(self.layout.homes, home_field.name)
            variants = (
                ("case", _case_variant(expected)),
                ("namespace", _windows_namespace_variant(expected)),
            )
            for variant_kind, variant in variants:
                with self.subTest(field=home_field.name, variant=variant_kind):
                    with self.assertRaises(LayoutError):
                        self.layout.assert_writable_target(variant)
                    redirected = WorkspaceLayout.from_binding(self.binding)
                    object.__setattr__(
                        redirected,
                        "homes",
                        replace(
                            redirected.homes,
                            **{home_field.name: variant},
                        ),
                    )
                    with self.assertRaisesRegex(LayoutError, home_field.name):
                        redirected.assert_exact_homes()

    def test_equivalent_binding_loaded_under_another_module_name_is_revalidated(self) -> None:
        binding_path = SETUP / "profile_binding.py"
        spec = importlib.util.spec_from_file_location("foreign_profile_binding", binding_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        foreign = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = foreign
        try:
            spec.loader.exec_module(foreign)
            equivalent = foreign.ProfileBinding.from_explicit(
                collection_root=self.collection,
                profile_id="alpha",
                profile_root=self.profile,
                workspace_root=self.workspace,
            )
            parsed_only = foreign.ProfileBinding.from_mapping(
                equivalent.to_mapping()
            )
            with self.assertRaisesRegex(LayoutError, "authorit|ProfileBinding"):
                WorkspaceLayout.from_binding(parsed_only)
            layout = WorkspaceLayout.from_binding(equivalent)
        finally:
            sys.modules.pop(spec.name, None)
        self.assertIsInstance(layout.binding, ProfileBinding)
        self.assertEqual(layout.binding.to_mapping(), self.binding.to_mapping())

    def test_runtime_destination_with_nested_git_metadata_is_refused(self) -> None:
        _write(self.workspace / "sage" / ".git" / "HEAD", "ref: refs/heads/main\n")
        _write(self.workspace / "sage" / "owned.txt", "do not replace\n")
        digest = _digest(self.workspace / "sage" / "owned.txt")

        with self.assertRaisesRegex(LayoutError, "Git-managed"):
            self.layout.stage_from_framework(self.framework)

        self.assertEqual(_digest(self.workspace / "sage" / "owned.txt"), digest)

    @unittest.skipUnless(shutil.which("git"), "git is required for tracked-target proof")
    def test_runtime_tracked_by_workspace_repository_is_refused(self) -> None:
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.workspace,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _write(self.workspace / "sage" / "tracked.txt", "owned by project git\n")
        subprocess.run(
            ["git", "add", "--", "sage/tracked.txt"],
            cwd=self.workspace,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        with self.assertRaisesRegex(LayoutError, "Git-managed"):
            self.layout.stage_from_framework(self.framework)

        self.assertEqual(
            (self.workspace / "sage" / "tracked.txt").read_text(),
            "owned by project git\n",
        )

    def test_symlink_or_windows_junction_runtime_destination_is_refused(self) -> None:
        outside = self.root / "outside-runtime"
        outside.mkdir()
        _write(outside / "keep.txt", "outside\n")
        link = self.workspace / "sage"

        if os.name == "nt":
            proc = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", os.fspath(link), os.fspath(outside)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if proc.returncode != 0:
                self.skipTest("Windows junction creation unavailable: %s" % proc.stderr)
        else:
            link.symlink_to(outside, target_is_directory=True)

        try:
            with self.assertRaisesRegex(LayoutError, "link|reparse"):
                self.layout.stage_from_framework(self.framework)
            self.assertEqual((outside / "keep.txt").read_text(), "outside\n")
        finally:
            if link.exists() or link.is_symlink():
                if link.is_dir() and not link.is_symlink() and os.name == "nt":
                    os.rmdir(link)
                else:
                    link.unlink()


if __name__ == "__main__":
    unittest.main()
