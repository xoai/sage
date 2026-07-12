---
name: context-packet
type: template
variant: subagent
version: "1.0.0"
description: >
  The context an implementer subagent gets, and the ONLY context it gets.
  Assembled by the orchestrator per task (R99). Structure adapted from
  obra/superpowers (MIT) — subagent-driven-development; Sage's version is built
  from the manifest ledger, the spec, and sage-memory rather than from a
  hand-written brief.
---

# Template

```markdown
# Context packet — Task {N}: {task title}

## Your task

{The plan task, VERBATIM. Do not paraphrase it into this packet — a paraphrase
is a second specification, and now there are two, and they disagree.}

**Deliverables (`Output:` from the plan):**
- {path} — {what it must contain}

## The spec says

{ONLY the spec excerpts this task cites or depends on. Not the whole spec.

The temptation is to paste the entire spec "just in case", and it defeats the
purpose: a fresh context that receives everything is not a fresh context, it is
the same context with extra steps and a higher bill.}

## Constraints

**From the plan header (global — apply to every task):**
- {constraint}

**From the constitution (the slice relevant to THIS task):**
- {principle} — {enforced by: hook/gate name, or "judgment"}

## What we already know

{sage-memory results for this task's keywords. Verbatim, with their titles, so
the subagent can weigh them.

If sage-memory is unavailable, this section reads exactly:
  "Memory unavailable — the MCP server did not respond. This packet was built
   without it; prior art on this task may exist and was not consulted."
Never omit the section silently. A missing section reads as "nothing to know",
which is a different and much more confident claim than "we could not check".}

## Files touched so far in this cycle

{From the ledger. This is how the subagent knows what its predecessors changed
without reading their transcripts.}

- {path} — task {N}, {one line on what changed}

## Files you may touch

{The task's declared files, plus tests. This list is CHECKED (R106): commits
that land outside it, beyond a small tolerance, are auto-flagged for review.

That is not an accusation. A task that genuinely needs a file outside this list
is a task whose plan was wrong, and the right move is to say so in your report
rather than to quietly widen the blast radius.}

## Definition of done

- [ ] A test exists for this behavior and it FAILED before the implementation
- [ ] The test passes now
- [ ] The full suite passes
- [ ] The deliverables above exist and contain what the spec says they contain
- [ ] Your report includes pasted test output, not a summary of it
```

# Rules

## Completeness contract

WHEN: The orchestrator dispatches an implementer subagent.
CHECK: Every section above is present. Sections with nothing in them say so
       explicitly ("Memory unavailable — …", "No files touched yet") rather
       than being dropped.
BECAUSE: The subagent has no other context. It cannot ask a follow-up question,
         it cannot read the conversation that produced the plan, and it cannot
         tell the difference between "this section is empty because there is
         nothing to say" and "this section is missing because the orchestrator
         forgot". A dropped section is indistinguishable from an empty one, and
         one of those two meanings is false.

BLOCKED RATIONALIZATIONS:
- "The subagent can read the spec file itself" — it can, and then it has read the
  whole spec, and the context isolation you were paying for is gone.
- "Memory was empty anyway" — then the section says memory was empty. That is a
  finding. Silence is not.
- "It'll figure out which files it can touch" — it will figure out SOMETHING, and
  R106 will flag it, and you will have spent a review cycle on a question the
  packet could have answered for free.

## Minimality contract

WHEN: Assembling the spec excerpt and memory sections.
CHECK: Include what THIS task cites. Not the whole spec, not every memory hit.
BECAUSE: Fresh context per task is the entire mechanism. Its value is that the
         implementer is not carrying six tasks' worth of accumulated reasoning,
         half-abandoned approaches, and stale assumptions. A packet that grows
         to include everything reproduces exactly the state you dispatched a
         subagent to escape — at a higher cost, because now you are paying for
         it once per task.
