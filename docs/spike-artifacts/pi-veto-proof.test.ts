/**
 * pi-veto-proof.test.ts — the Q1 proof (10-spec §21 R82).
 *
 * Drives the spike extension against Pi's FAUX MODEL PROVIDER: no network, no API
 * key, no spend, and a deterministic script of model turns. Pi exports the faux
 * provider publicly (packages/ai/src/index.ts re-exports providers/faux.ts), which
 * is what makes this proof free and repeatable rather than a $2 anecdote.
 *
 * The assertion is the one that matters, and it is deliberately hostile: the tool's
 * execute() THROWS. If the veto does not fire, the tool runs, the throw escapes,
 * and the test fails loudly. There is no way for this test to pass while the block
 * silently does nothing — which is the failure mode that has bitten this project
 * twice (codex's read-only sandbox and opencode's crashed runs BOTH left the file
 * unchanged, and a naive check would have recorded a successful veto in each case).
 *
 * Nothing-happened and correctly-blocked are indistinguishable unless you make the
 * mechanism prove itself. So:
 *
 *   1. the tool throws if executed          → a silent no-op cannot pass
 *   2. the file must not exist afterwards   → the write really did not happen
 *   3. the model must RECEIVE the reason    → an in-session denial, not a drop
 *
 * HOW TO RUN — see run-spike.md in this directory.
 */

import { describe, expect, it } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";

import {
  fauxAssistantMessage,
  fauxToolCall,
  registerFauxProvider,
} from "@earendil-works/pi-ai";

import { createHarness } from "../../test/suite/harness.js"; // pi's own harness

import sageSpike from "./pi-sage-spike.js";

describe("Sage spike — Q1: can a Pi extension veto a tool call?", () => {
  it("BLOCKS a write to *.blocked.* and tells the model why", async () => {
    const cwd = fs.mkdtempSync(path.join(os.tmpdir(), "sage-spike-"));
    const target = path.join(cwd, "test.blocked.ts");

    let toolActuallyRan = false;

    const faux = registerFauxProvider();
    faux.setResponses([
      // Turn 1: the model tries to create the forbidden file.
      fauxAssistantMessage([fauxToolCall("write", { path: target, content: "x" })], {
        stopReason: "toolUse",
      }),
      // Turn 2: whatever it says after receiving the tool result. We assert on the
      // tool result itself, not on this — an LLM's summary of what happened is not
      // evidence of what happened.
      fauxAssistantMessage([{ type: "text", text: "Understood — writing the spec first." }], {
        stopReason: "endTurn",
      }),
    ]);

    const harness = await createHarness({
      cwd,
      extensionFactories: [sageSpike],
      tools: [
        {
          name: "write",
          description: "write a file",
          parameters: { type: "object", properties: { path: { type: "string" } } },
          // If the veto fails, this runs — and a passing test becomes impossible.
          execute: async () => {
            toolActuallyRan = true;
            throw new Error("VETO FAILED: the tool executed. Q1 is NO.");
          },
        },
      ],
    });

    await harness.session.prompt("Create test.blocked.ts");

    // 1. The tool function was never invoked. This is the abort, not a swallowed result.
    expect(toolActuallyRan).toBe(false);

    // 2. The file does not exist. §22's success criterion, literally.
    expect(fs.existsSync(target)).toBe(false);

    // 3. The model RECEIVED the denial, addressed to the call it made. A veto the
    //    model never learns about is a dropped tool call, and it would loop forever.
    const messages = harness.session.getMessages();
    const toolResult = messages.find((m: any) => m.role === "toolResult");
    expect(toolResult).toBeDefined();
    expect(toolResult.isError).toBe(true);
    expect(JSON.stringify(toolResult.content)).toContain("Sage spike: pre-spec");
  });
});
