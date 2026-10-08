#!/usr/bin/env python3
"""Public-command contracts for the Hermes behavior-state doctor proof."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SETUP = ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup"
sys.path.insert(0, os.fspath(SETUP))

import doctor_probe  # noqa: E402
import profile_binding  # noqa: E402


def _bash() -> pathlib.Path:
    candidates = [shutil.which("bash"), "C:/Program Files/Git/bin/bash.exe"]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).is_file():
            return pathlib.Path(candidate).resolve()
    pytest.skip("bash is unavailable")


@pytest.fixture()
def installed(tmp_path: pathlib.Path):
    collection = tmp_path / "hermes"
    profile = collection / "profiles" / "alpha"
    workspace = profile / "workspace"
    workspace.mkdir(parents=True)
    binding = profile_binding.ProfileBinding.from_explicit(
        collection_root=collection,
        profile_id="alpha",
        profile_root=profile,
        workspace_root=workspace,
    )
    binding.config_path.write_text("plugins:\n  enabled: [sage]\n", encoding="utf-8")
    return binding, _bash()


def _valid_report(binding, *, nonce: str, parent_pid: int) -> dict:
    return {
        "ok": True,
        "mode": "doctor",
        "schema_version": 1,
        "surface": "cli",
        "nonce": nonce,
        "pid": parent_pid + 1000,
        "parent_pid": parent_pid,
        "read_only": True,
        "checks": {
            "hooks": {
                "state": "behaviorally-verified",
                "verified": True,
                "detail": "allow, block, and unverifiable hook outcomes matched",
            },
            "argv": {
                "state": "executed",
                "verified": True,
                "detail": "configured Hermes hook argv executed in the proof process",
            },
            "plugin": {
                "state": "discovered",
                "verified": True,
                "detail": "Hermes discovered and enabled the expected plugin",
            },
            "runtime": {
                "state": "context-delivered",
                "verified": True,
                "detail": "the expected plugin delivered the exact first-turn context",
            },
            "memory": {
                "state": "behaviorally-verified",
                "verified": True,
                "memory_db_path": os.fspath(binding.memory_db_path),
                "detail": "exact bound SQLite database opened immutable and rejected a write",
            },
        },
        "errors": [],
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda report: report.pop("checks"),
        lambda report: report["checks"].pop("runtime"),
        lambda report: report["checks"]["plugin"].update(verified=False),
        lambda report: report["checks"]["memory"].pop("memory_db_path"),
        lambda report: report.update(pid=os.getpid()),
        lambda report: report.update(nonce="wrong"),
        lambda report: report.update(mode="activation"),
        lambda report: report.update(errors=[{"code": "failed"}]),
    ],
)
def test_parent_validation_rejects_malformed_or_nonfresh_public_evidence(
    installed, mutate
) -> None:
    binding, _bash_path = installed
    nonce = "expected-nonce-0123456789"
    parent_pid = os.getpid()
    report = _valid_report(binding, nonce=nonce, parent_pid=parent_pid)
    mutate(report)

    with pytest.raises(doctor_probe.ProbeError):
        doctor_probe.validate_child_report(
            report,
            binding=binding,
            nonce=nonce,
            parent_pid=parent_pid,
        )


def test_probe_uses_only_public_hermes_command_without_checkout_injection(
    installed, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding, bash = installed
    monkeypatch.delenv("HERMES_PYTHON", raising=False)
    monkeypatch.delenv("HERMES_PYTHON_SRC_ROOT", raising=False)
    monkeypatch.setenv("PYTHONPATH", "parent-sentinel-path")
    monkeypatch.setattr(
        doctor_probe,
        "_build_public_expectation",
        lambda selected, *, nonce, parent_pid: {
            "mode": "doctor",
            "nonce": nonce,
            "parent_pid": parent_pid,
            "binding": selected.to_mapping(),
            "plugin": {"key": "sage", "name": "sage"},
            "shell_hooks": [],
            "policy_probes": [],
        },
    )
    observed: dict = {}

    def fake_run(command, **kwargs):
        assert command[:7] == [
            "fake-hermes",
            "--profile",
            binding.profile_id,
            "hooks",
            "activation-proof",
            "--surface",
            "cli",
        ]
        assert command[7] == "--expectation-file"
        expectation_path = pathlib.Path(command[8])
        expectation = json.loads(expectation_path.read_text(encoding="utf-8"))
        observed["expectation_path"] = expectation_path
        assert expectation["mode"] == "doctor"
        assert expectation["binding"] == binding.to_mapping()
        assert kwargs["cwd"] == binding.workspace_root
        assert kwargs["env"]["HERMES_HOME"] == os.fspath(binding.collection_root)
        assert "HERMES_PYTHON" not in kwargs["env"]
        assert "HERMES_PYTHON_SRC_ROOT" not in kwargs["env"]
        assert kwargs["env"]["PYTHONPATH"] == "parent-sentinel-path"
        report = _valid_report(
            binding,
            nonce=expectation["nonce"],
            parent_pid=expectation["parent_pid"],
        )
        return subprocess.CompletedProcess(command, 0, json.dumps(report) + "\n", "")

    monkeypatch.setattr(doctor_probe.subprocess, "run", fake_run)

    evidence = doctor_probe.probe(
        binding=binding,
        bash_path=os.fspath(bash),
        hermes_command=("fake-hermes",),
        timeout=30,
    )

    assert evidence["fresh_process_verified"] is True
    assert evidence["read_only"] is True
    assert evidence["checks"]["memory"]["memory_db_path"] == os.fspath(
        binding.memory_db_path
    )
    assert not observed["expectation_path"].exists()


def test_public_hermes_failure_fails_closed(installed, monkeypatch) -> None:
    binding, bash = installed
    monkeypatch.setattr(
        doctor_probe,
        "_build_public_expectation",
        lambda selected, *, nonce, parent_pid: {
            "mode": "doctor",
            "nonce": nonce,
            "parent_pid": parent_pid,
            "binding": selected.to_mapping(),
            "plugin": {"key": "sage", "name": "sage"},
            "shell_hooks": [],
            "policy_probes": [],
        },
    )

    def fake_run(command, **_kwargs):
        report = {"ok": False, "errors": [{"code": "plugin_missing"}]}
        return subprocess.CompletedProcess(command, 1, json.dumps(report) + "\n", "")

    monkeypatch.setattr(doctor_probe.subprocess, "run", fake_run)

    with pytest.raises(doctor_probe.ProbeError, match="plugin_missing"):
        doctor_probe.probe(
            binding=binding,
            bash_path=os.fspath(bash),
            hermes_command=("fake-hermes",),
        )


def test_hermes_command_must_be_an_argv_sequence(installed) -> None:
    binding, bash = installed

    with pytest.raises(doctor_probe.ProbeError, match="argv sequence"):
        doctor_probe.probe(
            binding=binding,
            bash_path=os.fspath(bash),
            hermes_command="hermes",
        )


def test_production_probe_contains_no_private_hermes_or_checkout_loader() -> None:
    module_path = doctor_probe.__file__
    assert module_path is not None
    source = pathlib.Path(module_path).read_text(encoding="utf-8")
    forbidden = (
        "from hermes_cli",
        "from agent import shell_hooks",
        "HERMES_PYTHON",
        "HERMES_PYTHON_SRC_ROOT",
        "PYTHONPATH",
    )

    assert [token for token in forbidden if token in source] == []