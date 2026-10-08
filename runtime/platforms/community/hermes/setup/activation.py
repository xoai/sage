#!/usr/bin/env python3
"""Fresh-process Hermes activation proof and reversible consent handling.

The installer owns candidate files/config.  This module owns the one external
Hermes authority needed to prove those bytes: the selected profile's shell-hook
consent file.  It snapshots that file byte-exactly, merges only the approved
Sage ``(event, command)`` pairs, runs Hermes's canonical activation-proof
command in distinct CLI and Gateway processes, and can restore the prior
consent bytes if either proof or a later transaction phase fails.
"""

from __future__ import annotations

import datetime as _datetime
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

import profile_binding
import hook_config


class ActivationError(RuntimeError):
    """Fresh-process activation could not be proved safely."""


def _validated_command_argv(value: Any, label: str) -> Tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ActivationError("%s must be a non-empty JSON string array" % label)
    executable = pathlib.Path(value[0])
    if not executable.is_absolute() or not executable.is_file():
        raise ActivationError(
            "%s argv[0] is not an absolute executable file: %s"
            % (label, value[0])
        )
    return (os.fspath(executable.resolve()), *value[1:])


def resolve_hermes_command() -> Tuple[str, ...]:
    """Resolve one public Hermes launcher without inspecting its installation.

    Normal users need only ``hermes`` on PATH.  Packaged, embedded, or otherwise
    non-standard installs may provide ``SAGE_HERMES_COMMAND`` as a JSON argv
    array.  Sage never discovers an adjacent venv, imports ``hermes_cli``, or
    requires a source checkout; the public CLI is the integration boundary.
    """

    explicit = os.environ.get("SAGE_HERMES_COMMAND")
    if explicit is not None:
        try:
            parsed = json.loads(explicit)
        except ValueError as exc:
            raise ActivationError(
                "SAGE_HERMES_COMMAND must be a JSON argv array: %s" % exc
            ) from exc
        return _validated_command_argv(parsed, "SAGE_HERMES_COMMAND")

    executable_value = shutil.which("hermes")
    if not executable_value:
        raise ActivationError("Hermes executable is not available on PATH")
    executable = pathlib.Path(os.path.abspath(executable_value)).resolve()
    if not executable.is_file():
        raise ActivationError(
            "Hermes executable on PATH is not a file: %s" % executable
        )
    return (os.fspath(executable),)


@dataclass(frozen=True)
class FileSnapshot:
    path: pathlib.Path
    existed: bool
    data: bytes


def _atomic_write(path: pathlib.Path, data: bytes) -> None:
    """Same-directory mkstemp write + fsync + os.replace.

    The previous PID-derived ``<name>.tmp-<pid>`` name was predictable and
    vulnerable to a TOCTOU redirect: a pre-placed symlink at that path
    silently followed the attacker target, and a same-pid second write
    collided. ``tempfile.mkstemp`` creates the file with ``O_CREAT |
    O_EXCL`` in ``path.parent``, so the destination is created atomically
    and any pre-existing entry (file, symlink, directory) makes the helper
    fail closed before any bytes are written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(
        prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent)
    )
    tmp = pathlib.Path(raw_tmp)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def allowlist_path(binding: profile_binding.ProfileBinding) -> pathlib.Path:
    return binding.profile_root / "shell-hooks-allowlist.json"


def snapshot_allowlist(binding: profile_binding.ProfileBinding) -> FileSnapshot:
    path = allowlist_path(binding)
    if path.is_file():
        return FileSnapshot(path=path, existed=True, data=path.read_bytes())
    if os.path.lexists(os.fspath(path)):
        raise ActivationError("shell-hook allowlist is not a regular file: %s" % path)
    return FileSnapshot(path=path, existed=False, data=b"")


def restore_allowlist(snapshot: FileSnapshot) -> None:
    if snapshot.existed:
        _atomic_write(snapshot.path, snapshot.data)
    elif os.path.lexists(os.fspath(snapshot.path)):
        snapshot.path.unlink()


def _approval_record(event: str, command: str) -> Dict[str, Any]:
    script_mtime = None
    try:
        import shlex

        argv = shlex.split(command)
        script = next((part for part in argv if part.lower().endswith((".sh", ".bash"))), None)
        if script and os.path.isfile(script):
            script_mtime = _datetime.datetime.fromtimestamp(
                os.path.getmtime(script), tz=_datetime.timezone.utc
            ).isoformat().replace("+00:00", "Z")
    except (OSError, ValueError):
        script_mtime = None
    return {
        "event": event,
        "command": command,
        "approved_at": _datetime.datetime.now(tz=_datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "script_mtime_at_approval": script_mtime,
    }


def merge_allowlist(
    binding: profile_binding.ProfileBinding,
    records: Iterable[Mapping[str, Any]],
) -> None:
    path = allowlist_path(binding)
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError) as exc:
        raise ActivationError("shell-hook allowlist is unreadable JSON: %s" % exc) from exc
    if not isinstance(current, dict):
        raise ActivationError("shell-hook allowlist must be a JSON object")
    approvals = current.get("approvals", [])
    if not isinstance(approvals, list):
        raise ActivationError("shell-hook allowlist approvals must be an array")

    pairs = []
    for record in records:
        event = record.get("event")
        command = record.get("command")
        if not isinstance(event, str) or not event or not isinstance(command, str) or not command:
            raise ActivationError("allowlist record must name non-empty event and command")
        pairs.append((event, command))
    pair_set = set(pairs)
    existing_by_pair = {
        (item.get("event"), item.get("command")): item
        for item in approvals
        if isinstance(item, dict)
    }
    preserved = [
        item
        for item in approvals
        if not (
            isinstance(item, dict)
            and (item.get("event"), item.get("command")) in pair_set
        )
    ]
    replacements = []
    for event, command in pairs:
        candidate = _approval_record(event, command)
        existing = existing_by_pair.get((event, command))
        if (
            isinstance(existing, dict)
            and existing.get("script_mtime_at_approval")
            == candidate.get("script_mtime_at_approval")
        ):
            replacements.append(existing)
        else:
            replacements.append(candidate)
    current["approvals"] = preserved + replacements
    _atomic_write(
        path,
        (json.dumps(current, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def _validated_allowlist_pairs(
    records: Iterable[Mapping[str, Any]],
) -> Tuple[Tuple[str, str], ...]:
    pairs = []
    for record in records:
        event = record.get("event")
        command = record.get("command")
        if not isinstance(event, str) or not event or not isinstance(command, str) or not command:
            raise ActivationError("allowlist record must name non-empty event and command")
        pairs.append((event, command))
    if len(set(pairs)) != len(pairs):
        raise ActivationError("allowlist records contain a duplicate event/command pair")
    return tuple(pairs)


def _read_allowlist(binding: profile_binding.ProfileBinding) -> Dict[str, Any]:
    path = allowlist_path(binding)
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError) as exc:
        raise ActivationError("shell-hook allowlist is unreadable JSON: %s" % exc) from exc
    if not isinstance(current, dict):
        raise ActivationError("shell-hook allowlist must be a JSON object")
    approvals = current.get("approvals", [])
    if not isinstance(approvals, list):
        raise ActivationError("shell-hook allowlist approvals must be an array")
    _validated_allowlist_pairs(
        item for item in approvals if isinstance(item, Mapping)
    )
    if any(not isinstance(item, Mapping) for item in approvals):
        raise ActivationError("shell-hook allowlist contains a non-object approval")
    return current


def remove_allowlist_records(
    binding: profile_binding.ProfileBinding,
    records: Iterable[Mapping[str, Any]],
) -> int:
    """Remove only exact receipt-owned consent pairs, preserving all others."""

    pair_set = set(_validated_allowlist_pairs(records))
    current = _read_allowlist(binding)
    approvals = current.get("approvals", [])
    preserved = [
        item
        for item in approvals
        if (item.get("event"), item.get("command")) not in pair_set
    ]
    removed = len(approvals) - len(preserved)
    if removed != len(pair_set):
        raise ActivationError(
            "expected to remove %d exact Sage consent pairs, removed %d"
            % (len(pair_set), removed)
        )
    current["approvals"] = preserved
    _atomic_write(
        allowlist_path(binding),
        (json.dumps(current, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return removed


def _current_allowlist_records(
    binding: profile_binding.ProfileBinding,
) -> Tuple[Dict[str, str], ...]:
    current = _read_allowlist(binding)
    pairs = _validated_allowlist_pairs(current.get("approvals", []))
    return tuple(
        {"event": event, "command": command}
        for event, command in sorted(pairs)
    )


def _hook_sort_key(record: Mapping[str, Any]) -> tuple:
    return (
        record["event"],
        record.get("matcher") or "",
        record["command"],
        record["timeout"],
        record["fail_closed"],
    )


def build_expectation(
    config_records: Iterable[Mapping[str, Any]],
    binding: profile_binding.ProfileBinding,
) -> Dict[str, Any]:
    hooks = []
    for record in config_records:
        hooks.append(
            {
                "event": record["event"],
                "matcher": record.get("matcher"),
                "command": record["command"],
                "timeout": 30,
                "fail_closed": bool(record.get("fail_closed")),
            }
        )
        # A stale host must not prove activation by silently ignoring the new
        # opt-in request. Required capabilities come from the installed platform,
        # not from the potentially incomplete configuration being checked.
        for entry in hook_config.expected_registry():
            if (entry.get("file_preview_patterns") and entry["event"] == record["event"]
                    and entry["script"] in hook_config._entry_scripts(record["command"])):
                hooks[-1]["file_preview_patterns"] = list(entry["file_preview_patterns"])
    hooks = sorted(hooks, key=_hook_sort_key)
    probe_index = next(
        (
            index
            for index, record in enumerate(hooks)
            if record["event"] == "pre_tool_call"
            and record["fail_closed"] is True
            and record.get("matcher")
            and ("write_file" in record["matcher"] or "patch" in record["matcher"])
            and "sage-secrets-gate.sh" in record["command"]
        ),
        None,
    )
    if probe_index is None:
        raise ActivationError("no blocking write hook is available for policy probes")
    safe_path = os.fspath(binding.state_root / "activation-proof.md")
    return {
        "plugin": {"key": "sage", "name": "sage"},
        "shell_hooks": hooks,
        "policy_probes": [
            {
                "name": "allow",
                "hook_index": probe_index,
                "expected": "allow",
                "payload": {
                    "tool_name": "write_file",
                    "tool_input": {
                        "path": safe_path,
                        "content": "activation proof safe payload\n",
                    },
                    "cwd": os.fspath(binding.workspace_root),
                },
            },
            {
                "name": "block",
                "hook_index": probe_index,
                "expected": "block",
                "payload": {
                    "tool_name": "write_file",
                    "tool_input": {
                        "path": safe_path,
                        "content": (
                            "PAY_KEY=" + "pfk_" + "live_"
                            + "9Fq2XvR7tLpZ4NcW8HbY3sKd\n"
                        ),
                    },
                    "cwd": os.fspath(binding.workspace_root),
                },
            },
            {
                "name": "unverifiable",
                "hook_index": probe_index,
                "expected": "unverifiable",
                "payload": {
                    "tool_name": "write_file",
                    "tool_input": {
                        "content": "activation proof unresolved payload\n",
                    },
                    "cwd": os.fspath(binding.workspace_root),
                },
            },
        ],
    }


def _parse_report(stdout: str) -> Mapping[str, Any]:
    for line in reversed(stdout.splitlines()):
        if not line.strip():
            continue
        try:
            report = json.loads(line)
        except ValueError:
            continue
        if isinstance(report, dict):
            return report
    raise ActivationError("Hermes activation proof emitted no JSON report")


def _topology_expectation(
    *,
    config_records: Iterable[Mapping[str, Any]],
    allowlist_records: Iterable[Mapping[str, Any]],
    plugin_present: bool,
) -> Dict[str, Any]:
    owned_hooks = [
        {
            "event": record["event"],
            "matcher": record.get("matcher"),
            "command": record["command"],
            "timeout": 30,
            "fail_closed": bool(record.get("fail_closed")),
            **({"file_preview_patterns": list(record["file_preview_patterns"])}
               if "file_preview_patterns" in record else {}),
        }
        for record in config_records
    ]
    owned_hooks = sorted(owned_hooks, key=_hook_sort_key)
    return {
        "mode": "topology",
        "plugin": {"key": "sage", "name": "sage", "present": plugin_present},
        "owned_shell_hooks": owned_hooks,
        "owned_present": plugin_present,
        "allowlist_pairs": [
            {"event": event, "command": command}
            for event, command in sorted(_validated_allowlist_pairs(allowlist_records))
        ],
    }


def run_fresh_topology_proof(
    *,
    binding: profile_binding.ProfileBinding,
    config_records: Iterable[Mapping[str, Any]],
    allowlist_records: Iterable[Mapping[str, Any]],
    plugin_present: bool,
    hermes_command: Sequence[str],
    timeout: int = 60,
) -> Dict[str, Any]:
    """Prove exact consent plus configured=registered on CLI and Gateway."""

    if not hermes_command:
        raise ActivationError("Hermes command is empty")
    expectation = _topology_expectation(
        config_records=config_records,
        allowlist_records=allowlist_records,
        plugin_present=plugin_present,
    )
    binding.runs_root.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(
        prefix="topology-expectation-", suffix=".json", dir=str(binding.runs_root)
    )
    expectation_path = pathlib.Path(raw_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(expectation, handle, sort_keys=True)
        env = os.environ.copy()
        env["HERMES_HOME"] = os.fspath(binding.collection_root)
        env["NO_COLOR"] = "1"
        env["HERMES_ACTIVATION_PROOF_READ_ONLY"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("HERMES_SAFE_MODE", None)
        env.pop("HERMES_ACCEPT_HOOKS", None)
        reports: Dict[str, Mapping[str, Any]] = {}
        for surface in ("cli", "gateway"):
            completed = subprocess.run(
                list(hermes_command)
                + [
                    "--profile",
                    binding.profile_id,
                    "hooks",
                    "activation-proof",
                    "--surface",
                    surface,
                    "--expectation-file",
                    os.fspath(expectation_path),
                ],
                cwd=binding.workspace_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            report = _parse_report(completed.stdout)
            reports[surface] = report
            if completed.returncode != 0 or report.get("ok") is not True:
                raise ActivationError(
                    "%s topology proof failed (rc=%s): %s"
                    % (
                        surface,
                        completed.returncode,
                        report.get("errors") or completed.stderr.strip(),
                    )
                )
        pids = [reports[surface].get("pid") for surface in ("cli", "gateway")]
        if any(not isinstance(pid, int) or pid == os.getpid() for pid in pids):
            raise ActivationError("topology reports are not fresh subprocesses")
        if len(set(pids)) != 2:
            raise ActivationError("CLI and Gateway topology proofs must use distinct processes")
        return {
            "ok": True,
            "fresh_process_verified": True,
            "detail": "fresh CLI and Gateway topology proofs passed",
            "surfaces": {
                surface: {"ok": True, "pid": reports[surface]["pid"]}
                for surface in ("cli", "gateway")
            },
        }
    finally:
        try:
            expectation_path.unlink()
        except OSError:
            pass


def run_fresh_process_proof(
    *,
    binding: profile_binding.ProfileBinding,
    config_records: Iterable[Mapping[str, Any]],
    allowlist_records: Iterable[Mapping[str, Any]],
    hermes_command: Sequence[str],
    timeout: int = 60,
) -> Dict[str, Any]:
    if not hermes_command:
        raise ActivationError("Hermes command is empty")
    expectation = build_expectation(config_records, binding)
    binding.runs_root.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(
        prefix="activation-expectation-", suffix=".json", dir=str(binding.runs_root)
    )
    expectation_path = pathlib.Path(raw_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(expectation, handle, sort_keys=True)
        merge_allowlist(binding, allowlist_records)
        env = os.environ.copy()
        env["HERMES_HOME"] = os.fspath(binding.collection_root)
        env["NO_COLOR"] = "1"
        env["HERMES_ACTIVATION_PROOF_READ_ONLY"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("HERMES_SAFE_MODE", None)
        env.pop("HERMES_ACCEPT_HOOKS", None)
        reports: Dict[str, Mapping[str, Any]] = {}
        for surface in ("cli", "gateway"):
            completed = subprocess.run(
                list(hermes_command)
                + [
                    "--profile",
                    binding.profile_id,
                    "hooks",
                    "activation-proof",
                    "--surface",
                    surface,
                    "--expectation-file",
                    os.fspath(expectation_path),
                ],
                cwd=binding.workspace_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            report = _parse_report(completed.stdout)
            reports[surface] = report
            if completed.returncode != 0 or report.get("ok") is not True:
                errors = report.get("errors")
                raise ActivationError(
                    "%s proof failed (rc=%s): %s"
                    % (surface, completed.returncode, errors or completed.stderr.strip())
                )
        pids = [reports[surface].get("pid") for surface in ("cli", "gateway")]
        if any(not isinstance(pid, int) or pid == os.getpid() for pid in pids):
            raise ActivationError("activation reports are not fresh subprocesses")
        if len(set(pids)) != 2:
            raise ActivationError("CLI and Gateway activation must use distinct fresh processes")
        return {
            "ok": True,
            "fresh_process_verified": True,
            "detail": "fresh CLI and Gateway activation proofs passed",
            "surfaces": {
                surface: {
                    "ok": True,
                    "pid": reports[surface]["pid"],
                    "policy_outcomes": [
                        probe.get("outcome")
                        for probe in reports[surface].get("policy_probes", [])
                    ],
                }
                for surface in ("cli", "gateway")
            },
        }
    finally:
        try:
            expectation_path.unlink()
        except OSError:
            pass


def callbacks(
    binding: profile_binding.ProfileBinding,
    hermes_command: Sequence[str],
) -> Tuple[Any, Any]:
    """Return the canonical ``(probe, rollback)`` pair for one install/update.

    The allowlist is snapshotted eagerly at callback creation, not lazily on
    the first probe. The migration rollback path constructs ``probe`` and
    ``rollback`` closures but never invokes ``probe``; the lazy snapshot
    left the rollback closure with no prior bytes to restore, so the
    migration rollback could not undo an in-flight allowlist mutation. Both
    closures now share one immutable creation-time snapshot.

    ``rollback`` honors an explicit ``plugin_present`` argument supplied by
    the migration driver (the post-restoration truth), and falls back to
    deriving it from ``config_records`` only when the caller omits the
    argument for backward compatibility.
    """
    snapshot = snapshot_allowlist(binding)

    def probe(**kwargs: Any) -> Mapping[str, Any]:
        return run_fresh_process_proof(
            binding=binding,
            config_records=kwargs["config_records"],
            allowlist_records=kwargs["allowlist_records"],
            hermes_command=hermes_command,
        )

    def rollback(**kwargs: Any) -> Mapping[str, Any]:
        restore_allowlist(snapshot)
        # Byte-verify the restoration succeeded before consulting Hermes;
        # a partial restore that left prior bytes on disk would silently
        # pass an allowlist-mismatch proof downstream.
        if snapshot.existed:
            current_bytes = snapshot.path.read_bytes()
            if current_bytes != snapshot.data:
                raise ActivationError(
                    "allowlist restoration failed: %s does not match prior bytes"
                    % snapshot.path
                )
        elif os.path.lexists(os.fspath(snapshot.path)):
            raise ActivationError(
                "allowlist restoration failed: %s was previously absent"
                % snapshot.path
            )
        if "plugin_present" in kwargs:
            plugin_present = bool(kwargs["plugin_present"])
        else:
            plugin_present = bool(kwargs["config_records"])
        return run_fresh_topology_proof(
            binding=binding,
            config_records=kwargs["config_records"],
            allowlist_records=_current_allowlist_records(binding),
            plugin_present=plugin_present,
            hermes_command=hermes_command,
        )

    return probe, rollback


def uninstall_callbacks(
    binding: profile_binding.ProfileBinding,
    hermes_command: Sequence[str],
) -> Tuple[Any, Any]:
    snapshot = snapshot_allowlist(binding)

    def absence_probe(**kwargs: Any) -> Mapping[str, Any]:
        remove_allowlist_records(binding, kwargs["allowlist_records"])
        return run_fresh_topology_proof(
            binding=binding,
            config_records=kwargs["config_records"],
            allowlist_records=_current_allowlist_records(binding),
            plugin_present=False,
            hermes_command=hermes_command,
        )

    def rollback(**kwargs: Any) -> Mapping[str, Any]:
        restore_allowlist(snapshot)
        if "plugin_present" in kwargs:
            plugin_present = bool(kwargs["plugin_present"])
        else:
            plugin_present = True
        return run_fresh_topology_proof(
            binding=binding,
            config_records=kwargs["config_records"],
            allowlist_records=_current_allowlist_records(binding),
            plugin_present=plugin_present,
            hermes_command=hermes_command,
        )

    return absence_probe, rollback
