#!/usr/bin/env bash
# ╔═══════════════════════════════════════════════════════════╗
# ║  Sage MCP Discovery                                      ║
# ║                                                           ║
# ║  Connects to configured MCP servers, lists available      ║
# ║  tools, and caches the manifest for CLAUDE.md inclusion.  ║
# ║                                                           ║
# ║  Usage:                                                   ║
# ║    bash discover.sh [project-dir]                         ║
# ║                                                           ║
# ║  Reads from: .claude/mcp.json or .sage/mcp.json          ║
# ║  Writes to:  .sage/mcp-manifest.json                     ║
# ╚═══════════════════════════════════════════════════════════╝
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${1:-.}"
PROJECT="$(cd "$PROJECT" && pwd)"
MCP_CLIENT="$SCRIPT_DIR/mcp-client.ts"

echo "═══ Sage MCP Discovery ═══"
echo "  Project: $PROJECT"

# ── Find MCP config ──
MCP_CONFIG=""
if [ -f "$PROJECT/.claude/mcp.json" ]; then
  MCP_CONFIG="$PROJECT/.claude/mcp.json"
elif [ -f "$PROJECT/.sage/mcp.json" ]; then
  MCP_CONFIG="$PROJECT/.sage/mcp.json"
fi

if [ -z "$MCP_CONFIG" ]; then
  echo ""
  echo "  ⚠️  No MCP configuration found"
  echo "  Expected: .claude/mcp.json or .sage/mcp.json"
  echo ""
  echo "  To configure MCP servers, create .sage/mcp.json:"
  echo '  {'
  echo '    "mcpServers": {'
  echo '      "context7": {'
  echo '        "command": "npx",'
  echo '        "args": ["-y", "@upstash/context7-mcp@latest"]'
  echo '      }'
  echo '    }'
  echo '  }'
  echo ""

  # Write empty manifest
  mkdir -p "$PROJECT/.sage"
  cat > "$PROJECT/.sage/mcp-manifest.json" << 'EMPTY'
{
  "discovered": null,
  "servers": {},
  "summary": "No MCP servers configured. Add .sage/mcp.json to enable."
}
EMPTY

  echo "  ✅ Empty manifest written to .sage/mcp-manifest.json"
  exit 0
fi

echo "  Config: $MCP_CONFIG"
echo ""

# ── Check MCP client available ──
if [ ! -f "$MCP_CLIENT" ]; then
  echo "  ❌ MCP client not found at $MCP_CLIENT"
  exit 1
fi

# ── List servers in config ──
SERVERS=$(node -e "
  const config = JSON.parse(require('fs').readFileSync('$MCP_CONFIG', 'utf-8'));
  const servers = config.mcpServers || config;
  console.log(Object.keys(servers).join('\n'));
" 2>/dev/null)

if [ -z "$SERVERS" ]; then
  echo "  ⚠️  No servers found in config"
  exit 0
fi

echo "── Discovering tools from $(echo "$SERVERS" | wc -l) server(s) ──"
echo ""

# ── Discover tools from each server ──
MANIFEST_SERVERS=""
SUMMARY_LINES=""
TOTAL_TOOLS=0
HAS_FAILURES=false

cd "$PROJECT"

for server in $SERVERS; do
  echo -n "  $server: "

  # Call list-tools for this server
  TOOLS_JSON=$(npx tsx "$MCP_CLIENT" list-tools --server "$server" 2>/dev/null)

  if [ $? -ne 0 ] || [ -z "$TOOLS_JSON" ]; then
    echo "❌ failed to connect"
    HAS_FAILURES=true
    continue
  fi

  # Count tools and extract names
  TOOL_COUNT=$(echo "$TOOLS_JSON" | node -e "
    const data = JSON.parse(require('fs').readFileSync('/dev/stdin','utf-8'));
    const tools = data['$server'] || [];
    console.log(tools.length);
  " 2>/dev/null)

  TOOL_NAMES=$(echo "$TOOLS_JSON" | node -e "
    const data = JSON.parse(require('fs').readFileSync('/dev/stdin','utf-8'));
    const tools = data['$server'] || [];
    tools.forEach(t => console.log(t.name + '|' + t.description.substring(0, 80)));
  " 2>/dev/null)

  echo "✅ ${TOOL_COUNT:-0} tools"

  # Build manifest entry
  TOOLS_ARRAY=$(echo "$TOOLS_JSON" | node -e "
    const data = JSON.parse(require('fs').readFileSync('/dev/stdin','utf-8'));
    const tools = (data['$server'] || []).map(t => ({
      name: t.name,
      description: t.description || ''
    }));
    console.log(JSON.stringify(tools));
  " 2>/dev/null)

  # Accumulate for manifest
  if [ -n "$MANIFEST_SERVERS" ]; then
    MANIFEST_SERVERS="$MANIFEST_SERVERS,"
  fi
  MANIFEST_SERVERS="$MANIFEST_SERVERS\"$server\":$TOOLS_ARRAY"

  # Build summary line for CLAUDE.md
  TOOL_NAME_LIST=$(echo "$TOOLS_JSON" | node -e "
    const data = JSON.parse(require('fs').readFileSync('/dev/stdin','utf-8'));
    const tools = data['$server'] || [];
    console.log(tools.map(t => t.name).join(', '));
  " 2>/dev/null)

  SUMMARY_LINES="$SUMMARY_LINES\n- $server: $TOOL_NAME_LIST"
  TOTAL_TOOLS=$((TOTAL_TOOLS + ${TOOL_COUNT:-0}))

  # Print tool details
  echo "$TOOL_NAMES" | while IFS='|' read -r tname tdesc; do
    [ -n "$tname" ] && echo "    · $tname — $tdesc"
  done
  echo ""
done

# ── Write manifest ──
mkdir -p "$PROJECT/.sage"
TIMESTAMP=$(date -Iseconds)

cat > "$PROJECT/.sage/mcp-manifest.json" << MANIFEST
{
  "discovered": "$TIMESTAMP",
  "servers": {$MANIFEST_SERVERS},
  "summary": "$TOTAL_TOOLS tools across $(echo "$SERVERS" | wc -l) server(s)"
}
MANIFEST

echo "── Results ──"
echo "  Total: $TOTAL_TOOLS tools discovered"
echo "  Manifest: .sage/mcp-manifest.json"
echo ""

# ── Generate CLAUDE.md snippet ──
SNIPPET_FILE="$PROJECT/.sage/mcp-snippet.md"
cat > "$SNIPPET_FILE" << SNIPPET
## MCP Tools Available

Use \`npx tsx sage/runtime/mcp/mcp-client.ts call-tool <server> <tool>\` to call these.
For current framework docs, prefer context7 over training data.
$(echo -e "$SUMMARY_LINES")
SNIPPET

echo "  CLAUDE.md snippet: .sage/mcp-snippet.md"
echo ""

if [ "$HAS_FAILURES" = true ]; then
  echo "  ⚠️  Some servers failed to connect. Re-run after fixing configuration."
fi

echo "═══ Discovery complete ═══"
