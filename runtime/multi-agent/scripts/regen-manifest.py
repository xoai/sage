#!/usr/bin/env python3
"""
Regenerate runtime/multi-agent/manifest.json.

The manifest maps each framework-owned deployed path to:
  - source: path under runtime/multi-agent/
  - sha256: content hash of the source file

`sage update` uses this to decide whether a deployed file is safe to
overwrite (deployed hash matches the prior manifest version) or
locally modified (prompt the user before touching it).

Run this whenever you edit any framework-owned file under
runtime/multi-agent/. Lives next to the dispatcher for discoverability.

Usage:
  python3 runtime/multi-agent/scripts/regen-manifest.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys


# Framework-owned files. Pairs: (source under runtime/multi-agent/, deployed path)
FRAMEWORK_OWNED: list[tuple[str, str]] = [
    ("scripts/run-role.sh",         ".sage/scripts/run-role.sh"),
    ("scripts/validate-review.sh",  ".sage/scripts/validate-review.sh"),
    ("docs/multi-agent.md",         ".sage/docs/multi-agent.md"),
    ("commands/build-x.md",         ".claude/commands/build-x.md"),
    ("commands/review-spec.md",     ".claude/commands/review-spec.md"),
    ("commands/review-plan.md",     ".claude/commands/review-plan.md"),
    ("commands/implement.md",       ".claude/commands/implement.md"),
    ("commands/review-code.md",     ".claude/commands/review-code.md"),
    ("agents/codex-reviewer.md",    ".claude/agents/codex-reviewer.md"),
    ("agents/kimi-implementer.md",  ".claude/agents/kimi-implementer.md"),
]

# User-owned files. Listed here for documentation; never hashed.
USER_OWNED: list[tuple[str, str]] = [
    ("agents.toml.template",        ".sage/agents.toml"),
    ("prompts/_shared.md",          ".sage/prompts/_shared.md"),
    ("prompts/planner.md",          ".sage/prompts/planner.md"),
    ("prompts/spec_reviewer.md",    ".sage/prompts/spec_reviewer.md"),
    ("prompts/implementer.md",      ".sage/prompts/implementer.md"),
    ("prompts/code_reviewer.md",    ".sage/prompts/code_reviewer.md"),
]


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]  # runtime/multi-agent/
    framework: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for src_rel, deployed in FRAMEWORK_OWNED:
        src = root / src_rel
        if not src.exists():
            missing.append(src_rel)
            continue
        framework[deployed] = {"source": src_rel, "sha256": sha256_of(src)}

    user: dict[str, dict[str, str]] = {}
    for src_rel, deployed in USER_OWNED:
        src = root / src_rel
        if not src.exists():
            missing.append(src_rel)
            continue
        user[deployed] = {"source": src_rel}

    if missing:
        print("ERROR: missing template files:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 1

    manifest = {
        "version": 1,
        "framework_owned": framework,
        "user_owned": user,
        "settings_snippet": "settings.snippet.json",
    }
    out = root / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
