#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" - "$ROOT" <<'PY'
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
route_hook = root / "runtime/platforms/claude-code/hooks/sage-route-context.py"
gate_hook = root / "runtime/platforms/claude-code/hooks/sage-strict-gate.py"

with tempfile.TemporaryDirectory() as raw_project:
    project = Path(raw_project)
    runtime_dir = project / ".sage" / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "route-catalog.json").write_text(
        json.dumps(
            {
                "schema": "route-catalog/v1",
                "platform": "claude-code",
                "routes": {
                    "map": {"workflow": "map", "target": "/map", "source": "map"}
                },
                "generated_at": "2026-07-10T12:00:00Z",
                "hash": "catalog-sha",
            }
        ),
        encoding="utf-8",
    )
    policy = project / "gate-modes.yaml"
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
    env = os.environ.copy()
    env.update(
        {
            "PYTHON_BIN": sys.executable,
            "SAGE_PROJECT": str(project),
            "SAGE_RUNTIME_CLI": str(root / "runtime/tools/sage_runtime_cli.py"),
            "SAGE_GATE_POLICY": str(policy),
        }
    )

    def invoke(path, payload):
        result = subprocess.run(
            [sys.executable, str(path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=project,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    route = invoke(
        route_hook,
        {
            "hook_event_name": "UserPromptSubmit",
            "cwd": str(project),
            "prompt": "Please map the spaces in this repository",
        },
    )
    context = route["hookSpecificOutput"]["additionalContext"]
    assert "/map" in context and "advisory" in context.lower()
    assert len(context.encode("utf-8")) <= 2048

    state_dir = runtime_dir / "runs" / "run-001"
    state_dir.mkdir(parents=True)
    state = {
        "schema": "run-state/v1",
        "run_id": "run-001",
        "status": "active",
        "explicit_intent": True,
        "workflow_owner": "sage:build",
        "active_capability": "change.implement",
        "active_provider": "sage:implement",
        "strict": True,
        "composition_hash": "composition-sha",
        "route_catalog_hash": "catalog-sha",
        "artifacts": {},
        "verification": {},
        "dirty": False,
        "updated_at": "2026-07-10T12:00:00Z",
    }
    (state_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
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
    denied = invoke(
        gate_hook,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "src/app.py", "content": "changed"},
            "cwd": str(project),
        },
    )["hookSpecificOutput"]
    assert denied["permissionDecision"] == "deny"
    assert "approved-plan" in denied["permissionDecisionReason"]

    allowed = invoke(
        gate_hook,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "src/app.py"},
            "cwd": str(project),
        },
    )["hookSpecificOutput"]
    assert allowed["permissionDecision"] == "allow"

print("Claude route/gate adapter contract: PASS")
PY
