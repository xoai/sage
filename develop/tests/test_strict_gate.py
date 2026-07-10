from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.contracts import RunState
from sage_runtime.gate import GatePolicy, Operation, evaluate


BOUND_AT = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


def run_state(
    *,
    strict: bool = True,
    explicit_intent: bool = True,
    artifacts: dict | None = None,
    verification: dict | None = None,
    workflow_owner: str = "sage:build",
) -> RunState:
    return RunState.from_dict(
        {
            "schema": "run-state/v1",
            "run_id": "run-001",
            "status": "active",
            "explicit_intent": explicit_intent,
            "workflow_owner": workflow_owner,
            "active_capability": "change.implement",
            "active_provider": "sage:implement",
            "strict": strict,
            "composition_hash": "composition-sha",
            "route_catalog_hash": "catalog-sha",
            "artifacts": artifacts or {},
            "verification": verification or {},
            "dirty": False,
            "updated_at": "2026-07-10T12:00:00Z",
        }
    )


def policy(
    *,
    artifacts: list[str] | None = None,
    approvals: list[str] | None = None,
    verification: list[str] | None = None,
    lane_roots: list[str] | None = None,
    lightweight_artifacts: list[str] | None = None,
    ttl_seconds: int = 3600,
) -> GatePolicy:
    return GatePolicy.from_dict(
        {
            "bound_at": "2026-07-10T12:00:00Z",
            "ttl_seconds": ttl_seconds,
            "lane_roots": lane_roots or [],
            "scopes": {
                "full": {
                    "stages": {
                        "pre-write": {
                            "required_artifacts": artifacts or [],
                            "required_approvals": approvals or [],
                            "required_verifications": verification or [],
                        }
                    }
                },
                "lightweight": {
                    "stages": {
                        "pre-write": {
                            "required_artifacts": lightweight_artifacts or [],
                            "required_approvals": [],
                            "required_verifications": [],
                        }
                    }
                },
            },
        }
    )


def operation(
    *, read_only: bool = False, scope: str = "full", paths: tuple[str, ...] = ("src/app.py",)
) -> Operation:
    return Operation(
        kind="tool",
        read_only=read_only,
        stage="pre-write",
        scope=scope,
        paths=paths,
    )


def test_advisory_or_missing_route_never_arms_strict_gate() -> None:
    verdict = evaluate(
        operation(),
        run_state(explicit_intent=False),
        policy(artifacts=["approved-plan"]),
        BOUND_AT + timedelta(minutes=1),
    )

    assert verdict.allowed is True
    assert verdict.invariant == "explicit-route-required"


def test_missing_active_state_fails_open() -> None:
    verdict = evaluate(operation(), None, policy(artifacts=["approved-plan"]), BOUND_AT)

    assert verdict.allowed is True
    assert verdict.invariant == "active-run-required"


def test_read_only_operation_is_always_allowed() -> None:
    verdict = evaluate(
        operation(read_only=True),
        run_state(),
        policy(artifacts=["approved-plan"], lane_roots=["other"]),
        BOUND_AT,
    )

    assert verdict.allowed is True
    assert verdict.invariant == "read-only"


def test_non_strict_run_is_always_allowed() -> None:
    verdict = evaluate(
        operation(),
        run_state(strict=False),
        policy(artifacts=["approved-plan"]),
        BOUND_AT,
    )

    assert verdict.allowed is True
    assert verdict.invariant == "strict-disabled"


def test_external_workflow_does_not_activate_sage_strict_gate() -> None:
    verdict = evaluate(
        operation(),
        run_state(workflow_owner="external:workflow"),
        policy(artifacts=["approved-plan"]),
        BOUND_AT,
    )

    assert verdict.allowed is True
    assert verdict.invariant == "sage-workflow-inactive"


def test_strict_run_denies_only_a_declared_missing_artifact() -> None:
    verdict = evaluate(
        operation(),
        run_state(),
        policy(artifacts=["approved-plan"]),
        BOUND_AT,
    )

    assert verdict.allowed is False
    assert verdict.invariant == "required-artifact"
    assert verdict.evidence == {"artifact": "approved-plan", "observed": False}
    assert "approved-plan" in verdict.remediation


def test_strict_run_denies_only_a_declared_absent_approval() -> None:
    verdict = evaluate(
        operation(),
        run_state(artifacts={"approved-plan": {"exists": True}}),
        policy(artifacts=["approved-plan"], approvals=["plan-approved"]),
        BOUND_AT,
    )

    assert verdict.allowed is False
    assert verdict.invariant == "required-approval"
    assert verdict.evidence["checkpoint"] == "plan-approved"


def test_strict_run_denies_only_a_declared_failed_verification() -> None:
    state = run_state(
        artifacts={
            "approved-plan": {"exists": True},
            "approvals": {"plan-approved": {"approved": True}},
        },
        verification={"unit-tests": {"passed": False, "exit_code": 1}},
    )
    verdict = evaluate(
        operation(),
        state,
        policy(
            artifacts=["approved-plan"],
            approvals=["plan-approved"],
            verification=["unit-tests"],
        ),
        BOUND_AT,
    )

    assert verdict.allowed is False
    assert verdict.invariant == "required-verification"
    assert verdict.evidence["verification"] == "unit-tests"


def test_strict_run_denies_a_write_outside_the_locked_lane() -> None:
    verdict = evaluate(
        operation(paths=("docs/outside.md",)),
        run_state(),
        policy(lane_roots=["src", "tests"]),
        BOUND_AT,
    )

    assert verdict.allowed is False
    assert verdict.invariant == "locked-lane"
    assert verdict.evidence["path"] == "docs/outside.md"


def test_strict_run_denies_unscoped_mutation_when_lane_is_locked() -> None:
    verdict = evaluate(
        operation(paths=()),
        run_state(),
        policy(lane_roots=["src", "tests"]),
        BOUND_AT,
    )

    assert verdict.allowed is False
    assert verdict.invariant == "locked-lane"
    assert verdict.evidence == {
        "path": None,
        "lane_roots": ["src", "tests"],
        "reason": "mutating operation has no deterministic path evidence",
    }


def test_satisfied_declared_invariants_allow_the_write() -> None:
    state = run_state(
        artifacts={
            "approved-plan": {"exists": True},
            "approvals": {"plan-approved": {"approved": True}},
        },
        verification={"unit-tests": {"passed": True}},
    )
    verdict = evaluate(
        operation(),
        state,
        policy(
            artifacts=["approved-plan"],
            approvals=["plan-approved"],
            verification=["unit-tests"],
            lane_roots=["src"],
        ),
        BOUND_AT,
    )

    assert verdict.allowed is True
    assert verdict.invariant == "strict-invariants-satisfied"


def test_denial_does_not_refresh_bound_at_or_ttl() -> None:
    gate_policy = policy(artifacts=["approved-plan"], ttl_seconds=60)
    original_bound_at = gate_policy.bound_at
    original_expiry = gate_policy.expires_at

    first = evaluate(operation(), run_state(), gate_policy, BOUND_AT + timedelta(seconds=5))
    second = evaluate(operation(), run_state(), gate_policy, BOUND_AT + timedelta(seconds=30))

    assert first.allowed is False
    assert second.allowed is False
    assert gate_policy.bound_at == original_bound_at
    assert gate_policy.expires_at == original_expiry


def test_expired_binding_fails_open_without_rearming() -> None:
    gate_policy = policy(artifacts=["approved-plan"], ttl_seconds=60)

    verdict = evaluate(operation(), run_state(), gate_policy, BOUND_AT + timedelta(seconds=61))

    assert verdict.allowed is True
    assert verdict.invariant == "binding-expired"
    assert gate_policy.bound_at == BOUND_AT


def test_lightweight_scope_does_not_require_skipped_full_artifacts() -> None:
    verdict = evaluate(
        operation(scope="lightweight"),
        run_state(),
        policy(artifacts=["approved-plan"], lightweight_artifacts=[]),
        BOUND_AT,
    )

    assert verdict.allowed is True
    assert verdict.invariant == "strict-invariants-satisfied"


def test_gate_cli_returns_three_for_a_concrete_strict_denial(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".sage" / "runtime"
    state_dir = runtime_dir / "runs" / "run-001"
    state_dir.mkdir(parents=True)
    (state_dir / "state.json").write_text(
        json.dumps(run_state().to_dict()), encoding="utf-8"
    )
    (runtime_dir / "active-run.json").write_text(
        json.dumps(
            {
                "schema": "active-run/v1",
                "active": True,
                "run_id": "run-001",
                "state_path": "runs/run-001/state.json",
                "bound_at": "2026-07-10T12:00:00Z",
                "updated_at": "2026-07-10T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    policy_path = tmp_path / "gate-modes.yaml"
    policy_path.write_text(
        """strict_runtime:
  ttl_seconds: 3600
  lane_roots: []
  scopes:
    full:
      stages:
        pre-write:
          required_artifacts: [approved-plan]
          required_approvals: []
          required_verifications: []
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "sage_runtime_cli.py"),
            "gate",
            "evaluate",
            "--project",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--now",
            "2026-07-10T12:01:00Z",
        ],
        input="\ufeff" + json.dumps(operation().to_dict()),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 3, result.stderr
    verdict = json.loads(result.stdout)
    assert verdict["allowed"] is False
    assert verdict["invariant"] == "required-artifact"
