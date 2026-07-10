from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
HERMES_ROUTE = ROOT / "runtime/platforms/hermes/hooks/sage-pre-llm.py"
HERMES_GATE = ROOT / "runtime/platforms/hermes/hooks/sage-pre-tool.py"
CLAUDE_ROUTE = ROOT / "runtime/platforms/claude-code/hooks/sage-route-context.py"


def resolved_composition(*, include_sage_validator: bool = True) -> dict:
    bindings = [
        {
            "capability": "requirements.elicit",
            "provider_id": "external:brainstorm",
            "role": "owner",
            "combine": "exclusive",
            "atomic": True,
            "terminal": "design-approved",
            "provenance": "explicit",
        }
    ]
    if include_sage_validator:
        bindings.append(
            {
                "capability": "requirements.elicit",
                "provider_id": "sage:review",
                "role": "validator",
                "combine": "compatible",
                "atomic": False,
                "terminal": None,
                "provenance": "compatible",
            }
        )
    return {
        "schema": "resolved-composition/v1",
        "catalog_hash": "catalog-sha",
        "selected_workflow": "external:workflow",
        "bindings": bindings,
        "hash": "resolved-sha",
    }


def write_active_run(
    project: Path,
    *,
    include_sage_validator: bool = True,
    strict: bool = False,
    capability_entered: bool = True,
) -> None:
    runtime_dir = project / ".sage" / "runtime"
    run_dir = runtime_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    composition = resolved_composition(include_sage_validator=include_sage_validator)
    state = {
        "schema": "run-state/v1",
        "run_id": "run-001",
        "status": "active",
        "explicit_intent": True,
        "workflow_owner": "external:workflow",
        "active_capability": "requirements.elicit" if capability_entered else None,
        "active_provider": "external:brainstorm" if capability_entered else None,
        "strict": strict,
        "composition_hash": "resolved-sha",
        "route_catalog_hash": "route-sha",
        "artifacts": {},
        "verification": {},
        "dirty": False,
        "atomic_span": "external:brainstorm" if capability_entered else None,
        "provider_terminal": "design-approved" if capability_entered else None,
        "updated_at": "2026-07-10T14:00:00Z",
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (run_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "schema": "sage-event/v1",
                "event_id": "run-started",
                "type": "run.started",
                "occurred_at": "2026-07-10T14:00:00Z",
                "payload": {
                    "run_id": "run-001",
                    "resolved_composition": composition,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runtime_dir / "active-run.json").write_text(
        json.dumps(
            {
                "schema": "active-run/v1",
                "active": True,
                "run_id": "run-001",
                "state_path": "runs/run-001/state.json",
                "bound_at": "2026-07-10T14:00:00Z",
                "updated_at": "2026-07-10T14:00:00Z",
            }
        ),
        encoding="utf-8",
    )


def env(project: Path) -> dict[str, str]:
    value = os.environ.copy()
    value.update(
        {
            "PYTHON_BIN": sys.executable,
            "SAGE_PROJECT": str(project),
            "SAGE_RUNTIME_CLI": str(ROOT / "runtime/tools/sage_runtime_cli.py"),
        }
    )
    return value


def invoke(script: Path, project: Path, envelope: dict) -> dict:
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        cwd=project,
        env=env(project),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_claude_and_hermes_render_identical_locked_composition_context(
    tmp_path: Path,
) -> None:
    write_active_run(tmp_path)
    hermes = invoke(
        HERMES_ROUTE,
        tmp_path,
        {"cwd": str(tmp_path), "extra": {"user_message": "continue"}},
    )["context"]
    claude = invoke(
        CLAUDE_ROUTE,
        tmp_path,
        {"cwd": str(tmp_path), "prompt": "continue"},
    )["hookSpecificOutput"]["additionalContext"]

    assert hermes == claude
    assert "requirements.elicit" in hermes
    assert "external:brainstorm" in hermes
    assert "design-approved" in hermes
    assert "sage:review" in hermes
    assert "validator" in hermes
    assert len(hermes.encode("utf-8")) <= 3072


def test_resolved_plan_is_visible_before_first_capability_enters(
    tmp_path: Path,
) -> None:
    write_active_run(tmp_path, capability_entered=False)

    context = invoke(
        HERMES_ROUTE,
        tmp_path,
        {"cwd": str(tmp_path), "extra": {"user_message": "start the workflow"}},
    )["context"]

    assert "[Composition plan]" in context
    assert "requirements.elicit" in context
    assert "external:brainstorm" in context
    assert "sage:review (validator)" in context
    assert "Do not substitute another method" in context


def test_external_only_workflow_injects_no_sage_instruction_or_gate(tmp_path: Path) -> None:
    write_active_run(tmp_path, include_sage_validator=False, strict=True)
    policy = tmp_path / "gate-modes.yaml"
    policy.write_text(
        """strict_runtime:
  ttl_seconds: 0
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
    hook_env = env(tmp_path)
    hook_env["SAGE_GATE_POLICY"] = str(policy)
    context = invoke(
        HERMES_ROUTE,
        tmp_path,
        {"cwd": str(tmp_path), "extra": {"user_message": "continue"}},
    )["context"]
    result = subprocess.run(
        [sys.executable, str(HERMES_GATE)],
        input=json.dumps(
            {
                "cwd": str(tmp_path),
                "tool_name": "write_file",
                "tool_input": {"path": "src/app.py"},
                "extra": {},
            }
        ),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=hook_env,
        check=False,
    )

    assert "Sage" not in context
    assert json.loads(result.stdout) == {"action": "allow"}


def test_choice_required_context_is_injected_exactly_once(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".sage" / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "choice-required.json").write_text(
        json.dumps(
            {
                "schema": "choice-required/v1",
                "capability": "requirements.elicit",
                "candidates": [
                    {"provider_id": "owner-a", "provenance": "unresolved", "sources": []},
                    {"provider_id": "owner-b", "provenance": "unresolved", "sources": []},
                ],
                "reason": "multiple exclusive owners require explicit selection",
            }
        ),
        encoding="utf-8",
    )
    envelope = {"cwd": str(tmp_path), "extra": {"user_message": "start"}}

    first = invoke(HERMES_ROUTE, tmp_path, envelope)["context"]
    second = invoke(HERMES_ROUTE, tmp_path, envelope)["context"]

    assert "requirements.elicit" in first
    assert "owner-a" in first and "owner-b" in first
    assert "choose" in first.lower()
    assert second == ""
