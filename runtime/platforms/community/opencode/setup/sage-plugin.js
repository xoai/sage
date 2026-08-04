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
//
// SCOPE JUDGE (SG-10..SG-19, opt-in via scope_judge: true). tool.execute.after
// additionally drives the shared judge runtime (scope_judge.py hook) and, when
// a drift correction is queued, delivers it by appending to the mutable tool
// result — attested 2026-08-04 (docs/attestations/opencode-context-injection-
// midstream-2026-08-04.md).
// ═══════════════════════════════════════════════════════════════
import { spawnSync } from "child_process"
import { existsSync, readFileSync } from "fs"
import { join } from "path"

// PreToolUse gates, in the order Claude Code runs them. Each is a script under
// .opencode/sage-hooks/ that reads a payload on stdin and exits 0/2.
const PRE_EDIT_GATES = [
  "sage-spec-gate.sh",
  "sage-tdd-gate.sh",
  "sage-bookkeeping-gate.sh",
  "sage-secrets-gate.sh",
  "sage-config-gate.sh",
  "sage-scope-gate.sh",   // SG-6: platform-agnostic script, this adapter's wire
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

// ── Scope judge (SG-10..SG-19) — journal, trigger, deliver ──────────────────
// The judge's brain is runtime/tools/scope_judge.py, shared verbatim with
// Claude Code: it owns the journal schema, cadence, locks, pending-file
// handoff and anti-nag rules. This adapter is only its wire — translate the
// event, pipe it to `scope_judge.py hook`, and deliver any queued correction
// by appending it to the tool result the model reads next ([V-A], attested
// 2026-08-04: tool.execute.after receives the live result object by
// reference, and a string appended to output.output is model-visible).

// The vendored framework first (a user project), then a source checkout —
// the same resolution order as the claude-code hook wrapper.
function judgeTool(root) {
  for (const rel of ["sage/runtime/tools/scope_judge.py",
                     "runtime/tools/scope_judge.py"]) {
    const p = join(root, rel)
    if (existsSync(p)) return p
  }
  return null
}

// Ships false: without an explicit `scope_judge: true` the judge path costs
// one file read per tool call — the same bar as the claude-code wrapper's
// one grep.
function scopeJudgeArmed(root) {
  try {
    return /^[ \t]*scope_judge:[ \t]*true\b/m.test(
      readFileSync(join(root, ".sage", "config.yaml"), "utf8"))
  } catch {
    return false
  }
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

export const SagePlugin = async ({ directory, client }) => {
  const root = directory || process.cwd()
  // Nothing to enforce if this is not a Sage project.
  if (!existsSync(join(root, ".sage"))) return {}

  // [V-B] task-tool subagents run in a CHILD session, and the hook input
  // carries only {tool, sessionID, callID} — the discriminator is the
  // session record's parentID (set only on task-spawned children, verified
  // live on 1.18.12). One client lookup per session, cached; unresolvable
  // reads as not-a-subagent — fail open, the judge is advisory (SG-11).
  const sessionParent = new Map()
  async function parentSession(id) {
    if (!client || !id) return null
    if (sessionParent.has(id)) return sessionParent.get(id)
    let parent = null
    try {
      const r = await client.session.get({ path: { id } })
      parent = (r && r.data && r.data.parentID) || null
    } catch {
      parent = null
    }
    sessionParent.set(id, parent)
    return parent
  }

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

      // Scope judge. Everything of substance — active-cycle resolution,
      // journal line, cadence, background spawn, pending consumption, the
      // SG-17 anti-nag rules, the SG-18 audit line — happens inside
      // `scope_judge.py hook`. SAGE_JUDGE is the SG-12 recursion guard: the
      // judge's own headless session loads this plugin too ([V-C]), and its
      // events must not re-enter judging.
      try {
        if (process.env.SAGE_JUDGE || !scopeJudgeArmed(root)) return
        const tool = judgeTool(root)
        if (!tool) return
        const hookInput = { tool_name: payload.tool_name,
                            tool_input: payload.tool_input, cwd: root }
        const parent = await parentSession(input?.sessionID)
        if (parent) hookInput.parent_session_id = parent   // SG-11 marker
        // CLAUDE_PROJECT_DIR pinned like runGate does: the tool prefers it
        // over the payload's cwd, and a user who exports it for another
        // project must not redirect this project's journal (review catch).
        const r = spawnSync("python3", [tool, "hook"], {
          input: JSON.stringify(hookInput), encoding: "utf8", timeout: 15000,
          env: { ...process.env, SAGE_PLATFORM: "opencode",
                 CLAUDE_PROJECT_DIR: root },
        })
        const text = JSON.parse(r.stdout || "{}")
          ?.hookSpecificOutput?.additionalContext
        if (text && typeof output?.output === "string") {
          // Delivery ([V-A]): the correction rides the result the model is
          // about to read. Registry tools always carry a string here; a
          // non-string result means an unknown shape — drop the delivery
          // rather than corrupt it (advisory, never load-bearing).
          output.output += "\n\n" + text
        }
      } catch {}   // fail open: a broken judge wire never breaks a session
    },
  }
}
