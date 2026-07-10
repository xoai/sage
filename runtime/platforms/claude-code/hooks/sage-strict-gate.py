#!/usr/bin/env python3
"""Claude Code PreToolUse adapter for facts-only Sage strict mode."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _load_shared() -> None:
    project = Path(os.environ.get("SAGE_PROJECT", os.getcwd()))
    candidates = [project / "sage/runtime/tools", Path(__file__).resolve().parents[3] / "tools"]
    for candidate in candidates:
        if (candidate / "sage_runtime").is_dir():
            sys.path.insert(0, str(candidate))
            return


_load_shared()

try:
    from sage_runtime.adapter import bounded_text, gate_verdict, operation_from_envelope
    from sage_runtime.adapter import project_path, read_envelope
except ImportError:
    bounded_text = gate_verdict = operation_from_envelope = None
    project_path = read_envelope = None


def main() -> int:
    if (
        read_envelope is None
        or operation_from_envelope is None
        or project_path is None
        or gate_verdict is None
        or bounded_text is None
    ):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "permissionDecisionReason": "",
                    }
                }
            )
        )
        return 0
    envelope = read_envelope()
    project = project_path(envelope)
    verdict = gate_verdict(operation_from_envelope(envelope, project), project)
    denied = isinstance(verdict, dict) and verdict.get("allowed") is False
    reason = ""
    if denied:
        reason = bounded_text(
            str(verdict.get("remediation") or verdict.get("invariant") or "Denied")
        )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny" if denied else "allow",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
