#!/usr/bin/env python3
"""Claude Code structured learning evidence observer."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Mapping


def _load_shared() -> None:
    project = Path(os.environ.get("SAGE_PROJECT", os.getcwd()))
    for candidate in (project / "sage/runtime/tools", Path(__file__).resolve().parents[3] / "tools"):
        if (candidate / "sage_runtime").is_dir():
            sys.path.insert(0, str(candidate))
            return


_load_shared()
from sage_runtime.adapter import read_envelope
from sage_runtime.lifecycle_adapter import observe_context


def handle(envelope: Mapping[str, object], *, occurred_at: str | None = None) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": str(envelope.get("hook_event_name", "PostToolUse")),
            "additionalContext": observe_context(
                envelope, occurred_at=occurred_at, dispatch=True
            ),
        }
    }


def main() -> int:
    print(json.dumps(handle(read_envelope())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
