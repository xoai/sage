#!/usr/bin/env python3
"""Behavioral contract for Task 18: staged install commit and managed
stale-file pruning (spec 5.7).

The module under test is
``runtime/platforms/community/hermes/setup/profile_installer.py``. These
tests pin the transaction BEFORE the implementation exists (red-first):
pure plan, complete staging, candidate validation, incomplete journal,
atomic receipt-owned replacement, stale managed prune, structural
idempotent config commit, activation, and final receipt.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import threading

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SETUP = ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup"
sys.path.insert(0, str(SETUP))

import hook_config  # noqa: E402
import profile_binding  # noqa: E402
import receipts  # noqa: E402

import profile_installer  # red: module does not exist yet — collection error is the RED


BASH_EXE = "C:/Program Files/Git/bin/bash.exe"
ADAPTER = "sage-hermes-gate.sh"


# ── fixtures ─────────────────────────────────────────────────────────────────

def _write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _digest(path: pathlib.Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config_text(binding: profile_binding.ProfileBinding, extra: str = "") -> str:
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
        "sage_profile_binding: " + json.dumps(block) + "\n" + extra
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
    _write(profile / "hooks" / "user-hook.sh", "#!/usr/bin/env bash\n# user-owned\n")
    _write(workspace / ".sage" / "decisions.md", "# user decisions\n")
    return binding


def _make_artifact(tmp_path: pathlib.Path, *, drop_script: str = "") -> pathlib.Path:
    artifact = tmp_path / "artifact"
    _write(artifact / "plugins" / "sage" / "__init__.py", "# plugin\n")
    _write(artifact / "plugins" / "sage" / "plugin.yaml", "name: sage\n")
    _write(
        artifact / "plugins" / "sage" / "profile_binding.py",
        (SETUP / "profile_binding.py").read_text(encoding="utf-8"),
    )
    scripts = [ADAPTER] + [
        entry["script"] for entry in hook_config.expected_registry()
    ]
    for script in scripts:
        if script == drop_script:
            continue
        _write(artifact / "hooks" / script, "#!/usr/bin/env bash\n# %s\n" % script)
    return artifact


def _verified_activation(**_details):
    return {
        "ok": True,
        "fresh_process_verified": True,
        "detail": "test fixture: both fresh surfaces verified",
        "surfaces": {"cli": {"ok": True}, "gateway": {"ok": True}},
    }


def _install(binding, artifact, **kwargs):

    params = dict(
        binding=binding,
        artifact_dir=artifact,
        consent_granted=True,
        source_version="1.3.18",
        source_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        bash_path=BASH_EXE,
        activation_probe=_verified_activation,
    )
    params.update(kwargs)
    return profile_installer.install(**params)


# ── 1. happy path ────────────────────────────────────────────────────────────

def test_fresh_install_writes_managed_set_config_receipt_and_journal(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)

    result = _install(binding, artifact)
    assert result["ok"] is True

    profile = binding.profile_root
    assert (profile / "plugins" / "sage" / "__init__.py").is_file()
    assert (profile / "plugins" / "sage" / "plugin.yaml").is_file()
    assert (profile / "hooks" / ADAPTER).is_file()
    for entry in hook_config.expected_registry():
        assert (profile / "hooks" / entry["script"]).is_file()

    config = (profile / "config.yaml").read_text(encoding="utf-8")
    validation = hook_config.validate_candidate_config(config)
    assert validation["ok"] is True, validation["errors"]
    assert "other_setting: 42" in config

    receipt = receipts.load_install_receipt(binding)
    assert receipt.source_version == "1.3.18"
    journal = receipts.load_completed_run_journal(binding, result["operation_id"])
    assert journal.is_complete


def test_install_receipt_owns_every_canonical_profile_hook(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)

    _install(binding, artifact)

    canonical_hooks = {
        path.name
        for path in (
            ROOT / "runtime" / "platforms" / "claude-code" / "hooks"
        ).glob("sage-*.sh")
    }
    expected = canonical_hooks | {ADAPTER}
    installed = {
        path.name for path in (binding.profile_root / "hooks").glob("sage-*.sh")
    }
    receipt = receipts.load_install_receipt(binding)
    receipt_hooks = {
        pathlib.PurePosixPath(target.relative_path).name
        for target in receipt.managed_targets
        if target.owner == "profile" and target.relative_path.startswith("hooks/")
    }

    assert installed == expected
    assert receipt_hooks == expected


# ── 2. validation failure before commit writes nothing ───────────────────────

def test_invalid_candidate_writes_nothing_before_commit(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path, drop_script="sage-scope-gate.sh")
    before = _digest(binding.profile_root / "config.yaml")

    with pytest.raises(profile_installer.InstallError):
        _install(binding, artifact)

    profile = binding.profile_root
    assert _digest(profile / "config.yaml") == before
    assert not (profile / "plugins" / "sage").exists()
    for entry in hook_config.expected_registry():
        assert not (profile / "hooks" / entry["script"]).exists()


# ── 3. injected mid-commit failure restores prior state ──────────────────────

def test_mid_commit_failure_restores_prior_config_and_files(tmp_path, monkeypatch) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    before = _digest(binding.profile_root / "config.yaml")

    real_copy = shutil.copy2
    calls = []

    def explode(dest, src, *args, **kwargs):
        calls.append(1)
        if len(calls) >= 2:
            raise OSError("injected mid-commit failure")
        return real_copy(dest, src, *args, **kwargs)

    monkeypatch.setattr(shutil, "copy2", explode)
    with pytest.raises(profile_installer.InstallError):
        _install(binding, artifact, operation_id="t18-mid-commit")

    profile = binding.profile_root
    assert _digest(profile / "config.yaml") == before
    assert not (profile / "plugins" / "sage" / "__init__.py").exists()
    journal = receipts.load_run_journal(binding, "t18-mid-commit")
    assert not journal.is_complete


# ── 4. reinstall hash-idempotent ─────────────────────────────────────────────

def test_reinstall_produces_identical_managed_hashes(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _install(binding, artifact)
    first = {
        path: _digest(path)
        for path in sorted((binding.profile_root / "hooks").glob("*.sh"))
    }
    first_config = _digest(binding.profile_root / "config.yaml")

    _install(binding, artifact)
    second = {
        path: _digest(path)
        for path in sorted((binding.profile_root / "hooks").glob("*.sh"))
    }
    assert first == second
    assert _digest(binding.profile_root / "config.yaml") == first_config


# ── 5. unrelated bytes survive ───────────────────────────────────────────────

def test_unrelated_config_files_and_durable_state_survive(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    user_hook = binding.profile_root / "hooks" / "user-hook.sh"
    decisions = binding.workspace_root / ".sage" / "decisions.md"
    before = (_digest(user_hook), _digest(decisions))

    _install(binding, artifact)
    assert (_digest(user_hook), _digest(decisions)) == before
    assert "other_setting: 42" in (binding.profile_root / "config.yaml").read_text(
        encoding="utf-8"
    )


# ── 6. git destination stops before mutation ─────────────────────────────────

def test_git_managed_destination_stops_before_any_write(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    (binding.profile_root / "plugins" / "sage" / ".git").mkdir(parents=True)
    before = _digest(binding.profile_root / "config.yaml")

    with pytest.raises(profile_installer.InstallError) as caught:
        _install(binding, artifact)
    assert "git" in str(caught.value).lower()
    assert _digest(binding.profile_root / "config.yaml") == before
    assert not (binding.profile_root / "hooks" / ADAPTER).exists()


# ── 7. cross-profile authorities fail closed before mutation ─────────────────

def test_cross_profile_receipt_fails_closed_before_mutation(tmp_path) -> None:
    binding = _make_profile(tmp_path, "alpha")
    other = _make_profile(tmp_path, "beta")
    artifact = _make_artifact(tmp_path)
    # A receipt belonging to beta sits in alpha's receipt slot — planted
    # directly because the validated writer (correctly) refuses mismatches.
    foreign = receipts.InstallReceipt.create(
        binding=other,
        source_version="0.0.0",
        source_commit="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        managed_targets=[],
        config_records=[],
        allowlist_records=[],
    )
    binding.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    binding.receipt_path.write_text(
        json.dumps(foreign.to_mapping(), indent=2), encoding="utf-8"
    )
    before = _digest(binding.profile_root / "config.yaml")

    with pytest.raises(profile_installer.InstallError):
        _install(binding, artifact)
    assert _digest(binding.profile_root / "config.yaml") == before
    assert not (binding.profile_root / "plugins" / "sage" / "__init__.py").exists()


# ── 8. stale managed pruned, unmanaged survives ──────────────────────────────

def test_stale_managed_files_are_pruned_unmanaged_survives(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    stale_hook = binding.profile_root / "hooks" / "sage-old-gate.sh"
    stale_plugin = binding.profile_root / "plugins" / "sage" / "old.py"
    _write(stale_hook, "# stale\n")
    _write(stale_plugin, "# stale\n")
    prior = receipts.InstallReceipt.create(
        binding=binding,
        source_version="0.0.0",
        source_commit="cccccccccccccccccccccccccccccccccccccccc",
        managed_targets=[
            receipts.ManagedTarget.from_path(binding, stale_hook, _digest(stale_hook)),
            receipts.ManagedTarget.from_path(binding, stale_plugin, _digest(stale_plugin)),
        ],
        config_records=[],
        allowlist_records=[],
    )
    receipts.write_install_receipt(binding, prior)
    artifact = _make_artifact(tmp_path)
    user_hook = binding.profile_root / "hooks" / "user-hook.sh"
    before_user = _digest(user_hook)

    _install(binding, artifact)
    assert not stale_hook.exists()
    assert not stale_plugin.exists()
    assert _digest(user_hook) == before_user


# ── 9. journal lifecycle ─────────────────────────────────────────────────────

def test_journal_records_planned_writes_and_completes(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    result = _install(binding, artifact)
    journal = receipts.load_completed_run_journal(binding, result["operation_id"])
    assert journal.is_complete
    assert journal.planned_writes


# ── 10. config idempotent across reruns ──────────────────────────────────────

def test_config_commit_is_structural_and_idempotent(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _install(binding, artifact)
    first = (binding.profile_root / "config.yaml").read_text(encoding="utf-8")
    _install(binding, artifact)
    second = (binding.profile_root / "config.yaml").read_text(encoding="utf-8")
    assert first == second
    assert second.count("sage-hermes-gate.sh") == 11


# ── 11. prune bytes are restored when a later phase fails ────────────────────

def _plant_stale(binding, target_path: pathlib.Path, content: str = "# stale\n"):
    _write(target_path, content)
    prior = receipts.InstallReceipt.create(
        binding=binding,
        source_version="0.0.0",
        source_commit="cccccccccccccccccccccccccccccccccccccccc",
        managed_targets=[
            receipts.ManagedTarget.from_path(binding, target_path, _digest(target_path))
        ],
        config_records=[],
        allowlist_records=[],
    )
    receipts.write_install_receipt(binding, prior)


def test_failure_after_prune_restores_stale_files_and_config(tmp_path, monkeypatch) -> None:
    binding = _make_profile(tmp_path)
    stale_hook = binding.profile_root / "hooks" / "sage-old-gate.sh"
    _plant_stale(binding, stale_hook)
    artifact = _make_artifact(tmp_path)
    before_config = _digest(binding.profile_root / "config.yaml")

    real_validate = hook_config.validate_candidate_config
    calls = []

    def fail_on_activation(text):
        calls.append(1)
        if len(calls) >= 2:
            return {"ok": False, "blocking_count": 0, "observer_count": 0,
                    "errors": ["injected activation failure"]}
        return real_validate(text)

    monkeypatch.setattr(
        profile_installer.hook_config, "validate_candidate_config", fail_on_activation
    )
    with pytest.raises(profile_installer.InstallError):
        _install(binding, artifact)

    assert stale_hook.is_file() and stale_hook.read_text(encoding="utf-8") == "# stale\n"
    assert _digest(binding.profile_root / "config.yaml") == before_config
    assert not (binding.profile_root / "plugins" / "sage" / "__init__.py").exists()
    assert not (binding.profile_root / "hooks" / ADAPTER).exists()


# ── 12. workspace-owned stale target prunes from the workspace root ──────────

def test_workspace_owned_stale_target_prunes_from_workspace_root(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    stale_runtime = binding.workspace_root / "sage" / "runtime" / "old.py"
    _plant_stale(binding, stale_runtime)
    artifact = _make_artifact(tmp_path)

    result = _install(binding, artifact)
    assert result["ok"] is True
    assert not stale_runtime.exists()


# ── 13. a user entry merely mentioning the adapter survives the strip ────────

def test_user_entry_mentioning_adapter_in_comment_survives(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    config_path = binding.profile_root / "config.yaml"
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
    artifact = _make_artifact(tmp_path)

    _install(binding, artifact)
    merged = config_path.read_text(encoding="utf-8")
    assert "user-hook.sh" in merged
    assert "borrows the sage-hermes-gate.sh pattern" in merged


# ── 14. user-edited managed file is preserved, never swept ───────────────────

def test_user_edited_managed_file_is_not_pruned(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    stale_hook = binding.profile_root / "hooks" / "sage-old-gate.sh"
    _plant_stale(binding, stale_hook, content="# original\n")
    _write(stale_hook, "# user edit\n")
    artifact = _make_artifact(tmp_path)

    _install(binding, artifact)
    assert stale_hook.read_text(encoding="utf-8") == "# user edit\n"


# ── T19: update, injected rollback, crash recovery ───────────────────────────

def _seed_installed(binding, artifact, version="1.3.18"):
    _install(
        binding,
        artifact,
        source_version=version,
        source_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )


def test_update_or_rollback_requires_an_existing_receipt(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    with pytest.raises(profile_installer.InstallError) as caught:
        profile_installer.update(
            binding=binding,
            artifact_dir=artifact,
            consent_granted=True,
            source_version="1.3.19",
            source_commit="dddddddddddddddddddddddddddddddddddddddd",
            bash_path=BASH_EXE,
        )
    assert "install" in str(caught.value).lower() or "migrat" in str(caught.value).lower()


def test_update_or_rollback_rejects_conflicting_binding_and_demands_migration(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    # Tamper the config binding so it no longer matches the receipt.
    config_path = binding.profile_root / "config.yaml"
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace(binding.profile_id, "someone-else", 1), encoding="utf-8"
    )

    with pytest.raises(profile_installer.InstallError) as caught:
        profile_installer.update(
            binding=binding,
            artifact_dir=artifact,
            consent_granted=True,
            source_version="1.3.19",
            source_commit="dddddddddddddddddddddddddddddddddddddddd",
            bash_path=BASH_EXE,
        )
    assert "migrat" in str(caught.value).lower()


def test_update_or_rollback_replaces_managed_and_prunes_stale(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    stale_hook = binding.profile_root / "hooks" / "sage-old-gate.sh"
    _write(stale_hook, "# stale\n")
    # Widen the receipt with the stale managed entry (the update must prune it).
    prior = receipts.load_install_receipt(binding)
    widened = receipts.InstallReceipt.create(
        binding=binding,
        source_version=prior.source_version,
        source_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        managed_targets=list(prior.managed_targets)
        + [receipts.ManagedTarget.from_path(binding, stale_hook, _digest(stale_hook))],
        config_records=[],
        allowlist_records=[],
    )
    receipts.write_install_receipt(binding, widened)

    result = profile_installer.update(
        binding=binding,
        artifact_dir=artifact,
        consent_granted=True,
        source_version="1.3.19",
        source_commit="dddddddddddddddddddddddddddddddddddddddd",
        bash_path=BASH_EXE,
        activation_probe=_verified_activation,
    )
    assert result["ok"] is True
    assert not stale_hook.exists()
    receipt = receipts.load_install_receipt(binding)
    assert receipt.source_version == "1.3.19"


def test_update_or_rollback_injected_failure_restores_exact_prior_state(tmp_path, monkeypatch) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    profile = binding.profile_root
    prior_config = (profile / "config.yaml").read_bytes()
    prior_hook = (profile / "hooks" / ADAPTER).read_bytes()
    prior_receipt = binding.receipt_path.read_bytes()

    real_copy = shutil.copy2
    calls = []

    def explode(dest, src, *args, **kwargs):
        calls.append(1)
        if len(calls) >= 3:
            raise OSError("injected update failure")
        return real_copy(dest, src, *args, **kwargs)

    monkeypatch.setattr(shutil, "copy2", explode)
    with pytest.raises(profile_installer.InstallError):
        profile_installer.update(
            binding=binding,
            artifact_dir=artifact,
            consent_granted=True,
            source_version="1.3.19",
            source_commit="dddddddddddddddddddddddddddddddddddddddd",
            bash_path=BASH_EXE,
        )

    assert (profile / "config.yaml").read_bytes() == prior_config
    assert (profile / "hooks" / ADAPTER).read_bytes() == prior_hook
    assert binding.receipt_path.read_bytes() == prior_receipt


def test_update_or_rollback_crash_resumption_restores_from_incomplete_journal(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    profile = binding.profile_root
    prior_config = (profile / "config.yaml").read_bytes()
    prior_hook = (profile / "hooks" / ADAPTER).read_bytes()

    real_copy = shutil.copy2
    calls = []

    def explode(dest, src, *args, **kwargs):
        calls.append(1)
        if len(calls) >= 2:
            raise OSError("simulated crash")
        return real_copy(dest, src, *args, **kwargs)

    import unittest.mock as mock

    with mock.patch.object(shutil, "copy2", explode):
        with pytest.raises(profile_installer.InstallError):
            profile_installer.update(
                binding=binding,
                artifact_dir=artifact,
                consent_granted=True,
                source_version="1.3.19",
                source_commit="dddddddddddddddddddddddddddddddddddddddd",
                bash_path=BASH_EXE,
                operation_id="t19-crash",
            )
    # Corrupt the state further to simulate a crash mid-restore.
    (profile / "hooks" / ADAPTER).write_text("# half-written\n", encoding="utf-8")

    with pytest.raises(profile_installer.InstallError, match="post-crash"):
        profile_installer.resume_incomplete(
            binding=binding, operation_id="t19-crash"
        )
    assert (profile / "config.yaml").read_bytes() == prior_config
    assert (profile / "hooks" / ADAPTER).read_text(encoding="utf-8") == "# half-written\n"
    assert not receipts.load_run_journal(binding, "t19-crash").is_complete


def test_update_or_rollback_framework_and_profile_updates_report_distinct_evidence(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    result = profile_installer.update(
        binding=binding,
        artifact_dir=artifact,
        consent_granted=True,
        source_version="1.3.19",
        source_commit="dddddddddddddddddddddddddddddddddddddddd",
        bash_path=BASH_EXE,
        activation_probe=_verified_activation,
    )
    assert result["operation"] == "update"
    journal = receipts.load_completed_run_journal(binding, result["operation_id"])
    assert journal.operation == "update"


# ── T19 revision coverage: resume paths, pack integrity, evidence precision ──

def _craft_crashed_run(binding, artifact, operation_id="t19-crafted", stale_targets=()):
    """Journal incomplete + durable pack, exactly as a dead process leaves them."""

    current_config = (binding.profile_root / "config.yaml").read_text(encoding="utf-8")
    writes = profile_installer._planned_writes(binding, artifact)
    planned = [
        receipts.ManagedTarget.from_path(binding, dest, _digest(src))
        for src, dest in writes
    ]
    candidate_receipt = receipts.InstallReceipt.create(
        binding=binding,
        source_version="1.3.19",
        source_commit="d" * 40,
        managed_targets=planned,
        config_records=[],
        allowlist_records=[],
    )
    receipts.begin_run_journal(
        binding=binding,
        operation_id=operation_id,
        operation="update",
        source_version="1.3.19",
        source_commit="dddddddddddddddddddddddddddddddddddddddd",
        previous_managed_targets=list(
            receipts.load_install_receipt(binding).managed_targets
        ),
        previous_config_records=[],
        previous_allowlist_records=[],
        planned_writes=planned,
        planned_removals=[
            receipts.TargetRef(owner=t.owner, relative_path=t.relative_path)
            for t in stale_targets
        ],
    )
    profile_installer._write_backup_pack(
        binding,
        operation_id,
        (binding.profile_root / "config.yaml").read_bytes(),
        writes,
        stale_targets,
        candidate_receipt=candidate_receipt,
    )
    return candidate_receipt


def test_update_or_rollback_resume_removes_non_existed_destinations(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    _craft_crashed_run(binding, artifact)
    # Crash left a freshly-written file that did not exist before.
    new_gate = binding.profile_root / "hooks" / "sage-config-gate.sh"
    assert new_gate.is_file()  # present from seed
    new_gate.unlink()          # simulate: never existed pre-crash
    _write(new_gate, "# crash-written\n")

    with pytest.raises(profile_installer.InstallError, match="post-crash"):
        profile_installer.resume_incomplete(
            binding=binding, operation_id="t19-crafted"
        )
    # Unknown bytes after the crash are not evidence of a partial candidate;
    # bounded recovery preserves them and leaves the journal incomplete.
    assert new_gate.read_text(encoding="utf-8") == "# crash-written\n"
    assert not receipts.load_run_journal(binding, "t19-crafted").is_complete


def test_update_or_rollback_resume_restores_pruned_file(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    stale = binding.profile_root / "hooks" / "sage-old-gate.sh"
    _write(stale, "# stale\n")
    target = receipts.ManagedTarget.from_path(binding, stale, _digest(stale))
    _craft_crashed_run(binding, artifact, stale_targets=[target])
    stale.unlink()  # the crash pruned it, then died mid-flight

    profile_installer.resume_incomplete(binding=binding, operation_id="t19-crafted")
    assert stale.read_text(encoding="utf-8") == "# stale\n"


def test_resume_restores_prior_receipt_before_completing_recovery(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    prior_receipt_bytes = binding.receipt_path.read_bytes()
    adapter_source = artifact / "hooks" / ADAPTER
    adapter_destination = binding.profile_root / "hooks" / ADAPTER
    prior_adapter_bytes = adapter_destination.read_bytes()

    adapter_source.write_text("# candidate adapter\n", encoding="utf-8")
    candidate_receipt = _craft_crashed_run(binding, artifact)
    shutil.copy2(adapter_source, adapter_destination)
    receipts.write_install_receipt(binding, candidate_receipt)
    assert binding.receipt_path.read_bytes() != prior_receipt_bytes

    result = profile_installer.resume_incomplete(
        binding=binding, operation_id="t19-crafted"
    )

    assert result["restored"] is True
    assert adapter_destination.read_bytes() == prior_adapter_bytes
    assert binding.receipt_path.read_bytes() == prior_receipt_bytes
    restored_receipt = receipts.load_install_receipt(binding)
    for target in restored_receipt.managed_targets:
        target_path = profile_installer._owner_root(binding, target.owner) / target.relative_path
        assert _digest(target_path) == target.sha256
    assert receipts.load_run_journal(binding, "t19-crafted").is_complete


def test_update_or_rollback_resume_refuses_torn_or_missing_pack(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    _craft_crashed_run(binding, artifact)
    pack = binding.runs_root / "t19-crafted.backup"
    (pack / "manifest.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(profile_installer.InstallError):
        profile_installer.resume_incomplete(binding=binding, operation_id="t19-crafted")

    _craft_crashed_run(binding, artifact, operation_id="t19-missing")
    shutil.rmtree(binding.runs_root / "t19-missing.backup")
    with pytest.raises(profile_installer.InstallError):
        profile_installer.resume_incomplete(binding=binding, operation_id="t19-missing")


def test_update_or_rollback_resume_rejects_pack_entries_outside_journal(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    _craft_crashed_run(binding, artifact)
    pack = binding.runs_root / "t19-crafted.backup"
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    manifest["writes"].append(
        {"dest": os.fspath(binding.profile_root / "hooks" / "never-planned.sh"),
         "existed": False, "bak": None, "sha256": None}
    )
    (pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(profile_installer.InstallError):
        profile_installer.resume_incomplete(binding=binding, operation_id="t19-crafted")
    assert not (binding.profile_root / "hooks" / "never-planned.sh").exists()


def test_update_or_rollback_journal_records_actual_pruned_count(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    stale_hook = binding.profile_root / "hooks" / "sage-old-gate.sh"
    _write(stale_hook, "# original\n")
    prior = receipts.load_install_receipt(binding)
    widened = receipts.InstallReceipt.create(
        binding=binding,
        source_version=prior.source_version,
        source_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        managed_targets=list(prior.managed_targets)
        + [receipts.ManagedTarget.from_path(binding, stale_hook, _digest(stale_hook))],
        config_records=[],
        allowlist_records=[],
    )
    receipts.write_install_receipt(binding, widened)
    _write(stale_hook, "# user edit\n")  # on-disk bytes differ -> preserved

    result = profile_installer.update(
        binding=binding,
        artifact_dir=artifact,
        consent_granted=True,
        source_version="1.3.19",
        source_commit="dddddddddddddddddddddddddddddddddddddddd",
        bash_path=BASH_EXE,
        activation_probe=_verified_activation,
    )
    journal = receipts.load_completed_run_journal(binding, result["operation_id"])
    assert stale_hook.read_text(encoding="utf-8") == "# user edit\n"
    mapping = journal.to_mapping()
    assert mapping["result"]["pruned"] == 0
    assert mapping["result"]["skipped_user_edited"] == 1


def test_update_or_rollback_pack_removed_after_success(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    result = _install(binding, artifact)
    assert not (binding.runs_root / ("%s.backup" % result["operation_id"])).exists()


# ── T26 blocker repair: one receipt transaction owns workspace + activation ──

def test_install_receipt_owns_workspace_runtime_instructions_and_exact_hook_records(
    tmp_path,
) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)

    result = _install(binding, artifact, framework_root=ROOT)

    assert result["activation"]["fresh_process_verified"] is True
    assert (binding.workspace_root / ".hermes.md").is_file()
    assert (binding.workspace_root / "sage" / "VERSION").read_bytes() == (
        ROOT / "VERSION"
    ).read_bytes()
    receipt = receipts.load_install_receipt(binding)
    owned = {(target.owner, target.relative_path) for target in receipt.managed_targets}
    assert ("workspace", ".hermes.md") in owned
    assert ("workspace", "sage/VERSION") in owned
    assert len(receipt.config_records) == 12
    assert len(receipt.allowlist_records) == 12
    session_records = [
        record
        for record in receipt.config_records
        if record["event"] == "on_session_start"
    ]
    assert len(session_records) == 1
    assert "sage-session-init.sh" in session_records[0]["command"]
    assert receipt.allowlist_records == tuple(
        {"event": record["event"], "command": record["command"]}
        for record in receipt.config_records
    )


def test_first_install_bootstraps_default_durable_enforcement_config(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    state_config = binding.state_root / "config.yaml"
    assert not state_config.exists()

    _install(binding, artifact, framework_root=ROOT)

    text = state_config.read_text(encoding="utf-8")
    assert "hard_enforcement: true" in text
    assert "secrets_gate: true" in text
    receipt = receipts.load_install_receipt(binding)
    assert all(target.relative_path != ".sage/config.yaml" for target in receipt.managed_targets)


def test_failed_first_install_removes_bootstrapped_durable_config(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    state_config = binding.state_root / "config.yaml"

    with pytest.raises(profile_installer.InstallError, match="activation"):
        _install(
            binding,
            artifact,
            framework_root=ROOT,
            activation_probe=lambda **_kwargs: {
                "ok": False,
                "fresh_process_verified": False,
                "detail": "injected first-install activation failure",
            },
        )

    assert not state_config.exists()
    assert not binding.receipt_path.exists()


def test_install_refuses_git_managed_plugin_before_workspace_staging(
    tmp_path, monkeypatch
) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    (binding.plugin_root / ".git").mkdir(parents=True)
    staged = False

    def observe_stage(*_args, **_kwargs):
        nonlocal staged
        staged = True
        raise AssertionError("workspace staging ran before Git ownership preflight")

    monkeypatch.setattr(profile_installer, "_stage_workspace", observe_stage)

    with pytest.raises(profile_installer.InstallError, match="Git repository/worktree"):
        profile_installer.install(
            binding=binding,
            artifact_dir=artifact,
            framework_root=tmp_path / "framework",
            consent_granted=True,
            source_version="1.3.18",
            source_commit="a" * 40,
            activation_probe=_verified_activation,
        )

    assert staged is False


def test_existing_durable_config_is_preserved_byte_exact(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    state_config = binding.state_root / "config.yaml"
    crlf = bytes((13, 10))
    before = b"hard_enforcement: false" + crlf + b"owner: user" + crlf
    state_config.write_bytes(before)

    _install(binding, artifact, framework_root=ROOT)

    assert state_config.read_bytes() == before


def test_install_refuses_unreceipted_workspace_managed_collision(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    instructions = binding.workspace_root / ".hermes.md"
    instructions.write_text("# user-owned instructions\n", encoding="utf-8")
    before = instructions.read_bytes()

    with pytest.raises(profile_installer.InstallError, match="receipt ownership"):
        _install(binding, artifact, framework_root=ROOT)

    assert instructions.read_bytes() == before
    assert not (binding.profile_root / "plugins" / "sage").exists()
    assert not binding.receipt_path.exists()


def test_activation_failure_rolls_back_profile_workspace_config_and_receipt(
    tmp_path,
) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _install(binding, artifact, framework_root=ROOT)
    before_profile = {
        path.relative_to(binding.profile_root).as_posix(): _digest(path)
        for path in binding.profile_root.rglob("*")
        if path.is_file() and ".sage/receipts/runs/" not in path.as_posix()
    }
    before_receipt = binding.receipt_path.read_bytes()
    before_config = (binding.profile_root / "config.yaml").read_bytes()

    rollback_calls = []

    def fail_activation(**_kwargs):
        assert (binding.workspace_root / ".hermes.md").is_file()
        assert (binding.workspace_root / "sage" / "VERSION").is_file()
        assert hook_config.validate_candidate_config(
            (binding.profile_root / "config.yaml").read_text(encoding="utf-8")
        )["ok"]
        # Candidate receipt is published inside the rollback envelope so the
        # fresh plugin process can validate its binding authority.
        assert receipts.load_install_receipt(binding).source_version == "1.3.19"
        return {"ok": False, "detail": "injected fresh-process activation failure"}

    def rollback_activation(**snapshot):
        assert (binding.profile_root / "config.yaml").read_bytes() == before_config
        assert binding.receipt_path.read_bytes() == before_receipt
        rollback_calls.append(snapshot)
        return {"ok": True, "fresh_process_verified": True}

    with pytest.raises(profile_installer.InstallError, match="activation"):
        profile_installer.update(
            binding=binding,
            artifact_dir=artifact,
            framework_root=ROOT,
            consent_granted=True,
            source_version="1.3.19",
            source_commit="dddddddddddddddddddddddddddddddddddddddd",
            bash_path=BASH_EXE,
            operation_id="t26-activation-rollback",
            activation_probe=fail_activation,
            activation_rollback=rollback_activation,
        )

    assert len(rollback_calls) == 1
    assert len(rollback_calls[0]["config_records"]) == 12
    assert len(rollback_calls[0]["allowlist_records"]) == 12
    journal = receipts.load_run_journal(binding, "t26-activation-rollback")
    assert not journal.is_complete
    assert len(journal.previous_config_records) == 12
    assert len(journal.previous_allowlist_records) == 12
    after_profile = {
        path.relative_to(binding.profile_root).as_posix(): _digest(path)
        for path in binding.profile_root.rglob("*")
        if path.is_file() and ".sage/receipts/runs/" not in path.as_posix()
    }
    assert after_profile == before_profile
    assert binding.receipt_path.read_bytes() == before_receipt


def test_resume_incomplete_refuses_to_clobber_post_crash_user_bytes(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    _seed_installed(binding, artifact)
    _craft_crashed_run(binding, artifact, operation_id="t19-bounded")
    destination = binding.profile_root / "hooks" / "sage-config-gate.sh"
    destination.write_text("# post-crash user bytes\n", encoding="utf-8")

    with pytest.raises(profile_installer.InstallError, match="post-crash"):
        profile_installer.resume_incomplete(
            binding=binding, operation_id="t19-bounded"
        )

    assert destination.read_text(encoding="utf-8") == "# post-crash user bytes\n"
    assert not receipts.load_run_journal(binding, "t19-bounded").is_complete


def test_install_refuses_a_precreated_backup_pack_directory(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    pack = binding.runs_root / "precreated-pack.backup" / "pack"
    pack.mkdir(parents=True)
    sentinel = pack / "attacker-sentinel.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")
    with receipts.profile_transaction_lock(binding):
        pass

    def snapshot_tree(root: pathlib.Path):
        snapshot = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                snapshot[relative] = ("symlink", os.readlink(path))
            elif path.is_file():
                snapshot[relative] = ("file", path.read_bytes())
            else:
                snapshot[relative] = ("directory", None)
        return snapshot

    before = snapshot_tree(binding.profile_root)

    with pytest.raises(profile_installer.InstallError, match="backup pack.*already exists"):
        _install(binding, artifact, operation_id="precreated-pack")

    assert snapshot_tree(binding.profile_root) == before
    assert sentinel.read_text(encoding="utf-8") == "preserve\n"
    assert not binding.run_journal_path("precreated-pack").exists()
    assert not binding.run_journal_path("precreated-pack").with_name(
        ".precreated-pack.json.lock"
    ).exists()
    assert not (binding.profile_root / "plugins" / "sage" / "__init__.py").exists()


def test_install_is_excluded_by_a_competing_profile_transaction(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    artifact = _make_artifact(tmp_path)
    assert hasattr(receipts, "profile_transaction_lock")
    locked = threading.Event()
    release = threading.Event()

    def hold_lock():
        with receipts.profile_transaction_lock(binding):
            locked.set()
            assert release.wait(timeout=10)

    holder = threading.Thread(target=hold_lock)
    holder.start()
    assert locked.wait(timeout=5)
    try:
        with pytest.raises(profile_installer.InstallError, match="profile operation|already being changed"):
            _install(binding, artifact, operation_id="blocked-by-lock")
    finally:
        release.set()
        holder.join(timeout=10)

    assert not holder.is_alive()
    assert not (binding.profile_root / "plugins" / "sage" / "__init__.py").exists()


def test_profile_transaction_lock_does_not_relabel_body_receipt_errors(tmp_path) -> None:
    binding = _make_profile(tmp_path)

    with pytest.raises(receipts.ReceiptError, match="body receipt failure"):
        with profile_installer._acquire_profile_transaction_lock(binding):
            raise receipts.ReceiptError("body receipt failure")


def test_profile_transaction_lock_keeps_body_error_primary_when_unlock_fails(
    tmp_path, monkeypatch
) -> None:
    binding = _make_profile(tmp_path)

    if os.name == "nt":
        original_unlock = receipts.msvcrt.locking

        def fail_unlock(descriptor, mode, count):
            if mode == receipts.msvcrt.LK_UNLCK:
                raise OSError("injected unlock failure")
            return original_unlock(descriptor, mode, count)

        monkeypatch.setattr(receipts.msvcrt, "locking", fail_unlock)
    else:
        original_unlock = receipts.fcntl.flock

        def fail_unlock(descriptor, operation):
            if operation == receipts.fcntl.LOCK_UN:
                raise OSError("injected unlock failure")
            return original_unlock(descriptor, operation)

        monkeypatch.setattr(receipts.fcntl, "flock", fail_unlock)

    with pytest.raises(receipts.ReceiptError, match="body failure sentinel") as caught:
        with profile_installer._acquire_profile_transaction_lock(binding):
            raise receipts.ReceiptError("body failure sentinel")

    notes = getattr(caught.value, "__notes__", ())
    assert any("cannot release profile transaction lock" in note for note in notes)
    release_error = getattr(caught.value, "profile_transaction_release_error", None)
    assert isinstance(release_error, receipts.ReceiptError)
    assert "injected unlock failure" in str(release_error)


def test_config_candidate_replaces_legacy_blanket_hook_consent(tmp_path) -> None:
    binding = _make_profile(tmp_path)
    current = (
        _config_text(binding)
        + "hooks_auto_accept: true\n"
        + "security:\n  hooks_auto_accept: true\n"
    )

    candidate = profile_installer._config_candidate(current, binding, BASH_EXE)
    document = hook_config.yaml.safe_load(candidate)

    assert "hooks_auto_accept" not in document
    assert document["security"]["hooks_auto_accept"] is True
    assert hook_config.validate_candidate_config(candidate)["ok"] is True
