// Deterministic test of the production opencode adapter — drives its hooks
// directly against the real gate scripts. No opencode model backend needed.
import { SagePlugin } from "./.opencode/plugin/sage.js"
import { writeFileSync, mkdirSync } from "fs"
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

console.log(`\n  adapter: ${pass} pass · ${fail} fail`)
process.exit(fail ? 1 : 0)
