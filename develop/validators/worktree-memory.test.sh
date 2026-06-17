#!/usr/bin/env bash
# Tests for worktree sage-memory handling:
#   1. `.mcp.json` (the MCP server config, gitignored) is seeded into a worktree
#      by default — without it the sage-memory server isn't configured there.
#   2. The session-init hook detects a linked worktree and directs the session to
#      sage_memory_set_project(<main root>), so memory is shared with the main
#      checkout (the DB is a single shared store, never copied/harvested).
#
# Usage: bash develop/validators/worktree-memory.test.sh
# Exit:  0 = all pass, 1 = at least one failure.

set -uo pipefail

ROOT_REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="$ROOT_REPO/bin/sage"
HOOK="$ROOT_REPO/runtime/platforms/claude-code/hooks/sage-session-init.sh"
PASS=0; FAIL=0
green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }
check() { if [ "$2" -eq 0 ]; then PASS=$((PASS+1)); green "  ✓ $1"; else FAIL=$((FAIL+1)); red "  ✗ $1"; fi; }

new_repo() {
  local d="$1"
  mkdir -p "$d" && git -C "$d" init -q -b main
  git -C "$d" config user.email t@t; git -C "$d" config user.name t
  printf '.sage/\n.sage-memory/\n.mcp.json\n' > "$d/.gitignore"
  echo code > "$d/app.txt"
  git -C "$d" add -A && git -C "$d" commit -qm init
}

echo ""
echo "── worktree sage-memory tests ──"

# 1) .mcp.json seeded into a new worktree (default worktree_copy).
T="$(mktemp -d)"; new_repo "$T/main"
mkdir -p "$T/main/.sage"; printf 'platforms: [claude-code]\n' > "$T/main/.sage/config.yaml"
printf '{"mcpServers":{"sage-memory":{"command":"uvx","args":["sage-memory"]}}}\n' > "$T/main/.mcp.json"
( cd "$T/main" && bash "$BIN" worktree mtest ) >/dev/null 2>&1
WT="$T/main-mtest"
[ -f "$WT/.mcp.json" ] && check ".mcp.json seeded into worktree (server configured there)" 0 || check ".mcp.json seeded into worktree (server configured there)" 1

# 2) session-init hook in the worktree emits the set_project(main) directive.
out_wt="$( cd "$WT" && bash "$HOOK" 2>/dev/null )"
printf '%s' "$out_wt" | grep -q "sage_memory_set_project" \
  && check "hook emits set_project directive in a worktree" 0 || check "hook emits set_project directive in a worktree" 1
# The directive names the MAIN checkout root (as git reports it), not the worktree.
expected_main="$( cd "$WT" && git worktree list --porcelain | awk '/^worktree /{print $2; exit}' )"
printf '%s' "$out_wt" | grep -qF "$expected_main" \
  && check "directive points at the main checkout root, not the worktree" 0 || check "directive points at the main checkout root, not the worktree" 1
# It must NOT name the worktree dir as the project root.
if printf '%s' "$out_wt" | grep -qF "path: $WT"; then wrc=1; else wrc=0; fi
check "directive does not point at the worktree itself" "$wrc"
printf '%s' "$out_wt" | grep -qi "never copy or harvest" \
  && check "directive states .sage-memory is shared (never harvested)" 0 || check "directive states .sage-memory is shared (never harvested)" 1

# 3) Same hook in the MAIN checkout does NOT emit the worktree directive.
out_main="$( cd "$T/main" && bash "$HOOK" 2>/dev/null )"
printf '%s' "$out_main" | grep -q "Memory (worktree)" \
  && check "main checkout: no worktree directive" 1 || check "main checkout: no worktree directive" 0

( cd "$T/main" && bash "$BIN" worktree remove mtest --force ) >/dev/null 2>&1
rm -rf "$T"

echo ""
echo "  worktree-memory: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
