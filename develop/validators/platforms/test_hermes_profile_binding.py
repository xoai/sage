#!/usr/bin/env python3
"""Isolation tests for the immutable Hermes profile binding authority."""

from __future__ import annotations

import dataclasses
import os
import pathlib
import subprocess
import sys
import threading
from typing import Dict

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
sys.path.insert(0, str(SETUP_ROOT))

from profile_binding import BindingError, ProfileBinding  # noqa: E402


def _tree_snapshot(root: pathlib.Path) -> Dict[str, bytes]:
    snapshot = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("link:" + os.readlink(str(path))).encode()
        elif path.is_file():
            snapshot[relative] = path.read_bytes()
        else:
            snapshot[relative] = b"<directory>"
    return snapshot


def _is_within(root: pathlib.Path, target: pathlib.Path) -> bool:
    try:
        return os.path.commonpath(
            [os.path.normcase(str(root)), os.path.normcase(str(target))]
        ) == os.path.normcase(str(root))
    except ValueError:
        return False


def _windows_extended(path: pathlib.Path) -> str:
    return "\\\\?\\" + os.fspath(path)


def _runtime_authority_consumer(value):
    if not isinstance(value, ProfileBinding):
        raise BindingError("runtime consumer requires authorized ProfileBinding")
    return value.run_journal_path("runtime-consumer")


@pytest.fixture
def profile_tree(tmp_path):
    collection = tmp_path / "hermes"
    profile_a = collection / "profiles" / "alpha"
    profile_b = collection / "profiles" / "beta"
    workspace_a = profile_a / "workspace"
    workspace_b = profile_b / "workspace"
    global_state = tmp_path / ".sage"
    global_memory = tmp_path / ".sage-memory"

    for directory in (workspace_a, workspace_b, global_state, global_memory):
        directory.mkdir(parents=True)

    (profile_a / "SOUL.md").write_text("alpha", encoding="utf-8")
    (profile_b / "SOUL.md").write_text("beta", encoding="utf-8")
    (global_state / "sentinel").write_text("global-state", encoding="utf-8")
    (global_memory / "sentinel").write_text("global-memory", encoding="utf-8")
    (workspace_a / "a-sentinel").write_text("A", encoding="utf-8")
    (workspace_b / "b-sentinel").write_text("B", encoding="utf-8")

    return {
        "root": tmp_path,
        "collection": collection,
        "profile_a": profile_a,
        "profile_b": profile_b,
        "workspace_a": workspace_a,
        "workspace_b": workspace_b,
        "global_state": global_state,
        "global_memory": global_memory,
    }


def _binding(tree, profile="alpha"):
    suffix = "a" if profile == "alpha" else "b"
    return ProfileBinding.from_explicit(
        collection_root=tree["collection"],
        profile_id=profile,
        profile_root=tree["profile_" + suffix],
        workspace_root=tree["workspace_" + suffix],
    )


def test_direct_unvalidated_construction_is_rejected():
    with pytest.raises(BindingError, match="from_explicit"):
        ProfileBinding()


def test_no_unchecked_class_constructor_surface_can_bypass_validation(profile_tree):
    alpha = _binding(profile_tree, "alpha")
    values = alpha.to_mapping()
    values.pop("profile_id")
    values = {key: pathlib.Path(value) for key, value in values.items()}
    values["profile_id"] = "../beta"

    with pytest.raises(AttributeError):
        ProfileBinding._construct(**values)


def test_explicit_a_b_bindings_are_frozen_isolated_and_mutation_free(profile_tree):
    before = _tree_snapshot(profile_tree["root"])

    alpha = _binding(profile_tree, "alpha")
    beta = _binding(profile_tree, "beta")

    assert dataclasses.is_dataclass(alpha)
    with pytest.raises(dataclasses.FrozenInstanceError):
        alpha.profile_id = "beta"

    assert alpha.collection_root == profile_tree["collection"].resolve()
    assert alpha.profile_root == profile_tree["profile_a"].resolve()
    assert alpha.workspace_root == profile_tree["workspace_a"].resolve()
    assert alpha.config_path == alpha.profile_root / "config.yaml"
    assert alpha.hooks_root == alpha.profile_root / "hooks"
    assert alpha.plugin_root == alpha.profile_root / "plugins" / "sage"
    assert alpha.skills_root == alpha.profile_root / "skills"
    assert alpha.state_root == alpha.workspace_root / ".sage"
    assert alpha.memory_root == alpha.workspace_root / ".sage-memory"
    assert alpha.memory_db_path == alpha.memory_root / "memory.db"
    assert alpha.receipt_path == alpha.state_root / "receipts" / "install.json"
    assert alpha.runs_root == alpha.state_root / "receipts" / "runs"
    assert alpha.pack_lock_path == alpha.state_root / "packs.lock"

    alpha_paths = dataclasses.asdict(alpha).values()
    beta_paths = dataclasses.asdict(beta).values()
    for value in alpha_paths:
        if isinstance(value, pathlib.Path):
            assert _is_within(alpha.collection_root, value)
            assert not _is_within(beta.profile_root, value)
            assert not _is_within(profile_tree["global_state"], value)
            assert not _is_within(profile_tree["global_memory"], value)
    for value in beta_paths:
        if isinstance(value, pathlib.Path):
            assert _is_within(beta.collection_root, value)
            assert not _is_within(alpha.profile_root, value)
            assert not _is_within(profile_tree["global_state"], value)
            assert not _is_within(profile_tree["global_memory"], value)

    assert _tree_snapshot(profile_tree["root"]) == before


@pytest.mark.parametrize(
    "case",
    [
        "missing_collection",
        "relative_collection",
        "wrong_profile_root",
        "sibling_workspace",
        "global_workspace",
        "noncanonical_workspace",
        "profile_component_escape",
    ],
)
def test_missing_cross_profile_and_noncanonical_inputs_fail_before_writes(
    profile_tree, case
):
    before = _tree_snapshot(profile_tree["root"])
    kwargs = {
        "collection_root": profile_tree["collection"],
        "profile_id": "alpha",
        "profile_root": profile_tree["profile_a"],
        "workspace_root": profile_tree["workspace_a"],
    }

    if case == "missing_collection":
        kwargs["collection_root"] = None
    elif case == "relative_collection":
        kwargs["collection_root"] = pathlib.Path("hermes")
    elif case == "wrong_profile_root":
        kwargs["profile_root"] = profile_tree["profile_b"]
    elif case == "sibling_workspace":
        kwargs["workspace_root"] = profile_tree["workspace_b"]
    elif case == "global_workspace":
        kwargs["workspace_root"] = profile_tree["root"]
    elif case == "noncanonical_workspace":
        kwargs["workspace_root"] = (
            profile_tree["workspace_a"] / "child" / ".."
        )
    elif case == "profile_component_escape":
        kwargs["profile_id"] = "../beta"

    with pytest.raises(BindingError):
        ProfileBinding.from_explicit(**kwargs)

    assert _tree_snapshot(profile_tree["root"]) == before


@pytest.mark.parametrize("workspace_name", ["project", "workspace-backup"])
def test_workspace_must_be_the_exact_profile_workspace(profile_tree, workspace_name):
    alternate = profile_tree["profile_a"] / workspace_name
    alternate.mkdir()

    with pytest.raises(BindingError, match="exactly profile_root/workspace"):
        ProfileBinding.from_explicit(
            collection_root=profile_tree["collection"],
            profile_id="alpha",
            profile_root=profile_tree["profile_a"],
            workspace_root=alternate,
        )


def test_nested_project_workspace_is_not_a_profile_workspace(profile_tree):
    project = profile_tree["workspace_a"] / "project"
    project.mkdir()

    with pytest.raises(BindingError, match="exactly profile_root/workspace"):
        ProfileBinding.from_explicit(
            collection_root=profile_tree["collection"],
            profile_id="alpha",
            profile_root=profile_tree["profile_a"],
            workspace_root=project,
        )


@pytest.mark.parametrize(
    "profile_id",
    [
        "Alpha",
        "ALPHA",
        "-alpha",
        "_alpha",
        "alpha.beta",
        "alpha beta",
        "alphá",
        "a" * 65,
    ],
)
def test_profile_id_must_match_the_cli_contract(profile_tree, profile_id):
    with pytest.raises(BindingError, match="CLI profile contract"):
        ProfileBinding.from_explicit(
            collection_root=profile_tree["collection"],
            profile_id=profile_id,
            profile_root=profile_tree["profile_a"],
            workspace_root=profile_tree["workspace_a"],
        )


@pytest.mark.parametrize("profile_id", ["a", "alpha", "rei-stewart", "rei_1", "a" * 64])
def test_profile_id_accepts_the_full_cli_contract(profile_tree, profile_id):
    profile = profile_tree["collection"] / "profiles" / profile_id
    workspace = profile / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    binding = ProfileBinding.from_explicit(
        collection_root=profile_tree["collection"],
        profile_id=profile_id,
        profile_root=profile,
        workspace_root=workspace,
    )

    assert binding.profile_id == profile_id


@pytest.mark.skipif(os.name != "nt", reason="Windows path-case canonicalization")
def test_case_variant_explicit_paths_are_not_canonical(profile_tree):
    with pytest.raises(BindingError, match="canonical"):
        ProfileBinding.from_explicit(
            collection_root=str(profile_tree["collection"]).upper(),
            profile_id="alpha",
            profile_root=profile_tree["profile_a"],
            workspace_root=profile_tree["workspace_a"],
        )


@pytest.mark.parametrize(
    "field,case_variant",
    [
        ("state_root", lambda binding: binding.workspace_root / ".SAGE"),
        ("memory_root", lambda binding: binding.workspace_root / ".SAGE-MEMORY"),
        (
            "receipt_path",
            lambda binding: binding.workspace_root
            / ".SAGE"
            / "RECEIPTS"
            / "INSTALL.JSON",
        ),
    ],
)
def test_absent_derived_home_case_mismatch_cannot_pair_receipt_and_config(
    profile_tree, field, case_variant
):
    alpha = _binding(profile_tree, "alpha")
    config = alpha.to_config_mapping()
    config[field] = os.fspath(case_variant(alpha))

    with pytest.raises(BindingError, match="receipt and config|canonical|match"):
        ProfileBinding.from_authorities(
            receipt={"binding": alpha.to_mapping()},
            config_binding=config,
            collection_root=alpha.collection_root,
            profile_root=alpha.profile_root,
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace aliases")
def test_windows_extended_namespace_cannot_become_binding_authority(profile_tree):
    with pytest.raises(BindingError, match="namespace|canonical"):
        ProfileBinding.from_explicit(
            collection_root=_windows_extended(profile_tree["collection"]),
            profile_id="alpha",
            profile_root=_windows_extended(profile_tree["profile_a"]),
            workspace_root=_windows_extended(profile_tree["workspace_a"]),
        )


def test_prefix_sibling_is_not_inside_the_selected_profile(profile_tree):
    prefix_sibling = profile_tree["collection"] / "profiles" / "alpha-backup"
    sibling_workspace = prefix_sibling / "workspace"
    sibling_workspace.mkdir(parents=True)

    with pytest.raises(BindingError):
        ProfileBinding.from_explicit(
            collection_root=profile_tree["collection"],
            profile_id="alpha",
            profile_root=profile_tree["profile_a"],
            workspace_root=sibling_workspace,
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows cross-drive boundary")
def test_cross_drive_profile_root_is_rejected(profile_tree):
    other_drive = "Z:" if profile_tree["collection"].drive.upper() != "Z:" else "Y:"
    with pytest.raises(BindingError):
        ProfileBinding.from_explicit(
            collection_root=profile_tree["collection"],
            profile_id="alpha",
            profile_root=pathlib.Path(other_drive + "\\profiles\\alpha"),
            workspace_root=profile_tree["workspace_a"],
        )


def test_receipt_config_and_full_mapping_must_match_exactly(profile_tree):
    alpha = _binding(profile_tree, "alpha")
    beta = _binding(profile_tree, "beta")
    mapping = alpha.to_mapping()

    assert ProfileBinding.from_mapping(mapping) == alpha
    assert ProfileBinding.from_receipt({"binding": mapping}) == alpha
    assert (
        ProfileBinding.from_config_mapping(
            alpha.to_config_mapping(),
            collection_root=alpha.collection_root,
            profile_root=alpha.profile_root,
        )
        == alpha
    )
    assert alpha.assert_same(mapping) is alpha
    assert alpha.assert_same({"binding": mapping}) is alpha

    with pytest.raises(BindingError, match="different Hermes profile binding"):
        alpha.assert_same(beta)

    for key in mapping:
        missing = dict(mapping)
        missing.pop(key)
        with pytest.raises(BindingError, match="missing"):
            ProfileBinding.from_mapping(missing)

    mismatches = {
        "collection_root": profile_tree["root"],
        "profile_id": "beta",
        "profile_root": beta.profile_root,
        "workspace_root": beta.workspace_root,
        "state_root": profile_tree["global_state"],
        "memory_root": profile_tree["global_memory"],
        "receipt_path": beta.receipt_path,
        "runs_root": beta.runs_root,
        "pack_lock_path": beta.pack_lock_path,
    }
    for key, value in mismatches.items():
        changed = dict(mapping)
        changed[key] = str(value)
        with pytest.raises(BindingError):
            ProfileBinding.from_mapping(changed)

    noncanonical = dict(mapping)
    noncanonical["workspace_root"] = str(
        alpha.workspace_root / "child" / ".."
    )
    with pytest.raises(BindingError, match="canonical"):
        ProfileBinding.from_mapping(noncanonical)

    incomplete_config = alpha.to_config_mapping()
    incomplete_config.pop("memory_root")
    with pytest.raises(BindingError, match="missing"):
        alpha.assert_same(incomplete_config)


def test_runtime_authority_requires_matching_receipt_and_config(profile_tree):
    alpha = _binding(profile_tree, "alpha")

    authorized = ProfileBinding.from_authorities(
        receipt={"binding": alpha.to_mapping()},
        config_binding=alpha.to_config_mapping(),
        collection_root=alpha.collection_root,
        profile_root=alpha.profile_root,
    )

    assert authorized == alpha


@pytest.mark.parametrize("missing_authority", ["receipt", "config_binding"])
def test_runtime_authority_fails_when_receipt_or_config_is_missing(
    profile_tree, missing_authority
):
    alpha = _binding(profile_tree, "alpha")
    kwargs = {
        "receipt": {"binding": alpha.to_mapping()},
        "config_binding": alpha.to_config_mapping(),
        "collection_root": alpha.collection_root,
        "profile_root": alpha.profile_root,
    }
    kwargs[missing_authority] = None

    with pytest.raises(BindingError):
        ProfileBinding.from_authorities(**kwargs)


def test_runtime_authority_rejects_receipt_config_profile_mismatch(profile_tree):
    alpha = _binding(profile_tree, "alpha")
    beta = _binding(profile_tree, "beta")

    with pytest.raises(BindingError, match="receipt and config"):
        ProfileBinding.from_authorities(
            receipt={"binding": alpha.to_mapping()},
            config_binding=beta.to_config_mapping(),
            collection_root=alpha.collection_root,
            profile_root=alpha.profile_root,
        )


@pytest.mark.parametrize("parser", ["mapping", "receipt", "config"])
def test_parser_results_cannot_enter_runtime_authority_consumers(
    profile_tree, parser
):
    alpha = _binding(profile_tree, "alpha")
    if parser == "mapping":
        parsed = ProfileBinding.from_mapping(alpha.to_mapping())
    elif parser == "receipt":
        parsed = ProfileBinding.from_receipt({"binding": alpha.to_mapping()})
    else:
        parsed = ProfileBinding.from_config_mapping(
            alpha.to_config_mapping(),
            collection_root=alpha.collection_root,
            profile_root=alpha.profile_root,
        )

    assert not isinstance(parsed, ProfileBinding)
    with pytest.raises(BindingError, match="authorized|authority"):
        _runtime_authority_consumer(parsed)


def test_untrusted_parser_results_cannot_self_authorize(profile_tree):
    alpha = _binding(profile_tree, "alpha")
    parsed_receipt = ProfileBinding.from_receipt(
        {"binding": alpha.to_mapping()}
    )
    parsed_config = ProfileBinding.from_config_mapping(
        alpha.to_config_mapping(),
        collection_root=alpha.collection_root,
        profile_root=alpha.profile_root,
    )

    with pytest.raises(BindingError, match="authorized|authority"):
        parsed_receipt.assert_same(alpha)
    with pytest.raises(BindingError):
        ProfileBinding.from_authorities(
            receipt=parsed_receipt,
            config_binding=parsed_config,
            collection_root=alpha.collection_root,
            profile_root=alpha.profile_root,
        )


def test_home_cwd_and_ancestor_state_are_never_fallbacks(
    profile_tree, monkeypatch
):
    monkeypatch.setenv("HOME", str(profile_tree["root"]))
    monkeypatch.setenv("HERMES_HOME", str(profile_tree["profile_b"]))
    monkeypatch.chdir(profile_tree["global_state"])

    with pytest.raises(BindingError):
        ProfileBinding.from_explicit(
            collection_root=None,
            profile_id="alpha",
            profile_root=profile_tree["profile_a"],
            workspace_root=profile_tree["workspace_a"],
        )
    with pytest.raises(BindingError):
        ProfileBinding.from_mapping(
            {
                "profile_id": "alpha",
                "workspace_root": str(profile_tree["workspace_a"]),
            }
        )


def test_symlink_escapes_for_workspace_state_memory_and_hooks_fail_closed(
    profile_tree,
):
    outside = profile_tree["root"] / "outside"
    outside.mkdir()

    link_workspace = profile_tree["profile_a"] / "linked-workspace"
    try:
        link_workspace.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip("directory symlinks unavailable in this test host: %s" % exc)

    with pytest.raises(BindingError):
        ProfileBinding.from_explicit(
            collection_root=profile_tree["collection"],
            profile_id="alpha",
            profile_root=profile_tree["profile_a"],
            workspace_root=link_workspace,
        )

    link_workspace.unlink()
    for relative in (".sage", ".sage-memory"):
        link = profile_tree["workspace_a"] / relative
        link.symlink_to(outside, target_is_directory=True)
        try:
            with pytest.raises(BindingError):
                _binding(profile_tree, "alpha")
        finally:
            link.unlink()

    hooks = profile_tree["profile_a"] / "hooks"
    hooks.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(BindingError):
            _binding(profile_tree, "alpha")
    finally:
        hooks.unlink()


def test_profile_identity_symlink_cannot_alias_alpha_to_beta(profile_tree):
    alias_collection = profile_tree["root"] / "alias-hermes"
    beta = alias_collection / "profiles" / "beta"
    workspace = beta / "workspace"
    workspace.mkdir(parents=True)
    alpha = alias_collection / "profiles" / "alpha"
    try:
        alpha.symlink_to(beta, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip("directory symlinks unavailable in this test host: %s" % exc)

    with pytest.raises(BindingError, match="alias|canonical|exact"):
        ProfileBinding.from_explicit(
            collection_root=alias_collection,
            profile_id="alpha",
            profile_root=beta,
            workspace_root=workspace,
        )


@pytest.mark.parametrize(
    "relative,alternate",
    [
        (".sage", "alternate-state"),
        (".sage-memory", "alternate-memory"),
        ("hooks", "alternate-hooks"),
        ("skills", "alternate-skills"),
    ],
)
def test_internal_symlink_aliases_for_exact_homes_are_rejected(
    profile_tree, relative, alternate
):
    owner = (
        profile_tree["workspace_a"]
        if relative.startswith(".")
        else profile_tree["profile_a"]
    )
    alternate_path = owner / alternate
    alternate_path.mkdir()
    alias = owner / relative
    try:
        alias.symlink_to(alternate_path, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip("directory symlinks unavailable in this test host: %s" % exc)

    try:
        with pytest.raises(BindingError, match="alias|canonical|exact"):
            _binding(profile_tree, "alpha")
    finally:
        alias.unlink()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction proof")
def test_windows_profile_junction_cannot_alias_alpha_to_beta(profile_tree):
    collection = profile_tree["root"] / "junction-hermes"
    beta = collection / "profiles" / "beta"
    workspace = beta / "workspace"
    workspace.mkdir(parents=True)
    alpha = collection / "profiles" / "alpha"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(alpha), str(beta)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("junction creation unavailable: " + result.stderr.strip())

    try:
        with pytest.raises(BindingError, match="alias|canonical|exact"):
            ProfileBinding.from_explicit(
                collection_root=collection,
                profile_id="alpha",
                profile_root=beta,
                workspace_root=workspace,
            )
    finally:
        os.rmdir(str(alpha))


@pytest.mark.skipif(os.name != "nt", reason="Windows junction proof")
def test_windows_internal_state_junction_alias_is_rejected(profile_tree):
    alternate = profile_tree["workspace_a"] / "alternate-state"
    alternate.mkdir()
    state = profile_tree["workspace_a"] / ".sage"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(state), str(alternate)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("junction creation unavailable: " + result.stderr.strip())

    try:
        with pytest.raises(BindingError, match="alias|canonical|exact"):
            _binding(profile_tree, "alpha")
    finally:
        os.rmdir(str(state))


@pytest.mark.parametrize(
    "target_name,target_path",
    [
        ("config_path", lambda binding: binding.profile_root / "config.yaml"),
        (
            "memory_db_path",
            lambda binding: binding.workspace_root / ".sage-memory" / "memory.db",
        ),
        (
            "receipt_path",
            lambda binding: binding.workspace_root
            / ".sage"
            / "receipts"
            / "install.json",
        ),
        (
            "pack_lock_path",
            lambda binding: binding.workspace_root / ".sage" / "packs.lock",
        ),
    ],
)
def test_existing_derived_file_hardlinks_are_rejected(
    profile_tree, target_name, target_path
):
    initial = _binding(profile_tree, "alpha")
    target = target_path(initial)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"owned")
    alias = profile_tree["root"] / (target_name + "-alias")
    os.link(str(target), str(alias))

    with pytest.raises(BindingError, match="hardlink|link count"):
        _binding(profile_tree, "alpha")


def test_existing_run_journal_hardlink_is_rejected(profile_tree):
    alpha = _binding(profile_tree, "alpha")
    journal = alpha.runs_root / "update-001.json"
    journal.parent.mkdir(parents=True)
    journal.write_bytes(b"journal")
    alias = profile_tree["root"] / "journal-alias.json"
    os.link(str(journal), str(alias))

    with pytest.raises(BindingError, match="hardlink|link count"):
        alpha.run_journal_path("update-001")


@pytest.mark.skipif(os.name != "nt", reason="Windows resolver race proof")
def test_transient_windows_extended_resolver_result_is_normalized(
    profile_tree, monkeypatch
):
    state = profile_tree["workspace_a"] / ".sage"
    original_resolve = pathlib.Path.resolve

    def racing_resolve(path, strict=False):
        resolved = original_resolve(path, strict=strict)
        if path == state and not strict:
            return pathlib.Path(_windows_extended(resolved))
        return resolved

    monkeypatch.setattr(pathlib.Path, "resolve", racing_resolve)

    alpha = _binding(profile_tree, "alpha")

    assert alpha.state_root == state


@pytest.mark.skipif(os.name != "nt", reason="Windows first-creation stress")
def test_concurrent_fresh_derived_home_creation_is_race_stable(profile_tree):
    targets = [
        profile_tree["workspace_a"] / ".sage",
        profile_tree["workspace_a"] / ".sage-memory",
        profile_tree["profile_a"] / "hooks",
        profile_tree["profile_a"] / "skills",
        profile_tree["profile_a"] / "plugins" / "sage",
    ]
    start = threading.Barrier(4)
    finished = threading.Event()
    failures = []

    def publish_fresh_homes():
        start.wait()
        try:
            for _ in range(300):
                for target in targets:
                    target.mkdir(parents=True, exist_ok=True)
                for target in reversed(targets):
                    try:
                        target.rmdir()
                    except OSError:
                        pass
        finally:
            finished.set()

    def bind_while_published():
        start.wait()
        while not finished.is_set():
            try:
                _binding(profile_tree, "alpha")
            except BindingError as exc:
                failures.append(str(exc))

    threads = [threading.Thread(target=bind_while_published) for _ in range(3)]
    threads.append(threading.Thread(target=publish_fresh_homes))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15.0)

    assert all(not thread.is_alive() for thread in threads)
    assert failures == []


@pytest.mark.skipif(os.name != "nt", reason="Windows junction proof")
def test_windows_junction_escape_is_rejected_before_any_target_write(profile_tree):
    outside = profile_tree["root"] / "junction-target"
    outside.mkdir()
    state = profile_tree["workspace_a"] / ".sage"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(state), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("junction creation unavailable: " + result.stderr.strip())

    try:
        with pytest.raises(BindingError):
            _binding(profile_tree, "alpha")
        assert list(outside.iterdir()) == []
    finally:
        os.rmdir(str(state))


@pytest.mark.parametrize(
    "operation_id",
    ["", ".", "..", "../beta", "alpha/beta", "alpha\\beta", "C:\\escape"],
)
def test_run_journal_path_rejects_non_component_ids(profile_tree, operation_id):
    alpha = _binding(profile_tree, "alpha")
    with pytest.raises(BindingError):
        alpha.run_journal_path(operation_id)


def test_run_journal_path_is_canonical_and_contained(profile_tree):
    alpha = _binding(profile_tree, "alpha")
    path = alpha.run_journal_path("install-20260810-001")
    assert path == alpha.runs_root / "install-20260810-001.json"
    assert _is_within(alpha.runs_root, path)
    assert not path.exists()
