# Lightpanda Browser Setup

Lightpanda is an optional dependency for Sage's /qa and /design-review
workflows. It provides browser-based testing via MCP. When not installed,
Sage falls back to code-only analysis.

## Install

### macOS (Homebrew)

```bash
brew install lightpanda
```

### Linux / WSL

```bash
ARCH=$(uname -m)
OS=$(uname -s | tr A-Z a-z)
curl -L -o lightpanda \
  https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-${ARCH}-${OS}
chmod +x ./lightpanda
sudo mv ./lightpanda /usr/local/bin/
```

### Docker

```bash
docker run -p 9222:9222 lightpanda/browser:nightly mcp
```

## Start MCP Server

```bash
lightpanda mcp
```

This starts the MCP server on stdio, ready for agent tool calls.

## MCP Configuration

### Claude Code

Add to `.claude/mcp.json` (project) or `~/.claude/mcp.json` (global):

```json
{
  "mcpServers": {
    "lightpanda": {
      "command": "lightpanda",
      "args": ["mcp"]
    }
  }
}
```

### Antigravity

Add to `.agent/mcp.json`:

```json
{
  "mcpServers": {
    "lightpanda": {
      "command": "lightpanda",
      "args": ["mcp"]
    }
  }
}
```

## Available MCP Tools

| Tool | What it does |
|------|-------------|
| `goto` | Navigate to a URL |
| `markdown` | Get page content as clean markdown |
| `semantic_tree` | Get structured page hierarchy |
| `interactiveElements` | List clickable/fillable elements with node IDs |
| `click` | Click an element by node ID |
| `fill` | Fill a form field by node ID |
| `evaluate` | Execute JavaScript in page context |
| `screenshot` | Capture page screenshot |
| `structuredData` | Extract JSON-LD, OpenGraph metadata |
| `console` | Get browser console output |

## Verification

After setup, verify in Claude Code:

```
> Can you navigate to http://localhost:3000?
```

If the agent successfully loads the page, Lightpanda is working.

## No-Lightpanda Behavior

When Lightpanda is not installed:
- /qa falls back to code-only analysis (diff review, contract checking)
- /design-review runs code audit only (no browser audit layer)
- browser-check gate (Gate 6) skips invisibly
- No warnings, no nag messages, no setup suggestions
  (unless the user explicitly invokes /qa)
