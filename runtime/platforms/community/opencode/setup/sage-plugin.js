// ═══════════════════════════════════════════════════════════════
// sage.js — the Sage enforcement adapter for opencode (production)
//
// Bridges opencode's plugin hooks to Sage's platform-agnostic gate scripts, so
// the same enforcement Claude Code gets from PreToolUse/PostToolUse hooks runs
// on opencode. Attested 2026-07-17 (docs/attestations/opencode-tier-a-*):
// tool.execute.before vetoes, tool.execute.after records, and both fire INSIDE
// dispatched subagents — so a subagent is not an escape hatch.
//
// HOW IT MAPS. opencode names tools and args differently from Claude Code; the
// gates speak Claude Code's payload. This translates:
//   edit/patch/apply_patch → Edit   (file_path, new_string; path parsed from
//                                     apply_patch's patchText, which has no
//                                     filePath field of its own)
//   write                  → Write  (file_path, content)
//   bash                   → Bash   (command)
// and hands each gate {tool_name, tool_input, cwd} on stdin, reading exit 2 as
// a veto (thrown → opencode blocks the call).
//
// FAIL OPEN. A missing gate, a spawn error, an unparseable arg — none of it
// blocks the user. Guards are guards: the cost of a false block is a broken
// session, so every uncertainty resolves to allow. The gates themselves also
// fail open, so this is belt-and-braces.
// ═══════════════════════════════════════════════════════════════
import { spawnSync } from "child_process"
import { existsSync } from "fs"
import { join } from "path"

// PreToolUse gates, in the order Claude Code runs them. Each is a script under
// .opencode/sage-hooks/ that reads a payload on stdin and exits 0/2.
const PRE_EDIT_GATES = [
  "sage-spec-gate.sh",
  "sage-tdd-gate.sh",
  "sage-bookkeeping-gate.sh",
  "sage-secrets-gate.sh",
  "sage-config-gate.sh",
]
const PRE_BASH_GATES = ["sage-verify-gate.sh", "sage-config-gate.sh"]
// PostToolUse recorders — never block; run for their side effects.
const POST_HOOKS = ["sage-verify-tracker.sh", "sage-degradation-log.sh",
                    "sage-manifest-sync.sh"]

// opencode tool + args → the Claude-Code payload the gates read. Returns null
// when the tool is not one the gates care about (→ allow without spawning).
function toPayload(tool, args, root) {
  const t = (tool || "").toLowerCase()
  const a = args || {}
  if (t === "bash" || t === "shell") {
    const command = a.command || a.cmd || a.script || ""
    return { kind: "bash", tool_name: "Bash", tool_input: { command }, cwd: root }
  }
  if (t === "write") {
    return { kind: "edit", tool_name: "Write",
             tool_input: { file_path: a.filePath || a.file_path || a.path || "",
                           content: a.content || a.text || "" }, cwd: root }
  }
  if (t === "edit") {
    return { kind: "edit", tool_name: "Edit",
             tool_input: { file_path: a.filePath || a.file_path || a.path || "",
                           old_string: a.oldString || a.old_string || "",
                           new_string: a.newString || a.new_string ||
                                       a.content || "" }, cwd: root }
  }
  if (t === "patch" || t === "apply_patch" || t === "applypatch") {
    const body = a.patchText || a.patch || a.input || ""
    const m = String(body).match(/^\*\*\* (?:Update|Add|Delete) File: (.+)$/m)
    return { kind: "edit", tool_name: "Edit",
             tool_input: { file_path: m ? m[1].trim() : "", new_string: body },
             cwd: root }
  }
  return null
}

function runGate(root, script, payload) {
  const path = join(root, ".opencode", "sage-hooks", script)
  if (!existsSync(path)) return { ran: false, blocked: false, reason: "" }
  try {
    const r = spawnSync("bash", [path], {
      input: JSON.stringify(payload), encoding: "utf8", timeout: 15000,
      env: { ...process.env, CLAUDE_PROJECT_DIR: root },
    })
    return { ran: true, blocked: r.status === 2, reason: (r.stderr || "").trim() }
  } catch {
    return { ran: false, blocked: false, reason: "" }   // fail open
  }
}

export const SagePlugin = async ({ directory }) => {
  const root = directory || process.cwd()
  // Nothing to enforce if this is not a Sage project.
  if (!existsSync(join(root, ".sage"))) return {}

  return {
    "tool.execute.before": async (input, output) => {
      const payload = toPayload(input?.tool, output?.args, root)
      if (!payload) return
      const gates = payload.kind === "bash" ? PRE_BASH_GATES : PRE_EDIT_GATES
      for (const g of gates) {
        const res = runGate(root, g, payload)
        if (res.blocked) {
          throw new Error(res.reason ||
            `Sage ${g} blocked this ${input?.tool} call.`)
        }
      }
    },
    "tool.execute.after": async (input, output) => {
      // Record for the audit trail / verify-tracker. Non-blocking by contract.
      const t = (input?.tool || "").toLowerCase()
      let payload = toPayload(input?.tool, input?.args, root)
      // Bash "after" needs the command that ran; opencode carries args on input.
      if (!payload && t === "bash") {
        payload = { tool_name: "Bash",
                    tool_input: { command: (input?.args || {}).command || "" },
                    cwd: root }
      }
      if (!payload) return
      for (const h of POST_HOOKS) runGate(root, h, payload)
    },
  }
}
