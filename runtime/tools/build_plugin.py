#!/usr/bin/env python3
"""
build_plugin.py — generate platform plugin artifacts from single sources.

The plugin used to live at tools/sage-claude-plugin/ as a hand-synced second
copy of every skill, gate script, and template (ADR-5). Drift was structural —
the Gate 4 bug shipped twice because of it. That mirror is gone (P3-T2b). This
generator is now the only way the plugin comes into existence: `main` holds one
copy of each file, and the release workflow builds the tree and publishes it to
the `plugin-dist` branch, which the marketplace `source` pins via `ref`.

Composition (three layers, applied in order — later layers win):

  1. Framework skills — copy skills/<name>/ → plugin skills/<name>/ for every
     skill in PLUGIN_SKILLS that has a skills/ source.
  2. File map — the files the plugin pulls from core/ and runtime/ (gate
     scripts, the spec-gate hook, templates, references).
  3. Overlay — runtime/plugin-overlay/ holds the plugin-ONLY files (manifests,
     sage-navigator, the workflow→skill wrappers, agents, plugin README) laid
     over the tree, overriding where present. The two .claude-plugin JSONs carry
     a {{VERSION}} placeholder filled from the root VERSION file.

Because no built tree is committed any more, PLUGIN_SKILLS below is the
reviewable statement of what the plugin ships — adding a skill to skills/
without listing it here (or in SKILLS_NOT_IN_PLUGIN) is a build error, so the
decision cannot be made by accident.

Usage:
  build_plugin.py                 build into dist/sage-claude-plugin/
  build_plugin.py --out DIR       build into DIR
  build_plugin.py --check         build and verify the artifact is well-formed,
                                  reproducible, and faithful to its sources
  build_plugin.py --target hermes build the full framework as a Hermes plugin

Exit: 0 = built / check passed | 1 = build error or failed check | 2 = bad invocation

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
OVERLAY = REPO_ROOT / "runtime" / "plugin-overlay"
HERMES_PLATFORM = REPO_ROOT / "runtime" / "platforms" / "community" / "hermes"
HERMES_OVERLAY = HERMES_PLATFORM / "plugin-overlay"
HERMES_TOPOLOGY = HERMES_PLATFORM / "setup" / "topology.json"
SKILLS = REPO_ROOT / "skills"
SYSTEM_SKILLS = REPO_ROOT / "core" / "system-skills"
INSTRUCTIONS_BODY = REPO_ROOT / "runtime" / "platforms" / "_shared" / "instructions-body.sh"
CONSTITUTION_SH = REPO_ROOT / "runtime" / "platforms" / "_shared" / "constitution.sh"

VERSION_PLACEHOLDER = "{{VERSION}}"
DEFAULT_TARGET = "claude"
BUILD_TARGETS = (DEFAULT_TARGET, "hermes")
HERMES_TOPOLOGY_SCHEMA_VERSION = 1
HERMES_BUILD_OWNER = "runtime/tools/build_plugin.py"
HERMES_SOURCE_BYTE_POLICY = "canonical_utf8_lf_git_index_blob"
HERMES_SOURCE_IDENTITY_HASH_POLICY = "source_sha256_byte_identity"
HERMES_BEHAVIORAL_ADAPTATION_HASH_POLICY = "behavioral_adaptation"
HERMES_FRAMEWORK_SOURCE_POLICY = "complete_git_tracked_or_release_tree"
HERMES_FRAMEWORK_MANIFEST_NAME = ".sage-framework-manifest.json"
HERMES_FRAMEWORK_MANIFEST_SCHEMA = "sage.hermes.framework-package"
HERMES_FRAMEWORK_EXCLUDED_ROOTS = frozenset({
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
})
HERMES_FRAMEWORK_PROJECTED_ROOT_FILES = frozenset({
    HERMES_FRAMEWORK_MANIFEST_NAME,
    "memory_namespace.py",
    "profile_binding.py",
})
HERMES_PACKAGE_CLASSIFICATIONS = frozenset({
    "hermes_shell_hook",
    "hermes_plugin_callback",
    "workflow_on_demand_gate",
})
HERMES_NON_PACKAGE_CLASSIFICATIONS = frozenset({
    "intentionally_unsupported",
    "not_applicable",
})
HERMES_WINDOWS_RESERVED_COMPONENTS = frozenset({
    "aux",
    "clock$",
    "con",
    "conin$",
    "conout$",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
})
HERMES_WINDOWS_UNSAFE_COMPONENT_CHARS = frozenset('<>:"|?*')
HERMES_NON_IDENTITY_GIT_ATTRIBUTES = ("filter", "working-tree-encoding")


def bash_path(path: pathlib.Path) -> str:
    """Return a path Bash can consume on both POSIX and Windows hosts."""
    return str(path).replace("\\", "/")


def _resolve_bash() -> str:
    """Prefer Git Bash on Windows; the System32 WSL shim cannot read MSYS drive paths."""
    explicit = os.environ.get("SAGE_BASH_EXE")
    if explicit:
        return explicit

    if os.name == "nt":
        candidates = []
        git_exe = shutil.which("git")
        if git_exe:
            git_root = pathlib.Path(git_exe).resolve().parent.parent
            candidates.extend((git_root / "bin" / "bash.exe",
                               git_root / "usr" / "bin" / "bash.exe"))
        for env_name, suffix in (
            ("ProgramFiles", ("Git", "bin", "bash.exe")),
            ("LOCALAPPDATA", ("Programs", "Git", "bin", "bash.exe")),
        ):
            base = os.environ.get(env_name)
            if base:
                candidates.append(pathlib.Path(base).joinpath(*suffix))
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

    return shutil.which("bash") or "bash"


BASH = _resolve_bash()

# The branch the release workflow publishes the built tree to. The marketplace
# entry must pin this as its `ref` — without it, `source` resolves to the default
# branch, which no longer carries a plugin tree, and the plugin is uninstallable.
DIST_REF = "plugin-dist"

# Every skill the plugin ships. Sources: skills/<name>/ (framework skills) and/or
# runtime/plugin-overlay/skills/<name>/ (plugin-only skills and overrides).
PLUGIN_SKILLS = frozenset({
    # workflow→skill wrappers + the router (overlay-only)
    "architect", "build", "configure", "continue", "fix", "learn", "reflect",
    "review", "sage", "sage-navigator",
    # framework skills (skills/)
    "api", "baas", "flutter", "mobile", "nextjs", "react", "react-native",
    "sage-memory", "sage-ontology", "sage-self-learning", "web",
})

# Skill dirs that exist in skills/ but are deliberately NOT shipped in the plugin.
SKILLS_NOT_IN_PLUGIN = frozenset({
    "autoresearch",
    # The hermes-platform skill set — workflow mirrors, persona skills, and the
    # Sage-about-Sage system skills the Hermes plugin registers via
    # ctx.register_skill() (the repo-root __init__.py — Hermes ships the
    # plugin at the repo root, not under runtime/platforms/community/hermes/).
    # They ship to Hermes users through that plugin; they are not part of the
    # claude-code plugin this builder produces.
    "sage", "sage-analyst", "sage-architect", "sage-autoresearch", "sage-build",
    "sage-checkpoints", "sage-classifier", "sage-constitution", "sage-continue",
    "sage-debugger", "sage-decisions", "sage-developer", "sage-fix",
    "sage-gates", "sage-learn", "sage-reflect", "sage-review", "sage-reviewer",
    "sage-routing", "sage-tiers", "sage-using-memory",
})

# System skills (core/system-skills/) — Sage-about-Sage content that ADR-9 moved
# OUT of the eager layer. They ship in the plugin because the plugin install has
# no vendored sage/ tree to point a loader stub at: if they are not here, the
# content the eager layer no longer carries does not exist at all for plugin
# users. Discovered from disk rather than enumerated, because the whole point of
# the diet is that this list grows as the eager layer shrinks — and a hand-kept
# copy of a directory listing is a drift bug waiting for a quiet release.
SYSTEM_SKILL_NAMES = frozenset(
    p.name for p in sorted(SYSTEM_SKILLS.iterdir()) if (p / "SKILL.md").is_file()
) if SYSTEM_SKILLS.is_dir() else frozenset()

# Per framework skill, the plugin ships only the runtime-facing content — the
# authoring extras (README.md, tests.md, patterns/, constitution/, gates/,
# anti-patterns/, examples/, templates/, integration/) stay in the repo.
SKILL_INCLUDE_FILES = {"SKILL.md"}
SKILL_INCLUDE_DIRS = {"references", "scripts"}

# Files the plugin pulls from core/ and runtime/ (plugin path → repo source).
FILE_MAP = {
    # The CLI the plugin's README tells users to run. The overlay used to carry its
    # own copy, which nothing regenerated: it froze at v1.1.7 (1007 lines against
    # bin/sage's 2056) and hardcoded `sage-version: "1.0.0"` into every project it
    # initialized. A second copy of a file that has a canonical source is exactly
    # what ADR-5 exists to forbid — so it is generated, and audit() now holds it
    # byte-identical to bin/sage forever.
    "scripts/sage": "bin/sage",
    "hooks/scripts/sage-hallucination-check.sh": "core/gates/scripts/sage-hallucination-check.sh",
    "hooks/scripts/sage-spec-check.sh": "core/gates/scripts/sage-spec-check.sh",
    "hooks/scripts/sage-verify.sh": "core/gates/scripts/sage-verify.sh",
    # sage-verify.sh sources this sibling at runtime — mapping the script
    # without its dependency ships a gate that breaks on install
    # (test_sourced_siblings_ship_with_their_scripts pins the class).
    "hooks/scripts/sage-bounded.sh": "core/gates/scripts/sage-bounded.sh",
    "hooks/scripts/sage-visual-gate.sh": "core/gates/scripts/sage-visual-gate.sh",
    "hooks/scripts/sage-spec-gate.sh": "runtime/platforms/claude-code/hooks/sage-spec-gate.sh",
    "hooks/scripts/sage-degradation-log.sh": "runtime/platforms/claude-code/hooks/sage-degradation-log.sh",
    "hooks/scripts/sage-manifest-sync.sh": "runtime/platforms/claude-code/hooks/sage-manifest-sync.sh",
    "hooks/scripts/sage-bookkeeping-gate.sh": "runtime/platforms/claude-code/hooks/sage-bookkeeping-gate.sh",
    "hooks/scripts/sage-secrets-gate.sh": "runtime/platforms/claude-code/hooks/sage-secrets-gate.sh",
    "hooks/scripts/sage-verify-gate.sh": "runtime/platforms/claude-code/hooks/sage-verify-gate.sh",
    "hooks/scripts/sage-verify-tracker.sh": "runtime/platforms/claude-code/hooks/sage-verify-tracker.sh",
    "hooks/scripts/sage-config-gate.sh": "runtime/platforms/claude-code/hooks/sage-config-gate.sh",
    # The manifest hook delegates here rather than inlining a second copy of the
    # state machine. A plugin-only project may have no vendored sage/, so the tool
    # ships with the plugin too.
    "tools/manifest.py": "runtime/tools/manifest.py",
    "hooks/scripts/sage-tdd-gate.sh": "runtime/platforms/claude-code/hooks/sage-tdd-gate.sh",
    "references/decision-template.md": "core/templates/architecture/decision-template.md",
    "references/full-spec-template.md": "core/templates/spec/full.spec-template.md",
    "references/plan-template.md": "core/templates/plan/standard.plan-template.md",
    "references/spec-template.md": "core/templates/spec/minimal.spec-template.md",
    "references/lightpanda-setup.md": "core/references/lightpanda-setup.md",
    "references/skill-authoring-guide.md": "develop/guides/skill-authoring-guide.md",
}

# ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/foo.sh → hooks/scripts/foo.sh
HOOK_COMMAND = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/(\S+)")


class BuildError(Exception):
    pass


def read_version() -> str:
    vf = REPO_ROOT / "VERSION"
    if not vf.is_file():
        raise BuildError("VERSION file not found at repo root")
    return vf.read_text().strip()


def copy_file(src: pathlib.Path, dst: pathlib.Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def canonical_hermes_source_bytes(src: pathlib.Path) -> bytes:
    """Return the bytes Git stores for a manifest-owned source.

    Windows may materialize the same tracked text as CRLF.  Hermes topology
    hashes and package artifacts deliberately use canonical UTF-8/LF for text
    and unchanged bytes for binary files, matching Git blob semantics without
    depending on checkout configuration.
    """
    try:
        raw = src.read_bytes()
    except OSError as exc:
        raise BuildError(f"cannot read Hermes package source {src}: {exc}")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    canonical = raw.replace(b"\r\n", b"\n")
    if b"\r" in canonical:
        raise BuildError(
            f"Hermes package source contains a lone CR outside Git LF semantics: {src}"
        )
    return canonical


def copy_hermes_source(src: pathlib.Path, dst: pathlib.Path) -> None:
    """Copy one manifest source using its canonical package-byte authority."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(canonical_hermes_source_bytes(src))
    shutil.copystat(src, dst)


def _require_hermes_hash_policy(row: dict, owner: str, expected: str) -> None:
    actual = row.get("hash_policy")
    if actual != expected:
        raise BuildError(
            f"Hermes topology {owner}.hash_policy must be "
            f"{expected!r}, got {actual!r}"
        )


def load_hermes_topology() -> dict:
    """Load the Hermes source-to-package ownership manifest."""
    try:
        topology = json.loads(HERMES_TOPOLOGY.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BuildError(
            f"Hermes topology not found: {HERMES_TOPOLOGY.relative_to(REPO_ROOT)}"
        )
    except json.JSONDecodeError as exc:
        raise BuildError(f"Hermes topology is not valid JSON: {exc}")

    schema_version = topology.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version != HERMES_TOPOLOGY_SCHEMA_VERSION
    ):
        raise BuildError(
            "Hermes topology schema_version "
            f"{schema_version!r} is unsupported; expected "
            f"{HERMES_TOPOLOGY_SCHEMA_VERSION}"
        )
    if topology.get("platform") != "hermes":
        raise BuildError("Hermes topology must declare platform 'hermes'")
    if topology.get("source_byte_policy") != HERMES_SOURCE_BYTE_POLICY:
        raise BuildError(
            "Hermes topology source_byte_policy must be "
            f"{HERMES_SOURCE_BYTE_POLICY!r}"
        )
    if not isinstance(topology.get("hooks"), list):
        raise BuildError("Hermes topology must declare a hooks list")
    if not isinstance(topology.get("adapter"), dict):
        raise BuildError("Hermes topology must declare an adapter object")
    if not isinstance(topology.get("plugin_files"), list):
        raise BuildError("Hermes topology must declare a plugin_files list")
    framework = topology.get("framework_package")
    if framework is not None and not isinstance(framework, dict):
        raise BuildError("Hermes topology framework_package must be an object")

    _require_hermes_hash_policy(
        topology["adapter"],
        "adapter",
        HERMES_SOURCE_IDENTITY_HASH_POLICY,
    )
    for index, row in enumerate(topology["plugin_files"]):
        if not isinstance(row, dict):
            raise BuildError(
                f"Hermes topology plugin_files row {index} must be an object"
            )
        _require_hermes_hash_policy(
            row,
            f"plugin_files[{row.get('id', index)}]",
            HERMES_SOURCE_IDENTITY_HASH_POLICY,
        )
    for index, row in enumerate(topology["hooks"]):
        if not isinstance(row, dict):
            raise BuildError(f"Hermes topology hook row {index} must be an object")
        classification = row.get("classification")
        if classification not in HERMES_PACKAGE_CLASSIFICATIONS:
            continue
        expected_hash_policy = (
            HERMES_BEHAVIORAL_ADAPTATION_HASH_POLICY
            if classification == "hermes_plugin_callback"
            else HERMES_SOURCE_IDENTITY_HASH_POLICY
        )
        _require_hermes_hash_policy(
            row,
            f"hooks[{row.get('id', index)}]",
            expected_hash_policy,
        )
    return topology


def _relative_manifest_path(value: object, field: str) -> pathlib.PurePosixPath:
    """Validate a manifest path before it reaches the filesystem."""
    if not isinstance(value, str) or not value:
        raise BuildError(f"Hermes topology field {field} must be a non-empty string")
    if "\\" in value:
        raise BuildError(f"Hermes topology field {field} must use POSIX separators: {value}")
    path = pathlib.PurePosixPath(value)
    windows_path = pathlib.PureWindowsPath(value)
    if (
        path.is_absolute()
        or bool(windows_path.drive)
        or ".." in path.parts
        or "." in path.parts
    ):
        raise BuildError(f"Hermes topology field {field} escapes its root: {value}")
    if value != path.as_posix():
        raise BuildError(
            f"Hermes topology field {field} must already be normalized: {value}"
        )
    return path


def _windows_package_target_key(
    target: pathlib.PurePosixPath,
    field: str,
) -> str:
    """Validate a target under Win32 filename rules and return its alias key."""
    normalized_parts = []
    for component in target.parts:
        if component.endswith((".", " ")):
            raise BuildError(
                f"Hermes topology field {field} has a Windows-unsafe trailing "
                f"dot or space: {component!r}"
            )
        unsafe = [
            char
            for char in component
            if ord(char) < 32 or char in HERMES_WINDOWS_UNSAFE_COMPONENT_CHARS
        ]
        if unsafe:
            detail = "colon/ADS" if ":" in unsafe else "filename character"
            raise BuildError(
                f"Hermes topology field {field} has a Windows-unsafe {detail}: "
                f"{component!r}"
            )
        device_stem = component.split(".", 1)[0].casefold()
        if device_stem in HERMES_WINDOWS_RESERVED_COMPONENTS:
            raise BuildError(
                f"Hermes topology field {field} uses a reserved Windows device "
                f"name: {component!r}"
            )
        normalized_parts.append(component.rstrip(" .").casefold())
    return "/".join(normalized_parts)


def _framework_source_is_excluded(relative: pathlib.PurePosixPath) -> bool:
    if any(part in HERMES_FRAMEWORK_EXCLUDED_ROOTS for part in relative.parts):
        return True
    if relative.suffix in (".pyc", ".pyo"):
        return True
    return (
        len(relative.parts) == 1
        and relative.name in HERMES_FRAMEWORK_PROJECTED_ROOT_FILES
    )


def _read_framework_source_manifest():
    """Return verified canonical source paths from an installed full plugin."""

    manifest_path = REPO_ROOT / HERMES_FRAMEWORK_MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildError(f"Hermes framework manifest is unreadable: {exc}")
    if not isinstance(document, dict) or set(document) != {
        "files",
        "schema",
        "schema_version",
        "source_policy",
    }:
        raise BuildError("Hermes framework manifest has an invalid document shape")
    if document.get("schema") != HERMES_FRAMEWORK_MANIFEST_SCHEMA:
        raise BuildError("Hermes framework manifest has an unsupported schema")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise BuildError("Hermes framework manifest has an unsupported schema version")
    if document.get("source_policy") != HERMES_FRAMEWORK_SOURCE_POLICY:
        raise BuildError("Hermes framework manifest has an unsupported source policy")
    rows = document.get("files")
    if not isinstance(rows, list) or not rows:
        raise BuildError("Hermes framework manifest files must be a nonempty array")

    paths = []
    for index, row in enumerate(rows):
        label = f"Hermes framework manifest files[{index}]"
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise BuildError(f"{label} must contain exactly path and sha256")
        relative = _relative_manifest_path(row.get("path"), f"{label}.path")
        if _framework_source_is_excluded(relative):
            raise BuildError(f"{label}.path names generated local state: {relative}")
        expected_hash = row.get("sha256")
        if not isinstance(expected_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_hash
        ):
            raise BuildError(f"{label}.sha256 must be one lowercase SHA-256")
        source = REPO_ROOT / relative.as_posix()
        if not source.is_file() or source.is_symlink():
            raise BuildError(f"{label}.path is missing or unsafe: {relative}")
        actual_hash = hashlib.sha256(canonical_hermes_source_bytes(source)).hexdigest()
        if actual_hash != expected_hash:
            raise BuildError(
                f"Hermes framework source drift for {relative}: "
                f"expected {expected_hash}, actual {actual_hash}"
            )
        paths.append(relative.as_posix())
    if len(paths) != len(set(paths)):
        raise BuildError("Hermes framework manifest contains duplicate source paths")
    return sorted(paths)


def _hermes_framework_source_paths() -> list:
    """Return the complete canonical framework tree without local state.

    A Git checkout uses the index as the release manifest, so untracked state
    such as ``.serena`` can never leak into the package.  A verified release
    archive has no Git metadata, so its extracted file tree is the manifest;
    only known local/build-state roots and Hermes projection files are ignored.
    """

    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "-z"],
        capture_output=True,
    )
    if proc.returncode == 0:
        candidates = [
            pathlib.PurePosixPath(os.fsdecode(path))
            for path in proc.stdout.split(b"\0")
            if path
        ]
    else:
        manifested = _read_framework_source_manifest()
        if manifested is not None:
            return manifested
        candidates = [
            pathlib.PurePosixPath(path.relative_to(REPO_ROOT).as_posix())
            for path in REPO_ROOT.rglob("*")
            if path.is_file()
        ]

    included = []
    for relative in candidates:
        if not relative.parts:
            continue
        if _framework_source_is_excluded(relative):
            continue
        included.append(relative.as_posix())
    return sorted(set(included))


def hermes_framework_manifest_bytes() -> bytes:
    rows = []
    for source_key in _hermes_framework_source_paths():
        source = REPO_ROOT / source_key
        rows.append(
            {
                "path": source_key,
                "sha256": hashlib.sha256(
                    canonical_hermes_source_bytes(source)
                ).hexdigest(),
            }
        )
    document = {
        "schema": HERMES_FRAMEWORK_MANIFEST_SCHEMA,
        "schema_version": 1,
        "source_policy": HERMES_FRAMEWORK_SOURCE_POLICY,
        "files": rows,
    }
    return (json.dumps(document, sort_keys=True, indent=2) + "\n").encode("utf-8")


def hermes_file_map() -> dict:
    """Return package target -> canonical source for the full Hermes package."""
    topology = load_hermes_topology()
    file_map = {}
    normalized_targets = {}

    def require_build_owner(row: dict, owner: str) -> None:
        actual = row.get("build_owner")
        if actual != HERMES_BUILD_OWNER:
            raise BuildError(
                f"Hermes topology {owner}.build_owner must be "
                f"{HERMES_BUILD_OWNER!r}, got {actual!r}"
            )

    def add(
        target_value: object,
        source_value: object,
        expected_hash: object,
        owner: str,
    ) -> None:
        target = _relative_manifest_path(target_value, f"{owner}.package_target")
        source = _relative_manifest_path(source_value, f"{owner}.package_source")
        target_key = target.as_posix()
        source_key = source.as_posix()
        if target_key in file_map:
            if file_map[target_key] == source_key:
                return
            raise BuildError(f"duplicate Hermes package target: {target_key}")
        normalized_target = _windows_package_target_key(
            target,
            f"{owner}.package_target",
        )
        if normalized_target in normalized_targets:
            raise BuildError(
                "Hermes package targets collide on Windows/casefold filesystems: "
                f"{normalized_targets[normalized_target]} and {target_key}"
            )
        source_path = REPO_ROOT / source_key
        try:
            resolved_repo = REPO_ROOT.resolve(strict=True)
            resolved_source = source_path.resolve(strict=True)
        except (FileNotFoundError, OSError, RuntimeError):
            raise BuildError(f"Hermes package source missing: {source_key}")
        try:
            resolved_source.relative_to(resolved_repo)
        except ValueError:
            raise BuildError(
                "Hermes package source resolves outside the repository: "
                f"{source_key} -> {resolved_source}"
            )
        if source_path.is_symlink():
            raise BuildError(
                f"Hermes package source must not be a symlink: {source_key}"
            )
        if not resolved_source.is_file():
            raise BuildError(f"Hermes package source is not a file: {source_key}")
        if expected_hash is not None:
            actual_hash = hashlib.sha256(
                canonical_hermes_source_bytes(resolved_source)
            ).hexdigest()
            if not isinstance(expected_hash, str) or actual_hash != expected_hash:
                raise BuildError(
                    f"Hermes topology hash for {source_key} is stale: "
                    f"expected {expected_hash!r}, actual {actual_hash}"
                )
        file_map[target_key] = source_key
        normalized_targets[normalized_target] = target_key

    framework = topology.get("framework_package")
    if framework is not None:
        require_build_owner(framework, "framework_package")
        if framework.get("source_policy") != HERMES_FRAMEWORK_SOURCE_POLICY:
            raise BuildError(
                "Hermes topology framework_package.source_policy must be "
                f"{HERMES_FRAMEWORK_SOURCE_POLICY!r}"
            )
        package_root = _relative_manifest_path(
            framework.get("package_target"),
            "framework_package.package_target",
        )
        if package_root.as_posix() != "plugins/sage":
            raise BuildError(
                "Hermes topology framework_package.package_target must be "
                "'plugins/sage'"
            )
        manifest_target = _relative_manifest_path(
            framework.get("manifest_target"),
            "framework_package.manifest_target",
        )
        if manifest_target.as_posix() != (
            "plugins/sage/" + HERMES_FRAMEWORK_MANIFEST_NAME
        ):
            raise BuildError(
                "Hermes topology framework_package.manifest_target must be "
                f"'plugins/sage/{HERMES_FRAMEWORK_MANIFEST_NAME}'"
            )
        for source_key in _hermes_framework_source_paths():
            add(
                (package_root / pathlib.PurePosixPath(source_key)).as_posix(),
                source_key,
                None,
                "framework_package",
            )

    adapter = topology["adapter"]
    require_build_owner(adapter, "adapter")
    add(
        adapter.get("package_target"),
        adapter.get("source"),
        adapter.get("source_sha256"),
        "adapter",
    )

    for index, row in enumerate(topology["plugin_files"]):
        if not isinstance(row, dict):
            raise BuildError(
                f"Hermes topology plugin_files row {index} must be an object"
            )
        owner = f"plugin_files[{row.get('id', index)}]"
        require_build_owner(row, owner)
        add(
            row.get("package_target"),
            row.get("source"),
            row.get("source_sha256"),
            owner,
        )

    known = HERMES_PACKAGE_CLASSIFICATIONS | HERMES_NON_PACKAGE_CLASSIFICATIONS
    for index, row in enumerate(topology["hooks"]):
        if not isinstance(row, dict):
            raise BuildError(f"Hermes topology hook row {index} must be an object")
        classification = row.get("classification")
        if classification not in known:
            raise BuildError(
                f"Hermes topology hook {row.get('id', index)!r} has unknown "
                f"classification {classification!r}"
            )
        if classification in HERMES_PACKAGE_CLASSIFICATIONS:
            owner = f"hooks[{row.get('id', index)}]"
            require_build_owner(row, owner)
            add(
                row.get("package_target"),
                row.get("package_source"),
                row.get("package_source_sha256"),
                f"hooks[{row.get('id', index)}]",
            )

    if HERMES_OVERLAY.is_dir():
        declared_sources = set(file_map.values())
        unowned = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in sorted(HERMES_OVERLAY.rglob("*"))
            if path.is_file()
            and "__pycache__" not in path.parts
            and not path.name.endswith(".pyc")
            and path.relative_to(REPO_ROOT).as_posix() not in declared_sources
        ]
        if unowned:
            raise BuildError(
                "Hermes plugin overlay holds unmanifested build inputs: "
                + ", ".join(unowned)
            )

    untracked = _untracked_repo_paths(file_map.values())
    if untracked:
        raise BuildError(
            "Hermes declared package source is not tracked by git: "
            + ", ".join(untracked)
        )
    symlinks = _git_symlink_repo_paths(file_map.values())
    if symlinks:
        raise BuildError(
            "Hermes declared package source must not be a Git symlink: "
            + ", ".join(symlinks)
        )
    non_identity_attributes = _git_non_identity_attributes(file_map.values())
    if non_identity_attributes:
        raise BuildError(
            "Hermes declared package source has a content-transforming Git "
            "attribute incompatible with canonical byte identity: "
            + ", ".join(non_identity_attributes)
        )

    return file_map


def _untracked_repo_paths(paths) -> list:
    """Return repository-relative paths absent from Git's tracked index."""
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "-z"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    tracked = {
        pathlib.PurePosixPath(os.fsdecode(path)).as_posix()
        for path in proc.stdout.split(b"\0")
        if path
    }
    return sorted(set(paths) - tracked)


def _git_symlink_repo_paths(paths) -> list:
    """Return declared sources recorded with Git's symlink index mode."""
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--stage", "-z"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    modes = {}
    for entry in proc.stdout.split(b"\0"):
        metadata, separator, encoded_path = entry.partition(b"\t")
        if not separator:
            continue
        mode = metadata.split(b" ", 1)[0]
        path = pathlib.PurePosixPath(os.fsdecode(encoded_path)).as_posix()
        modes[path] = os.fsdecode(mode)
    return sorted(
        path for path in set(paths) if modes.get(path) == "120000"
    )


def _git_non_identity_attributes(paths) -> list:
    """Return declared sources with clean/smudge or encoding transforms."""
    path_list = sorted(set(paths))
    if not path_list:
        return []
    # An installed Sage framework is copied from verified release bytes and
    # intentionally has no Git metadata. Attribute transforms can only affect a
    # checkout, so there is nothing to inspect in that distribution shape.
    if not (REPO_ROOT / ".git").exists():
        return []
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "check-attr",
            "-z",
            "--stdin",
            *HERMES_NON_IDENTITY_GIT_ATTRIBUTES,
        ],
        input=b"\0".join(os.fsencode(path) for path in path_list) + b"\0",
        capture_output=True,
    )
    if proc.returncode != 0:
        raise BuildError(
            "cannot verify canonical Git attributes for Hermes package sources: "
            + proc.stderr.decode("utf-8", errors="replace").strip()
        )
    fields = proc.stdout.split(b"\0")
    violations = []
    for index in range(0, len(fields) - 1, 3):
        encoded_path, encoded_attribute, encoded_value = fields[index : index + 3]
        path = os.fsdecode(encoded_path)
        attribute = os.fsdecode(encoded_attribute)
        value = os.fsdecode(encoded_value)
        if value not in {"unspecified", "unset"}:
            violations.append(f"{path} ({attribute}={value})")
    return sorted(violations)


NAVIGATOR_FRONTMATTER = """---
name: sage-navigator
description: >
  Sage's process layer — routing, the constitution, the checkpoint contract, and
  the skill-check rule. A plugin cannot install a CLAUDE.md, so this carries what
  a vendored install puts in the eager layer. Generated from the same source; do
  not hand-edit.
user-invocable: false
---

<!-- GENERATED by runtime/tools/build_plugin.py from
     runtime/platforms/_shared/instructions-body.sh. Do not edit: build_plugin.py
     --check rebuilds it and a hand edit will be silently overwritten. The
     hand-maintained version of this file drifted for two releases and shipped a
     routing table that was a release out of date. -->

"""


def build_navigator() -> str:
    """The eager body, rendered as the plugin's process skill.

    Same source as every platform's instructions file — because a second copy is
    a copy that drifts, and this one did.
    """
    script = (
        'set -eu\n'
        'source "%s"\n'
        'source "%s"\n'
        'emit_instructions_body\n' % (bash_path(INSTRUCTIONS_BODY),
                                      bash_path(CONSTITUTION_SH))
    )
    proc = subprocess.run([BASH, "-c", script], capture_output=True, text=True)
    if proc.returncode != 0:
        raise BuildError("could not emit the instructions body for the navigator:\n"
                         + proc.stderr[-800:])

    body = proc.stdout

    # The constitution placeholder is substituted by each platform's generator. The
    # plugin has no project to read a preset from, so it gets the base five — with
    # each principle naming the mechanism that enforces it, exactly as the eager
    # layer does.
    const = subprocess.run(
        [BASH, "-c",
         'source "%s"; build_constitution_section "%s" "/nonexistent"'
         % (bash_path(CONSTITUTION_SH), bash_path(REPO_ROOT / "core"))],
        capture_output=True, text=True)
    if const.returncode != 0:
        raise BuildError("constitution merge failed:\n" + const.stderr[-400:])

    body = body.replace("__CONSTITUTION_PLACEHOLDER__", const.stdout.rstrip("\n"))

    if "__CONSTITUTION_PLACEHOLDER__" in body:
        raise BuildError("the navigator still carries an unsubstituted placeholder")

    return NAVIGATOR_FRONTMATTER + body


def copy_file_text(text: str, dst: pathlib.Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


def build(out: pathlib.Path, target: str = DEFAULT_TARGET) -> None:
    """Build one explicit platform artifact; Claude remains the default."""
    if target == DEFAULT_TARGET:
        _build_claude(out)
    elif target == "hermes":
        _build_hermes(out)
    else:
        raise BuildError(
            f"unknown plugin build target {target!r}; choose from {', '.join(BUILD_TARGETS)}"
        )


def _build_hermes(out: pathlib.Path) -> None:
    """Build the complete Sage framework as a Hermes plugin package."""
    file_map = hermes_file_map()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for package_target, source in sorted(file_map.items()):
        copy_hermes_source(
            REPO_ROOT / source,
            out / pathlib.PurePosixPath(package_target),
        )
    if load_hermes_topology().get("framework_package") is not None:
        manifest = out / "plugins" / "sage" / HERMES_FRAMEWORK_MANIFEST_NAME
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(hermes_framework_manifest_bytes())


def _build_claude(out: pathlib.Path) -> None:
    version = read_version()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # ── 1. Framework skills ──
    # A skill in skills/ that is neither shipped nor explicitly excluded is an
    # unmade decision — fail rather than silently pick one.
    on_disk = {p.name for p in SKILLS.iterdir() if p.is_dir()}
    undeclared = on_disk - PLUGIN_SKILLS - SKILLS_NOT_IN_PLUGIN
    if undeclared:
        raise BuildError(
            "skills/ holds dirs the plugin manifest does not mention: "
            + ", ".join(sorted(undeclared))
            + " — add each to PLUGIN_SKILLS or SKILLS_NOT_IN_PLUGIN in build_plugin.py"
        )

    for name in sorted(PLUGIN_SKILLS & on_disk):
        skill = SKILLS / name
        for f in skill.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(skill)
            top = rel.parts[0]
            if not (str(rel) in SKILL_INCLUDE_FILES or top in SKILL_INCLUDE_DIRS):
                continue
            copy_file(f, out / "skills" / name / rel)

    # ── 1a. sage-navigator — GENERATED from the eager body ──
    #
    # A plugin cannot write a CLAUDE.md into a user's project, so the navigator is
    # the plugin's process layer. It used to be a 441-line file maintained BY HAND
    # alongside the real eager body — and it had drifted for two releases: it still
    # routed to /analyze, /qa, /design-review and /status, every one of them folded
    # into another command back in v1.2.0. Plugin users were being handed a routing
    # table a release out of date, and nothing noticed, because nothing compared the
    # two copies.
    #
    # It is generated from the same source as CLAUDE.md now. There is one eager
    # layer. If it is wrong it is wrong in one place, and every consumer is wrong
    # together — which is the only kind of wrong you can actually fix.
    #
    # This is the drift ADR-5 exists to forbid, and it survived because the
    # navigator lived in the overlay rather than in FILE_MAP. It is neither now.
    copy_file_text(build_navigator(), out / "skills" / "sage-navigator" / "SKILL.md")

    # ── 1b. System skills (ADR-9 delivery class 2) ──
    for name in sorted(SYSTEM_SKILL_NAMES):
        copy_file(SYSTEM_SKILLS / name / "SKILL.md",
                  out / "skills" / name / "SKILL.md")

    # ── 2. File map ──
    for plugin_rel, src_rel in FILE_MAP.items():
        src = REPO_ROOT / src_rel
        if not src.is_file():
            raise BuildError(f"file-map source missing: {src_rel}")
        copy_file(src, out / plugin_rel)

    # ── 3. Overlay (overrides) ──
    if not OVERLAY.is_dir():
        raise BuildError(f"overlay dir missing: {OVERLAY.relative_to(REPO_ROOT)}")
    for f in sorted(OVERLAY.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(OVERLAY)
        dst = out / rel
        content = f.read_bytes()
        placeholder = VERSION_PLACEHOLDER.encode("utf-8")
        if placeholder in content:
            content = content.replace(placeholder, version.encode("utf-8"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(content)

    # Every declared skill must have materialized from one layer or the other.
    for name in sorted(PLUGIN_SKILLS | SYSTEM_SKILL_NAMES):
        if not (out / "skills" / name / "SKILL.md").is_file():
            raise BuildError(
                f"PLUGIN_SKILLS names {name!r} but no layer produced "
                f"skills/{name}/SKILL.md"
            )


def build_inputs() -> list:
    """Every repo file the build reads. The artifact is exactly a function of these."""
    inputs = [REPO_ROOT / "VERSION"]
    inputs += [REPO_ROOT / src for src in FILE_MAP.values()]
    inputs += [f for f in OVERLAY.rglob("*") if f.is_file()]
    for name in sorted(PLUGIN_SKILLS):
        skill = SKILLS / name
        if not skill.is_dir():
            continue
        for f in skill.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(skill)
            if str(rel) in SKILL_INCLUDE_FILES or rel.parts[0] in SKILL_INCLUDE_DIRS:
                inputs.append(f)
    return inputs


def untracked_inputs() -> list:
    """Build inputs that git does not track — files that exist for you and nobody else.

    .gitignore's unanchored `sage/` rule silently swallowed the plugin's /sage
    router for the whole Phase-3 program: it sat on every developer's disk, was
    absent from every clean checkout, and would have shipped a plugin with no
    entry point once the committed mirror stopped covering for it. An input the
    release runner cannot see is not an input — it is a local accident.

    Returns [] when this is not a git checkout (a release tarball, say), where
    the question does not apply.
    """
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "-z"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    tracked = {
        REPO_ROOT / p.decode()
        for p in proc.stdout.split(b"\0") if p
    }
    return [f for f in build_inputs() if f not in tracked]


def _diff(a: pathlib.Path, b: pathlib.Path, rel: str, out: list):
    """Recursively compare two trees; append drift descriptions to `out`."""
    cmp = filecmp.dircmp(a, b)
    for name in sorted(cmp.left_only):
        out.append(f"  only in generated: {rel}{name}")
    for name in sorted(cmp.right_only):
        out.append(f"  only in mirror:    {rel}{name}")
    # filecmp uses shallow stat compare by default; force content compare.
    for name in sorted(cmp.common_files):
        if not filecmp.cmp(a / name, b / name, shallow=False):
            out.append(f"  differs:           {rel}{name}")
    for name in sorted(cmp.common_dirs):
        _diff(a / name, b / name, f"{rel}{name}/", out)


def audit(tree: pathlib.Path, target: str = DEFAULT_TARGET) -> list:
    """Audit one platform artifact against the matching source contract."""
    if target == DEFAULT_TARGET:
        return _audit_claude(tree)
    if target == "hermes":
        return _audit_hermes(tree)
    return [f"unknown plugin audit target {target!r}"]


def _audit_hermes(tree: pathlib.Path) -> list:
    """Reject missing, changed, or unmanifested Hermes package bytes."""
    problems = []
    try:
        file_map = hermes_file_map()
    except BuildError as exc:
        return [str(exc)]

    actual_files = {
        path.relative_to(tree).as_posix()
        for path in tree.rglob("*")
        if path.is_file()
    }
    has_framework = load_hermes_topology().get("framework_package") is not None
    manifest_relative = "plugins/sage/" + HERMES_FRAMEWORK_MANIFEST_NAME
    expected_files = set(file_map)
    if has_framework:
        expected_files.add(manifest_relative)

    for rel in sorted(actual_files - expected_files):
        problems.append(f"unmanifested file in Hermes artifact: {rel}")
    for rel in sorted(expected_files - actual_files):
        problems.append(f"manifested Hermes package target is missing: {rel}")
    for rel in sorted((actual_files & expected_files) - {manifest_relative}):
        source = REPO_ROOT / file_map[rel]
        artifact = tree / pathlib.PurePosixPath(rel)
        if canonical_hermes_source_bytes(source) != artifact.read_bytes():
            problems.append(f"Hermes package target {rel} differs from {file_map[rel]}")
    manifest = tree / pathlib.PurePosixPath(manifest_relative)
    if (
        has_framework
        and manifest.is_file()
        and manifest.read_bytes() != hermes_framework_manifest_bytes()
    ):
        problems.append("Hermes framework package manifest differs from canonical sources")

    return problems


def _audit_claude(tree: pathlib.Path) -> list:
    """Verify a built tree is well-formed and faithful to its sources.

    No committed mirror exists to diff against any more, so these are the
    properties that used to be enforced by eyeballing the mirror's diff:
    the manifests are stamped and pin the dist branch, the gate scripts are
    byte-identical to the ones the repo tests, and every hook the plugin
    registers actually ships.
    """
    version = read_version()
    problems: list = []

    # 1. No placeholder survives into the artifact.
    for f in sorted(tree.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if VERSION_PLACEHOLDER in text:
            problems.append(f"unsubstituted {VERSION_PLACEHOLDER} in {f.relative_to(tree)}")

    # 2. plugin.json is the version authority and agrees with VERSION.
    plugin_json = tree / ".claude-plugin" / "plugin.json"
    if not plugin_json.is_file():
        problems.append("missing .claude-plugin/plugin.json")
    else:
        try:
            found = json.loads(plugin_json.read_text()).get("version")
        except json.JSONDecodeError as exc:
            problems.append(f".claude-plugin/plugin.json is not valid JSON: {exc}")
            found = None
        if found is not None and found != version:
            problems.append(
                f".claude-plugin/plugin.json version {found} != VERSION {version}"
            )

    # 3. The marketplace entry pins the dist branch and defers the version to
    #    plugin.json. Without `ref` the source resolves to the default branch,
    #    which carries no plugin tree — the plugin would be uninstallable.
    market = tree / ".claude-plugin" / "marketplace.json"
    if not market.is_file():
        problems.append("missing .claude-plugin/marketplace.json")
    else:
        try:
            entries = json.loads(market.read_text()).get("plugins", [])
        except json.JSONDecodeError as exc:
            problems.append(f".claude-plugin/marketplace.json is not valid JSON: {exc}")
            entries = []
        for entry in entries:
            name = entry.get("name", "?")
            source = entry.get("source", {})
            if source.get("source") == "git-subdir" and source.get("ref") != DIST_REF:
                problems.append(
                    f"marketplace entry {name!r}: source.ref is {source.get('ref')!r}, "
                    f"expected {DIST_REF!r} — the default branch carries no plugin tree"
                )
            if "version" in entry:
                problems.append(
                    f"marketplace entry {name!r} pins a version — remove it; "
                    f"plugin.json is the single authority"
                )

    # 4. Gate scripts and templates are byte-identical to the sources the repo
    #    tests. A mis-wired FILE_MAP would ship a stale gate.
    for plugin_rel, src_rel in FILE_MAP.items():
        src, dst = REPO_ROOT / src_rel, tree / plugin_rel
        if not dst.is_file():
            problems.append(f"file-map target missing from artifact: {plugin_rel}")
        elif not filecmp.cmp(src, dst, shallow=False):
            problems.append(f"{plugin_rel} differs from its source {src_rel}")

    # 5. Every hook the plugin registers resolves to a file that ships.
    hooks_json = tree / "hooks" / "hooks.json"
    if not hooks_json.is_file():
        problems.append("missing hooks/hooks.json")
    else:
        try:
            hooks = json.loads(hooks_json.read_text())
        except json.JSONDecodeError as exc:
            problems.append(f"hooks/hooks.json is not valid JSON: {exc}")
            hooks = {}
        for matchers in hooks.get("hooks", {}).values():
            for matcher in matchers:
                for hook in matcher.get("hooks", []):
                    for rel in HOOK_COMMAND.findall(hook.get("command", "")):
                        if not (tree / rel).is_file():
                            problems.append(f"hooks.json registers {rel}, which does not ship")

    # 6. Every shipped skill can actually REGISTER. Claude Code discovers a skill
    #    by its frontmatter; a SKILL.md whose `name:` disagrees with its directory
    #    or whose description is empty is not rejected loudly — it just silently
    #    never loads, which on the install path most users take looks exactly like
    #    "Sage doesn't work". Same failure family as the stale router that shipped
    #    for two releases.
    for skill_dir in sorted((tree / "skills").iterdir()):
        smd = skill_dir / "SKILL.md"
        if not smd.is_file():
            continue                      # rule 3 already reports missing SKILL.md
        text = smd.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"\A---\r?\n(.*?)\r?\n---", text, re.S)
        if not m:
            problems.append(f"skills/{skill_dir.name}/SKILL.md has no frontmatter "
                            f"— it will silently fail to register")
            continue
        fm = m.group(1)
        nm = re.search(r"^name:\s*[\"']?([A-Za-z0-9_-]+)", fm, re.M)
        if not nm or nm.group(1) != skill_dir.name:
            problems.append(
                f"skills/{skill_dir.name}: frontmatter name "
                f"{nm.group(1) if nm else '(missing)'!r} does not match its "
                f"directory — discovery will misfile or drop it")
        if not re.search(r"^description:\s*\S", fm, re.M):
            problems.append(
                f"skills/{skill_dir.name}: empty or missing description — "
                f"description-triggered discovery can never fire")

    # 7. Every input the build reads is tracked by git. Otherwise this build and
    #    the one the release runner does are builds of two different trees.
    for f in untracked_inputs():
        problems.append(
            f"build input is not tracked by git: {f.relative_to(REPO_ROOT)} "
            f"— it exists here and in no clean checkout (check .gitignore)"
        )

    return problems


def check(target: str = DEFAULT_TARGET) -> int:
    a = pathlib.Path(tempfile.mkdtemp(prefix="sage-plugin-a-"))
    b = pathlib.Path(tempfile.mkdtemp(prefix="sage-plugin-b-"))
    try:
        build(a, target=target)
        build(b, target=target)
        problems = audit(a, target=target)
        # A build that is not reproducible cannot be reviewed by its inputs.
        drift: list = []
        _diff(a, b, "", drift)
        if drift:
            problems.append("build is not reproducible — two runs differ:")
            problems.extend(drift)
        if target == DEFAULT_TARGET:
            artifact_count = len(
                [p for p in (a / "skills").iterdir() if p.is_dir()]
            )
            artifact_label = "skills"
        else:
            artifact_count = len([p for p in a.rglob("*") if p.is_file()])
            artifact_label = "manifested files"
    finally:
        shutil.rmtree(a, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)

    if problems:
        if target == DEFAULT_TARGET:
            print("✗ the generated plugin does not satisfy its contract:")
        else:
            print("✗ the Hermes manifest-owned package artifact is invalid:")
        for line in problems:
            print(f"  {line}")
        print()
        if target == DEFAULT_TARGET:
            print("FAIL — correct the source side (skills/, core/, runtime/plugin-overlay/).")
        else:
            print(f"FAIL — correct the source side for the {target} target.")
        return 1

    if target == DEFAULT_TARGET:
        print(f"OK — plugin builds clean: {artifact_count} skills, "
              f"{len(FILE_MAP)} mapped files, version {read_version()}.")
    else:
        print("OK — Hermes manifest-owned package artifact verified: "
              f"{artifact_count} {artifact_label}, version {read_version()}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Sage plugin artifact.")
    parser.add_argument(
        "--target",
        choices=BUILD_TARGETS,
        default=DEFAULT_TARGET,
        help="artifact target (default: claude)",
    )
    parser.add_argument("--check", action="store_true",
                        help="build and verify the artifact against its contract")
    parser.add_argument("--out", type=pathlib.Path, default=None,
                        help="output directory (default: dist/sage-claude-plugin)")
    args = parser.parse_args()

    try:
        if args.check:
            return check(target=args.target)
        default_dir = (
            "sage-claude-plugin"
            if args.target == DEFAULT_TARGET
            else f"sage-{args.target}-plugin"
        )
        out = args.out or (REPO_ROOT / "dist" / default_dir)
        build(out, target=args.target)
        if args.target == DEFAULT_TARGET:
            print(f"OK — built plugin into {out}")
        else:
            print(f"OK — built the full Sage framework as a Hermes plugin into {out}")
        return 0
    except BuildError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
