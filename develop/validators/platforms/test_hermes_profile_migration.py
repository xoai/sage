#!/usr/bin/env python3
"""Red-first contract for the explicit receipt-less Hermes profile migration."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SETUP = ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup"
sys.path.insert(0, os.fspath(SETUP))

import hook_config  # noqa: E402
import profile_binding  # noqa: E402
import profile_installer  # noqa: E402
import receipts  # noqa: E402
import profile_migration  # noqa: E402  # red: the transaction does not exist yet


BASH_EXE = "C:/Program Files/Git/bin/bash.exe"
SOURCE_COMMIT = "a" * 40


def _write(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _binding(tmp_path: pathlib.Path, profile_id: str = "alpha"):
    collection = tmp_path / "hermes"
    profile = collection / "profiles" / profile_id
    workspace = profile / "workspace"
    workspace.mkdir(parents=True)
    (profile / "hooks").mkdir()
    (profile / "plugins").mkdir()
    return profile_binding.ProfileBinding.from_explicit(
        collection_root=collection,
        profile_id=profile_id,
        profile_root=profile,
        workspace_root=workspace,
    )


def _artifact(tmp_path: pathlib.Path) -> pathlib.Path:
    artifact = tmp_path / "artifact"
    _write(artifact / "plugins" / "sage" / "__init__.py", b"# canonical plugin\n")
    _write(artifact / "plugins" / "sage" / "plugin.yaml", b"name: sage\n")
    for script in ["sage-hermes-gate.sh"] + [
        record["script"] for record in hook_config.expected_registry()
    ]:
        _write(artifact / "hooks" / script, ("# canonical %s\n" % script).encode())
    return artifact


def _legacy(binding) -> dict[str, bytes]:
    profile = binding.profile_root
    workspace = binding.workspace_root
    config = (
        b"user_setting: keep\r\n"
        b"hooks:\r\n"
        b"  pre_tool_call:\r\n"
        b"    - matcher: write_file|patch\r\n"
        b"      command: \"bash agent-hooks/sage/sage-old-gate.sh\"\r\n"
        b"      fail_closed: true\r\n"
        b"  post_tool_call:\r\n"
        b"sage_profile_binding: {\"profile_id\": \"wrong\"}\r\n"
    )
    files = {
        "config.yaml": config,
        "plugins/sage/legacy.py": b"# legacy plugin\n",
        "plugins/sage/.git/HEAD": b"ref: refs/heads/legacy\n",
        "hooks/sage-hermes-gate.sh": b"# legacy gate\n",
        "workspace/.hermes.md": b"# legacy instructions\n",
        "workspace/sage/runtime/legacy.py": b"# legacy runtime\n",
        "workspace/.sage/identity.json": b'{"name":"Rei"}\n',
        "workspace/.sage/decisions.md": b"# decisions\n",
        "workspace/.sage-memory/memory.db": b"memory-bytes\x00\x01",
        "credentials.json": b'{"token":"preserve"}\n',
        "SOUL.md": b"user identity\n",
        "hooks/user-hook.sh": b"# user hook\n",
        "workspace/notes.txt": b"user notes\n",
        "agent-hooks/sage/sage-old-gate.sh": b"# inert legacy location\n",
    }
    for relative, data in files.items():
        _write(profile / relative, data)
    return files


def _snapshot(binding) -> dict[str, bytes]:
    return {
        path.relative_to(binding.profile_root).as_posix(): path.read_bytes()
        for path in binding.profile_root.rglob("*")
        if path.is_file()
        and path != binding.pack_lock_path
        and ".sage/receipts/runs/" not in path.as_posix()
    }


def _journal(binding, operation_id: str) -> dict:
    return json.loads(
        profile_migration.migration_journal_path(binding, operation_id).read_text(
            encoding="utf-8"
        )
    )


def _migrate(binding, artifact, **overrides):
    backup_root = pathlib.Path(overrides.pop("backup_root", binding.collection_root.parent / "backups"))
    params = dict(
        binding=binding,
        artifact_dir=artifact,
        consent_granted=True,
        source_version="1.3.19",
        source_commit=SOURCE_COMMIT,
        bash_path=BASH_EXE,
        operation_id="receiptless-001",
        backup_root=backup_root,
        activation_probe=lambda **_kwargs: {
            "ok": True,
            "fresh_process_verified": True,
            "detail": "test fresh process",
        },
        activation_rollback=lambda **_kwargs: None,
    )
    params.update(overrides)
    return profile_migration.migrate_receiptless_profile(**params)


def test_receiptless_migration_adopts_only_allowlisted_legacy_surfaces(tmp_path) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    legacy = _legacy(binding)
    sibling = _binding(tmp_path, "beta")
    _write(sibling.profile_root / "sentinel.bin", b"beta exact\x00")
    sibling_before = _snapshot(sibling)

    result = _migrate(binding, artifact)

    assert result["ok"] is True
    assert result["operation"] == "receiptless-profile-migration"
    assert result["activation"]["fresh_process_verified"] is True
    assert receipts.load_install_receipt(binding).source_version == "1.3.19"
    assert (binding.profile_root / "plugins" / "sage" / "__init__.py").read_bytes() == b"# canonical plugin\n"
    assert not (binding.profile_root / "plugins" / "sage" / "legacy.py").exists()
    assert not (binding.profile_root / "plugins" / "sage" / ".git").exists()
    assert (binding.workspace_root / "sage" / "runtime" / "legacy.py").exists() is False
    assert b"user_setting: keep" in binding.config_path.read_bytes()
    assert b"agent-hooks/sage" not in binding.config_path.read_bytes()

    for relative in (
        "workspace/.sage/identity.json",
        "workspace/.sage/decisions.md",
        "workspace/.sage-memory/memory.db",
        "credentials.json",
        "SOUL.md",
        "hooks/user-hook.sh",
        "workspace/notes.txt",
    ):
        assert (binding.profile_root / relative).read_bytes() == legacy[relative]
    assert not (binding.profile_root / "agent-hooks" / "sage").exists()
    assert _snapshot(sibling) == sibling_before

    journal = _journal(binding, result["operation_id"])
    assert journal["schema"] == "sage.hermes.profile-migration"
    assert journal["status"] == "complete"
    assert journal["binding"] == binding.to_mapping()
    backup = pathlib.Path(journal["backup_path"])
    assert backup.is_relative_to(binding.collection_root.parent / "backups")
    assert backup.is_dir()
    assert (backup / "manifest.json").is_file()
    assert (backup / "legacy" / "plugins" / "sage" / "legacy.py").read_bytes() == legacy[
        "plugins/sage/legacy.py"
    ]
    assert (backup / "legacy" / "config.yaml").read_bytes() == legacy["config.yaml"]
    assert (
        backup / "legacy" / "agent-hooks" / "sage" / "sage-old-gate.sh"
    ).read_bytes() == legacy["agent-hooks/sage/sage-old-gate.sh"]


def test_migration_requires_backup_root_outside_hermes_collection(tmp_path) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)

    with pytest.raises(profile_migration.MigrationError, match="outside the Hermes collection"):
        _migrate(
            binding,
            artifact,
            operation_id="inside-home",
            backup_root=binding.collection_root / "backups",
        )


def test_missing_consent_and_valid_receipt_fail_before_migration_evidence(tmp_path) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)

    with pytest.raises(profile_migration.MigrationError, match="consent"):
        _migrate(binding, artifact, consent_granted=False, operation_id="no-consent")
    assert not profile_migration.migration_journal_path(binding, "no-consent").exists()

    clean = _binding(tmp_path, "clean")
    clean.config_path.write_text("user_setting: keep\n", encoding="utf-8")
    profile_installer.install(
        binding=clean,
        artifact_dir=artifact,
        consent_granted=True,
        source_version="1.3.18",
        source_commit=SOURCE_COMMIT,
        bash_path=BASH_EXE,
        activation_probe=lambda **_kwargs: {"ok": True, "fresh_process_verified": True},
    )
    before = _snapshot(clean)
    with pytest.raises(profile_migration.MigrationError, match="update"):
        _migrate(clean, artifact, operation_id="already-owned")
    assert _snapshot(clean) == before
    assert not profile_migration.migration_journal_path(clean, "already-owned").exists()

    malformed = _binding(tmp_path, "malformed")
    _legacy(malformed)
    _write(malformed.receipt_path, b"{not-json\x00")
    malformed_before = _snapshot(malformed)
    with pytest.raises(profile_migration.MigrationError, match="receipt-less"):
        _migrate(malformed, artifact, operation_id="malformed-receipt")
    assert _snapshot(malformed) == malformed_before
    assert not profile_migration.migration_journal_path(
        malformed, "malformed-receipt"
    ).exists()


def test_activation_failure_restores_exact_prior_bytes_and_retains_evidence(tmp_path) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)
    before = _snapshot(binding)
    rollback_calls = []

    def fail_activation(**_kwargs):
        return {"ok": False, "fresh_process_verified": False, "detail": "injected"}

    def rollback_activation(**kwargs):
        rollback_calls.append(kwargs)

    with pytest.raises(profile_migration.MigrationError, match="restored"):
        _migrate(
            binding,
            artifact,
            operation_id="activation-failure",
            activation_probe=fail_activation,
            activation_rollback=rollback_activation,
        )

    assert _snapshot(binding) == before
    assert not binding.receipt_path.exists()
    assert len(rollback_calls) == 1
    journal = _journal(binding, "activation-failure")
    assert journal["status"] == "incomplete"
    assert "injected" in journal["failure"]
    backup = pathlib.Path(journal["backup_path"])
    assert backup.is_dir() and (backup / "manifest.json").is_file()
    assert (backup / "legacy" / "config.yaml").read_bytes() == before["config.yaml"]


def test_failure_after_child_install_restores_exact_prior_bytes_and_retains_candidate(
    tmp_path, monkeypatch
) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)
    before = _snapshot(binding)
    rollback_calls = []

    def fail_post_capture(*_args, **_kwargs):
        raise OSError("injected post-install evidence failure")

    monkeypatch.setattr(profile_migration, "_capture_post_migration", fail_post_capture)
    with pytest.raises(profile_migration.MigrationError, match="restored"):
        _migrate(
            binding,
            artifact,
            operation_id="post-install-failure",
            activation_rollback=lambda **kwargs: rollback_calls.append(kwargs),
        )

    assert _snapshot(binding) == before
    assert not binding.receipt_path.exists()
    assert len(rollback_calls) == 1
    journal = _journal(binding, "post-install-failure")
    assert journal["status"] == "incomplete"
    assert "post-install evidence" in journal["failure"]
    backup = pathlib.Path(journal["backup_path"])
    assert (backup / "failed_candidate" / "install.json").is_file()
    assert (
        backup / "failed_candidate" / "plugins" / "sage" / "__init__.py"
    ).read_bytes() == b"# canonical plugin\n"


def test_failed_child_completion_restores_local_state_before_activation_rollback(
    tmp_path, monkeypatch
) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)
    observed = []

    def fail_post_capture(*_args, **_kwargs):
        raise OSError("injected post-install evidence failure")

    def prove_restored_order(**kwargs):
        assert (binding.plugin_root / "legacy.py").is_file()
        assert not binding.receipt_path.exists()
        assert kwargs["plugin_present"] is True
        observed.append("restored-before-proof")
        return {"ok": True, "fresh_process_verified": True}

    monkeypatch.setattr(profile_migration, "_capture_post_migration", fail_post_capture)
    with pytest.raises(profile_migration.MigrationError, match="post-install evidence"):
        _migrate(
            binding,
            artifact,
            operation_id="failure-proof-order",
            activation_rollback=prove_restored_order,
        )

    assert observed == ["restored-before-proof"]


def test_failed_activation_rollback_cannot_prevent_exact_local_restoration(
    tmp_path, monkeypatch
) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)
    before = _snapshot(binding)

    def fail_post_capture(*_args, **_kwargs):
        raise OSError("injected post-install evidence failure")

    def fail_activation_rollback(**_kwargs):
        raise RuntimeError("injected activation rollback failure")

    monkeypatch.setattr(profile_migration, "_capture_post_migration", fail_post_capture)
    with pytest.raises(profile_migration.MigrationError, match="activation rollback failed"):
        _migrate(
            binding,
            artifact,
            operation_id="rollback-callback-failure",
            activation_rollback=fail_activation_rollback,
        )

    assert _snapshot(binding) == before
    assert not binding.receipt_path.exists()
    journal = _journal(binding, "rollback-callback-failure")
    assert journal["phase"] == "failed-restored"
    assert journal["restored"] is True
    assert "injected activation rollback failure" in journal["activation_rollback_failure"]
    backup = pathlib.Path(journal["backup_path"])
    assert (backup / "failed_candidate" / "manifest.json").is_file()


def test_completed_migration_can_be_reversed_without_losing_installed_bytes(tmp_path) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)
    before = _snapshot(binding)
    result = _migrate(binding, artifact, operation_id="reversible")
    installed_receipt = binding.receipt_path.read_bytes()
    rollback_calls = []

    reversed_result = profile_migration.rollback_receiptless_profile(
        binding=binding,
        operation_id=result["operation_id"],
        activation_rollback=lambda **kwargs: rollback_calls.append(kwargs),
    )

    assert reversed_result == {
        "ok": True,
        "operation": "receiptless-profile-migration-rollback",
        "operation_id": "reversible",
    }
    assert _snapshot(binding) == before
    assert not binding.receipt_path.exists()
    assert len(rollback_calls) == 1
    journal = _journal(binding, "reversible")
    assert journal["status"] == "rolled_back"
    backup = pathlib.Path(journal["backup_path"])
    assert (backup / "post_migration" / "install.json").read_bytes() == installed_receipt
    assert (backup / "post_migration" / "plugins" / "sage" / "__init__.py").read_bytes() == b"# canonical plugin\n"


def test_rollback_refuses_to_clobber_post_migration_user_edits(tmp_path) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)
    result = _migrate(binding, artifact, operation_id="edited")
    edited = binding.profile_root / "plugins" / "sage" / "__init__.py"
    edited.write_bytes(b"# post-migration user edit\n")

    with pytest.raises(profile_migration.MigrationError, match="changed"):
        profile_migration.rollback_receiptless_profile(
            binding=binding, operation_id=result["operation_id"]
        )

    assert edited.read_bytes() == b"# post-migration user edit\n"
    assert binding.receipt_path.is_file()
    assert _journal(binding, "edited")["status"] == "complete"


def test_child_operation_id_is_durable_before_child_install_starts(
    tmp_path, monkeypatch
) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)
    observed = []

    def interrupting_install(**kwargs):
        observed.append(_journal(binding, "child-id-first")["child_operation_id"])
        raise RuntimeError("injected child interruption")

    monkeypatch.setattr(profile_migration.profile_installer, "install", interrupting_install)
    with pytest.raises(profile_migration.MigrationError, match="injected child interruption"):
        _migrate(binding, artifact, operation_id="child-id-first")

    assert observed == ["child-id-first-install"]


def test_interrupted_pre_child_migration_can_be_rolled_back_from_backup(tmp_path) -> None:
    binding = _binding(tmp_path)
    _legacy(binding)
    before = _snapshot(binding)
    operation_id = "interrupted-pre-child"
    backup_root = binding.collection_root.parent / "backups"
    journal = {
        "schema": profile_migration.SCHEMA,
        "schema_version": profile_migration.SCHEMA_VERSION,
        "operation": "receiptless-profile-migration",
        "operation_id": operation_id,
        "status": "incomplete",
        "phase": "preparing-backup",
        "binding": binding.to_mapping(),
        "backup_path": os.fspath(
            profile_migration._backup_root(binding, operation_id, backup_root)
        ),
        "backup_root": os.fspath(backup_root),
        "backup_manifest_sha256": None,
        "child_operation_id": None,
        "post_migration": None,
        "activation": None,
        "failure": None,
        "restored": False,
    }
    _backup, entries = profile_migration._backup_legacy(
        binding, operation_id, journal, backup_root
    )
    config_candidate = profile_migration._legacy_config_candidate(
        binding.config_path.read_bytes()
    )
    profile_migration._quarantine_legacy(binding, entries, config_candidate)
    journal["phase"] = "legacy-quarantined"
    profile_migration._atomic_json(
        profile_migration.migration_journal_path(binding, operation_id), journal
    )

    result = profile_migration.rollback_receiptless_profile(
        binding=binding,
        operation_id=operation_id,
        activation_rollback=lambda **_kwargs: {
            "ok": True,
            "fresh_process_verified": True,
        },
    )

    assert result["ok"] is True
    assert _snapshot(binding) == before
    assert _journal(binding, operation_id)["status"] == "rolled_back"


def test_interrupted_child_journal_is_recovered_before_legacy_restore(
    tmp_path,
) -> None:
    binding = _binding(tmp_path)
    _legacy(binding)
    before = _snapshot(binding)
    operation_id = "interrupted-child"
    child_operation_id = operation_id + "-install"
    backup_root = binding.collection_root.parent / "backups"
    journal = {
        "schema": profile_migration.SCHEMA,
        "schema_version": profile_migration.SCHEMA_VERSION,
        "operation": "receiptless-profile-migration",
        "operation_id": operation_id,
        "status": "incomplete",
        "phase": "preparing-backup",
        "binding": binding.to_mapping(),
        "backup_path": os.fspath(
            profile_migration._backup_root(binding, operation_id, backup_root)
        ),
        "backup_root": os.fspath(backup_root),
        "backup_manifest_sha256": None,
        "child_operation_id": None,
        "post_migration": None,
        "activation": None,
        "failure": None,
        "restored": False,
    }
    _backup, entries = profile_migration._backup_legacy(
        binding, operation_id, journal, backup_root
    )
    config_candidate = profile_migration._legacy_config_candidate(
        binding.config_path.read_bytes()
    )
    profile_migration._quarantine_legacy(binding, entries, config_candidate)
    journal["status"] = "child-install-running"
    journal["phase"] = "child-install-starting"
    journal["child_operation_id"] = child_operation_id
    profile_migration._atomic_json(
        profile_migration.migration_journal_path(binding, operation_id), journal
    )

    partial_child_config = b"partial_child: true\n"
    receipts.begin_run_journal(
        binding=binding,
        operation_id=child_operation_id,
        operation="install",
        source_version="1.3.19",
        source_commit=SOURCE_COMMIT,
        previous_managed_targets=(),
        previous_config_records=(),
        previous_allowlist_records=(),
        planned_writes=(),
        planned_removals=(),
    )
    profile_installer._write_backup_pack(
        binding,
        child_operation_id,
        binding.config_path.read_bytes(),
        [],
        [],
        candidate_config_bytes=partial_child_config,
    )
    profile_migration._atomic_write(binding.config_path, partial_child_config)

    result = profile_migration.rollback_receiptless_profile(
        binding=binding,
        operation_id=operation_id,
        activation_rollback=lambda **_kwargs: {
            "ok": True,
            "fresh_process_verified": True,
        },
    )

    child = receipts.load_run_journal(binding, child_operation_id)
    assert child.is_complete is True
    assert child.result["recovered"] is True
    assert result["ok"] is True
    assert _snapshot(binding) == before
    assert _journal(binding, operation_id)["status"] == "rolled_back"


def test_completed_rollback_restores_prior_allowlist_before_fresh_proof(
    tmp_path,
) -> None:
    binding = _binding(tmp_path)
    artifact = _artifact(tmp_path)
    _legacy(binding)
    allowlist = binding.profile_root / "shell-hooks-allowlist.json"
    prior = (
        b'{"approvals":[{"event":"x","command":"user"}],"sentinel":42}'
        + bytes((13, 10))
    )
    candidate = b'{"schema_version":1,"approvals":[{"event":"pre_tool_call","command":"sage"}]}\n'
    _write(allowlist, prior)
    before = _snapshot(binding)

    def activate(**_kwargs):
        allowlist.write_bytes(candidate)
        return {
            "ok": True,
            "fresh_process_verified": True,
            "detail": "candidate activated",
        }

    result = _migrate(
        binding,
        artifact,
        operation_id="fresh-rollback",
        activation_probe=activate,
    )
    assert allowlist.read_bytes() == candidate

    def fresh_rollback_proof(**kwargs):
        allowlist.write_bytes(prior)
        assert allowlist.read_bytes() == prior
        assert (binding.profile_root / "plugins" / "sage" / "legacy.py").is_file()
        assert not binding.receipt_path.exists()
        assert kwargs["plugin_present"] is True
        return {"ok": True, "fresh_process_verified": True}

    reversed_result = profile_migration.rollback_receiptless_profile(
        binding=binding,
        operation_id=result["operation_id"],
        activation_rollback=fresh_rollback_proof,
    )

    assert reversed_result["ok"] is True
    assert _snapshot(binding) == before
