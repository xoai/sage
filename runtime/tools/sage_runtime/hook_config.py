"""Validated, idempotent hook configuration merges for supported platforms."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from .io import atomic_write_json


class HookConfigError(ValueError):
    """Raised before a malformed hook configuration can be replaced."""


_MANAGED_HOOK_SCRIPTS = (
    "sage-session-init.sh",
    "sage-route-context.py",
    "sage-strict-gate.py",
    "sage-learning-recall.py",
    "sage-learning-observe.py",
    "sage-reflect-stop.py",
    "sage-pre-llm.py",
    "sage-pre-tool.py",
    "sage-reflect-checkpoint.py",
)


def _managed_identity(command: object) -> str | None:
    if not isinstance(command, str):
        return None
    lowered = command.casefold()
    return next((name for name in _MANAGED_HOOK_SCRIPTS if name in lowered), None)


def _backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    backup = path.with_name(f"{path.name}.malformed-{stamp}.bak")
    shutil.copy2(path, backup)
    return backup


def _reject(path: Path, message: str, backup_malformed: bool) -> HookConfigError:
    suffix = ""
    if backup_malformed and path.is_file():
        suffix = f"; backup: {_backup(path)}"
    return HookConfigError(f"malformed hook config {path}: {message}{suffix}")


def _validate_hooks_mapping(
    path: Path, loaded: Mapping[str, Any], backup_malformed: bool
) -> dict[str, Any]:
    hooks = loaded.get("hooks", {})
    if not isinstance(hooks, Mapping):
        raise _reject(path, "hooks must be a mapping", backup_malformed)
    for event, entries in hooks.items():
        if not isinstance(event, str) or not isinstance(entries, list):
            raise _reject(path, "hook events must contain lists", backup_malformed)
    return dict(loaded)


def validate_hook_config(
    path: Path, platform: str, *, backup_malformed: bool = False
) -> dict[str, Any]:
    """Parse one platform config without fabricating an empty replacement."""

    config = Path(path)
    if not config.is_file():
        return {}
    try:
        if platform == "claude-code":
            loaded = json.loads(config.read_text(encoding="utf-8-sig"))
        elif platform == "hermes":
            loaded = yaml.safe_load(config.read_text(encoding="utf-8-sig")) or {}
        else:
            raise HookConfigError(f"unsupported hook platform: {platform}")
    except (json.JSONDecodeError, yaml.YAMLError, UnicodeError) as exc:
        raise _reject(config, str(exc), backup_malformed) from exc
    if not isinstance(loaded, Mapping):
        raise _reject(config, "document must be a mapping", backup_malformed)
    return _validate_hooks_mapping(config, loaded, backup_malformed)


def _claude_has_command(entries: list[object], command: str) -> bool:
    for group in entries:
        if not isinstance(group, Mapping):
            continue
        hooks = group.get("hooks", [])
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if isinstance(hook, Mapping) and hook.get("command") == command:
                return True
    return False


def _replace_claude_managed(entries: list[object], command: str) -> None:
    identity = _managed_identity(command)
    if identity is None:
        return
    retained: list[object] = []
    for group in entries:
        if not isinstance(group, Mapping):
            retained.append(group)
            continue
        raw_hooks = group.get("hooks", [])
        if not isinstance(raw_hooks, list):
            retained.append(group)
            continue
        filtered = [
            hook
            for hook in raw_hooks
            if not (
                isinstance(hook, Mapping)
                and _managed_identity(hook.get("command")) == identity
            )
        ]
        if filtered:
            updated = dict(group)
            updated["hooks"] = filtered
            retained.append(updated)
    entries[:] = retained


def install_claude_hooks(
    path: Path,
    *,
    session_command: str,
    route_command: str,
    gate_command: str,
    learning_recall_command: str | None = None,
    learning_observe_command: str | None = None,
    reflect_command: str | None = None,
) -> None:
    config = Path(path)
    loaded = validate_hook_config(config, "claude-code", backup_malformed=True)
    hooks = loaded.setdefault("hooks", {})
    registrations: list[tuple[str, str, str]] = [
        ("SessionStart", "startup|resume|clear|compact", session_command),
        ("UserPromptSubmit", "", route_command),
        ("PreToolUse", ".*", gate_command),
    ]
    if learning_recall_command:
        registrations.append(("UserPromptSubmit", "", learning_recall_command))
    if learning_observe_command:
        registrations.append(("PostToolUse", ".*", learning_observe_command))
    if reflect_command:
        registrations.append(("Stop", "", reflect_command))
    for event, matcher, command in registrations:
        entries = hooks.setdefault(event, [])
        _replace_claude_managed(entries, command)
        if not _claude_has_command(entries, command):
            entries.append(
                {
                    "matcher": matcher,
                    "hooks": [{"type": "command", "command": command}],
                }
            )
    atomic_write_json(config, loaded)


def _atomic_write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            yaml.safe_dump(dict(value), handle, sort_keys=False, allow_unicode=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def install_hermes_hooks(
    path: Path,
    *,
    route_command: str,
    gate_command: str,
    learning_recall_command: str | None = None,
    learning_observe_command: str | None = None,
    reflect_command: str | None = None,
) -> None:
    config = Path(path)
    loaded = validate_hook_config(config, "hermes", backup_malformed=True)
    hooks = loaded.setdefault("hooks", {})
    registrations: list[tuple[str, dict[str, str]]] = [
        ("pre_llm_call", {"command": route_command}),
        ("pre_tool_call", {"command": gate_command, "matcher": ".*"}),
    ]
    if learning_recall_command:
        registrations.append(("pre_llm_call", {"command": learning_recall_command}))
    if learning_observe_command:
        registrations.extend(
            (
                ("post_tool_call", {"command": learning_observe_command}),
                ("on_session_end", {"command": learning_observe_command}),
                ("on_session_finalize", {"command": learning_observe_command}),
            )
        )
    if reflect_command:
        registrations.append(("pre_verify", {"command": reflect_command}))
    for event, registration in registrations:
        entries = hooks.setdefault(event, [])
        identity = _managed_identity(registration["command"])
        if identity is not None:
            entries[:] = [
                item
                for item in entries
                if not (
                    isinstance(item, Mapping)
                    and _managed_identity(item.get("command")) == identity
                )
            ]
        if not any(
            isinstance(item, Mapping) and item.get("command") == registration["command"]
            for item in entries
        ):
            entries.append(registration)
    _atomic_write_yaml(config, loaded)
