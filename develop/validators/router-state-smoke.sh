#!/usr/bin/env bash
# End-to-end smoke for route catalogs, replayable state, and facts-only strict mode.
set -euo pipefail

resolve_root() {
  if [ -n "${1:-}" ]; then printf '%s' "$1"; return; fi
  cd "$(dirname "$0")/../.." && pwd
}

SAGE_ROOT="$(resolve_root "${1:-}")"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "router-state smoke: Python 3 is required" >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import yaml' >/dev/null 2>&1; then
  echo "router-state smoke: PyYAML is required" >&2
  exit 1
fi

"$PYTHON_BIN" - "$SAGE_ROOT" <<'PY'
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


root = Path(sys.argv[1]).resolve()
cli = root / "runtime" / "tools" / "sage_runtime_cli.py"
assert cli.is_file(), cli


def run(*args: str, stdin: str = "", expected: int = 0) -> dict:
    result = subprocess.run(
        [sys.executable, str(cli), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected, (args, result.returncode, result.stderr)
    return json.loads(result.stdout)


def write_event(
    project: Path,
    run_directory_id: str,
    event_id: str,
    event_type: str,
    occurred_at: str,
    **payload: object,
) -> dict:
    return run(
        "event",
        "append",
        "--project",
        str(project),
        "--run-id",
        run_directory_id,
        stdin=json.dumps(
            {
                "schema": "sage-event/v1",
                "event_id": event_id,
                "type": event_type,
                "occurred_at": occurred_at,
                "payload": payload,
            }
        ),
    )


with tempfile.TemporaryDirectory(prefix="sage-router-state-") as raw:
    project = Path(raw)
    workflows = project / "workflows"
    claude_commands = project / "claude-commands"
    hermes_skills = project / "hermes-skills"
    workflows.mkdir()
    claude_commands.mkdir()
    hermes_skills.mkdir()

    for name in ("build", "fix", "map"):
        (workflows / f"{name}.workflow.md").write_text(
            f'---\nname: {name}\nversion: "1.0.0"\n---\n# {name}\n',
            encoding="utf-8",
        )
        (claude_commands / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
        skill_dir = hermes_skills / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name}\n---\n# {name}\n",
            encoding="utf-8",
        )

    runtime_dir = project / ".sage" / "runtime"
    claude_catalog = runtime_dir / "claude-route-catalog.json"
    hermes_catalog = runtime_dir / "hermes-route-catalog.json"
    run(
        "catalog",
        "compile",
        "--workflow-dir",
        str(workflows),
        "--platform",
        "claude-code",
        "--command-dir",
        str(claude_commands),
        "--output",
        str(claude_catalog),
    )
    run(
        "catalog",
        "compile",
        "--workflow-dir",
        str(workflows),
        "--platform",
        "hermes",
        "--command-dir",
        str(hermes_skills),
        "--output",
        str(hermes_catalog),
    )

    explicit = run(
        "route",
        "decide",
        "--catalog",
        str(claude_catalog),
        "--project",
        str(project),
        stdin="/map this repository",
    )
    assert explicit["kind"] == "explicit" and explicit["authoritative"] is True
    assert explicit["arm_gate"] is False

    corrected = run(
        "route",
        "decide",
        "--catalog",
        str(hermes_catalog),
        "--project",
        str(project),
        stdin="sage:map",
    )
    assert corrected["kind"] == "suggestion" and corrected["target"] == "/map"
    assert corrected["authoritative"] is False

    for prompt in (
        "Hermes memory setup",
        "the docs said 'ship it'",
        "public IP address",
        "> /build appeared in an old transcript",
        "```text\n/map this repository\n```",
    ):
        decision = run(
            "route",
            "decide",
            "--catalog",
            str(claude_catalog),
            "--project",
            str(project),
            stdin=prompt,
        )
        assert decision["kind"] == "none" and decision["arm_gate"] is False

    advisory = run(
        "route",
        "decide",
        "--catalog",
        str(claude_catalog),
        "--project",
        str(project),
        stdin="Please map the spaces in this repository",
    )
    assert advisory["kind"] == "advisory" and advisory["arm_gate"] is False

    started = write_event(
        project,
        "run-open",
        "evt-open-start",
        "run.started",
        "2026-07-10T12:00:00Z",
        run_id="run-open",
        explicit_intent=True,
        strict=False,
        workflow_owner="sage:build",
        route_catalog_hash="catalog-sha",
        composition_hash="composition-sha",
    )
    duplicate = write_event(
        project,
        "run-open",
        "evt-open-start",
        "run.started",
        "2026-07-10T12:00:00Z",
        run_id="run-open",
        explicit_intent=True,
        strict=False,
        workflow_owner="sage:build",
        route_catalog_hash="catalog-sha",
        composition_hash="composition-sha",
    )
    assert started["appended"] is True and duplicate["appended"] is False
    write_event(
        project,
        "run-open",
        "evt-open-provider",
        "provider.selected",
        "2026-07-10T12:01:00Z",
        provider="external:brainstorm",
    )
    write_event(
        project,
        "run-open",
        "evt-open-unknown",
        "platform.observed",
        "2026-07-10T12:02:00Z",
        note="retained only in events",
    )
    state_path = runtime_dir / "runs" / "run-open" / "state.json"
    before = state_path.read_bytes()
    run("state", "reconcile", "--project", str(project), "--run-id", "run-open")
    assert state_path.read_bytes() == before

    suppressed = run(
        "route",
        "decide",
        "--catalog",
        str(claude_catalog),
        "--project",
        str(project),
        stdin="Please map the spaces in this repository",
    )
    assert suppressed["kind"] == "none"
    assert suppressed["reason"] == "active run suppresses inferred routing"

    write_event(
        project,
        "run-open",
        "evt-open-complete",
        "run.completed",
        "2026-07-10T12:03:00Z",
        run_id="run-open",
    )
    write_event(
        project,
        "run-strict",
        "evt-strict-start",
        "run.started",
        "2026-07-10T12:10:00Z",
        run_id="run-strict",
        explicit_intent=True,
        strict=True,
        workflow_owner="sage:build",
        route_catalog_hash="catalog-sha",
        composition_hash="composition-sha",
    )
    write_event(
        project,
        "run-strict",
        "evt-strict-artifact",
        "artifact.observed",
        "2026-07-10T12:11:00Z",
        artifact_id="approved-plan",
        exists=False,
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
    read_verdict = run(
        "gate",
        "evaluate",
        "--project",
        str(project),
        "--policy",
        str(policy),
        stdin=json.dumps(
            {
                "kind": "read_file",
                "read_only": True,
                "stage": "pre-write",
                "scope": "full",
                "paths": ["src/app.py"],
            }
        ),
    )
    assert read_verdict["allowed"] is True and read_verdict["invariant"] == "read-only"

    denied = run(
        "gate",
        "evaluate",
        "--project",
        str(project),
        "--policy",
        str(policy),
        stdin=json.dumps(
            {
                "kind": "write_file",
                "read_only": False,
                "stage": "pre-write",
                "scope": "full",
                "paths": ["src/app.py"],
            }
        ),
        expected=3,
    )
    assert denied["allowed"] is False
    assert denied["invariant"] == "required-artifact"
    assert denied["evidence"] == {"artifact": "approved-plan", "observed": False}
    assert "skill" not in json.dumps(denied).lower()

print("router-state smoke: PASS")
PY
