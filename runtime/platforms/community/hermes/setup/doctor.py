#!/usr/bin/env python3
"""Behavior-state doctor for the Hermes Sage install (spec 5.9.1-3).

READ-ONLY. For every surface the doctor reports the deepest state it can
honestly reach: present, registered, discovered, executed, context-delivered,
or behaviorally-verified. Only the last applicable state counts as passing —
a file existing is not a hook firing, and a hook firing is not the policy
holding.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import shlex
from collections.abc import Callable, Mapping
from typing import Any, Dict, List, Optional

import hook_config
import profile_binding
import receipts
from profile_installer import (
    _binding_mismatches,
    _config_binding_block,
    _expected_fields,
)


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_STATE_RANK = {
    "failed": -1,
    "present": 0,
    "registered": 1,
    "discovered": 2,
    "executed": 3,
    "context-delivered": 4,
    "behaviorally-verified": 5,
}

_STATIC_STATE = {
    "binding": "registered",
    "receipt": "present",
    "config_policy": "registered",
    "hooks": "present",
    "argv": "registered",
    "plugin": "present",
    "runtime": "present",
    "memory": "present",
    "version": "present",
}

_REQUIRED_STATE = {
    **_STATIC_STATE,
    "hooks": "behaviorally-verified",
    "argv": "executed",
    "plugin": "discovered",
    "runtime": "context-delivered",
    "memory": "behaviorally-verified",
}


def _passed(state: str, required_state: str) -> bool:
    return _STATE_RANK[state] >= _STATE_RANK[required_state]


def _check(name: str, ok: bool, detail: str) -> Dict[str, Any]:
    state = _STATIC_STATE[name] if ok else "failed"
    required_state = _REQUIRED_STATE[name]
    return {
        "name": name,
        "state": state,
        "required_state": required_state,
        "passed": _passed(state, required_state),
        "detail": detail,
    }


def _apply_behavioral_evidence(
    checks: List[Dict[str, Any]],
    evidence: Any,
    *,
    binding: profile_binding.ProfileBinding,
) -> None:
    """Promote checks only from explicit read-only fresh-process evidence."""

    if not isinstance(evidence, Mapping):
        return
    if evidence.get("fresh_process_verified") is not True:
        return
    if evidence.get("read_only") is not True:
        return
    probed_checks = evidence.get("checks")
    if not isinstance(probed_checks, Mapping):
        return

    by_name = {check["name"]: check for check in checks}
    for name, probed in probed_checks.items():
        check = by_name.get(name)
        if check is None or not isinstance(probed, Mapping):
            continue
        if check["state"] == "failed":
            continue
        state = probed.get("state")
        if probed.get("verified") is not True or state not in {
            "discovered",
            "executed",
            "context-delivered",
            "behaviorally-verified",
        }:
            continue
        if name == "memory":
            reported_db = probed.get("memory_db_path")
            if reported_db is None or os.fspath(reported_db) != os.fspath(
                binding.memory_db_path
            ):
                check["detail"] = (
                    "behavioral probe did not verify the exact bound workspace database: %s"
                    % binding.memory_db_path
                )
                continue
        check["state"] = state
        check["passed"] = _passed(state, check["required_state"])
        if probed.get("detail"):
            check["detail"] = str(probed["detail"])


def _command_argv(command: str) -> Optional[List[str]]:
    """Split the already decoded YAML command like Hermes does."""

    try:
        return shlex.split(command)
    except ValueError:
        return None


def _sage_commands(config_text: str) -> List[str]:
    """Use the same validated, decoded hook records as the installer."""

    records = hook_config.extract_sage_records(config_text)
    return [record["command"] for record in records["config_records"]]


def diagnose(
    binding: profile_binding.ProfileBinding,
    *,
    bash_path: str,
    behavioral_probe: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Profile-scoped diagnostic; never mutates anything it inspects.

    ``behavioral_probe``, when supplied, must run in a fresh process and remain
    read-only. Static inspection alone is intentionally capped at ``present``
    or ``registered``.
    """

    checks: List[Dict[str, Any]] = []
    profile = binding.profile_root
    config_path = profile / "config.yaml"
    try:
        config_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        config_text = ""
        checks.append(_check("binding", False, "config unreadable: %s" % exc))

    if config_text:
        try:
            block = _config_binding_block(config_text)
            mismatched = _binding_mismatches(block, _expected_fields(binding))
            checks.append(
                _check(
                    "binding",
                    not mismatched,
                    "config binding matches the selected profile"
                    if not mismatched
                    else "binding mismatch: %s" % ", ".join(mismatched),
                )
            )
        except Exception as exc:
            checks.append(_check("binding", False, str(exc)))

    receipt = None
    try:
        receipt = receipts.load_install_receipt(binding)
    except Exception as exc:
        checks.append(_check("receipt", False, "receipt load failed: %s" % exc))
    if receipt is not None:
        drifted = []
        for target in receipt.managed_targets:
            root = binding.profile_root if target.owner == "profile" else binding.workspace_root
            dest = root / target.relative_path.replace("/", os.sep)
            if not dest.is_file() or _sha256(dest) != target.sha256:
                drifted.append(target.relative_path)
        checks.append(
            _check(
                "receipt",
                not drifted,
                "all managed hashes match"
                if not drifted
                else "drifted: %s" % ", ".join(drifted[:4]),
            )
        )

    if config_text:
        validation = hook_config.validate_candidate_config(config_text)
        checks.append(
            _check(
                "config_policy",
                validation["ok"],
                "exact 7+4 registry holds"
                if validation["ok"]
                else "; ".join(validation["errors"][:2]),
            )
        )

    scripts = [entry["script"] for entry in hook_config.expected_registry()]
    scripts.append("sage-hermes-gate.sh")
    missing = [s for s in scripts if not (profile / "hooks" / s).is_file()]
    checks.append(
        _check(
            "hooks",
            not missing,
            "all 12 hook scripts present"
            if not missing
            else "missing: %s" % ", ".join(missing[:4]),
        )
    )

    argv_ok = True
    argv_detail = "argv is registered to an existing bash executable"
    if not os.path.isfile(bash_path):
        argv_ok = False
        argv_detail = "bash executable not found: %s" % bash_path
    else:
        seen = set()
        try:
            commands = _sage_commands(config_text)
        except ValueError as exc:
            commands = []
            argv_ok = False
            argv_detail = "hook commands could not be validated: %s" % exc
        for command in commands:
            argv = _command_argv(command)
            is_session = bool(argv and len(argv) == 2 and
                              argv[1].replace("\\", "/").endswith("/sage-session-init.sh"))
            if not argv or (len(argv) != 3 and not is_session):
                argv_ok = False
                argv_detail = "command does not split to bash/session or bash/adapter/script: %s" % command[:60]
                break
            exe = argv[0]
            if exe in seen:
                continue
            seen.add(exe)
            if not os.path.isfile(exe):
                argv_ok = False
                argv_detail = "argv[0] is not an existing file: %s" % exe
                break

    checks.append(_check("argv", argv_ok, argv_detail))

    plugin_files = ("__init__.py", "plugin.yaml", "profile_binding.py")
    missing_plugin = [
        name for name in plugin_files if not (profile / "plugins" / "sage" / name).is_file()
    ]
    checks.append(
        _check(
            "plugin",
            not missing_plugin,
            "plugin package present"
            if not missing_plugin
            else "missing: %s" % ", ".join(missing_plugin),
        )
    )

    runtime_ok = (
        (binding.workspace_root / "sage" / "VERSION").is_file()
        and (binding.workspace_root / "sage" / "runtime" / "tools").is_dir()
    )
    checks.append(
        _check(
            "runtime",
            runtime_ok,
            "bound workspace runtime complete"
            if runtime_ok
            else "workspace sage/VERSION or runtime/tools missing",
        )
    )

    memory_ok = (binding.workspace_root / ".sage-memory" / "memory.db").is_file()
    checks.append(
        _check(
            "memory",
            memory_ok,
            "workspace-isolated memory database present"
            if memory_ok
            else "workspace .sage-memory/memory.db missing",
        )
    )

    version_ok = False
    version_detail = "receipt or VERSION missing"
    if receipt is not None and (binding.workspace_root / "sage" / "VERSION").is_file():
        on_disk = (binding.workspace_root / "sage" / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
        version_ok = on_disk == receipt.source_version
        version_detail = (
            "framework/profile versions agree (%s)" % on_disk
            if version_ok
            else "receipt %s != runtime VERSION %s" % (receipt.source_version, on_disk)
        )
    checks.append(_check("version", version_ok, version_detail))

    if behavioral_probe is not None:
        try:
            evidence = behavioral_probe(binding=binding, bash_path=bash_path)
        except Exception:
            evidence = None
        _apply_behavioral_evidence(checks, evidence, binding=binding)

    return {
        "ok": all(check["passed"] for check in checks),
        "roots": {
            "collection_root": os.fspath(binding.collection_root),
            "profile_root": os.fspath(binding.profile_root),
            "workspace_root": os.fspath(binding.workspace_root),
            "receipt_path": os.fspath(binding.receipt_path),
        },
        "checks": checks,
    }
