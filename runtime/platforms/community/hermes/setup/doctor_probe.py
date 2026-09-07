#!/usr/bin/env python3
"""Public-command, fresh-process behavioral evidence for :mod:`doctor`.

Sage owns the expected profile/workspace contract. Hermes owns discovery,
plugin execution, shell-hook execution, and runtime introspection. The two
meet only through ``hermes hooks activation-proof`` and a nonce-bound JSON
report; Sage never imports a Hermes checkout or injects a Python source path.
"""

from __future__ import annotations

import json
import os
import pathlib
import secrets
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any, Dict

import activation
import hook_config
import profile_binding


_SCHEMA_VERSION = 1
_CHECK_CONTRACT = {
    "hooks": (
        "behaviorally-verified",
        "allow, block, and unverifiable hook outcomes matched",
    ),
    "argv": (
        "executed",
        "configured Hermes hook argv executed in the proof process",
    ),
    "plugin": (
        "discovered",
        "Hermes discovered and enabled the expected plugin",
    ),
    "runtime": (
        "context-delivered",
        "the expected plugin delivered the exact first-turn context",
    ),
    "memory": (
        "behaviorally-verified",
        "exact bound SQLite database opened immutable and rejected a write",
    ),
}


class ProbeError(RuntimeError):
    """The public Hermes process could not produce trustworthy evidence."""


def _existing_file(value: Any, label: str) -> pathlib.Path:
    try:
        path = pathlib.Path(os.fspath(value))
    except TypeError as exc:
        raise ProbeError("%s must be a path" % label) from exc
    if not path.is_absolute() or not path.is_file():
        raise ProbeError("%s is not an existing absolute file: %s" % (label, path))
    return path


def _build_public_expectation(
    binding: profile_binding.ProfileBinding,
    *,
    nonce: str,
    parent_pid: int,
) -> Dict[str, Any]:
    try:
        config_text = binding.config_path.read_text(encoding="utf-8")
        records = hook_config.extract_sage_records(config_text)
        expectation = activation.build_expectation(
            records["config_records"], binding
        )
    except (OSError, ValueError, activation.ActivationError) as exc:
        raise ProbeError(
            "cannot build public Hermes doctor expectation: %s" % exc
        ) from exc
    expectation.update(
        {
            "mode": "doctor",
            "nonce": nonce,
            "parent_pid": parent_pid,
            "binding": binding.to_mapping(),
        }
    )
    return expectation


def _parse_last_report(stdout: str) -> Mapping[str, Any]:
    for line in reversed(stdout.splitlines()):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, Mapping):
            return value
    raise ProbeError("public Hermes doctor proof emitted no JSON report")


def validate_child_report(
    report: Any,
    *,
    binding: profile_binding.ProfileBinding,
    nonce: str,
    parent_pid: int,
) -> Dict[str, Any]:
    """Fail closed unless one complete public Hermes report is exact."""

    if not isinstance(report, Mapping):
        raise ProbeError("fresh probe evidence is not a mapping")
    required_top = {
        "ok",
        "mode",
        "schema_version",
        "surface",
        "nonce",
        "pid",
        "parent_pid",
        "read_only",
        "checks",
        "errors",
    }
    if not required_top.issubset(report):
        raise ProbeError("fresh probe evidence is missing a required field")
    if report.get("ok") is not True or report.get("errors") != []:
        raise ProbeError("fresh probe evidence reports a failed Hermes proof")
    if report.get("mode") != "doctor" or report.get("surface") != "cli":
        raise ProbeError("fresh probe evidence names the wrong mode or surface")
    if report.get("schema_version") != _SCHEMA_VERSION:
        raise ProbeError("fresh probe evidence has an unsupported schema")
    if report.get("nonce") != nonce:
        raise ProbeError("fresh probe evidence nonce does not match")
    pid = report.get("pid")
    if (
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
        or pid == parent_pid
    ):
        raise ProbeError("fresh probe evidence did not come from a child process")
    if report.get("parent_pid") != parent_pid:
        raise ProbeError("fresh probe evidence names the wrong parent process")
    if report.get("read_only") is not True:
        raise ProbeError("fresh probe evidence is not read-only")

    checks = report.get("checks")
    if not isinstance(checks, Mapping) or set(checks) != set(_CHECK_CONTRACT):
        raise ProbeError("fresh probe evidence does not contain exactly five checks")
    normalized: Dict[str, Dict[str, Any]] = {}
    for name, (state, detail) in _CHECK_CONTRACT.items():
        item = checks.get(name)
        expected_keys = {"state", "verified", "detail"}
        if name == "memory":
            expected_keys.add("memory_db_path")
        if not isinstance(item, Mapping) or set(item) != expected_keys:
            raise ProbeError("fresh probe %s evidence is malformed" % name)
        if (
            item.get("state") != state
            or item.get("verified") is not True
            or item.get("detail") != detail
        ):
            raise ProbeError("fresh probe %s evidence did not verify its tier" % name)
        if name == "memory" and item.get("memory_db_path") != os.fspath(
            binding.memory_db_path
        ):
            raise ProbeError(
                "fresh probe did not verify the exact bound memory database"
            )
        normalized[name] = dict(item)

    return {
        "fresh_process_verified": True,
        "read_only": True,
        "probe_pid": pid,
        "checks": normalized,
    }


def probe(
    *,
    binding: profile_binding.ProfileBinding,
    bash_path: str,
    hermes_command: Sequence[str],
    timeout: int | None = None,
) -> Dict[str, Any]:
    """Run the public Hermes doctor proof in one fresh read-only process."""

    if isinstance(hermes_command, (str, bytes)):
        raise ProbeError("hermes_command must be an argv sequence, not text")
    command = tuple(hermes_command)
    if not command or any(not isinstance(item, str) or not item for item in command):
        raise ProbeError(
            "hermes_command must contain one or more non-empty argv items"
        )
    _existing_file(bash_path, "bash_path")

    nonce = secrets.token_hex(24)
    parent_pid = os.getpid()
    expectation = _build_public_expectation(
        binding, nonce=nonce, parent_pid=parent_pid
    )
    if timeout is None:
        # The child executes these probes serially. Keep the existing bounded
        # 60-second non-probe allowance, plus each actual invocation's declared
        # hook budget; an unexecuted hook contributes nothing. Explicit caller
        # timeouts remain exact. This changes no individual hook timeout.
        timeout = 60 + sum(
            expectation["shell_hooks"][item["hook_index"]]["timeout"]
            for item in expectation["policy_probes"]
        )
    descriptor, raw_path = tempfile.mkstemp(
        prefix="sage-hermes-doctor-", suffix=".json"
    )
    expectation_path = pathlib.Path(raw_path)
    env = os.environ.copy()
    env["HERMES_HOME"] = os.fspath(binding.collection_root)
    env["HERMES_ACTIVATION_PROOF_READ_ONLY"] = "1"
    env["HERMES_ENABLE_PROJECT_PLUGINS"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NO_COLOR"] = "1"
    env.pop("HERMES_SAFE_MODE", None)
    env.pop("HERMES_ACCEPT_HOOKS", None)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(expectation, handle, sort_keys=True)
        try:
            completed = subprocess.run(
                list(command)
                + [
                    "--profile",
                    binding.profile_id,
                    "hooks",
                    "activation-proof",
                    "--surface",
                    "cli",
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
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProbeError(
                "public Hermes doctor proof could not complete: %s" % exc
            ) from exc
        report = _parse_last_report(completed.stdout)
        if completed.returncode != 0 or report.get("ok") is not True:
            raise ProbeError(
                "public Hermes doctor proof failed (rc=%d): %s"
                % (
                    completed.returncode,
                    report.get("errors") or completed.stderr.strip()[-1000:],
                )
            )
        return validate_child_report(
            report,
            binding=binding,
            nonce=nonce,
            parent_pid=parent_pid,
        )
    finally:
        try:
            expectation_path.unlink()
        except OSError:
            pass


__all__ = ["ProbeError", "probe", "validate_child_report"]
