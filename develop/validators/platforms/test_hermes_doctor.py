#!/usr/bin/env python3
"""Behavioral contract for Task 20: the behavior-state doctor (spec 5.9.1-3).

The module under test is
``runtime/platforms/community/hermes/setup/doctor.py``. The doctor is
READ-ONLY and distinguishes present / registered / discovered / executed /
context-delivered / behaviorally-verified — only the last applicable state
counts as passing. Every drift case must produce a stable, named, nonzero
diagnostic with zero mutation.

Fixtures install a REAL candidate via the Task 18 installer, then diagnose.
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

import doctor  # red: module does not exist yet — collection error is the RED


BASH_EXE = "C:/Program Files/Git/bin/bash.exe"
ADAPTER = "sage-hermes-gate.sh"


def _write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hashes(root: pathlib.Path) -> dict:
    return {
        os.fspath(p.relative_to(root)): _digest(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


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
    return binding


def _make_artifact(tmp_path: pathlib.Path) -> pathlib.Path:
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
        _write(artifact / "hooks" / script, "#!/usr/bin/env bash\n# %s\n" % script)
    return artifact


@pytest.fixture()
def healthy(tmp_path):
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
    # A complete install includes the bound runtime surface the doctor checks.
    _write(binding.workspace_root / "sage" / "VERSION", "1.3.18\n")
    _write(binding.workspace_root / "sage" / "runtime" / "tools" / "manifest.py", "# tool\n")
    (binding.workspace_root / ".sage-memory").mkdir(exist_ok=True)
    (binding.workspace_root / ".sage-memory" / "memory.db").write_bytes(b"sqlite")
    return binding


def _states(report: dict) -> dict:
    return {check["name"]: check["state"] for check in report["checks"]}


# ── healthy ──────────────────────────────────────────────────────────────────

def test_static_diagnosis_reports_only_honest_present_or_registered_tiers(healthy) -> None:
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    assert report["ok"] is False
    for check in report["checks"]:
        assert check["state"] in {"present", "registered"}, check
        assert set(check) >= {"state", "required_state", "passed"}
        assert check["passed"] == (
            check["state"] == check["required_state"]
        ), check


def _verified_probe(*, binding, **_kwargs):
    return {
        "fresh_process_verified": True,
        "read_only": True,
        "checks": {
            "hooks": {"state": "behaviorally-verified", "verified": True},
            "argv": {"state": "executed", "verified": True},
            "plugin": {"state": "discovered", "verified": True},
            "runtime": {"state": "context-delivered", "verified": True},
            "memory": {
                "state": "behaviorally-verified",
                "verified": True,
                "memory_db_path": os.fspath(binding.memory_db_path),
            },
        },
    }


def test_verified_fresh_process_probe_can_satisfy_behavioral_requirements(healthy) -> None:
    report = doctor.diagnose(
        healthy, bash_path=BASH_EXE, behavioral_probe=_verified_probe
    )
    assert report["ok"] is True
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["hooks"]["state"] == "behaviorally-verified"
    assert checks["argv"]["state"] == "executed"
    assert checks["plugin"]["state"] == "discovered"
    assert checks["runtime"]["state"] == "context-delivered"
    assert checks["memory"]["state"] == "behaviorally-verified"
    assert all(check["passed"] for check in report["checks"])


@pytest.mark.parametrize(
    "probe_patch",
    [
        {"fresh_process_verified": False},
        {"read_only": False},
        {"checks": {"plugin": {"state": "discovered", "verified": False}}},
    ],
)
def test_unverified_probe_evidence_cannot_promote_static_states(
    healthy, probe_patch
) -> None:
    def probe(**kwargs):
        evidence = _verified_probe(**kwargs)
        evidence.update(probe_patch)
        return evidence

    report = doctor.diagnose(healthy, bash_path=BASH_EXE, behavioral_probe=probe)
    assert report["ok"] is False
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["plugin"]["state"] == "present"


def test_memory_probe_must_name_exact_bound_workspace_db(healthy, tmp_path) -> None:
    wrong_db = tmp_path / "global" / "memory.db"

    def probe(**kwargs):
        evidence = _verified_probe(**kwargs)
        evidence["checks"]["memory"]["memory_db_path"] = os.fspath(wrong_db)
        return evidence

    report = doctor.diagnose(healthy, bash_path=BASH_EXE, behavioral_probe=probe)
    memory = next(check for check in report["checks"] if check["name"] == "memory")
    assert report["ok"] is False
    assert memory["state"] == "present"
    assert memory["passed"] is False
    assert "exact bound workspace database" in memory["detail"]


def test_memory_probe_rejects_an_alias_spelling_of_the_bound_db(healthy) -> None:
    alias = healthy.memory_root / ".." / ".sage-memory" / "memory.db"

    def probe(**kwargs):
        evidence = _verified_probe(**kwargs)
        evidence["checks"]["memory"]["memory_db_path"] = os.fspath(alias)
        return evidence

    report = doctor.diagnose(healthy, bash_path=BASH_EXE, behavioral_probe=probe)
    memory = next(check for check in report["checks"] if check["name"] == "memory")
    assert report["ok"] is False
    assert memory["state"] == "present"


def test_behavioral_evidence_does_not_hide_a_static_failure(healthy) -> None:
    (healthy.profile_root / "plugins" / "sage" / "plugin.yaml").unlink()
    report = doctor.diagnose(
        healthy, bash_path=BASH_EXE, behavioral_probe=_verified_probe
    )
    plugin = next(check for check in report["checks"] if check["name"] == "plugin")
    assert report["ok"] is False
    assert plugin["state"] == "failed"
    assert plugin["passed"] is False


def test_doctor_is_read_only(healthy) -> None:
    before = _tree_hashes(healthy.profile_root)
    before_ws = _tree_hashes(healthy.workspace_root)
    report = doctor.diagnose(
        healthy, bash_path=BASH_EXE, behavioral_probe=_verified_probe
    )
    assert report["ok"] is True
    assert _tree_hashes(healthy.profile_root) == before
    assert _tree_hashes(healthy.workspace_root) == before_ws


# ── drift cases ──────────────────────────────────────────────────────────────

def test_drifted_managed_hash_fails(healthy) -> None:
    (healthy.profile_root / "hooks" / ADAPTER).write_text(
        "# tampered\n", encoding="utf-8"
    )
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    assert report["ok"] is False
    states = _states(report)
    assert states["receipt"] == "failed"


def test_wrong_binding_fails(healthy) -> None:
    config_path = healthy.profile_root / "config.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            healthy.profile_id, "someone-else", 1
        ),
        encoding="utf-8",
    )
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    assert report["ok"] is False
    assert _states(report)["binding"] == "failed"


def test_partial_install_fails(healthy) -> None:
    (healthy.profile_root / "hooks" / "sage-scope-gate.sh").unlink()
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    assert report["ok"] is False
    states = _states(report)
    assert states.get("hooks") == "failed" or states.get("config_policy") == "failed" or states.get("receipt") == "failed"


def test_bad_argv_fails(healthy) -> None:
    config_path = healthy.profile_root / "config.yaml"
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace('\\"' + BASH_EXE + '\\"', '\\"C:/nope/missing-bash.exe\\"'),
        encoding="utf-8",
    )
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    assert report["ok"] is False
    assert _states(report)["argv"] == "failed"


def test_wrong_seven_four_policy_fails(healthy) -> None:
    config_path = healthy.profile_root / "config.yaml"
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace("fail_closed: true", "fail_closed: false", 1),
        encoding="utf-8",
    )
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    assert report["ok"] is False
    assert _states(report)["config_policy"] == "failed"


def test_missing_bash_fails(healthy) -> None:
    report = doctor.diagnose(healthy, bash_path="C:/nope/definitely-not-bash.exe")
    assert report["ok"] is False
    assert _states(report)["argv"] == "failed"


def test_incomplete_runtime_fails(healthy) -> None:
    (healthy.workspace_root / "sage" / "VERSION").unlink()
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    assert report["ok"] is False
    assert _states(report)["runtime"] == "failed"


def test_version_mismatch_fails(healthy) -> None:
    _write(healthy.workspace_root / "sage" / "VERSION", "0.0.0\n")
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    assert report["ok"] is False
    assert _states(report)["version"] == "failed"


def test_missing_memory_isolation_fails(healthy) -> None:
    import shutil

    shutil.rmtree(healthy.workspace_root / ".sage-memory")
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    assert report["ok"] is False
    assert _states(report)["memory"] == "failed"


def test_report_names_resolved_roots(healthy) -> None:
    report = doctor.diagnose(healthy, bash_path=BASH_EXE)
    roots = report["roots"]
    assert roots["profile_root"] == os.fspath(healthy.profile_root)
    assert roots["workspace_root"] == os.fspath(healthy.workspace_root)
    assert "collection_root" in roots and "receipt_path" in roots
