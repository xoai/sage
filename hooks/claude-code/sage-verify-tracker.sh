#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-verify-tracker.sh — Claude Code PostToolUse hook (the evidence half)
#
# Records two timestamps in .sage/tmp/verify-state:
#   last_source_edit   an Edit/Write/MultiEdit landed on a code file
#   last_test_run      a Bash command that runs tests completed
#
# It never blocks anything (PostToolUse cannot); it only writes the evidence
# that sage-verify-gate.sh reads at `git commit` time. Split into two scripts
# on purpose: a recorder that always succeeds and a gate that reads state are
# separately testable, and a bug in one cannot take down the other.
#
# HOOKS ARE GUARDS, NOT GATES — any internal error exits 0 silently.
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

command -v python3 >/dev/null 2>&1 || exit 0

PY=$(mktemp "${TMPDIR:-/tmp}/sage-verify-tracker-XXXXXX" 2>/dev/null) || exit 0
trap 'rm -f "$PY"' EXIT

cat > "$PY" <<'PYEOF'
import json
import os
import re
import sys
import time

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(data, dict):
    sys.exit(0)

project_root = (os.environ.get("CLAUDE_PROJECT_DIR")
                or (data.get("cwd") or "").strip() or os.getcwd())
project_root = os.path.abspath(project_root)
sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    sys.exit(0)

tool = data.get("tool_name") or ""
tool_input = data.get("tool_input") or {}
session_id = str(data.get("session_id") or "")

CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
            ".java", ".rb", ".dart", ".c", ".cc", ".cpp", ".h", ".swift", ".kt")
TEST_CMD = re.compile(
    r"\b(pytest|unittest|go\s+test|cargo\s+test|flutter\s+test|"
    r"npm\s+(run\s+)?test|npx\s+(vitest|jest|mocha)|vitest|jest|mocha|"
    r"sage-verify(\.sh)?)\b")

key = None
if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
    path = str(tool_input.get("file_path") or "")
    rel = path.replace("\\", "/")
    # Sage machinery and docs are not source; a test file IS source here —
    # a freshly written test needs running exactly as much as the code does.
    if rel.endswith(CODE_EXT) and not any(
            seg in ("/.sage/", "/sage/", "/.claude/", "/node_modules/")
            for seg in ["/" + p + "/" for p in rel.split("/")[:-1]]):
        key = "last_source_edit"
elif tool == "Bash":
    if TEST_CMD.search(str(tool_input.get("command") or "")):
        key = "last_test_run"

if key is None:
    sys.exit(0)

tmp_dir = os.path.join(sage_dir, "tmp")
state_path = os.path.join(tmp_dir, "verify-state")
try:
    os.makedirs(tmp_dir, exist_ok=True)
    state = {}
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "=" in line:
                    k, _, v = line.strip().partition("=")
                    state[k] = v
    state[key] = str(int(time.time() * 1000))
    if session_id:
        state[key.replace("_run", "").replace("_edit", "") + "_session"] = session_id
    with open(state_path, "w", encoding="utf-8") as fh:
        for k, v in sorted(state.items()):
            fh.write(f"{k}={v}\n")
except OSError:
    pass
sys.exit(0)
PYEOF

python3 "$PY" 2>/dev/null || true
exit 0
