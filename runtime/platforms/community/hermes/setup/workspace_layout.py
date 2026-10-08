#!/usr/bin/env python3
"""Materialize Sage inside exactly one frozen Hermes profile workspace.

This module owns only the workspace surfaces of a Hermes installation:

* ``workspace/.hermes.md`` is generated from the current canonical shared
  instructions and the bound workspace's preserved constitution.
* ``workspace/sage`` is a complete replace-managed runtime copy.
* durable state remains under ``workspace/.sage`` and
  ``workspace/.sage-memory`` and is never part of that replacement.

The public staging/commit split lets the transactional installer inspect and
journal a complete candidate before committing it.  There is deliberately no
HOME, cwd, ancestor, or profile-enumeration fallback in this module.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

try:  # Package import in an installed adapter.
    from .profile_binding import ProfileBinding
except ImportError:  # Direct path import in validators and bootstrap code.
    from profile_binding import ProfileBinding


PathInput = Union[str, os.PathLike]


class LayoutError(RuntimeError):
    """A workspace layout source or destination is absent, unsafe, or stale."""


_RUNTIME_ENTRIES = (
    "core",
    "skills",
    "runtime",
    "bin",
    "__init__.py",
    "plugin.yaml",
    "LICENSE",
    "VERSION",
)
_RUNTIME_DIRECTORIES = frozenset(("core", "skills", "runtime", "bin"))
_RUNTIME_PRUNE_PATHS = (
    "runtime/tools/release.py",
    "runtime/tools/build_plugin.py",
    "runtime/plugin-overlay",
)
_RUNTIME_COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
_INITIATIVE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PRESET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_FORBIDDEN_RUNTIME_FILES = frozenset(("soul.md", "claude.md"))
_FORBIDDEN_RUNTIME_COMPONENTS = frozenset((".claude", "agent-hooks"))
_RECOVERY_MARKER_NAME = "RECOVERY_REQUIRED.txt"
_RECOVERY_MARKER_BYTES = (
    b"Sage workspace replacement did not roll back completely.\n"
    b"Preserve this directory and recover prior bytes from backup/.\n"
)


def _path_key(path: pathlib.Path) -> str:
    return os.path.normpath(os.fspath(path))


def _path_spelling(path: pathlib.Path) -> str:
    return os.path.normpath(os.fspath(path))


def _same_path(left: pathlib.Path, right: pathlib.Path) -> bool:
    return _path_key(left) == _path_key(right)


def _is_nonexact_windows_alias(left: pathlib.Path, right: pathlib.Path) -> bool:
    """Detect a case-insensitive Windows alias only so it can be rejected."""

    if os.name != "nt" or _same_path(left, right):
        return False
    return _path_spelling(left).casefold() == _path_spelling(right).casefold()


def _is_same_source_profile_binding(value: Any) -> bool:
    """Recognize only the authorized class loaded twice from this exact file."""

    value_type = type(value)
    if value_type.__name__ != "ProfileBinding":
        return False
    module = sys.modules.get(value_type.__module__)
    if module is None or getattr(module, "ProfileBinding", None) is not value_type:
        return False
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str) or not module_file:
        return False
    try:
        expected = pathlib.Path(__file__).with_name("profile_binding.py").resolve(
            strict=True
        )
        actual = pathlib.Path(module_file).resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    return _same_path(actual, expected)


def _contains(root: pathlib.Path, target: pathlib.Path) -> bool:
    root_parts = pathlib.Path(_path_spelling(root)).parts
    target_parts = pathlib.Path(_path_spelling(target)).parts
    return (
        len(target_parts) >= len(root_parts)
        and target_parts[: len(root_parts)] == root_parts
    )


def _has_windows_namespace_prefix(native: str) -> bool:
    normalized = native.replace("/", "\\").casefold()
    return normalized.startswith(("\\\\?\\", "\\\\.\\", "\\??\\"))


def _normalize_resolver_path(path: pathlib.Path) -> pathlib.Path:
    """Remove only a Windows namespace prefix introduced by Path.resolve."""

    if os.name != "nt":
        return path
    native = os.fspath(path)
    folded = native.casefold()
    if folded.startswith("\\\\?\\unc\\"):
        return pathlib.Path("\\\\" + native[8:])
    if folded.startswith("\\\\?\\"):
        return pathlib.Path(native[4:])
    return path


def _as_absolute_path(value: Any, label: str) -> pathlib.Path:
    if value is None or isinstance(value, bool):
        raise LayoutError("%s must be an explicit absolute path" % label)
    try:
        native = os.fspath(value)
    except TypeError as exc:
        raise LayoutError("%s must be an explicit absolute path" % label) from exc
    if not isinstance(native, str) or not native or "\x00" in native:
        raise LayoutError("%s must be an explicit absolute path" % label)
    if _has_windows_namespace_prefix(native):
        raise LayoutError(
            "%s must use exact spelling without a Windows namespace alias" % label
        )
    path = pathlib.Path(native)
    if not path.is_absolute():
        raise LayoutError("%s must be an explicit absolute path" % label)
    if ".." in path.parts:
        raise LayoutError("%s cannot contain '..'" % label)
    return path


def _canonical_source_root(value: Any) -> pathlib.Path:
    path = _as_absolute_path(value, "framework_root")
    try:
        canonical = _normalize_resolver_path(path.resolve(strict=True))
    except (OSError, RuntimeError) as exc:
        raise LayoutError("framework_root does not resolve: %s" % exc) from exc
    if not canonical.is_dir():
        raise LayoutError("framework_root must be an existing directory")
    if _path_spelling(path) != _path_spelling(canonical):
        raise LayoutError(
            "framework_root must be its canonical physical path: %s" % canonical
        )
    if _is_link_or_reparse(path):
        raise LayoutError("framework_root cannot be a link or reparse point")
    return canonical


def _is_link_or_reparse(path: pathlib.Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & _REPARSE_ATTRIBUTE)
    except FileNotFoundError:
        return path.is_symlink()
    except OSError as exc:
        raise LayoutError("cannot inspect path metadata for %s: %s" % (path, exc)) from exc


def _assert_existing_file_not_aliased(path: pathlib.Path, label: str) -> None:
    """Reject an existing file whose bytes have another filesystem name."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise LayoutError("%s cannot be inspected safely: %s" % (label, exc)) from exc
    attributes = getattr(metadata, "st_file_attributes", 0)
    if stat.S_ISLNK(metadata.st_mode) or bool(attributes & _REPARSE_ATTRIBUTE):
        raise LayoutError("%s cannot be a link or reparse point" % label)
    if stat.S_ISREG(metadata.st_mode) and int(metadata.st_nlink) != 1:
        raise LayoutError(
            "%s cannot be a hardlink (link count: %d)"
            % (label, metadata.st_nlink)
        )


def _path_lexists(path: pathlib.Path) -> bool:
    """Return whether one directory entry exists without following its leaf."""

    return os.path.lexists(os.fspath(path))


@dataclass(frozen=True)
class _LocalFileIdentity:
    """One no-follow snapshot of a single-link local regular file.

    Alias evidence is device/inode/link_count.  On Windows the timestamp
    fields are forgeable via SetFileTime, so modified_ns/changed_ns and
    size are supplemental byte-drift signals, not identity proof.  A
    snapshot pair proves "no alias between the two stat() calls"; a
    caller that needs return-path safety must re-snapshot at the point
    of use instead of trusting an earlier capture.
    """

    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int
    link_count: int


def _single_link_local_file_identity(
    path: pathlib.Path,
) -> Optional[_LocalFileIdentity]:
    """Snapshot one leaf without following it; reject links and hardlinks."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LayoutError("cannot inspect local file %s: %s" % (path, exc)) from exc
    attributes = getattr(metadata, "st_file_attributes", 0)
    link_count = int(metadata.st_nlink)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or bool(attributes & _REPARSE_ATTRIBUTE)
        or link_count != 1
    ):
        return None
    return _LocalFileIdentity(
        device=int(metadata.st_dev),
        inode=int(metadata.st_ino),
        size=int(metadata.st_size),
        modified_ns=int(
            getattr(metadata, "st_mtime_ns", int(metadata.st_mtime * 1000000000))
        ),
        changed_ns=int(
            getattr(metadata, "st_ctime_ns", int(metadata.st_ctime * 1000000000))
        ),
        link_count=link_count,
    )


def _iter_existing_components(root: pathlib.Path, target: pathlib.Path) -> Iterable[pathlib.Path]:
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise LayoutError("target is outside the bound workspace: %s" % target) from exc
    current = root
    yield current
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            yield current
        else:
            break


def _assert_no_link_escape(
    root: pathlib.Path, target: pathlib.Path, label: str
) -> pathlib.Path:
    for component in _iter_existing_components(root, target):
        if _is_link_or_reparse(component):
            raise LayoutError(
                "%s cannot traverse a link, junction, or reparse point: %s"
                % (label, component)
            )
    try:
        canonical = _normalize_resolver_path(target.resolve(strict=False))
    except (OSError, RuntimeError) as exc:
        raise LayoutError("%s cannot be canonicalized: %s" % (label, exc)) from exc
    if _path_spelling(target) != _path_spelling(canonical):
        raise LayoutError(
            "%s escapes through a link or reparse point (resolved path: %s)"
            % (label, canonical)
        )
    return canonical


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LayoutError("cannot hash %s: %s" % (path, exc)) from exc
    return digest.hexdigest()


def _regular_files(
    root: pathlib.Path,
    label: str = "runtime destination",
    skip_roots: Tuple[pathlib.Path, ...] = (),
) -> Iterable[pathlib.Path]:
    if not root.exists():
        return
    for directory, names, files in os.walk(os.fspath(root), followlinks=False):
        directory_path = pathlib.Path(directory)
        retained_names = []
        for name in sorted(names):
            path = directory_path / name
            if any(_same_path(path, skip_root) for skip_root in skip_roots):
                continue
            if _is_link_or_reparse(path):
                raise LayoutError(
                    "%s cannot contain a link or reparse point: %s" % (label, path)
                )
            retained_names.append(name)
        names[:] = retained_names
        for name in sorted(files):
            path = directory_path / name
            if _is_link_or_reparse(path):
                raise LayoutError(
                    "%s cannot contain a link or reparse point: %s" % (label, path)
                )
            try:
                metadata = path.lstat()
            except OSError as exc:
                raise LayoutError(
                    "cannot inspect %s file %s: %s" % (label, path, exc)
                ) from exc
            if not stat.S_ISREG(metadata.st_mode):
                raise LayoutError("%s contains a non-regular file: %s" % (label, path))
            if int(metadata.st_nlink) != 1:
                raise LayoutError(
                    "%s cannot contain a hardlink (link count: %d): %s"
                    % (label, metadata.st_nlink, path)
                )
            yield path


def _clear_readonly_and_retry(function: Any, path: str, _error: Any) -> None:
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    function(path)


def _remove_tree(path: pathlib.Path) -> None:
    """Remove one already-contained, link-free operation tree."""

    shutil.rmtree(path, onerror=_clear_readonly_and_retry)


def _source_tree_preflight(path: pathlib.Path, framework_root: pathlib.Path) -> None:
    if _is_link_or_reparse(path):
        raise LayoutError("runtime source cannot be a link or reparse point: %s" % path)
    if path.is_file():
        if path.name.casefold() in _FORBIDDEN_RUNTIME_FILES:
            raise LayoutError("forbidden Hermes host artifact in runtime source: %s" % path)
        if not stat.S_ISREG(path.stat().st_mode):
            raise LayoutError("runtime source must be a regular file: %s" % path)
        return
    if not path.is_dir():
        raise LayoutError("runtime source is missing or has the wrong type: %s" % path)

    seen: Dict[str, pathlib.Path] = {}
    for directory, names, files in os.walk(os.fspath(path), followlinks=False):
        directory_path = pathlib.Path(directory)
        folded_names = {name.casefold() for name in names}
        folded_files = {name.casefold() for name in files}
        forbidden_components = (folded_names | folded_files) & _FORBIDDEN_RUNTIME_COMPONENTS
        if forbidden_components:
            name = sorted(forbidden_components)[0]
            raise LayoutError(
                "forbidden Hermes host artifact in runtime source: %s"
                % (directory_path / name)
            )
        forbidden_files = (folded_names | folded_files) & _FORBIDDEN_RUNTIME_FILES
        if forbidden_files:
            name = sorted(forbidden_files)[0]
            raise LayoutError(
                "forbidden Hermes host artifact in runtime source: %s"
                % (directory_path / name)
            )
        if "hook.yaml" in folded_files and "handler.py" in folded_files:
            raise LayoutError(
                "forbidden Hermes gateway HOOK.yaml/handler bundle in runtime source: %s"
                % directory_path
            )
        for name in sorted(names):
            child = directory_path / name
            relative = child.relative_to(framework_root).as_posix()
            key = relative.casefold()
            if key in seen and seen[key] != child:
                raise LayoutError(
                    "runtime source has a case-insensitive path collision: %s and %s"
                    % (seen[key], child)
                )
            seen[key] = child
            if name.casefold() == ".git":
                raise LayoutError("runtime source contains nested Git metadata: %s" % child)
            if _is_link_or_reparse(child):
                raise LayoutError("runtime source contains a link or reparse point: %s" % child)
        for name in sorted(files):
            child = directory_path / name
            relative = child.relative_to(framework_root).as_posix()
            key = relative.casefold()
            if key in seen and seen[key] != child:
                raise LayoutError(
                    "runtime source has a case-insensitive path collision: %s and %s"
                    % (seen[key], child)
                )
            seen[key] = child
            if name.casefold() == ".git":
                raise LayoutError("runtime source contains nested Git metadata: %s" % child)
            if _is_link_or_reparse(child):
                raise LayoutError("runtime source contains a link or reparse point: %s" % child)
            try:
                mode = child.stat().st_mode
            except OSError as exc:
                raise LayoutError("cannot inspect runtime source %s: %s" % (child, exc)) from exc
            if not stat.S_ISREG(mode):
                raise LayoutError("runtime source contains a non-regular file: %s" % child)


def _assert_framework_disjoint(root: pathlib.Path, binding: ProfileBinding) -> None:
    workspace = binding.workspace_root
    runtime = workspace / "sage"
    if (
        _contains(root, workspace)
        or _contains(workspace, root)
        or _contains(root, runtime)
        or _contains(runtime, root)
    ):
        raise LayoutError(
            "framework source overlaps the frozen Hermes workspace/runtime: %s" % root
        )


def _preflight_framework(value: Any, binding: ProfileBinding) -> pathlib.Path:
    root = _canonical_source_root(value)
    _assert_framework_disjoint(root, binding)
    for name in _RUNTIME_ENTRIES:
        path = root / name
        if not path.exists() and not path.is_symlink():
            raise LayoutError("framework runtime source is missing required entry: %s" % name)
        if name in _RUNTIME_DIRECTORIES and not path.is_dir():
            raise LayoutError("framework runtime directory has the wrong type: %s" % name)
        if name not in _RUNTIME_DIRECTORIES and not path.is_file():
            raise LayoutError("framework runtime file has the wrong type: %s" % name)
        _source_tree_preflight(path, root)

    instructions = root / "runtime" / "platforms" / "_shared" / "instructions-body.sh"
    constitution = root / "runtime" / "platforms" / "_shared" / "constitution.sh"
    if not instructions.is_file() or not constitution.is_file():
        raise LayoutError("framework is missing canonical shared instruction sources")
    return root


def _read_utf8(path: pathlib.Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LayoutError("cannot read %s %s: %s" % (label, path, exc)) from exc


def _frontmatter_extends(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^extends:\s*(.*?)\s*$", line)
        if match:
            return match.group(1).strip().strip("\"'")
    return ""


def _bash_path(path: pathlib.Path) -> str:
    return os.fspath(path).replace("\\", "/")


def _resolve_bash() -> pathlib.Path:
    explicit = os.environ.get("SAGE_BASH_EXE")
    candidates: List[pathlib.Path] = []
    if explicit:
        candidate = pathlib.Path(explicit)
        if not candidate.is_absolute():
            raise LayoutError("SAGE_BASH_EXE must be an explicit absolute path")
        candidates.append(candidate)

    if os.name == "nt":
        git_executable = shutil.which("git")
        if git_executable:
            git_root = pathlib.Path(git_executable).resolve().parent.parent
            candidates.extend(
                (git_root / "usr" / "bin" / "bash.exe", git_root / "bin" / "bash.exe")
            )
        for environment_name, suffix in (
            ("ProgramFiles", ("Git", "usr", "bin", "bash.exe")),
            ("ProgramFiles", ("Git", "bin", "bash.exe")),
            ("LOCALAPPDATA", ("Programs", "Git", "usr", "bin", "bash.exe")),
            ("LOCALAPPDATA", ("Programs", "Git", "bin", "bash.exe")),
        ):
            base = os.environ.get(environment_name)
            if base:
                candidates.append(pathlib.Path(base).joinpath(*suffix))
    else:
        discovered = shutil.which("bash")
        if discovered:
            candidates.append(pathlib.Path(discovered))

    for candidate in candidates:
        try:
            canonical = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if canonical.is_file():
            return canonical
    raise LayoutError(
        "canonical instruction generation requires Git Bash on Windows or bash on POSIX"
    )


def _instruction_input_fingerprints(
    framework_root: pathlib.Path, state_root: pathlib.Path
) -> Tuple["SourceFingerprint", ...]:
    sources = [
        (
            "framework:runtime/platforms/_shared/instructions-body.sh",
            framework_root
            / "runtime"
            / "platforms"
            / "_shared"
            / "instructions-body.sh",
        ),
        (
            "framework:runtime/platforms/_shared/constitution.sh",
            framework_root / "runtime" / "platforms" / "_shared" / "constitution.sh",
        ),
    ]
    project_constitution = state_root / "constitution.md"
    if project_constitution.exists() or project_constitution.is_symlink():
        if _is_link_or_reparse(project_constitution) or not project_constitution.is_file():
            raise LayoutError("workspace constitution cannot be a link or reparse point")
        sources.append(("workspace:.sage/constitution.md", project_constitution))
        preset = _frontmatter_extends(_read_utf8(project_constitution, "workspace constitution"))
        if preset and preset not in ("base", "none"):
            if not _PRESET_ID.fullmatch(preset):
                raise LayoutError("workspace constitution has an unsafe preset name: %s" % preset)
            preset_path = (
                framework_root
                / "core"
                / "constitution"
                / "presets"
                / (preset + ".constitution.md")
            )
            if preset_path.exists():
                if _is_link_or_reparse(preset_path) or not preset_path.is_file():
                    raise LayoutError("constitution preset cannot be a link or reparse point")
                sources.append(
                    (
                        "framework:core/constitution/presets/%s.constitution.md" % preset,
                        preset_path,
                    )
                )

    result = []
    for relative_path, path in sources:
        result.append(
            SourceFingerprint(
                relative_path=relative_path,
                sha256=_sha256(path),
                size=path.stat().st_size,
            )
        )
    return tuple(sorted(result, key=lambda item: item.relative_path.casefold()))


def _emit_canonical_instructions(
    framework_root: pathlib.Path, state_root: pathlib.Path
) -> bytes:
    instructions = framework_root / "runtime" / "platforms" / "_shared" / "instructions-body.sh"
    constitution = framework_root / "runtime" / "platforms" / "_shared" / "constitution.sh"
    emitter = r"""set -euo pipefail
export PATH="/usr/bin:/bin:$PATH"
source "$1"
source "$2"
type emit_instructions_body >/dev/null 2>&1
type build_constitution_section >/dev/null 2>&1
emit_instructions_body
printf '\0'
build_constitution_section "$3" "$4"
"""
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    try:
        completed = subprocess.run(
            [
                os.fspath(_resolve_bash()),
                "-c",
                emitter,
                "sage-workspace-emitter",
                _bash_path(instructions),
                _bash_path(constitution),
                _bash_path(framework_root / "core"),
                _bash_path(state_root),
            ],
            cwd=os.fspath(framework_root),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LayoutError("canonical instruction emitter could not run: %s" % exc) from exc
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0:
        raise LayoutError(
            "canonical instruction emitter failed with exit %d: %s"
            % (completed.returncode, stderr or "no diagnostic")
        )
    if stderr:
        raise LayoutError("canonical instruction emitter wrote stderr: %s" % stderr)
    if completed.stdout.count(b"\0") != 1:
        raise LayoutError("canonical instruction emitter returned an ambiguous result")
    template, section = completed.stdout.split(b"\0", 1)
    placeholder = b"__CONSTITUTION_PLACEHOLDER__"
    if template.count(placeholder) != 1:
        raise LayoutError(
            "canonical instructions must contain exactly one constitution placeholder"
        )
    return template.replace(placeholder, section.rstrip(b"\r\n"))


def _render_instructions(
    framework_root: pathlib.Path, state_root: pathlib.Path
) -> Tuple[bytes, Tuple["SourceFingerprint", ...]]:
    before = _instruction_input_fingerprints(framework_root, state_root)
    rendered = _emit_canonical_instructions(framework_root, state_root)
    after = _instruction_input_fingerprints(framework_root, state_root)
    if before != after:
        raise LayoutError("canonical instruction inputs changed during emission")
    return rendered, before


def _copy_runtime(framework_root: pathlib.Path, candidate: pathlib.Path) -> None:
    try:
        candidate.mkdir()
        for name in _RUNTIME_ENTRIES:
            source = framework_root / name
            target = candidate / name
            if source.is_dir():
                shutil.copytree(
                    source,
                    target,
                    copy_function=shutil.copy2,
                    ignore=_RUNTIME_COPY_IGNORE,
                    symlinks=False,
                )
            else:
                shutil.copy2(source, target)

        for relative in _RUNTIME_PRUNE_PATHS:
            target = candidate / pathlib.PurePosixPath(relative)
            if target.is_dir():
                _remove_tree(target)
            elif target.exists():
                target.unlink()

        version = _read_utf8(candidate / "VERSION", "runtime VERSION").strip() or "unknown"
        readme = """# Sage (vendored runtime)

Vendored Sage %s runtime for this project: `core/`, `skills/`,
`runtime/`, `bin/`, plus the Hermes plugin entry files. This is a generated
copy — do not edit it by hand.

- Framework source and docs: https://github.com/xoai/sage
- Regenerate platform files: `sage update`
""" % version
        (candidate / "README.md").write_bytes(readme.encode("utf-8"))
        _source_tree_preflight(candidate, candidate)
    except (OSError, shutil.Error) as exc:
        raise LayoutError("cannot stage the workspace runtime: %s" % exc) from exc


_GIT_METADATA_ENTRIES = frozenset((
    "head", "index", "objects", "refs", "config", "config.worktree",
    "commondir", "gitdir", "packed-refs", "shallow", "worktrees", "modules",
    "reftable", "info", "logs", "hooks", "description", "branches",
    "orig_head", "fetch_head", "merge_head", "auto_merge", "rr-cache",
))


def _git_marker_above(path: pathlib.Path) -> bool:
    """Retain possible Git ownership, not unrelated directories named .git.

    A gitfile, alias, inaccessible marker, or even partially damaged Git
    metadata is conservative evidence. A plain directory containing none of
    Git's metadata cannot by its name alone claim every descendant workspace.
    """
    current = path
    while True:
        marker = current / ".git"
        try:
            metadata = marker.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise LayoutError("cannot inspect Git ownership marker: %s" % exc) from exc
        else:
            if (not stat.S_ISDIR(metadata.st_mode)
                    or getattr(metadata, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE):
                return True
            try:
                names = {entry.name.casefold().removesuffix(".lock") for entry in marker.iterdir()}
            except OSError as exc:
                raise LayoutError("cannot inspect Git ownership marker: %s" % exc) from exc
            if names & _GIT_METADATA_ENTRIES or any(name.startswith("sharedindex.") for name in names):
                return True
        if current.parent == current:
            return False
        current = current.parent


def _git_tracked_runtime(workspace: pathlib.Path, runtime_root: pathlib.Path) -> bool:
    git = shutil.which("git")
    if git is None:
        if _git_marker_above(workspace):
            raise LayoutError(
                "cannot prove the runtime destination is not Git-managed because git is unavailable"
            )
        return False
    try:
        root_probe = subprocess.run(
            [git, "-C", os.fspath(workspace), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise LayoutError("cannot inspect Git ownership for the runtime destination: %s" % exc) from exc
    if root_probe.returncode != 0:
        if _git_marker_above(workspace):
            raise LayoutError(
                "cannot inspect Git ownership for the runtime destination: %s"
                % root_probe.stderr.strip()
            )
        return False
    try:
        repository = pathlib.Path(root_probe.stdout.strip()).resolve(strict=True)
        relative = runtime_root.relative_to(repository).as_posix()
    except (OSError, RuntimeError, ValueError) as exc:
        raise LayoutError("Git reported an invalid repository root for the workspace: %s" % exc) from exc
    tracked = subprocess.run(
        [git, "-C", os.fspath(repository), "ls-files", "--", relative],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if tracked.returncode != 0:
        raise LayoutError(
            "cannot inspect Git ownership for runtime destination: %s"
            % tracked.stderr.strip()
        )
    return bool(tracked.stdout.strip())


def _assert_runtime_replaceable(workspace: pathlib.Path, runtime_root: pathlib.Path) -> None:
    if runtime_root.exists() or runtime_root.is_symlink():
        if _is_link_or_reparse(runtime_root):
            raise LayoutError(
                "runtime destination cannot be a link, junction, or reparse point: %s"
                % runtime_root
            )
        if not runtime_root.is_dir():
            raise LayoutError("runtime destination exists but is not a directory: %s" % runtime_root)
        for directory, names, files in os.walk(os.fspath(runtime_root), followlinks=False):
            directory_path = pathlib.Path(directory)
            for name in tuple(names) + tuple(files):
                child = directory_path / name
                if name == ".git":
                    raise LayoutError(
                        "runtime destination is Git-managed and cannot be replaced: %s" % child
                    )
                if _is_link_or_reparse(child):
                    raise LayoutError(
                        "runtime destination cannot contain a link or reparse point: %s" % child
                    )
    if _git_tracked_runtime(workspace, runtime_root):
        raise LayoutError(
            "runtime destination is Git-managed by the workspace repository: %s"
            % runtime_root
        )


def _snapshot_managed(
    workspace: pathlib.Path,
    instructions_path: pathlib.Path,
    runtime_root: pathlib.Path,
) -> Dict[str, str]:
    snapshot: Dict[str, str] = {}
    if instructions_path.exists():
        if _is_link_or_reparse(instructions_path) or not instructions_path.is_file():
            raise LayoutError("managed instructions destination must be one regular file")
        snapshot[".hermes.md"] = _sha256(instructions_path)
    if runtime_root.exists():
        for path in _regular_files(runtime_root):
            relative = path.relative_to(workspace).as_posix()
            snapshot[relative] = _sha256(path)
    return snapshot


def _candidate_manifest(
    workspace: pathlib.Path,
    instructions_candidate: pathlib.Path,
    runtime_candidate: pathlib.Path,
) -> Tuple["ManagedFile", ...]:
    def measured(path: pathlib.Path, label: str) -> Tuple[str, int]:
        """Hash one staged leaf while binding the read to one local inode."""

        before = _single_link_local_file_identity(path)
        if before is None:
            raise LayoutError(
                "%s must be a single-link regular local candidate file: %s"
                % (label, path)
            )
        digest = _sha256(path)
        after = _single_link_local_file_identity(path)
        if after is None or after != before:
            raise LayoutError("%s identity changed while hashing: %s" % (label, path))
        return digest, after.size

    instructions_hash, instructions_size = measured(
        instructions_candidate, "staged instructions candidate"
    )
    result = [
        ManagedFile(
            relative_path=".hermes.md",
            sha256=instructions_hash,
            size=instructions_size,
        )
    ]
    for path in _regular_files(runtime_candidate):
        relative = pathlib.PurePosixPath("sage") / pathlib.PurePosixPath(
            path.relative_to(runtime_candidate).as_posix()
        )
        file_hash, file_size = measured(path, "staged runtime candidate")
        result.append(
            ManagedFile(
                relative_path=relative.as_posix(),
                sha256=file_hash,
                size=file_size,
            )
        )
    return tuple(sorted(result, key=lambda item: item.relative_path.casefold()))


def _candidate_manifest_identities(
    instructions_candidate: pathlib.Path,
    runtime_candidate: pathlib.Path,
) -> Tuple[Tuple[str, _LocalFileIdentity], ...]:
    def checked_identity(path: pathlib.Path, label: str) -> _LocalFileIdentity:
        identity = _single_link_local_file_identity(path)
        if identity is None:
            raise LayoutError(
                "%s must be a single-link regular local candidate file: %s"
                % (label, path)
            )
        return identity

    identities: List[Tuple[str, _LocalFileIdentity]] = [
        (
            ".hermes.md",
            checked_identity(instructions_candidate, "staged instructions candidate"),
        )
    ]
    for path in _regular_files(runtime_candidate):
        relative = pathlib.PurePosixPath("sage") / pathlib.PurePosixPath(
            path.relative_to(runtime_candidate).as_posix()
        )
        identities.append(
            (relative.as_posix(), checked_identity(path, "staged runtime candidate"))
        )
    return tuple(sorted(identities, key=lambda item: item[0].casefold()))


@dataclass(frozen=True)
class SourceFingerprint:
    """One canonical input that produced the managed instructions file."""

    relative_path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class ManagedFile:
    """One receipt-ready managed workspace file."""

    relative_path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class WorkspaceHomes:
    """Exact bound homes for managed and durable project data."""

    instructions_path: pathlib.Path
    runtime_root: pathlib.Path
    state_root: pathlib.Path
    config_path: pathlib.Path
    gates_root: pathlib.Path
    temporary_root: pathlib.Path
    work_root: pathlib.Path
    session_lock_path: pathlib.Path
    session_pickup_path: pathlib.Path
    session_log_path: pathlib.Path
    gate_blocks_log_path: pathlib.Path
    verification_state_path: pathlib.Path
    decisions_path: pathlib.Path
    pack_lock_path: pathlib.Path
    receipts_root: pathlib.Path
    receipt_path: pathlib.Path
    runs_root: pathlib.Path
    memory_root: pathlib.Path
    memory_db_path: pathlib.Path


@dataclass(frozen=True)
class InitiativeHomes:
    """Exact per-initiative state and quality-ledger homes."""

    root: pathlib.Path
    manifest_path: pathlib.Path
    mode_state_path: pathlib.Path
    goal_state_path: pathlib.Path
    decisions_path: pathlib.Path
    review_ledger_path: pathlib.Path
    autoresearch_log_path: pathlib.Path
    autonomy_log_path: pathlib.Path
    scope_journal_path: pathlib.Path


@dataclass(frozen=True)
class RefreshResult:
    """Receipt-ready evidence from one committed workspace refresh."""

    managed_files: Tuple[ManagedFile, ...]
    stale_paths: Tuple[str, ...]
    instruction_inputs: Tuple[SourceFingerprint, ...]


def _homes_for_binding(binding: ProfileBinding) -> WorkspaceHomes:
    state = binding.state_root
    return WorkspaceHomes(
        instructions_path=binding.workspace_root / ".hermes.md",
        runtime_root=binding.workspace_root / "sage",
        state_root=state,
        config_path=state / "config.yaml",
        gates_root=state / "gates",
        temporary_root=state / "tmp",
        work_root=state / "work",
        session_lock_path=state / ".session-lock",
        session_pickup_path=state / "gates" / "session-pickup.md",
        session_log_path=state / "gates" / "session-log",
        gate_blocks_log_path=state / "gates" / "gate-blocks.log",
        verification_state_path=state / "tmp" / "verify-state",
        decisions_path=state / "decisions.md",
        pack_lock_path=binding.pack_lock_path,
        receipts_root=state / "receipts",
        receipt_path=binding.receipt_path,
        runs_root=binding.runs_root,
        memory_root=binding.memory_root,
        memory_db_path=binding.memory_db_path,
    )


@dataclass(frozen=True, init=False)
class WorkspaceLayout:
    """Binding-driven workspace target selection and candidate staging."""

    binding: ProfileBinding
    homes: WorkspaceHomes

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise LayoutError("WorkspaceLayout must be constructed with from_binding")

    @classmethod
    def from_binding(cls, binding: ProfileBinding) -> "WorkspaceLayout":
        if not isinstance(binding, ProfileBinding):
            # Bootstrap callers sometimes load adjacent setup modules by file
            # path, giving the same class a second Python module identity.
            # Accept only that exact same-source authorized class, then pair
            # its receipt and config views through the local authority gate.
            try:
                if not _is_same_source_profile_binding(binding):
                    raise LayoutError(
                        "cross-module binding is not the same-source authorized "
                        "ProfileBinding"
                    )
                foreign_binding = binding
                receipt_binding = foreign_binding.to_mapping()
                foreign_binding.assert_same(receipt_binding)
                config_binding = foreign_binding.to_config_mapping()
                binding = ProfileBinding.from_authorities(
                    receipt={"binding": receipt_binding},
                    config_binding=config_binding,
                    collection_root=foreign_binding.collection_root,
                    profile_root=foreign_binding.profile_root,
                )
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError) as exc:
                raise LayoutError(
                    "workspace layout requires one paired-authority frozen "
                    "ProfileBinding: %s"
                    % exc
                ) from exc
        instance = object.__new__(cls)
        object.__setattr__(instance, "binding", binding)
        object.__setattr__(instance, "homes", _homes_for_binding(binding))
        instance.assert_exact_homes()
        return instance

    def assert_exact_homes(self) -> "WorkspaceLayout":
        try:
            self.binding.assert_same(self.binding.to_mapping())
        except (TypeError, ValueError, OSError, RuntimeError) as exc:
            raise LayoutError("frozen profile binding is no longer valid: %s" % exc) from exc
        expected = _homes_for_binding(self.binding)
        for field_name in expected.__dataclass_fields__:
            actual_path = getattr(self.homes, field_name)
            expected_path = getattr(expected, field_name)
            if not _same_path(actual_path, expected_path):
                raise LayoutError(
                    "%s does not match the frozen profile binding" % field_name
                )
            self._assert_writable_target_against(actual_path, expected)
        for root, label, skip_roots in (
            (expected.runtime_root, "managed runtime", ()),
            (
                expected.state_root,
                "durable state",
                (expected.temporary_root,),
            ),
            (expected.memory_root, "durable memory", ()),
        ):
            if root.exists() or root.is_symlink():
                tuple(_regular_files(root, label, skip_roots))
        return self

    def _assert_writable_target_against(
        self, value: PathInput, homes: WorkspaceHomes
    ) -> pathlib.Path:
        target = _as_absolute_path(value, "workspace write target")
        workspace = self.binding.workspace_root
        if not _contains(workspace, target):
            raise LayoutError("write target is outside the frozen workspace binding: %s" % target)
        for field_name in homes.__dataclass_fields__:
            expected_target = getattr(homes, field_name)
            if _is_nonexact_windows_alias(target, expected_target):
                raise LayoutError(
                    "workspace write target is a non-exact spelling of %s: %s"
                    % (field_name, target)
                )
        _assert_no_link_escape(workspace, target, "workspace write target")
        _assert_existing_file_not_aliased(target, "workspace write target")
        allowed = (
            _same_path(target, homes.instructions_path)
            or _contains(homes.runtime_root, target)
            or _contains(self.binding.state_root, target)
            or _contains(self.binding.memory_root, target)
        )
        if not allowed:
            raise LayoutError("write target is not a Sage-owned bound workspace surface: %s" % target)
        return target

    def assert_writable_target(self, value: PathInput) -> pathlib.Path:
        self.assert_exact_homes()
        return self._assert_writable_target_against(value, self.homes)

    def initiative_homes(self, initiative_id: str) -> InitiativeHomes:
        if (
            not isinstance(initiative_id, str)
            or not _INITIATIVE_ID.fullmatch(initiative_id)
            or initiative_id in (".", "..")
        ):
            raise LayoutError("initiative_id must be one safe directory component")
        root = self.assert_writable_target(self.homes.work_root / initiative_id)
        manifest = self.assert_writable_target(root / "manifest.md")
        return InitiativeHomes(
            root=root,
            manifest_path=manifest,
            mode_state_path=manifest,
            goal_state_path=manifest,
            decisions_path=self.assert_writable_target(root / "decisions.md"),
            review_ledger_path=self.assert_writable_target(root / "review-ledger.json"),
            autoresearch_log_path=self.assert_writable_target(root / "autoresearch.jsonl"),
            autonomy_log_path=self.assert_writable_target(root / "autonomy.jsonl"),
            scope_journal_path=self.assert_writable_target(root / "scope-journal.jsonl"),
        )

    def _create_durable_homes(self) -> Tuple[pathlib.Path, ...]:
        directories = (
            self.homes.state_root,
            self.homes.work_root,
            self.homes.gates_root,
            self.homes.temporary_root,
            self.homes.receipts_root,
            self.homes.runs_root,
            self.homes.memory_root,
        )
        for path in directories:
            self.assert_writable_target(path)
        created: List[pathlib.Path] = []
        try:
            for path in directories:
                if path.exists():
                    if not path.is_dir():
                        raise LayoutError("durable home exists but is not a directory: %s" % path)
                    continue
                path.mkdir()
                created.append(path)
        except (OSError, LayoutError) as exc:
            rollback_errors = []
            for path in reversed(created):
                try:
                    path.rmdir()
                except OSError as rollback_exc:
                    rollback_errors.append("%s: %s" % (path, rollback_exc))
            if rollback_errors:
                raise LayoutError(
                    "durable-home creation failed and zero-write rollback failed (%s): %s"
                    % ("; ".join(rollback_errors), exc)
                ) from exc
            if isinstance(exc, LayoutError):
                raise
            raise LayoutError("cannot create bound durable homes: %s" % exc) from exc
        return tuple(created)

    def ensure_durable_homes(self) -> WorkspaceHomes:
        self._create_durable_homes()
        return self.homes

    def render_instructions(self, framework_root: PathInput) -> bytes:
        framework = _preflight_framework(framework_root, self.binding)
        self.assert_writable_target(self.homes.state_root / "constitution.md")
        rendered, _inputs = _render_instructions(framework, self.homes.state_root)
        return rendered

    def stage_from_framework(self, framework_root: PathInput) -> "StagedWorkspace":
        framework = _preflight_framework(framework_root, self.binding)
        self.assert_exact_homes()
        _assert_runtime_replaceable(self.binding.workspace_root, self.homes.runtime_root)
        prior = _snapshot_managed(
            self.binding.workspace_root,
            self.homes.instructions_path,
            self.homes.runtime_root,
        )
        instructions, instruction_inputs = _render_instructions(
            framework, self.homes.state_root
        )

        stage_root = self.assert_writable_target(
            self.homes.temporary_root / ("workspace-layout-" + uuid.uuid4().hex)
        )
        candidate_root = stage_root / "candidate"
        instructions_candidate = candidate_root / ".hermes.md"
        runtime_candidate = candidate_root / "sage"
        created_directories: Tuple[pathlib.Path, ...] = ()
        try:
            created_directories = self._create_durable_homes()
            candidate_root.mkdir(parents=True)
            instructions_candidate.write_bytes(instructions)
            _copy_runtime(framework, runtime_candidate)
            _source_tree_preflight(runtime_candidate, runtime_candidate)
            managed_files = _candidate_manifest(
                self.binding.workspace_root,
                instructions_candidate,
                runtime_candidate,
            )
        except (OSError, LayoutError) as exc:
            rollback_errors = []
            if stage_root.exists() or stage_root.is_symlink():
                try:
                    if _is_link_or_reparse(stage_root):
                        raise LayoutError("staging root became a link or reparse point")
                    tuple(_regular_files(stage_root))
                    _remove_tree(stage_root)
                except (OSError, LayoutError) as rollback_exc:
                    rollback_errors.append("staging tree: %s" % rollback_exc)
            for path in reversed(created_directories):
                try:
                    path.rmdir()
                except OSError as rollback_exc:
                    rollback_errors.append("%s: %s" % (path, rollback_exc))
            if rollback_errors:
                raise LayoutError(
                    "workspace staging failed and zero-write rollback failed (%s): %s"
                    % ("; ".join(rollback_errors), exc)
                ) from exc
            if isinstance(exc, LayoutError):
                raise
            raise LayoutError("cannot stage bound workspace layout: %s" % exc) from exc

        candidate_paths = {entry.relative_path for entry in managed_files}
        stale = tuple(sorted(path for path in prior if path.startswith("sage/") and path not in candidate_paths))
        return StagedWorkspace(
            layout=self,
            staging_root=stage_root,
            instructions_candidate=instructions_candidate,
            runtime_candidate=runtime_candidate,
            managed_files=managed_files,
            stale_paths=stale,
            prior_snapshot=prior,
            instruction_inputs=instruction_inputs,
            framework_root=framework,
        )

    def refresh_from_framework(self, framework_root: PathInput) -> RefreshResult:
        staged = self.stage_from_framework(framework_root)
        try:
            result = staged.commit()
        except LayoutError as exc:
            if staged.recovery_required:
                raise
            try:
                staged.cleanup()
            except LayoutError as cleanup_exc:
                raise LayoutError(
                    "%s; candidate cleanup also failed: %s" % (exc, cleanup_exc)
                ) from exc
            raise
        else:
            staged.cleanup()
            return result


@dataclass
class StagedWorkspace:
    """A complete candidate that has not yet changed managed workspace bytes."""

    layout: WorkspaceLayout
    staging_root: pathlib.Path
    instructions_candidate: pathlib.Path
    runtime_candidate: pathlib.Path
    managed_files: Tuple[ManagedFile, ...]
    stale_paths: Tuple[str, ...]
    prior_snapshot: Mapping[str, str]
    instruction_inputs: Tuple[SourceFingerprint, ...]
    framework_root: pathlib.Path
    recovery_required: bool = False
    _recovery_paths: Tuple[pathlib.Path, ...] = ()
    _recovery_marker_identity: Optional[_LocalFileIdentity] = None
    _committed: bool = False

    @property
    def recovery_marker_path(self) -> pathlib.Path:
        """The sole marker home owned by this exact staging operation."""

        marker = self.staging_root / _RECOVERY_MARKER_NAME
        if not _same_path(marker.parent, self.staging_root):
            raise LayoutError("recovery marker is not an exact child of the staging root")
        if not _contains(self.layout.binding.workspace_root, marker):
            raise LayoutError("recovery marker is outside the frozen workspace binding")
        return marker

    @property
    def recovery_paths(self) -> Tuple[pathlib.Path, ...]:
        """Return recovery locations, freshly validating any marker identity."""

        paths = self._recovery_paths
        marker = self.recovery_marker_path
        if marker not in paths:
            return paths
        expected = self._recovery_marker_identity
        current = _single_link_local_file_identity(marker)
        if expected is None or current is None or current != expected:
            return tuple(path for path in paths if path != marker)
        return paths

    def _publish_recovery_marker(
        self,
    ) -> Tuple[pathlib.Path, _LocalFileIdentity]:
        """Atomically publish a recovery marker without opening its leaf path."""

        marker = self.recovery_marker_path
        parent = marker.parent

        # Validate the exact parent and leaf immediately before staging bytes.
        # ``lexists`` and ``lstat``-based checks do not follow a hostile leaf.
        self.layout.assert_writable_target(parent)
        if _is_link_or_reparse(parent):
            raise LayoutError("recovery marker parent cannot be a link or reparse point")
        if _path_lexists(marker):
            if _is_link_or_reparse(marker):
                raise LayoutError(
                    "recovery marker cannot replace a link, junction, or reparse point: %s"
                    % marker
                )
            raise LayoutError("recovery marker already exists: %s" % marker)
        self.layout.assert_writable_target(marker)

        temporary = parent / (
            ".%s.%s.tmp" % (_RECOVERY_MARKER_NAME, uuid.uuid4().hex)
        )
        self.layout.assert_writable_target(temporary)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOINHERIT", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(os.fspath(temporary), flags, 0o600)
        try:
            remaining = memoryview(_RECOVERY_MARKER_BYTES)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("recovery marker write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

        # Revalidate after writing the temporary file.  A concurrent leaf
        # insertion either makes this check fail or is atomically replaced as
        # a directory entry by os.replace; its target is never opened/followed.
        self.layout.assert_writable_target(parent)
        if _is_link_or_reparse(parent):
            raise LayoutError("recovery marker parent became a link or reparse point")
        if _path_lexists(marker):
            if _is_link_or_reparse(marker):
                raise LayoutError(
                    "recovery marker became a link, junction, or reparse point: %s"
                    % marker
                )
            raise LayoutError("recovery marker appeared concurrently: %s" % marker)
        self.layout.assert_writable_target(marker)
        candidate_identity = _single_link_local_file_identity(temporary)
        if candidate_identity is None:
            raise LayoutError(
                "staged recovery marker is not a single-link regular local file"
            )
        os.replace(os.fspath(temporary), os.fspath(marker))

        published_identity = _single_link_local_file_identity(marker)
        if published_identity is None or published_identity != candidate_identity:
            raise LayoutError(
                "published recovery marker does not match its staged single-link identity"
            )
        # Do not return a path based on an earlier stat.  A second no-follow
        # snapshot binds the returned marker to the same filesystem identity.
        return_identity = _single_link_local_file_identity(marker)
        if return_identity is None or return_identity != published_identity:
            raise LayoutError("published recovery marker identity changed before return")
        return marker, return_identity

    def _assert_current(self) -> None:
        if self._committed:
            raise LayoutError("staged workspace candidate has already been committed")
        expected_candidate_root = self.staging_root / "candidate"
        expected_instructions = expected_candidate_root / ".hermes.md"
        expected_runtime = expected_candidate_root / "sage"
        if not _same_path(self.instructions_candidate, expected_instructions):
            raise LayoutError("instructions candidate is not in its exact staging home")
        if not _same_path(self.runtime_candidate, expected_runtime):
            raise LayoutError("runtime candidate is not in its exact staging home")
        self.layout.assert_writable_target(self.staging_root)
        self.layout.assert_writable_target(self.instructions_candidate)
        self.layout.assert_writable_target(self.runtime_candidate)
        if _is_link_or_reparse(self.staging_root):
            raise LayoutError("staging root cannot be a link or reparse point")
        if not self.instructions_candidate.is_file() or not self.runtime_candidate.is_dir():
            raise LayoutError("staged workspace candidate is incomplete")

    def commit(self) -> RefreshResult:
        self._assert_current()
        homes = self.layout.homes
        self.layout.assert_exact_homes()
        _preflight_framework(self.framework_root, self.layout.binding)
        current_instruction_inputs = _instruction_input_fingerprints(
            self.framework_root, homes.state_root
        )
        if current_instruction_inputs != self.instruction_inputs:
            raise LayoutError("canonical instruction inputs changed after staging")
        _source_tree_preflight(self.runtime_candidate, self.runtime_candidate)
        current_candidate = _candidate_manifest(
            self.layout.binding.workspace_root,
            self.instructions_candidate,
            self.runtime_candidate,
        )
        if current_candidate != self.managed_files:
            raise LayoutError("staged workspace candidate bytes changed after validation")
        _assert_runtime_replaceable(self.layout.binding.workspace_root, homes.runtime_root)
        current = _snapshot_managed(
            self.layout.binding.workspace_root,
            homes.instructions_path,
            homes.runtime_root,
        )
        if dict(current) != dict(self.prior_snapshot):
            raise LayoutError("managed workspace bytes changed after staging; refusing replacement")

        backup_root = self.staging_root / "backup"
        backup_runtime = backup_root / "sage"
        backup_instructions = backup_root / ".hermes.md"
        failed_runtime = self.staging_root / "failed-sage"
        failed_instructions = self.staging_root / "failed-hermes.md"
        runtime_backed_up = False
        runtime_installed = False
        instructions_backed_up = False
        instructions_installed = False
        try:
            backup_root.mkdir()
            if homes.runtime_root.exists():
                os.replace(os.fspath(homes.runtime_root), os.fspath(backup_runtime))
                runtime_backed_up = True
            if _candidate_manifest(
                self.layout.binding.workspace_root,
                self.instructions_candidate,
                self.runtime_candidate,
            ) != self.managed_files:
                raise LayoutError(
                    "staged workspace candidate changed immediately before publication"
                )
            os.replace(os.fspath(self.runtime_candidate), os.fspath(homes.runtime_root))
            runtime_installed = True

            if homes.instructions_path.exists():
                os.replace(os.fspath(homes.instructions_path), os.fspath(backup_instructions))
                instructions_backed_up = True
            if _candidate_manifest(
                self.layout.binding.workspace_root,
                self.instructions_candidate,
                homes.runtime_root,
            ) != self.managed_files:
                raise LayoutError(
                    "staged workspace candidate changed before instructions publication"
                )
            os.replace(
                os.fspath(self.instructions_candidate),
                os.fspath(homes.instructions_path),
            )
            instructions_installed = True
            published_identity = _candidate_manifest_identities(
                homes.instructions_path,
                homes.runtime_root,
            )
            if _candidate_manifest(
                self.layout.binding.workspace_root,
                homes.instructions_path,
                homes.runtime_root,
            ) != self.managed_files:
                raise LayoutError(
                    "published workspace candidate identity or bytes changed"
                )
            if (
                _candidate_manifest_identities(
                    homes.instructions_path,
                    homes.runtime_root,
                )
                != published_identity
            ):
                raise LayoutError(
                    "published workspace candidate identity changed before return"
                )
        except (OSError, LayoutError) as exc:
            rollback_errors: List[str] = []
            try:
                if instructions_installed and homes.instructions_path.exists():
                    os.replace(os.fspath(homes.instructions_path), os.fspath(failed_instructions))
                if instructions_backed_up and backup_instructions.exists():
                    os.replace(os.fspath(backup_instructions), os.fspath(homes.instructions_path))
            except OSError as rollback_exc:
                rollback_errors.append("instructions: %s" % rollback_exc)
            try:
                if runtime_installed and homes.runtime_root.exists():
                    os.replace(os.fspath(homes.runtime_root), os.fspath(failed_runtime))
                if runtime_backed_up and backup_runtime.exists():
                    os.replace(os.fspath(backup_runtime), os.fspath(homes.runtime_root))
            except OSError as rollback_exc:
                rollback_errors.append("runtime: %s" % rollback_exc)
            detail = "workspace commit failed and prior managed bytes were restored: %s" % exc
            if rollback_errors:
                self.recovery_required = True
                recovery_marker = None
                recovery_marker_identity = None
                try:
                    recovery_marker, recovery_marker_identity = (
                        self._publish_recovery_marker()
                    )
                except (OSError, LayoutError) as marker_exc:
                    rollback_errors.append("recovery marker: %s" % marker_exc)
                candidates: Tuple[pathlib.Path, ...] = (
                    backup_runtime,
                    backup_instructions,
                    failed_runtime,
                    failed_instructions,
                    self.staging_root,
                )
                visible_paths: List[pathlib.Path] = []
                for path in candidates:
                    if not _path_lexists(path):
                        continue
                    try:
                        self.layout.assert_writable_target(path)
                        if _is_link_or_reparse(path):
                            raise LayoutError(
                                "recovery artifact is a link or reparse point: %s" % path
                            )
                    except LayoutError as path_exc:
                        rollback_errors.append("recovery path: %s" % path_exc)
                        continue
                    visible_paths.append(path)
                if (
                    recovery_marker is not None
                    and recovery_marker_identity is not None
                ):
                    try:
                        if not _same_path(
                            recovery_marker, self.recovery_marker_path
                        ):
                            raise LayoutError(
                                "recovery marker left its exact staging home"
                            )
                        self.layout.assert_writable_target(recovery_marker)
                        report_identity = _single_link_local_file_identity(
                            recovery_marker
                        )
                        if (
                            report_identity is None
                            or report_identity != recovery_marker_identity
                        ):
                            raise LayoutError(
                                "recovery marker identity changed before reporting"
                            )
                    except LayoutError as path_exc:
                        rollback_errors.append("recovery marker report: %s" % path_exc)
                    else:
                        # ``report_identity`` is the fresh snapshot associated
                        # with this reported path; no earlier stat is trusted.
                        self._recovery_marker_identity = report_identity
                        visible_paths.append(recovery_marker)
                self._recovery_paths = tuple(visible_paths)
                detail = (
                    "RECOVERY REQUIRED: workspace commit failed and rollback also failed "
                    "(%s): %s. Preserve staging at %s; prior bytes may exist under backup/."
                    % ("; ".join(rollback_errors), exc, self.staging_root)
                )
            raise LayoutError(detail) from exc

        self._committed = True
        return RefreshResult(
            managed_files=self.managed_files,
            stale_paths=self.stale_paths,
            instruction_inputs=self.instruction_inputs,
        )

    def cleanup(self) -> None:
        recovery_marker = self.recovery_marker_path
        if self.recovery_required or _path_lexists(recovery_marker):
            raise LayoutError(
                "recovery is required; refusing to delete preserved staging at %s"
                % self.staging_root
            )
        if not self.staging_root.exists() and not self.staging_root.is_symlink():
            return
        self.layout.assert_writable_target(self.staging_root)
        if _is_link_or_reparse(self.staging_root):
            raise LayoutError("refusing to clean a linked or reparsed staging root")
        try:
            # Refuse cleanup if a concurrently inserted link could redirect a
            # recursive removal outside this operation's staging tree.
            tuple(_regular_files(self.staging_root))
            _remove_tree(self.staging_root)
        except (OSError, LayoutError) as exc:
            raise LayoutError("cannot clean workspace staging root %s: %s" % (self.staging_root, exc)) from exc


__all__ = [
    "InitiativeHomes",
    "LayoutError",
    "ManagedFile",
    "RefreshResult",
    "SourceFingerprint",
    "StagedWorkspace",
    "WorkspaceHomes",
    "WorkspaceLayout",
]
