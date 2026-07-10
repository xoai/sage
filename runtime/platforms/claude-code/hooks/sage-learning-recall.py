#!/usr/bin/env python3
"""Claude Code UserPromptSubmit adapter for deterministic learning recall."""

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
from sage_runtime.adapter import combine_context, read_envelope
from sage_runtime.lifecycle_adapter import pending_candidate_context, recall_context


def handle(envelope: Mapping[str, object], *, backend: object | None = None) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": combine_context(
                recall_context(envelope, "claude-code", backend=backend),
                pending_candidate_context(envelope),
            ),
        }
    }


def main() -> int:
    print(json.dumps(handle(read_envelope())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
