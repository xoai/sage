#!/usr/bin/env python3
"""Claude Code UserPromptSubmit adapter for the shared Sage router."""

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
    from sage_runtime.adapter import (
        combine_context,
        composition_context,
        project_path,
        read_envelope,
        route_context,
    )
except ImportError:
    project_path = read_envelope = route_context = None
    combine_context = composition_context = None


def main() -> int:
    if (
        read_envelope is None
        or project_path is None
        or route_context is None
        or composition_context is None
        or combine_context is None
    ):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": "",
                    }
                }
            )
        )
        return 0
    envelope = read_envelope()
    prompt = envelope.get("prompt", "")
    project = project_path(envelope)
    session_id = envelope.get("session_id", "platform")
    context = combine_context(
        route_context(
            prompt if isinstance(prompt, str) else "",
            project,
            session_id=session_id if isinstance(session_id, str) else "platform",
        ),
        composition_context(project),
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
