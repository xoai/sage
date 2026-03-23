---
name: reflect
version: "1.0.0"
mode: reflect
produces: ["Cycle review", "Learnings with prevention rules", "Next-cycle seeds"]
checkpoints: 2
scope: "Single session"
user-role: "Provide real-world feedback, approve learnings before storage"
---

# Reflect Workflow

Look back. Extract learnings. Seed the next cycle.

## Auto-Pickup

Scan `.sage/work/` for recently completed initiatives
(status: completed in frontmatter). Scan `.sage/docs/` for
research and analysis artifacts. Read `.sage/decisions.md`
for the full decision trail.

If no completed work exists: "Sage: No completed initiatives
found. /reflect works best after a deliver cycle. Describe
what you want to reflect on, or type / for other commands."

## Step 1: Review the Cycle (Zone 1)

Sage → reflect workflow. Looking back at what was done.

[1] Full initiative — review the entire cycle for [initiative name]
[2] Recent work — reflect on the last few decisions
[3] Specific topic — describe what you want to reflect on

Pick 1-3, type / for commands, or describe what you need.

**For full initiative review, gather and present:**

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

## Step 2: Evaluate Outcomes

Ask the user for real-world feedback. This is the human input
Sage cannot generate — the signal from reality.

Sage: Now I need your perspective on how this went.

[1] What worked well? (What should we do again?)
[2] What didn't work? (What caused friction or rework?)
[3] What surprised you? (What was unexpected?)
[4] What feedback have you received? (From users, team, stakeholders)

Share any or all — or describe your overall assessment.

Pick 1-4, type / for commands, or describe what you need.

Listen to the user's responses. Ask follow-up questions if
the feedback is vague — specifics make better prevention rules.

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

🔒 **LEARNINGS CHECKPOINT (Zone 2):**

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

## Step 4: Store and Update

On approval:

1. **Store each learning** via sage_memory_store with tags:
   `self-learning`, `reflect`, `[initiative-slug]`, and
   category tag (`reinforce`, `prevent`, or `improve`).

2. **Update conventions.md** if any learning revealed a project
   pattern that should become a convention. Announce what was
   added.

3. **Save reflection report** to `.sage/docs/reflect-[slug].md`
   with the full cycle review, user feedback, and learnings.

4. **Append to decisions.md:**
   ```
   ### YYYY-MM-DD — Reflection: [initiative/topic]
   [Summary of key learnings and what changes going forward.]
   ```

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
- User feedback is required. Don't generate learnings from the
  cycle review alone — the real-world signal matters most.
- WHEN/CHECK/BECAUSE is mandatory for every learning.
- Store learnings with `self-learning` + `reflect` tags so Rule 0
  memory search finds them in future cycles.
- Save the reflection report to .sage/docs/ — it's a permanent
  artifact, not a transient conversation.
- Seeding the next cycle is not optional. The value of reflection
  is in what changes going forward, not in the act of looking back.
