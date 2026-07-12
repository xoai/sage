/**
 * pi-sage-spike.ts — throwaway PoC for the Phase-1 Pi spike (10-spec §21 R81).
 *
 * NOT PRODUCTION CODE. Nothing here merges into runtime/ or core/ (R84). It exists
 * to answer three questions about Pi's extension API and then be deleted:
 *
 *   Q1 (decisive) — can an extension PREVENT a built-in tool call, with a denial
 *                   reason delivered back to the model in-session?
 *   Q2            — can an extension inject Sage's eager core at session start?
 *   Q3            — can an extension observe completed tool calls well enough to
 *                   implement the degradation log?
 *
 * Pi API version: @earendil-works/pi-coding-agent 0.80.6 (packages/coding-agent).
 * Pin exactly. Pi's own AGENTS.md:122 says a MINOR bump is where breaking changes
 * land ("patch = fixes + additions, minor = breaking changes. No major releases"),
 * and AGENTS.md:22 says "Do not preserve backward compatibility unless the user
 * asks for it." A caret range on this package is not a range, it is a bet.
 *
 * To run the proof, see run-spike.md in this directory.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const AUDIT_LOG = "/tmp/sage-spike-audit.log";

/** The one file the spike refuses to let the model create. */
const BLOCKED = /\.blocked\./;

export default function sageSpike(pi: ExtensionAPI): void {
  // ── Q2: context injection at session start ────────────────────────────────
  //
  // The equivalent of Claude Code's SessionStart additionalContext. `deliverAs:
  // "nextTurn"` queues the message for the next user prompt without interrupting
  // or triggering a turn — which is the semantics Sage's eager core needs: it must
  // be PRESENT before the model reasons, not shouted mid-thought.
  //
  // A custom message is converted to role:"user" on its way into the LLM context
  // (coding-agent/src/core/messages.ts:148-168), so this provably reaches the
  // model. Contrast pi.appendEntry(), which renders in the UI and is explicitly
  // NOT sent to the model — an easy and silent way to build a Sage that injects
  // nothing.
  pi.on("session_start", async (_event, ctx) => {
    const eager = readEagerCore(ctx.cwd);
    if (!eager) return;

    pi.sendMessage(
      {
        customType: "sage-eager-core",
        content: eager,
        display: "Sage: constitution + dispatcher loaded",
      },
      { deliverAs: "nextTurn" },
    );
  });

  // ── Q1: THE VETO ──────────────────────────────────────────────────────────
  //
  // The decisive question. Interception without denial is a NO — Sage's gates are
  // not advisory, and a platform that can only WATCH an edit it disagrees with
  // gives us Tier C, not Tier B.
  //
  // Mechanics: the `tool_call` event fires before execution, and returning
  // { block: true, reason } aborts it. The return value is genuinely consumed:
  //
  //   runner.emitToolCall()          extensions/runner.ts:881-902  (first block wins)
  //     → agent-session.ts:424-443   wires it to agent-core's beforeToolCall
  //       → agent-loop.ts:621-645    `if (beforeResult?.block) return { kind:
  //                                  "immediate", result: createErrorToolResult(...) }`
  //
  // Only `kind: "prepared"` reaches executePreparedToolCall(), which is the sole
  // caller of tool.execute(). So the tool function is never invoked — this is a
  // true abort, not a suppressed result. The `reason` becomes an errored
  // toolResult addressed to the exact toolCallId the model asked for, which is
  // appended to the conversation and sent on the next provider call. The model
  // sees the denial and can react to it. That is Sage's hook contract, exactly.
  //
  // NOTE the shape: it is a RETURNED DECISION OBJECT, not a thrown error and not
  // a mutated call. (Throwing also blocks — emitToolCall has no try/catch, unlike
  // every sibling emitter — but { block, reason } is the documented, typed, and
  // vendor-tested path. Use it.)
  pi.on("tool_call", async (event, _ctx) => {
    const target = filePathOf(event.toolName, event.input);
    if (!target || !BLOCKED.test(target)) return;

    return {
      block: true,
      reason:
        `Sage spike: pre-spec. \`${path.basename(target)}\` matches a blocked ` +
        `pattern, so this write was refused before it ran. Write the spec first.`,
    };
  });

  // ── Q3: post-tool observation (the degradation log) ───────────────────────
  //
  // `tool_result` carries toolName, input, content, isError and a correlating
  // toolCallId — everything the degradation log needs. tool_execution_end is the
  // lighter alternative but drops `input`, which is the field that makes an audit
  // line worth writing.
  //
  // In Pi's parallel tool mode these may interleave in completion order, so an
  // audit log must key on toolCallId rather than trusting arrival order
  // (docs/extensions.md:822).
  pi.on("tool_result", async (event, _ctx) => {
    const line = JSON.stringify({
      at: new Date().toISOString(),
      tool: event.toolName,
      id: event.toolCallId,
      error: event.isError,
      input: event.input,
    });
    fs.appendFileSync(AUDIT_LOG, line + "\n");
  });
}

/**
 * Q5: synchronous fs from extension context.
 *
 * Extensions are in-process TypeScript loaded via jiti — no sandbox, no worker,
 * node builtins available (docs/extensions.md:155; "Extensions run with your full
 * system permissions", :112). Reading .sage/work/-star-/manifest.md synchronously is a
 * non-issue, which is what a Sage gate needs to do on every tool call.
 */
function readEagerCore(cwd: string): string | null {
  const candidate = path.join(cwd, ".sage", "CLAUDE.md");
  try {
    if (!fs.existsSync(candidate)) return null;
    return fs.readFileSync(candidate, "utf8");
  } catch {
    return null;
  }
}

/** The path a write/edit tool is about to touch, or null for tools that touch none. */
function filePathOf(
  toolName: string,
  input: Record<string, unknown>,
): string | null {
  if (toolName !== "write" && toolName !== "edit") return null;
  const p = input.path ?? input.file_path ?? input.filePath;
  return typeof p === "string" ? p : null;
}
