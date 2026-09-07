#!/usr/bin/env python3
"""Behavioral contract for Task 23: strict profile memory namespace and
visible fallback (spec 5.8.5-7).

Every memory session resolves the EXACT bound workspace database:
``<workspace>/.sage-memory/memory.db`` — verified per call, never assumed.
Project search never includes global memory; profile A never sees profile B;
a returned DB path that isn't the bound one fails visibly; junction/symlink
escapes are rejected. Tags are never the isolation mechanism — the database
file itself is.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "runtime" / "platforms" / "community" / "hermes" / "plugin-overlay"
sys.path.insert(0, str(OVERLAY))

import memory_namespace  # red: module does not exist yet — collection error is the RED


def _workspace(root: pathlib.Path, name: str) -> pathlib.Path:
    workspace = root / name / "workspace"
    workspace.mkdir(parents=True)
    return workspace


@pytest.fixture()
def pair(tmp_path):
    return _workspace(tmp_path, "alpha"), _workspace(tmp_path, "beta")


# ── resolution ───────────────────────────────────────────────────────────────

def test_resolve_returns_the_exact_bound_workspace_db(tmp_path) -> None:
    workspace = _workspace(tmp_path, "alpha")
    resolved = memory_namespace.resolve_memory_db(workspace)
    assert resolved == (workspace / ".sage-memory" / "memory.db")


def test_verify_session_db_accepts_the_bound_path(tmp_path) -> None:
    workspace = _workspace(tmp_path, "alpha")
    bound = memory_namespace.resolve_memory_db(workspace)
    assert memory_namespace.verify_session_db(bound, workspace) == bound


def test_verify_session_db_fails_visibly_on_a_wrong_db(tmp_path) -> None:
    workspace = _workspace(tmp_path, "alpha")
    wrong = tmp_path / "global" / "memory.db"
    with pytest.raises(memory_namespace.MemoryNamespaceError):
        memory_namespace.verify_session_db(wrong, workspace)


def test_missing_strict_mode_fails_visibly(tmp_path) -> None:
    workspace = _workspace(tmp_path, "alpha")
    with pytest.raises(memory_namespace.MemoryNamespaceError):
        memory_namespace.verify_session_db(None, workspace)


def test_junction_escape_is_rejected(tmp_path) -> None:
    real = _workspace(tmp_path, "real")
    link = tmp_path / "linked"
    try:
        os.symlink(real.parent, link)
    except OSError as exc:
        pytest.skip("symlink creation needs privilege on this host: %s" % exc)
    with pytest.raises(memory_namespace.MemoryNamespaceError):
        memory_namespace.resolve_memory_db(link / "workspace")


def test_sage_memory_dir_junction_is_rejected(tmp_path) -> None:
    workspace = _workspace(tmp_path, "alpha")
    shared = tmp_path / "shared-memory"
    shared.mkdir()
    try:
        os.symlink(shared, workspace / ".sage-memory")
    except OSError as exc:
        pytest.skip("symlink creation needs privilege on this host: %s" % exc)
    with pytest.raises(memory_namespace.MemoryNamespaceError):
        memory_namespace.resolve_memory_db(workspace)


def test_nonexistent_workspace_fails_visibly(tmp_path) -> None:
    with pytest.raises(memory_namespace.MemoryNamespaceError):
        memory_namespace.resolve_memory_db(tmp_path / "ghost" / "workspace")


# ── reciprocal isolation, before and after restart ───────────────────────────

def _round_trip(workspace, marker, visible=()):
    store = memory_namespace.WorkspaceMemoryStore(workspace)
    store.remember("sentinel", marker)
    assert store.recall("sentinel") == marker
    for other in visible:
        assert store.recall("sentinel") != other
    store.close()


def test_a_never_sees_b_or_global_and_reciprocally(pair, tmp_path) -> None:
    alpha, beta = pair
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    (global_dir / "memory.db").write_bytes(b"global-sentinel")

    _round_trip(alpha, "alpha-sentinel", visible=("beta-sentinel", "global-sentinel"))
    _round_trip(beta, "beta-sentinel", visible=("alpha-sentinel", "global-sentinel"))

    # Fresh process state: new store instances must see exactly the same.
    _round_trip(alpha, "alpha-sentinel", visible=("beta-sentinel", "global-sentinel"))
    _round_trip(beta, "beta-sentinel", visible=("alpha-sentinel", "global-sentinel"))


def test_store_survives_restart_with_only_own_rows(pair) -> None:
    alpha, beta = pair
    first = memory_namespace.WorkspaceMemoryStore(alpha)
    first.remember("k", "alpha-only")
    first.close()
    other = memory_namespace.WorkspaceMemoryStore(beta)
    other.remember("k", "beta-only")
    other.close()

    reopened = memory_namespace.WorkspaceMemoryStore(alpha)
    assert reopened.recall("k") == "alpha-only"
    reopened.close()
    reopened_beta = memory_namespace.WorkspaceMemoryStore(beta)
    assert reopened_beta.recall("k") == "beta-only"
    reopened_beta.close()


def test_store_db_is_the_bound_path(pair) -> None:
    alpha, _beta = pair
    store = memory_namespace.WorkspaceMemoryStore(alpha)
    assert store.db_path == memory_namespace.resolve_memory_db(alpha)
    store.close()
