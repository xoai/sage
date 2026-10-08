#!/usr/bin/env python3
"""Fail-closed receipt and run-journal tests for one Hermes profile."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import threading

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SETUP_ROOT = (
    REPO_ROOT
    / "runtime"
    / "platforms"
    / "community"
    / "hermes"
    / "setup"
)
sys.path.insert(0, os.fspath(SETUP_ROOT))

import receipts as receipts_module  # noqa: E402
from profile_binding import ProfileBinding  # noqa: E402
from receipts import (  # noqa: E402
    INSTALL_RECEIPT_SCHEMA,
    RUN_JOURNAL_SCHEMA,
    InstallReceipt,
    ManagedTarget,
    ReceiptError,
    RunJournal,
    TargetRef,
    begin_run_journal,
    complete_run_journal,
    load_completed_run_journal,
    load_install_receipt,
    load_run_journal,
    write_install_receipt,
)


SOURCE_VERSION = "1.3.18"
SOURCE_COMMIT = "a" * 40
FIRST_TIME = "2026-08-10T12:00:00Z"
SECOND_TIME = "2026-08-10T12:05:00Z"


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _write(path: pathlib.Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


@pytest.fixture
def profile_tree(tmp_path):
    collection = tmp_path / "hermes"
    profile_a = collection / "profiles" / "alpha"
    profile_b = collection / "profiles" / "beta"
    workspace_a = profile_a / "workspace"
    workspace_b = profile_b / "workspace"
    global_state = tmp_path / ".sage"
    for directory in (workspace_a, workspace_b, global_state):
        directory.mkdir(parents=True)
    (global_state / "sentinel").write_text("global", encoding="utf-8")
    return {
        "root": tmp_path,
        "collection": collection,
        "profile_a": profile_a,
        "profile_b": profile_b,
        "workspace_a": workspace_a,
        "workspace_b": workspace_b,
        "global_state": global_state,
    }


def _binding(tree, profile="alpha"):
    suffix = "a" if profile == "alpha" else "b"
    return ProfileBinding.from_explicit(
        collection_root=tree["collection"],
        profile_id=profile,
        profile_root=tree["profile_" + suffix],
        workspace_root=tree["workspace_" + suffix],
    )


def _managed_targets(binding):
    return [
        ManagedTarget.from_path(
            binding,
            binding.workspace_root / "sage" / "runtime" / "current.py",
            _sha(b"runtime"),
        ),
        ManagedTarget.from_path(
            binding,
            binding.profile_root / "plugins" / "sage" / "__init__.py",
            _sha(b"plugin"),
        ),
        ManagedTarget.from_path(
            binding,
            binding.workspace_root / ".hermes.md",
            _sha(b"instructions"),
        ),
    ]


def _config_records():
    return [
        {
            "event": "pre_tool_call",
            "command": '"C:/Program Files/Git/usr/bin/bash.exe" hook.sh',
            "matcher": "write_file|patch",
            "fail_closed": True,
        }
    ]


def _allowlist_records():
    return [
        {
            "event": "pre_tool_call",
            "command": '"C:/Program Files/Git/usr/bin/bash.exe" hook.sh',
        }
    ]


def _receipt(binding, *, version=SOURCE_VERSION, timestamp=FIRST_TIME):
    return InstallReceipt.create(
        binding=binding,
        source_version=version,
        source_commit=SOURCE_COMMIT,
        managed_targets=reversed(_managed_targets(binding)),
        config_records=_config_records(),
        allowlist_records=_allowlist_records(),
        created_at=timestamp,
        updated_at=timestamp,
    )


def _journal_kwargs(binding):
    previous = _receipt(binding)
    writes = _managed_targets(binding)
    removals = [
        TargetRef.from_path(
            binding,
            binding.profile_root / "hooks" / "sage-obsolete.sh",
        )
    ]
    return {
        "binding": binding,
        "operation_id": "update-20260810-001",
        "operation": "update",
        "source_version": SOURCE_VERSION,
        "source_commit": SOURCE_COMMIT,
        "previous_managed_targets": previous.managed_targets,
        "previous_config_records": previous.config_records,
        "previous_allowlist_records": previous.allowlist_records,
        "planned_writes": writes,
        "planned_removals": removals,
        "started_at": FIRST_TIME,
    }


def _write_raw(path: pathlib.Path, mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(mapping, sort_keys=True, indent=2) + "\n")


def _race_replace_at(monkeypatch, destination: pathlib.Path):
    original_replace = receipts_module.os.replace
    barrier = threading.Barrier(2)

    def racing_replace(source, target):
        if pathlib.Path(target) == destination:
            try:
                barrier.wait(timeout=1.0)
            except threading.BrokenBarrierError:
                pass
        return original_replace(source, target)

    monkeypatch.setattr(receipts_module.os, "replace", racing_replace)


def _lock_path(document_path: pathlib.Path) -> pathlib.Path:
    return document_path.with_name(".%s.lock" % document_path.name)


def _parallel_outcomes(worker, workers=8):
    start = threading.Barrier(workers)

    def synchronized(index):
        start.wait()
        return worker(index)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(synchronized, range(workers)))


def test_receipts_module_supports_installed_package_import() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from runtime.platforms.community.hermes.setup.receipts "
                "import INSTALL_RECEIPT_SCHEMA; print(INSTALL_RECEIPT_SCHEMA)"
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == INSTALL_RECEIPT_SCHEMA


def test_install_receipt_is_versioned_bound_canonical_and_timestamp_stable(profile_tree):
    binding = _binding(profile_tree)
    first = _receipt(binding, timestamp=FIRST_TIME)
    second = _receipt(binding, timestamp=SECOND_TIME)
    normal_order = InstallReceipt.create(
        binding=binding,
        source_version=SOURCE_VERSION,
        source_commit=SOURCE_COMMIT,
        managed_targets=_managed_targets(binding),
        config_records=_config_records(),
        allowlist_records=_allowlist_records(),
        created_at=FIRST_TIME,
        updated_at=FIRST_TIME,
    )

    mapping = first.to_mapping()
    assert set(mapping) == {
        "schema",
        "schema_version",
        "binding",
        "source",
        "managed_targets",
        "config_records",
        "allowlist_records",
        "semantic_hash",
        "timestamps",
    }
    assert mapping["schema"] == INSTALL_RECEIPT_SCHEMA
    assert mapping["schema_version"] == 1
    assert mapping["binding"] == binding.to_mapping()
    assert mapping["source"] == {
        "version": SOURCE_VERSION,
        "commit": SOURCE_COMMIT,
    }
    assert [
        (item["owner"], item["path"])
        for item in mapping["managed_targets"]
    ] == sorted(
        (item["owner"], item["path"])
        for item in mapping["managed_targets"]
    )
    assert mapping["config_records"] == _config_records()
    assert mapping["allowlist_records"] == _allowlist_records()
    assert first.semantic_hash == second.semantic_hash
    assert first.semantic_hash == normal_order.semantic_hash
    assert first.to_mapping()["timestamps"] != second.to_mapping()["timestamps"]


def test_install_receipt_accepts_the_canonical_nonblocking_session_hook(profile_tree):
    binding = _binding(profile_tree)
    command = (
        '"C:/Program Files/Git/usr/bin/bash.exe" '
        '"G:/hermes/profiles/alpha/hooks/sage-session-init.sh"'
    )
    config_record = {
        "event": "on_session_start",
        "command": command,
        "matcher": None,
        "fail_closed": False,
    }
    allowlist_record = {"event": "on_session_start", "command": command}

    receipt = InstallReceipt.create(
        binding=binding,
        source_version=SOURCE_VERSION,
        source_commit=SOURCE_COMMIT,
        managed_targets=_managed_targets(binding),
        config_records=[config_record],
        allowlist_records=[allowlist_record],
        created_at=FIRST_TIME,
        updated_at=FIRST_TIME,
    )

    assert receipt.config_records == (config_record,)
    assert receipt.allowlist_records == (allowlist_record,)


def test_install_receipt_round_trips_atomically_only_in_the_bound_workspace(profile_tree):
    alpha = _binding(profile_tree, "alpha")
    beta = _binding(profile_tree, "beta")
    receipt = _receipt(alpha)
    sibling_before = list(beta.workspace_root.rglob("*"))
    global_before = (profile_tree["global_state"] / "sentinel").read_bytes()

    written = write_install_receipt(alpha, receipt)
    loaded = load_install_receipt(alpha)

    assert written == alpha.receipt_path
    assert loaded == receipt
    assert loaded.binding == alpha
    assert list(beta.workspace_root.rglob("*")) == sibling_before
    assert (profile_tree["global_state"] / "sentinel").read_bytes() == global_before
    assert not beta.receipt_path.exists()


@pytest.mark.parametrize("schema_version", [True, 1.0, "1", 2])
def test_install_receipt_schema_version_requires_exact_integer_one(
    profile_tree, schema_version
):
    binding = _binding(profile_tree)
    mapping = _receipt(binding).to_mapping()
    mapping["schema_version"] = schema_version
    _write_raw(binding.receipt_path, mapping)

    with pytest.raises(ReceiptError, match="schema version"):
        load_install_receipt(binding)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda value: value.update(schema="other.receipt"), "schema"),
        (lambda value: value.update(schema_version=2), "schema version"),
        (lambda value: value.update(extra=True), "unexpected"),
        (lambda value: value.pop("source"), "missing"),
        (lambda value: value.update(semantic_hash="0" * 64), "semantic hash"),
    ],
)
def test_schema_mismatch_tampering_and_unknown_fields_fail_closed(
    profile_tree, mutation, match
):
    binding = _binding(profile_tree)
    mapping = _receipt(binding).to_mapping()
    mutation(mapping)
    _write_raw(binding.receipt_path, mapping)

    with pytest.raises(ReceiptError, match=match):
        load_install_receipt(binding)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema":',
        b'{"schema":"first","schema":"second"}',
        b'\xff\xfe\x00',
        b'{"value":NaN}',
    ],
)
def test_truncated_corrupt_duplicate_key_and_nonfinite_json_fail_closed(
    profile_tree, raw
):
    binding = _binding(profile_tree)
    _write(binding.receipt_path, raw)

    with pytest.raises(ReceiptError, match="valid strict JSON"):
        load_install_receipt(binding)


def test_cross_profile_receipt_fails_closed_even_when_both_profiles_exist(profile_tree):
    alpha = _binding(profile_tree, "alpha")
    beta = _binding(profile_tree, "beta")
    _write_raw(alpha.receipt_path, _receipt(beta).to_mapping())

    with pytest.raises(ReceiptError, match="binding|profile"):
        load_install_receipt(alpha)


def test_noncanonical_binding_in_receipt_fails_closed(profile_tree):
    binding = _binding(profile_tree)
    mapping = _receipt(binding).to_mapping()
    mapping["binding"]["workspace_root"] = os.fspath(
        binding.workspace_root / "child" / ".."
    )
    _write_raw(binding.receipt_path, mapping)

    with pytest.raises(ReceiptError, match="canonical"):
        load_install_receipt(binding)


def test_managed_target_rejects_outside_protected_duplicate_and_bad_hashes(profile_tree):
    binding = _binding(profile_tree)
    outside = profile_tree["root"] / "outside.txt"
    protected = binding.profile_root / "SOUL.md"
    invalid_paths = (outside, protected, binding.workspace_root / "notes.txt")

    for path in invalid_paths:
        with pytest.raises(ReceiptError):
            ManagedTarget.from_path(binding, path, _sha(b"x"))
    with pytest.raises(ReceiptError, match="sha256"):
        ManagedTarget.from_path(
            binding,
            binding.workspace_root / ".hermes.md",
            "not-a-digest",
        )

    target = ManagedTarget.from_path(
        binding,
        binding.workspace_root / ".hermes.md",
        _sha(b"x"),
    )
    with pytest.raises(ReceiptError, match="duplicate"):
        InstallReceipt.create(
            binding=binding,
            source_version=SOURCE_VERSION,
            source_commit=SOURCE_COMMIT,
            managed_targets=[target, target],
            config_records=[],
            allowlist_records=[],
            created_at=FIRST_TIME,
            updated_at=FIRST_TIME,
        )


def test_target_records_reject_aliases_and_reparse_escapes(profile_tree):
    binding = _binding(profile_tree)
    outside = profile_tree["root"] / "outside"
    outside.mkdir()
    alias = binding.workspace_root / "sage"
    try:
        alias.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip("directory symlinks unavailable: %s" % exc)

    try:
        with pytest.raises(ReceiptError, match="canonical|link|reparse|escape"):
            ManagedTarget.from_path(binding, alias / "runtime.py", _sha(b"x"))
    finally:
        alias.unlink()


def test_config_and_allowlist_records_require_exact_json_values(profile_tree):
    binding = _binding(profile_tree)

    with pytest.raises(ReceiptError, match="config"):
        InstallReceipt.create(
            binding=binding,
            source_version=SOURCE_VERSION,
            source_commit=SOURCE_COMMIT,
            managed_targets=[],
            config_records=[{"bad": {1, 2}}],
            allowlist_records=[],
            created_at=FIRST_TIME,
            updated_at=FIRST_TIME,
        )
    with pytest.raises(ReceiptError, match="allowlist"):
        InstallReceipt.create(
            binding=binding,
            source_version=SOURCE_VERSION,
            source_commit=SOURCE_COMMIT,
            managed_targets=[],
            config_records=[],
            allowlist_records=[{"bad": float("nan")}],
            created_at=FIRST_TIME,
            updated_at=FIRST_TIME,
        )


@pytest.mark.parametrize(
    "config_record",
    [
        "not-an-object",
        {
            "event": "pre_tool_call",
            "command": "hook.sh",
            "matcher": "write_file|patch",
        },
        {
            "event": "pre_tool_call",
            "command": "hook.sh",
            "matcher": "write_file|patch",
            "fail_closed": True,
            "unexpected": "value",
        },
        {
            "event": "unknown_event",
            "command": "hook.sh",
            "matcher": "write_file|patch",
            "fail_closed": True,
        },
        {
            "event": "pre_tool_call",
            "command": "hook.sh",
            "matcher": "arbitrary-tool",
            "fail_closed": True,
        },
        {
            "event": "pre_tool_call",
            "command": "hook.sh",
            "matcher": "write_file|patch",
            "fail_closed": 1,
        },
        {
            "event": "pre_tool_call",
            "command": "hook.sh",
            "matcher": "write_file|patch",
            "fail_closed": False,
        },
        {
            "event": "post_tool_call",
            "command": "hook.sh",
            "matcher": "write_file|patch",
            "fail_closed": True,
        },
    ],
)
def test_config_records_reject_unknown_or_untyped_nested_values(
    profile_tree, config_record
):
    binding = _binding(profile_tree)

    with pytest.raises(ReceiptError, match="config"):
        InstallReceipt.create(
            binding=binding,
            source_version=SOURCE_VERSION,
            source_commit=SOURCE_COMMIT,
            managed_targets=[],
            config_records=[config_record],
            allowlist_records=[],
            created_at=FIRST_TIME,
            updated_at=FIRST_TIME,
        )


@pytest.mark.parametrize(
    "allowlist_record",
    [
        "not-an-object",
        {"event": "pre_tool_call"},
        {
            "event": "pre_tool_call",
            "command": "hook.sh",
            "unexpected": "value",
        },
        {"event": "unknown_event", "command": "hook.sh"},
        {"event": "pre_tool_call", "command": 1},
    ],
)
def test_allowlist_records_reject_unknown_or_untyped_nested_values(
    profile_tree, allowlist_record
):
    binding = _binding(profile_tree)

    with pytest.raises(ReceiptError, match="allowlist"):
        InstallReceipt.create(
            binding=binding,
            source_version=SOURCE_VERSION,
            source_commit=SOURCE_COMMIT,
            managed_targets=[],
            config_records=[],
            allowlist_records=[allowlist_record],
            created_at=FIRST_TIME,
            updated_at=FIRST_TIME,
        )


def test_failed_atomic_receipt_replace_preserves_the_previous_valid_bytes(
    profile_tree, monkeypatch
):
    binding = _binding(profile_tree)
    write_install_receipt(binding, _receipt(binding, version="1.3.17"))
    before = binding.receipt_path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("injected replace failure")

    monkeypatch.setattr(receipts_module.os, "replace", fail_replace)
    with pytest.raises(ReceiptError, match="atomic replace"):
        write_install_receipt(binding, _receipt(binding, version="1.3.18"))

    assert binding.receipt_path.read_bytes() == before
    assert not list(binding.receipt_path.parent.glob(".*.tmp"))


@pytest.mark.parametrize("existing_kind", ["corrupt", "cross-profile"])
def test_receipt_overwrite_rejects_invalid_existing_authority_before_writes(
    profile_tree, existing_kind
):
    alpha = _binding(profile_tree, "alpha")
    if existing_kind == "corrupt":
        _write(alpha.receipt_path, b"{")
    else:
        beta = _binding(profile_tree, "beta")
        _write_raw(alpha.receipt_path, _receipt(beta).to_mapping())
    before = alpha.receipt_path.read_bytes()

    with pytest.raises(ReceiptError):
        write_install_receipt(alpha, _receipt(alpha, version="1.3.19"))

    assert alpha.receipt_path.read_bytes() == before
    assert not list(alpha.receipt_path.parent.glob(".*.tmp"))


def test_receipt_writer_rejects_state_symlink_without_touching_its_target(profile_tree):
    binding = _binding(profile_tree)
    outside = profile_tree["root"] / "outside-state"
    outside.mkdir()
    try:
        binding.state_root.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip("directory symlinks unavailable: %s" % exc)

    try:
        with pytest.raises(ReceiptError, match="canonical|link|reparse|escape"):
            write_install_receipt(binding, _receipt(binding))
        assert list(outside.iterdir()) == []
    finally:
        binding.state_root.unlink()


def test_begin_journal_persists_exact_incomplete_rollback_and_plan_records(profile_tree):
    binding = _binding(profile_tree)
    journal = begin_run_journal(**_journal_kwargs(binding))
    mapping = journal.to_mapping()

    assert journal.status == "incomplete"
    assert journal.is_complete is False
    assert mapping["schema"] == RUN_JOURNAL_SCHEMA
    assert mapping["schema_version"] == 1
    assert mapping["operation_id"] == "update-20260810-001"
    assert mapping["operation"] == "update"
    assert mapping["status"] == "incomplete"
    assert mapping["binding"] == binding.to_mapping()
    assert mapping["source"] == {
        "version": SOURCE_VERSION,
        "commit": SOURCE_COMMIT,
    }
    assert mapping["previous"] == {
        "managed_targets": [item.to_mapping() for item in _receipt(binding).managed_targets],
        "config_records": _config_records(),
        "allowlist_records": _allowlist_records(),
    }
    assert mapping["plan"]["writes"] == [
        item.to_mapping() for item in sorted(_managed_targets(binding))
    ]
    assert mapping["plan"]["removals"] == [
        {
            "owner": "profile",
            "path": "hooks/sage-obsolete.sh",
        }
    ]
    assert mapping["result"] is None
    assert mapping["timestamps"] == {
        "started_at": FIRST_TIME,
        "completed_at": None,
    }
    assert binding.run_journal_path(journal.operation_id).is_file()
    assert load_run_journal(binding, journal.operation_id) == journal


def test_incomplete_journal_requires_an_explicit_completion_transition(profile_tree):
    binding = _binding(profile_tree)
    incomplete = begin_run_journal(**_journal_kwargs(binding))

    with pytest.raises(ReceiptError, match="incomplete"):
        incomplete.require_complete()
    with pytest.raises(ReceiptError, match="incomplete"):
        load_completed_run_journal(binding, incomplete.operation_id)

    complete = complete_run_journal(
        binding=binding,
        operation_id=incomplete.operation_id,
        result={
            "receipt_semantic_hash": _receipt(binding).semantic_hash,
            "restart_verified": True,
        },
        completed_at=SECOND_TIME,
    )

    assert complete.status == "complete"
    assert complete.is_complete is True
    assert complete.require_complete() is complete
    assert load_completed_run_journal(binding, complete.operation_id) == complete
    with pytest.raises(ReceiptError, match="already complete"):
        complete_run_journal(
            binding=binding,
            operation_id=complete.operation_id,
            result={"receipt_semantic_hash": _receipt(binding).semantic_hash},
            completed_at=SECOND_TIME,
        )


def test_journal_semantic_hash_excludes_timestamps(profile_tree):
    binding = _binding(profile_tree)
    first = RunJournal.create_incomplete(**_journal_kwargs(binding))
    later_kwargs = _journal_kwargs(binding)
    later_kwargs["started_at"] = SECOND_TIME
    second = RunJournal.create_incomplete(**later_kwargs)

    assert first.semantic_hash == second.semantic_hash


def test_concurrent_same_id_begin_has_exactly_one_winner(
    profile_tree, monkeypatch
):
    binding = _binding(profile_tree)
    journal_path = binding.run_journal_path("update-20260810-001")
    _race_replace_at(monkeypatch, journal_path)
    start = threading.Barrier(2)

    def begin_once(version):
        start.wait()
        kwargs = _journal_kwargs(binding)
        kwargs["source_version"] = version
        try:
            return ("winner", begin_run_journal(**kwargs))
        except ReceiptError as exc:
            return ("rejected", str(exc))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(begin_once, ("1.3.18", "1.3.19")))

    assert [kind for kind, _ in results].count("winner") == 1
    assert [kind for kind, _ in results].count("rejected") == 1
    assert load_run_journal(binding, "update-20260810-001").status == "incomplete"
    assert _lock_path(journal_path).is_file()
    assert _lock_path(journal_path).stat().st_size >= 1


def test_concurrent_same_id_completion_has_exactly_one_winner(
    profile_tree, monkeypatch
):
    binding = _binding(profile_tree)
    incomplete = begin_run_journal(**_journal_kwargs(binding))
    original_load = receipts_module.load_run_journal
    loaded = threading.Barrier(2)

    def racing_load(selected_binding, operation_id):
        journal = original_load(selected_binding, operation_id)
        try:
            loaded.wait(timeout=1.0)
        except threading.BrokenBarrierError:
            pass
        return journal

    monkeypatch.setattr(receipts_module, "load_run_journal", racing_load)
    start = threading.Barrier(2)

    def complete_once(marker):
        start.wait()
        try:
            return (
                "winner",
                complete_run_journal(
                    binding=binding,
                    operation_id=incomplete.operation_id,
                    result={"winner": marker},
                    completed_at=SECOND_TIME,
                ),
            )
        except ReceiptError as exc:
            return ("rejected", str(exc))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(complete_once, ("alpha", "beta")))

    assert [kind for kind, _ in results].count("winner") == 1
    assert [kind for kind, _ in results].count("rejected") == 1
    assert load_completed_run_journal(binding, incomplete.operation_id).is_complete
    journal_path = binding.run_journal_path(incomplete.operation_id)
    assert _lock_path(journal_path).is_file()
    assert _lock_path(journal_path).stat().st_size >= 1


def test_hard_exit_holder_releases_persistent_os_lock_for_retry(profile_tree):
    binding = _binding(profile_tree)
    operation_id = "hard-exit-retry-001"
    document_path = binding.run_journal_path(operation_id)
    script = "\n".join(
        (
            "import os, pathlib, sys",
            "sys.path.insert(0, sys.argv[1])",
            "import receipts",
            "from profile_binding import ProfileBinding",
            "binding = ProfileBinding.from_explicit(",
            "    collection_root=sys.argv[2],",
            "    profile_id=sys.argv[3],",
            "    profile_root=sys.argv[4],",
            "    workspace_root=sys.argv[5],",
            ")",
            "path = pathlib.Path(sys.argv[6])",
            "with receipts._exclusive_document_lock(binding, path, 'run journal'):",
            "    print('LOCKED', flush=True)",
            "    os._exit(23)",
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            os.fspath(SETUP_ROOT),
            os.fspath(binding.collection_root),
            binding.profile_id,
            os.fspath(binding.profile_root),
            os.fspath(binding.workspace_root),
            os.fspath(document_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert result.returncode == 23, result.stderr
    assert result.stdout.strip() == "LOCKED"
    assert _lock_path(document_path).is_file()
    kwargs = _journal_kwargs(binding)
    kwargs["operation_id"] = operation_id
    assert begin_run_journal(**kwargs).status == "incomplete"


def test_persistent_lock_identity_prevents_aba_and_successor_release(profile_tree):
    binding = _binding(profile_tree)
    document_path = binding.run_journal_path("persistent-identity-001")
    lock_path = _lock_path(document_path)

    first = receipts_module._exclusive_document_lock(
        binding, document_path, "run journal"
    )
    with first:
        first_identity = (lock_path.stat().st_dev, lock_path.stat().st_ino)

    assert lock_path.is_file()
    assert (lock_path.stat().st_dev, lock_path.stat().st_ino) == first_identity

    with receipts_module._exclusive_document_lock(
        binding, document_path, "run journal"
    ):
        successor_identity = (lock_path.stat().st_dev, lock_path.stat().st_ino)
        assert successor_identity == first_identity
        with pytest.raises(ReceiptError, match="another operation"):
            with receipts_module._exclusive_document_lock(
                binding, document_path, "run journal"
            ):
                pytest.fail("a prior/third owner released the successor lock")

    assert lock_path.is_file()
    assert (lock_path.stat().st_dev, lock_path.stat().st_ino) == first_identity


def test_persistent_lock_is_exact_home_and_rejects_link_escape(profile_tree):
    binding = _binding(profile_tree)
    write_install_receipt(binding, _receipt(binding))
    receipt_lock = _lock_path(binding.receipt_path)
    assert receipt_lock == binding.receipt_path.parent / ".install.json.lock"
    assert receipt_lock.is_file()

    operation_id = "lock-link-escape-001"
    journal_path = binding.run_journal_path(operation_id)
    journal_lock = _lock_path(journal_path)
    journal_lock.parent.mkdir(parents=True, exist_ok=True)
    outside = profile_tree["root"] / "outside-lock"
    outside.write_bytes(b"outside\n")
    try:
        journal_lock.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        pytest.skip("file symlinks unavailable: %s" % exc)

    try:
        kwargs = _journal_kwargs(binding)
        kwargs["operation_id"] = operation_id
        with pytest.raises(ReceiptError, match="lock|link|reparse|outside"):
            begin_run_journal(**kwargs)
        assert outside.read_bytes() == b"outside\n"
    finally:
        journal_lock.unlink()


def test_persistent_lock_rejects_hardlink_escape_before_writing(profile_tree):
    binding = _binding(profile_tree)
    operation_id = "lock-hardlink-escape-001"
    journal_path = binding.run_journal_path(operation_id)
    journal_lock = _lock_path(journal_path)
    journal_lock.parent.mkdir(parents=True, exist_ok=True)
    outside = profile_tree["root"] / "outside-hardlink"
    outside.write_bytes(b"")
    try:
        os.link(os.fspath(outside), os.fspath(journal_lock))
    except OSError as exc:
        pytest.skip("hardlinks unavailable: %s" % exc)

    try:
        kwargs = _journal_kwargs(binding)
        kwargs["operation_id"] = operation_id
        with pytest.raises(ReceiptError, match="lock|link|outside"):
            begin_run_journal(**kwargs)
        assert outside.read_bytes() == b""
    finally:
        journal_lock.unlink()


def test_hundred_round_eight_worker_begin_and_completion_have_one_winner(
    profile_tree,
):
    binding = _binding(profile_tree)
    base = _journal_kwargs(binding)

    for round_index in range(100):
        operation_id = "stress-begin-%03d" % round_index

        def begin_worker(worker_index):
            kwargs = dict(base)
            kwargs["operation_id"] = operation_id
            kwargs["source_version"] = "1.3.18-%d" % worker_index
            try:
                begin_run_journal(**kwargs)
                return "winner"
            except ReceiptError:
                return "rejected"

        outcomes = _parallel_outcomes(begin_worker)
        assert outcomes.count("winner") == 1, (round_index, outcomes)
        assert outcomes.count("rejected") == 7, (round_index, outcomes)

    for round_index in range(100):
        operation_id = "stress-complete-%03d" % round_index
        kwargs = dict(base)
        kwargs["operation_id"] = operation_id
        begin_run_journal(**kwargs)

        def complete_worker(worker_index):
            try:
                complete_run_journal(
                    binding=binding,
                    operation_id=operation_id,
                    result={"worker": worker_index},
                    completed_at=SECOND_TIME,
                )
                return "winner"
            except ReceiptError:
                return "rejected"

        outcomes = _parallel_outcomes(complete_worker)
        assert outcomes.count("winner") == 1, (round_index, outcomes)
        assert outcomes.count("rejected") == 7, (round_index, outcomes)


@pytest.mark.skipif(os.name != "nt", reason="Windows target identity proof")
def test_windows_case_variants_are_duplicate_managed_targets(profile_tree):
    binding = _binding(profile_tree)
    upper = ManagedTarget(
        owner="workspace",
        relative_path="sage/runtime/Case.py",
        sha256=_sha(b"upper"),
    )
    lower = ManagedTarget(
        owner="workspace",
        relative_path="sage/runtime/case.py",
        sha256=_sha(b"lower"),
    )

    with pytest.raises(ReceiptError, match="duplicate"):
        InstallReceipt.create(
            binding=binding,
            source_version=SOURCE_VERSION,
            source_commit=SOURCE_COMMIT,
            managed_targets=[upper, lower],
            config_records=[],
            allowlist_records=[],
            created_at=FIRST_TIME,
            updated_at=FIRST_TIME,
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows target identity proof")
def test_windows_case_variants_conflict_across_write_and_removal(profile_tree):
    binding = _binding(profile_tree)
    kwargs = _journal_kwargs(binding)
    kwargs["planned_writes"] = [
        ManagedTarget(
            owner="workspace",
            relative_path="sage/runtime/Case.py",
            sha256=_sha(b"write"),
        )
    ]
    kwargs["planned_removals"] = [
        TargetRef(owner="workspace", relative_path="sage/runtime/case.py")
    ]

    with pytest.raises(ReceiptError, match="both a planned write and removal"):
        RunJournal.create_incomplete(**kwargs)


@pytest.mark.skipif(os.name == "nt", reason="case-sensitive portable behavior")
def test_posix_case_variants_remain_distinct_managed_targets(profile_tree):
    binding = _binding(profile_tree)
    receipt = InstallReceipt.create(
        binding=binding,
        source_version=SOURCE_VERSION,
        source_commit=SOURCE_COMMIT,
        managed_targets=[
            ManagedTarget(
                owner="workspace",
                relative_path="sage/runtime/Case.py",
                sha256=_sha(b"upper"),
            ),
            ManagedTarget(
                owner="workspace",
                relative_path="sage/runtime/case.py",
                sha256=_sha(b"lower"),
            ),
        ],
        config_records=[],
        allowlist_records=[],
        created_at=FIRST_TIME,
        updated_at=FIRST_TIME,
    )

    assert len(receipt.managed_targets) == 2


@pytest.mark.parametrize("operation", ["install", "update", "remove"])
def test_all_documented_operations_are_accepted(profile_tree, operation):
    binding = _binding(profile_tree)
    kwargs = _journal_kwargs(binding)
    kwargs["operation"] = operation
    kwargs["operation_id"] = operation + "-001"

    journal = RunJournal.create_incomplete(**kwargs)

    assert journal.operation == operation


@pytest.mark.parametrize("operation", ["", "upgrade", "rollback", "INSTALL"])
def test_undocumented_operations_are_rejected(profile_tree, operation):
    binding = _binding(profile_tree)
    kwargs = _journal_kwargs(binding)
    kwargs["operation"] = operation

    with pytest.raises(ReceiptError, match="operation"):
        RunJournal.create_incomplete(**kwargs)


@pytest.mark.parametrize("schema_version", [True, 1.0, "1", 2])
def test_run_journal_schema_version_requires_exact_integer_one(
    profile_tree, schema_version
):
    binding = _binding(profile_tree)
    journal = RunJournal.create_incomplete(**_journal_kwargs(binding))
    mapping = journal.to_mapping()
    mapping["schema_version"] = schema_version
    _write_raw(binding.run_journal_path(journal.operation_id), mapping)

    with pytest.raises(ReceiptError, match="schema version"):
        load_run_journal(binding, journal.operation_id)


def test_existing_journal_is_never_overwritten_by_a_second_begin(profile_tree):
    binding = _binding(profile_tree)
    first = begin_run_journal(**_journal_kwargs(binding))
    before = binding.run_journal_path(first.operation_id).read_bytes()

    with pytest.raises(ReceiptError, match="already exists"):
        begin_run_journal(**_journal_kwargs(binding))

    assert binding.run_journal_path(first.operation_id).read_bytes() == before


def test_cross_profile_and_corrupt_journals_fail_closed(profile_tree):
    alpha = _binding(profile_tree, "alpha")
    beta = _binding(profile_tree, "beta")
    beta_journal = RunJournal.create_incomplete(**_journal_kwargs(beta))
    alpha_path = alpha.run_journal_path(beta_journal.operation_id)
    _write_raw(alpha_path, beta_journal.to_mapping())

    with pytest.raises(ReceiptError, match="binding|profile"):
        load_run_journal(alpha, beta_journal.operation_id)

    alpha_path.write_text("{", encoding="utf-8")
    with pytest.raises(ReceiptError, match="valid strict JSON"):
        load_run_journal(alpha, beta_journal.operation_id)


def test_failed_atomic_completion_leaves_a_recoverable_incomplete_journal(
    profile_tree, monkeypatch
):
    binding = _binding(profile_tree)
    incomplete = begin_run_journal(**_journal_kwargs(binding))
    path = binding.run_journal_path(incomplete.operation_id)
    before = path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("injected replace failure")

    monkeypatch.setattr(receipts_module.os, "replace", fail_replace)
    with pytest.raises(ReceiptError, match="atomic replace"):
        complete_run_journal(
            binding=binding,
            operation_id=incomplete.operation_id,
            result={"receipt_semantic_hash": _receipt(binding).semantic_hash},
            completed_at=SECOND_TIME,
        )

    assert path.read_bytes() == before
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "incomplete"
    assert not list(path.parent.glob(".*.tmp"))


def test_journal_writer_rejects_runs_symlink_without_touching_target(profile_tree):
    binding = _binding(profile_tree)
    binding.runs_root.parent.mkdir(parents=True)
    outside = profile_tree["root"] / "outside-runs"
    outside.mkdir()
    try:
        binding.runs_root.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip("directory symlinks unavailable: %s" % exc)

    try:
        with pytest.raises(ReceiptError, match="canonical|link|reparse|escape"):
            begin_run_journal(**_journal_kwargs(binding))
        assert list(outside.iterdir()) == []
    finally:
        binding.runs_root.unlink()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction proof")
def test_windows_receipt_root_junction_is_rejected_before_write(profile_tree):
    binding = _binding(profile_tree)
    outside = profile_tree["root"] / "junction-target"
    outside.mkdir()
    result = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            os.fspath(binding.state_root),
            os.fspath(outside),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("junction creation unavailable: " + result.stderr.strip())

    try:
        with pytest.raises(ReceiptError, match="canonical|link|reparse|escape"):
            write_install_receipt(binding, _receipt(binding))
        assert list(outside.iterdir()) == []
    finally:
        os.rmdir(os.fspath(binding.state_root))


def test_profile_transaction_lock_is_reentrant_and_excludes_other_threads(
    profile_tree,
):
    binding = _binding(profile_tree)
    assert hasattr(receipts_module, "profile_transaction_lock")

    def contend():
        with receipts_module.profile_transaction_lock(binding):
            return True

    with receipts_module.profile_transaction_lock(binding):
        with receipts_module.profile_transaction_lock(binding):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(contend)
                with pytest.raises(ReceiptError, match="profile operation|already being changed"):
                    future.result(timeout=5)

    assert contend() is True
