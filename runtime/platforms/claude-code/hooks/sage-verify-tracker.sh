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

# The TDD gate's notion of source (sage-tdd-gate.sh SOURCE_EXT): what spends
# its red-commit unlock. Wider than CODE_EXT, which only times verify evidence.
TDD_SOURCE_EXT = (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go",
                  ".rs", ".java", ".rb", ".php", ".swift", ".kt", ".kts", ".c",
                  ".cc", ".cpp", ".h", ".hpp", ".cs", ".scala", ".ex", ".exs",
                  ".dart")

key = None
edited = ""                                     # project-relative, real path
if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
    path = str(tool_input.get("file_path") or "")
    real = os.path.realpath(path if os.path.isabs(path)
                            else os.path.join(project_root, path))
    rel = os.path.relpath(real, os.path.realpath(project_root)).replace(os.sep, "/")
    if rel.startswith(".."):
        rel = path.replace("\\", "/")           # outside the project: as given
    else:
        edited = rel
    # Sage machinery and docs are not source; a test file IS source here —
    # a freshly written test needs running exactly as much as the code does.
    # Judged on the project-relative path, so a project that itself lives
    # under .claude/worktrees/ is not mistaken for Sage machinery.
    machinery = any(seg in ("/.sage/", "/sage/", "/.claude/", "/node_modules/")
                    for seg in ["/" + p + "/" for p in ("/" + rel).split("/")[1:-1]])
    if machinery:
        edited = ""
    elif rel.endswith(CODE_EXT):
        key = "last_source_edit"
    if not edited.endswith(TDD_SOURCE_EXT):
        edited = ""
elif tool == "Bash":
    command = str(tool_input.get("command") or "")
    # Recording a baseline runs the suite but exits 0 even when it is red —
    # it is bookkeeping, not evidence that the tests pass.
    if TEST_CMD.search(command) and "--record-baseline" not in command:
        key = "last_test_run"

if key is None and not edited:
    sys.exit(0)

tmp_dir = os.path.join(sage_dir, "tmp")
state_path = os.path.join(tmp_dir, "verify-state")
try:
    os.makedirs(tmp_dir, exist_ok=True)
    # .sage/tmp/ is hook scratch, never project content: a self-ignoring
    # .gitignore keeps it out of `git status` without touching the user's own
    # .gitignore (review 2026-10-26, X7).
    ignore_path = os.path.join(tmp_dir, ".gitignore")
    if not os.path.exists(ignore_path):
        with open(ignore_path, "w", encoding="utf-8") as fh:
            fh.write("*\n")
except OSError:
    pass

if key is not None:
    try:
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

# The TDD gate's red-commit unlock (review 2026-10-26, X2): a test-only commit
# buys ONE change — the first source file edited after it. Recorded HERE,
# after the edit happened (a rejected or blocked edit spends nothing), once
# per HEAD; sage-tdd-gate.sh only reads it. Test files never spend it. A Bash
# write spends it in sage-bash-write-gate.sh, which sees the command.
TEST_RE = re.compile(r"(^|/)tests?/|(^|/)__tests__/|(^|/)spec/|(^|/)test_[^/]+$"
                     r"|[^/]*_test\.[a-z]+$|[^/]*\.(test|spec)\.[a-z]+$", re.I)
if edited:
    try:
        import subprocess
        head = subprocess.run(["git", "-C", project_root, "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=5)
        head = head.stdout.strip() if head.returncode == 0 else ""
        red = os.path.join(tmp_dir, "tdd-red")
        recorded = ""
        if os.path.isfile(red):
            with open(red, encoding="utf-8") as fh:
                recorded = fh.read().partition("\t")[0].strip()
        if head and recorded != head and not TEST_RE.search(edited):
            with open(red, "w", encoding="utf-8") as fh:
                fh.write("%s\t%s\n" % (head, edited))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
sys.exit(0)
PYEOF

python3 "$PY" 2>/dev/null || true
exit 0
