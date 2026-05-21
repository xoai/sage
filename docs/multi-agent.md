# Sage Multi-Agent — Comprehensive Guide

A complete reference for Sage's optional **cross-model build cycle**:
what it is, how to install it, how to use it day-to-day, how to
customize it, and how to debug when something goes wrong.

If you're skimming, the [Quickstart](#quickstart) is enough to install
and run your first cycle. The rest is for when you want to tune the
loop, add a new agent, swap models, or understand what the framework
is doing under the hood.

> **Status:** v1.1.6, Claude Code only.
> **Required:** Sage v1.1.6+, Python 3.11+, the CLIs for whichever
> roles you bind (default: Codex CLI + Kimi CLI).

---

## Table of contents

1. [Why multi-agent](#1-why-multi-agent)
2. [The cycle in one picture](#2-the-cycle-in-one-picture)
3. [Quickstart](#3-quickstart)
4. [Prerequisites](#4-prerequisites)
5. [Installation](#5-installation)
6. [Configuration — `agents.toml` deep dive](#6-configuration--agentstoml-deep-dive)
7. [Daily use — the slash commands](#7-daily-use--the-slash-commands)
8. [The `/build-x` cycle, phase by phase](#8-the-build-x-cycle-phase-by-phase)
9. [Customization](#9-customization)
10. [File layout — framework- vs user-owned](#10-file-layout--framework--vs-user-owned)
11. [Upgrades — `sage update` behavior](#11-upgrades--sage-update-behavior)
12. [Uninstall](#12-uninstall)
13. [Reviewer output contract](#13-reviewer-output-contract)
14. [Cost, latency, and capacity](#14-cost-latency-and-capacity)
15. [Security model](#15-security-model)
16. [Troubleshooting](#16-troubleshooting)
17. [Migrating from the standalone prototype](#17-migrating-from-the-standalone-prototype)
18. [FAQ](#18-faq)

---

## 1. Why multi-agent

Sage's standard `/build` cycle runs entirely inside one model session.
That model both plans and writes the code, then reviews its own diff.
This is fast, but it has known failure modes:

- **The planner rationalises gaps.** "The conversation is the spec" is
  the classic LLM-planner failure. The spec.md never quite catches up
  to what was discussed.
- **The implementer drifts.** Without an outside pair of eyes, small
  shortcuts compound into spec misalignment that only surfaces in
  review — by which point the diff is large and reviewers are tired.
- **Self-review systematically misses what self-bias hides.** A model
  reviewing its own output approves at materially higher rates than an
  independent reviewer on the same artefact.

The multi-agent cycle addresses all three by binding *different models*
to the planner, reviewer, and implementer roles, and forcing all
hand-offs through **files on disk** (no shared session memory). The
host model (Claude Code, Opus) keeps the planner role and stays the
only interface you interact with; external CLIs handle review and
implementation.

When to use it:

- Non-trivial work (multi-file, security-adjacent, migration-shaped)
  where reviewer disagreement materially changes your mind.
- Work where a tight spec matters — adversarial spec review catches
  ambiguities the planner glossed over.
- When you want a *deliberate*, paper-trail-heavy loop: every reviewer
  pass is timestamped and saved.

When *not* to use it:

- Trivial work — a one-line config tweak, a typo fix, a rename sweep.
  The overhead (multiple external CLI calls per cycle) isn't worth it.
- Exploratory spikes where you're still figuring out what to build.
  Use `/research` or `/architect` first.

---

## 2. The cycle in one picture

```
┌──────────────────────── Claude Code (host) ────────────────────────┐
│                                                                    │
│   /build-x  ──────►  planner (Opus)                                │
│                          │                                         │
│                          ▼                                         │
│                      brief.md                                      │
│                          │                                         │
│       (optional)   ┌─────┴──────┐                                  │
│                    │            │                                  │
│                /architect    /research    /design                  │
│                    │            │            │                     │
│                    └─────┬──────┘            │                     │
│                          ▼                                         │
│                       spec.md                                      │
│                          │                                         │
│                          ▼                                         │
│       ┌──────────────────┴──────────────────┐                      │
│       │  Phase 3 — external spec review     │  ◄── Codex CLI       │
│       │  (loop up to 3, BLOCKER/MAJOR)      │      (read-only)     │
│       └──────────────────┬──────────────────┘                      │
│                          ▼                                         │
│                       plan.md                                      │
│                          │                                         │
│                          ▼                                         │
│       ┌──────────────────┴──────────────────┐                      │
│       │  Phase 5 — external plan review     │  ◄── Codex CLI       │
│       │  (loop up to 2, SCOPE_DRIFT)        │      (read-only)     │
│       └──────────────────┬──────────────────┘                      │
│                          ▼                                         │
│       ┌──────────────────┴──────────────────┐                      │
│       │  Phase 6 — external implement       │  ◄── Kimi CLI        │
│       │  (writes diff + implementer-notes)  │      (--yolo)        │
│       └──────────────────┬──────────────────┘                      │
│                          ▼                                         │
│       ┌──────────────────┴──────────────────┐                      │
│       │  Phase 7 — external code review     │  ◄── Codex CLI       │
│       │  (loops until APPROVE or escalate)  │      (read-only)     │
│       └──────────────────┬──────────────────┘                      │
│                          ▼                                         │
│                      /reflect                                      │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

All hand-offs are files under `.sage/work/<slug>/`. No agent reads any
other agent's session memory. The host orchestrates; you stay in
Claude Code the whole time.

---

## 3. Quickstart

```bash
# 1. Make sure you're in a Sage-initialized project on the claude-code platform.
cd my-project
sage init                           # if not already initialized

# 2. Install the multi-agent capability.
sage setup multi-agent              # adds 5 slash commands, ~16 files

# 3. (One-time) install the external CLIs you bound. Defaults:
#    - codex (OpenAI): https://github.com/openai/codex
#    - kimi  (Moonshot): https://github.com/MoonshotAI/Kimi-CLI
#    Both need their respective API keys in your environment.

# 4. Open the project in Claude Code, then run the augmented cycle:
#    /build-x  add a retry-with-exponential-backoff helper

# 5. (When you're done) uninstall, leaving no trace except your work tree:
sage setup multi-agent --remove
```

That's the whole loop. Read on if you want to swap models, tune prompts,
or understand why something behaved a particular way.

---

## 4. Prerequisites

### Hard requirements (install blocks if missing)

| Requirement                    | Why                                                         |
|--------------------------------|-------------------------------------------------------------|
| Sage v1.1.6+                   | The `sage setup multi-agent` subcommand exists from 1.1.6.  |
| Python 3.11+ on `PATH`         | The dispatcher uses `tomllib` (stdlib from 3.11).           |
| `.sage/` initialized           | Run `sage init` first if absent.                            |
| `claude-code` in `platforms:`  | The slash commands and sub-agents are Claude Code shaped.   |

### Soft requirements (install warns; you can defer)

| Requirement   | Default role bound to it       | Where to get it                              |
|---------------|--------------------------------|----------------------------------------------|
| `codex` CLI   | `spec_reviewer`, `code_reviewer` | OpenAI Codex CLI (gpt-5-codex)             |
| `kimi`  CLI   | `implementer`                  | Moonshot Kimi CLI                            |

You don't *have* to use those defaults. Edit `.sage/agents.toml` after
install to bind any role to any CLI you have working — see
[Section 6](#6-configuration--agentstoml-deep-dive).

### Platform scope

**Claude Code only in v1.** The slash commands, sub-agent isolation
pattern, and `Bash(...)` permission patterns assume Claude Code
primitives. Antigravity, Codex-as-host, Opencode, and Gemini CLI are
explicit non-goals for v1.

If you've installed Sage on multiple platforms in the same project
(e.g., `claude-code` + `antigravity`), multi-agent only wires into
`.claude/` — the other platforms continue to use `/build` only.

---

## 5. Installation

### Step 1: install

```bash
cd my-project
sage setup multi-agent
```

You'll see a pre-flight check, then a confirmation prompt listing what
will be installed:

```
  Sage — Setup Multi-Agent

  Pre-flight checks
  ✓ .sage/ exists
  ✓ Python 3.12 (≥3.11)
  ✓ claude-code platform configured
  ✓ codex CLI on PATH
  ⚠ kimi CLI not on PATH (install before first /build-x)

  This will install (sage v1.1.6):

  ↻ .sage/agents.toml            (yours — edit freely)
  ↻ .sage/prompts/_shared.md     (yours — edit freely)
  ↻ .sage/prompts/planner.md     (yours — edit freely)
  ↻ .sage/prompts/spec_reviewer.md  (yours — edit freely)
  ↻ .sage/prompts/implementer.md (yours — edit freely)
  ↻ .sage/prompts/code_reviewer.md  (yours — edit freely)
  ↻ .sage/scripts/run-role.sh    (framework — refreshed by sage update)
  ↻ .sage/scripts/validate-review.sh  (framework)
  ↻ .sage/docs/multi-agent.md    (framework)
  ↻ .claude/commands/build-x.md  (framework)
  ↻ .claude/commands/review-spec.md  (framework)
  ↻ .claude/commands/review-plan.md  (framework)
  ↻ .claude/commands/implement.md    (framework)
  ↻ .claude/commands/review-code.md  (framework)
  ↻ .claude/agents/codex-reviewer.md (framework)
  ↻ .claude/agents/kimi-implementer.md  (framework)
  ↻ .claude/settings.json        (merged, not overwritten)
  ↻ .sage/config.yaml            (multi_agent block added)
  ↻ CLAUDE.md                    (multi-agent section appended)

  [A] Proceed  |  [C] Cancel:
```

Type `A` (or just Enter — `A` is the default). For unattended runs:

```bash
sage setup multi-agent --yes
```

### Step 2: verify

```bash
sage setup multi-agent --status
# → multi-agent: enabled=true version=1.1.6
```

### Step 3: install the external CLIs (if not already done)

If pre-flight warned about a missing CLI, install it now. The defaults:

```bash
# Codex CLI (OpenAI gpt-5-codex)
npm install -g @openai/codex          # or whatever the install path is
export OPENAI_API_KEY=...

# Kimi CLI (Moonshot)
# Follow the upstream install instructions.
export MOONSHOT_API_KEY=...
```

Then verify:

```bash
codex --version
kimi  --version
```

If you bind different agents, install those instead. The pre-flight is
purely a sanity check; it doesn't validate CLI versions.

### Step 4: try it

Open Claude Code in your project, then:

```
/build-x  add a /healthz endpoint that returns 200 OK
```

Watch the augmented cycle run. If anything errors, jump to
[Section 16](#16-troubleshooting).

---

## 6. Configuration — `agents.toml` deep dive

All tool bindings live in `.sage/agents.toml`. This is the single file
you'll edit when you want to swap models, change modes, or add a new
agent. The dispatcher reads it on every invocation; no script edit is
required to change a binding.

### The two halves: `[roles.*]` and `[agents.*]`

```toml
# WHO does WHAT
[roles.planner]
agent = "claude"
model = "claude-opus-4-7"
mode  = "interactive"

[roles.spec_reviewer]
agent = "codex"
model = "gpt-5-codex"
mode  = "read-only"

# HOW each agent is invoked
[agents.codex]
kind            = "cli"
command         = "codex"
exec_subcommand = "exec"
prompt_style    = "argv"
flags           = ["--skip-git-repo-check"]
model_flag      = "--model"
output_flag     = "--output-last-message"

[agents.codex.modes]
read-only = ["--sandbox", "read-only"]
workspace = ["--sandbox", "workspace-write"]
yolo      = ["--full-auto"]
```

The split is deliberate: roles are *what your project needs done*;
agents are *how a particular CLI happens to be invoked*. You usually
edit role bindings (one line); you rarely edit agent invocation blocks
(several lines per CLI).

### Role fields

Every `[roles.<name>]` block has three fields:

| Field   | Required | What it means                                                                  |
|---------|----------|--------------------------------------------------------------------------------|
| `agent` | yes      | Key under `[agents.<name>]` — which CLI to invoke for this role.               |
| `model` | yes      | Model identifier passed to the CLI via the agent's `model_flag`.               |
| `mode`  | yes      | Key under `[agents.<agent>.modes]` — extra CLI flags appended at invoke time. |

The four shipped roles:

| Role            | Cardinality      | What it does                                                |
|-----------------|------------------|-------------------------------------------------------------|
| `planner`       | host-only        | Writes brief/spec/plan; orchestrates the cycle.            |
| `spec_reviewer` | external (CLI)   | Adversarial review of `spec.md` and `plan.md`. Read-only.  |
| `implementer`   | external (CLI)   | Writes code + tests + `implementer-notes.md`. Edit-permitting. |
| `code_reviewer` | external (CLI)   | Adversarial review of the uncommitted diff. Read-only.     |

You can rename existing role bindings or add new ones (e.g., a
`security_reviewer` role that the planner invokes for sensitive
diffs) — the dispatcher reads role names dynamically.

### Agent fields

Every `[agents.<name>]` block has:

| Field             | Required           | What it means                                                                      |
|-------------------|--------------------|------------------------------------------------------------------------------------|
| `kind`            | yes                | `"host"` (Claude Code itself) or `"cli"` (any external binary).                    |
| `command`         | cli only           | Binary name on `PATH`.                                                              |
| `exec_subcommand` | cli, optional      | First positional arg inserted before everything else (e.g., `"exec"` for Codex). |
| `prompt_style`    | cli only           | `"argv"` (last positional), `"flag"` (`--prompt "..."`), `"stdin"` (piped).       |
| `flags`           | cli, optional      | Flags applied on every invocation.                                                  |
| `model_flag`      | cli, optional      | Flag for the model name (empty string = skip).                                      |
| `output_flag`     | cli, optional      | Flag to redirect final message to a file (empty = redirect stdout).                |
| `modes.<name>`    | cli, optional      | Extra flags appended when a role selects this mode.                                |

### Worked examples

#### Swap the code reviewer to Kimi

```toml
[roles.code_reviewer]
agent = "kimi"
model = "kimi-for-coding"
mode  = "read-only"
```

That's it. The next `/review-code` invocation will dispatch to Kimi.
No script edit needed.

#### Use Codex for both spec review and implementation

```toml
[roles.implementer]
agent = "codex"
model = "gpt-5-codex"
mode  = "workspace"      # Codex's edit-permitting mode

[roles.spec_reviewer]
agent = "codex"
model = "gpt-5-codex"
mode  = "read-only"

[roles.code_reviewer]
agent = "codex"
model = "gpt-5-codex"
mode  = "read-only"
```

Now you don't need Kimi installed at all. The cycle is single-CLI but
still cross-process (each invocation is sandboxed, file-handoff only).

#### Add a hypothetical Gemini CLI as a reviewer alternative

```toml
[agents.gemini]
kind         = "cli"
command      = "gemini"
prompt_style = "stdin"
flags        = ["--no-color"]
model_flag   = "--model"
output_flag  = "-o"

[agents.gemini.modes]
read-only = ["--read-only"]
yolo      = ["--auto-approve"]

# Then point a role at it:
[roles.code_reviewer]
agent = "gemini"
model = "gemini-2.5-pro"
mode  = "read-only"
```

No dispatcher edit needed — the script is data-driven from these
fields. As long as the CLI accepts a prompt and writes its final
message somewhere readable, the dispatcher can drive it.

### What you cannot configure (by design)

- **The planner can't be external.** It must be a `kind = "host"` agent
  because it needs sub-agent invocation and slash command dispatch,
  which only the host model has. Pre-flight catches this.
- **Roles can't share session memory.** Every hand-off is a file under
  `.sage/work/<slug>/`. This is the audit trail and the sandbox
  guarantee — you don't get to bypass it.

---

## 7. Daily use — the slash commands

Multi-agent ships five Claude Code slash commands. They live alongside
Sage's built-ins (none of them shadow `/build`, `/architect`, `/fix`,
etc.):

### `/build-x <task description>`

Run the full augmented cycle: brief → spec → external spec review →
plan → external plan review → external implement → external code review
→ reflect. Use this when you want the whole loop.

```
/build-x  refactor the auth middleware to use signed cookies instead of session tokens
```

### `/review-spec <slug>`

Run the `spec_reviewer` role against `spec.md` for the named work
directory. Use this when you've edited `spec.md` and want a second
opinion before continuing to planning.

```
/review-spec  20260517-auth-refactor
```

If no slug is given, defaults to the most recent `.sage/work/` directory.

### `/review-plan <slug>`

Run the `spec_reviewer` role against `plan.md`. Same shape as
`/review-spec`. The plan reviewer specifically looks for SCOPE_DRIFT
(plan does things spec doesn't ask for) and CONTRADICTIONS (plan step
contradicts a spec requirement).

### `/implement <slug>`

Hand implementation off to the `implementer` role. Preconditions:
`spec.md` + `plan.md` exist, and the working tree is clean
(uncommitted diff would contaminate the code-review step).

The implementer writes:
- Source code (uncommitted — *not* `git add`ed or `git commit`ed)
- `implementer-notes.md` with the step log, spec coverage matrix, and
  any spec ambiguities flagged as questions for the planner

### `/review-code <slug>`

Run the `code_reviewer` role against the uncommitted diff. Use this
after `/implement` and before committing. The reviewer checks:

1. Spec alignment (every requirement → an implementation row)
2. Plan adherence (every plan step → an implementation row)
3. Correctness (off-by-ones, async races, resource leaks, etc.)
4. Boundaries (input validation, secrets, authz)
5. Tests (honest? failure paths? deterministic?)
6. Principles (clarity, fail-loudly, smallest-scope)

The output is a structured review file with a verdict. You decide
whether to commit.

---

## 8. The `/build-x` cycle, phase by phase

This section explains what happens inside `/build-x` so you can predict
behavior, intervene at the right step, and understand the artefacts on
disk.

### Phase 1 — Establish work directory

The planner creates `.sage/work/YYYYMMDD-<slug>/`, picks a short
descriptive slug from your task description, and writes `brief.md` (the
problem framing).

**Artefacts:** `brief.md`

### Phase 2 — Spec (with optional workflow reuse)

Before drafting `spec.md`, the planner classifies the task:

| Task shape                                           | Workflow invoked first |
|------------------------------------------------------|------------------------|
| Architecture-shaped (new module, cross-cutting)      | `/architect`           |
| Knowledge-gap / unfamiliar domain                    | `/research`            |
| UX-shaped (new flow, screen, accessibility)          | `/design`              |
| Mechanical (config tweak, rename sweep)              | none — straight to spec.md |

If a Sage workflow runs first, `spec.md` cites its artefacts (ADRs
under `.sage/work/<slug>/`, research files under `.sage/docs/`).

The planner then writes `spec.md` following the charter in
`.sage/prompts/planner.md`. **Stops** and asks you to approve before
continuing:

```
[A] Approve · [R] Revise · [X] Cancel
```

**Artefacts:** `spec.md` (+ optional architecture / research artefacts)

### Phase 3 — External spec review (severity-gated loop)

The host invokes `/review-spec <slug>` which dispatches to the
configured `spec_reviewer`. The reviewer reads `spec.md` (and sibling
artefacts), runs against the AMBIGUITIES / MISSING_CASES / UNTESTABLE /
UNSTATED_ASSUMPTIONS / CONTRADICTIONS / SCOPE_DRIFT checklist, and
writes a timestamped review to `.sage/work/<slug>/reviews/`.

The loop is **severity-gated**, not verdict-gated. After each review
the host counts the `### [BLOCKER]` / `### [MAJOR]` findings and:
- **0 BLOCKER / 0 MAJOR** (verdict `APPROVE` or `REVISE`) → continue to
  Phase 4; open MINORs are logged as deferred. The loop never re-runs
  on a MINOR-only review.
- **`REJECT`**, a review whose verdict contradicts its counts, or one
  that fails schema validation → stop and escalate to you.
- **BLOCKER/MAJOR remain** → the planner patches `spec.md` and re-runs,
  until the stakes-tier cap (`prototype` 2, `production` 3) is reached
  — then the host stops and asks you. A user-granted extra round is
  exactly one round; the cap re-arms.
- The trajectory is watched: once three reviews exist, a
  `BLOCKER + MAJOR` count that stops decreasing means the loop is not
  converging — the host escalates rather than spending more rounds.

On iteration 2+, the dispatcher injects the previous review into the
prompt: confirm prior findings are resolved, hunt for new ones, do not
soften standards — but equally do not escalate trivia to keep the loop
alive.

Every iteration is logged to `.sage/decisions.md`:

```
## 2026-05-17T10:42:18 · spec review iteration 2
- Verdict: REVISE
- BLOCKERs addressed: B1, B2
- Intentional non-changes: B3 (out of scope, see spec §3 non-goals)
```

**Artefacts:** `.sage/work/<slug>/reviews/spec-spec_reviewer-*.md`

### Phase 4 — Plan

The planner writes `plan.md` following the charter. Each step cites the
spec section it satisfies and ends in a state where tests pass.

**Artefacts:** `plan.md`

### Phase 5 — Plan review (loop, max 2 iterations)

`/review-plan <slug>` runs. Same verdict semantics as Phase 3, but
common findings are SCOPE_DRIFT and PLAN_ADHERENCE issues.

**Artefacts:** `.sage/work/<slug>/reviews/plan-spec_reviewer-*.md`

### Phase 6 — Implementation

`/implement <slug>` runs. Preconditions: clean working tree (the diff
must be cleanly attributable to the implementer's work). The
`kimi-implementer` sub-agent wrapper isolates stdout from the main
context and returns only a short summary: files touched, plan adherence,
tests added, spec ambiguities flagged.

If the implementer reports unresolved spec ambiguities, treat them as
late-binding findings: patch `spec.md`, re-run `/review-spec`, and
re-implement only the affected steps.

**Artefacts:** uncommitted source diff + `implementer-notes.md`

### Phase 7 — Code review (loop)

`/review-code <slug>` runs against the uncommitted diff. Verdicts:

- **APPROVE** → proceed to Phase 8 (you decide whether to commit)
- **FIX_BEFORE_MERGE** → present findings to you with options:
  - `[F]` Fix small things yourself (only for trivial corrections)
  - `[K]` Send the fix list back to `/implement`
  - `[D]` Show the full review and decide
- **REWORK** → return to Phase 4 (plan), possibly Phase 2 (spec)

Multi-agent **never auto-commits.** Even APPROVE just means "no
blocking findings" — you decide what to stage.

After 3 FIX_BEFORE_MERGE rounds the orchestrator surfaces "consider
reworking the plan" to you — at that point, the issue is probably
upstream of the implementation.

**Artefacts:** `.sage/work/<slug>/reviews/diff-code_reviewer-*.md`

### Phase 8 — Reflect

Sage's built-in `/reflect` runs. It reads `.sage/decisions.md`, the
review files, and `implementer-notes.md` to extract WHEN/CHECK/BECAUSE
learnings into `.sage/docs/reflect-*.md` for the next cycle.

**Artefacts:** `.sage/docs/reflect-<slug>.md`

---

## 9. Customization

### Swap models / agents (most common)

Edit `.sage/agents.toml` — see [Section 6 worked examples](#worked-examples).
Changes take effect on the next invocation. No script edit needed.

### Tune role prompts

Prompts live under `.sage/prompts/` and are **yours** — `sage update`
never touches them. After running a few cycles, look at your reviews:

- Are BLOCKERs real, or is the reviewer crying wolf? Tighten the
  reviewer's "what is a blocker" prose in `spec_reviewer.md` or
  `code_reviewer.md`.
- Is the implementer producing test theater (`assert result is not None`)?
  Tighten `implementer.md`'s "tests must assert what the behavior
  produces, not that it produced something" rule.
- Is the planner skipping the adversarial self-check? Strengthen the
  "you are not done planning until self-check finds nothing" line in
  `planner.md`.

Treat prompts as **living code**. They diff in git alongside the rest
of your project; review changes the same way you'd review a refactor.

### Add a new role

To add, say, a `security_reviewer` role that runs only on sensitive
diffs:

1. Write `.sage/prompts/security_reviewer.md` (start by copying
   `code_reviewer.md` and narrowing scope to BOUNDARIES + injection +
   secrets).
2. Add a `[roles.security_reviewer]` block to `.sage/agents.toml`
   pointing at whatever CLI you want.
3. Optionally add a new slash command at `.claude/commands/review-security.md`
   following the pattern of `review-code.md` — or just have the
   planner invoke the role via the dispatcher when its heuristics
   identify a sensitive diff.

The dispatcher (`run-role.sh`) handles arbitrary role names — it reads
them from `agents.toml`. No script edit needed unless the new role's
output schema differs from the reviewer schema (in which case extend
`validate-review.sh` in lockstep).

### Add a new agent (CLI)

See [Section 6 worked example: Add a hypothetical Gemini CLI](#add-a-hypothetical-gemini-cli-as-a-reviewer-alternative).

The general pattern:

1. Add an `[agents.<name>]` block to `.sage/agents.toml` describing
   how the CLI is invoked.
2. Add `[agents.<name>.modes]` for whatever sandbox modes it supports.
3. Point a role at it via `[roles.<role>].agent = "<name>"`.

The dispatcher's invocation logic is data-driven. No script changes
needed.

### Change the loop budgets

The `/build-x` command file (`.claude/commands/build-x.md`) declares
the iteration caps:

- Phase 3 (spec review): cap set by the stakes tier — 2 (`prototype`)
  or 3 (`production`); re-arms on a user-granted extra round
- Phase 5 (plan review): max 2 iterations
- Phase 7 (code review): no fixed cap, soft escalation after 3 rounds

These are guidelines for the host model, not hard limits enforced by
scripts. To raise or lower them, edit the prose in the corresponding
phase section. (Remember: `build-x.md` is framework-owned. If you edit
it, `sage update` will prompt before refreshing.)

### Run the framework against itself

The standalone prototype lives at `/mnt/e/Codes/sage-multi-agent/`.
After integration into Sage, the framework copy at
`runtime/multi-agent/` is the source of truth — and Sage itself can be
a multi-agent project. Run `sage setup multi-agent` inside the Sage
repo to dogfood the loop.

---

## 10. File layout — framework- vs user-owned

This split is enforced by `sage setup multi-agent` (install) and
`sage update` (refresh). Editing the wrong column has predictable
consequences.

### User-owned (NEVER touched by `sage update`)

| Deployed path                  | Purpose                                          |
|--------------------------------|--------------------------------------------------|
| `.sage/agents.toml`            | Your tool bindings — the file you edit most.    |
| `.sage/prompts/_shared.md`     | Universal rules prepended to every role prompt. |
| `.sage/prompts/planner.md`     | Charter for the host (Claude Code, Opus).       |
| `.sage/prompts/spec_reviewer.md` | Adversarial spec/plan reviewer prompt.         |
| `.sage/prompts/implementer.md` | Implementer behavior contract.                  |
| `.sage/prompts/code_reviewer.md` | Code reviewer prompt.                           |
| `.sage/work/`                  | Your in-flight initiatives. Pre-existing Sage state. |

These files exist so you can tune the loop. Once installed, they are
yours forever.

### Framework-owned (refreshed by `sage update`)

| Deployed path                            | Purpose                                        |
|------------------------------------------|------------------------------------------------|
| `.sage/scripts/run-role.sh`              | Dispatcher — reads agents.toml, invokes CLIs.  |
| `.sage/scripts/validate-review.sh`       | Reviewer output schema check.                  |
| `.sage/docs/multi-agent.md`              | End-user protocol reference (deployed).        |
| `.claude/commands/build-x.md`            | The `/build-x` slash command.                  |
| `.claude/commands/review-spec.md`        | The `/review-spec` slash command.              |
| `.claude/commands/review-plan.md`        | The `/review-plan` slash command.              |
| `.claude/commands/implement.md`          | The `/implement` slash command.                |
| `.claude/commands/review-code.md`        | The `/review-code` slash command.              |
| `.claude/agents/codex-reviewer.md`       | Sub-agent wrapper isolating reviewer stdout.   |
| `.claude/agents/kimi-implementer.md`     | Sub-agent wrapper isolating implementer stdout. |

If you edit one of these and then run `sage update`, you'll be prompted
`[K]eep | [R]eplace | [D]iff` before any change. See
[Section 11](#11-upgrades--sage-update-behavior).

### Merged (not overwritten)

| Path                            | What multi-agent contributes                          |
|---------------------------------|-------------------------------------------------------|
| `.claude/settings.json`         | 13 `Bash(...)` permission patterns. Your patterns kept. |
| `.sage/config.yaml`             | A `multi_agent: { enabled, installed_version }` block. |
| `CLAUDE.md`                     | A "Multi-Agent build cycle (optional)" section, wrapped in HTML comment markers so it can be cleanly removed. |

---

## 11. Upgrades — `sage update` behavior

When you run `sage update` in a project with multi-agent installed, here's
exactly what happens for each multi-agent file:

```
For each framework-owned deployed file:
  1. Hash the deployed copy (SHA-256).
  2. Compare against the manifest's expected hash for the installed_version.

  3a. Hashes match the new template? → "up to date", no action.
  3b. Deployed hash matches the prior-version's manifest hash? → safe
      to overwrite (you haven't edited it locally). Refresh from
      template. Log "refreshed".
  3c. Deployed hash differs from both template AND prior-version's
      hash? → DRIFT (you've edited it locally). Prompt:
        [K]eep yours  |  [R]eplace with template  |  [D]iff first
      On [R], save a timestamped backup at <file>.replaced-<STAMP>
      before overwriting.

For each user-owned file (agents.toml, prompts/*):
  Never touched. Print "preserved".
```

After all files are processed, `installed_version` in
`.sage/config.yaml` is bumped to match the framework version.

### Non-interactive updates (CI / scripts)

By default, `sage update` is interactive — it prompts on drift. For
non-interactive use:

```bash
# Preserves locally-modified framework files (safe default — drift kept).
sage update           # equivalent to --yes for the multi-agent step

# Force-replace locally-modified framework files (backup saved).
SAGE_UPDATE_FORCE_MULTI_AGENT_REPLACE=1 sage update
```

The forced-replace path saves a backup at `<file>.replaced-<STAMP>`
next to the replaced file, so nothing is lost — you just have to fish
your changes out of the backup and re-apply them manually.

### Checking version

```bash
sage setup multi-agent --status
# → multi-agent: enabled=true version=1.1.6
```

The version tracks the Sage framework version (from
`.claude-plugin/plugin.json`) at install or last refresh time.

---

## 12. Uninstall

```bash
sage setup multi-agent --remove
```

Behavior:

1. **User-owned files** (`agents.toml`, `prompts/*.md`) are *moved* to
   `.sage/.removed-multi-agent-<STAMP>/` rather than deleted. Your
   prompt tuning isn't lost.
2. **Framework-owned files** (scripts, command files, sub-agents) are
   deleted outright.
3. **Empty directories** (`.sage/prompts/`, `.sage/scripts/`,
   `.sage/docs/` if empty after removal) are pruned.
4. **`.claude/settings.json`** has the 13 multi-agent `Bash(...)`
   patterns pruned. Your custom patterns survive.
5. **`.sage/config.yaml`** has the `multi_agent:` block removed.
6. **`CLAUDE.md`** has the multi-agent section removed (HTML comment
   markers make this clean).
7. **`.sage/work/`** is **never** touched. Your in-flight initiatives
   are safe.

For unattended:

```bash
sage setup multi-agent --remove --yes
```

Idempotent: running `--remove` on a project where multi-agent isn't
installed prints "nothing to remove" and exits 0.

### Re-install after remove

If you change your mind and re-install later:

```bash
sage setup multi-agent
```

The fresh install will write new defaults to `.sage/prompts/`. To
recover your tuned prompts, copy them back from the backup directory:

```bash
ls .sage/.removed-multi-agent-*/
cp .sage/.removed-multi-agent-<STAMP>/.sage/prompts/*.md .sage/prompts/
```

---

## 13. Reviewer output contract

Every reviewer output (`.sage/work/<slug>/reviews/*.md`) MUST satisfy:

1. **Last non-empty line is a verdict.** One of:
   - `APPROVE`, `REVISE`, `REJECT` (for spec/plan review)
   - `APPROVE`, `FIX_BEFORE_MERGE`, `REWORK` (for code review)
2. A `## Findings` H2 section exists.
3. Every finding subheader matches `^### \[(BLOCKER|MAJOR|MINOR)\] `.
4. Every finding has a `- **Where:**` line and a `- **Quote:**` line.

This is enforced by `.sage/scripts/validate-review.sh`, which the
dispatcher runs automatically after every reviewer invocation.
Validation failures print a warning to stderr but **do not** change the
dispatcher's exit code — the orchestrator is responsible for surfacing
the malformed output to you rather than parsing the verdict
optimistically.

### Why the schema is strict

Multi-agent is a loop with machine-readable hand-offs. If the reviewer
writes "looks good to me" instead of `APPROVE`, the dispatcher can't
tell whether to continue, retry, or stop. The schema is the contract
that lets the loop work without a human in every link.

If you're tuning a reviewer prompt and the validator starts failing
where it didn't before, your prompt change probably loosened the
output format. The fix is in the prompt, not the validator.

### Verdict semantics

| Verdict           | Meaning                                                      | Use in          |
|-------------------|--------------------------------------------------------------|-----------------|
| `APPROVE`         | No blocking findings. Safe to proceed.                       | spec/plan/code  |
| `REVISE`          | Findings exist; fix them and re-review.                      | spec/plan       |
| `REJECT`          | Artefact is fundamentally wrong; go back a layer.            | spec/plan       |
| `FIX_BEFORE_MERGE`| Diff has issues; fix and re-review, but planning was sound.  | code            |
| `REWORK`          | Diff issues trace back to plan or spec; re-plan / re-spec.   | code            |

A reviewer can only emit verdicts from the appropriate column. If a
spec reviewer emits `FIX_BEFORE_MERGE`, the validator catches it.

---

## 14. Cost, latency, and capacity

One `/build-x` invocation triggers between **4 and 9 external CLI
calls**:

| Phase           | Min | Max |
|-----------------|-----|-----|
| Spec review     | 1   | 3   |
| Plan review     | 1   | 2   |
| Implement       | 1   | 1   |
| Code review     | 1   | 3+  |
| **Total**       | **4** | **~9** |

Per-call token usage is dominated by:

- Prompt (~2–5k tokens — the role prompt + shared rules + placeholders)
- The artefact under review (spec.md is typically 3–8k; plan.md
  similar; the diff in code review is the variable one — anything from
  500 to 20k+ tokens)
- For reviewer iterations 2+, the previous review is injected too
  (another 1–5k tokens)
- Output is the review file itself (~1–3k tokens)

**Typical full cycle on a medium feature: 30k–100k tokens across all
external calls**, distributed across whichever models you've bound.

Latency is dominated by the external CLIs (each call takes whatever the
underlying model takes — typically 10s–60s per CLI invocation). The
dispatcher itself is <200ms overhead per call. There is **no
parallelisation within a single cycle** — phases run serially and
file-handoffs are synchronous. This is intentional (deterministic
ordering, clean audit trail).

If you find the cycle too slow for fast-iteration work, that's a sign
to use `/build` (single-session) for those tasks and reserve `/build-x`
for the work where reviewer disagreement actually changes outcomes.

No SLA — multi-agent surfaces whatever the bound CLIs surface.

---

## 15. Security model

### API keys and credentials

You provide API keys for the bound CLIs **out of band** (typically
environment variables: `OPENAI_API_KEY`, `MOONSHOT_API_KEY`, etc.).
Sage does not handle, store, or surface those keys. The dispatcher
invokes the CLI as a subprocess and inherits your environment — the
CLI authenticates itself.

If you've added secret-handling to a custom CLI binding, that's your
responsibility. Sage does not vault secrets.

### Sandbox enforcement

Each role's `mode` field selects a sandbox profile:

- **`read-only`** for `spec_reviewer` and `code_reviewer`. Concretely:
  - Codex: `--sandbox read-only`
  - Kimi: `--plan` (planning mode, no edits)
  - Any custom CLI: whatever you put in its `modes.read-only` block

Reviewers literally cannot modify the workspace or commit. The Codex
sandbox is enforced at the OS level (filesystem read-only); Kimi's
`--plan` mode is enforced at the CLI level.

- **`yolo` / `workspace`** for `implementer`. Edit-permitting, but the
  prompt and the `kimi-implementer` sub-agent wrapper both forbid
  `git commit` and `git add`. Compliance is verified at code-review
  time by the precondition "diff must be uncommitted" — if the
  implementer committed, the code reviewer sees a clean tree and
  raises a BLOCKER.

### Settings.json permission patterns

`sage setup multi-agent` adds 13 `Bash(...)` patterns to
`.claude/settings.json`:

```
Bash(.sage/scripts/run-role.sh:*)
Bash(.sage/scripts/validate-review.sh:*)
Bash(codex exec:*)
Bash(codex review:*)
Bash(kimi --print:*)
Bash(git diff:*)
Bash(git status:*)
Bash(git diff --stat)
Bash(git diff --stat:*)
Bash(ls -1t .sage/work/*)
Bash(ls -1t .sage/work/)
Bash(cat .sage/work/*)
Bash(mkdir -p .sage/work/*)
```

These permit only the specific subprocess invocations the loop needs.
Nothing broader. If you bind a new CLI (e.g., `gemini`), you'll need
to add a corresponding `Bash(gemini ...)` pattern manually — the
dispatcher will refuse to run the CLI otherwise.

### No cross-agent memory

By design, no agent reads any other agent's session memory. All
context flows through files under `.sage/work/<slug>/`. This means:

- A compromised reviewer can write a misleading review file, but the
  file is right there on disk for you to read.
- A compromised implementer can write malicious code, but the diff is
  right there in `git diff` and the code reviewer runs against it.
- There is no covert channel between agents.

This is the same security model as code review by humans — the
artefact is the contract.

---

## 16. Troubleshooting

### Install: "Multi-agent requires Python 3.11+ (for tomllib)"

Sage Multi-Agent uses `tomllib` from the stdlib (3.11+). Earlier Pythons
don't have it.

```bash
python3 --version
# If <3.11, install a newer Python:
#   macOS:   brew install python@3.12
#   Ubuntu:  sudo apt install python3.12
#   Windows: download from python.org
```

### Install: "❌ .sage/ missing — run `sage init` first"

You're in a directory that isn't a Sage project. Either initialise it:

```bash
sage init
```

…or change to a directory that already has `.sage/`.

### Install: "❌ claude-code platform not configured"

The project was initialised for a different platform. Multi-agent is
Claude Code only in v1. To add Claude Code as an additional platform:

```bash
sage init --platform claude-code,<existing-platform>
```

### Pre-flight: "⚠ codex CLI not on PATH"

Install (or finish installing) the CLI you bound to that role. Or rebind
the role to a CLI you do have — edit `.sage/agents.toml`:

```toml
[roles.spec_reviewer]
agent = "kimi"      # was "codex"
model = "kimi-for-coding"
mode  = "read-only"
```

### `/build-x` exits with "Unknown role: X"

`agents.toml` references a role name that has no matching `[roles.<name>]`
block, or vice versa. Open `.sage/agents.toml` and confirm:

- Every `[roles.<X>]` has a corresponding `agent = "<Y>"` where
  `[agents.<Y>]` exists.
- The reverse isn't required — you can have unused agent blocks (e.g.,
  the `gemini` example block) without binding any role to them.

### `/build-x` exits with "Agent CLI not on PATH: codex"

The role's bound agent has `command = "codex"` but `codex` isn't on
PATH at runtime. Either:

1. Add it to PATH (check your shell config, not just the current
   terminal Sage is running in).
2. Rebind the role to a CLI that is on PATH.

### Reviewer output fails schema validation

The dispatcher prints a warning like:

```
WARN: review output failed schema validation: .sage/work/.../reviews/spec-spec_reviewer-20260517-104500.md
```

Open the file and look at the last non-empty line. It must be exactly
one of `APPROVE | REVISE | REJECT | FIX_BEFORE_MERGE | REWORK` — no
periods, no trailing text, no markdown formatting.

If the reviewer keeps producing malformed output, the prompt likely
got loosened. Compare your `.sage/prompts/<role>.md` against the
template at `runtime/multi-agent/prompts/<role>.md` in the Sage
framework — restore the strict "## Verdict" trailer.

### `/implement` refuses to run: "tree is dirty"

The code reviewer's precondition is that the diff must be cleanly
attributable to the implementer. Pre-existing uncommitted changes
would contaminate the review.

```bash
git status                # see what's dirty
git stash                 # set it aside
# …or…
git commit -a -m "WIP"    # commit it
# then re-run /implement
```

### `sage update` keeps prompting on the same file

The deployed file has been locally edited *and* is currently different
from what was last shipped. You have three choices each time:

- `[K]eep yours` — accept your edit will diverge further. Fine for
  long-term customisations.
- `[R]eplace` — accept the template; your edit goes to a backup.
- `[D]iff` — see what's different, then choose K or R.

If you want to bake your edit into the template permanently, send a PR
to the Sage repo. Otherwise, expect the prompt every refresh.

### "Multi-agent refresh exited non-zero"

The Python helper had an unexpected error. Run it directly to see the
full traceback:

```bash
python3 ~/.sage/framework/runtime/tools/multi_agent_setup.py refresh \
  ~/.sage/framework \
  $(pwd) \
  --yes
```

Likely causes: malformed `.sage/config.yaml`, malformed
`.claude/settings.json`, file permission issues.

### CLAUDE.md regenerated and lost the multi-agent section

Sage's platform generators sometimes rewrite CLAUDE.md (e.g., on
preset change). The next `sage update` will re-append the multi-agent
section automatically — that's a built-in safety net.

To re-append manually:

```bash
sage setup multi-agent --refresh
```

---

## 17. Migrating from the standalone prototype

If you were using the standalone prototype at
`/mnt/e/Codes/sage-multi-agent/` (or a similar manual install), here's
how to move to the framework-integrated version.

### Step 1: back up your tuned prompts

Your `.sage/prompts/*.md` and `.sage/agents.toml` likely have edits
you want to keep.

```bash
cp -r .sage/prompts /tmp/my-prompts-backup
cp .sage/agents.toml /tmp/my-agents-backup
```

### Step 2: remove the prototype install (manual)

```bash
rm .sage/scripts/run-role.sh .sage/scripts/validate-review.sh
rm .sage/docs/external-tools.md   # the prototype's docs file
rm .claude/commands/{build-x,review-spec,review-plan,implement,review-code}.md
rm .claude/agents/{codex-reviewer,kimi-implementer}.md
# Don't delete .sage/agents.toml or .sage/prompts/ — they're yours.
```

Manually edit `.claude/settings.json` to remove the multi-agent
`Bash(...)` patterns the prototype added.

### Step 3: install the framework version

```bash
sage upgrade               # get Sage 1.1.6+ on your machine
sage setup multi-agent     # install in your project
```

The install will detect that `.sage/agents.toml` and `.sage/prompts/*`
exist and **preserve them** (per-file: prompts you've kept will stay
yours; the prompt files that are still defaults will be untouched
because they already exist).

### Step 4: re-apply your customisations

If you had custom prompts in your backup that the install overwrote
(unlikely, since user-owned files are preserved, but possible if you'd
edited a file that the framework version renames):

```bash
diff -r /tmp/my-prompts-backup .sage/prompts/
# Cherry-pick anything you want to restore.
```

### Step 5: verify

```bash
sage setup multi-agent --status
# → multi-agent: enabled=true version=1.1.6
```

Open Claude Code and run `/build-x` on a small test task to confirm
the loop completes.

### Differences from the prototype

The framework version is functionally equivalent to the prototype but
adds:

- `sage update` integration (drift detection, prompt-before-replace)
- `--remove` flag (clean uninstall with backup)
- `--status` flag
- CLAUDE.md augmentation (host model knows when to prefer `/build-x`)
- Workflow reuse hints (planner invokes `/architect`, `/research`,
  `/design` when appropriate)
- Survives `sage update` correctly (the prototype required manual
  reinstall after upgrade)

---

## 18. FAQ

### Can I use multi-agent with Cursor / Aider / Continue / Cline?

Not in v1. The slash commands, sub-agent isolation, and `Bash(...)`
permission patterns assume Claude Code primitives. The dispatcher
itself (`run-role.sh`) is platform-agnostic — if you have a host that
can invoke shell scripts and read files, you could in principle write
your own host-side command set. But that's a fork, not a supported path.

Multi-platform support is on the long roadmap but explicitly out of
scope for v1.

### Why isn't there a `/security-review` command?

Because nobody's written one yet. The dispatcher handles arbitrary role
names — if you want one, add a `[roles.security_reviewer]` block to
`agents.toml`, write `.sage/prompts/security_reviewer.md`, and either
add a slash command or have the planner invoke it via the dispatcher
directly. See [Section 9: Add a new role](#add-a-new-role).

### Can the planner be something other than Opus?

In principle, any host model that can:
- Read slash command files and dispatch
- Run Bash sub-processes
- Invoke sub-agents (for stdout isolation)

…can play the planner role. In practice, the prompts in
`.sage/prompts/planner.md` are tuned for Opus's specific strengths
(long-form planning, adversarial self-critique, charter adherence).
Other Claude models (Sonnet 4.6, etc.) work but produce less rigorous
spec drafts. Configure with:

```yaml
# .sage/agents.toml
[roles.planner]
agent = "claude"
model = "claude-sonnet-4-6"
mode  = "interactive"
```

### Does multi-agent work with Sage's quality_locked and autonomous flags?

Yes. `/build-x` is built on the same Sage core as `/build` and honors
the same flags:

```
/build-x --quality-locked  add foo
/build-x --autonomous --no-autonomous  …  # config defaults respected
```

See `CHANGELOG.md` [1.1.5] for the flag-defaults contract.

### What happens if a CLI's API is down?

The dispatcher invokes the CLI as a subprocess and surfaces whatever
exit code / stderr it produces. The orchestrator (the host model)
sees the failure and stops the cycle, surfacing the error to you. No
silent downgrade to single-model behavior — that's an intentional
spec requirement (see `.sage/docs/multi-agent.md` §4.6).

### Can I pin a specific model version?

Yes. The `model` field in `[roles.<name>]` is passed verbatim to the
CLI's `--model` flag (or whatever `model_flag` you've configured).
If your CLI accepts dated versions like `gpt-5-codex-2026-01-15`, use
that.

### Does multi-agent share `.sage/work/<slug>/` with `/build`?

Yes — they write the same artefacts (`brief.md`, `spec.md`, `plan.md`,
`implementer-notes.md`). You can run `/build` on a slug, abandon it
mid-cycle, then resume with `/build-x` (it'll read the existing
artefacts and continue). The augmented cycle adds only the
`reviews/` subdirectory.

### How do I see what reviews have been run?

```bash
ls -lt .sage/work/<slug>/reviews/
```

Files are timestamped (`-YYYYMMDD-HHMMSS.md`) and never overwritten.
Iteration history is preserved for free.

### Can I delete old review files?

Yes. They're not consumed by anything after the cycle completes
(except by `/reflect`, which reads recent ones). The only consequence
of deleting them is losing the audit trail. Add `.sage/work/*/reviews/`
to `.gitignore` if you don't want them committed; otherwise they're
useful in PR history.

### Where does the loop log its decisions?

`.sage/decisions.md` (Sage's standard decision log) gets a per-iteration
entry from the planner. Reviewer outputs themselves go to
`.sage/work/<slug>/reviews/`. After the cycle, `/reflect` consolidates
both into `.sage/docs/reflect-<slug>.md`.

### How is multi-agent different from sub-agents in Claude Code?

Claude Code's built-in sub-agents share the host model. They're great
for parallelising work or isolating context — but they don't give you
*independent review by a different model*. Multi-agent's value is
specifically cross-model adversarial review. The two coexist:
`/build-x` uses sub-agents internally to isolate the external CLI's
stdout from the host's main context.

### Can I run `/build-x` in a fresh git repo?

Yes, but the implementer's precondition is a clean working tree. If
the repo has no commits yet, run an initial `git commit --allow-empty
-m init` first so `git status` is meaningful.

### Will this work offline?

The dispatcher itself is offline. The bound CLIs (Codex, Kimi) make
network calls to their providers. If you're offline, the cycle will
fail at the first external invocation with whatever error the CLI
produces (typically a connection timeout).

If you have a local-model CLI (e.g., `ollama run`), you could bind
roles to it — write an `[agents.ollama]` block following the patterns
in [Section 6](#6-configuration--agentstoml-deep-dive).

---

## Appendix: command reference

### `sage setup multi-agent`

| Subcommand / flag         | What it does                                          |
|---------------------------|-------------------------------------------------------|
| (no flags)                | Install (interactive).                                |
| `--yes`                   | Install without prompting (CI).                       |
| `--force`                 | Overwrite locally-modified framework files on install. |
| `--remove`                | Uninstall (interactive). User files backed up.        |
| `--remove --yes`          | Uninstall without prompting.                          |
| `--refresh`               | Re-apply the template (idempotent).                   |
| `--status`                | Print install status + version.                       |

### Environment variables

| Variable                                  | Effect                                                              |
|-------------------------------------------|---------------------------------------------------------------------|
| `SAGE_UPDATE_FORCE_MULTI_AGENT_REPLACE=1` | `sage update` force-replaces locally-modified framework files.      |
| `SAGE_HOME`                               | Override where Sage looks for the framework (testing / dev).        |

### Slash commands

| Command                       | Role invoked    | Args                |
|-------------------------------|-----------------|---------------------|
| `/build-x <task>`             | planner (host)  | task description    |
| `/review-spec <slug>`         | `spec_reviewer` | slug (optional)     |
| `/review-plan <slug>`         | `spec_reviewer` | slug (optional)     |
| `/implement <slug>`           | `implementer`   | slug (optional)     |
| `/review-code <slug>`         | `code_reviewer` | slug (optional)     |

### Dispatcher exit codes (`.sage/scripts/run-role.sh`)

| Code | Meaning                                                |
|------|--------------------------------------------------------|
| 0    | Success; review or implementation written to disk      |
| 2    | Bad invocation (missing arg, unknown kind)             |
| 3    | Role bound to host agent (caller error)                |
| 4    | Missing prompt template                                |
| 5    | Python 3.11+ required and not found                    |
| 6    | Unknown role or agent in `agents.toml`                 |
| 7    | Agent CLI not on `PATH`                                |
| 8    | Unknown `prompt_style`                                 |

---

**Next steps:**

- New to Sage? Start with the [main README](../README.md).
- Want to extend the framework itself? See
  [runtime/multi-agent/README.md](../runtime/multi-agent/README.md).
- Hit a wall? File an issue at https://github.com/xoai/sage/issues.
