#!/usr/bin/env python3
"""Strict, profile-bound install receipts and atomic operation journals.

The installer is the only intended writer.  Every public read or write starts
from an already frozen :class:`ProfileBinding`; this module never discovers a
profile from HOME, process CWD, ancestors, or sibling profile enumeration.
"""

from __future__ import annotations

import datetime
import errno
import hashlib
import json
import math
import os
import pathlib
import re
import tempfile
import threading
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

if os.name == "nt":
    import msvcrt
else:
    import fcntl

try:  # Package import in an installed adapter.
    from .profile_binding import BindingError, ProfileBinding
except ImportError:  # Direct path import in validators and bootstrap code.
    from profile_binding import BindingError, ProfileBinding


INSTALL_RECEIPT_SCHEMA = "sage.hermes.install-receipt"
RUN_JOURNAL_SCHEMA = "sage.hermes.run-journal"
SCHEMA_VERSION = 1

_INSTALL_FIELDS = (
    "schema",
    "schema_version",
    "binding",
    "source",
    "managed_targets",
    "config_records",
    "allowlist_records",
    "semantic_hash",
    "timestamps",
)
_JOURNAL_FIELDS = (
    "schema",
    "schema_version",
    "operation_id",
    "operation",
    "status",
    "binding",
    "source",
    "previous",
    "plan",
    "result",
    "semantic_hash",
    "timestamps",
)
_SOURCE_FIELDS = ("version", "commit")
_TARGET_FIELDS = ("owner", "path")
_MANAGED_TARGET_FIELDS = _TARGET_FIELDS + ("sha256",)
_PREVIOUS_FIELDS = (
    "managed_targets",
    "config_records",
    "allowlist_records",
)
_PLAN_FIELDS = ("writes", "removals")
_RECEIPT_TIMESTAMP_FIELDS = ("created_at", "updated_at")
_JOURNAL_TIMESTAMP_FIELDS = ("started_at", "completed_at")
_CONFIG_RECORD_FIELDS = ("event", "command", "matcher", "fail_closed")
_ALLOWLIST_RECORD_FIELDS = ("event", "command")
_HOOK_EVENTS = frozenset(("on_session_start", "pre_tool_call", "post_tool_call"))
_HOOK_MATCHERS = frozenset(
    (
        "terminal",
        "write_file|patch",
        "write_file|patch|terminal",
    )
)
_SOURCE_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]{0,127}$")
_SOURCE_COMMIT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?Z$"
)
_OPERATIONS = frozenset(("install", "update", "remove"))
_STAT_REPARSE_POINT = getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
_PROFILE_TRANSACTION_GUARD = threading.Lock()
_PROFILE_TRANSACTION_OWNERS: Dict[str, Tuple[int, int]] = {}


class ReceiptError(ValueError):
    """Receipt or journal data is absent, unsafe, corrupt, or inconsistent."""


def _require_mapping(value: Any, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ReceiptError("%s must be a JSON object" % label)
    return value


def _require_exact_fields(mapping: Mapping, fields: Tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in mapping]
    if missing:
        raise ReceiptError(
            "%s is missing required field(s): %s" % (label, ", ".join(missing))
        )
    unexpected = sorted(str(key) for key in mapping if key not in fields)
    if unexpected:
        raise ReceiptError(
            "%s contains unexpected field(s): %s"
            % (label, ", ".join(unexpected))
        )


def _validate_json_value(value: Any, label: str) -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ReceiptError("%s must contain only finite JSON values" % label)
        return value
    if isinstance(value, list):
        return [
            _validate_json_value(item, "%s[%d]" % (label, index))
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ReceiptError("%s must use JSON string object keys" % label)
            result[key] = _validate_json_value(item, "%s.%s" % (label, key))
        return result
    raise ReceiptError("%s must contain only exact JSON values" % label)


def _record_sequence(value: Any, label: str, *, require_list: bool) -> List[Any]:
    if require_list:
        accepted = isinstance(value, list)
    else:
        accepted = isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        )
    if not accepted:
        raise ReceiptError("%s must be a JSON array" % label)
    return list(value)


def _hook_event(value: Any, label: str) -> str:
    if not isinstance(value, str) or value not in _HOOK_EVENTS:
        raise ReceiptError(
            "%s must be exactly on_session_start, pre_tool_call, or post_tool_call"
            % label
        )
    return value


def _hook_command(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\r" in value
        or "\n" in value
    ):
        raise ReceiptError("%s must be one nonempty command string" % label)
    return value


def _config_records(
    value: Any, label: str, *, require_list: bool
) -> Tuple[Dict[str, Any], ...]:
    records = []
    for index, item in enumerate(
        _record_sequence(value, label, require_list=require_list)
    ):
        item_label = "%s[%d]" % (label, index)
        mapping = _require_mapping(item, item_label)
        fields = _CONFIG_RECORD_FIELDS
        if "file_preview_patterns" in mapping:
            fields += ("file_preview_patterns",)
        _require_exact_fields(mapping, fields, item_label)
        event = _hook_event(mapping["event"], item_label + ".event")
        command = _hook_command(mapping["command"], item_label + ".command")
        matcher = mapping["matcher"]
        if event == "on_session_start" and matcher is not None:
            raise ReceiptError(
                "%s.matcher must be null for on_session_start" % item_label
            )
        if event != "on_session_start" and (
            not isinstance(matcher, str) or matcher not in _HOOK_MATCHERS
        ):
            raise ReceiptError(
                "%s.matcher is not one of the supported Sage hook matchers"
                % item_label
            )
        fail_closed = mapping["fail_closed"]
        if type(fail_closed) is not bool:
            raise ReceiptError("%s.fail_closed must be a JSON boolean" % item_label)
        expected_fail_closed = event == "pre_tool_call"
        if fail_closed is not expected_fail_closed:
            raise ReceiptError(
                "%s.fail_closed must be %s for %s"
                % (item_label, str(expected_fail_closed).lower(), event)
            )
        records.append(
            {
                "event": event,
                "command": command,
                "matcher": matcher,
                "fail_closed": fail_closed,
            }
        )
        if "file_preview_patterns" in mapping:
            patterns = mapping["file_preview_patterns"]
            if (not isinstance(patterns, list) or not patterns or
                    any(not isinstance(pattern, str) or not pattern.strip() for pattern in patterns)):
                raise ReceiptError("%s.file_preview_patterns must be a nonempty string array" % item_label)
            records[-1]["file_preview_patterns"] = list(patterns)

    identities = [_canonical_bytes(record) for record in records]
    if len(identities) != len(set(identities)):
        raise ReceiptError("%s contains a duplicate config record" % label)
    return tuple(records)


def _allowlist_records(
    value: Any, label: str, *, require_list: bool
) -> Tuple[Dict[str, str], ...]:
    records = []
    for index, item in enumerate(
        _record_sequence(value, label, require_list=require_list)
    ):
        item_label = "%s[%d]" % (label, index)
        mapping = _require_mapping(item, item_label)
        _require_exact_fields(mapping, _ALLOWLIST_RECORD_FIELDS, item_label)
        records.append(
            {
                "event": _hook_event(mapping["event"], item_label + ".event"),
                "command": _hook_command(
                    mapping["command"], item_label + ".command"
                ),
            }
        )

    identities = [_canonical_bytes(record) for record in records]
    if len(identities) != len(set(identities)):
        raise ReceiptError("%s contains a duplicate allowlist record" % label)
    return tuple(records)


def _mapping_copy(value: Mapping, label: str) -> Dict[str, Any]:
    checked = _validate_json_value(value, label)
    if not isinstance(checked, dict):
        raise ReceiptError("%s must be a JSON object" % label)
    return checked


def _source(version: Any, commit: Any) -> Tuple[str, str]:
    if not isinstance(version, str) or not _SOURCE_VERSION.fullmatch(version):
        raise ReceiptError("source version must be one explicit version token")
    if not isinstance(commit, str) or not _SOURCE_COMMIT.fullmatch(commit):
        raise ReceiptError("source commit must be a lowercase 40- or 64-hex commit")
    return version, commit


def _source_from_mapping(value: Any) -> Tuple[str, str]:
    mapping = _require_mapping(value, "source")
    _require_exact_fields(mapping, _SOURCE_FIELDS, "source")
    return _source(mapping["version"], mapping["commit"])


def _timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise ReceiptError("%s must be an ISO-8601 UTC timestamp ending in Z" % label)
    try:
        parsed = datetime.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ReceiptError("%s is not a valid calendar timestamp" % label) from exc
    if parsed.tzinfo != datetime.timezone.utc:
        raise ReceiptError("%s must be UTC" % label)
    return value


def _now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _path_key(path: pathlib.Path) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def _same_path(left: pathlib.Path, right: pathlib.Path) -> bool:
    return _path_key(left) == _path_key(right)


def _contains(root: pathlib.Path, target: pathlib.Path) -> bool:
    try:
        return os.path.commonpath((_path_key(root), _path_key(target))) == _path_key(
            root
        )
    except ValueError:
        return False


def _is_reparse(path: pathlib.Path) -> bool:
    try:
        stat_result = os.stat(os.fspath(path), follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ReceiptError("cannot inspect receipt path %s: %s" % (path, exc)) from exc
    return bool(
        path.is_symlink()
        or getattr(stat_result, "st_file_attributes", 0) & _STAT_REPARSE_POINT
    )


def _validated_binding(value: Any) -> ProfileBinding:
    if not isinstance(value, ProfileBinding):
        raise ReceiptError("binding must be a validated ProfileBinding")
    try:
        current = ProfileBinding.from_mapping(value.to_mapping())
        value.assert_same(current)
    except BindingError as exc:
        raise ReceiptError("Hermes profile binding is not canonical: %s" % exc) from exc
    return value


def _validate_relative_path(owner: Any, value: Any) -> Tuple[str, str]:
    if owner not in ("profile", "workspace"):
        raise ReceiptError("target owner must be exactly 'profile' or 'workspace'")
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\\" in value
        or ":" in value
        or value.startswith("/")
    ):
        raise ReceiptError("target path must be one canonical POSIX relative path")
    components = value.split("/")
    if any(component in ("", ".", "..") for component in components):
        raise ReceiptError("target path must be one canonical POSIX relative path")
    normalized = pathlib.PurePosixPath(value).as_posix()
    if normalized != value:
        raise ReceiptError("target path must be canonical")

    allowed = False
    if owner == "workspace":
        allowed = value == ".hermes.md" or value.startswith("sage/")
    elif owner == "profile":
        allowed = (
            value.startswith("plugins/sage/")
            or value.startswith("skills/")
            or (
                len(components) == 2
                and components[0] == "hooks"
                and components[1].startswith("sage-")
                and components[1].endswith(".sh")
            )
        )
    if not allowed:
        raise ReceiptError(
            "target path is outside the Sage-managed profile/workspace surfaces"
        )
    return owner, normalized


def _target_path(binding: ProfileBinding, owner: str, relative_path: str) -> pathlib.Path:
    root = binding.profile_root if owner == "profile" else binding.workspace_root
    target = root.joinpath(*relative_path.split("/"))
    try:
        canonical = target.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ReceiptError("target path cannot be canonicalized: %s" % exc) from exc
    if not _same_path(target, canonical):
        raise ReceiptError(
            "target path is not canonical and crosses a link or reparse point: %s"
            % target
        )
    if not _contains(root, canonical):
        raise ReceiptError("target path escapes its bound %s root" % owner)
    return canonical


def _relative_from_path(binding: ProfileBinding, value: Any) -> Tuple[str, str]:
    if isinstance(value, bool) or value is None:
        raise ReceiptError("managed target must be an explicit absolute path")
    try:
        native = os.fspath(value)
    except TypeError:
        raise ReceiptError("managed target must be an explicit absolute path")
    if not isinstance(native, str) or not native or "\x00" in native:
        raise ReceiptError("managed target must be an explicit absolute path")
    target = pathlib.Path(native)
    if not target.is_absolute() or ".." in target.parts:
        raise ReceiptError("managed target must be an explicit canonical path")
    try:
        canonical = target.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ReceiptError("managed target cannot be canonicalized: %s" % exc) from exc
    if not _same_path(target, canonical):
        raise ReceiptError(
            "managed target is not canonical and crosses a link or reparse point"
        )

    # The workspace is nested beneath the profile root, so test the narrower
    # authority first or every workspace target would be misclassified as a
    # profile target with a leading ``workspace/`` component.
    candidates = (
        ("workspace", binding.workspace_root),
        ("profile", binding.profile_root),
    )
    for owner, root in candidates:
        if _contains(root, canonical):
            relative = canonical.relative_to(root).as_posix()
            owner, relative = _validate_relative_path(owner, relative)
            _target_path(binding, owner, relative)
            return owner, relative
    raise ReceiptError("managed target escapes the bound profile and workspace")


@dataclass(frozen=True, order=True)
class TargetRef:
    """One Sage-managed target expressed without a machine-local absolute path."""

    owner: str
    relative_path: str

    def __post_init__(self) -> None:
        owner, relative = _validate_relative_path(self.owner, self.relative_path)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "relative_path", relative)

    @classmethod
    def from_path(cls, binding: ProfileBinding, path: Any) -> "TargetRef":
        binding = _validated_binding(binding)
        owner, relative = _relative_from_path(binding, path)
        return cls(owner=owner, relative_path=relative)

    @classmethod
    def from_mapping(
        cls, binding: ProfileBinding, value: Any, label: str = "target"
    ) -> "TargetRef":
        mapping = _require_mapping(value, label)
        _require_exact_fields(mapping, _TARGET_FIELDS, label)
        target = cls(owner=mapping["owner"], relative_path=mapping["path"])
        _target_path(binding, target.owner, target.relative_path)
        return target

    def to_mapping(self) -> Dict[str, str]:
        return {"owner": self.owner, "path": self.relative_path}


@dataclass(frozen=True, order=True)
class ManagedTarget:
    """One managed target and the SHA-256 of its exact installed bytes."""

    owner: str
    relative_path: str
    sha256: str

    def __post_init__(self) -> None:
        owner, relative = _validate_relative_path(self.owner, self.relative_path)
        if not isinstance(self.sha256, str) or not _SHA256.fullmatch(self.sha256):
            raise ReceiptError("managed target sha256 must be 64 lowercase hex digits")
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "relative_path", relative)

    @classmethod
    def from_path(
        cls, binding: ProfileBinding, path: Any, sha256: str
    ) -> "ManagedTarget":
        binding = _validated_binding(binding)
        owner, relative = _relative_from_path(binding, path)
        return cls(owner=owner, relative_path=relative, sha256=sha256)

    @classmethod
    def from_mapping(
        cls, binding: ProfileBinding, value: Any, label: str = "managed target"
    ) -> "ManagedTarget":
        mapping = _require_mapping(value, label)
        _require_exact_fields(mapping, _MANAGED_TARGET_FIELDS, label)
        target = cls(
            owner=mapping["owner"],
            relative_path=mapping["path"],
            sha256=mapping["sha256"],
        )
        _target_path(binding, target.owner, target.relative_path)
        return target

    def to_mapping(self) -> Dict[str, str]:
        return {
            "owner": self.owner,
            "path": self.relative_path,
            "sha256": self.sha256,
        }


def _target_identity(owner: str, relative_path: str) -> Tuple[str, str]:
    native = relative_path.replace("/", os.sep)
    identity = os.path.normcase(os.path.normpath(native))
    if os.name == "nt":
        identity = identity.casefold()
    return owner, identity


def _managed_target_order(target: ManagedTarget) -> Tuple[str, str, str, str]:
    owner, identity = _target_identity(target.owner, target.relative_path)
    return owner, identity, target.relative_path, target.sha256


def _target_ref_order(target: TargetRef) -> Tuple[str, str, str]:
    owner, identity = _target_identity(target.owner, target.relative_path)
    return owner, identity, target.relative_path


def _managed_targets(
    binding: ProfileBinding,
    values: Iterable[Any],
    label: str,
    *,
    require_list: bool,
    require_sorted: bool,
) -> Tuple[ManagedTarget, ...]:
    if require_list and not isinstance(values, list):
        raise ReceiptError("%s must be a JSON array" % label)
    try:
        supplied = list(values)
    except TypeError as exc:
        raise ReceiptError("%s must be an iterable of managed targets" % label) from exc
    targets: List[ManagedTarget] = []
    for index, value in enumerate(supplied):
        if isinstance(value, ManagedTarget):
            target = value
            _target_path(binding, target.owner, target.relative_path)
        else:
            target = ManagedTarget.from_mapping(
                binding, value, "%s[%d]" % (label, index)
            )
        targets.append(target)
    ordered = sorted(targets, key=_managed_target_order)
    identities = [
        _target_identity(target.owner, target.relative_path) for target in ordered
    ]
    if len(identities) != len(set(identities)):
        raise ReceiptError("%s contains a duplicate managed target" % label)
    if require_sorted and targets != ordered:
        raise ReceiptError("%s must use canonical owner/path order" % label)
    return tuple(ordered)


def _target_refs(
    binding: ProfileBinding,
    values: Iterable[Any],
    label: str,
    *,
    require_list: bool,
    require_sorted: bool,
) -> Tuple[TargetRef, ...]:
    if require_list and not isinstance(values, list):
        raise ReceiptError("%s must be a JSON array" % label)
    try:
        supplied = list(values)
    except TypeError as exc:
        raise ReceiptError("%s must be an iterable of targets" % label) from exc
    targets: List[TargetRef] = []
    for index, value in enumerate(supplied):
        if isinstance(value, TargetRef):
            target = value
            _target_path(binding, target.owner, target.relative_path)
        else:
            target = TargetRef.from_mapping(binding, value, "%s[%d]" % (label, index))
        targets.append(target)
    ordered = sorted(targets, key=_target_ref_order)
    identities = [
        _target_identity(target.owner, target.relative_path) for target in ordered
    ]
    if len(identities) != len(set(identities)):
        raise ReceiptError("%s contains a duplicate target" % label)
    if require_sorted and targets != ordered:
        raise ReceiptError("%s must use canonical owner/path order" % label)
    return tuple(ordered)


def _canonical_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ReceiptError("receipt data is not canonical JSON: %s" % exc) from exc
    return encoded.encode("utf-8")


def _semantic_hash(mapping: Mapping) -> str:
    semantic = {
        key: value
        for key, value in mapping.items()
        if key not in ("semantic_hash", "timestamps")
    }
    return hashlib.sha256(_canonical_bytes(semantic)).hexdigest()


@dataclass(frozen=True, init=False)
class InstallReceipt:
    """Validated versioned ownership record for one installed profile."""

    binding: ProfileBinding
    source_version: str
    source_commit: str
    managed_targets: Tuple[ManagedTarget, ...]
    config_records: Tuple[Dict[str, Any], ...]
    allowlist_records: Tuple[Dict[str, str], ...]
    semantic_hash: str
    created_at: str
    updated_at: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise ReceiptError("InstallReceipt must be constructed with create or from_mapping")

    @classmethod
    def _construct(cls, **values: Any) -> "InstallReceipt":
        instance = object.__new__(cls)
        for field in (
            "binding",
            "source_version",
            "source_commit",
            "managed_targets",
            "config_records",
            "allowlist_records",
            "semantic_hash",
            "created_at",
            "updated_at",
        ):
            object.__setattr__(instance, field, values[field])
        return instance

    @classmethod
    def create(
        cls,
        *,
        binding: ProfileBinding,
        source_version: str,
        source_commit: str,
        managed_targets: Iterable[Any],
        config_records: Sequence[Any],
        allowlist_records: Sequence[Any],
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> "InstallReceipt":
        binding = _validated_binding(binding)
        version, commit = _source(source_version, source_commit)
        managed = _managed_targets(
            binding,
            managed_targets,
            "managed_targets",
            require_list=False,
            require_sorted=False,
        )
        config = _config_records(
            config_records, "config_records", require_list=False
        )
        allowlist = _allowlist_records(
            allowlist_records, "allowlist_records", require_list=False
        )
        created = _timestamp(created_at or _now(), "created_at")
        updated = _timestamp(updated_at or created, "updated_at")
        provisional = cls._construct(
            binding=binding,
            source_version=version,
            source_commit=commit,
            managed_targets=managed,
            config_records=config,
            allowlist_records=allowlist,
            semantic_hash="",
            created_at=created,
            updated_at=updated,
        )
        digest = _semantic_hash(provisional.to_mapping())
        return cls._construct(
            binding=binding,
            source_version=version,
            source_commit=commit,
            managed_targets=managed,
            config_records=config,
            allowlist_records=allowlist,
            semantic_hash=digest,
            created_at=created,
            updated_at=updated,
        )

    @classmethod
    def from_mapping(
        cls, value: Any, *, expected_binding: Optional[ProfileBinding] = None
    ) -> "InstallReceipt":
        mapping = _require_mapping(value, "install receipt")
        _require_exact_fields(mapping, _INSTALL_FIELDS, "install receipt")
        if mapping["schema"] != INSTALL_RECEIPT_SCHEMA:
            raise ReceiptError("install receipt schema is not supported")
        if type(mapping["schema_version"]) is not int or mapping["schema_version"] != 1:
            raise ReceiptError("install receipt schema version is not supported")
        try:
            parsed_binding = ProfileBinding.from_mapping(mapping["binding"])
            if expected_binding is not None:
                expected_binding = _validated_binding(expected_binding)
                expected_binding.assert_same(parsed_binding)
                binding = expected_binding
            else:
                binding = parsed_binding
        except BindingError as exc:
            raise ReceiptError("install receipt binding is invalid: %s" % exc) from exc
        version, commit = _source_from_mapping(mapping["source"])
        managed = _managed_targets(
            binding,
            mapping["managed_targets"],
            "managed_targets",
            require_list=True,
            require_sorted=True,
        )
        config = _config_records(
            mapping["config_records"], "config_records", require_list=True
        )
        allowlist = _allowlist_records(
            mapping["allowlist_records"], "allowlist_records", require_list=True
        )
        timestamps = _require_mapping(mapping["timestamps"], "timestamps")
        _require_exact_fields(
            timestamps, _RECEIPT_TIMESTAMP_FIELDS, "install receipt timestamps"
        )
        created = _timestamp(timestamps["created_at"], "created_at")
        updated = _timestamp(timestamps["updated_at"], "updated_at")
        digest = mapping["semantic_hash"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ReceiptError("install receipt semantic hash must be lowercase SHA-256")
        receipt = cls._construct(
            binding=binding,
            source_version=version,
            source_commit=commit,
            managed_targets=managed,
            config_records=config,
            allowlist_records=allowlist,
            semantic_hash=digest,
            created_at=created,
            updated_at=updated,
        )
        if _semantic_hash(receipt.to_mapping()) != digest:
            raise ReceiptError("install receipt semantic hash does not match its content")
        return receipt

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "schema": INSTALL_RECEIPT_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "binding": self.binding.to_mapping(),
            "source": {
                "version": self.source_version,
                "commit": self.source_commit,
            },
            "managed_targets": [item.to_mapping() for item in self.managed_targets],
            "config_records": [
                _validate_json_value(item, "config record")
                for item in self.config_records
            ],
            "allowlist_records": [
                _validate_json_value(item, "allowlist record")
                for item in self.allowlist_records
            ],
            "semantic_hash": self.semantic_hash,
            "timestamps": {
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            },
        }


@dataclass(frozen=True, init=False)
class RunJournal:
    """Atomic operation record that remains incomplete until explicit proof."""

    operation_id: str
    operation: str
    status: str
    binding: ProfileBinding
    source_version: str
    source_commit: str
    previous_managed_targets: Tuple[ManagedTarget, ...]
    previous_config_records: Tuple[Dict[str, Any], ...]
    previous_allowlist_records: Tuple[Dict[str, str], ...]
    planned_writes: Tuple[ManagedTarget, ...]
    planned_removals: Tuple[TargetRef, ...]
    result: Optional[Dict[str, Any]]
    semantic_hash: str
    started_at: str
    completed_at: Optional[str]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise ReceiptError("RunJournal must be constructed with create_incomplete or from_mapping")

    @classmethod
    def _construct(cls, **values: Any) -> "RunJournal":
        instance = object.__new__(cls)
        for field in (
            "operation_id",
            "operation",
            "status",
            "binding",
            "source_version",
            "source_commit",
            "previous_managed_targets",
            "previous_config_records",
            "previous_allowlist_records",
            "planned_writes",
            "planned_removals",
            "result",
            "semantic_hash",
            "started_at",
            "completed_at",
        ):
            object.__setattr__(instance, field, values[field])
        return instance

    @classmethod
    def create_incomplete(
        cls,
        *,
        binding: ProfileBinding,
        operation_id: str,
        operation: str,
        source_version: str,
        source_commit: str,
        previous_managed_targets: Iterable[Any],
        previous_config_records: Sequence[Any],
        previous_allowlist_records: Sequence[Any],
        planned_writes: Iterable[Any],
        planned_removals: Iterable[Any],
        started_at: Optional[str] = None,
    ) -> "RunJournal":
        binding = _validated_binding(binding)
        try:
            binding.run_journal_path(operation_id)
        except BindingError as exc:
            raise ReceiptError("operation_id is invalid: %s" % exc) from exc
        if operation not in _OPERATIONS:
            raise ReceiptError("operation must be exactly install, update, or remove")
        version, commit = _source(source_version, source_commit)
        previous_managed = _managed_targets(
            binding,
            previous_managed_targets,
            "previous.managed_targets",
            require_list=False,
            require_sorted=False,
        )
        previous_config = _config_records(
            previous_config_records,
            "previous.config_records",
            require_list=False,
        )
        previous_allowlist = _allowlist_records(
            previous_allowlist_records,
            "previous.allowlist_records",
            require_list=False,
        )
        writes = _managed_targets(
            binding,
            planned_writes,
            "plan.writes",
            require_list=False,
            require_sorted=False,
        )
        removals = _target_refs(
            binding,
            planned_removals,
            "plan.removals",
            require_list=False,
            require_sorted=False,
        )
        write_ids = {
            _target_identity(item.owner, item.relative_path) for item in writes
        }
        removal_ids = {
            _target_identity(item.owner, item.relative_path) for item in removals
        }
        if write_ids & removal_ids:
            raise ReceiptError("one target cannot be both a planned write and removal")
        started = _timestamp(started_at or _now(), "started_at")
        provisional = cls._construct(
            operation_id=operation_id,
            operation=operation,
            status="incomplete",
            binding=binding,
            source_version=version,
            source_commit=commit,
            previous_managed_targets=previous_managed,
            previous_config_records=previous_config,
            previous_allowlist_records=previous_allowlist,
            planned_writes=writes,
            planned_removals=removals,
            result=None,
            semantic_hash="",
            started_at=started,
            completed_at=None,
        )
        digest = _semantic_hash(provisional.to_mapping())
        return cls._construct(
            operation_id=operation_id,
            operation=operation,
            status="incomplete",
            binding=binding,
            source_version=version,
            source_commit=commit,
            previous_managed_targets=previous_managed,
            previous_config_records=previous_config,
            previous_allowlist_records=previous_allowlist,
            planned_writes=writes,
            planned_removals=removals,
            result=None,
            semantic_hash=digest,
            started_at=started,
            completed_at=None,
        )

    @classmethod
    def from_mapping(
        cls, value: Any, *, expected_binding: Optional[ProfileBinding] = None
    ) -> "RunJournal":
        mapping = _require_mapping(value, "run journal")
        _require_exact_fields(mapping, _JOURNAL_FIELDS, "run journal")
        if mapping["schema"] != RUN_JOURNAL_SCHEMA:
            raise ReceiptError("run journal schema is not supported")
        if type(mapping["schema_version"]) is not int or mapping["schema_version"] != 1:
            raise ReceiptError("run journal schema version is not supported")
        try:
            parsed_binding = ProfileBinding.from_mapping(mapping["binding"])
            if expected_binding is not None:
                expected_binding = _validated_binding(expected_binding)
                expected_binding.assert_same(parsed_binding)
                binding = expected_binding
            else:
                binding = parsed_binding
        except BindingError as exc:
            raise ReceiptError("run journal binding is invalid: %s" % exc) from exc
        operation_id = mapping["operation_id"]
        try:
            binding.run_journal_path(operation_id)
        except BindingError as exc:
            raise ReceiptError("operation_id is invalid: %s" % exc) from exc
        operation = mapping["operation"]
        if operation not in _OPERATIONS:
            raise ReceiptError("run journal operation is not supported")
        status = mapping["status"]
        if status not in ("incomplete", "complete"):
            raise ReceiptError("run journal status must be incomplete or complete")
        version, commit = _source_from_mapping(mapping["source"])
        previous = _require_mapping(mapping["previous"], "previous")
        _require_exact_fields(previous, _PREVIOUS_FIELDS, "previous")
        previous_managed = _managed_targets(
            binding,
            previous["managed_targets"],
            "previous.managed_targets",
            require_list=True,
            require_sorted=True,
        )
        previous_config = _config_records(
            previous["config_records"],
            "previous.config_records",
            require_list=True,
        )
        previous_allowlist = _allowlist_records(
            previous["allowlist_records"],
            "previous.allowlist_records",
            require_list=True,
        )
        plan = _require_mapping(mapping["plan"], "plan")
        _require_exact_fields(plan, _PLAN_FIELDS, "plan")
        writes = _managed_targets(
            binding,
            plan["writes"],
            "plan.writes",
            require_list=True,
            require_sorted=True,
        )
        removals = _target_refs(
            binding,
            plan["removals"],
            "plan.removals",
            require_list=True,
            require_sorted=True,
        )
        if {
            _target_identity(item.owner, item.relative_path) for item in writes
        } & {
            _target_identity(item.owner, item.relative_path) for item in removals
        }:
            raise ReceiptError("one target cannot be both a planned write and removal")
        timestamps = _require_mapping(mapping["timestamps"], "timestamps")
        _require_exact_fields(
            timestamps, _JOURNAL_TIMESTAMP_FIELDS, "run journal timestamps"
        )
        started = _timestamp(timestamps["started_at"], "started_at")
        completed_value = timestamps["completed_at"]
        result_value = mapping["result"]
        if status == "incomplete":
            if completed_value is not None or result_value is not None:
                raise ReceiptError(
                    "incomplete run journal cannot contain completion evidence"
                )
            completed = None
            result = None
        else:
            completed = _timestamp(completed_value, "completed_at")
            result_mapping = _require_mapping(result_value, "result")
            result = _mapping_copy(result_mapping, "result")
        digest = mapping["semantic_hash"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ReceiptError("run journal semantic hash must be lowercase SHA-256")
        journal = cls._construct(
            operation_id=operation_id,
            operation=operation,
            status=status,
            binding=binding,
            source_version=version,
            source_commit=commit,
            previous_managed_targets=previous_managed,
            previous_config_records=previous_config,
            previous_allowlist_records=previous_allowlist,
            planned_writes=writes,
            planned_removals=removals,
            result=result,
            semantic_hash=digest,
            started_at=started,
            completed_at=completed,
        )
        if _semantic_hash(journal.to_mapping()) != digest:
            raise ReceiptError("run journal semantic hash does not match its content")
        return journal

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"

    def require_complete(self) -> "RunJournal":
        if not self.is_complete:
            raise ReceiptError(
                "run journal %s is incomplete and is not success evidence"
                % self.operation_id
            )
        return self

    def completed(
        self, *, result: Mapping, completed_at: Optional[str] = None
    ) -> "RunJournal":
        if self.is_complete:
            raise ReceiptError("run journal %s is already complete" % self.operation_id)
        result_copy = _mapping_copy(_require_mapping(result, "result"), "result")
        completed = _timestamp(completed_at or _now(), "completed_at")
        provisional = self._construct(
            operation_id=self.operation_id,
            operation=self.operation,
            status="complete",
            binding=self.binding,
            source_version=self.source_version,
            source_commit=self.source_commit,
            previous_managed_targets=self.previous_managed_targets,
            previous_config_records=self.previous_config_records,
            previous_allowlist_records=self.previous_allowlist_records,
            planned_writes=self.planned_writes,
            planned_removals=self.planned_removals,
            result=result_copy,
            semantic_hash="",
            started_at=self.started_at,
            completed_at=completed,
        )
        digest = _semantic_hash(provisional.to_mapping())
        return self._construct(
            operation_id=self.operation_id,
            operation=self.operation,
            status="complete",
            binding=self.binding,
            source_version=self.source_version,
            source_commit=self.source_commit,
            previous_managed_targets=self.previous_managed_targets,
            previous_config_records=self.previous_config_records,
            previous_allowlist_records=self.previous_allowlist_records,
            planned_writes=self.planned_writes,
            planned_removals=self.planned_removals,
            result=result_copy,
            semantic_hash=digest,
            started_at=self.started_at,
            completed_at=completed,
        )

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "schema": RUN_JOURNAL_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "operation_id": self.operation_id,
            "operation": self.operation,
            "status": self.status,
            "binding": self.binding.to_mapping(),
            "source": {
                "version": self.source_version,
                "commit": self.source_commit,
            },
            "previous": {
                "managed_targets": [
                    item.to_mapping() for item in self.previous_managed_targets
                ],
                "config_records": [
                    _validate_json_value(item, "previous config record")
                    for item in self.previous_config_records
                ],
                "allowlist_records": [
                    _validate_json_value(item, "previous allowlist record")
                    for item in self.previous_allowlist_records
                ],
            },
            "plan": {
                "writes": [item.to_mapping() for item in self.planned_writes],
                "removals": [item.to_mapping() for item in self.planned_removals],
            },
            "result": (
                None
                if self.result is None
                else _validate_json_value(self.result, "result")
            ),
            "semantic_hash": self.semantic_hash,
            "timestamps": {
                "started_at": self.started_at,
                "completed_at": self.completed_at,
            },
        }


def _json_object_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptError("document is not valid strict JSON: duplicate key %s" % key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ReceiptError("document is not valid strict JSON: %s" % value)


def _read_json(binding: ProfileBinding, path: pathlib.Path, label: str) -> Any:
    _validated_binding(binding)
    if _is_reparse(path):
        raise ReceiptError("%s path is a link or reparse point" % label)
    try:
        stat_result = path.stat()
    except FileNotFoundError as exc:
        raise ReceiptError("%s is missing at %s" % (label, path)) from exc
    except OSError as exc:
        raise ReceiptError("cannot inspect %s at %s: %s" % (label, path, exc)) from exc
    if not path.is_file():
        raise ReceiptError("%s is not a regular file at %s" % (label, path))
    if stat_result.st_size > _MAX_DOCUMENT_BYTES:
        raise ReceiptError("%s exceeds the maximum safe document size" % label)
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except ReceiptError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptError("%s is not valid strict JSON: %s" % (label, exc)) from exc
    _validated_binding(binding)
    return value


def _serialized_document(mapping: Mapping) -> bytes:
    try:
        text = json.dumps(
            mapping,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ReceiptError("document cannot be serialized as strict JSON: %s" % exc) from exc
    return (text + "\n").encode("utf-8")


def _fsync_directory(path: pathlib.Path) -> None:
    if os.name == "nt":
        # Windows does not expose a portable directory fsync.  The temporary
        # file itself is fsynced before the same-volume atomic os.replace.
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(os.fspath(path), flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _prepare_parent(
    binding: ProfileBinding, path: pathlib.Path, expected: pathlib.Path, label: str
) -> None:
    _validated_binding(binding)
    if not _same_path(path, expected):
        raise ReceiptError("%s destination is not the exact bound path" % label)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ReceiptError("cannot create %s parent: %s" % (label, exc)) from exc
    _validated_binding(binding)
    try:
        canonical_parent = path.parent.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ReceiptError("%s parent cannot be canonicalized: %s" % (label, exc)) from exc
    if not _same_path(path.parent, canonical_parent):
        raise ReceiptError("%s parent crosses a link or reparse point" % label)
    if _is_reparse(path):
        raise ReceiptError("%s destination is a link or reparse point" % label)


def _document_lock_path(
    binding: ProfileBinding, document_path: pathlib.Path
) -> pathlib.Path:
    if _same_path(document_path, binding.receipt_path):
        owner = binding.receipt_path.parent
    elif _contains(binding.runs_root, document_path):
        owner = binding.runs_root
    else:
        raise ReceiptError("document lock target is outside the bound receipt roots")
    lock_path = document_path.with_name(".%s.lock" % document_path.name)
    try:
        canonical = lock_path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ReceiptError("document lock path cannot be canonicalized: %s" % exc) from exc
    if not _same_path(lock_path, canonical) or not _contains(owner, canonical):
        raise ReceiptError("document lock path crosses a link or reparse point")
    return canonical


@contextmanager
def _exclusive_document_lock(
    binding: ProfileBinding, document_path: pathlib.Path, label: str
) -> Iterator[None]:
    lock_path = _document_lock_path(binding, document_path)
    _prepare_parent(binding, lock_path, lock_path, label + " lock")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if os.name != "nt" and hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(os.fspath(lock_path), flags, 0o600)
    except OSError as exc:
        raise ReceiptError("cannot open %s lock: %s" % (label, exc)) from exc

    locked = False
    try:
        opened = os.fstat(descriptor)
        _prepare_parent(binding, lock_path, lock_path, label + " lock")
        visible = os.stat(os.fspath(lock_path), follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) != (visible.st_dev, visible.st_ino):
            raise ReceiptError("%s lock path changed while it was opened" % label)
        if getattr(opened, "st_nlink", 1) != 1:
            raise ReceiptError("%s lock path is a hardlink outside its home" % label)
        _fsync_directory(lock_path.parent)
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            contention_errnos = {errno.EACCES, errno.EAGAIN}
            if hasattr(errno, "EDEADLK"):
                contention_errnos.add(errno.EDEADLK)
            if exc.errno in contention_errnos:
                raise ReceiptError(
                    "%s is already being changed by another operation" % label
                ) from exc
            raise ReceiptError("cannot acquire %s lock: %s" % (label, exc)) from exc
        locked = True
        current = os.fstat(descriptor)
        if getattr(current, "st_nlink", 1) != 1:
            raise ReceiptError("%s lock path gained an outside hardlink" % label)
        if current.st_size < 1:
            os.lseek(descriptor, 0, os.SEEK_SET)
            os.write(descriptor, b"\x00")
            os.fsync(descriptor)
        if getattr(os.fstat(descriptor), "st_nlink", 1) != 1:
            raise ReceiptError("%s lock path gained an outside hardlink" % label)
        yield
    finally:
        try:
            if locked:
                os.lseek(descriptor, 0, os.SEEK_SET)
                if os.name == "nt":
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError as exc:
            raise ReceiptError("cannot release %s lock: %s" % (label, exc)) from exc
        finally:
            try:
                os.close(descriptor)
            except OSError as exc:
                raise ReceiptError("cannot close %s lock: %s" % (label, exc)) from exc


@contextmanager
def profile_transaction_lock(binding: ProfileBinding) -> Iterator[None]:
    """Serialize profile-wide Sage mutations, re-entrant for one thread."""

    binding = _validated_binding(binding)
    lock_path = binding.pack_lock_path
    lock_key = os.path.normcase(os.path.normpath(os.fspath(lock_path)))
    thread_id = threading.get_ident()
    nested = False

    with _PROFILE_TRANSACTION_GUARD:
        owner = _PROFILE_TRANSACTION_OWNERS.get(lock_key)
        if owner is not None:
            owner_thread, depth = owner
            if owner_thread != thread_id:
                raise ReceiptError(
                    "profile operation is already being changed by another thread: %s"
                    % binding.profile_id
                )
            _PROFILE_TRANSACTION_OWNERS[lock_key] = (thread_id, depth + 1)
            nested = True
        else:
            _PROFILE_TRANSACTION_OWNERS[lock_key] = (thread_id, 1)

    if nested:
        try:
            yield
        finally:
            with _PROFILE_TRANSACTION_GUARD:
                owner_thread, depth = _PROFILE_TRANSACTION_OWNERS[lock_key]
                if owner_thread != thread_id:
                    raise ReceiptError("profile transaction lock ownership changed")
                if depth == 1:
                    _PROFILE_TRANSACTION_OWNERS.pop(lock_key, None)
                else:
                    _PROFILE_TRANSACTION_OWNERS[lock_key] = (thread_id, depth - 1)
        return

    descriptor = -1
    locked = False
    primary_error: Optional[BaseException] = None
    try:
        _prepare_parent(binding, lock_path, lock_path, "profile transaction lock")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        if os.name != "nt" and hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(os.fspath(lock_path), flags, 0o600)
        opened = os.fstat(descriptor)
        _prepare_parent(binding, lock_path, lock_path, "profile transaction lock")
        visible = os.stat(os.fspath(lock_path), follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) != (visible.st_dev, visible.st_ino):
            raise ReceiptError("profile transaction lock changed while it was opened")
        if getattr(opened, "st_nlink", 1) != 1:
            raise ReceiptError("profile transaction lock is a hardlink outside its home")
        _fsync_directory(lock_path.parent)
        if opened.st_size < 1:
            os.lseek(descriptor, 0, os.SEEK_SET)
            os.write(descriptor, b"\x00")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            contention_errnos = {errno.EACCES, errno.EAGAIN}
            if hasattr(errno, "EDEADLK"):
                contention_errnos.add(errno.EDEADLK)
            if exc.errno in contention_errnos:
                raise ReceiptError(
                    "profile operation is already being changed by another process: %s"
                    % binding.profile_id
                ) from exc
            raise ReceiptError("cannot acquire profile transaction lock: %s" % exc) from exc
        locked = True
        try:
            yield
        except BaseException as exc:
            primary_error = exc
            raise
    finally:
        release_error = None
        if descriptor >= 0:
            if locked:
                try:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    if os.name == "nt":
                        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError as exc:
                    release_error = exc
            try:
                os.close(descriptor)
            except OSError as exc:
                if release_error is None:
                    release_error = exc
        with _PROFILE_TRANSACTION_GUARD:
            owner = _PROFILE_TRANSACTION_OWNERS.get(lock_key)
            if owner is not None and owner[0] == thread_id:
                _PROFILE_TRANSACTION_OWNERS.pop(lock_key, None)
        if release_error is not None:
            failure = ReceiptError(
                "cannot release profile transaction lock: %s" % release_error
            )
            failure.__cause__ = release_error
            if primary_error is not None:
                if hasattr(primary_error, "add_note"):
                    primary_error.add_note(str(failure))
                try:
                    setattr(
                        primary_error,
                        "profile_transaction_release_error",
                        failure,
                    )
                except (AttributeError, TypeError):
                    pass
            else:
                raise failure from release_error


def _atomic_write_json(
    binding: ProfileBinding,
    path: pathlib.Path,
    expected: pathlib.Path,
    mapping: Mapping,
    label: str,
    *,
    reject_existing: bool,
) -> pathlib.Path:
    _prepare_parent(binding, path, expected, label)
    if reject_existing and path.exists():
        raise ReceiptError("%s already exists at %s" % (label, path))
    document = _serialized_document(mapping)
    descriptor = -1
    temporary_name = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".%s." % path.name,
            suffix=".tmp",
            dir=os.fspath(path.parent),
        )
        temporary = pathlib.Path(temporary_name)
        canonical_temporary = temporary.resolve(strict=True)
        if not _same_path(temporary, canonical_temporary) or not _contains(
            path.parent, canonical_temporary
        ):
            raise ReceiptError("temporary receipt path escaped its bound directory")
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(document)
            stream.flush()
            os.fsync(stream.fileno())
        _prepare_parent(binding, path, expected, label)
        if reject_existing and path.exists():
            raise ReceiptError("%s already exists at %s" % (label, path))
        try:
            os.replace(os.fspath(temporary), os.fspath(path))
        except OSError as exc:
            raise ReceiptError("%s atomic replace failed: %s" % (label, exc)) from exc
        temporary_name = None
        _fsync_directory(path.parent)
        return path
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def write_install_receipt(
    binding: ProfileBinding, receipt: InstallReceipt
) -> pathlib.Path:
    """Atomically replace the one receipt owned by ``binding``."""

    binding = _validated_binding(binding)
    if not isinstance(receipt, InstallReceipt):
        raise ReceiptError("receipt must be a validated InstallReceipt")
    try:
        binding.assert_same(receipt.binding)
    except BindingError as exc:
        raise ReceiptError("install receipt belongs to a different binding") from exc
    validated = InstallReceipt.from_mapping(
        receipt.to_mapping(), expected_binding=binding
    )
    with _exclusive_document_lock(
        binding, binding.receipt_path, "install receipt"
    ):
        if os.path.lexists(os.fspath(binding.receipt_path)):
            load_install_receipt(binding)
        return _atomic_write_json(
            binding,
            binding.receipt_path,
            binding.receipt_path,
            validated.to_mapping(),
            "install receipt",
            reject_existing=False,
        )


def load_install_receipt(binding: ProfileBinding) -> InstallReceipt:
    """Read and validate only the selected profile's exact install receipt."""

    binding = _validated_binding(binding)
    mapping = _read_json(binding, binding.receipt_path, "install receipt")
    return InstallReceipt.from_mapping(mapping, expected_binding=binding)


def begin_run_journal(
    *,
    binding: ProfileBinding,
    operation_id: str,
    operation: str,
    source_version: str,
    source_commit: str,
    previous_managed_targets: Iterable[Any],
    previous_config_records: Sequence[Any],
    previous_allowlist_records: Sequence[Any],
    planned_writes: Iterable[Any],
    planned_removals: Iterable[Any],
    started_at: Optional[str] = None,
) -> RunJournal:
    """Persist one immutable incomplete journal before installer mutation."""

    journal = RunJournal.create_incomplete(
        binding=binding,
        operation_id=operation_id,
        operation=operation,
        source_version=source_version,
        source_commit=source_commit,
        previous_managed_targets=previous_managed_targets,
        previous_config_records=previous_config_records,
        previous_allowlist_records=previous_allowlist_records,
        planned_writes=planned_writes,
        planned_removals=planned_removals,
        started_at=started_at,
    )
    path = binding.run_journal_path(journal.operation_id)
    with _exclusive_document_lock(journal.binding, path, "run journal"):
        _atomic_write_json(
            journal.binding,
            path,
            path,
            journal.to_mapping(),
            "run journal",
            reject_existing=True,
        )
    return journal


def load_run_journal(binding: ProfileBinding, operation_id: str) -> RunJournal:
    """Load either incomplete recovery state or a completed journal explicitly."""

    binding = _validated_binding(binding)
    try:
        path = binding.run_journal_path(operation_id)
    except BindingError as exc:
        raise ReceiptError("operation_id is invalid: %s" % exc) from exc
    mapping = _read_json(binding, path, "run journal")
    journal = RunJournal.from_mapping(mapping, expected_binding=binding)
    if journal.operation_id != operation_id:
        raise ReceiptError("run journal operation_id does not match its filename")
    return journal


def load_completed_run_journal(
    binding: ProfileBinding, operation_id: str
) -> RunJournal:
    """Load success evidence, rejecting an incomplete recovery journal."""

    return load_run_journal(binding, operation_id).require_complete()


def complete_run_journal(
    *,
    binding: ProfileBinding,
    operation_id: str,
    result: Mapping,
    completed_at: Optional[str] = None,
) -> RunJournal:
    """Atomically transition an existing incomplete journal to complete."""

    binding = _validated_binding(binding)
    try:
        path = binding.run_journal_path(operation_id)
    except BindingError as exc:
        raise ReceiptError("operation_id is invalid: %s" % exc) from exc
    with _exclusive_document_lock(binding, path, "run journal"):
        journal = load_run_journal(binding, operation_id)
        if journal.is_complete:
            raise ReceiptError("run journal %s is already complete" % operation_id)
        completed = journal.completed(result=result, completed_at=completed_at)
        _atomic_write_json(
            binding,
            path,
            path,
            completed.to_mapping(),
            "run journal",
            reject_existing=False,
        )
        return completed


__all__ = [
    "INSTALL_RECEIPT_SCHEMA",
    "RUN_JOURNAL_SCHEMA",
    "SCHEMA_VERSION",
    "InstallReceipt",
    "ManagedTarget",
    "ReceiptError",
    "RunJournal",
    "TargetRef",
    "begin_run_journal",
    "complete_run_journal",
    "load_completed_run_journal",
    "load_install_receipt",
    "load_run_journal",
    "profile_transaction_lock",
    "write_install_receipt",
]
