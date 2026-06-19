#!/usr/bin/env bash
# Tests for automatic sage-memory MCP setup (sage init / sage setup memory).
# Verifies the merge is idempotent and NON-DESTRUCTIVE — it must never clobber
# an existing .mcp.json that holds other servers/secrets.
#
# Usage: bash develop/validators/memory-setup.test.sh
# Exit:  0 = all pass, 1 = at least one failure.

set -uo pipefail
BIN="$(cd "$(dirname "$0")/../.." && pwd)/bin/sage"
HAS_JQ=0; command -v jq >/dev/null 2>&1 && HAS_JQ=1
PASS=0; FAIL=0
green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }
check() { if [ "$2" -eq 0 ]; then PASS=$((PASS+1)); green "  ✓ $1"; else FAIL=$((FAIL+1)); red "  ✗ $1"; fi; }

mk_proj() { local d="$1" plat="${2:-claude-code}"; mkdir -p "$d/.sage"; printf 'platforms: [%s]\n' "$plat" > "$d/.sage/config.yaml"; }

echo ""
echo "── sage-memory setup tests ── (jq: $([ $HAS_JQ -eq 1 ] && echo present || echo absent))"

# 1) Fresh project: .mcp.json created with sage-memory; .gitignore gets .sage-memory/.
T="$(mktemp -d)"; mk_proj "$T"
( cd "$T" && bash "$BIN" setup memory ) >/dev/null 2>&1
grep -q '"sage-memory"' "$T/.mcp.json" 2>/dev/null && check "fresh: .mcp.json created with sage-memory" 0 || check "fresh: .mcp.json created with sage-memory" 1
grep -qxF '.sage-memory/' "$T/.gitignore" 2>/dev/null && check "fresh: .gitignore covers .sage-memory/" 0 || check "fresh: .gitignore covers .sage-memory/" 1
python3 -c "import json,sys; json.load(open('$T/.mcp.json'))" 2>/dev/null && check "fresh: .mcp.json is valid JSON" 0 || check "fresh: .mcp.json is valid JSON" 1

# 2) Idempotent: running again does not duplicate the entry.
( cd "$T" && bash "$BIN" setup memory ) >/dev/null 2>&1
# Count the KEY (`"sage-memory":`), not the package name (which also appears in args).
n=$(grep -c '"sage-memory":' "$T/.mcp.json" 2>/dev/null || echo 99)
[ "$n" -eq 1 ] && check "idempotent: exactly one sage-memory entry after re-run" 0 || check "idempotent: exactly one sage-memory entry (got $n)" 1
gn=$(grep -c '^\.sage-memory/$' "$T/.gitignore" 2>/dev/null || echo 99)
[ "$gn" -eq 1 ] && check "idempotent: .gitignore not duplicated" 0 || check "idempotent: .gitignore not duplicated (got $gn)" 1
rm -rf "$T"

# 3) NON-DESTRUCTIVE: an existing .mcp.json with another server is never clobbered.
T="$(mktemp -d)"; mk_proj "$T"
cat > "$T/.mcp.json" <<'JSON'
{
  "mcpServers": {
    "other-server": { "command": "node", "args": ["x.js"] }
  }
}
JSON
( cd "$T" && bash "$BIN" setup memory ) >/dev/null 2>&1
grep -q '"other-server"' "$T/.mcp.json" && check "merge: existing 'other-server' preserved (never clobbered)" 0 || check "merge: existing 'other-server' preserved (never clobbered)" 1
python3 -c "import json; json.load(open('$T/.mcp.json'))" 2>/dev/null && check "merge: .mcp.json still valid JSON" 0 || check "merge: .mcp.json still valid JSON" 1
if [ "$HAS_JQ" -eq 1 ]; then
  grep -q '"sage-memory"' "$T/.mcp.json" && check "merge (jq): sage-memory added alongside other-server" 0 || check "merge (jq): sage-memory added alongside other-server" 1
else
  # No jq → must NOT have hand-edited the file (would risk corruption); other-server intact, sage-memory not added.
  grep -q '"sage-memory"' "$T/.mcp.json" && check "merge (no jq): file left untouched, manual snippet path" 1 || check "merge (no jq): file left untouched, manual snippet path" 0
fi
rm -rf "$T"

# 4) Cursor platform → .cursor/mcp.json.
T="$(mktemp -d)"; mk_proj "$T" cursor
( cd "$T" && bash "$BIN" setup memory ) >/dev/null 2>&1
grep -q '"sage-memory"' "$T/.cursor/mcp.json" 2>/dev/null && check "cursor: server written to .cursor/mcp.json" 0 || check "cursor: server written to .cursor/mcp.json" 1
rm -rf "$T"

echo ""
echo "  memory-setup: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]