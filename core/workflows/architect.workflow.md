---
name: architect
version: "1.1.0"
mode: architect
produces: ["Architecture Decision Records", "System spec", "Milestone plan"]
checkpoints: 3
scope: "Multi-session"
user-role: "Review and approve design decisions at each gate"
---

# Architect Workflow

System design for new projects or major redesigns.
Elicit, then design, then plan. Never skip steps.

## Auto-Pickup

Scan `.sage/work/` for architect initiatives.
This scan is MANDATORY — check the DISK.

**Manifest-first path:** If `.sage/work/*/manifest.md` exists with
`workflow: architect`, read it. Resume at the phase indicated.
Use context summary and handoff guidance for judgment context.
Multi-session architect cycles benefit most from the manifest —
it preserves the reasoning behind architecture decisions across sessions.

**Fallback path:** If no manifest.md but artifacts exist, use file-scan:
- No artifacts → Step 2 (elicitation)
- Brief exists, no spec/ADRs → Step 3 (design)
- Spec/ADRs exist, no plan → Step 4 (milestone plan)
- Plan exists → Step 5 (phased build)
Create manifest.md from inferred state before proceeding (backfill).

You MUST follow this routing. Do not override it.

Scan `.sage/docs/` for existing research, ADRs, or decisions.
Read `.sage/decisions.md` for context. Read `handoff` field in
the most recent artifact if present.

### Manifest Lifecycle (architect workflow)

**Create** manifest.md when brief.md is saved (after elicitation).
**Update** at every checkpoint: elicitation gate, design checkpoint,
plan checkpoint, each milestone completion.
**Session end ([N]):** Manifest update is MANDATORY — architect cycles
span sessions, so handoff guidance is critical.
**Completion:** Set `status: complete` after final milestone.
**Anti-lazy-manifest:** Same contract as build workflow — summary must
contain judgment, not spec titles.

## Phase Announcements

At each major phase transition, announce before doing any phase work:

```
Sage: Entering UNDERSTAND phase [cycle-id] — gathering requirements via deep-elicit.
Sage: Entering PLAN phase [cycle-id] — creating architecture design and ADRs.
Sage: Entering DELIVER phase [cycle-id] — implementing milestones with quality gates.
Sage: Entering REVIEW phase [cycle-id] — validating architecture against implementation.
```

The cycle ID is the directory name under `.sage/work/` (e.g., `20260324-platform-redesign`).

## Step 2: Deep Elicitation

This is the most important step. Understand the full picture before
designing anything.

For comprehensive elicitation process, read
`sage/core/capabilities/elicitation/deep-elicit/SKILL.md`.

**Three rounds — each produces a VISIBLE ARTIFACT:**

**Round 1 — Vision:** What are you building and why? Who is it for?
What does success look like?
→ Produce: vision summary (saved inline in brief or presented)

**Round 2 — Constraints:** Technical constraints, timeline, team size,
existing systems to integrate with, non-negotiables.
→ Produce: constraints list (saved inline in brief or presented)

**Round 3 — Gaps:** What's still unclear? What assumptions are we making?
→ Produce: gaps analysis (saved inline in brief or presented)

Save combined elicitation to `.sage/work/YYYYMMDD-slug/brief.md`.

**Do NOT proceed to design until all three rounds are complete.**
Do NOT compress three rounds into one response.
Do NOT skip rounds because "the user already explained everything."
Each round asks different questions — answers to Round 1 don't
satisfy Round 2 or 3.

If Sage has relevant UNDERSTAND skills (research, analysis), recommend
them here:

Sage recommends understanding the context before designing:

[1] Start with research — understand user needs first
[2] Continue with elicitation round [N]
[3] Something else

🔒 **ELICITATION GATE:**

**File check:** Does `.sage/work/*/brief.md` exist with content
from all three rounds (vision, constraints, gaps)?
If no → complete the missing rounds. Do NOT proceed to design.

Do NOT rationalize skipping:
- "The user described the system clearly" → NOT three-round elicitation
- "I understand the requirements" → your understanding is not a brief file
- "We can figure out details during design" → gaps analysis exists to
  catch exactly this. Do it now, not during design.

Sage: Elicitation complete. Brief saved.

[A] Approve — continue to architecture design
[R] Revise — I want to add or change something
[N] New session — type /architect to continue with design

Pick A/R/N, or tell me what to change.

## Step 3: Architecture Design

**File check:** `.sage/work/*/brief.md` MUST exist before designing.
If it doesn't exist, go back to Step 2. No exceptions.

Define: system components, data model, API boundaries, technology choices,
deployment architecture, security model. Document key trade-offs and
the reasoning behind each decision.

Save architecture decisions to `.sage/docs/decision-*.md`.
Save the full design to `.sage/work/YYYYMMDD-slug/spec.md` with frontmatter.

🔒 **DESIGN CHECKPOINT:**

**Self-check (observable conditions):**
- [ ] brief.md exists in .sage/work/ (elicitation was completed)
- [ ] spec.md exists in .sage/work/ (design was written)
- [ ] At least one decision-*.md exists in .sage/docs/ (ADRs written)
- [ ] Trade-offs are named for each major decision
If ANY fails → go back and create the missing artifact.

Sage: Architecture design saved. ADRs in .sage/docs/decision-*.md
Decision: [key architecture decisions]. (append to .sage/decisions.md)

[A] Approve — continue to planning in this session
[R] Revise — here's what needs changing
[Q] Question — I want to understand [specific decision] better
[N] New session — type /architect to continue with milestone plan

Pick A/R/Q/N, or tell me what to change.

On approval: update spec frontmatter to `status: completed`.
Write `handoff` field in frontmatter:
```yaml
handoff: |
  Key decisions: [architecture choices and trade-offs]
  Open questions: [what needs resolution during build]
  Risks: [cross-cutting concerns, performance, migration]
  Next agent should: [specific guidance for milestone planning]
```
Append architecture decisions to decisions.md (Rule 7).

⚡ **AUTO-REVIEW: Architecture / ADR**

After design approval, run an independent sub-agent review.
Read `sage/core/capabilities/review/auto-review/SKILL.md`.

If conditions met (Task tool available + auto_review ≠ false):
  Spawn sub-agent with the **ADR / Architectural Spec Review** prompt.
  Pass the ADR path(s) and brief path.
  Present findings inline.
  If CRITICAL: recommend [R] Revise before planning.
  If no CRITICAL: note findings, continue to Step 4.
  Append review verdict to decisions.md.
If conditions not met: skip silently.

## Step 4: Milestone Plan

**File check:** `.sage/work/*/spec.md` MUST exist with `status: completed`
before creating a milestone plan. If it doesn't → go back to Step 3.

Break the build into milestones (not tasks — milestones). Each milestone
should be deployable and testable independently. Within each milestone,
create a task plan.

Save to `.sage/work/YYYYMMDD-slug/plan.md` with frontmatter.

🔒 **PLAN CHECKPOINT:**
Sage: Milestone plan saved to .sage/work/YYYYMMDD-slug/plan.md

[A] Approve — start building milestone 1 in this session
[R] Revise — adjust the breakdown
[N] New session — type /build to start milestone 1

Pick A/R/N, or tell me what to change.

On approval: append plan approach to decisions.md (Rule 7).

⚡ **AUTO-REVIEW: Milestone Plan**

After plan approval, run an independent sub-agent review.
Read `sage/core/capabilities/review/auto-review/SKILL.md`.

If conditions met (Task tool available + auto_review ≠ false):
  Spawn sub-agent with the **Plan Review** prompt.
  Pass the plan path and spec path.
  Present findings inline.
  If CRITICAL: recommend [R] Revise before building.
  If no CRITICAL: note findings, continue.
  Append review verdict to decisions.md.
If conditions not met: skip silently.

**Next steps (Zone 3):**

Next steps:
  /build   — spec → plan → implement → verify (start milestone 1)
  /review  — independent evaluation of the architecture
  /reflect — review design decisions before building

Type a command, or describe what you want to do next.

## Step 5: Phased Build

Execute milestone by milestone. **Each milestone MUST follow the build
workflow gates independently:**

For each milestone:
1. Create milestone-specific spec if the milestone adds new details
   beyond the architecture spec
2. Create milestone task plan
3. Implement via build-loop with quality gates per task
4. Verify milestone independently (tests pass, feature works)
5. Present milestone checkpoint

Do NOT batch-implement multiple milestones without checkpoints.
Do NOT skip per-milestone verification because "I'll test everything
at the end."

**At each milestone completion checkpoint:**
Sage: Milestone [N] complete — [summary]
Decision: [what was learned during implementation]. (append to decisions.md)

[C] Continue to milestone [N+1]
[R] Revise — adjust before continuing
[P] Pause — type /build to continue next session

**Re-validate after each milestone:** Check architecture assumptions
against what implementation revealed. If the architecture needs
adjustment, note it in decisions.md and update ADRs before proceeding.

## Quality Criteria

**Communication style:** Systems thinking. Name trade-offs explicitly,
discuss failure modes, and explain decisions in terms of constraints
and alternatives considered.

Good architecture output:
- Trade-offs are named explicitly — no trade-offs = not deep enough
- Failure modes addressed for every integration point
- System boundaries are clear — what's in scope, what's external
- Each milestone is independently deployable and valuable

## Rules

- Elicitation before design. brief.md MUST EXIST before spec.md is
  created. "I understand the requirements" is NOT a brief file.
- Three elicitation rounds. Do NOT compress or skip rounds.
- Decisions documented with rationale. ADRs in .sage/docs/.
- Checkpoints mandatory. Present [A]/[R] and wait.
- Milestones build independently. Each follows build workflow gates.
- Re-validate after each milestone. Architecture assumptions may
  be wrong — implementation reveals truth.

## Failure Modes

- **Agent skips elicitation:** "I already understand the system."
  The elicitation gate blocks this — brief.md must exist.
- **Agent compresses rounds:** One response covering all three rounds
  misses the back-and-forth that catches gaps. Rounds must be
  sequential with user input between them.
- **Agent batch-implements milestones:** "I'll build all three
  milestones in one pass." Each milestone needs its own checkpoint.
- **Architecture assumptions survive implementation:** The re-validate
  step after each milestone catches stale assumptions.
