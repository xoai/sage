---
name: build
version: "1.0.0"
mode: build
produces: ["Brief (medium+ tasks)", "Spec", "Implementation plan"]
checkpoints: 3
scope: "Single session for medium tasks, multi-session for large"
user-role: "Review and approve at each gate"
---

# Build Workflow

Feature development guided by Sage.

## Auto-Pickup

BEFORE ANYTHING: Scan `.sage/work/` for existing artifacts.
This scan is MANDATORY — check the DISK.

**Manifest-first path:** If `.sage/work/*/manifest.md` exists, run
`python3 sage/runtime/tools/manifest.py resume` (plugin installs:
`python3 "${CLAUDE_PLUGIN_ROOT}/tools/manifest.py" resume`; no python3 →
read the manifest by hand). The brief it prints is the primary context
source: resume at the phase indicated, with the manifest body as judgment
*context, not orders* — apply the resume authority order
(cycle-protocol.md): live user > recorded decisions > manifest prose,
and evidence over all of it.

**Fallback path:** If no manifest.md but artifacts exist, use file-scan
routing (below). Create manifest.md from inferred state before proceeding
(backfill). This preserves backward compatibility with pre-v1.0.9 cycles.

**File-scan routing (when no manifest):**
- No artifacts exist → Step 2 (scope assessment)
- Brief exists, no spec → Step 4 (spec)
- Spec exists, no plan → Step 5 (plan)
- Plan exists, not all completed → Step 6 (build-loop)
- All status: completed → offer next steps

You MUST follow this routing. Do not override it based on:
- Conversation context ("we discussed this before")
- User description ("the design is clear")
- Your own assessment ("this is straightforward")
The disk is the source of truth. Not your memory.

**Multiple in-progress:** Present list:
[1] Continue [initiative A] — [phase]
[2] Continue [initiative B] — [phase]
[3] Start something new

**Branch check (git projects):** when resuming, compare the current
branch against the initiative's recorded `branch:` manifest field
(see git-discipline); if they differ, surface it before proceeding.
Prefer the initiative whose recorded branch matches HEAD.

Read the initiative's decision log for recent context (global
`.sage/decisions.md` for cross-initiative context). Read the
`handoff` field in the most recent artifact's frontmatter if present.

**Upstream context:** Also scan `.sage/docs/` for research and
analysis artifacts (jtbd-*, ux-audit-*, opportunity-*, ux-evaluate-*).
If found, announce: "Sage: Found research/analysis context — [list].
Using as build input."

### Manifest Lifecycle (build workflow)

**Create** manifest.md when the first artifact is saved (brief or spec).
Use the template from `core/templates/manifest-template.md`.

**Update** manifest.md at EVERY checkpoint:
- Every [A]/[R]/[N] gate: update phase, status, `gate_state`, updated timestamp
- Phase transitions: update context summary if new information emerged
- New decisions: append to the manifest's decisions list

**gate_state at each checkpoint (machine field — the spec-gate hook reads it):**
- Spec approved `[A]` → `gate_state: spec-approved`
- Plan approved `[A]` → `gate_state: plan-approved`
- Entering the build-loop (Step 6) → `gate_state: building`
- All quality gates pass → `gate_state: gates-passed`
- Step 8 completion → `gate_state: complete`

Until `gate_state` reaches `spec-approved`, the Claude Code hook blocks edits to
source files — that is Rule 3 made mechanical. Advance it the moment the spec is
approved, not "later"; a stale `pre-spec` keeps blocking the very work you just
approved.

**Context budget pressure:** If the conversation is very long (many
tool calls, approaching context limits), write a manifest update BEFORE
suggesting a session break. This is the critical moment — capture the
judgment that's about to be lost.

**Session end ([N]):** Manifest update is MANDATORY. Write handoff
guidance and context summary before ending.

**Completion:** Set `status: complete` and `gate_state: complete` at Step 8.
The completion guard blocks this transition unless `gate_state` was already
`gates-passed` — so run the quality gates before closing (Rule 5).

**Anti-lazy-manifest contract:**
Context summary MUST NOT be:
- A copy of the spec's title or description
- "See spec.md for details"
- Generic guidance ("Continue with implementation")
The summary must contain judgment the spec doesn't contain.

**Shared cycle protocol:** decision-log targeting (Rule 7), gate_state
discipline, phase announcements, and the session-break contract are shared across
the delivery workflows — see `core/workflows/_shared/cycle-protocol.md`.

## Phase Announcements

At each major phase transition, announce before doing any phase work:

```
Sage: Entering UNDERSTAND phase [cycle-id] — gathering requirements via quick-elicit.
Sage: Entering PLAN phase [cycle-id] — creating implementation plan from spec.
Sage: Entering DELIVER phase [cycle-id] — implementing with TDD and quality gates.
Sage: Entering REVIEW phase [cycle-id] — running quality verification.
```

The cycle ID is the directory name under `.sage/work/` (e.g., `20260324-auth-flow`).

## Step 2: Assess Scope

Classify by structural complexity — not time, not gut feeling.

**Lightweight:** One component, no design decisions, no behavior changes
visible to other team members. The change is obvious from the request.
→ Skip to Step 6, implement directly.

**Standard:** Multiple components, OR any design decision, OR
coordination between modules. Spec file REQUIRED.
→ spec.md MUST exist at .sage/work/ before implementation.
→ plan.md MUST exist at .sage/work/ before implementation.
→ If the task also needs scope definition, write brief first (Step 3).

**Comprehensive:** New subsystem, cross-cutting changes, or multiple
stakeholder impact.
→ MUST write brief (Step 3) → spec (Step 4) → plan (Step 5) → implement.

**Complexity signals** (any ONE makes it Standard or above):
- Touches more than 3 files
- Involves a new API endpoint or data model change
- Requires coordination between multiple modules or services
- Has user-facing behavior changes (new UI, changed flow)
- Involves a decision a team member would need to know about
- Multiple layers affected (database + backend + frontend)

**Anti-downgrade:** When in doubt, classify as Standard, not Lightweight.
Do NOT downgrade to Lightweight to avoid writing a spec. If you find
yourself thinking "this is simple enough to skip the spec," that
thought is the signal to NOT skip the spec.

Present your assessment:

**Sage → build workflow.** [Scope] — [what makes it this scope].
Starting with [first required step].

If the user explicitly asks to skip a required step, write a minimal
5-line spec anyway (WHAT, WHY, HOW, DONE-WHEN), present [A]/[R], and
record the skip rationale in decisions.md.

## Step 2.5: Branch Setup (Standard+ scope, git projects)

For Standard or Comprehensive scope in a git repository, create the
initiative branch before any artifact or code work: read and follow
`sage/core/capabilities/execution/git-discipline/SKILL.md` — propose
`feat/<slug>`, confirm with the user, create from the default branch,
and record the branch name in the initiative's manifest frontmatter
(`branch:`). The capability owns dirty-tree, already-on-a-branch,
detached-HEAD, and decline handling. Lightweight scope skips
branching (it produces no multi-commit initiative). Not a git
repository → skip silently.

**Parallel-session note (`isolation: worktree`).** If
`isolation:` in `.sage/config.yaml` is `worktree` and this session is
in the main checkout (not a linked worktree), apply the **worktree
bounce** from git-discipline (offer `sage worktree <slug>` as a
guided menu) before branching in place. With `isolation: branch`
(default), ignore this — branch in place as below.

## Step 3: Brief (Standard with unclear scope, or Comprehensive)

If scope is unclear or the task is Comprehensive, elicit requirements
before defining the brief.

**If `autonomous_mode` is active** (from flag-parser): skip the
interactive elicitation rounds. Read
`sage/core/capabilities/orchestration/autonomous/SKILL.md` and follow
its pre-flight + decision protocol. Produce brief.md with a Rationale
block citing memory, codebase patterns, principles, and prior decisions.
If substantive unconfident decisions remain, surface them as a Zone 1
question block. Skip the rest of this step.

**Otherwise:**

For structured elicitation process, read
`sage/core/capabilities/elicitation/quick-elicit/SKILL.md`.
It provides 3 focused rounds (~2 minutes):
1. Intent — what should this do when working perfectly?
2. Boundaries — what should this NOT do?
3. Verification — how will we know it works?

If quick-elicit cannot be loaded, ask these three questions directly
and draft a brief from the answers.

Define: what to build, why, acceptance scenarios, and constraints.

Save to `.sage/work/YYYYMMDD-slug/brief.md` with frontmatter:

```yaml
---
title: "Brief description of the initiative"
status: in-progress
phase: brief
priority: high  # high | medium | low
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

🔒 **CHECKPOINT:**

Sage: Brief saved to .sage/work/YYYYMMDD-slug/brief.md
Decision: [key scope decisions]. (prepend to the initiative's decisions.md)

[A] Approve — continue to spec in this session
[R] Revise — tell me what to change
[N] New session — type /build to continue with spec

Pick A/R/N, or tell me what to change.

On approval: update brief frontmatter to `status: completed`.
Prepend decision to decisions.md (Rule 7).

## Step 4: Spec

Define: components, data model, APIs, key decisions, edge cases.
Resolve open questions from the brief.

**If `autonomous_mode` is active**: populate the spec using the
autonomous capability's decision protocol. Include a Rationale block
at the top of spec.md citing context sources. Surface unconfident
substantive decisions as Zone 1 questions before finalizing.

For detailed spec writing process, read
`sage/core/capabilities/planning/specify/SKILL.md`.

Save to `.sage/work/YYYYMMDD-slug/spec.md` with frontmatter:

```yaml
---
title: "Spec for [initiative]"
status: in-progress
phase: spec
priority: high
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

🔒 **CHECKPOINT:**
Sage: Spec saved to .sage/work/YYYYMMDD-slug/spec.md
Decision: [key technical decisions]. (prepend to the initiative's decisions.md)

[A] Review — sub-agent reviews spec, then continue to plan
[S] Skip review — approve without independent review
[R] Revise — tell me what to change
[N] New session — type /build to continue with planning

Pick A/S/R/N, or tell me what to change.

**On [A] Review:**
1. Update spec frontmatter to `status: completed`.
2. Write `handoff` field in frontmatter:
```yaml
handoff: |
  Key decisions: [summary of choices made]
  Open questions: [what's unresolved]
  Risks: [what to watch for during implementation]
  Next agent should: [specific guidance for planning phase]
```
3. Prepend decision to decisions.md (Rule 7).
4. **Run auto-review BEFORE proceeding to Step 5:**
   Read `sage/core/capabilities/review/auto-review/SKILL.md`.
   If conditions met (Task tool available + Standard+ scope +
   auto_review ≠ false in config):
     Announce: "⚡ Running spec review (sub-agent)..."
     Spawn sub-agent with the **Spec Review** prompt.
     Pass the spec path and decisions.md path.
     Present findings inline (see capability for format).
     Prepend review verdict to decisions.md.

     **If `quality_locked_mode` is active** (from flag-parser):
     Read `sage/core/capabilities/orchestration/quality-locked/SKILL.md`
     and run the review-revise loop instead of presenting findings to user.
     Loop until the checker's exit decision (v1: clean bar or cap 10,
     logged to manifest; `review_loop: v2`: the ledger controller —
     `review.py close-round` computes and records every verdict).
   If Task tool NOT available:
     Announce: "Task tool not available — skipping independent review."
5. THEN proceed to Step 5.

**On [S] Skip review:**
1. Update spec frontmatter, write handoff, append decision (same as above).
2. Announce: "Skipping independent review."
3. Log to decisions.md: "Spec approved without auto-review (user chose [S])."
4. Proceed to Step 5.

## Step 5: Plan

Break into small, independently testable tasks. Each task: what to do,
done criteria, files involved. Use checkboxes as a guide.

**If `autonomous_mode` is active**: decompose tasks using the autonomous
capability's decision protocol. Each task's rationale (ordering,
dependencies, scope) cites codebase patterns or prior plans where
relevant. Include a Rationale block at the top of plan.md.

For detailed planning process, read
`sage/core/capabilities/planning/plan/SKILL.md`.

Save to `.sage/work/YYYYMMDD-slug/plan.md` with frontmatter:

```yaml
---
title: "Plan for [initiative]"
status: in-progress
phase: plan
priority: high
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

🔒 **CHECKPOINT:**

Sage: Plan saved to .sage/work/YYYYMMDD-slug/plan.md

[A] Review — sub-agent reviews plan, then start building
[S] Skip review — approve without independent review
[R] Revise — tell me what to change
[N] New session — type /build to start implementation

Pick A/S/R/N, or tell me what to change.

**On [A] Review:**
1. Prepend plan approach to decisions.md (Rule 7).
2. **Run auto-review BEFORE proceeding to Step 6:**
   Read `sage/core/capabilities/review/auto-review/SKILL.md`.
   If conditions met (Task tool available + Standard+ scope +
   auto_review ≠ false in config):
     Announce: "⚡ Running plan review (sub-agent)..."
     Spawn sub-agent with the **Plan Review** prompt.
     Pass the plan path and spec path.
     Present findings inline.
     Prepend review verdict to decisions.md.

     **If `quality_locked_mode` is active**:
     Run the review-revise loop per `sage/core/capabilities/orchestration/quality-locked/SKILL.md`.
   If Task tool NOT available:
     Announce: "Task tool not available — skipping independent review."
3. THEN proceed to Step 6.

**On [S] Skip review:**
1. Prepend plan approach to decisions.md.
2. Announce: "Skipping independent review."
3. Log to decisions.md: "Plan approved without auto-review (user chose [S])."
4. Proceed to Step 6.

## Step 6: Implement

Execute the plan task by task.

**First, resolve the execution mode.** Do NOT read the `subagents` flag
directly — it is the one flag the platform is allowed to refuse:

```bash
python3 sage/runtime/tools/sage_flags.py parse "$ARGUMENTS" --config-path .sage/config.yaml
```

Then reconcile the request against what the platform can actually do
(`resolve_execution_mode()` in `sage_flags.py`, R97):

| Result | What runs |
|---|---|
| `mode: subagent` | **Read and follow `sage/core/workflows/sub-workflows/subagent-execution.workflow.md`.** A fresh implementer per task, a fresh reviewer per task, a branch review at the end. Record `execution_mode: subagent` in the manifest. |
| `mode: inline`, `degraded: false` | The inline build loop below. This is the default (C13). |
| `mode: inline`, `degraded: true` | The inline build loop — **and announce the degradation**, write the `decisions.md` line, and record `execution_mode: inline (subagents-unavailable)`. The user asked for independent per-task review and is not getting it; they are told so, in the session and in the log. |

A silent fallback here would mean a user who asked for per-task independent
review got one context reviewing its own work, with no indication. That is the
exact failure v1.2.x was spent eliminating.

### The inline build loop (default)

Read and follow `sage/core/capabilities/orchestration/build-loop/SKILL.md`.
It provides:
- Task-by-task execution with status reporting
- TDD discipline for each task (loads `sage/core/capabilities/execution/tdd/SKILL.md`)
- Scope guard to prevent drift (loads `sage/core/capabilities/context/scope-guard/SKILL.md`)
- Quality gates between tasks (loads `sage/core/workflows/sub-workflows/quality-gates.workflow.md`)
- Inter-task checkpoints every 1-3 tasks
- Escalation on repeated failure (3x → ask human)
- Context budget awareness (suggest new session if full)

If the build-loop cannot be loaded, follow these minimum rules:
implement one task at a time, write tests before code, run full
suite after each task, stay in scope, commit after each task.

If relevant Sage skills exist in `sage/skills/`, read and follow them.

**If stuck during implementation:** Activate the `problem-solving` skill.
Match the stuck pattern to a technique — complexity spiral → Simplification,
forced solution → Inversion, works-locally-but-fails → Scale Testing,
can't isolate → Minimal Reproduction.

## Step 7: Quality Gates

Run quality gates on the completed implementation.

Read and follow `sage/core/workflows/sub-workflows/quality-gates.workflow.md`.
It sequences 5 verification stages:
1. Spec compliance — does implementation match the plan? (adversarial)
2. Constitution compliance — does it respect project principles?
3. Code quality — clean, secure, maintainable?
4. Hallucination check — are all imports, APIs, versions real?
5. Verification — tests pass with pasted evidence?

Each gate that fails triggers fix-and-retry (max 3 attempts) or
escalation to the user.

If quality-gates cannot be loaded, follow these minimum rules:
run full test suite, paste output, verify implementation matches spec,
check for hallucinated imports or APIs.

Quality gates now include Gate 8 (Auto-QA) which runs automatically
as part of the gate sequence when Task tool is available. See
`quality-gates.workflow.md` for the full sequence including Gate 8.

## Step 8: Review and Close

Review against spec. Check for missed edge cases.

**Anti-deferral guard:** Before presenting the completion checkpoint,
verify ALL plan tasks are addressed. If any tasks remain incomplete,
do NOT present "Build complete." Instead:
1. List what's done and what remains
2. Explain why remaining tasks couldn't be completed
3. Ask the user: continue, pause, or adjust scope?
Never mark an initiative as complete with unfinished tasks, and never
defer planned work without the user's explicit decision.

🔒 **CHECKPOINT:**

Sage: Build complete. [summary of what was built]
Decision: [key implementation decisions]. (prepend to the
initiative's decisions.md)

[A] Approve — accept the work; branch stays unmerged
[M] Merge to [default] — user-gated merge per git-discipline
[R] Revise — here's what needs fixing
[V] Verify — type /review for independent verification

Pick A/M/R/V, or tell me what to change.

[M] is the ONLY merge path — [A] never merges. On [M], apply the
merge protocol from
`sage/core/capabilities/execution/git-discipline/SKILL.md` —
preconditions, the merge, conflict handling, and the deletion offer
all live there; do not restate them here. (No git repository or no
initiative branch → omit [M].)

**On approval — checkpoint state (Rule 7):**
1. **Apply the bookkeeping in ONE pass** — compose the summary, decisions, and
   completed-task list, then:
   ```bash
   python3 sage/runtime/tools/manifest.py close-out .sage/work/[initiative]/manifest.md \
     --summary "..." --next-step "..." --decision "completion: ..." \
     --complete-task 1 --complete-task 2 ... --phase complete
   ```
   Do not hand-edit manifest.md/decisions.md/plan.md incrementally — `updated:`
   and `gate_state` are machine-owned, and the command checks the plan boxes and
   prepends the decision for you (cycle-protocol.md § Resume close-out economy).
2. Update plan.md frontmatter: `status: completed`
3. Write `handoff` field in plan.md frontmatter with key decisions,
   open questions, and risks for the next agent
4. Store key findings in memory if sage-memory available — **except on a resume
   close-out with `resume_memory: skip` (default)**, where this is skipped: L2
   measured memory's value at this horizon as null (cycle-protocol.md § Resume
   close-out economy). First-session builds always store.
5. **Wiring check:** Verify all new components are connected — imports
   wired, routes registered, handlers hooked up, config entries added.
6. **Ontology update (if sage-memory available):** For significant new
   structure (new module, service, API endpoint, major component), create
   ontology entities and link them to existing graph. Skip for small
   changes within existing modules — only update when the codebase's
   *navigable structure* changed. Search ontology first to avoid dupes.
   (Also skipped on a resume close-out under `resume_memory: skip`.)

**Next steps (Zone 3):**

Next steps:
  /qa             — browser-based functional testing
  /design-review  — design quality audit
  /reflect        — review the cycle, extract learnings
  /review         — independent code evaluation

Type a command, or describe what you want to do next.

## Quality Criteria

**Communication style:** Engineering precision. Emphasize trade-offs,
edge cases, and implementation specifics. Reference file paths, function
names, and test results concretely.

Good build output:
- Implementation matches the spec — no undocumented deviations
- Tests exist for new functionality and pass — output pasted as evidence
- Edge cases from the spec are handled, not just happy paths
- Code follows project conventions (naming, structure, patterns)
- No unrelated changes mixed in — scope discipline maintained
- Verification output is from the actual test run, not a summary

## Self-Review

Before presenting completed work, check each criterion above. Also:
- Did I paste actual test output, or just claim tests pass?
- Did I run the FULL suite, or just the new tests?
- Are there spec requirements I didn't implement or test?

## Rules

- Spec before implementing (Rule 0 gate). DO NOT implement without
  an approved spec in .sage/work/.
- Tests before code (Base Principle 1). Write failing test first.
- Checkpoints mandatory (Rule 4). Present [A]/[R] and wait.
- Verify with evidence (Rule 5). Paste actual test output.
- Capture corrections (Rule 6). Store as self-learning.
- Record decisions at checkpoints (Rule 7). Prepend to decisions.md.
- Stay in scope — note improvements, don't add them.
- If stuck, use problem-solving skill. Don't retry the same approach.
