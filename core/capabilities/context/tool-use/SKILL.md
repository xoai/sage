---
name: tool-use
description: >
  Guides tool selection across three layers: local scripts (zero context cost),
  MCP proxy (minimal context), and subagent dispatch (isolated context). Ensures
  the agent uses the cheapest effective layer and never pollutes the main context
  window with raw tool output. Use when the agent needs external information,
  current documentation, database access, or multi-step research.
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [tools, mcp, context, efficiency]
inputs: [task-context, mcp-manifest]
outputs: [tool-results]
requires: []
-->

# Tool Use

Pick the right tool at the right cost. Every token matters.

## When to Use

When the agent needs information that isn't in its context window: current
documentation, database queries, external APIs, file system operations, or
multi-step research. Also when the agent needs to verify information (check
if an import exists, test an API endpoint) rather than relying on memory.

**Core Principle:** The main context window is shared between your instructions
(CLAUDE.md), the conversation, the task, and any tool output. A 2000-token MCP
response is 2000 tokens of pack guidance or conversation history that gets pushed
out. Use the cheapest layer that answers the question. Escalate only when needed.

## The Three Layers

### Layer 1 — Local Tools (Zero Context Cost)

Bash scripts that run and return a result. The output is small and deterministic.
Use for anything that can be answered by running a command.

```bash
# Run tests
bash .sage/gates/scripts/sage-verify.sh .

# Check for hallucinated imports
bash .sage/gates/scripts/sage-hallucination-check.sh src/ .

# Capture screenshots
bash .sage/tools/sage-screenshot.sh http://localhost:3000 --output .sage/screenshots --full-page

# Check build
npm run build

# Check types
npx tsc --noEmit
```

**When:** Tests, builds, type checks, linting, screenshots, file operations.
**Cost:** Only the exit code or small output enters context.

### Layer 2 — MCP Proxy (Minimal Context Cost)

Calls an external MCP tool through the proxy script. The proxy connects to the
MCP server, executes the tool, and returns the extracted content — not the raw
protocol response.

```bash
# Get current framework documentation
npx tsx sage/runtime/mcp/mcp-client.ts call-tool context7 query-docs \
  --params '{"libraryId":"/nextjs/nextjs","topic":"server components caching"}'

# Resolve a library name to Context7 ID
npx tsx sage/runtime/mcp/mcp-client.ts call-tool context7 resolve-library-id \
  --params '{"libraryName":"supabase"}'
```

**When:** You need a SPECIFIC fact from current documentation. "What's the
exact API for `revalidatePath` in Next.js 16?" "What are the parameters for
Supabase's `createClient`?" Single-question, single-answer lookups.

**Cost:** ~200-500 tokens per call. The proxy extracts the relevant text.

**Decision test:** Can you state the exact question in one sentence? → Layer 2.
Do you need to browse, synthesize, or follow up? → Layer 3.

### Layer 3 — Subagent Dispatch (Isolated Context)

Spawn a subagent (on Tier 1 platforms like Claude Code) with a focused task.
The subagent has its own context window, can make multiple MCP calls, search
the web, and synthesize results. It returns a compressed summary.

**When:**
- Research requiring multiple sources or steps
- Category benchmarking (analyze 3-5 competitor approaches)
- Complex debugging requiring cross-referencing (Sentry errors + codebase + docs)
- Any task where you'd need 3+ Layer 2 calls to answer

**How to dispatch:**
```
Subagent task: "Research how Next.js 16 changed the caching model compared to
Next.js 15. Focus on: what's different for Server Components, what migration
steps are needed, and what the @sage/nextjs pack should update."

Context to include: @sage/nextjs pack rules (caching section only)
Return: 3-5 bullet summary of key changes + specific migration steps
```

**Cost:** Only the returned summary enters the main context (~100-300 tokens).
The subagent's full research stays in its isolated window.

## Tool Selection Rules

**MUST (violation = wasted context or missed information):**

- MUST check `.sage/mcp-manifest.json` before attempting MCP calls. If no
  manifest exists, run `bash sage/runtime/mcp/discover.sh .` first.
- MUST use Layer 1 for all verification tasks (tests, build, type check,
  screenshots). Never use MCP or subagents for things bash can do.
- MUST NOT paste raw MCP responses into the conversation. Extract the
  relevant fact and state it concisely.

**SHOULD (violation = inefficient but functional):**

- SHOULD prefer pack guidance over MCP lookups when the pack covers the topic.
  Packs contain judgment ("use server components for data fetching"). MCP
  contains knowledge ("here's the API for server components"). Judgment first,
  then knowledge if you need specific syntax.
- SHOULD batch related MCP calls. If you need 3 facts from the same library's
  docs, make one call with a broader topic rather than 3 narrow calls.
- SHOULD use Layer 3 for any task requiring 3+ MCP calls. The subagent
  handles the multi-step work; you get a summary.

**MAY (context-dependent):**

- MAY skip Layer 2 and go directly to Layer 3 for research-heavy tasks
  (category benchmarking, architecture research, migration planning).
- MAY use Layer 2 for a quick fact-check even if the pack likely covers it,
  when accuracy for a specific API detail is critical (version-specific syntax).

## Context Budget Awareness

Monitor your context usage. As conversation grows:

- **Early in conversation (< 30% context used):** Layers 2 and 3 freely.
  You have room for tool output.
- **Mid conversation (30-60%):** Prefer Layer 1 and Layer 3 (isolated).
  Avoid Layer 2 calls that return large text blocks.
- **Late in conversation (> 60%):** Layer 1 only. If you need MCP information,
  use Layer 3 with a tight summary requirement. Re-read `.sage/progress.md`
  to avoid losing your place.

## When NOT to Use Tools

- **The pack already answers the question.** "Should I use server components?"
  → Pack says yes. Don't query Context7 to confirm what the pack already states.
- **Your training data is sufficient.** "What does `useState` do?" → You know
  this. Don't waste a tool call.
- **The user already provided the answer.** If the user told you the API format,
  don't verify it with MCP. Trust the user over tools.

## Failure Modes

- **MCP server not responding:** Fall back to training data + web search.
  Note in your response: "Context7 was unreachable; using training data for
  this API reference — verify the syntax is current."
- **Tool returns irrelevant content:** Don't paste it into context. State:
  "MCP returned unrelated results for [query]. Falling back to [alternative]."
- **No MCP manifest exists:** Run discovery: `bash sage/runtime/mcp/discover.sh .`
  If no MCP config exists at all, tools are Layer 1 only — that's fine.
- **Subagent not available (Tier 2 platform):** Use Layer 2 with multiple
  focused calls. Summarize results yourself instead of delegating to a subagent.
