---
name: reflect
version: "1.0.0"
mode: reflect
produces: ["Cycle review", "Learnings with prevention rules", "Next-cycle seeds"]
checkpoints: 2
scope: "Single session"
user-role: "Provide only unobserved external signals; approve in interactive mode"
---

# Reflect Workflow

Look back. Extract learnings. Seed the next cycle.

## Invocation Modes

- **Evidence mode (`--evidence`, default):** use the transcript, normalized
  event log, tool outcomes, explicit corrections, artifacts, verification
  outcomes, and prior learnings recalled or created during the run. Do not ask
  the user to restate evidence the agent already observed.
- **Interactive mode (`--interactive`):** retain the questionnaire and
  learnings approval checkpoint for a user who wants a guided retrospective.

User feedback is conditional in evidence mode. Ask only when a claim depends
on an **unobserved external outcome**, **personal preference**, or
**stakeholder signal** that is absent from the run evidence.

## Auto-Pickup

Scan `.sage/work/` for recently completed initiatives
(status: completed in frontmatter). Scan `.sage/docs/` for
research and analysis artifacts. For the decision trail, read the
initiative's own log first —
`.sage/work/[initiative]/decisions.md` — then fall back to the
global `.sage/decisions.md` (cross-initiative decisions live
there; older projects may have only the global file).

If no completed work exists: "Sage: No completed initiatives
found. /reflect works best after a deliver cycle. Describe
what you want to reflect on, or type / for other commands."

## Step 1: Review the Cycle and Evidence (Zone 1)

Sage → reflect workflow. Looking back at what was done.

[1] Full initiative — review the entire cycle for [initiative name]
[2] Recent work — reflect on the last few decisions
[3] Specific topic — describe what you want to reflect on

Pick 1-3, type / for commands, or describe what you need.

**For full initiative review, gather and present:**

Before presenting, gather every available evidence source: transcript, event
log, tool outcomes and recoveries, explicit corrections, artifacts and
decisions, verification results, and prior learnings recalled or created.

Sage: Cycle review for [initiative name].

Timeline:
  [Date] — Brief approved: [summary]
  [Date] — Spec approved: [key decisions]
  [Date] — Plan: [N] tasks planned
  [Date] — Build complete: [what was shipped]

Decisions made: [count from decisions.md]
Approaches tried: [count from scratch.md if exists]
Learnings stored: [count from self-learning entries]

Key artifacts:
  .sage/work/[initiative]/brief.md
  .sage/work/[initiative]/spec.md
  .sage/docs/[related research/analysis]

## Step 2: Classify Evidence Gaps

In evidence mode, classify each proposed claim as observed or externally
unresolved. Do not ask the user to restate tool output, corrections, artifacts,
decisions, or verification already present in the run.

Ask for feedback only for an unobserved external outcome, personal preference,
or stakeholder signal. If none exists, continue directly to Step 3.

In interactive mode, ask the original guided questions:

Sage: Now I need your perspective on how this went.

[1] What worked well? (What should we do again?)
[2] What didn't work? (What caused friction or rework?)
[3] What surprised you? (What was unexpected?)
[4] What feedback have you received? (From users, team, stakeholders)

Share any or all — or describe your overall assessment.

Pick 1-4, type / for commands, or describe what you need.

Listen to the user's responses. Ask follow-up questions only when the external
signal is necessary to make a claim evidence-backed.

## Step 3: Extract Learnings

Based on the cycle review + user feedback, identify learnings
in three categories:

**Reinforce** — what went well and should become standard practice.
**Prevent** — what went wrong and should be avoided next time.
**Improve** — what could be better with a specific change.

For each learning, write a WHEN/CHECK/BECAUSE prevention rule:

```
WHEN: [situation that triggers this learning]
CHECK: [observable condition to verify]
BECAUSE: [what happens if you don't — the consequence]
```

**Learnings quality check (before presenting):**
- Specific? Names concrete situations, not vague patterns.
- Actionable? A future agent could apply this without context.
- Has a CHECK? Observable condition, not self-assessment.
If a learning fails any criterion, improve it before presenting.

🔒 **LEARNINGS CHECKPOINT (Zone 2, interactive mode):**

Sage: Learnings extracted from [initiative/topic].

Reinforce:
  1. [Learning] — WHEN/CHECK/BECAUSE
  2. [Learning]

Prevent:
  1. [Learning] — WHEN/CHECK/BECAUSE
  2. [Learning]

Improve:
  1. [Learning] — WHEN/CHECK/BECAUSE

[A] Approve — store learnings  [R] Revise  [N] New session

Pick A/R/N, or tell me what to change.

In evidence mode, the quality check replaces mandatory user approval. Continue
when every claim is grounded in cited run evidence. It is valid to conclude
that there is no novel learning to store.

## Step 4: Store and Update

After the interactive approval, or immediately after the evidence-mode quality
check:

1. **Delegate every proposed learning through the canonical
   `sage-self-learning` skill — one invocation per candidate.** Pass its
   evidence references and category tags (`reflect`, `[initiative-slug]`, and
   `reinforce`, `prevent`, or `improve`). The canonical skill must classify the
   learning, author the four-part What happened / Why wrong / What's correct /
   Prevention rule record, perform search-before-store, enrich or update an
   equivalent record, invalidate and link a correction when an old rule is
   wrong, and link the result to relevant tasks, modules, technologies, or code
   memories. Reflect must not write directly to a learning backend.

2. **Update conventions.md** if any learning revealed a project
   pattern that should become a convention. Announce what was
   added.

3. **Save reflection report** to `.sage/docs/reflect-[slug].md`
   with the full cycle review, user feedback, and learnings.

4. **Prepend to decisions.md:**
   ```
   ### YYYY-MM-DD — Reflection: [initiative/topic]
   [Summary of key learnings and what changes going forward.]
   ```

5. **Acknowledge the lifecycle request** when the injected reflection context
   supplies runtime commands. After the report and all delegated learning
   writes finish, run the provided `reflection complete` command with the
   actual stored and novel-candidate counts. Zero is a valid result. If the
   reflection is deliberately inapplicable or cannot proceed, run the provided
   `reflection skip` command with an evidence-based reason. Never leave a
   requested reflection pending silently.

## Step 5: Seed the Next Cycle (Zone 3)

The most powerful step — connect learnings to future work.

Sage: Reflection complete. [N] learnings stored.

Seeds for next cycle:
  [Specific recommendation based on learnings, e.g.,
  "Start with payment edge case research next time —
  this area took 3x longer than expected."]

Report: .sage/docs/reflect-[slug].md

Next steps:
  /research — start the next initiative (learnings loaded via Rule 0)
  /build    — spec → plan → implement → verify
  /design   — brief → spec → copy

Type a command, or describe what you want to do next.

## Quality Criteria

Good reflection output:
- Cycle review is factual — dates, decisions, artifacts, not summaries
- User feedback is captured in their words, not paraphrased away
- Every learning has WHEN/CHECK/BECAUSE format
- Learnings are specific enough for a different agent to apply
- Next-cycle seeds are concrete recommendations, not generic advice
- The reflection report is saved as a permanent artifact

## Rules

- Reflect is for LOOKING BACK, not for fixing. If the reflection
  reveals something to fix, suggest /fix. Don't fix during reflect.
- Evidence mode is the default. User feedback is required only for an
  unobserved external outcome, personal preference, or stakeholder signal.
- Interactive mode retains the questionnaire and approval checkpoint.
- Do not ask the user to restate transcript, event log, tool outcomes,
  corrections, artifacts, verification, or prior learnings.
- WHEN/CHECK/BECAUSE is mandatory for every learning.
- Delegate every candidate to the canonical `sage-self-learning` skill; reflect
  never authors or stores an ad hoc learning itself.
- When a lifecycle acknowledgment command is supplied, complete or skip it
  after the reflection work; do not acknowledge completion early.
- Save the reflection report to .sage/docs/ — it's a permanent
  artifact, not a transient conversation.
- Seeding the next cycle is not optional. The value of reflection
  is in what changes going forward, not in the act of looking back.
