#!/usr/bin/env python3
"""Behavioral contract for Task 21: receipt-guided uninstall and
post-restart absence proof (spec 5.7.8, 5.9.4).

Uninstall reads the valid receipt, removes only receipt-owned files and the
exact Sage config entries, and preserves `.sage`, `.sage-memory`, identity,
user skills, databases, and every unmanaged sentinel. A missing or corrupt
receipt never guesses ownership — it fails closed and touches nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SETUP = ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup"
sys.path.insert(0, str(SETUP))

import hook_config  # noqa: E402
import profile_binding  # noqa: E402
import profile_installer  # noqa: E402
import receipts  # noqa: E402


BASH_EXE = "C:/Program Files/Git/bin/bash.exe"
ADAPTER = "sage-hermes-gate.sh"


def _write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config_text(binding) -> str:
    block = {
        "profile_id": binding.profile_id,
        "workspace_root": os.fspath(binding.workspace_root),
        "state_root": os.fspath(binding.state_root),
        "memory_root": os.fspath(binding.memory_root),
        "receipt_path": os.fspath(binding.receipt_path),
    }
    return (
        "other_setting: 42\n"
        "plugins:\n  enabled: [sage]\n"
        "sage_profile_binding: " + json.dumps(block) + "\n"
    )


def _make_profile(tmp_path: pathlib.Path, profile_id: str = "alpha"):
    collection = tmp_path / "hermes"
    profile = collection / "profiles" / profile_id
    workspace = profile / "workspace"
    workspace.mkdir(parents=True)
    (profile / "plugins").mkdir()
    (profile / "hooks").mkdir()
    binding = profile_binding.ProfileBinding.from_explicit(
        collection_root=collection,
        profile_id=profile_id,
        profile_root=profile,
        workspace_root=workspace,
    )
    _write(profile / "config.yaml", _config_text(binding))
    _write(profile / "SOUL.md", "# identity — never Sage-owned\n")
    _write(profile / "hooks" / "user-hook.sh", "#!/usr/bin/env bash\n# user-owned\n")
    _write(workspace / ".sage" / "decisions.md", "# user decisions\n")
    (workspace / ".sage-memory").mkdir(exist_ok=True)
    (workspace / ".sage-memory" / "memory.db").write_bytes(b"sqlite")
    return binding


def _make_artifact(tmp_path: pathlib.Path) -> pathlib.Path:
    artifact = tmp_path / "artifact"
    _write(artifact / "plugins" / "sage" / "__init__.py", "# plugin\n")
    _write(artifact / "plugins" / "sage" / "plugin.yaml", "name: sage\n")
    _write(
        artifact / "plugins" / "sage" / "profile_binding.py",
        (SETUP / "profile_binding.py").read_text(encoding="utf-8"),
    )
    for script in [ADAPTER] + [e["script"] for e in hook_config.expected_registry()]:
        _write(artifact / "hooks" / script, "#!/usr/bin/env bash\n# %s\n" % script)
    return artifact


@pytest.fixture()
def installed(tmp_path):
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    profile_installer.install(
        binding=binding,
        artifact_dir=artifact,
        consent_granted=True,
        source_version="1.3.18",
        source_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        bash_path=BASH_EXE,
        activation_probe=lambda **_kwargs: {
            "ok": True,
            "fresh_process_verified": True,
            "surfaces": {"cli": {"ok": True}, "gateway": {"ok": True}},
        },
    )
    return binding


def _uninstall(binding, **kwargs):
    params = dict(
        binding=binding,
        consent_granted=True,
        absence_probe=lambda **_details: {
            "ok": True,
            "fresh_process_verified": True,
            "surfaces": {"cli": {"ok": True}, "gateway": {"ok": True}},
        },
        absence_rollback=lambda **_details: {
            "ok": True,
            "fresh_process_verified": True,
        },
    )
    params.update(kwargs)
    return profile_installer.uninstall(**params)


# ── happy path ───────────────────────────────────────────────────────────────

def test_uninstall_removes_only_receipt_owned_files(installed) -> None:
    result = _uninstall(installed)
    assert result["ok"] is True
    profile = installed.profile_root
    assert not (profile / "plugins" / "sage" / "__init__.py").exists()
    for entry in hook_config.expected_registry():
        assert not (profile / "hooks" / entry["script"]).exists()
    assert not (profile / "hooks" / ADAPTER).exists()


def test_uninstall_preserves_all_durable_and_unmanaged_bytes(installed) -> None:
    profile = installed.profile_root
    soul = _digest(profile / "SOUL.md")
    user_hook = _digest(profile / "hooks" / "user-hook.sh")
    decisions = _digest(installed.workspace_root / ".sage" / "decisions.md")
    memory = _digest(installed.workspace_root / ".sage-memory" / "memory.db")

    _uninstall(installed)
    assert _digest(profile / "SOUL.md") == soul
    assert _digest(profile / "hooks" / "user-hook.sh") == user_hook
    assert _digest(installed.workspace_root / ".sage" / "decisions.md") == decisions
    assert _digest(installed.workspace_root / ".sage-memory" / "memory.db") == memory
    assert "other_setting: 42" in (profile / "config.yaml").read_text(encoding="utf-8")


def test_uninstall_leaves_zero_sage_registry_entries(installed) -> None:
    _uninstall(installed)
    config = (installed.profile_root / "config.yaml").read_text(encoding="utf-8")
    assert "sage-hermes-gate.sh" not in config
    assert "sage-spec-gate.sh" not in config


def test_uninstall_journal_records_and_completes(installed) -> None:
    proof_calls = []

    def prove_absence(**kwargs):
        journal = receipts.load_run_journal(installed, kwargs["operation_id"])
        assert not journal.is_complete
        assert "sage-hermes-gate.sh" not in installed.config_path.read_text(
            encoding="utf-8"
        )
        assert not (installed.profile_root / "plugins" / "sage" / "plugin.yaml").exists()
        assert len(kwargs["config_records"]) == 12
        assert len(kwargs["allowlist_records"]) == 12
        proof_calls.append(kwargs)
        return {"ok": True, "fresh_process_verified": True}

    result = _uninstall(installed, absence_probe=prove_absence)
    journal = receipts.load_completed_run_journal(installed, result["operation_id"])
    assert journal.is_complete
    assert journal.operation == "remove"
    assert journal.planned_removals
    assert journal.result["fresh_process_verified"] is True
    assert len(proof_calls) == 1


def test_uninstall_absence_failure_restores_then_fresh_proves_prior_state(installed) -> None:
    profile = installed.profile_root
    config_before = installed.config_path.read_bytes()
    plugin_before = (profile / "plugins" / "sage" / "plugin.yaml").read_bytes()
    rollback_calls = []

    def fail_absence(**_kwargs):
        return {
            "ok": False,
            "fresh_process_verified": False,
            "detail": "injected stale Sage registry",
        }

    def prove_restored(**kwargs):
        assert installed.config_path.read_bytes() == config_before
        assert (profile / "plugins" / "sage" / "plugin.yaml").read_bytes() == plugin_before
        rollback_calls.append(kwargs)
        return {"ok": True, "fresh_process_verified": True}

    with pytest.raises(profile_installer.InstallError, match="restored"):
        _uninstall(
            installed,
            operation_id="uninstall-proof-red",
            absence_probe=fail_absence,
            absence_rollback=prove_restored,
        )

    assert len(rollback_calls) == 1
    assert not receipts.load_run_journal(
        installed, "uninstall-proof-red"
    ).is_complete


def test_uninstall_requires_fresh_absence_callback_before_mutation(installed) -> None:
    before = installed.config_path.read_bytes()

    with pytest.raises(profile_installer.InstallError, match="fresh.*absence"):
        profile_installer.uninstall(
            binding=installed,
            consent_granted=True,
            absence_probe=None,
        )

    assert installed.config_path.read_bytes() == before
    assert (installed.profile_root / "plugins" / "sage" / "plugin.yaml").is_file()


# ── fail-closed ownership ────────────────────────────────────────────────────

def test_missing_receipt_never_guesses_ownership(installed) -> None:
    installed.receipt_path.unlink()
    config_before = _digest(installed.profile_root / "config.yaml")
    hook_before = _digest(installed.profile_root / "hooks" / ADAPTER)
    with pytest.raises(profile_installer.InstallError):
        _uninstall(installed)
    assert _digest(installed.profile_root / "config.yaml") == config_before
    assert _digest(installed.profile_root / "hooks" / ADAPTER) == hook_before


def test_corrupt_receipt_never_guesses_ownership(installed) -> None:
    installed.receipt_path.write_text("{torn", encoding="utf-8")
    config_before = _digest(installed.profile_root / "config.yaml")
    with pytest.raises(profile_installer.InstallError):
        _uninstall(installed)
    assert _digest(installed.profile_root / "config.yaml") == config_before
    assert (installed.profile_root / "hooks" / ADAPTER).is_file()


def test_uninstall_requires_consent(installed) -> None:
    with pytest.raises(profile_installer.InstallError):
        _uninstall(installed, consent_granted=False)
    assert (installed.profile_root / "hooks" / ADAPTER).is_file()


# ── user edits inside managed paths survive uninstall ────────────────────────

def test_user_edited_managed_file_survives_uninstall(installed) -> None:
    edited = installed.profile_root / "hooks" / "sage-spec-gate.sh"
    _write(edited, "# user edit\n")
    _uninstall(installed)
    assert edited.read_text(encoding="utf-8") == "# user edit\n"


# ── T21 revision coverage ────────────────────────────────────────────────────

def test_uninstall_survives_comment_only_adapter_mention(installed) -> None:
    config_path = installed.profile_root / "config.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "hooks:\n"
        + "  pre_tool_call:\n"
        + "    - matcher: terminal\n"
        + "      # borrows the sage-hermes-gate.sh pattern\n"
        + "      command: \"\\\"C:/Program Files/Git/bin/bash.exe\\\" \\\"G:/profile/hooks/user-hook.sh\\\" run\"\n"
        + "      timeout: 30\n",
        encoding="utf-8",
    )
    result = _uninstall(installed)
    assert result["ok"] is True
    merged = config_path.read_text(encoding="utf-8")
    assert "user-hook.sh" in merged
    assert "borrows the sage-hermes-gate.sh pattern" in merged


def test_crash_resumed_remove_restores_removed_bytes(installed) -> None:
    profile = installed.profile_root
    adapter = profile / "hooks" / ADAPTER
    prior_adapter = adapter.read_bytes()
    receipt = receipts.load_install_receipt(installed)
    removal_targets = list(receipt.managed_targets)
    operation_id = "t21-crash"

    receipts.begin_run_journal(
        binding=installed,
        operation_id=operation_id,
        operation="remove",
        source_version=receipt.source_version,
        source_commit=receipt.source_commit,
        previous_managed_targets=removal_targets,
        previous_config_records=[],
        previous_allowlist_records=[],
        planned_writes=[],
        planned_removals=[
            receipts.TargetRef(owner=t.owner, relative_path=t.relative_path)
            for t in removal_targets
        ],
    )
    profile_installer._write_backup_pack(
        installed,
        operation_id,
        (profile / "config.yaml").read_bytes(),
        [],
        removal_targets,
    )
    adapter.unlink()  # the crash removed it, then died before completing

    recovery = profile_installer.resume_incomplete(
        binding=installed, operation_id=operation_id
    )
    assert recovery["restored"] is True
    assert adapter.read_bytes() == prior_adapter
