/**
 * pi-sage-spike.ts — throwaway PoC for the Phase-1 Pi spike (10-spec §21 R81).
 *
 * Q1 (decisive) — can an extension PREVENT a built-in tool call, with a denial
 *                 reason delivered back to the model in-session?
 * Q2            — can an extension inject Sage's eager core at session start?
 * Q3            — can an extension observe completed tool calls well enough to
 *                 implement the degradation log?
 *
 * Paths come from env so the proof can point them at a temp dir.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "../src/index.ts";

/** The one file the spike refuses to let the model create. */
const BLOCKED = /\.blocked\./;

export default function sageSpike(pi: ExtensionAPI): void {
	// ── Q2: context injection at session start ──────────────────────────────
	// A custom message is converted to role:"user" on its way into the LLM
	// context (core/messages.ts), so this provably reaches the model. Contrast
	// pi.appendEntry(), which renders in the UI and is NOT sent to the model.
	pi.on("session_start", async () => {
		const file = process.env.SAGE_EAGER_FILE;
		if (!file || !fs.existsSync(file)) return;
		pi.sendMessage(
			{
				customType: "sage-eager-core",
				content: fs.readFileSync(file, "utf8"),
				display: "Sage: constitution + dispatcher loaded",
			},
			{ deliverAs: "nextTurn" },
		);
	});

	// ── Q1: THE VETO ────────────────────────────────────────────────────────
	// Returned decision object — not a throw, not a mutated call.
	pi.on("tool_call", async (event) => {
		const target = filePathOf(event.toolName, event.input);
		if (!target || !BLOCKED.test(target)) return;
		return {
			block: true,
			reason:
				`Sage spike: pre-spec. \`${path.basename(target)}\` matches a blocked ` +
				`pattern, so this write was refused before it ran. Write the spec first.`,
		};
	});

	// ── Q3: post-tool observation (the degradation log) ─────────────────────
	pi.on("tool_result", async (event) => {
		const log = process.env.SAGE_SPIKE_AUDIT;
		if (!log) return;
		fs.appendFileSync(
			log,
			JSON.stringify({
				tool: event.toolName,
				id: event.toolCallId,
				error: event.isError,
				input: event.input,
			}) + "\n",
		);
	});
}

/** The path a write/edit tool is about to touch, or null. */
function filePathOf(toolName: string, input: Record<string, unknown>): string | null {
	if (toolName !== "write" && toolName !== "edit") return null;
	const p = input.path ?? input.file_path ?? input.filePath;
	return typeof p === "string" ? p : null;
}
