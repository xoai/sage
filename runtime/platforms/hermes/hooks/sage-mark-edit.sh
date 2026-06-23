#!/usr/bin/env bash
set -euo pipefail

# Hermes post_tool_call hook.
# Records that Hermes completed an edit-like tool call in this Sage project.
# post_tool_call is observer-only in Hermes, so this script never blocks.

PAYLOAD="$(cat - 2>/dev/null || true)"

if [ -n "$PAYLOAD" ] && command -v python3 >/dev/null 2>&1; then
  HOOK_CWD="$(printf '%s' "$PAYLOAD" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("cwd") or ""))' 2>/dev/null || true)"
  if [ -n "${HOOK_CWD:-}" ]; then
    cd "$HOOK_CWD" 2>/dev/null || true
  fi
fi

SAGE_DIR=".sage"
[ -d "$SAGE_DIR" ] || { printf '{}\n'; exit 0; }

MARKER="$SAGE_DIR/.last-edit"
TOOL_NAME=""
SESSION_ID=""
if command -v python3 >/dev/null 2>&1 && [ -n "$PAYLOAD" ]; then
  TOOL_NAME="$(printf '%s' "$PAYLOAD" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("tool_name") or "")' 2>/dev/null || true)"
  SESSION_ID="$(printf '%s' "$PAYLOAD" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("session_id") or "")' 2>/dev/null || true)"
fi

{
  printf 'updated_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date)"
  printf 'tool_name=%s\n' "$TOOL_NAME"
  printf 'session_id=%s\n' "$SESSION_ID"
} > "$MARKER" 2>/dev/null || true

GI="$SAGE_DIR/.gitignore"
if [ -e "$MARKER" ] && [ -d "$SAGE_DIR" ]; then
  if [ ! -f "$GI" ] || ! grep -qx ".last-edit" "$GI" 2>/dev/null; then
    if [ -s "$GI" ] && [ -n "$(tail -c1 "$GI" 2>/dev/null)" ]; then echo "" >> "$GI"; fi
    echo ".last-edit" >> "$GI"
  fi
fi

printf '{}\n'
