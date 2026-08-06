#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-hermes-gate.sh — run a claude-code sage gate under the Hermes
# shell-hook protocol (adapter, single source of truth preserved).
#
# Claude Code hook contract (what the gate scripts implement):
#   exit 0  → allow      exit 2 → block, reason on stderr
#   stdin: {tool_name, tool_input.file_path, cwd, ...}
#
# Hermes shell-hook contract (docs: user-guide/features/hooks):
#   stdout JSON: {"decision":"block","reason":"..."} to block
#   stdin: {hook_event_name, tool_name, tool_input, cwd, ...}
#   where write_file/patch carry tool_input.path (not file_path)
#
# This adapter translates in both directions so the claude-code gate
# scripts stay the ONLY copy of the decision logic. Runs the gate once,
# reads exit code + both streams. Fails OPEN like every sage hook:
# any internal error allows the action.
#
# Usage (registered in <profile>/config.yaml hooks: block):
#   command: "<profile>/agent-hooks/sage/sage-hermes-gate.sh sage-spec-gate.sh"
# ═══════════════════════════════════════════════════════════════
set -uo pipefail

GATE_SCRIPT="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/$GATE_SCRIPT"

# No adapter arg, missing target, or no python3 → fail open.
if [ -z "$GATE_SCRIPT" ] || [ ! -f "$TARGET" ]; then
  echo "sage-hermes-gate: gate script '$GATE_SCRIPT' not found; allowing" >&2
  printf '{}\n'
  exit 0
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "sage-hermes-gate: python3 not found; allowing" >&2
  printf '{}\n'
  exit 0
fi

TMP_OUT="$(mktemp "${TMPDIR:-/tmp}/sage-hermes-gate-out-XXXXXX" 2>/dev/null)" || { printf '{}\n'; exit 0; }
TMP_ERR="$(mktemp "${TMPDIR:-/tmp}/sage-hermes-gate-err-XXXXXX" 2>/dev/null)" || { rm -f "$TMP_OUT"; printf '{}\n'; exit 0; }
trap 'rm -f "$TMP_OUT" "$TMP_ERR"' EXIT

PAYLOAD="$(cat 2>/dev/null || true)"

# Hermes payload → claude-code-shaped payload (path → file_path).
printf '%s' "$PAYLOAD" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
ti = d.get('tool_input') or {}
if isinstance(ti, dict) and 'path' in ti and 'file_path' not in ti:
    ti['file_path'] = ti['path']
out = {
    'hook_event_name': d.get('hook_event_name') or 'pre_tool_call',
    'tool_name': d.get('tool_name'),
    'tool_input': ti,
    'cwd': d.get('cwd') or '.',
}
print(json.dumps(out))
" 2>/dev/null | bash "$TARGET" >"$TMP_OUT" 2>"$TMP_ERR"
RC=$?

if [ "$RC" -eq 2 ]; then
  # Block: stderr carries the claude-code reason → Hermes JSON decision.
  python3 -c "
import json, sys
reason = sys.stdin.read().strip()[:4000]
if not reason:
    reason = 'blocked by sage gate'
print(json.dumps({'decision': 'block', 'reason': reason}))
" < "$TMP_ERR" 2>/dev/null || printf '{"decision":"block","reason":"blocked by sage gate"}\n'
  exit 0
fi

# Allow: if the gate printed JSON with context (session-init style),
# forward it as a Hermes context injection — as the ONLY JSON document
# on stdout (Hermes core json.loads the whole stdout, so a trailing
# {} would corrupt it). Silent allow otherwise.
python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ctx = None
if isinstance(d, dict):
    hso = d.get('hookSpecificOutput') or {}
    ctx = hso.get('additionalContext') or d.get('context')
if ctx:
    print(json.dumps({'context': str(ctx)[:8000]}))
else:
    print('{}')
" < "$TMP_OUT" 2>/dev/null || printf '{}\n'
