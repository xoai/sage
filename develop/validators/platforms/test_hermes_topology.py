#!/usr/bin/env python3
"""Fail-on-drift checks for the Hermes install topology manifest."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import unittest
from typing import Any, Dict, Set, Tuple


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
TOPOLOGY = (
    REPO_ROOT
    / "runtime"
    / "platforms"
    / "community"
    / "hermes"
    / "setup"
    / "topology.json"
)
BUILD_PLUGIN = REPO_ROOT / "runtime" / "tools" / "build_plugin.py"
PLUGIN_OVERLAY_HOOKS = REPO_ROOT / "runtime" / "plugin-overlay" / "hooks" / "scripts"
PLUGIN_HOOKS_JSON = REPO_ROOT / "runtime" / "plugin-overlay" / "hooks" / "hooks.json"
PROJECT_HOOKS = REPO_ROOT / "runtime" / "platforms" / "claude-code" / "hooks"
PROJECT_GENERATOR = (
    REPO_ROOT
    / "runtime"
    / "platforms"
    / "claude-code"
    / "setup"
    / "generate-claude-code.sh"
)
BUILD_PLUGIN_SPEC = importlib.util.spec_from_file_location(
    "hermes_topology_build_plugin",
    BUILD_PLUGIN,
)
if BUILD_PLUGIN_SPEC is None or BUILD_PLUGIN_SPEC.loader is None:
    raise RuntimeError(f"cannot load canonical builder: {BUILD_PLUGIN}")
build_plugin = importlib.util.module_from_spec(BUILD_PLUGIN_SPEC)
BUILD_PLUGIN_SPEC.loader.exec_module(build_plugin)

CLASSIFICATIONS = {
    "hermes_shell_hook",
    "hermes_plugin_callback",
    "workflow_on_demand_gate",
    "intentionally_unsupported",
    "not_applicable",
}
REQUIRED_ROW_FIELDS = {
    "id",
    "classification",
    "sources",
    "build_owner",
    "package_source",
    "package_target",
    "install_target",
    "runtime_consumer",
    "hash_policy",
    "update_policy",
    "acceptance_test",
    "failure_contract",
    "package_source_sha256",
    "support_status",
    "callback",
    "event",
    "fail_closed",
}
EXPECTED_SHELL_HOOKS = {
    "sage-session-init.sh": ("on_session_start", None, False),
    "sage-spec-gate.sh": ("pre_tool_call", "write_file|patch", True),
    "sage-tdd-gate.sh": ("pre_tool_call", "write_file|patch", True),
    "sage-bookkeeping-gate.sh": ("pre_tool_call", "write_file|patch", True),
    "sage-secrets-gate.sh": ("pre_tool_call", "write_file|patch", True),
    "sage-verify-gate.sh": ("pre_tool_call", "terminal", True),
    "sage-config-gate.sh": ("pre_tool_call", "write_file|patch|terminal", True),
    "sage-scope-gate.sh": ("pre_tool_call", "write_file|patch", True),
    "sage-verify-tracker.sh": ("post_tool_call", "write_file|patch|terminal", False),
    "sage-degradation-log.sh": ("post_tool_call", "write_file|patch", False),
    "sage-manifest-sync.sh": ("post_tool_call", "write_file|patch", False),
    "sage-scope-journal.sh": ("post_tool_call", "write_file|patch|terminal", False),
}
WORKFLOW_GATES = {
    "sage-hallucination-check.sh",
    "sage-spec-check.sh",
    "sage-verify.sh",
    "sage-visual-gate.sh",
}
REQUIRED_SUBSYSTEMS = {
    "shared-framework",
    "project-runtime-workflows",
    "instructions-constitution",
    "project-state",
    "mechanical-hook-logic",
    "authoritative-hook-context",
    "hermes-plugin",
    "plugin-result-transformation",
    "core-persona-skills",
    "optional-packs",
    "quality-gates",
    "memory-mcp-tools",
    "goal-mode-metadata",
    "install-run-metadata",
}


def _repo_path(path: pathlib.Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _file_map() -> Dict[str, str]:
    tree = ast.parse(BUILD_PLUGIN.read_text(encoding="utf-8"))
    file_map = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "FILE_MAP"
            for target in node.targets
        ):
            file_map = ast.literal_eval(node.value)
            break
    if file_map is None:
        raise AssertionError("build_plugin.py has no literal FILE_MAP")

    return file_map


def _plugin_hook_sources() -> Set[Tuple[str, str]]:
    sources = {
        ("claude_plugin", source)
        for target, source in _file_map().items()
        if target.startswith("hooks/scripts/") and target.endswith(".sh")
    }
    sources.update(
        ("claude_plugin", _repo_path(path))
        for path in PLUGIN_OVERLAY_HOOKS.glob("sage-*.sh")
    )
    return sources


def _plugin_registration_metadata() -> Dict[Tuple[str, str], Tuple[Any, Any]]:
    by_name = {
        pathlib.PurePosixPath(target).name: source
        for target, source in _file_map().items()
        if target.startswith("hooks/scripts/") and target.endswith(".sh")
    }
    by_name.update(
        {path.name: _repo_path(path) for path in PLUGIN_OVERLAY_HOOKS.glob("sage-*.sh")}
    )
    metadata = {key: (None, None) for key in _plugin_hook_sources()}
    registered = set()
    registry = json.loads(PLUGIN_HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
    for event, groups in registry.items():
        for group in groups:
            matcher = group.get("matcher")
            for hook in group.get("hooks", []):
                match = re.search(r"(sage-[A-Za-z0-9-]+\.sh)", hook.get("command", ""))
                if not match:
                    continue
                name = match.group(1)
                if name not in by_name:
                    raise AssertionError(f"unowned Claude plugin hook command: {name}")
                key = ("claude_plugin", by_name[name])
                if key in registered:
                    raise AssertionError(f"duplicate Claude plugin hook registration: {key}")
                registered.add(key)
                metadata[key] = (event, matcher)
    return metadata


def _project_hook_sources() -> Set[Tuple[str, str]]:
    return {
        ("claude_project", _repo_path(path))
        for path in PROJECT_HOOKS.glob("sage-*.sh")
    }


def _project_registration_metadata() -> Dict[Tuple[str, str], Tuple[Any, Any]]:
    text = PROJECT_GENERATOR.read_text(encoding="utf-8")
    metadata = {}
    for event, matcher, name in re.findall(
        r'\("(PreToolUse|PostToolUse)",\s*"([^"]+)",\s*"(sage-[^"]+\.sh)"\)',
        text,
    ):
        key = ("claude_project", f"runtime/platforms/claude-code/hooks/{name}")
        if key in metadata:
            raise AssertionError(f"duplicate Claude project hook registration: {key}")
        metadata[key] = (
            event,
            matcher,
        )
    sessions = re.findall(
        r'"matcher":\s*"([^"]+)"[\s\S]{0,180}?sage-session-init\.sh', text
    )
    if len(sessions) != 1:
        raise AssertionError(
            f"expected one project session-init registration, found {len(sessions)}"
        )
    metadata[
        (
            "claude_project",
            "runtime/platforms/claude-code/hooks/sage-session-init.sh",
        )
    ] = ("SessionStart", sessions[0])
    return metadata


def _load_topology() -> Dict[str, Any]:
    if not TOPOLOGY.is_file():
        return {"hooks": []}
    return json.loads(TOPOLOGY.read_text(encoding="utf-8"))


def _manifest_surface_keys() -> Set[Tuple[str, str]]:
    data = _load_topology()
    return {
        (source["surface"], source["path"])
        for row in data.get("hooks", [])
        for source in row.get("sources", [])
    }


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(
        build_plugin.canonical_hermes_source_bytes(path)
    ).hexdigest()


class HermesTopologyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = _load_topology()
        cls.rows = cls.data.get("hooks", [])

    def test_every_current_claude_hook_surface_is_classified(self) -> None:
        expected = _plugin_hook_sources() | _project_hook_sources()
        self.assertEqual(expected, _manifest_surface_keys())

    def test_manifest_declares_platform_schema_and_no_gateway_bundle(self) -> None:
        self.assertEqual(1, self.data.get("schema_version"))
        self.assertEqual("hermes", self.data.get("platform"))
        self.assertEqual(
            build_plugin.HERMES_SOURCE_BYTE_POLICY,
            self.data.get("source_byte_policy"),
        )
        self.assertIsNone(self.data.get("gateway_bundle"))
        self.assertIsInstance(self.data.get("gateway_bundle_policy"), str)
        self.assertTrue(self.data.get("gateway_bundle_policy", "").strip())

    def test_manifest_source_paths_are_committed_as_lf_text(self) -> None:
        paths = {self.data["adapter"]["source"]}
        paths.update(row["source"] for row in self.data.get("plugin_files", []))
        for row in self.rows:
            paths.add(row["package_source"])
            paths.update(source["path"] for source in row["sources"])
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "check-attr",
                "-z",
                "text",
                "eol",
                "filter",
                "working-tree-encoding",
                "--",
                *sorted(paths),
            ],
            check=True,
            capture_output=True,
        )
        fields = proc.stdout.decode("utf-8").split("\0")
        attributes = {}
        for index in range(0, len(fields) - 1, 3):
            path, attribute, value = fields[index : index + 3]
            attributes.setdefault(path, {})[attribute] = value
        self.assertEqual(paths, set(attributes))
        for path in sorted(paths):
            with self.subTest(path=path):
                self.assertEqual("set", attributes[path]["text"])
                self.assertEqual("lf", attributes[path]["eol"])
                self.assertEqual("unset", attributes[path]["filter"])
                self.assertEqual(
                    "unset",
                    attributes[path]["working-tree-encoding"],
                )

    def test_rows_have_complete_ownership_metadata(self) -> None:
        self.assertTrue(self.rows, "topology must declare hook behaviors")
        ids = []
        surface_keys = []
        for row in self.rows:
            with self.subTest(row=row.get("id")):
                self.assertFalse(REQUIRED_ROW_FIELDS - set(row))
                self.assertIn(row["classification"], CLASSIFICATIONS)
                self.assertIn(row["support_status"], {"planned", "verified"})
                ids.append(row["id"])
                for field in (
                    "id",
                    "build_owner",
                    "package_source",
                    "package_target",
                    "install_target",
                    "runtime_consumer",
                    "hash_policy",
                    "update_policy",
                    "acceptance_test",
                    "failure_contract",
                ):
                    self.assertIsInstance(row[field], str)
                    self.assertTrue(row[field].strip(), field)
                self.assertTrue((REPO_ROOT / row["package_source"]).is_file())
                self.assertTrue((REPO_ROOT / row["build_owner"]).is_file())
                self.assertTrue((REPO_ROOT / row["acceptance_test"]).is_file())
                self.assertTrue(row["sources"])
                for source in row["sources"]:
                    self.assertEqual(
                        {"surface", "path", "sha256", "claude_event", "claude_matcher"},
                        set(source),
                    )
                    self.assertIn(source["surface"], {"claude_plugin", "claude_project"})
                    self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
                    self.assertTrue((REPO_ROOT / source["path"]).is_file())
                    surface_keys.append((source["surface"], source["path"]))
                if row["classification"] in {
                    "intentionally_unsupported",
                    "not_applicable",
                }:
                    self.assertTrue(row.get("reason", "").strip())
        self.assertEqual(len(ids), len(set(ids)), "behavior ids must be unique")
        self.assertEqual(
            len(surface_keys),
            len(set(surface_keys)),
            "each Claude hook surface must have exactly one classification",
        )

    def test_source_hashes_fail_on_byte_drift(self) -> None:
        for row in self.rows:
            self.assertEqual(
                _sha256(REPO_ROOT / row["package_source"]),
                row["package_source_sha256"],
            )
            for source in row["sources"]:
                with self.subTest(surface=source["surface"], path=source["path"]):
                    self.assertEqual(
                        _sha256(REPO_ROOT / source["path"]), source["sha256"]
                    )

        adapter = self.data["adapter"]
        self.assertEqual(
            _sha256(REPO_ROOT / adapter["source"]), adapter["source_sha256"]
        )

    def test_manifest_tracks_actual_claude_registration_tables(self) -> None:
        expected = _plugin_registration_metadata()
        expected.update(_project_registration_metadata())
        actual = {
            (source["surface"], source["path"]): (
                source["claude_event"],
                source["claude_matcher"],
            )
            for row in self.rows
            for source in row["sources"]
        }
        self.assertEqual(expected, actual)
        self.assertEqual(_project_hook_sources(), set(_project_registration_metadata()))

    def test_shell_registry_is_canonical_session_seven_blockers_four_observers(self) -> None:
        shell_rows = {
            row["id"]: row
            for row in self.rows
            if row["classification"] == "hermes_shell_hook"
        }
        self.assertEqual(set(EXPECTED_SHELL_HOOKS), set(shell_rows))

        blockers = [
            row for row in shell_rows.values()
            if row["event"] == "pre_tool_call" and row["fail_closed"] is True
        ]
        observers = [
            row for row in shell_rows.values()
            if row["event"] == "post_tool_call" and row["fail_closed"] is False
        ]
        sessions = [
            row for row in shell_rows.values()
            if row["event"] == "on_session_start" and row["fail_closed"] is False
        ]
        self.assertEqual(7, len(blockers))
        self.assertEqual(4, len(observers))
        self.assertEqual(1, len(sessions))

        for hook_id, (event, matcher, fail_closed) in EXPECTED_SHELL_HOOKS.items():
            row = shell_rows[hook_id]
            with self.subTest(hook=hook_id):
                self.assertEqual(event, row["event"])
                self.assertIs(fail_closed, row["fail_closed"])
                self.assertEqual(
                    {
                        "type": "config_shell_hook",
                        "event": event,
                        "matcher": matcher,
                        "fail_closed": fail_closed,
                    },
                    row["callback"],
                )

    def test_shell_targets_are_flat_and_all_targets_are_unique(self) -> None:
        adapter = self.data["adapter"]
        targets = [*self.rows, *self.data.get("plugin_files", []), adapter]
        package_targets = []
        install_targets = []
        forbidden = {"agent-hooks", "hook.yaml", "handler.py"}
        for row in targets:
            package_targets.append(row["package_target"])
            install_targets.append(row["install_target"])
            for field in ("package_target", "install_target"):
                target = row[field]
                self.assertNotIn("\\", target)
                self.assertFalse(target.startswith("/"), target)
                self.assertNotRegex(target, r"^[A-Za-z]:")
                parts = pathlib.PurePosixPath(target).parts
                self.assertNotIn("..", parts)
                self.assertFalse({part.casefold() for part in parts} & forbidden)
            if row.get("classification") == "hermes_shell_hook":
                self.assertEqual(
                    ("hooks", row["id"]),
                    pathlib.PurePosixPath(row["install_target"]).parts,
                )
                self.assertEqual(row["install_target"], row["package_target"])
        normalized_packages = {
            pathlib.PurePosixPath(target).as_posix().casefold()
            for target in package_targets
        }
        normalized_installs = {
            pathlib.PurePosixPath(target).as_posix().casefold()
            for target in install_targets
        }
        self.assertEqual(len(package_targets), len(normalized_packages))
        self.assertEqual(len(install_targets), len(normalized_installs))

    def test_plugin_support_files_are_explicit_hashed_builder_inputs(self) -> None:
        rows = self.data.get("plugin_files", [])
        self.assertEqual(
            {"sage-plugin-manifest", "sage-profile-binding-authority", "sage-memory-namespace"},
            {row.get("id") for row in rows},
        )
        expected_fields = {
            "id",
            "source",
            "source_sha256",
            "build_owner",
            "package_target",
            "install_target",
            "runtime_consumer",
            "hash_policy",
            "update_policy",
            "acceptance_test",
            "failure_contract",
            "support_status",
        }
        for row in rows:
            with self.subTest(plugin_file=row.get("id")):
                self.assertEqual(expected_fields, set(row))
                self.assertEqual(row["package_target"], row["install_target"])
                self.assertTrue(row["package_target"].startswith("plugins/sage/"))
                self.assertEqual("runtime/tools/build_plugin.py", row["build_owner"])
                self.assertEqual("verified", row["support_status"])
                self.assertEqual(
                    _sha256(REPO_ROOT / row["source"]),
                    row["source_sha256"],
                )
                for field in ("source", "build_owner", "acceptance_test"):
                    self.assertTrue((REPO_ROOT / row[field]).is_file())

    def test_workflow_gates_are_not_lifecycle_hooks(self) -> None:
        rows = {
            row["id"]: row
            for row in self.rows
            if row["classification"] == "workflow_on_demand_gate"
        }
        self.assertEqual(WORKFLOW_GATES, set(rows))
        for row in rows.values():
            self.assertIsNone(row["event"])
            self.assertIsNone(row["fail_closed"])
            self.assertIsNone(row["callback"])

    def test_session_init_is_installed_and_context_is_adapted(self) -> None:
        shell = next(row for row in self.rows if row["id"] == "sage-session-init.sh")
        self.assertEqual("hermes_shell_hook", shell["classification"])
        self.assertEqual("on_session_start", shell["event"])
        self.assertEqual(
            {
                (
                    "claude_project",
                    "runtime/platforms/claude-code/hooks/sage-session-init.sh",
                ),
            },
            {(source["surface"], source["path"]) for source in shell["sources"]},
        )

        row = next(row for row in self.rows if row["id"] == "session-context-injection")
        self.assertEqual("hermes_plugin_callback", row["classification"])
        self.assertEqual(
            {
                "type": "plugin_callbacks",
                "events": ["on_session_start", "pre_llm_call"],
            },
            row["callback"],
        )
        self.assertIsNone(row["event"])
        self.assertIsNone(row["fail_closed"])
        self.assertEqual(
            {
                (
                    "claude_plugin",
                    "runtime/plugin-overlay/hooks/scripts/sage-session-init.sh",
                ),
            },
            {(source["surface"], source["path"]) for source in row["sources"]},
        )

    def test_adapter_is_owned_flat_and_has_an_explicit_failure_contract(self) -> None:
        adapter = self.data["adapter"]
        self.assertEqual(
            {
                "source",
                "source_sha256",
                "build_owner",
                "package_target",
                "install_target",
                "runtime_consumer",
                "hash_policy",
                "update_policy",
                "acceptance_test",
                "failure_contract",
                "support_status",
            },
            set(adapter),
        )
        self.assertEqual("hooks/sage-hermes-gate.sh", adapter["install_target"])
        self.assertEqual(adapter["install_target"], adapter["package_target"])
        self.assertTrue((REPO_ROOT / adapter["source"]).is_file())
        self.assertTrue((REPO_ROOT / adapter["build_owner"]).is_file())
        self.assertTrue((REPO_ROOT / adapter["acceptance_test"]).is_file())
        self.assertIn(adapter["support_status"], {"planned", "verified"})
        for field in ("runtime_consumer", "hash_policy", "update_policy"):
            self.assertIsInstance(adapter[field], str)
            self.assertTrue(adapter[field].strip())
        self.assertEqual(
            {
                "missing_target",
                "missing_python",
                "missing_mktemp",
                "malformed_response",
            },
            set(adapter["failure_contract"]),
        )

    def test_dead_generator_never_owns_a_topology_entry(self) -> None:
        serialized = json.dumps(self.data, sort_keys=True)
        self.assertNotIn("generate-plugin.sh", serialized)

    def test_every_required_subsystem_has_an_explicit_support_disposition(self) -> None:
        subsystems = self.data.get("subsystems", [])
        self.assertEqual(REQUIRED_SUBSYSTEMS, {row.get("id") for row in subsystems})
        for row in subsystems:
            with self.subTest(subsystem=row.get("id")):
                self.assertEqual(
                    {
                        "id",
                        "canonical_source",
                        "build_owner",
                        "installed_target",
                        "runtime_consumer",
                        "update_policy",
                        "support_status",
                        "acceptance_test",
                        "reason",
                    },
                    set(row),
                )
                self.assertIn(row["support_status"], {"planned", "verified"})
                self.assertTrue((REPO_ROOT / row["build_owner"]).is_file())
                self.assertTrue(row["runtime_consumer"].strip())
                self.assertIsInstance(row["installed_target"], str)
                self.assertTrue(row["installed_target"].strip())
                self.assertIsInstance(row["update_policy"], str)
                self.assertTrue(row["update_policy"].strip())
                self.assertTrue(row["reason"].strip())
                if row["canonical_source"] is not None:
                    self.assertTrue((REPO_ROOT / row["canonical_source"]).exists())
                if row["support_status"] == "verified":
                    self.assertIsInstance(row["acceptance_test"], str)
                    self.assertTrue((REPO_ROOT / row["acceptance_test"]).is_file())
                else:
                    self.assertIsNone(row["acceptance_test"])

    def test_plugin_callback_contract_forbids_duplicate_python_gate_engines(self) -> None:
        callbacks = self.data.get("plugin_callbacks", {})
        self.assertEqual("verified", callbacks.get("support_status"))
        self.assertEqual(
            {"on_session_start", "pre_llm_call", "transform_tool_result"},
            set(callbacks.get("required", [])),
        )
        self.assertEqual(["pre_verify"], callbacks.get("optional"))
        self.assertEqual(
            {"pre_tool_call", "post_tool_call"},
            set(callbacks.get("forbidden_gate_duplicates", [])),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
