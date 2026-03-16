# Sage MCP Integration

> **Status: Experimental** — Available but requires manual configuration.

Sage can discover and proxy MCP (Model Context Protocol) servers for tool
integration. This allows Sage skills to access external tools like databases,
APIs, and services.

## Configuration

Copy `sage-mcp-config.example.json` to your project and configure:

```json
{
  "servers": [
    {
      "name": "example-server",
      "command": "npx",
      "args": ["-y", "@example/mcp-server"]
    }
  ]
}
```

## Discovery

Run `bash sage/runtime/mcp/discover.sh` to detect available MCP servers
in your project configuration.
