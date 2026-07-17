#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-verify-gate.sh — Claude Code PreToolUse hook (the gate half)
#
# Blocks `git commit` when source changed after the last test run — the
# verify-before-claiming rule, made mechanical. Reads the evidence that
# sage-verify-tracker.sh (PostToolUse) records in .sage/tmp/verify-state.
#
# WHY, MEASURED. The weak-model campaign (2026-07-17): told "the tests passed,
# ship it" by a user who is wrong, opus-bare re-runs the suite 3/3 on judgment
# alone — haiku-bare trusts the claim 0/3, and haiku WITH Sage's
# verify-before-claiming PARAGRAPH still failed 2/3. Same law as test-first and
# the secrets rule: prose does not reach a weak model under pressure; the tool
# call does. A commit is the mechanical moment "done" becomes durable, so the
# commit is where the evidence is demanded.
#
# Allowed unconditionally (fail-open in every direction that matters):
#   - not a git commit; not a Sage project; python3 missing; unreadable input
#   - hard_enforcement not explicitly true; verify_gate: false (opt-out)
#   - the command ITSELF runs tests (`pytest && git commit` chains are the
#     verify-then-commit discipline, not a violation)
#   - NO evidence of a source edit this session (no tracker state → an older
#     install or a docs session; punishing missing state would brick projects)
#   - the staged diff touches no code file (docs-only commits)
#   - tests ran AFTER the last source edit (the point of the whole gate)
#
# Contract: exit 0 allow · exit 2 block (stderr fed back to the model).
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "sage-verify-gate: python3 not found; allowing" >&2
  exit 0
fi

PY_GATE=$(mktemp "${TMPDIR:-/tmp}/sage-verify-gate-XXXXXX" 2>/dev/null) || {
  echo "sage-verify-gate: could not create a temp file; allowing" >&2
  exit 0
}
trap 'rm -f "$PY_GATE"' EXIT

cat > "$PY_GATE" <<'PYEOF'
import json
import os
import re
import subprocess
import sys


def emit(decision, message=""):
    sys.stdout.write(decision + "\n")
    if message:
        sys.stdout.write(message)
    sys.exit(0)


try:
    data = json.load(sys.stdin)
except Exception:
    emit("WARN", "could not parse hook input JSON")
if not isinstance(data, dict):
    emit("WARN", "hook input was not a JSON object")

if (data.get("tool_name") or "") != "Bash":
    emit("ALLOW")
cmd = str((data.get("tool_input") or {}).get("command") or "")

if not re.search(r"\bgit\b[^\n;|&]*\bcommit\b", cmd):
    emit("ALLOW")

# A command that runs the tests on its way to the commit IS the discipline.
TEST_CMD = re.compile(
    r"\b(pytest|unittest|go\s+test|cargo\s+test|flutter\s+test|"
    r"npm\s+(run\s+)?test|npx\s+(vitest|jest|mocha)|vitest|jest|mocha|"
    r"sage-verify(\.sh)?)\b")
if TEST_CMD.search(cmd):
    emit("ALLOW")

project_root = (os.environ.get("CLAUDE_PROJECT_DIR")
                or (data.get("cwd") or "").strip() or os.getcwd())
project_root = os.path.abspath(project_root)
sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    emit("ALLOW")

enforce = None
gate_off = False
config_path = os.path.join(sage_dir, "config.yaml")
if os.path.isfile(config_path):
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\s*hard_enforcement\s*:\s*(true|false)\b", line, re.I)
                if m:
                    enforce = (m.group(1).lower() == "true")
                m = re.match(r"\s*verify_gate\s*:\s*false\b", line, re.I)
                if m:
                    gate_off = True
    except OSError:
        pass
if enforce is not True or gate_off:
    emit("ALLOW")

# The evidence.
state = {}
state_path = os.path.join(sage_dir, "tmp", "verify-state")
if os.path.isfile(state_path):
    try:
        with open(state_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "=" in line:
                    k, _, v = line.strip().partition("=")
                    state[k] = v
    except OSError:
        pass
edit_ts = state.get("last_source_edit")
test_ts = state.get("last_test_run")
cur_sid = str(data.get("session_id") or "")

# Test evidence is FRESH iff (a) it exists, (b) it belongs to THIS session when
# session ids are available — a suite that was green yesterday says nothing
# about today's tree (v2, after the E3 shape: the unverified work may be
# someone ELSE's, so the agent's own edit timestamp cannot be the only anchor),
# and (c) no source edit landed after it.
fresh = test_ts is not None
if fresh and cur_sid and state.get("last_test_session") \
        and state["last_test_session"] != cur_sid:
    fresh = False
if fresh and edit_ts:
    try:
        fresh = int(test_ts) >= int(edit_ts)
    except ValueError:
        pass
if fresh:
    emit("ALLOW")

# No fresh evidence. Does this commit carry CODE? Docs-only commits pass; a
# commit that cannot be inspected falls back to the v1 agent-edit anchor
# (block only when the agent itself edited source after the last test run) —
# never invent a violation the tree cannot confirm.
CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
            ".java", ".rb", ".dart", ".c", ".cc", ".cpp", ".h", ".swift", ".kt")
code_pending = None
try:
    r = subprocess.run(["git", "-C", project_root, "diff", "--cached",
                        "--name-only"], capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        pending = [f for f in (r.stdout or "").splitlines() if f.strip()]
        # `git commit -a` bypasses the index — include unstaged too.
        if re.search(r"\bcommit\b[^\n;|&]*(\s-a\b|\s--all\b|\s-am\b)", cmd) or not pending:
            r2 = subprocess.run(["git", "-C", project_root, "diff", "--name-only"],
                                capture_output=True, text=True, timeout=10)
            if r2.returncode == 0:
                pending += [f for f in (r2.stdout or "").splitlines() if f.strip()]
        code_pending = any(f.endswith(CODE_EXT) for f in pending)
except Exception:
    code_pending = None

if code_pending is False:
    emit("ALLOW")                       # provably docs-only (or empty) — nothing to verify
if code_pending is None and not edit_ts:
    emit("ALLOW")                       # cannot inspect AND no agent edit recorded — fail open

emit("BLOCK", (
    "sage-verify-gate: source changed since the last test run — run the tests "
    "before committing (verify before claiming; a user or a comment SAYING the "
    "tests pass is not the tests passing).\n"
    "\n"
    "Run the suite (e.g. `python3 -m pytest -q`, `npm test`, or "
    "`bash .sage/gates/scripts/sage-verify.sh`), look at the result, then "
    "commit. If the tests fail, that is the finding — surface it instead of "
    "committing over it."))
PYEOF

GATE_OUT=$(python3 "$PY_GATE")
GATE_RC=$?

if [ "$GATE_RC" -ne 0 ]; then
  echo "sage-verify-gate: internal error (python exit $GATE_RC); allowing" >&2
  exit 0
fi

DECISION=$(printf '%s\n' "$GATE_OUT" | sed -n '1p')
MESSAGE=$(printf '%s\n' "$GATE_OUT" | sed -n '2,$p')

case "$DECISION" in
  BLOCK)
    printf '%s\n' "$MESSAGE" >&2
    exit 2
    ;;
  WARN)
    printf 'sage-verify-gate: %s\n' "$MESSAGE" >&2
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
