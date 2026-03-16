#!/usr/bin/env npx tsx
/**
 * Sage MCP Client — Layer 2 Proxy
 *
 * Connects to MCP servers and calls tools without polluting the
 * main agent's context window. Returns extracted results only.
 *
 * Usage:
 *   npx tsx mcp-client.ts list-tools [--server <name>]
 *   npx tsx mcp-client.ts call-tool <server> <tool> [--params '{"key":"value"}']
 *   npx tsx mcp-client.ts call-tool <server> <tool> --params-arg key1=value1 key2=value2
 *
 * Configuration:
 *   Reads from .claude/mcp.json or .sage/mcp.json (Claude Code standard format)
 *
 * Output:
 *   JSON to stdout. Errors to stderr. Exit code 0 on success, 1 on failure.
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { readFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";

// ── Types ──
interface MCPServerConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
}

interface MCPConfig {
  mcpServers: Record<string, MCPServerConfig>;
}

interface ToolInfo {
  name: string;
  description: string;
  inputSchema?: Record<string, unknown>;
}

interface CallResult {
  server: string;
  tool: string;
  success: boolean;
  content: string;
  contentType: "text" | "json" | "error";
}

// ── Config Loading ──
function findConfig(startDir: string = process.cwd()): MCPConfig | null {
  const searchPaths = [
    resolve(startDir, ".claude", "mcp.json"),
    resolve(startDir, ".sage", "mcp.json"),
  ];

  for (const configPath of searchPaths) {
    if (existsSync(configPath)) {
      try {
        const raw = readFileSync(configPath, "utf-8");
        const parsed = JSON.parse(raw);
        // Handle both { mcpServers: {} } and top-level server configs
        if (parsed.mcpServers) return parsed;
        return { mcpServers: parsed };
      } catch (e) {
        console.error(`Error reading ${configPath}: ${(e as Error).message}`);
      }
    }
  }
  return null;
}

// ── Server Connection ──
async function connectToServer(
  name: string,
  config: MCPServerConfig,
  timeoutMs: number = 15000
): Promise<Client> {
  const client = new Client(
    { name: `sage-mcp-${name}`, version: "1.0.0" },
    { capabilities: {} }
  );

  const env = { ...process.env, ...(config.env || {}) };

  const transport = new StdioClientTransport({
    command: config.command,
    args: config.args || [],
    env,
  });

  // Connect with timeout
  const connectPromise = client.connect(transport);
  const timeoutPromise = new Promise<never>((_, reject) =>
    setTimeout(() => reject(new Error(`Connection to ${name} timed out after ${timeoutMs}ms`)), timeoutMs)
  );

  await Promise.race([connectPromise, timeoutPromise]);
  return client;
}

// ── List Tools ──
async function listTools(
  config: MCPConfig,
  serverFilter?: string
): Promise<Record<string, ToolInfo[]>> {
  const results: Record<string, ToolInfo[]> = {};
  const servers = serverFilter
    ? { [serverFilter]: config.mcpServers[serverFilter] }
    : config.mcpServers;

  for (const [name, serverConfig] of Object.entries(servers)) {
    if (!serverConfig) {
      console.error(`Server '${name}' not found in config`);
      continue;
    }

    try {
      const client = await connectToServer(name, serverConfig);
      const response = await client.listTools();

      results[name] = (response.tools || []).map((t) => ({
        name: t.name,
        description: t.description || "",
        inputSchema: t.inputSchema as Record<string, unknown> | undefined,
      }));

      await client.close();
    } catch (e) {
      console.error(`Failed to list tools from ${name}: ${(e as Error).message}`);
      results[name] = [];
    }
  }

  return results;
}

// ── Call Tool ──
async function callTool(
  config: MCPConfig,
  serverName: string,
  toolName: string,
  params: Record<string, unknown>
): Promise<CallResult> {
  const serverConfig = config.mcpServers[serverName];
  if (!serverConfig) {
    return {
      server: serverName,
      tool: toolName,
      success: false,
      content: `Server '${serverName}' not found in MCP configuration`,
      contentType: "error",
    };
  }

  try {
    const client = await connectToServer(serverName, serverConfig);

    const response = await client.callTool({
      name: toolName,
      arguments: params,
    });

    await client.close();

    // Extract text content from response
    const contentParts = (response.content as Array<{ type: string; text?: string }>) || [];
    const textContent = contentParts
      .filter((c) => c.type === "text" && c.text)
      .map((c) => c.text!)
      .join("\n");

    // Try to detect if content is JSON
    let contentType: "text" | "json" = "text";
    if (textContent.startsWith("{") || textContent.startsWith("[")) {
      try {
        JSON.parse(textContent);
        contentType = "json";
      } catch {
        // Not JSON, keep as text
      }
    }

    return {
      server: serverName,
      tool: toolName,
      success: !response.isError,
      content: textContent,
      contentType,
    };
  } catch (e) {
    return {
      server: serverName,
      tool: toolName,
      success: false,
      content: (e as Error).message,
      contentType: "error",
    };
  }
}

// ── CLI ──
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === "--help" || command === "-h") {
    console.log(`Sage MCP Client — Layer 2 Proxy

Usage:
  npx tsx mcp-client.ts list-tools [--server <name>]
  npx tsx mcp-client.ts call-tool <server> <tool> [--params '{"key":"val"}']
  npx tsx mcp-client.ts call-tool <server> <tool> --params-arg key=val key2=val2

Examples:
  npx tsx mcp-client.ts list-tools
  npx tsx mcp-client.ts list-tools --server context7
  npx tsx mcp-client.ts call-tool context7 resolve-library-id --params '{"libraryName":"next.js"}'
  npx tsx mcp-client.ts call-tool context7 query-docs --params-arg libraryId=/nextjs/nextjs topic=caching`);
    process.exit(0);
  }

  const config = findConfig();
  if (!config) {
    console.error("No MCP configuration found.");
    console.error("Expected: .claude/mcp.json or .sage/mcp.json");
    console.error("See: runtime/mcp/sage-mcp-config.example.json");
    process.exit(1);
  }

  if (command === "list-tools") {
    const serverIdx = args.indexOf("--server");
    const serverFilter = serverIdx >= 0 ? args[serverIdx + 1] : undefined;

    const tools = await listTools(config, serverFilter);
    console.log(JSON.stringify(tools, null, 2));
    process.exit(0);
  }

  if (command === "call-tool") {
    const serverName = args[1];
    const toolName = args[2];

    if (!serverName || !toolName) {
      console.error("Usage: call-tool <server> <tool> [--params '{...}']");
      process.exit(1);
    }

    // Parse params from either --params JSON or --params-arg key=value pairs
    let params: Record<string, unknown> = {};

    const paramsIdx = args.indexOf("--params");
    const paramsArgIdx = args.indexOf("--params-arg");

    if (paramsIdx >= 0 && args[paramsIdx + 1]) {
      try {
        params = JSON.parse(args[paramsIdx + 1]);
      } catch {
        console.error("Invalid JSON in --params");
        process.exit(1);
      }
    } else if (paramsArgIdx >= 0) {
      // Parse key=value pairs
      for (let i = paramsArgIdx + 1; i < args.length; i++) {
        if (args[i].startsWith("--")) break;
        const eq = args[i].indexOf("=");
        if (eq > 0) {
          params[args[i].slice(0, eq)] = args[i].slice(eq + 1);
        }
      }
    }

    const result = await callTool(config, serverName, toolName, params);

    if (result.success) {
      // Output extracted content directly — not wrapped in JSON
      // This is what the agent sees in its context
      console.log(result.content);
      process.exit(0);
    } else {
      console.error(`MCP call failed: ${result.content}`);
      process.exit(1);
    }
  }

  console.error(`Unknown command: ${command}`);
  process.exit(1);
}

main().catch((e) => {
  console.error(`Fatal: ${e.message}`);
  process.exit(1);
});
