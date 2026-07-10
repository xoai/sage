#!/usr/bin/env python3
"""Claude Code Stop adapter for exactly-once evidence reflection."""

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
from sage_runtime.lifecycle_adapter import reflection_context


def handle(envelope: Mapping[str, object], *, occurred_at: str | None = None) -> dict[str, object]:
    if envelope.get("stop_hook_active") is True:
        return {}
    context = reflection_context(envelope, source="claude-stop", occurred_at=occurred_at)
    return {"decision": "block", "reason": context} if context else {}


def main() -> int:
    print(json.dumps(handle(read_envelope())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
