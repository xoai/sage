#!/usr/bin/env python3
"""Explicit, reversible adoption of one receipt-less legacy Hermes profile.

This is deliberately separate from install/update.  It never discovers profiles:
the caller supplies one already-authorized ``ProfileBinding``.  Only the narrow
legacy Sage surface allowlist is quarantined; durable identity, memory, state,
credentials, and unrelated files remain in place.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import tempfile
import uuid
from contextlib import ExitStack, contextmanager
from datetime import date
from collections.abc import Mapping
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

try:  # Installed package import.
    from . import profile_installer, receipts
    from .profile_binding import ProfileBinding
except ImportError:  # Direct-path import used by validators/bootstrap.
    import profile_installer
    import receipts
    from profile_binding import ProfileBinding


SCHEMA = "sage.hermes.profile-migration"
SCHEMA_VERSION = 1
_OPERATION = "receiptless-profile-migration"
_WINDOWS_REPARSE_POINT = 0x400


class MigrationError(RuntimeError):
    """The explicit profile migration was rejected or restored after failure."""


@contextmanager
def _acquire_profile_transaction_lock(
    binding: ProfileBinding,
) -> Iterator[None]:
    """Translate lock enter/exit failures without relabeling body errors."""

    stack = ExitStack()
    try:
        stack.enter_context(receipts.profile_transaction_lock(binding))
    except receipts.ReceiptError as exc:
        raise MigrationError(
            "profile migration cannot start because this profile is already being changed: %s"
            % exc
        ) from exc
    try:
        yield
    finally:
        try:
            stack.close()
        except receipts.ReceiptError as exc:
            raise MigrationError(
                "profile migration could not release its transaction lock: %s" % exc
            ) from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: pathlib.Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _atomic_write(path: pathlib.Path, data: bytes) -> None:
    # Same-directory mkstemp + descriptor-based write + fsync + os.replace +
    # parent fsync + cleanup. Mirrors receipts._atomic_write_json's discipline
    # so a PID-named temp cannot be pre-created as a symlink or reparse point,
    # and a crash mid-write does not leave an attacker-named file behind.
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = -1
    temporary_name = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".%s." % path.name,
            suffix=".tmp",
            dir=os.fspath(path.parent),
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(os.fspath(temporary_name), os.fspath(path))
        temporary_name = None
        if os.name != "nt":
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            directory_descriptor = os.open(os.fspath(path.parent), flags)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def _atomic_json(path: pathlib.Path, value: Mapping[str, Any]) -> None:
    _atomic_write(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def _require_binding(binding: ProfileBinding) -> ProfileBinding:
    if not isinstance(binding, ProfileBinding):
        raise MigrationError("migration requires one explicit ProfileBinding")
    try:
        current = ProfileBinding.from_explicit(
            collection_root=binding.collection_root,
            profile_id=binding.profile_id,
            profile_root=binding.profile_root,
            workspace_root=binding.workspace_root,
        )
        binding.assert_same(current)
    except Exception as exc:
        raise MigrationError("explicit profile binding is no longer safe: %s" % exc) from exc
    return binding


def migration_journal_path(
    binding: ProfileBinding, operation_id: str
) -> pathlib.Path:
    """Return the durable parent journal path for one explicit migration."""

    _require_binding(binding)
    # Reuse ProfileBinding's safe-filename validation, but keep this operation's
    # journal visibly distinct from an installer run journal.
    validated = binding.run_journal_path(operation_id)
    return validated.with_name(operation_id + ".migration.json")


def default_backup_root(binding: ProfileBinding) -> pathlib.Path:
    """Return an external, date-scoped backup root for this collection."""

    collection = binding.collection_root.resolve()
    if collection.drive:
        base = pathlib.Path(collection.drive + os.sep) / "backups"
    else:
        base = collection.parent / "backups"
    return base / ("sage-hermes-profile-%s" % date.today().isoformat())


def _validated_backup_root(
    binding: ProfileBinding, backup_root: pathlib.Path
) -> pathlib.Path:
    root = pathlib.Path(backup_root).resolve()
    collection = binding.collection_root.resolve()
    if root == collection or collection in root.parents:
        raise MigrationError("migration backup root must be outside the Hermes collection")
    return root


def _backup_root(
    binding: ProfileBinding, operation_id: str, backup_root: pathlib.Path
) -> pathlib.Path:
    migration_journal_path(binding, operation_id)  # validates the component
    return _validated_backup_root(binding, backup_root) / (
        "%s-%s" % (binding.profile_id, operation_id)
    )


def _path_kind(path: pathlib.Path) -> Optional[str]:
    try:
        metadata = os.stat(os.fspath(path), follow_symlinks=False)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(metadata.st_mode) or (
        getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_POINT
    ):
        raise MigrationError("legacy migration refuses links/reparse points: %s" % path)
    if stat.S_ISREG(metadata.st_mode):
        if metadata.st_nlink > 1:
            raise MigrationError("legacy migration refuses hardlinked files: %s" % path)
        return "file"
    if stat.S_ISDIR(metadata.st_mode):
        return "directory"
    raise MigrationError("legacy migration refuses special filesystem entries: %s" % path)


def _inventory_tree(path: pathlib.Path) -> List[Dict[str, Any]]:
    kind = _path_kind(path)
    if kind is None:
        return []
    if kind == "file":
        metadata = path.stat()
        return [
            {
                "path": "",
                "size": metadata.st_size,
                "mode": stat.S_IMODE(metadata.st_mode),
                "sha256": _sha256(path),
            }
        ]
    files: List[Dict[str, Any]] = []
    for child in sorted(path.rglob("*")):
        child_kind = _path_kind(child)
        if child_kind != "file":
            continue
        metadata = child.stat()
        files.append(
            {
                "path": child.relative_to(path).as_posix(),
                "size": metadata.st_size,
                "mode": stat.S_IMODE(metadata.st_mode),
                "sha256": _sha256(child),
            }
        )
    return files


def _copy_entry(source: pathlib.Path, destination: pathlib.Path, kind: str) -> None:
    if kind == "file":
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(destination, source.read_bytes())
        shutil.copystat(source, destination, follow_symlinks=False)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, copy_function=shutil.copy2)


def _remove_entry(path: pathlib.Path) -> None:
    kind = _path_kind(path)
    if kind == "file":
        path.unlink()
    elif kind == "directory":
        shutil.rmtree(path)


def _legacy_surface_paths(binding: ProfileBinding) -> List[Tuple[str, pathlib.Path]]:
    paths: List[Tuple[str, pathlib.Path]] = [
        ("config.yaml", binding.config_path),
        ("plugins/sage", binding.plugin_root),
        ("agent-hooks/sage", binding.profile_root / "agent-hooks" / "sage"),
        ("workspace/sage", binding.workspace_root / "sage"),
        ("workspace/.hermes.md", binding.workspace_root / ".hermes.md"),
    ]
    if binding.hooks_root.is_dir():
        for hook in sorted(binding.hooks_root.glob("sage-*.sh")):
            paths.append(("hooks/" + hook.name, hook))
    return paths


def _backup_legacy(
    binding: ProfileBinding,
    operation_id: str,
    journal: Dict[str, Any],
    backup_root: pathlib.Path,
) -> Tuple[pathlib.Path, List[Dict[str, Any]]]:
    backup = _backup_root(binding, operation_id, backup_root)
    journal["backup_path"] = os.fspath(backup)
    journal["backup_root"] = os.fspath(backup.parent)
    _atomic_json(migration_journal_path(binding, operation_id), journal)
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.mkdir(parents=True, exist_ok=False)

    entries: List[Dict[str, Any]] = []
    for relative, source in _legacy_surface_paths(binding):
        kind = _path_kind(source)
        entry: Dict[str, Any] = {
            "relative_path": relative,
            "source_path": os.fspath(source),
            "kind": kind,
            "files": _inventory_tree(source),
        }
        if kind is not None:
            _copy_entry(source, backup / "legacy" / relative, kind)
        entries.append(entry)

    manifest = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "binding": binding.to_mapping(),
        "operation_id": operation_id,
        "entries": entries,
    }
    _atomic_json(backup / "manifest.json", manifest)
    _verify_legacy_backup(binding, backup, entries)
    journal["backup_manifest_sha256"] = _sha256(backup / "manifest.json")
    journal["phase"] = "backup-complete"
    _atomic_json(migration_journal_path(binding, operation_id), journal)
    return backup, entries


def _verify_file_inventory(root: pathlib.Path, files: Iterable[Mapping[str, Any]]) -> None:
    for record in files:
        path = root if not record["path"] else root / record["path"]
        if not path.is_file() or _sha256(path) != record["sha256"]:
            raise MigrationError("migration backup verification failed: %s" % path)


def _verify_legacy_backup(
    binding: ProfileBinding,
    backup: pathlib.Path,
    entries: Iterable[Mapping[str, Any]],
) -> None:
    for entry in entries:
        if entry["kind"] is None:
            continue
        target = backup / "legacy" / entry["relative_path"]
        if _path_kind(target) != entry["kind"]:
            raise MigrationError("migration backup type verification failed: %s" % target)
        _verify_file_inventory(target, entry["files"])


def _legacy_config_candidate(raw: bytes) -> bytes:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MigrationError("selected profile config is not UTF-8: %s" % exc) from exc

    lines = text.splitlines(keepends=True)
    kept: List[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        plain = line.rstrip("\r\n")
        indent = len(plain) - len(plain.lstrip())
        if indent == 0 and re.match(r"^sage_profile_binding\s*:", plain):
            index += 1
            while index < len(lines):
                following = lines[index].rstrip("\r\n")
                if following.strip() and len(following) - len(following.lstrip()) == 0:
                    break
                index += 1
            continue
        if re.match(r"^\s*-\s*matcher\s*:", plain):
            block = [line]
            lookahead = index + 1
            while lookahead < len(lines):
                candidate = lines[lookahead].rstrip("\r\n")
                candidate_indent = len(candidate) - len(candidate.lstrip())
                if candidate.strip() and candidate_indent <= indent:
                    break
                block.append(lines[lookahead])
                lookahead += 1
            command_lines = [
                item for item in block if re.match(r"^\s*command\s*:", item)
            ]
            if any(
                re.search(
                    r"(?:agent-hooks[/\\]sage|hooks[/\\]sage-[^\s\"']*\.sh|sage-hermes-gate\.sh)",
                    command,
                    re.IGNORECASE,
                )
                for command in command_lines
            ):
                index = lookahead
                continue
        kept.append(line)
        index += 1
    return "".join(kept).encode("utf-8")


def _matching_receipt(binding: ProfileBinding, config_bytes: bytes) -> bool:
    if not binding.receipt_path.exists():
        return False
    try:
        receipt = receipts.load_install_receipt(binding)
        text = config_bytes.decode("utf-8")
        profile_installer._require_config_matches_receipt(text, receipt)
        profile_installer._read_json_binding(text, binding)
    except (Exception, UnicodeDecodeError):
        return False
    return True


def _has_legacy_surface(binding: ProfileBinding, config_bytes: bytes) -> bool:
    if any(
        _path_kind(path) is not None
        for relative, path in _legacy_surface_paths(binding)
        if relative != "config.yaml"
    ):
        return True
    lowered = config_bytes.lower()
    return b"sage_profile_binding" in lowered or b"agent-hooks/sage" in lowered


def _quarantine_legacy(
    binding: ProfileBinding,
    entries: Iterable[Mapping[str, Any]],
    config_candidate: bytes,
) -> None:
    # Config is replaced rather than removed.  Its exact prior bytes are already
    # verified in the retained backup.
    for entry in entries:
        relative = entry["relative_path"]
        if entry["kind"] is None or relative == "config.yaml":
            continue
        _remove_entry(pathlib.Path(entry["source_path"]))
    _atomic_write(binding.config_path, config_candidate)


def _restore_legacy(
    binding: ProfileBinding,
    backup: pathlib.Path,
    entries: Iterable[Mapping[str, Any]],
) -> None:
    _verify_legacy_backup(binding, backup, entries)
    # Remove only explicit adoption surfaces.  This is used immediately after a
    # failed child transaction; completed migrations use receipt-bounded removal.
    for entry in entries:
        path = pathlib.Path(entry["source_path"])
        if entry["relative_path"] == "config.yaml":
            continue
        _remove_entry(path)
    for entry in entries:
        source = backup / "legacy" / entry["relative_path"]
        destination = pathlib.Path(entry["source_path"])
        if entry["kind"] is None:
            if entry["relative_path"] == "config.yaml" and destination.exists():
                destination.unlink()
            continue
        _remove_entry(destination)
        _copy_entry(source, destination, entry["kind"])


def _target_path(binding: ProfileBinding, target: receipts.ManagedTarget) -> pathlib.Path:
    root = binding.profile_root if target.owner == "profile" else binding.workspace_root
    return root / target.relative_path.replace("/", os.sep)


def _capture_installed_state(
    binding: ProfileBinding,
    backup: pathlib.Path,
    directory_name: str,
) -> Dict[str, Any]:
    receipt = receipts.load_install_receipt(binding)
    records: List[Dict[str, Any]] = []
    receipt_lock = binding.receipt_path.with_name(".%s.lock" % binding.receipt_path.name)
    for owner, relative, backup_relative, source in [
        ("profile", "config.yaml", "config.yaml", binding.config_path),
        (
            "workspace",
            ".sage/config.yaml",
            "workspace/.sage/config.yaml",
            binding.state_root / "config.yaml",
        ),
        (
            "workspace",
            ".sage/receipts/install.json",
            "install.json",
            binding.receipt_path,
        ),
        (
            "workspace",
            ".sage/receipts/.install.json.lock",
            ".install.json.lock",
            receipt_lock,
        ),
    ] + [
        (
            target.owner,
            target.relative_path,
            (
                target.relative_path
                if target.owner == "profile"
                else "workspace/" + target.relative_path
            ),
            _target_path(binding, target),
        )
        for target in receipt.managed_targets
    ]:
        data = source.read_bytes()
        destination = backup / directory_name / backup_relative
        _atomic_write(destination, data)
        records.append(
            {
                "owner": owner,
                "relative_path": relative,
                "backup_relative_path": backup_relative,
                "source_path": os.fspath(source),
                "sha256": _sha256_bytes(data),
            }
        )
    manifest = {
        "receipt_semantic_hash": receipt.semantic_hash,
        "records": records,
    }
    _atomic_json(backup / directory_name / "manifest.json", manifest)
    return manifest


def _capture_post_migration(
    binding: ProfileBinding,
    backup: pathlib.Path,
) -> Dict[str, Any]:
    return _capture_installed_state(binding, backup, "post_migration")


def _remove_receipt_owned_candidate(binding: ProfileBinding) -> None:
    """Remove unchanged child-install bytes after retaining them in the backup."""

    receipt = receipts.load_install_receipt(binding)
    parents = set()
    for target in receipt.managed_targets:
        path = _target_path(binding, target)
        if not path.is_file() or _sha256(path) != target.sha256:
            raise MigrationError("failed child candidate changed before restoration: %s" % path)
        path.unlink()
        parents.add(path.parent)
    for parent in sorted(parents, key=lambda value: len(value.parts), reverse=True):
        try:
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
    binding.receipt_path.unlink()
    receipt_lock = binding.receipt_path.with_name(".%s.lock" % binding.receipt_path.name)
    if receipt_lock.is_file():
        receipt_lock.unlink()
    durable_config = binding.state_root / "config.yaml"
    if durable_config.is_file():
        durable_config.unlink()


def _verified_probe(
    activation_probe: Optional[Callable[..., Mapping[str, Any]]]
) -> Callable[..., Mapping[str, Any]]:
    def probe(**kwargs: Any) -> Mapping[str, Any]:
        if activation_probe is None:
            return {
                "ok": False,
                "fresh_process_verified": False,
                "detail": "fresh-process activation probe is required",
            }
        result = activation_probe(**kwargs)
        if not isinstance(result, Mapping):
            return {
                "ok": False,
                "fresh_process_verified": False,
                "detail": "activation probe returned a malformed result",
            }
        if result.get("ok") is not True or result.get("fresh_process_verified") is not True:
            failed = dict(result)
            failed["ok"] = False
            failed.setdefault("detail", "fresh-process activation was not verified")
            return failed
        return dict(result)

    return probe


def migrate_receiptless_profile(
    *,
    binding: ProfileBinding,
    artifact_dir: pathlib.Path,
    consent_granted: bool,
    source_version: str,
    source_commit: str,
    backup_root: pathlib.Path,
    bash_path: str = "bash",
    operation_id: Optional[str] = None,
    framework_root: Optional[pathlib.Path] = None,
    activation_probe: Optional[Callable[..., Mapping[str, Any]]] = None,
    activation_rollback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """Adopt one explicit receipt-less profile under its transaction lock."""

    _require_binding(binding)
    with _acquire_profile_transaction_lock(binding):
        return _migrate_receiptless_profile_locked(
            binding=binding,
            artifact_dir=artifact_dir,
            consent_granted=consent_granted,
            source_version=source_version,
            source_commit=source_commit,
            backup_root=backup_root,
            bash_path=bash_path,
            operation_id=operation_id,
            framework_root=framework_root,
            activation_probe=activation_probe,
            activation_rollback=activation_rollback,
        )


def _migrate_receiptless_profile_locked(
    *,
    binding: ProfileBinding,
    artifact_dir: pathlib.Path,
    consent_granted: bool,
    source_version: str,
    source_commit: str,
    backup_root: pathlib.Path,
    bash_path: str = "bash",
    operation_id: Optional[str] = None,
    framework_root: Optional[pathlib.Path] = None,
    activation_probe: Optional[Callable[..., Mapping[str, Any]]] = None,
    activation_rollback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """Adopt one explicit receipt-less/conflicting legacy profile transactionally."""

    _require_binding(binding)
    if not consent_granted:
        raise MigrationError("explicit consent for receipt-less profile migration was not granted")
    operation_id = operation_id or ("migration-" + uuid.uuid4().hex)
    backup_root = _validated_backup_root(binding, pathlib.Path(backup_root))
    journal_path = migration_journal_path(binding, operation_id)
    backup = _backup_root(binding, operation_id, backup_root)
    if journal_path.exists() or backup.exists():
        raise MigrationError("migration operation already exists: %s" % operation_id)

    try:
        config_bytes = binding.config_path.read_bytes()
    except FileNotFoundError:
        config_bytes = b""
    except OSError as exc:
        raise MigrationError("selected profile config is unreadable: %s" % exc) from exc
    if binding.receipt_path.exists():
        if _matching_receipt(binding, config_bytes):
            raise MigrationError("profile already has matching receipt ownership; run sage update")
        raise MigrationError(
            "receipt-less migration refuses an existing malformed or conflicting receipt"
        )
    if not _has_legacy_surface(binding, config_bytes):
        raise MigrationError("no receipt-less legacy Sage surfaces were found")
    config_candidate = _legacy_config_candidate(config_bytes)

    journal: Dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "operation": _OPERATION,
        "operation_id": operation_id,
        "status": "incomplete",
        "phase": "preparing-backup",
        "binding": binding.to_mapping(),
        "backup_path": os.fspath(backup),
        "backup_root": os.fspath(backup_root),
        "backup_manifest_sha256": None,
        "child_operation_id": None,
        "post_migration": None,
        "activation": None,
        "failure": None,
        "restored": False,
    }

    entries: List[Dict[str, Any]] = []
    child_completed = False
    try:
        backup, entries = _backup_legacy(
            binding, operation_id, journal, backup_root
        )
        _quarantine_legacy(binding, entries, config_candidate)
        journal["phase"] = "legacy-quarantined"
        _atomic_json(journal_path, journal)

        child_operation_id = operation_id + "-install"
        journal["child_operation_id"] = child_operation_id
        journal["status"] = "child-install-running"
        journal["phase"] = "child-install-starting"
        _atomic_json(journal_path, journal)
        result = profile_installer.install(
            binding=binding,
            artifact_dir=pathlib.Path(artifact_dir),
            consent_granted=True,
            source_version=source_version,
            source_commit=source_commit,
            bash_path=bash_path,
            operation_id=child_operation_id,
            framework_root=(pathlib.Path(framework_root) if framework_root else None),
            activation_probe=_verified_probe(activation_probe),
            activation_rollback=activation_rollback,
        )
        child_completed = True
        post = _capture_post_migration(binding, backup)
        journal["status"] = "complete"
        journal["phase"] = "complete"
        journal["child_operation_id"] = result["operation_id"]
        journal["post_migration"] = post
        journal["activation"] = result["activation"]
        _atomic_json(journal_path, journal)
        return {
            "ok": True,
            "operation": _OPERATION,
            "operation_id": operation_id,
            "child_operation_id": result["operation_id"],
            "activation": result["activation"],
            "backup_path": os.fspath(backup),
        }
    except Exception as exc:
        restore_error: Optional[Exception] = None
        activation_rollback_error: Optional[Exception] = None
        if entries:
            try:
                if binding.receipt_path.is_file():
                    _capture_installed_state(binding, backup, "failed_candidate")
                    _remove_receipt_owned_candidate(binding)
                else:
                    receipt_lock = binding.receipt_path.with_name(
                        ".%s.lock" % binding.receipt_path.name
                    )
                    if receipt_lock.is_file():
                        receipt_lock.unlink()
                _restore_legacy(binding, backup, entries)
            except Exception as restore_exc:  # retain both failures in evidence
                restore_error = restore_exc
            if (
                restore_error is None
                and child_completed
                and activation_rollback is not None
            ):
                try:
                    plugin_present = _path_kind(binding.plugin_root) == "directory"
                    proof = activation_rollback(
                        binding=binding,
                        config_records=(),
                        allowlist_records=(),
                        plugin_present=plugin_present,
                    )
                    if isinstance(proof, Mapping) and (
                        proof.get("ok") is not True
                        or proof.get("fresh_process_verified") is not True
                    ):
                        raise MigrationError(
                            "restored legacy topology proof failed: %s"
                            % proof.get(
                                "detail", "fresh-process proof did not pass"
                            )
                        )
                except Exception as rollback_exc:
                    # Local bytes are already restored. Retain proof failure
                    # independently so it cannot strand candidate bytes over
                    # the legacy profile or be mistaken for a local rollback.
                    activation_rollback_error = rollback_exc
        journal["status"] = "incomplete"
        journal["phase"] = "failed-restored" if restore_error is None else "failed-restore-error"
        journal["failure"] = str(exc)
        journal["restored"] = restore_error is None
        if activation_rollback_error is not None:
            journal["activation_rollback_failure"] = str(activation_rollback_error)
        if restore_error is not None:
            journal["restore_failure"] = str(restore_error)
        try:
            _atomic_json(journal_path, journal)
        except Exception:
            pass
        if restore_error is not None:
            raise MigrationError(
                "migration failed and exact restoration also failed; durable evidence retained: %s; %s"
                % (exc, restore_error)
            ) from exc
        if activation_rollback_error is not None:
            raise MigrationError(
                "migration failed; exact prior bytes were restored but activation rollback failed; "
                "durable evidence retained: %s; %s"
                % (exc, activation_rollback_error)
            ) from exc
        raise MigrationError(
            "migration failed and exact prior bytes were restored; durable evidence retained: %s"
            % exc
        ) from exc


def _load_journal(binding: ProfileBinding, operation_id: str) -> Dict[str, Any]:
    path = migration_journal_path(binding, operation_id)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MigrationError("migration journal is missing or malformed: %s" % exc) from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise MigrationError("migration journal has the wrong schema")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise MigrationError("migration journal has an unsupported schema version")
    try:
        binding.assert_same(value["binding"])
    except Exception as exc:
        raise MigrationError("migration journal names a different profile binding: %s" % exc) from exc
    return value


def _load_legacy_manifest(
    binding: ProfileBinding, journal: Mapping[str, Any]
) -> Tuple[pathlib.Path, List[Dict[str, Any]]]:
    backup = pathlib.Path(journal["backup_path"])
    expected = _backup_root(
        binding,
        journal["operation_id"],
        pathlib.Path(journal["backup_root"]),
    )
    if os.path.normcase(os.path.normpath(backup)) != os.path.normcase(os.path.normpath(expected)):
        raise MigrationError("migration journal backup path escapes the bound run root")
    manifest_path = backup / "manifest.json"
    if _sha256(manifest_path) != journal["backup_manifest_sha256"]:
        raise MigrationError("migration backup manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    binding.assert_same(manifest["binding"])
    entries = manifest["entries"]
    _verify_legacy_backup(binding, backup, entries)
    return backup, entries


def _verify_current_post_migration(
    binding: ProfileBinding, backup: pathlib.Path, post: Mapping[str, Any]
) -> None:
    expected_paths = set()
    for record in post["records"]:
        path = pathlib.Path(record["source_path"])
        expected_paths.add(os.path.normcase(os.path.normpath(path)))
        if not path.is_file() or _sha256(path) != record["sha256"]:
            raise MigrationError("post-migration bytes changed; rollback refused: %s" % path)
        retained = backup / "post_migration" / record["backup_relative_path"]
        if not retained.is_file() or _sha256(retained) != record["sha256"]:
            raise MigrationError("retained post-migration backup changed: %s" % retained)

    # Restoring a legacy directory would replace it wholesale.  Refuse if a
    # user added anything after migration that the receipt did not own.
    for root in (
        binding.plugin_root,
        binding.profile_root / "agent-hooks" / "sage",
        binding.workspace_root / "sage",
    ):
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and os.path.normcase(os.path.normpath(path)) not in expected_paths:
                raise MigrationError("post-migration directory changed; rollback refused: %s" % path)


def _verify_current_legacy(
    entries: Iterable[Mapping[str, Any]],
) -> None:
    """Refuse to claim restoration unless live legacy bytes match the backup."""

    for entry in entries:
        source = pathlib.Path(entry["source_path"])
        expected_kind = entry["kind"]
        actual_kind = _path_kind(source)
        if actual_kind != expected_kind:
            raise MigrationError(
                "restored legacy path has the wrong type: %s" % source
            )
        if expected_kind is None:
            continue
        expected_files = {
            (record["path"], record["size"], record["sha256"])
            for record in entry["files"]
        }
        actual_files = {
            (record["path"], record["size"], record["sha256"])
            for record in _inventory_tree(source)
        }
        if actual_files != expected_files:
            raise MigrationError(
                "restored legacy bytes do not match the retained backup: %s"
                % source
            )


def _load_child_journal_if_present(
    binding: ProfileBinding,
    child_operation_id: Any,
) -> Optional[receipts.RunJournal]:
    if child_operation_id is None:
        return None
    if not isinstance(child_operation_id, str) or not child_operation_id:
        raise MigrationError("migration journal has an invalid child operation id")
    try:
        child_path = binding.run_journal_path(child_operation_id)
    except Exception as exc:
        raise MigrationError("migration child operation id is unsafe: %s" % exc) from exc
    if not os.path.lexists(os.fspath(child_path)):
        return None
    try:
        child = receipts.load_run_journal(binding, child_operation_id)
    except receipts.ReceiptError as exc:
        raise MigrationError("migration child journal is invalid: %s" % exc) from exc
    if child.operation != "install":
        raise MigrationError(
            "migration child journal has the wrong operation: %s" % child.operation
        )
    return child


def rollback_receiptless_profile(
    *,
    binding: ProfileBinding,
    operation_id: str,
    activation_rollback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """Reverse one completed or recoverable incomplete migration."""

    _require_binding(binding)
    with _acquire_profile_transaction_lock(binding):
        return _rollback_receiptless_profile_locked(
            binding=binding,
            operation_id=operation_id,
            activation_rollback=activation_rollback,
        )


def _rollback_receiptless_profile_locked(
    *,
    binding: ProfileBinding,
    operation_id: str,
    activation_rollback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """Locked rollback/recovery state machine for one explicit migration."""

    _require_binding(binding)
    journal = _load_journal(binding, operation_id)
    status = journal.get("status")
    if status == "rolled_back":
        return {
            "ok": True,
            "operation": "receiptless-profile-migration-rollback",
            "operation_id": operation_id,
        }
    recoverable = {
        "complete",
        "incomplete",
        "child-install-running",
        "rollback-pending-proof",
    }
    if status not in recoverable:
        raise MigrationError("migration journal is not in a recoverable state: %s" % status)
    backup, entries = _load_legacy_manifest(binding, journal)

    if journal.get("restored") is True:
        _verify_current_legacy(entries)
    else:
        if status == "complete":
            post = journal.get("post_migration")
            if not isinstance(post, Mapping):
                raise MigrationError("migration journal is missing post-migration evidence")
            _verify_current_post_migration(binding, backup, post)
            receipt = receipts.load_install_receipt(binding)
            if receipt.semantic_hash != post.get("receipt_semantic_hash"):
                raise MigrationError("post-migration receipt changed; rollback refused")
            _remove_receipt_owned_candidate(binding)
        else:
            child = _load_child_journal_if_present(
                binding, journal.get("child_operation_id")
            )
            if child is not None and not child.is_complete:
                try:
                    profile_installer.resume_incomplete(
                        binding=binding,
                        operation_id=child.operation_id,
                    )
                except profile_installer.InstallError as exc:
                    raise MigrationError(
                        "migration child recovery failed: %s" % exc
                    ) from exc
                child = _load_child_journal_if_present(binding, child.operation_id)

            if binding.receipt_path.is_file():
                _capture_installed_state(binding, backup, "interrupted_candidate")
                _remove_receipt_owned_candidate(binding)
            elif (
                child is not None
                and child.is_complete
                and not (isinstance(child.result, Mapping) and child.result.get("recovered") is True)
            ):
                raise MigrationError(
                    "completed migration child is missing its install receipt"
                )

        _restore_legacy(binding, backup, entries)
        _verify_current_legacy(entries)
        journal["status"] = "rollback-pending-proof"
        journal["phase"] = "rollback-local-restored"
        journal["restored"] = True
        _atomic_json(migration_journal_path(binding, operation_id), journal)

    if activation_rollback is not None:
        plugin_present = _path_kind(binding.plugin_root) == "directory"
        try:
            proof = activation_rollback(
                binding=binding,
                config_records=(),
                allowlist_records=(),
                plugin_present=plugin_present,
            )
            if isinstance(proof, Mapping) and (
                proof.get("ok") is not True
                or proof.get("fresh_process_verified") is not True
            ):
                raise MigrationError(
                    "restored legacy topology proof failed: %s"
                    % proof.get("detail", "fresh-process proof did not pass")
                )
        except Exception as exc:
            journal["rollback_failure"] = str(exc)
            _atomic_json(migration_journal_path(binding, operation_id), journal)
            if isinstance(exc, MigrationError):
                raise
            raise MigrationError(
                "activation rollback failed after local restoration: %s" % exc
            ) from exc

    journal["status"] = "rolled_back"
    journal["phase"] = "rolled-back"
    journal["restored"] = True
    journal.pop("rollback_failure", None)
    _atomic_json(migration_journal_path(binding, operation_id), journal)
    return {
        "ok": True,
        "operation": "receiptless-profile-migration-rollback",
        "operation_id": operation_id,
    }


__all__ = [
    "MigrationError",
    "default_backup_root",
    "migrate_receiptless_profile",
    "migration_journal_path",
    "rollback_receiptless_profile",
]
