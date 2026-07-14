# Pi spike — verdict

**Question:** can Sage's mechanism layer exist on Pi, or only its prose?
**Answer:** it can. **Recommendation: GO.** Q1, Q2 and Q3 were **executed** against
Pi and all three pass. The transcript is committed.

| | |
|---|---|
| Pi at | `earendil-works/pi` @ `8479bd8`, `@earendil-works/pi-coding-agent` **0.80.6** |
| Spike ran | 2026-07-12 |
| Elapsed | ~1 day of the 2-day box (10-spec §22) |
| Derived tier | **B** (`contract.py derive_tier`: veto + context-injection, no subagent chain) |
| Port estimate | **2–3 person-weeks** — inside ADR-12's ≤3-week GO bar |
| Proof | `spike-artifacts/pi-veto-transcript.txt` — 4/4 pass, offline, zero spend |
| Port code landed | **none**, per ADR-12 and R84. This document and `spike-artifacts/` are the deliverable. |

---

## The proof

```
✓ CONTROL: an allowed path is written (so an unwritten file MEANS something)
✓ Q1: BLOCKS a write to *.blocked.* and tells the model why
✓ Q2: the eager core reaches the model's context at session start
✓ Q3: completed tool calls are observable, with name + input + status

Test Files  1 passed (1)      Tests  4 passed (4)      Duration 2.38s
```

No network. No API key. **Zero spend** — Pi ships a faux model provider whose base URL is
`http://localhost:0` and is never dialed, so the model's turns are scripted and the
whole thing runs offline in two seconds.

**Two guards, because a green test is not evidence until it can go red.**

1. **A negative control.** A tool that is broken, or never wired up, ALSO leaves the
   file uncreated — and would look exactly like a successful veto. So the control
   test writes to an *allowed* path and asserts the file appears. Only once the tool
   is proven capable of writing does its failure to write mean anything.

   This is not paranoia; it is scar tissue. Twice this project has been within one
   commit of recording a veto that never happened: codex's read-only sandbox blocked
   an edit, and opencode's crashed runs left the file unchanged. **Nothing-happened
   and correctly-blocked are indistinguishable unless you make the mechanism prove
   itself.**

2. **A mutation check.** Change the extension's `{block: true}` to `{block: false}`
   and re-run:

   ```
   FAIL  Q1: BLOCKS a write to *.blocked.*
   AssertionError: expected true to be false
   ```

   With the veto disabled the tool **executes and writes the file**. The veto is what
   stops it. The test is not vacuous.

---

## Q1 — Veto. **YES — executed.**

An extension can intercept `edit` / `write` / `bash`, **prevent execution**, and
deliver a denial reason back to the model in-session.

**Mechanics: a returned decision object.** Not a thrown error, not a mutated call.
The `tool_call` event fires before execution and the handler returns
`ToolCallEventResult` — `packages/coding-agent/src/core/extensions/types.ts:1055`:

```ts
export interface ToolCallEventResult {
    /** Block tool execution. To modify arguments, mutate `event.input` in place instead. */
    block?: boolean;
    reason?: string;
}
```

**The return value is genuinely consumed.** This is the part that matters, and it
is the part a type declaration alone cannot tell you — a handler whose return value
is collected and dropped would look identical at the type level. Three hops:

1. `extensions/runner.ts:881-902` — `emitToolCall()` walks handlers and
   short-circuits on the first `result.block`. (Note: unlike every sibling emitter,
   it has no `try/catch` — exceptions propagate rather than being swallowed.)
2. `core/agent-session.ts:424-443` — wires that into agent-core's `beforeToolCall`.
3. **`packages/agent/src/agent-loop.ts:621-645`** — the call site that aborts:

```ts
if (beforeResult?.block) {
    return {
        kind: "immediate",
        result: createErrorToolResult(beforeResult.reason || "Tool execution was blocked"),
        isError: true,
    };
}
```

Only `kind: "prepared"` reaches `executePreparedToolCall()`, which is the **sole
caller of `tool.execute`** (`agent-loop.ts:677`). So the tool function is never
invoked. This is a true abort, not a suppressed result.

**And the model is told.** `createErrorToolResult` becomes a `ToolResultMessage`
addressed to the exact `toolCallId` the model requested (`agent-loop.ts:757-787`),
pushed into `messages` and sent on the next provider call. The model sees the
denial as an errored tool result and can react — which is Sage's hook contract
exactly, and is what separates a veto from a dropped call that would loop forever.

**Prior art — four shipped extensions deny, and one vendor test proves it.**

- `examples/extensions/protected-paths.ts:13-26` — `return { block: true, reason: ... }` on `write`/`edit` by path.
- `examples/extensions/permission-gate.ts:19-30` — blocks dangerous `bash`; blocks unconditionally when headless.
- `examples/extensions/plan-mode/index.ts:163-175` — read-only mode with an allowlist and a model-facing reason.
- **`test/suite/agent-session-model-extension.test.ts:117-160`** — *"allows extension tool_call handlers to block tool execution"*. The tool's `execute` is `async () => { throw new Error("tool should have been blocked"); }`. It never fires, and the test asserts the model receives the reason.

Pi's own suite asserts this too, which is how the spike knew where to look. But the
transcript above is Sage's extension, blocking Sage's pattern, with Sage's reason
reaching the model — run here, not read about.

## Q2 — Context injection. **YES — executed.** Two mechanisms, and one trap that cost an hour.

The eager core can be delivered at session start, equivalent to Claude Code's
SessionStart `additionalContext`:

- **`pi.sendMessage(...,{deliverAs:"nextTurn"})`** (`types.ts:1265`) — *"queued for
  next user prompt; does not interrupt or trigger anything"* (`docs/extensions.md:1398`).
  It provably reaches the model: a custom message is converted to `role:"user"` in
  `core/messages.ts:148-168`.
- **`before_agent_start` → `{ systemPrompt }`** (`types.ts:1080`) — replaces or
  chains the system prompt for the turn; consumed at `agent-session.ts:1184-1211`.

The proof asserts the injected marker is **actually present in the messages the model
received** — not that the extension called `sendMessage` and felt good about it.

**Two traps, and the second one is the reason this section is worth reading.**

1. `pi.appendEntry()` (`types.ts:1281`) renders in the UI and is explicitly **not**
   sent to the model. A port that reached for it would inject nothing, silently.

2. **`session_start` does not fire until `bindExtensions()` is called.** It is
   emitted at `agent-session.ts:2197`, *inside* `bindExtensions()` — and Pi's own
   test harness never calls it. So the first run of the Q2 proof **failed**, and the
   failure said, in effect, *"Pi cannot inject context at session start."*

   It says nothing of the sort. Nothing had ever asked it to. `print-mode.ts:73`
   calls `session.bindExtensions({mode})` before driving a turn; once the proof did
   the same, Q2 passed.

   **That is the whole lesson of this spike in miniature.** A Sage-on-Pi port that
   forgets `bindExtensions()` will inject nothing, report no error, and look exactly
   like a correctly-installed Sage — right up until an agent skips a test and nobody
   can explain why the constitution did not stop it. An hour was spent on it here, in
   a spike, where it was cheap. It is written down so it is never spent again.

## Q3 — Post-tool observation. **YES — executed.**

`tool_result` (`types.ts:900-906`) carries `toolName`, `input`, `content`,
`isError`, and a correlating `toolCallId` — everything the degradation log needs.
`tool_execution_end` is the lighter alternative but drops `input`, which is the
field that makes an audit line worth writing.

One caveat for the port: in parallel tool mode these may interleave in *completion*
order (`docs/extensions.md:822`), so the log must key on `toolCallId` and never
trust arrival order.

## Q4 — Skill delivery. **YES — and workflows do not have to become skills.**

Pi reads `package.json` → `"pi": { "skills": [...] }` (`core/package-manager.ts:158`,
consumed `:2100`), with glob and `!exclusion` support, plus convention-directory
auto-discovery (`skills/`, `extensions/`, `prompts/`). Skills are injected into the
system prompt as `<available_skills>` per the agentskills.io spec
(`core/skills.ts:335`) — descriptions always in context, body loaded on demand.
That is the same contract ADR-9 built Sage's native skills against, so **class-2
content ships as-is.**

For workflow payloads there are three invocation routes
(`core/slash-commands.ts:4` — `SlashCommandSource = "extension" | "prompt" | "skill"`):
**prompt templates** (plain `.md` with frontmatter, `/name` invokes it — the
natural home for Sage's workflows, zero code), `/skill:name`, and
`pi.registerCommand()` for anything needing logic. Sage's workflows do not have to
be contorted into skills.

## Q5 — State access. **YES. No sandbox.**

Extensions are in-process TypeScript loaded via jiti (`extensions/loader.ts:389`),
with node builtins available (`docs/extensions.md:155`) and, in the docs' own words,
*"full system permissions"* (`:112`). A shipped example does synchronous `fs`
reads (`examples/extensions/claude-rules.ts:20-34`). Reading
`.sage/work/*/manifest.md` synchronously, inside a gate, on every tool call, is a
non-issue. I grepped `loader.ts` for `vm.`, `isolate`, `sandbox`, `worker_threads`:
zero hits.

Project-local `.pi/extensions` load only after the project is trusted
(`docs/extensions.md:113`) — worth knowing, not a blocker.

## Q6 — Effort. **2–3 person-weeks for a Tier-B port.**

The estimate is low for one reason: **the gates do not need rewriting.** Sage's
gates are bash scripts that read a JSON payload on stdin and exit 0 or 2 with a
reason on stderr. Pi's extension is TypeScript that returns `{block, reason}`. The
port is a thin adapter — translate `ToolCallEvent` into the hook payload shape,
`pi.exec` the existing gate, map exit 2 + stderr onto `{block: true, reason}`.

This is the same shape the codex investigation found (Sage's *unmodified*
`sage-spec-gate.sh` already exits 2 on a codex-shaped payload), and it is the
architecture that avoids the mistake this project has already made once: **the
navigator was a second copy of the eager layer, and it drifted.** One gate
implementation, many adapters. Never two.

| Work | Days |
|---|---|
| Tool-call adapter: payload mapping, exit-code → `{block, reason}`, spec-gate + tdd-gate wired | 3 |
| Eager-core injection (`sendMessage`/`before_agent_start`) + native-skill packaging via `pi.skills` | 2 |
| Degradation log on `tool_result` (keyed by `toolCallId`) | 1 |
| Context-budget instrumentation | 1 |
| Offline regression suite on the faux provider + CI job | 2 |
| npm packaging, `porting-sage.md` row, docs | 2 |
| Buffer for 0.x churn (see risks) | 2 |
| **Total** | **~13 working days ≈ 2.5 weeks** |

**Test strategy is the pleasant surprise.** Pi ships a **faux model provider**
(`packages/ai/src/providers/faux.ts`, publicly re-exported) that scripts the
model's turns with no network and no API key — its `DEFAULT_BASE_URL` is
`http://localhost:0` and is never dialed. Every capability above is verifiable
**offline, deterministically, for nothing**, and Pi's own suite harness
(`test/suite/harness.ts`) is built entirely from publicly exported constructors, so
Sage can reuse the pattern against published npm packages rather than a fork.

A Sage-on-Pi veto regression test in CI costs seconds and nothing. Given the risk
below, it is not optional.

---

## Risks

### Pi's API churn is the dominant risk, and it is structural

There is effectively **no stability policy.**

- **Version 0.80.6** — pre-1.0.
- **`AGENTS.md:22`, a project rule, verbatim:** *"Do not preserve backward
  compatibility unless the user asks for it."*
- **`AGENTS.md:122`: semver is inverted.** *"Lockstep versioning... `patch` = fixes
  + additions, `minor` = breaking changes. No major releases."* A `0.80.x → 0.81.0`
  bump is **where breaking changes land**. `^0.80.0` is not a range, it is a bet.
  **Pin exact.**
- The `coding-agent` CHANGELOG carries **40 separate `### Breaking Changes`
  sections**. Extension-facing breaks are routine: `ToolDefinition.execute`
  parameter reorder (`:2503`), `createAgentSession({tools})` changing from `Tool[]`
  to `string[]` (`:1158`), removal of `session_switch`/`session_fork` events
  (`:1450`), stale-session invalidation after `fork` (`:1108`).
- The project has changed npm scope and GitHub org at least twice.

**Maintenance cost, stated plainly.** A Sage-on-Pi port is not a 2.5-week
expenditure. It is 2.5 weeks plus a standing tax of **roughly a day per Pi minor
release**, indefinitely, to re-verify and repair the seam. Anyone approving the
port is approving the tax. If nobody owns that tax, the port will rot exactly the
way the navigator rotted — quietly, in public, for two releases.

### The one mitigating signal, and it is specific

The capability Sage actually depends on — `{block, reason}` on `tool_call` — sits
on the **most-exercised, best-documented, most-tested seam in the extension API**,
and it has been *hardened*, not churned. Every changelog hit is additive:
`ToolCallEventResult` added to public exports (`:1705`), input mutation documented
with regression coverage (`:1584`), the interception re-platformed onto agent-core's
`beforeToolCall` while **explicitly preserving** sequential preflight (`:1884`).
Blocking has existed since the earliest hook docs (`:4536` — *"tool_call (can
block)"*). **No breaking change has ever altered `{block, reason}`.**

So: the load-bearing beam is the sturdiest thing in the house. The floorboards
around it move every minor. Keep the extension thin, pin exact, and let the free
regression test tell you the morning a bump breaks something.

### Tier B is a ceiling, not a failure

ADR-12 predicted this and it holds: Pi has no built-in subagent dispatch — session
`fork`/`newSession` exist on `ExtensionCommandContext` (`types.ts:341`) and could
plausibly be orchestrated into something like it, but that is a **different shape**
from a model-dispatched Task tool and it is **not proven**. So `subagent-dispatch:
false`, and `derive_tier` returns **B** (veto + context-injection). Sage's quality
chain — implementer and independent reviewer in separate fresh contexts — does not
come along. The enforcement spine does.

---

## Recommendation

**GO** for a program-3 Pi port, at Tier B, with these conditions:

1. **The contract row is now earned, and only when the platform exists.** Q1's proof
   ran; `pre-tool-veto: true` is a claim Pi can now support. But Sage has no Pi
   platform — creating one is a PORT, and ADR-12 forbids port code in this program
   either way. So the row lands in program 3, *with* the regression test, and not
   before. The capability is proven; the platform is not yet built.

   Note what this is **not**: it is not codex's situation. Codex's `pre-tool-veto`
   stays `false` because no session ever honoured its documented hook contract. Pi's
   is `true`-able because a session did, and the transcript is committed. Same rule,
   different evidence.

2. **Someone owns the churn tax** — a day per Pi minor, or the port rots.
3. **The gates are not rewritten.** One implementation, many adapters. The port is
   an adapter, and if it ever starts being a second copy of the gate logic, stop.
4. **The regression test lands WITH the port, not after it.** It is free, it runs
   offline in two seconds, and given Pi's inverted semver it is the only thing that
   will catch a breaking minor before a user does. It has already earned its keep
   once: it is what caught the `bindExtensions()` trap.

## Open / not answered

- **Whether `fork`/`newSession` can be orchestrated into a real subagent chain** —
  out of the box's scope, and Tier B does not depend on it. If someone wants Tier A
  on Pi, that is the question to spike next.
- **`bash` tool payload shape** — the proof exercised `write`; `write`/`edit` carry a
  path in `event.input`. I did not enumerate the `bash` payload's exact fields, which
  the adapter will need for the tdd-gate. Ten minutes with `types.ts`, not a risk.
- **The real gate scripts were not run through the adapter.** The spike blocked on a
  filename pattern, not by shelling out to `sage-spec-gate.sh`. The exit-2 → `{block,
  reason}` mapping is a five-line function and the codex investigation already proved
  Sage's unmodified gate exits 2 on a foreign payload — but it has not been wired end
  to end, and that is the first thing the port should do.
