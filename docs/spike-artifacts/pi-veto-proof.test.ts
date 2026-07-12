/**
 * pi-veto-proof.test.ts — the Q1/Q2/Q3 proof (10-spec §21 R82).
 *
 * Driven by Pi's FAUX model provider: no network, no API key, no spend.
 *
 * The Q1 assertion is deliberately hostile: the `write` tool's execute() creates
 * the file and records that it ran. If the veto does not fire, the file exists and
 * the flag is true, and the test fails. There is no way for it to pass while the
 * block quietly does nothing.
 *
 * And there is a NEGATIVE CONTROL. A tool that is simply broken, or never wired up,
 * also leaves the file uncreated — and would look exactly like a successful veto.
 * (Sage has been burned by precisely this twice: codex's read-only sandbox blocked
 * an edit, and opencode's crashed runs left the file unchanged. A naive check would
 * have recorded a veto in both cases.) So the allowed-path test proves the tool CAN
 * execute and DOES write. Only then does the blocked-path test mean anything.
 */

import type { AgentTool } from "@earendil-works/pi-agent-core";
import { fauxAssistantMessage, fauxToolCall } from "@earendil-works/pi-ai";
import { Type } from "typebox";
import { afterEach, describe, expect, it } from "vitest";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import { createHarness, getAssistantTexts, type Harness } from "../test/suite/harness.ts";
import sageSpike from "./pi-sage-spike.ts";

/** A real write tool: it actually writes, and it tells us it ran. */
function writeTool(ran: { value: boolean }): AgentTool {
	return {
		name: "write",
		label: "Write",
		description: "Write a file",
		parameters: Type.Object({ path: Type.String(), content: Type.String() }),
		execute: async (_toolCallId, params) => {
			const p = params as { path: string; content: string };
			ran.value = true;
			fs.writeFileSync(p.path, p.content);
			return { content: [{ type: "text", text: `wrote ${p.path}` }], details: {} };
		},
	};
}

describe("Sage spike — can a Pi extension enforce?", () => {
	const harnesses: Harness[] = [];
	const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "sage-spike-"));

	afterEach(() => {
		while (harnesses.length > 0) harnesses.pop()?.cleanup();
		delete process.env.SAGE_SPIKE_AUDIT;
		delete process.env.SAGE_EAGER_FILE;
	});

	// ── NEGATIVE CONTROL — the tool must actually work ────────────────────────
	it("CONTROL: an allowed path is written (so an unwritten file MEANS something)", async () => {
		const ran = { value: false };
		const target = path.join(tmp, "allowed.ts");

		const harness = await createHarness({
			tools: [writeTool(ran)],
			extensionFactories: [sageSpike],
		});
		harnesses.push(harness);
		harness.setResponses([
			fauxAssistantMessage([fauxToolCall("write", { path: target, content: "ok" })], {
				stopReason: "toolUse",
			}),
			fauxAssistantMessage("done"),
		]);

		await harness.session.prompt("Create allowed.ts");

		expect(ran.value).toBe(true);
		expect(fs.existsSync(target)).toBe(true);
		expect(fs.readFileSync(target, "utf8")).toBe("ok");
	});

	// ── Q1 — THE VETO ─────────────────────────────────────────────────────────
	it("Q1: BLOCKS a write to *.blocked.* and tells the model why", async () => {
		const ran = { value: false };
		const target = path.join(tmp, "test.blocked.ts");

		const harness = await createHarness({
			tools: [writeTool(ran)],
			extensionFactories: [sageSpike],
		});
		harnesses.push(harness);
		harness.setResponses([
			fauxAssistantMessage([fauxToolCall("write", { path: target, content: "x" })], {
				stopReason: "toolUse",
			}),
			// Echo back whatever the tool result said, so we can prove the MODEL saw it.
			(context) => {
				const tr = context.messages.find((m) => m.role === "toolResult");
				const text =
					tr?.role === "toolResult"
						? tr.content
								.filter((p): p is { type: "text"; text: string } => p.type === "text")
								.map((p) => p.text)
								.join("\n")
						: "";
				return fauxAssistantMessage(text);
			},
		]);

		await harness.session.prompt("Create test.blocked.ts");

		// 1. The tool function was never invoked. A true abort, not a swallowed result.
		expect(ran.value).toBe(false);

		// 2. The file does not exist. §22's success criterion, literally.
		expect(fs.existsSync(target)).toBe(false);

		// 3. The model RECEIVED the denial. A veto it never learns about is a dropped
		//    tool call, and it would loop forever.
		const toolResult = harness.session.messages.find(
			(m) => m.role === "toolResult" && m.isError,
		);
		expect(toolResult).toBeDefined();
		expect(getAssistantTexts(harness).join("\n")).toContain("Sage spike: pre-spec");
	});

	// ── Q2 — context injection ────────────────────────────────────────────────
	it("Q2: the eager core reaches the model's context at session start", async () => {
		const eager = path.join(tmp, "eager.md");
		fs.writeFileSync(eager, "SAGE-EAGER-CORE-MARKER: tests before code.");
		process.env.SAGE_EAGER_FILE = eager;

		let sawEager = false;
		const harness = await createHarness({
			tools: [writeTool({ value: false })],
			extensionFactories: [sageSpike],
		});
		harnesses.push(harness);

		// session_start is emitted inside bindExtensions() (agent-session.ts:2197),
		// which the test harness does not call on its own. print-mode.ts calls it
		// exactly like this. Without it the event never fires, the extension never
		// injects, and the test reports "Pi cannot inject context" when what actually
		// happened is that nothing was ever asked to.
		await harness.session.bindExtensions({ mode: "print" });

		harness.setResponses([
			(context) => {
				sawEager = JSON.stringify(context.messages).includes("SAGE-EAGER-CORE-MARKER");
				return fauxAssistantMessage("ack");
			},
		]);

		await harness.session.prompt("hello");

		expect(sawEager).toBe(true);
	});

	// ── Q3 — post-tool audit ──────────────────────────────────────────────────
	it("Q3: completed tool calls are observable, with name + input + status", async () => {
		const log = path.join(tmp, "audit.log");
		process.env.SAGE_SPIKE_AUDIT = log;
		const target = path.join(tmp, "audited.ts");

		const harness = await createHarness({
			tools: [writeTool({ value: false })],
			extensionFactories: [sageSpike],
		});
		harnesses.push(harness);
		harness.setResponses([
			fauxAssistantMessage([fauxToolCall("write", { path: target, content: "y" })], {
				stopReason: "toolUse",
			}),
			fauxAssistantMessage("done"),
		]);

		await harness.session.prompt("Create audited.ts");

		expect(fs.existsSync(log)).toBe(true);
		const entry = JSON.parse(fs.readFileSync(log, "utf8").trim().split("\n")[0]);
		expect(entry.tool).toBe("write");
		expect(entry.error).toBe(false);
		expect(entry.input.path).toBe(target);
		expect(typeof entry.id).toBe("string");
	});
});
