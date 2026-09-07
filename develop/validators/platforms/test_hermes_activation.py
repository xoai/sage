#!/usr/bin/env python3
"""Contracts for fresh CLI+Gateway activation and reversible hook consent."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SETUP = ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup"
sys.path.insert(0, str(SETUP))

import activation  # noqa: E402
import hook_config  # noqa: E402
import profile_binding  # noqa: E402


def _binding(tmp_path: pathlib.Path):
    collection = tmp_path / "hermes"
    profile = collection / "profiles" / "alpha"
    workspace = profile / "workspace"
    workspace.mkdir(parents=True)
    return profile_binding.ProfileBinding.from_explicit(
        collection_root=collection,
        profile_id="alpha",
        profile_root=profile,
        workspace_root=workspace,
    )


def _records(binding, bash="C:/Program Files/Git/bin/bash.exe"):
    records = []
    for item in hook_config.expected_registry():
        adapter = (binding.profile_root / "hooks" / "sage-hermes-gate.sh").as_posix()
        records.append(
            {
                "event": item["event"],
                "matcher": item["matcher"],
                "command": f'"{bash}" "{adapter}" {item["script"]}',
                "fail_closed": item["fail_closed"],
            }
        )
    return records


def test_resolve_hermes_command_accepts_explicit_argv_without_python_or_source_root(
    tmp_path, monkeypatch,
):
    launcher = pathlib.Path(sys.executable).resolve()
    shim = tmp_path / "portable-hermes.py"
    shim.write_text("# explicit launcher argument\n", encoding="utf-8")
    monkeypatch.setenv(
        "SAGE_HERMES_COMMAND",
        json.dumps([os.fspath(launcher), os.fspath(shim)]),
    )
    # These were the old private-host contract.  Bogus values prove they are no
    # longer consulted by install, update, migration, activation, or doctor.
    monkeypatch.setenv("HERMES_PYTHON", os.fspath(tmp_path / "missing-python"))
    monkeypatch.setenv("HERMES_PYTHON_SRC_ROOT", os.fspath(tmp_path / "missing-source"))

    assert activation.resolve_hermes_command() == (
        os.fspath(launcher),
        os.fspath(shim),
    )


def test_resolve_hermes_command_uses_path_launcher_without_adjacent_python(
    tmp_path, monkeypatch,
):
    executable = tmp_path / ("hermes.exe" if os.name == "nt" else "hermes")
    executable.write_bytes(b"launcher")
    executable.chmod(0o755)
    monkeypatch.delenv("SAGE_HERMES_COMMAND", raising=False)
    monkeypatch.setenv("HERMES_PYTHON", os.fspath(tmp_path / "missing-python"))
    monkeypatch.setenv("HERMES_PYTHON_SRC_ROOT", os.fspath(tmp_path / "missing-source"))
    monkeypatch.setattr(activation.shutil, "which", lambda name: os.fspath(executable))

    assert activation.resolve_hermes_command() == (os.fspath(executable.resolve()),)


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        "{}",
        "[]",
        '["relative-hermes"]',
        '["C:/missing/hermes.exe"]' if os.name == "nt" else '["/missing/hermes"]',
    ],
)
def test_resolve_hermes_command_rejects_malformed_or_missing_explicit_argv(
    raw, monkeypatch,
):
    monkeypatch.setenv("SAGE_HERMES_COMMAND", raw)

    with pytest.raises(activation.ActivationError, match="SAGE_HERMES_COMMAND"):
        activation.resolve_hermes_command()


def test_resolve_hermes_command_fails_closed_without_public_launcher(monkeypatch):
    monkeypatch.delenv("SAGE_HERMES_COMMAND", raising=False)
    monkeypatch.setattr(activation.shutil, "which", lambda name: None)

    with pytest.raises(activation.ActivationError, match="Hermes executable"):
        activation.resolve_hermes_command()


def test_expectation_is_exact_and_contains_three_policy_outcomes(tmp_path):
    binding = _binding(tmp_path)
    expectation = activation.build_expectation(_records(binding), binding)
    assert expectation["plugin"] == {"key": "sage", "name": "sage"}
    assert len(expectation["shell_hooks"]) == 12
    assert [p["expected"] for p in expectation["policy_probes"]] == [
        "allow",
        "block",
        "unverifiable",
    ]
    assert all(p["hook_index"] == expectation["policy_probes"][0]["hook_index"]
               for p in expectation["policy_probes"])


def test_allowlist_merge_preserves_unrelated_and_restore_is_byte_exact(tmp_path):
    binding = _binding(tmp_path)
    path = activation.allowlist_path(binding)
    path.parent.mkdir(parents=True, exist_ok=True)
    before = b'{"approvals":[{"event":"x","command":"user"}],"sentinel":42}\r\n'
    path.write_bytes(before)
    snapshot = activation.snapshot_allowlist(binding)
    records = _records(binding)

    activation.merge_allowlist(
        binding,
        ({"event": r["event"], "command": r["command"]} for r in records),
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["sentinel"] == 42
    assert {("x", "user")} <= {
        (item["event"], item["command"]) for item in data["approvals"]
    }
    assert len(data["approvals"]) == 13

    activation.restore_allowlist(snapshot)
    assert path.read_bytes() == before


def test_allowlist_merge_is_byte_idempotent_for_current_records(tmp_path):
    binding = _binding(tmp_path)
    records = _records(binding)
    approvals = [
        {"event": record["event"], "command": record["command"]}
        for record in records
    ]

    activation.merge_allowlist(binding, approvals)
    first = activation.allowlist_path(binding).read_bytes()
    activation.merge_allowlist(binding, approvals)

    assert activation.allowlist_path(binding).read_bytes() == first


def test_remove_allowlist_records_removes_only_exact_sage_pairs(tmp_path):
    binding = _binding(tmp_path)
    sage_records = [
        {"event": record["event"], "command": record["command"]}
        for record in _records(binding)
    ]
    unrelated = {"event": "pre_tool_call", "command": "user-command"}
    activation.merge_allowlist(binding, [unrelated, *sage_records])

    removed = activation.remove_allowlist_records(binding, sage_records)

    data = json.loads(activation.allowlist_path(binding).read_text(encoding="utf-8"))
    assert removed == 12
    assert [
        (entry["event"], entry["command"]) for entry in data["approvals"]
    ] == [(unrelated["event"], unrelated["command"])]


def test_callbacks_restore_absent_allowlist_after_later_failure(tmp_path, monkeypatch):
    binding = _binding(tmp_path)
    assert not activation.allowlist_path(binding).exists()
    records = _records(binding)

    def fake_proof(**kwargs):
        activation.merge_allowlist(binding, kwargs["allowlist_records"])
        return {"ok": True, "fresh_process_verified": True}

    rollback_proofs = []

    def fake_topology(**kwargs):
        rollback_proofs.append(kwargs)
        assert not activation.allowlist_path(binding).exists()
        return {"ok": True, "fresh_process_verified": True}

    monkeypatch.setattr(activation, "run_fresh_process_proof", fake_proof)
    monkeypatch.setattr(activation, "run_fresh_topology_proof", fake_topology)
    probe, rollback = activation.callbacks(binding, [sys.executable, "-m", "hermes_cli.main"])
    result = probe(
        config_records=records,
        allowlist_records=[
            {"event": r["event"], "command": r["command"]} for r in records
        ],
    )
    assert result["fresh_process_verified"] is True
    assert activation.allowlist_path(binding).is_file()
    result = rollback(config_records=(), allowlist_records=())
    assert not activation.allowlist_path(binding).exists()
    assert result["fresh_process_verified"] is True
    assert len(rollback_proofs) == 1


def test_callbacks_snapshot_allowlist_at_creation_for_explicit_rollback(
    tmp_path, monkeypatch,
):
    binding = _binding(tmp_path)
    path = activation.allowlist_path(binding)
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = b'{"approvals":[{"event":"x","command":"user"}]}\n'
    path.write_bytes(prior)
    proofs = []

    def fake_topology(**kwargs):
        proofs.append(kwargs)
        assert path.read_bytes() == prior
        return {"ok": True, "fresh_process_verified": True}

    monkeypatch.setattr(activation, "run_fresh_topology_proof", fake_topology)
    _probe, rollback = activation.callbacks(
        binding, [sys.executable, "-m", "hermes_cli.main"]
    )
    path.write_bytes(b'{"approvals":[{"event":"pre_tool_call","command":"sage"}]}\n')

    result = rollback(
        config_records=(),
        allowlist_records=(),
        plugin_present=True,
    )

    assert result["fresh_process_verified"] is True
    assert path.read_bytes() == prior
    assert proofs[0]["plugin_present"] is True


def test_callbacks_restore_a_previously_absent_allowlist_exactly(
    tmp_path, monkeypatch,
):
    binding = _binding(tmp_path)
    path = activation.allowlist_path(binding)
    dangling_target = tmp_path / "missing-allowlist-target.json"
    proofs = []

    def fake_topology(**kwargs):
        proofs.append(kwargs)
        assert not os.path.lexists(os.fspath(path))
        return {"ok": True, "fresh_process_verified": True}

    monkeypatch.setattr(activation, "run_fresh_topology_proof", fake_topology)
    _probe, rollback = activation.callbacks(
        binding, [sys.executable, "-m", "hermes_cli.main"]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.symlink_to(dangling_target)
    except (NotImplementedError, OSError) as exc:
        pytest.skip("symlink creation unavailable: %s" % exc)

    result = rollback(
        config_records=(),
        allowlist_records=(),
        plugin_present=False,
    )

    assert result["fresh_process_verified"] is True
    assert not os.path.lexists(os.fspath(path))
    assert proofs[0]["plugin_present"] is False


def test_uninstall_callbacks_remove_consent_prove_absence_and_restore_prior(tmp_path, monkeypatch):
    binding = _binding(tmp_path)
    records = _records(binding)
    sage_pairs = [
        {"event": record["event"], "command": record["command"]}
        for record in records
    ]
    unrelated = {"event": "pre_tool_call", "command": "user-command"}
    activation.merge_allowlist(binding, [unrelated, *sage_pairs])
    before = activation.allowlist_path(binding).read_bytes()
    proofs = []

    def fake_topology(**kwargs):
        proofs.append(kwargs)
        return {"ok": True, "fresh_process_verified": True}

    monkeypatch.setattr(activation, "run_fresh_topology_proof", fake_topology)
    absence_probe, rollback = activation.uninstall_callbacks(
        binding, [sys.executable, "-m", "hermes_cli.main"]
    )

    result = absence_probe(allowlist_records=sage_pairs, config_records=())
    current = json.loads(activation.allowlist_path(binding).read_text(encoding="utf-8"))
    assert result["fresh_process_verified"] is True
    assert [(item["event"], item["command"]) for item in current["approvals"]] == [
        (unrelated["event"], unrelated["command"])
    ]
    assert proofs[-1]["plugin_present"] is False

    restored = rollback(config_records=())
    assert activation.allowlist_path(binding).read_bytes() == before
    assert restored["fresh_process_verified"] is True
    assert proofs[-1]["plugin_present"] is True


def test_fresh_process_proof_requires_two_distinct_successful_surfaces(
    tmp_path, monkeypatch,
):
    binding = _binding(tmp_path)
    records = _records(binding)
    reports = iter(
        [
            {"ok": True, "pid": 111, "policy_probes": [
                {"outcome": "allow"}, {"outcome": "block"}, {"outcome": "unverifiable"}
            ]},
            {"ok": False, "pid": 222, "errors": [{"code": "gateway-red"}]},
        ]
    )

    class Completed:
        returncode = 0
        stderr = ""

        def __init__(self, report):
            self.stdout = json.dumps(report)

    monkeypatch.setattr(
        activation.subprocess,
        "run",
        lambda *_args, **_kwargs: Completed(next(reports)),
    )
    with pytest.raises(activation.ActivationError, match="gateway proof failed"):
        activation.run_fresh_process_proof(
            binding=binding,
            config_records=records,
            allowlist_records=[
                {"event": r["event"], "command": r["command"]} for r in records
            ],
            hermes_command=[sys.executable, "-m", "hermes_cli.main"],
        )


def test_fresh_process_proof_rejects_same_pid_for_both_surfaces(tmp_path, monkeypatch):
    binding = _binding(tmp_path)
    records = _records(binding)
    report = {"ok": True, "pid": 777, "policy_probes": [
        {"outcome": "allow"}, {"outcome": "block"}, {"outcome": "unverifiable"}
    ]}

    class Completed:
        returncode = 0
        stderr = ""
        stdout = json.dumps(report)

    monkeypatch.setattr(activation.subprocess, "run", lambda *_a, **_k: Completed())
    with pytest.raises(activation.ActivationError, match="distinct fresh processes"):
        activation.run_fresh_process_proof(
            binding=binding,
            config_records=records,
            allowlist_records=[
                {"event": r["event"], "command": r["command"]} for r in records
            ],
            hermes_command=[sys.executable, "-m", "hermes_cli.main"],
        )
