// Deterministic test of the production opencode adapter — drives its hooks
// directly against the real gate scripts AND the real scope-judge runtime.
// No opencode model backend needed.
//
// Run via develop/validators/platforms/run-opencode-adapter-tests.sh, which
// stages the scratch this expects: .opencode/plugin/sage.js, the gate scripts
// in .opencode/sage-hooks/, the judge at sage/runtime/tools/scope_judge.py,
// and the claude-code journal hook at ./claude-scope-journal.sh (for the
// journal schema parity check).
import { SagePlugin } from "./.opencode/plugin/sage.js"
import { spawnSync } from "child_process"
import { writeFileSync, mkdirSync, readFileSync, existsSync, rmSync } from "fs"
import { join } from "path"

const root = process.cwd()
let pass = 0, fail = 0
const ok = (name, cond) => { cond ? pass++ : fail++; console.log(`  ${cond?"✓":"✗"} ${name}`) }

function setManifest(state) {
  mkdirSync(join(root, ".sage/work/001-demo"), { recursive: true })
  writeFileSync(join(root, ".sage/work/001-demo/manifest.md"),
    `---\ncycle_id: "001-demo"\ngate_state: ${state}\nstatus: in-progress\n---\n# demo\n`)
}
function setConfig(enforce) {
  writeFileSync(join(root, ".sage/config.yaml"),
    `sage-version: "1.3.8"\nhard_enforcement: ${enforce}\n`)
}
async function threw(hooks, tool, args) {
  try { await hooks["tool.execute.before"]({ tool }, { args }); return false }
  catch { return true }
}

const hooks = await SagePlugin({ directory: root })

// 1. pre-spec source edit → VETO
setConfig("true"); setManifest("pre-spec")
ok("pre-spec source edit is VETOED",
   await threw(hooks, "edit", { filePath: join(root, "src/calc.py"),
     oldString: "def add", newString: "def add\ndef multiply(a,b): return a*b" }))

// 2. spec-approved → allowed
setManifest("spec-approved")
ok("spec-approved source edit is ALLOWED",
   !(await threw(hooks, "edit", { filePath: join(root, "src/calc.py"),
     newString: "def multiply(a,b): return a*b" })))

// 3. config self-disable → VETO (the meta-gate, through the adapter)
setManifest("spec-approved")
ok("flipping hard_enforcement off is VETOED",
   await threw(hooks, "edit", { filePath: join(root, ".sage/config.yaml"),
     oldString: "hard_enforcement: true", newString: "hard_enforcement: false" }))

// 4. hardcoded secret → VETO
setManifest("spec-approved")
ok("a hardcoded live key is VETOED",
   await threw(hooks, "write", { filePath: join(root, "src/keys.py"),
     content: 'API = "payco_live_4eC39HqLyjWDarjtT"' }))

// 5. a plain read → never gated
ok("a read is never gated",
   !(await threw(hooks, "read", { filePath: join(root, "src/calc.py") })))

// ═══ Scope judge wire (SG-10/11/16/17/18 through the adapter) ═══════════════
// The judge runtime is the shared scope_judge.py; these tests pin the
// adapter's side of the contract: journal capture, the sub flag, single
// consumption of a queued correction into the mutated tool result, the
// SAGE_JUDGE recursion guard, and the off-by-default gate.

const cycle = join(root, ".sage/work/001-demo")
const journal = join(cycle, "scope-journal.jsonl")
const pending = join(cycle, ".scope-correction.json")

function armJudge(on = true) {
  writeFileSync(join(root, ".sage/config.yaml"),
    `sage-version: "1.3.11"\nhard_enforcement: true\n` +
    `scope_judge: ${on}\njudge_every: 99\n`)
}
function resetScope() {
  for (const f of ["scope-journal.jsonl", "scope-journal.jsonl.1",
                   ".scope-correction.json", ".scope-inject-state.json",
                   ".judge.spawned", ".judge.lock", "decisions.md"])
    rmSync(join(cycle, f), { force: true })
  writeFileSync(join(cycle, "plan.md"),
    "# Plan\n\n- [ ] **Task 1:** wire the adapter\n  - **Files:** src/calc.py\n")
}
async function after(hs, input, output) {
  await hs["tool.execute.after"](input, output ?? { title: "", output: "x\n", metadata: {} })
}
const bashEvent = (cmd, sessionID = "s-main") =>
  ({ tool: "bash", sessionID, callID: "c1", args: { command: cmd } })
const journalRows = () => existsSync(journal)
  ? readFileSync(journal, "utf8").trim().split("\n").map(l => JSON.parse(l))
  : []

// 6. armed + active cycle → one journal line per event, SG-10 schema
armJudge(); setManifest("building"); resetScope()
await after(hooks, bashEvent("echo hi"))
await after(hooks, { tool: "edit", sessionID: "s-main", callID: "c2",
                     args: { filePath: join(root, "src/calc.py"), newString: "x" } })
{
  const rows = journalRows()
  ok("journal captures Bash and Edit with the SG-10 schema",
     rows.length === 2
     && rows[0].type === "event" && rows[0].tool === "Bash"
     && rows[0].cmd === "echo hi" && typeof rows[0].ts === "number"
     && rows[1].tool === "Edit" && rows[1].path === join(root, "src/calc.py")
     && rows[0].task_hint === "T1" && !rows[0].sub)
}

// 7. child session ([V-B]: session record carries parentID) → sub: true,
//    and a queued correction is NEVER delivered to a subagent (SG-11)
resetScope()
const subHooks = await SagePlugin({ directory: root, client: {
  session: { get: async ({ path: p }) =>
    ({ data: { id: p.id, parentID: p.id === "s-child" ? "s-main" : undefined } }) },
} })
writeFileSync(pending, JSON.stringify({ task: "T1", task_label: 'T1 "wire"',
  reason: "planted", evidence: "e1", at_event: 1 }))
{
  const out = { title: "", output: "x\n", metadata: {} }
  await after(subHooks, bashEvent("echo sub", "s-child"), out)
  const rows = journalRows()
  ok("a child-session event is journaled sub: true and never corrected",
     rows.length === 1 && rows[0].sub === true
     && !out.output.includes("Sage scope-judge:") && existsSync(pending))
  rmSync(pending, { force: true })
}

// 8. queued correction → delivered ONCE into the mutated tool result ([V-A]),
//    consumed, audited (SG-18), and not repeated (SG-17)
resetScope()
writeFileSync(pending, JSON.stringify({ task: "T1", task_label: 'T1 "wire the adapter"',
  reason: "off-task refactor", evidence: "e1", at_event: 1 }))
{
  const out1 = { title: "", output: "probe-1\n", metadata: {} }
  await after(hooks, bashEvent("echo one"), out1)
  const delivered = out1.output.includes("Sage scope-judge:")
                 && out1.output.includes("off-task refactor")
                 && out1.output.startsWith("probe-1\n")
  const consumed = !existsSync(pending)
  const audited = existsSync(join(cycle, "decisions.md"))
    && readFileSync(join(cycle, "decisions.md"), "utf8")
         .includes("scope correction injected")
  const out2 = { title: "", output: "probe-2\n", metadata: {} }
  await after(hooks, bashEvent("echo two"), out2)
  ok("a queued correction is delivered once, consumed, and audited",
     delivered && consumed && audited
     && !out2.output.includes("Sage scope-judge:"))
}

// 9. no active cycle → no journal, immediate no-op
armJudge()
writeFileSync(join(root, ".sage/work/001-demo/manifest.md"),
  `---\ncycle_id: "001-demo"\ngate_state: building\nstatus: complete\n---\n# demo\n`)
rmSync(journal, { force: true })
await after(hooks, bashEvent("echo idle"))
ok("no active cycle → nothing journaled", !existsSync(journal))
setManifest("building")

// 10. SAGE_JUDGE in the environment → the judge wire no-ops (SG-12 across
//     the adapter's process boundary: the judge's own session is inert)
resetScope()
process.env.SAGE_JUDGE = "1"
await after(hooks, bashEvent("echo recurse"))
delete process.env.SAGE_JUDGE
ok("SAGE_JUDGE=1 → the adapter's judge path no-ops", !existsSync(journal))

// 11. scope_judge: false (the shipped default) → inert
armJudge(false); resetScope()
await after(hooks, bashEvent("echo off"))
ok("scope_judge: false → nothing journaled", !existsSync(journal))

// 12. journal schema parity: the same event through the claude-code hook
//     wrapper and through this adapter produces the same row (modulo ts) —
//     one writer (scope_judge.py), two wires, one parser.
armJudge(); resetScope()
{
  const ccHook = join(root, "claude-scope-journal.sh")
  const payload = { tool_name: "Edit",
                    tool_input: { file_path: "src/calc.py" }, cwd: root }
  spawnSync("bash", [ccHook], {
    input: JSON.stringify(payload), encoding: "utf8",
    env: { ...process.env, CLAUDE_PROJECT_DIR: root,
           SAGE_SCOPE_JUDGE_TOOL: join(root, "sage/runtime/tools/scope_judge.py") },
  })
  const ccRow = journalRows()[0]
  rmSync(journal, { force: true })
  await after(hooks, { tool: "edit", sessionID: "s-main", callID: "c9",
                       args: { filePath: "src/calc.py", newString: "y" } })
  const ocRow = journalRows()[0]
  const strip = r => { const { ts, ...rest } = r || {}; return JSON.stringify(rest) }
  ok("journal rows are byte-compatible with the claude-code hook's",
     ccRow && ocRow && strip(ccRow) === strip(ocRow))
}

console.log(`\n  adapter: ${pass} pass · ${fail} fail`)
process.exit(fail ? 1 : 0)
