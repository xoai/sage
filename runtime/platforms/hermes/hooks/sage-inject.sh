#!/usr/bin/env bash
set -euo pipefail

# Hermes pre_llm_call hook.
# Adapts Sage's canonical session context output to Hermes' {"context": "..."}
# response shape. The context body itself comes from sage-session-init.sh.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
SESSION_INIT="$SCRIPT_DIR/sage-session-init.sh"
PAYLOAD="$(cat - 2>/dev/null || true)"

if [ -n "$PAYLOAD" ] && command -v python3 >/dev/null 2>&1; then
  HOOK_CWD="$(printf '%s' "$PAYLOAD" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("cwd") or ""))' 2>/dev/null || true)"
  if [ -n "${HOOK_CWD:-}" ]; then
    cd "$HOOK_CWD" 2>/dev/null || true
  fi
fi

if [ ! -f "$SESSION_INIT" ]; then
  CONTEXT=""
else
  CONTEXT="$(printf '%s' "$PAYLOAD" | SAGE_SESSION_INIT_RAW=1 bash "$SESSION_INIT" 2>/dev/null || true)"
fi

ROUTING_CONTEXT="$(cat <<'EOF'
## Sage Routing Reminder (Hermes always-on)

Before answering the user, classify the latest ask. Do not wait for an explicit slash command.

- fix/bug/broken/error/crash/failing/debug/not working -> start `Sage -> fix workflow`
- build/implement/add/create/develop/ship/code/feature -> start `Sage -> build workflow`
- check/verify/make sure/test/QA -> verify with evidence
- explicit `/fix`, `/build`, `/qa`, etc. wins

For coding work: inspect real files/logs first, patch narrowly, verify with actual output, and restart/check services when runtime behavior changes.
EOF
)"

if [ -z "$CONTEXT" ]; then
  CONTEXT="$ROUTING_CONTEXT"
else
  CONTEXT="$ROUTING_CONTEXT

$CONTEXT"
fi

if command -v python3 >/dev/null 2>&1; then
  printf '%s' "$CONTEXT" | python3 -c 'import json,sys; print(json.dumps({"context": sys.stdin.read()}))'
else
  printf '{}\n'
fi
