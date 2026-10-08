"""Profile-bound Sage lifecycle integration for Hermes.

The installed plugin is intentionally a thin native adapter.  Its only path
authority is the profile that physically contains this file, reconciled with
that profile's selected config and install receipt.  Mechanical gate ownership
remains in Hermes hooks installed at the profile root; this module does not
register Python ``pre_tool_call`` or ``post_tool_call`` gates.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import pathlib
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Dict, Mapping, Optional, Set, Tuple
from urllib.parse import unquote, urlparse


LOGGER = logging.getLogger(__name__)
# Single source of truth: the VERSION file at the plugin root. The runtime
# version check (_validate_runtime) requires workspace/sage/VERSION to equal
# this constant; deriving it here ends the 1.3.18/1.3.21 drift class
# (2026-08-30 diagnosis: "plugin.yaml version lag").
with open(
    pathlib.Path(__file__).absolute().parent / "VERSION", encoding="utf-8"
) as _version_file:
    PLUGIN_VERSION = _version_file.read().strip()

MAX_AUTHORITY_BYTES = 1024 * 1024
MAX_CONTEXT_BYTES = 2 * 1024 * 1024

SUPPORTED_SKILLS = (
    "sage",
    "sage-analyst",
    "sage-architect",
    "sage-autoresearch",
    "sage-build",
    "sage-checkpoints",
    "sage-classifier",
    "sage-constitution",
    "sage-continue",
    "sage-debugger",
    "sage-decisions",
    "sage-developer",
    "sage-fix",
    "sage-gates",
    "sage-learn",
    "sage-reflect",
    "sage-review",
    "sage-reviewer",
    "sage-routing",
    "sage-tiers",
    "sage-using-memory",
)

REGISTERED_HOOKS = (
    "on_session_start",
    "pre_llm_call",
    "transform_tool_result",
    "pre_verify",
)

RUNTIME_TOOLS = (
    "scope_judge.py",
    "manifest.py",
    "skill_manager.py",
    "sage_flags.py",
    "memory_sync.py",
)

# Slash commands are deliberately NOT registered (2026-09-01, Willie's bug):
# Hermes prints a plugin *command*'s return value to the user (cli.py
# `_cprint(str(result))`; gateway returns it as the reply) — it never reaches
# the model. ctx.register_skill() exposes the 21 namespaced skill_view entries;
# the installer's skills.external_dirs entry separately enables Hermes' native
# /sage-* skill commands, which DO load into the model turn. The registration
# alone does not enable native slash discovery. Registering the same names as
# commands double-listed them in the picker and let the command win
# dispatch, pasting the skill body as chat output instead of running it.
# Compatibility aliases (/sage-status -> sage-continue, etc.) are gone; the
# canonical skill names are the commands.
COMMAND_SPECS: Tuple[Tuple[str, str, str, str], ...] = ()

REGISTERED_COMMANDS = tuple(row[0] for row in COMMAND_SPECS)
REGISTERED_TOOLS = (
    "sage_run_gates",
    "sage_spec_check",
    "sage_hallucination_check",
    "sage_verify",
    "sage_visual_gate",
    "sage_memory_set_project",
    "sage_memory_store",
    "sage_memory_search",
)

_FORBIDDEN_AUTHORITY_ARGUMENTS = frozenset(
    {
        "cwd",
        "workspace",
        "workspace_root",
        "project",
        "project_root",
        "profile",
        "profile_root",
        "state_root",
        "memory_root",
        "memory_db",
        "memory_db_path",
        "hermes_home",
    }
)

DEFAULT_GATE_MODES = {
    "fix": {
        "mandatory": ["hallucination-check", "verification"],
        "optional": ["spec-compliance"],
        "skipped": ["constitution-compliance", "code-quality"],
    },
    "build": {
        "mandatory": [
            "spec-compliance",
            "constitution-compliance",
            "code-quality",
            "hallucination-check",
            "verification",
        ],
        "optional": [],
        "skipped": [],
    },
    "architect": {
        "mandatory": [
            "spec-compliance",
            "constitution-compliance",
            "code-quality",
            "hallucination-check",
            "verification",
        ],
        "optional": [],
        "skipped": [],
    },
}
GATE_ORDER = {
    "spec-compliance": 1,
    "constitution-compliance": 2,
    "code-quality": 3,
    "hallucination-check": 4,
    "verification": 5,
    "visual-verification": 6,
    "auto-qa": 8,
}
GATE_ALIASES = {
    "spec": "spec-compliance",
    "spec-check": "spec-compliance",
    "hallucination": "hallucination-check",
    "verify": "verification",
    "visual": "visual-verification",
    "visual-gate": "visual-verification",
    "visual-check": "visual-verification",
}
AGENT_REVIEW_GATES = {
    "constitution-compliance": "Review the active bound-workspace constitution.",
    "code-quality": "Run the code-quality review; no deterministic script owns this verdict.",
    "auto-qa": "Run Auto-QA when the active workflow requires it.",
}
SCRIPT_REVIEW_NOTES = {
    "spec-compliance": "Perform adversarial spec review before considering Gate 1 complete.",
    "hallucination-check": "Check non-obvious hallucinations the script cannot decide.",
    "verification": "Verify acceptance criteria beyond the test-runner output.",
    "visual-verification": "Review captured screenshots for visual correctness.",
}


def _object_schema(properties=None, required=None):
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


TOOL_SCHEMAS = {
    "sage_run_gates": {
        "name": "sage_run_gates",
        "description": "Run deterministic Sage gates for one bound-workspace workflow mode.",
        "parameters": _object_schema(
            {
                "mode": {"type": "string", "enum": ["fix", "build", "architect"]},
                "plan_file": {"type": "string"},
                "task_number": {"type": "integer", "minimum": 1},
                "target": {"type": "string"},
                "visual_url": {"type": "string"},
                "visual_output_dir": {"type": "string"},
                "optional_gates": {"type": "array", "items": {"type": "string"}},
                "include_optional": {"type": "boolean"},
            },
            ["mode"],
        ),
    },
    "sage_spec_check": {
        "name": "sage_spec_check",
        "description": "Run Sage Gate 1 against one plan task inside the bound workspace.",
        "parameters": _object_schema(
            {
                "plan_file": {"type": "string"},
                "task_number": {"type": "integer", "minimum": 1},
            },
            ["plan_file", "task_number"],
        ),
    },
    "sage_hallucination_check": {
        "name": "sage_hallucination_check",
        "description": "Run Sage Gate 4 inside the bound workspace.",
        "parameters": _object_schema({"target": {"type": "string"}}),
    },
    "sage_verify": {
        "name": "sage_verify",
        "description": "Run Sage Gate 5 against the bound workspace.",
        "parameters": _object_schema(),
    },
    "sage_visual_gate": {
        "name": "sage_visual_gate",
        "description": "Run Sage Gate 6 and write evidence only inside the bound workspace.",
        "parameters": _object_schema(
            {"url": {"type": "string"}, "output_dir": {"type": "string"}},
            ["url"],
        ),
    },
    "sage_memory_set_project": {
        "name": "sage_memory_set_project",
        "description": "Select the already-bound workspace memory database; no project override is accepted.",
        "parameters": _object_schema(),
    },
    "sage_memory_store": {
        "name": "sage_memory_store",
        "description": "Store project-only knowledge in the bound workspace database.",
        "parameters": _object_schema(
            {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "scope": {"type": "string", "enum": ["project"]},
            },
            ["title", "content"],
        ),
    },
    "sage_memory_search": {
        "name": "sage_memory_search",
        "description": "Search only the bound workspace memory database.",
        "parameters": _object_schema(
            {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "filter_tags": {"type": "array", "items": {"type": "string"}},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            ["query"],
        ),
    },
}


class PluginAuthorityError(RuntimeError):
    """The installed profile cannot prove exclusive authority for Sage."""


def _load_profile_binding_module():
    """Import packaged authority bytes, with a repo-collection fallback only.

    Pytest imports a repository-root ``__init__.py`` as a top-level module,
    where relative imports have no package parent.  The fallback keeps that
    collection mode working without allowing an installed plugin to escape to
    repository sources when its packaged authority module is absent.
    """

    if __package__:
        from . import profile_binding as module

        return module

    source = (
        pathlib.Path(__file__).resolve().parent
        / "runtime"
        / "platforms"
        / "community"
        / "hermes"
        / "setup"
        / "profile_binding.py"
    )
    if not source.is_file():
        raise ImportError("repository profile_binding fallback is unavailable")
    name = "_sage_repo_profile_binding_%s" % hashlib.sha256(
        os.fspath(source).encode("utf-8")
    ).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load repository profile_binding fallback")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


_PROFILE_BINDING_MODULE = _load_profile_binding_module()
BindingError = _PROFILE_BINDING_MODULE.BindingError
ProfileBinding = _PROFILE_BINDING_MODULE.ProfileBinding


def _load_memory_namespace_module():
    if __package__:
        from . import memory_namespace as module

        return module
    source = (
        pathlib.Path(__file__).resolve().parent
        / "runtime"
        / "platforms"
        / "community"
        / "hermes"
        / "plugin-overlay"
        / "memory_namespace.py"
    )
    if not source.is_file():
        raise ImportError("repository memory_namespace fallback is unavailable")
    name = "_sage_repo_memory_namespace_%s" % hashlib.sha256(
        os.fspath(source).encode("utf-8")
    ).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load repository memory_namespace fallback")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


_MEMORY_NAMESPACE_MODULE = _load_memory_namespace_module()
MemoryNamespaceError = _MEMORY_NAMESPACE_MODULE.MemoryNamespaceError


@dataclass(frozen=True)
class PluginBinding:
    """One validated immutable authority captured once by ``register(ctx)``."""

    authority: Any
    workspace_root: pathlib.Path
    runtime_root: pathlib.Path
    context: str
    skill_paths: Mapping[str, pathlib.Path]
    command_texts: Mapping[str, str]
    gate_scripts: Mapping[str, pathlib.Path]
    gate_modes_path: pathlib.Path
    bash_executable: str
    scope_judge: Any
    sage_flags: Any
    memory_namespace: Any


def _path_key(path: pathlib.Path) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def _same_path(left: pathlib.Path, right: pathlib.Path) -> bool:
    return _path_key(left) == _path_key(right)


def _contains(root: pathlib.Path, target: pathlib.Path) -> bool:
    try:
        common = os.path.commonpath((_path_key(root), _path_key(target)))
    except ValueError:
        return False
    return common == _path_key(root)


def _is_reparse(stat_result: os.stat_result) -> bool:
    attributes = getattr(stat_result, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _require_plain_directory(
    path: pathlib.Path,
    *,
    owner: Optional[pathlib.Path] = None,
    label: str,
) -> pathlib.Path:
    try:
        info = path.lstat()
        canonical = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PluginAuthorityError(
            "%s is unavailable or cannot be resolved: %s" % (label, exc)
        ) from exc
    if not stat.S_ISDIR(info.st_mode):
        raise PluginAuthorityError("%s is not a directory" % label)
    if path.is_symlink() or _is_reparse(info) or not _same_path(path, canonical):
        raise PluginAuthorityError(
            "%s must be a physical canonical directory, not a link or reparse point"
            % label
        )
    if owner is not None and not _contains(owner, canonical):
        raise PluginAuthorityError("%s escapes its bound owner" % label)
    return canonical


def _read_plain_text(
    path: pathlib.Path,
    *,
    owner: pathlib.Path,
    label: str,
    max_bytes: int,
) -> str:
    try:
        info = path.lstat()
        canonical = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PluginAuthorityError("%s is unavailable: %s" % (label, exc)) from exc
    if not stat.S_ISREG(info.st_mode):
        raise PluginAuthorityError("%s is not a regular file" % label)
    if path.is_symlink() or _is_reparse(info) or not _same_path(path, canonical):
        raise PluginAuthorityError(
            "%s must be a physical canonical file, not a link or reparse point"
            % label
        )
    if not _contains(owner, canonical):
        raise PluginAuthorityError("%s escapes its bound owner" % label)
    if info.st_size > max_bytes:
        raise PluginAuthorityError("%s exceeds the bounded read limit" % label)
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            raise PluginAuthorityError("%s exceeds the bounded read limit" % label)
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PluginAuthorityError("%s is not valid UTF-8" % label) from exc
    except OSError as exc:
        raise PluginAuthorityError("%s cannot be read: %s" % (label, exc)) from exc


def _reject_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PluginAuthorityError("duplicate authority key: %s" % key)
        result[key] = value
    return result


def _load_receipt(text: str) -> Mapping[str, Any]:
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except PluginAuthorityError:
        raise
    except (TypeError, ValueError) as exc:
        raise PluginAuthorityError("install receipt is not valid JSON: %s" % exc) from exc
    if not isinstance(value, dict):
        raise PluginAuthorityError("install receipt must be a mapping")
    if value.get("schema_version") != 1:
        raise PluginAuthorityError("install receipt schema_version must be 1")
    return value


def _load_yaml_mapping(text: str, label: str) -> Mapping[str, Any]:
    try:
        import yaml
        from yaml.resolver import BaseResolver
    except ImportError as exc:
        raise PluginAuthorityError(
            "%s requires the Hermes PyYAML dependency" % label
        ) from exc

    class UniqueKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                duplicate = key in result
            except TypeError as exc:
                raise PluginAuthorityError(
                    "%s contains an unhashable key" % label
                ) from exc
            if duplicate:
                raise PluginAuthorityError(
                    "%s contains duplicate key: %s" % (label, key)
                )
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueKeyLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    try:
        value = yaml.load(text, Loader=UniqueKeyLoader)
    except PluginAuthorityError:
        raise
    except yaml.YAMLError as exc:
        raise PluginAuthorityError(
            "%s is not valid YAML: %s" % (label, exc)
        ) from exc
    if not isinstance(value, dict):
        raise PluginAuthorityError("%s must be a mapping" % label)
    return value


def _load_config(text: str) -> Mapping[str, Any]:
    return _load_yaml_mapping(text, "selected profile config")


def _installed_roots() -> Tuple[pathlib.Path, pathlib.Path, pathlib.Path, str]:
    source = pathlib.Path(__file__).absolute()
    plugin_root = source.parent
    if plugin_root.name != "sage" or plugin_root.parent.name != "plugins":
        raise PluginAuthorityError(
            "installed plugin must live at <collection>/profiles/<id>/plugins/sage"
        )
    profile_root = plugin_root.parent.parent
    profiles_root = profile_root.parent
    collection_root = profiles_root.parent
    if profiles_root.name != "profiles" or not profile_root.name:
        raise PluginAuthorityError(
            "installed plugin path does not identify one Hermes profile"
        )
    collection = _require_plain_directory(collection_root, label="collection_root")
    profiles = _require_plain_directory(
        profiles_root, owner=collection, label="profiles_root"
    )
    profile = _require_plain_directory(
        profile_root, owner=profiles, label="installed profile_root"
    )
    plugins = _require_plain_directory(
        plugin_root.parent, owner=profile, label="installed plugins_root"
    )
    plugin = _require_plain_directory(
        plugin_root, owner=plugins, label="installed plugin_root"
    )
    _read_plain_text(
        source,
        owner=plugin,
        label="installed plugin entrypoint",
        max_bytes=MAX_CONTEXT_BYTES,
    )
    return collection, profile, plugin, profile.name


def _active_profile_root(expected: pathlib.Path) -> pathlib.Path:
    raw = os.environ.get("HERMES_HOME")
    if not raw:
        raise PluginAuthorityError(
            "active HERMES_HOME is required for selected-profile authority"
        )
    supplied = pathlib.Path(raw)
    if not supplied.is_absolute():
        raise PluginAuthorityError("active HERMES_HOME must be an absolute path")
    active = _require_plain_directory(supplied, label="active HERMES_HOME")
    if not _same_path(active, expected):
        raise PluginAuthorityError(
            "installed plugin profile and active HERMES_HOME do not match"
        )
    return active


def _enabled_for_selected_profile(config: Mapping[str, Any]) -> None:
    plugins = config.get("plugins")
    enabled = plugins.get("enabled") if isinstance(plugins, dict) else None
    if not isinstance(enabled, list) or "sage" not in enabled:
        raise PluginAuthorityError(
            "selected profile config does not enable the sage plugin"
        )


def _project_plugins_enabled() -> bool:
    return os.environ.get("HERMES_ENABLE_PROJECT_PLUGINS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _reject_project_collision(
    plugin_root: pathlib.Path,
    workspace_root: pathlib.Path,
) -> None:
    if not _project_plugins_enabled():
        return
    candidate = workspace_root / ".hermes" / "plugins" / "sage"
    if not candidate.exists():
        return
    try:
        collision = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PluginAuthorityError(
            "enabled project plugin collision cannot be resolved: %s" % exc
        ) from exc
    if not _same_path(collision, plugin_root):
        raise PluginAuthorityError(
            "enabled project plugin collision for key 'sage'; disable project "
            "plugins or remove the duplicate before loading the profile plugin"
        )


def _authorize_profile():
    collection, profile, plugin, profile_id = _installed_roots()
    _active_profile_root(profile)
    workspace = _require_plain_directory(
        profile / "workspace", owner=profile, label="bound workspace_root"
    )
    try:
        expected = ProfileBinding.from_explicit(
            collection_root=collection,
            profile_id=profile_id,
            profile_root=profile,
            workspace_root=workspace,
        )
    except BindingError as exc:
        raise PluginAuthorityError("installed profile binding is invalid: %s" % exc) from exc
    if not _same_path(expected.plugin_root, plugin):
        raise PluginAuthorityError(
            "installed plugin path does not match the derived profile binding"
        )

    config_text = _read_plain_text(
        expected.config_path,
        owner=profile,
        label="selected profile config",
        max_bytes=MAX_AUTHORITY_BYTES,
    )
    config = _load_config(config_text)
    _enabled_for_selected_profile(config)
    config_binding = config.get("sage_profile_binding")
    if not isinstance(config_binding, dict):
        raise PluginAuthorityError(
            "selected profile config is missing sage_profile_binding authority"
        )

    receipt_text = _read_plain_text(
        expected.receipt_path,
        owner=workspace,
        label="selected profile install receipt",
        max_bytes=MAX_AUTHORITY_BYTES,
    )
    receipt = _load_receipt(receipt_text)
    try:
        binding = ProfileBinding.from_authorities(
            receipt=receipt,
            config_binding=config_binding,
            collection_root=collection,
            profile_root=profile,
        )
        binding.assert_same(expected)
    except BindingError as exc:
        raise PluginAuthorityError(
            "selected profile config and receipt binding authorities disagree: %s"
            % exc
        ) from exc
    _reject_project_collision(plugin, binding.workspace_root)
    return binding


def _load_runtime_module(path: pathlib.Path):
    name = "_sage_bound_scope_judge_%s" % hashlib.sha256(
        os.fspath(path).encode("utf-8")
    ).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PluginAuthorityError("bound scope_judge module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(name, None)
        raise PluginAuthorityError(
            "bound scope_judge module failed to load: %s" % exc
        ) from exc
    return module


def _gate_bash_executable() -> str:
    if os.name == "nt":
        # Windows also ships System32/bash.exe, which is a WSL launcher and
        # cannot execute this native profile's paths. Resolve Git's own shell.
        git = shutil.which("git")
        if git:
            git_dir = pathlib.Path(git).resolve().parent
            candidates = [git_dir / "bash.exe", git_dir.parent / "bin" / "bash.exe"]
            if git_dir.name.casefold() == "bin" and git_dir.parent.name.casefold() in {
                "mingw64", "mingw32", "clangarm64", "ucrt64",
            }:
                candidates.append(git_dir.parent.parent / "bin" / "bash.exe")
            for candidate in candidates:
                if candidate.is_file():
                    return os.fspath(candidate.resolve())
        raise PluginAuthorityError("Git Bash is required for native Windows Sage gates")
    bash = shutil.which("bash")
    if not bash:
        raise PluginAuthorityError("bash is required for the bound Sage deterministic gate tools")
    return os.fspath(pathlib.Path(bash).resolve())


def _validate_runtime(binding) -> PluginBinding:
    workspace = binding.workspace_root
    runtime = _require_plain_directory(
        workspace / "sage", owner=workspace, label="bound Sage runtime"
    )
    version = _read_plain_text(
        runtime / "VERSION",
        owner=runtime,
        label="bound Sage runtime VERSION",
        max_bytes=1024,
    ).strip()
    if version != PLUGIN_VERSION:
        raise PluginAuthorityError(
            "bound Sage runtime version %r does not match plugin version %s"
            % (version, PLUGIN_VERSION)
        )

    context = _read_plain_text(
        workspace / ".hermes.md",
        owner=workspace,
        label="bound workspace .hermes.md",
        max_bytes=MAX_CONTEXT_BYTES,
    ).strip()
    if not context:
        raise PluginAuthorityError("bound workspace .hermes.md is empty")

    tools_root = _require_plain_directory(
        runtime / "runtime" / "tools",
        owner=runtime,
        label="bound Sage runtime tools",
    )
    tool_paths = {}
    for name in RUNTIME_TOOLS:
        path = tools_root / name
        _read_plain_text(
            path,
            owner=tools_root,
            label="bound runtime tool %s" % name,
            max_bytes=MAX_CONTEXT_BYTES,
        )
        tool_paths[name] = path

    skills_root = _require_plain_directory(
        runtime / "skills", owner=runtime, label="bound Sage runtime skills"
    )
    skill_paths = {}
    skill_texts = {}
    for name in SUPPORTED_SKILLS:
        skill_dir = _require_plain_directory(
            skills_root / name,
            owner=skills_root,
            label="bound runtime skill %s" % name,
        )
        skill_path = skill_dir / "SKILL.md"
        skill_texts[name] = _read_plain_text(
            skill_path,
            owner=skill_dir,
            label="bound runtime skill %s/SKILL.md" % name,
            max_bytes=MAX_CONTEXT_BYTES,
        )
        skill_paths[name] = skill_path

    command_texts = {}
    for command_name, skill_name, _prefix, _description in COMMAND_SPECS:
        if skill_name not in skill_texts:
            raise PluginAuthorityError(
                "command %s refers to an unvalidated bound skill %s"
                % (command_name, skill_name)
            )
        command_texts[command_name] = skill_texts[skill_name]

    gates_root = _require_plain_directory(
        runtime / "core" / "gates" / "scripts",
        owner=runtime,
        label="bound Sage gate scripts",
    )
    gate_scripts = {}
    for name in (
        "sage-spec-check.sh",
        "sage-hallucination-check.sh",
        "sage-verify.sh",
        "sage-visual-gate.sh",
    ):
        path = gates_root / name
        _read_plain_text(
            path,
            owner=gates_root,
            label="bound gate script %s" % name,
            max_bytes=MAX_CONTEXT_BYTES,
        )
        gate_scripts[name] = path

    gate_modes_path = runtime / "core" / "gates" / "_config" / "gate-modes.yaml"
    _read_plain_text(
        gate_modes_path,
        owner=runtime,
        label="bound gate modes",
        max_bytes=MAX_AUTHORITY_BYTES,
    )
    bash_executable = _gate_bash_executable()

    return PluginBinding(
        authority=binding,
        workspace_root=workspace,
        runtime_root=runtime,
        context=context,
        skill_paths=MappingProxyType(skill_paths),
        command_texts=MappingProxyType(command_texts),
        gate_scripts=MappingProxyType(gate_scripts),
        gate_modes_path=gate_modes_path,
        bash_executable=os.fspath(pathlib.Path(bash_executable).resolve()),
        scope_judge=_load_runtime_module(tool_paths["scope_judge.py"]),
        sage_flags=_load_runtime_module(tool_paths["sage_flags.py"]),
        memory_namespace=_MEMORY_NAMESPACE_MODULE,
    )

_RUNTIME = None
_CONTEXT_SESSIONS: Set[str] = set()


def _runtime() -> PluginBinding:
    if _RUNTIME is None:
        raise PluginAuthorityError("Sage plugin has not completed registration")
    return _RUNTIME


def _parse_frontmatter(text: str) -> Mapping[str, Any]:
    """The YAML frontmatter mapping of a manifest, or {} when there is none.

    Trade-off (review-pinned 2026-08-10): an UNCLOSED fence (crash-truncated
    manifest write) returns {} rather than raising, so a quality_locked cycle
    would report all-false and pre_verify would stay silent. Fail-open keeps
    sessions alive on a corrupt manifest; a loud failure would brick the
    plugin on a partial write. Accepted because the manifest writer
    (manifest.py close-out) is single-pass and the workspace_layout commit
    path guards published bytes.
    """

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return {}
    return _load_yaml_mapping(
        "\n".join(lines[1:end]), "active cycle manifest frontmatter"
    )


def _read_platform_contract(runtime: PluginBinding) -> Optional[Mapping[str, Any]]:
    """The vendored Hermes platform contract, or None when the runtime lacks one.

    A missing contract is not an error: it is the degraded default — the
    subagent capability must be treated as unavailable (ADR-10 loud
    degradation), never assumed.
    """

    contract_path = (
        runtime.runtime_root
        / "runtime"
        / "platforms"
        / "community"
        / "hermes"
        / "platform.yaml"
    )
    try:
        text = _read_plain_text(
            contract_path,
            owner=runtime.runtime_root,
            label="Hermes platform contract",
            max_bytes=MAX_AUTHORITY_BYTES,
        )
    except PluginAuthorityError:
        return None
    return _load_yaml_mapping(text, "Hermes platform contract")


def cycle_metadata(binding: Optional[PluginBinding] = None) -> Dict[str, Any]:
    """Consume the bound workspace's active-cycle metadata.

    Reads only the frozen binding's workspace — sibling workspaces and
    collection-global state are unreachable by construction. Subagent
    availability is resolved against the platform contract: a persisted flag
    is a request, never proof the capability exists.
    """

    runtime = binding or _runtime()
    workspace = runtime.workspace_root
    cycle = runtime.scope_judge.active_cycle(workspace)
    if cycle is None:
        return {
            "cycle": None,
            "goal": None,
            "quality_locked": False,
            "autonomous": False,
            "subagents": False,
            "execution_mode": "inline",
            "degraded": False,
            "announcement": None,
        }
    manifest_text = _read_plain_text(
        cycle / "manifest.md",
        owner=workspace,
        label="active cycle manifest",
        max_bytes=MAX_AUTHORITY_BYTES,
    )
    frontmatter = _parse_frontmatter(manifest_text)
    flags = frontmatter.get("flags")
    if not isinstance(flags, Mapping):
        flags = {}
    goal = frontmatter.get("goal")
    resolution = runtime.sage_flags.resolve_execution_mode(
        flags.get("subagents") is True, _read_platform_contract(runtime)
    )
    return {
        "cycle": cycle.name,
        "goal": goal if isinstance(goal, str) else None,
        "quality_locked": flags.get("quality_locked") is True,
        "autonomous": flags.get("autonomous") is True,
        "subagents": flags.get("subagents") is True,
        "execution_mode": resolution["manifest_value"],
        "degraded": resolution["degraded"],
        "announcement": resolution["announcement"],
    }


def binding_snapshot() -> Dict[str, str]:
    return _runtime().authority.to_mapping()


def runtime_inventory() -> Dict[str, Any]:
    binding = _runtime()
    return {
        "hooks": {"registered": sorted(REGISTERED_HOOKS)},
        "skills": {"registered": sorted(SUPPORTED_SKILLS)},
        "tools": {"registered": sorted(REGISTERED_TOOLS)},
        "commands": {"registered": sorted(REGISTERED_COMMANDS)},
        "memory": {
            "adapter_registered": True,
            "database": os.fspath(binding.authority.memory_db_path),
            "scope": "project-only",
        },
        "delegation": {
            "delegate_task_registered": False,
            "kanban_registered": False,
        },
        "quality": {
            "pre_verify_policy": (
                "consumes the bound workspace's active-cycle quality_locked "
                "via cycle_metadata()"
            ),
            "kanban_worker_bridge": False,
            "kanban_worker_bridge_status": (
                "separate initiative — never claimed by this surface"
            ),
        },
    }


def _tool_arguments(value: Any, allowed: Set[str]) -> Dict[str, Any]:
    if value is None:
        args = {}
    elif isinstance(value, Mapping):
        args = dict(value)
    else:
        raise PluginAuthorityError("tool arguments must be a mapping")
    overrides = sorted(_FORBIDDEN_AUTHORITY_ARGUMENTS.intersection(args))
    if overrides:
        raise PluginAuthorityError(
            "workspace/project authority override is forbidden: %s"
            % ", ".join(overrides)
        )
    unknown = sorted(str(key) for key in args if key not in allowed)
    if unknown:
        raise PluginAuthorityError(
            "unsupported tool argument(s): %s" % ", ".join(unknown)
        )
    return args


def _bound_path(
    binding: PluginBinding,
    value: Any,
    *,
    default: str,
    label: str,
    require_file: bool = False,
) -> pathlib.Path:
    raw = default if value is None or str(value).strip() == "" else str(value).strip()
    if not raw or "\x00" in raw:
        raise PluginAuthorityError("%s must be a non-empty path" % label)
    supplied = pathlib.Path(raw)
    candidate = supplied if supplied.is_absolute() else binding.workspace_root / supplied
    try:
        canonical = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise PluginAuthorityError("%s cannot be resolved: %s" % (label, exc)) from exc
    if not _contains(binding.workspace_root, canonical):
        raise PluginAuthorityError("%s escapes the bound workspace" % label)
    if require_file and not canonical.is_file():
        raise PluginAuthorityError("%s is not a file inside the bound workspace" % label)
    return canonical


def _bound_url(binding: PluginBinding, value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise PluginAuthorityError("url is required")
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return raw
    if parsed.scheme != "file":
        raise PluginAuthorityError("url must use http, https, or a bound file URL")
    native = unquote(parsed.path)
    if os.name == "nt" and len(native) >= 3 and native[0] == "/" and native[2] == ":":
        native = native[1:]
    return _bound_path(
        binding,
        native,
        default=".",
        label="file URL",
        require_file=True,
    ).as_uri()


def _json_error(exc: Exception) -> str:
    return json.dumps({"ok": False, "error": str(exc)}, sort_keys=True)


def _run_script_data(
    binding: PluginBinding,
    script_name: str,
    argv: Tuple[str, ...],
    *,
    timeout: int = 300,
) -> Dict[str, Any]:
    script = binding.gate_scripts.get(script_name)
    if script is None:
        raise PluginAuthorityError("unregistered bound gate script: %s" % script_name)
    command = [binding.bash_executable, os.fspath(script), *argv]
    if os.name == "nt" and script_name == "sage-spec-check.sh":
        runner = binding.runtime_root / "runtime/platforms/community/hermes/gate-runner.sh"
        _read_plain_text(runner, owner=binding.runtime_root,
                         label="bound Windows formal-gate runner", max_bytes=MAX_CONTEXT_BYTES)
        command = [binding.bash_executable, os.fspath(runner), sys.executable,
                   os.fspath(script), *argv]
    try:
        completed = subprocess.run(
            command,
            cwd=os.fspath(binding.workspace_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": 2,
            "script": script_name,
            "cwd": os.fspath(binding.workspace_root),
            "error": "gate timed out after %s seconds" % timeout,
            "stdout": (exc.stdout or "")[-20000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "",
        }
    except OSError as exc:
        return {
            "ok": False,
            "exit_code": 2,
            "script": script_name,
            "cwd": os.fspath(binding.workspace_root),
            "error": "gate executable failed: %s" % exc,
            "stdout": "",
            "stderr": "",
        }
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "script": script_name,
        "cwd": os.fspath(binding.workspace_root),
        "stdout": (completed.stdout or "")[-20000:],
        "stderr": (completed.stderr or "")[-8000:],
    }


def _canonical_gate(value: Any) -> str:
    name = str(value).strip().lower().replace("_", "-")
    return GATE_ALIASES.get(name, name)


def _as_gate_list(value: Any) -> list[str]:
    raw = value if isinstance(value, list) else ([] if value is None else [value])
    return [_canonical_gate(item) for item in raw if str(item).strip()]


def _sort_gates(items) -> list[str]:
    return sorted(set(items), key=lambda gate: (GATE_ORDER.get(gate, 99), gate))


def _load_bound_yaml(binding: PluginBinding, path: pathlib.Path, label: str) -> Mapping[str, Any]:
    text = _read_plain_text(
        path,
        owner=binding.workspace_root if _contains(binding.workspace_root, path) else binding.runtime_root,
        label=label,
        max_bytes=MAX_AUTHORITY_BYTES,
    )
    return _load_yaml_mapping(text, label)


def _mode_config(binding: PluginBinding, mode: str) -> Tuple[Dict[str, list[str]], Dict[str, Any]]:
    project_modes = binding.authority.state_root / "gates" / "gate-modes.yaml"
    if project_modes.is_file():
        modes = _load_bound_yaml(binding, project_modes, "bound project gate modes")
        source_label = os.fspath(project_modes)
    else:
        modes = _load_bound_yaml(binding, binding.gate_modes_path, "bound runtime gate modes")
        source_label = os.fspath(binding.gate_modes_path)
    raw = modes.get(mode) if isinstance(modes, Mapping) else None
    if not isinstance(raw, Mapping):
        raw = DEFAULT_GATE_MODES[mode]
        source_label = "validated built-in fallback"
    config = {
        "mandatory": _sort_gates(_as_gate_list(raw.get("mandatory"))),
        "optional": _sort_gates(_as_gate_list(raw.get("optional"))),
        "skipped": _sort_gates(_as_gate_list(raw.get("skipped"))),
    }
    meta: Dict[str, Any] = {
        "mode_config": source_label,
        "project_config": None,
        "waiver_required": [],
        "optional_enabled": [],
    }
    project_config = binding.authority.state_root / "config.yaml"
    if not project_config.is_file():
        return config, meta
    data = _load_bound_yaml(binding, project_config, "bound project Sage config")
    gates = data.get("gates") if isinstance(data, Mapping) else None
    if not isinstance(gates, Mapping):
        return config, meta
    meta["project_config"] = os.fspath(project_config)
    override = None
    modes_value = gates.get("modes")
    if isinstance(modes_value, Mapping) and isinstance(modes_value.get(mode), Mapping):
        override = modes_value[mode]
    elif isinstance(gates.get(mode), Mapping):
        override = gates[mode]
    elif any(key in gates for key in ("mandatory", "optional", "skipped")):
        override = gates
    if isinstance(override, Mapping):
        for key in ("mandatory", "optional", "skipped"):
            if key in override:
                config[key] = _sort_gates(_as_gate_list(override.get(key)))
    disabled = _as_gate_list(gates.get("disabled"))
    if disabled:
        mandatory = set(config["mandatory"])
        config["mandatory"] = [gate for gate in config["mandatory"] if gate not in disabled]
        config["optional"] = [gate for gate in config["optional"] if gate not in disabled]
        config["skipped"] = _sort_gates(config["skipped"] + disabled)
        meta["waiver_required"] = sorted(mandatory.intersection(disabled))
    config["optional"] = _sort_gates(
        config["optional"] + _as_gate_list(gates.get("additional"))
    )
    enabled = (
        gates.get("enabled")
        or gates.get("optional_enabled")
        or gates.get("run_optional")
        or gates.get("enabled_optional")
    )
    meta["optional_enabled"] = _as_gate_list(enabled)
    return config, meta


def _gate_result(
    gate: str,
    required: str,
    status: str,
    blocking: bool,
    details: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "gate": gate,
        "required": required,
        "status": status,
        "blocking": blocking,
    }
    if details:
        result.update(details)
    return result


def _run_one_gate(
    binding: PluginBinding,
    gate: str,
    required: str,
    args: Mapping[str, Any],
) -> Dict[str, Any]:
    mandatory = required == "mandatory"
    if gate == "spec-compliance":
        task_number = args.get("task_number")
        plan_file = args.get("plan_file")
        if not isinstance(task_number, int) or task_number < 1 or not plan_file:
            return _gate_result(
                gate,
                required,
                "missing_args",
                mandatory,
                {"error": "plan_file and positive task_number are required"},
            )
        plan = _bound_path(
            binding,
            plan_file,
            default="",
            label="plan_file",
            require_file=True,
        )
        data = _run_script_data(
            binding,
            "sage-spec-check.sh",
            (os.fspath(plan), str(task_number)),
        )
    elif gate == "hallucination-check":
        target = _bound_path(
            binding,
            args.get("target"),
            default=".",
            label="target",
        )
        data = _run_script_data(
            binding,
            "sage-hallucination-check.sh",
            (os.fspath(target), os.fspath(binding.workspace_root)),
        )
    elif gate == "verification":
        data = _run_script_data(
            binding,
            "sage-verify.sh",
            (os.fspath(binding.workspace_root),),
            timeout=600,
        )
    elif gate == "visual-verification":
        if not args.get("visual_url"):
            return _gate_result(
                gate,
                required,
                "missing_args",
                mandatory,
                {"error": "visual_url is required"},
            )
        url = _bound_url(binding, args.get("visual_url"))
        output = _bound_path(
            binding,
            args.get("visual_output_dir"),
            default=".sage/screenshots",
            label="visual_output_dir",
        )
        data = _run_script_data(
            binding,
            "sage-visual-gate.sh",
            (url, os.fspath(output)),
            timeout=600,
        )
    elif gate in AGENT_REVIEW_GATES:
        return _gate_result(
            gate,
            required,
            "agent_review_required",
            False,
            {"agent_review_required": True, "note": AGENT_REVIEW_GATES[gate]},
        )
    else:
        return _gate_result(
            gate,
            required,
            "unsupported",
            mandatory,
            {"error": "no bound Hermes gate implementation is registered"},
        )
    return _gate_result(
        gate,
        required,
        "script_passed" if data["ok"] else "failed",
        mandatory and not data["ok"],
        {
            **data,
            "agent_review_required": bool(data["ok"]),
            "review_note": SCRIPT_REVIEW_NOTES.get(gate),
        },
    )


def _handle_spec_check(binding: PluginBinding, value: Any) -> str:
    args = _tool_arguments(value, {"plan_file", "task_number"})
    task_number = args.get("task_number")
    if not isinstance(task_number, int) or task_number < 1:
        raise PluginAuthorityError("task_number must be a positive integer")
    plan = _bound_path(
        binding,
        args.get("plan_file"),
        default="",
        label="plan_file",
        require_file=True,
    )
    return json.dumps(
        _run_script_data(
            binding,
            "sage-spec-check.sh",
            (os.fspath(plan), str(task_number)),
        ),
        sort_keys=True,
    )


def _handle_hallucination_check(binding: PluginBinding, value: Any) -> str:
    args = _tool_arguments(value, {"target"})
    target = _bound_path(binding, args.get("target"), default=".", label="target")
    return json.dumps(
        _run_script_data(
            binding,
            "sage-hallucination-check.sh",
            (os.fspath(target), os.fspath(binding.workspace_root)),
        ),
        sort_keys=True,
    )


def _handle_verify(binding: PluginBinding, value: Any) -> str:
    _tool_arguments(value, set())
    return json.dumps(
        _run_script_data(
            binding,
            "sage-verify.sh",
            (os.fspath(binding.workspace_root),),
            timeout=600,
        ),
        sort_keys=True,
    )


def _handle_visual_gate(binding: PluginBinding, value: Any) -> str:
    args = _tool_arguments(value, {"url", "output_dir"})
    url = _bound_url(binding, args.get("url"))
    output = _bound_path(
        binding,
        args.get("output_dir"),
        default=".sage/screenshots",
        label="output_dir",
    )
    return json.dumps(
        _run_script_data(
            binding,
            "sage-visual-gate.sh",
            (url, os.fspath(output)),
            timeout=600,
        ),
        sort_keys=True,
    )


def _handle_run_gates(binding: PluginBinding, value: Any) -> str:
    allowed = {
        "mode",
        "plan_file",
        "task_number",
        "target",
        "visual_url",
        "visual_output_dir",
        "optional_gates",
        "include_optional",
    }
    args = _tool_arguments(value, allowed)
    mode = _canonical_gate(args.get("mode"))
    if mode not in DEFAULT_GATE_MODES:
        raise PluginAuthorityError("mode must be one of: fix, build, architect")
    config, meta = _mode_config(binding, mode)
    requested = set(_as_gate_list(args.get("optional_gates")))
    requested.update(meta["optional_enabled"])
    active_optional = [
        gate
        for gate in config["optional"]
        if args.get("include_optional") is True or gate in requested
    ]
    if args.get("visual_url") and "visual-verification" not in config["skipped"]:
        active_optional.append("visual-verification")
    skipped = set(config["skipped"])
    active = _sort_gates(
        gate
        for gate in config["mandatory"] + active_optional
        if gate not in skipped
    )
    required_by_gate = {
        gate: "mandatory" for gate in config["mandatory"] if gate not in skipped
    }
    for gate in active_optional:
        required_by_gate.setdefault(gate, "optional")
    results = [
        _run_one_gate(binding, gate, required_by_gate.get(gate, "optional"), args)
        for gate in active
    ]
    blocking = [result for result in results if result["blocking"]]
    review = [result for result in results if result.get("agent_review_required")]
    waiver = meta["waiver_required"]
    ok = not blocking and not waiver
    return json.dumps(
        {
            "ok": ok,
            "all_gates_complete": ok and not review,
            "mode": mode,
            "cwd": os.fspath(binding.workspace_root),
            "config": config,
            "sources": meta,
            "active_gates": active,
            "optional_not_run": _sort_gates(
                gate
                for gate in config["optional"]
                if gate not in skipped and gate not in active
            ),
            "skipped": _sort_gates(skipped),
            "waiver_required": waiver,
            "agent_review_required": [
                {
                    "gate": result["gate"],
                    "required": result["required"],
                    "note": result.get("review_note") or result.get("note"),
                }
                for result in review
            ],
            "results": results,
            "summary": {
                "script_passed": sum(
                    result["status"] == "script_passed" for result in results
                ),
                "failed": sum(result["status"] == "failed" for result in results),
                "agent_review_required": len(review),
                "missing_args": sum(
                    result["status"] == "missing_args" for result in results
                ),
                "unsupported": sum(
                    result["status"] == "unsupported" for result in results
                ),
                "blocking": len(blocking) + len(waiver),
            },
        },
        sort_keys=True,
    )


def _memory_store(binding: PluginBinding):
    store = binding.memory_namespace.WorkspaceMemoryStore(binding.workspace_root)
    binding.memory_namespace.verify_session_db(store.db_path, binding.workspace_root)
    if not _same_path(store.db_path, binding.authority.memory_db_path):
        store.close()
        raise PluginAuthorityError(
            "memory backend did not select the frozen binding database"
        )
    return store


def _handle_memory_set_project(binding: PluginBinding, value: Any) -> str:
    _tool_arguments(value, set())
    with _memory_store(binding) as store:
        database = os.fspath(store.db_path)
    return json.dumps(
        {
            "ok": True,
            "project": os.fspath(binding.workspace_root),
            "database": database,
            "scope": "project",
        },
        sort_keys=True,
    )


def _string_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PluginAuthorityError("%s must be an array of strings" % label)
    return [item.strip() for item in value if item.strip()]


def _handle_memory_store(binding: PluginBinding, value: Any) -> str:
    args = _tool_arguments(value, {"title", "content", "tags", "scope"})
    title = str(args.get("title") or "").strip()
    content = str(args.get("content") or "").strip()
    if not title or not content:
        raise PluginAuthorityError("title and content are required")
    if args.get("scope", "project") != "project":
        raise PluginAuthorityError("only project memory scope is supported")
    tags = _string_list(args.get("tags"), "tags")
    with _memory_store(binding) as store:
        row = store.store(title=title, content=content, tags=tags)
    return json.dumps({"ok": True, **row}, sort_keys=True)


def _handle_memory_search(binding: PluginBinding, value: Any) -> str:
    args = _tool_arguments(value, {"query", "limit", "filter_tags", "tags"})
    query = str(args.get("query") or "").strip()
    if not query:
        raise PluginAuthorityError("query is required")
    limit = args.get("limit", 5)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise PluginAuthorityError("limit must be an integer from 1 to 50")
    filter_tags = _string_list(args.get("filter_tags"), "filter_tags")
    tags = _string_list(args.get("tags"), "tags")
    with _memory_store(binding) as store:
        results = store.search(
            query=query,
            limit=limit,
            filter_tags=filter_tags,
            boost_tags=tags,
        )
    return json.dumps(
        {
            "ok": True,
            "database": os.fspath(binding.authority.memory_db_path),
            "scope": "project",
            "results": results,
        },
        sort_keys=True,
    )


_TOOL_HANDLERS: Mapping[str, Callable[[PluginBinding, Any], str]] = {
    "sage_run_gates": _handle_run_gates,
    "sage_spec_check": _handle_spec_check,
    "sage_hallucination_check": _handle_hallucination_check,
    "sage_verify": _handle_verify,
    "sage_visual_gate": _handle_visual_gate,
    "sage_memory_set_project": _handle_memory_set_project,
    "sage_memory_store": _handle_memory_store,
    "sage_memory_search": _handle_memory_search,
}


def _make_tool_handler(
    binding: PluginBinding,
    implementation: Callable[[PluginBinding, Any], str],
):
    def handler(args=None, **_kwargs):
        try:
            return implementation(binding, args)
        except (PluginAuthorityError, MemoryNamespaceError, ValueError) as exc:
            return _json_error(exc)

    return handler


def _make_command_handler(
    binding: PluginBinding,
    command_name: str,
    prefix: str,
):
    def handler(raw_args: str = "") -> str:
        raw = "" if raw_args is None else str(raw_args).strip()
        invocation = " ".join(part for part in (prefix, raw) if part).strip()
        text = binding.command_texts[command_name]
        if "$ARGUMENTS" in text:
            return text.replace("$ARGUMENTS", invocation)
        suffix = invocation or "(no arguments)"
        return (
            "%s\n\n## Bound Hermes invocation\n"
            "- command: /%s\n"
            "- arguments: %s\n"
            "- workspace: %s"
            % (
                text.rstrip(),
                command_name,
                suffix,
                binding.workspace_root,
            )
        )

    return handler


def _on_session_start(_binding: PluginBinding, **_kwargs):
    """Initialization only; first-turn content belongs to ``pre_llm_call``."""

    return None


def _on_pre_llm_call(
    binding: PluginBinding,
    session_id=None,
    is_first_turn=False,
    **_kwargs,
):
    if not is_first_turn:
        return None
    key = str(session_id) if session_id is not None else "<anonymous-session>"
    if key in _CONTEXT_SESSIONS:
        return None
    _CONTEXT_SESSIONS.add(key)
    return {"context": binding.context}


def _pending_scope_correction(binding: PluginBinding) -> Optional[str]:
    workspace = binding.workspace_root
    module = binding.scope_judge
    try:
        config = module.read_config(workspace)
        if not config.get("scope_judge"):
            return None
        cycle = module.active_cycle(workspace)
        if cycle is None:
            return None
        rows = module.read_journal(cycle)
        event_count = len(module.events(rows))
        envelope = module.maybe_inject(cycle, config, event_count)
        if not isinstance(envelope, dict):
            return None
        specific = envelope.get("hookSpecificOutput")
        if not isinstance(specific, dict):
            return None
        context = specific.get("additionalContext")
        return context if isinstance(context, str) and context.strip() else None
    except Exception:
        LOGGER.exception("Sage scope correction delivery failed inside bound workspace")
        return None


def _on_transform_tool_result(
    binding: PluginBinding,
    result=None,
    **_kwargs,
):
    correction = _pending_scope_correction(binding)
    if correction is None:
        return None
    original = "" if result is None else str(result)
    return "%s\n\n%s" % (original, correction) if original else correction


def _on_pre_verify(binding: PluginBinding, **_kwargs):
    """Surface bound quality policy without claiming the Kanban bridge."""

    try:
        metadata = cycle_metadata(binding)
    except PluginAuthorityError:
        LOGGER.exception("Sage quality metadata unavailable inside bound workspace")
        return None
    if not metadata["quality_locked"]:
        return None
    note = (
        "quality_locked is active for cycle %s: completion claims need "
        "pasted, current-byte verification receipts before they count."
        % metadata["cycle"]
    )
    if metadata["announcement"]:
        note = "%s\n%s" % (note, metadata["announcement"])
    return {"context": note}


def _make_hook_handler(binding: PluginBinding, implementation: Callable):
    def handler(**kwargs):
        return implementation(binding, **kwargs)

    return handler


def register(ctx) -> None:
    """Register one validated, frozen, profile-bound Hermes plugin instance."""

    global _RUNTIME
    authority = _authorize_profile()
    binding = _validate_runtime(authority)

    # All authorities, source bytes, and executable paths are frozen before the
    # first PluginContext mutation. Every callback, command, and tool handler
    # closes over this exact PluginBinding; no handler rediscovers cwd/HOME.
    for name in SUPPORTED_SKILLS:
        ctx.register_skill(name, binding.skill_paths[name])
    ctx.register_hook(
        "on_session_start", _make_hook_handler(binding, _on_session_start)
    )
    ctx.register_hook(
        "pre_llm_call", _make_hook_handler(binding, _on_pre_llm_call)
    )
    ctx.register_hook(
        "transform_tool_result",
        _make_hook_handler(binding, _on_transform_tool_result),
    )
    ctx.register_hook("pre_verify", _make_hook_handler(binding, _on_pre_verify))

    for command_name, _skill_name, prefix, description in COMMAND_SPECS:
        ctx.register_command(
            name=command_name,
            handler=_make_command_handler(binding, command_name, prefix),
            description=description,
            args_hint="[arguments]",
        )
    for tool_name in REGISTERED_TOOLS:
        schema = TOOL_SCHEMAS[tool_name]
        ctx.register_tool(
            name=tool_name,
            toolset="sage",
            schema=schema,
            handler=_make_tool_handler(binding, _TOOL_HANDLERS[tool_name]),
            description=schema["description"],
            emoji="S",
        )

    _CONTEXT_SESSIONS.clear()
    _RUNTIME = binding


__all__ = [
    "PluginAuthorityError",
    "PluginBinding",
    "binding_snapshot",
    "cycle_metadata",
    "register",
    "runtime_inventory",
]
