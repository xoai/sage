#!/usr/bin/env python3
"""Immutable, explicit path authority for one Hermes profile installation.

This module deliberately has no discovery path.  It never reads HOME, the
process working directory, an ancestor project, or the Hermes profiles
directory.  Callers must supply one collection, profile, and workspace, and
must preserve the returned binding through every operation.
"""

from __future__ import annotations

import os
import pathlib
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Dict, Tuple, Union


PathInput = Union[str, os.PathLike]


class BindingError(ValueError):
    """The supplied Hermes profile binding is absent, ambiguous, or unsafe."""


_PATH_FIELDS = (
    "collection_root",
    "profile_root",
    "workspace_root",
    "config_path",
    "hooks_root",
    "plugin_root",
    "skills_root",
    "state_root",
    "memory_root",
    "memory_db_path",
    "receipt_path",
    "runs_root",
    "pack_lock_path",
)
_FULL_MAPPING_FIELDS = ("profile_id",) + _PATH_FIELDS
_CONFIG_MAPPING_FIELDS = (
    "profile_id",
    "workspace_root",
    "state_root",
    "memory_root",
    "receipt_path",
)
_PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_WINDOWS_REPARSE_POINT = 0x400
_RESOLVE_ATTEMPTS = 8


def _path_key(path: pathlib.Path) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def _path_spelling(path: pathlib.Path) -> str:
    return os.path.normpath(os.fspath(path))


def _same_exact_path(left: pathlib.Path, right: pathlib.Path) -> bool:
    return _path_spelling(left) == _path_spelling(right)


def _same_path(left: pathlib.Path, right: pathlib.Path) -> bool:
    return _path_key(left) == _path_key(right)


def _contains(root: pathlib.Path, target: pathlib.Path) -> bool:
    try:
        common = os.path.commonpath((_path_key(root), _path_key(target)))
    except ValueError:
        return False
    return common == _path_key(root)


def _has_windows_namespace_prefix(native: str) -> bool:
    normalized = native.replace("/", "\\").casefold()
    return normalized.startswith(("\\\\?\\", "\\\\.\\", "\\??\\"))


def _normalize_resolver_path(path: pathlib.Path) -> pathlib.Path:
    """Remove a resolver-added Windows namespace prefix, never a user input."""

    native = os.fspath(path)
    if os.name != "nt":
        return path
    folded = native.casefold()
    if folded.startswith("\\\\?\\unc\\"):
        return pathlib.Path("\\\\" + native[8:])
    if folded.startswith("\\\\?\\"):
        return pathlib.Path(native[4:])
    return path


def _resolve_for_validation(
    path: pathlib.Path, label: str, *, strict: bool
) -> pathlib.Path:
    """Resolve a path while tolerating Windows first-creation namespace churn."""

    last_error = None
    for _ in range(_RESOLVE_ATTEMPTS):
        try:
            resolved = _normalize_resolver_path(path.resolve(strict=strict))
        except (OSError, RuntimeError) as exc:
            last_error = exc
            if strict:
                break
            continue
        native = os.fspath(resolved).replace("/", "\\").casefold()
        if os.name == "nt" and "\\$extend\\$deleted\\" in native:
            last_error = OSError("Windows returned a transient deleted-path identity")
            continue
        return resolved

    if not strict:
        try:
            if not path.exists() and not path.is_symlink():
                return path
        except OSError:
            pass
    raise BindingError("%s cannot be canonicalized: %s" % (label, last_error))


def _reject_existing_file_alias(path: pathlib.Path, label: str) -> None:
    """Reject reparse aliases and multi-name file identities before authority."""

    try:
        metadata = os.stat(os.fspath(path), follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise BindingError("%s cannot be inspected safely: %s" % (label, exc))
    if (
        stat.S_ISLNK(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_POINT
    ):
        raise BindingError("%s cannot be a link or reparse point" % label)
    if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink > 1:
        raise BindingError(
            "%s cannot be a hardlink (link count: %d)" % (label, metadata.st_nlink)
        )


def _require_mapping(value: Any, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise BindingError("%s must be a mapping" % label)
    return value


def _require_fields(mapping: Mapping, fields: Tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in mapping]
    if missing:
        raise BindingError(
            "%s is missing required binding field(s): %s"
            % (label, ", ".join(missing))
        )


def _reject_unexpected_fields(
    mapping: Mapping, fields: Tuple[str, ...], label: str
) -> None:
    unexpected = sorted(str(key) for key in mapping if key not in fields)
    if unexpected:
        raise BindingError(
            "%s contains unexpected binding field(s): %s"
            % (label, ", ".join(unexpected))
        )


def _path_from_value(value: Any, label: str) -> pathlib.Path:
    if value is None or isinstance(value, bool):
        raise BindingError("%s must be an explicit absolute path" % label)
    try:
        native = os.fspath(value)
    except TypeError:
        raise BindingError("%s must be an explicit absolute path" % label)
    if not isinstance(native, str) or not native or "\x00" in native:
        raise BindingError("%s must be an explicit absolute path" % label)
    if _has_windows_namespace_prefix(native):
        raise BindingError(
            "%s must use one canonical path without a Windows namespace alias"
            % label
        )

    path = pathlib.Path(native)
    if not path.is_absolute():
        raise BindingError("%s must be an explicit absolute path" % label)
    if ".." in path.parts:
        raise BindingError("%s must be canonical and cannot contain '..'" % label)
    return path


def _explicit_directory(value: Any, label: str) -> pathlib.Path:
    path = _path_from_value(value, label)
    try:
        canonical = _resolve_for_validation(path, label, strict=True)
    except BindingError as exc:
        raise BindingError(
            "%s does not resolve to an existing directory: %s" % (label, exc)
        )
    if not canonical.is_dir():
        raise BindingError("%s does not resolve to an existing directory" % label)
    if not _same_exact_path(path, canonical):
        raise BindingError(
            "%s is not canonical (resolved path: %s)" % (label, canonical)
        )
    return canonical


def _canonical_mapping_path(value: Any, label: str) -> pathlib.Path:
    path = _path_from_value(value, label)
    canonical = _resolve_for_validation(path, label, strict=False)
    if not _same_exact_path(path, canonical):
        raise BindingError(
            "%s is not canonical (resolved path: %s)" % (label, canonical)
        )
    return canonical


def _canonical_target(
    owner: pathlib.Path,
    target: pathlib.Path,
    label: str,
    *,
    file_target: bool = False,
) -> pathlib.Path:
    canonical = _resolve_for_validation(target, label, strict=False)
    if not _same_exact_path(target, canonical):
        raise BindingError(
            "%s must be the exact canonical target and cannot be an alias or "
            "reparse point (resolved path: %s)" % (label, canonical)
        )
    if not _contains(owner, canonical):
        raise BindingError(
            "%s escapes its bound root %s through a link or reparse point: %s"
            % (label, owner, canonical)
        )
    if file_target:
        _reject_existing_file_alias(canonical, label)
    return canonical


def _profile_id(value: Any) -> str:
    if not isinstance(value, str) or not _PROFILE_ID.fullmatch(value):
        raise BindingError(
            "profile_id must match the CLI profile contract "
            "^[a-z0-9][a-z0-9_-]{0,63}$"
        )
    return value


def _binding_mapping(value: Any) -> Dict[str, str]:
    result = {"profile_id": value.profile_id}
    for field in _PATH_FIELDS:
        result[field] = os.fspath(getattr(value, field))
    return result


def _config_binding_mapping(value: Any) -> Dict[str, str]:
    return {
        "profile_id": value.profile_id,
        "workspace_root": os.fspath(value.workspace_root),
        "state_root": os.fspath(value.state_root),
        "memory_root": os.fspath(value.memory_root),
        "receipt_path": os.fspath(value.receipt_path),
    }


def _bindings_match(left: Any, right: Any) -> bool:
    if left.profile_id != right.profile_id:
        return False
    return all(
        _same_exact_path(getattr(left, field), getattr(right, field))
        for field in _PATH_FIELDS
    )


@dataclass(frozen=True, eq=False)
class ParsedProfileBinding:
    """Immutable validated bytes that deliberately carry no runtime authority."""

    profile_id: str
    collection_root: pathlib.Path
    profile_root: pathlib.Path
    workspace_root: pathlib.Path
    config_path: pathlib.Path
    hooks_root: pathlib.Path
    plugin_root: pathlib.Path
    skills_root: pathlib.Path
    state_root: pathlib.Path
    memory_root: pathlib.Path
    memory_db_path: pathlib.Path
    receipt_path: pathlib.Path
    runs_root: pathlib.Path
    pack_lock_path: pathlib.Path

    @classmethod
    def _from_validated(cls, value: Any) -> "ParsedProfileBinding":
        return cls(
            **{
                field: getattr(value, field)
                for field in ("profile_id",) + _PATH_FIELDS
            }
        )

    def __eq__(self, other: Any) -> bool:
        try:
            return _bindings_match(self, other)
        except (AttributeError, TypeError):
            return False

    def to_mapping(self) -> Dict[str, str]:
        return _binding_mapping(self)

    def to_config_mapping(self) -> Dict[str, str]:
        return _config_binding_mapping(self)

    def assert_same(self, value: Any) -> "ParsedProfileBinding":
        raise BindingError(
            "parsed binding is not authorized runtime authority; "
            "use ProfileBinding.from_authorities"
        )

    def run_journal_path(self, operation_id: str) -> pathlib.Path:
        raise BindingError(
            "parsed binding is not authorized runtime authority; "
            "use ProfileBinding.from_authorities"
        )


@dataclass(frozen=True, init=False)
class ProfileBinding:
    """Canonical authority for exactly one Hermes profile and workspace."""

    profile_id: str
    collection_root: pathlib.Path
    profile_root: pathlib.Path
    workspace_root: pathlib.Path
    config_path: pathlib.Path
    hooks_root: pathlib.Path
    plugin_root: pathlib.Path
    skills_root: pathlib.Path
    state_root: pathlib.Path
    memory_root: pathlib.Path
    memory_db_path: pathlib.Path
    receipt_path: pathlib.Path
    runs_root: pathlib.Path
    pack_lock_path: pathlib.Path

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise BindingError(
            "ProfileBinding must be constructed with from_explicit, "
            "or reconstructed with from_authorities"
        )

    @classmethod
    def from_explicit(
        cls,
        *,
        collection_root: PathInput,
        profile_id: str,
        profile_root: PathInput,
        workspace_root: PathInput,
    ) -> "ProfileBinding":
        """Freeze one binding without discovering or creating any path."""

        collection = _explicit_directory(collection_root, "collection_root")
        identity = _profile_id(profile_id)
        profile = _explicit_directory(profile_root, "profile_root")
        workspace = _explicit_directory(workspace_root, "workspace_root")

        expected_profile = _explicit_directory(
            collection / "profiles" / identity,
            "expected profile_root",
        )
        if not _same_exact_path(profile, expected_profile):
            raise BindingError(
                "profile_root must be the exact collection_root/profiles/profile_id: "
                "expected %s, received %s" % (expected_profile, profile)
            )

        expected_workspace = _explicit_directory(
            profile / "workspace",
            "expected workspace_root",
        )
        if not _same_exact_path(workspace, expected_workspace):
            raise BindingError(
                "workspace_root must be exactly profile_root/workspace: "
                "expected %s, received %s" % (expected_workspace, workspace)
            )

        config = _canonical_target(
            profile,
            profile / "config.yaml",
            "config_path",
            file_target=True,
        )
        hooks = _canonical_target(profile, profile / "hooks", "hooks_root")
        plugin = _canonical_target(
            profile, profile / "plugins" / "sage", "plugin_root"
        )
        skills = _canonical_target(profile, profile / "skills", "skills_root")

        state = _canonical_target(workspace, workspace / ".sage", "state_root")
        memory = _canonical_target(
            workspace, workspace / ".sage-memory", "memory_root"
        )
        memory_db = _canonical_target(
            memory,
            memory / "memory.db",
            "memory_db_path",
            file_target=True,
        )
        receipt = _canonical_target(
            state,
            state / "receipts" / "install.json",
            "receipt_path",
            file_target=True,
        )
        runs = _canonical_target(
            state, state / "receipts" / "runs", "runs_root"
        )
        pack_lock = _canonical_target(
            state,
            state / "packs.lock",
            "pack_lock_path",
            file_target=True,
        )

        values = dict(
            profile_id=identity,
            collection_root=collection,
            profile_root=profile,
            workspace_root=workspace,
            config_path=config,
            hooks_root=hooks,
            plugin_root=plugin,
            skills_root=skills,
            state_root=state,
            memory_root=memory,
            memory_db_path=memory_db,
            receipt_path=receipt,
            runs_root=runs,
            pack_lock_path=pack_lock,
        )
        instance = object.__new__(cls)
        for field in ("profile_id",) + _PATH_FIELDS:
            object.__setattr__(instance, field, values[field])
        return instance

    @classmethod
    def from_mapping(cls, value: Any) -> ParsedProfileBinding:
        """Validate one complete mapping without granting runtime authority.

        Runtime startup must use :meth:`from_authorities` so config and receipt
        are both present and agree.  This lower-level parser exists for receipt
        creation, migration diagnostics, and exact comparisons.
        """

        mapping = _require_mapping(value, "binding mapping")
        _require_fields(mapping, _FULL_MAPPING_FIELDS, "binding mapping")
        _reject_unexpected_fields(mapping, _FULL_MAPPING_FIELDS, "binding mapping")

        binding = cls.from_explicit(
            collection_root=mapping["collection_root"],
            profile_id=mapping["profile_id"],
            profile_root=mapping["profile_root"],
            workspace_root=mapping["workspace_root"],
        )
        binding._assert_full_mapping(mapping)
        return ParsedProfileBinding._from_validated(binding)

    @classmethod
    def from_receipt(cls, value: Any) -> ParsedProfileBinding:
        """Validate a receipt binding without granting runtime authority.

        A receipt alone is not sufficient for CLI/Gateway startup.  Use
        :meth:`from_authorities` to pair it with the selected profile config.
        """

        receipt = _require_mapping(value, "install receipt")
        if "binding" not in receipt:
            raise BindingError("install receipt is missing required binding field")
        return cls.from_mapping(receipt["binding"])

    @classmethod
    def from_config_mapping(
        cls,
        value: Any,
        *,
        collection_root: PathInput,
        profile_root: PathInput,
    ) -> ParsedProfileBinding:
        """Validate one config block without granting runtime authority.

        A config block alone is not sufficient for CLI/Gateway startup.  Use
        :meth:`from_authorities` to pair it with the install receipt.
        """

        mapping = _require_mapping(value, "config binding")
        _require_fields(mapping, _CONFIG_MAPPING_FIELDS, "config binding")
        _reject_unexpected_fields(mapping, _CONFIG_MAPPING_FIELDS, "config binding")
        binding = cls.from_explicit(
            collection_root=collection_root,
            profile_id=mapping["profile_id"],
            profile_root=profile_root,
            workspace_root=mapping["workspace_root"],
        )
        binding._assert_config_mapping(mapping)
        return ParsedProfileBinding._from_validated(binding)

    @classmethod
    def from_authorities(
        cls,
        *,
        receipt: Any,
        config_binding: Any,
        collection_root: PathInput,
        profile_root: PathInput,
    ) -> "ProfileBinding":
        """Authorize runtime state only from matching receipt and config data."""

        receipt_binding = cls.from_receipt(receipt)
        try:
            config = cls.from_config_mapping(
                config_binding,
                collection_root=collection_root,
                profile_root=profile_root,
            )
            if not _bindings_match(receipt_binding, config):
                raise BindingError("receipt and config name different bindings")
        except BindingError as exc:
            raise BindingError(
                "receipt and config authorities do not match: %s" % exc
            ) from exc
        authorized = cls.from_explicit(
            collection_root=receipt_binding.collection_root,
            profile_id=receipt_binding.profile_id,
            profile_root=receipt_binding.profile_root,
            workspace_root=receipt_binding.workspace_root,
        )
        authorized._assert_full_mapping(receipt_binding.to_mapping())
        authorized._assert_config_mapping(config.to_config_mapping())
        return authorized

    def to_mapping(self) -> Dict[str, str]:
        """Return the complete receipt-safe binding using native paths."""

        return _binding_mapping(self)

    def to_config_mapping(self) -> Dict[str, str]:
        """Return the exact Sage-owned profile config binding block."""

        return _config_binding_mapping(self)

    def _assert_full_mapping(self, mapping: Mapping) -> None:
        if mapping["profile_id"] != self.profile_id:
            raise BindingError("profile_id does not match the frozen binding")
        for field in _PATH_FIELDS:
            supplied = _canonical_mapping_path(mapping[field], field)
            expected = getattr(self, field)
            if not _same_exact_path(supplied, expected):
                raise BindingError(
                    "%s does not match the frozen binding: expected %s, received %s"
                    % (field, expected, supplied)
                )

    def _assert_config_mapping(self, mapping: Mapping) -> None:
        if mapping["profile_id"] != self.profile_id:
            raise BindingError("profile_id does not match the frozen binding")
        for field in _CONFIG_MAPPING_FIELDS[1:]:
            supplied = _canonical_mapping_path(mapping[field], field)
            expected = getattr(self, field)
            if not _same_exact_path(supplied, expected):
                raise BindingError(
                    "%s does not match the frozen binding: expected %s, received %s"
                    % (field, expected, supplied)
                )

    def assert_same(self, value: Any) -> "ProfileBinding":
        """Compare exact bindings; this lower-level helper grants no authority."""

        if isinstance(value, ProfileBinding):
            candidate = value
        elif isinstance(value, ParsedProfileBinding):
            candidate = value
        else:
            mapping = _require_mapping(value, "binding comparison")
            if "binding" in mapping:
                candidate = self.from_receipt(mapping)
            elif all(field in mapping for field in _FULL_MAPPING_FIELDS):
                candidate = self.from_mapping(mapping)
            else:
                _require_fields(mapping, _CONFIG_MAPPING_FIELDS, "config binding")
                _reject_unexpected_fields(
                    mapping, _CONFIG_MAPPING_FIELDS, "config binding"
                )
                self._assert_config_mapping(mapping)
                return self

        if not _bindings_match(candidate, self):
            raise BindingError("received a different Hermes profile binding")
        return self

    def run_journal_path(self, operation_id: str) -> pathlib.Path:
        """Return one contained journal path without creating it."""

        if (
            not isinstance(operation_id, str)
            or not _OPERATION_ID.fullmatch(operation_id)
            or operation_id in (".", "..")
            or operation_id.endswith(".json")
        ):
            raise BindingError("operation_id must be one safe filename component")
        return _canonical_target(
            self.runs_root,
            self.runs_root / (operation_id + ".json"),
            "run_journal_path",
            file_target=True,
        )


__all__ = ["BindingError", "ParsedProfileBinding", "ProfileBinding"]
