---
name: manifest
type: manifest
version: "1.0.0"
description: >
  Cycle manifest — single source of truth for cycle state, context summary,
  and handoff guidance. Created at first checkpoint, updated at every gate.
  Read by /continue and Auto-Pickup for session resumption.
---

# Template

```markdown
---
cycle_id: "YYYYMMDD-slug"
workflow: build | architect | fix | research | design | analyze | reflect
phase: framing | brief | spec | plan | implement | quality-gates | review | complete
status: in-progress | paused | blocked | complete
created: YYYY-MM-DD
updated: YYYY-MM-DD HH:MM
---

# Cycle: {title}

## State

**Current phase:** {phase} — {what's happening in this phase}
**Next step:** {concrete next action when resumed}
**Artifacts:**
- brief.md: {exists | missing | not-required}
- spec.md: {exists | missing | not-required}
- plan.md: {exists | missing | not-required}
- implementation: {not-started | in-progress (N/M tasks) | complete}
- quality-gates: {not-run | passed | failed (which gate)}
- qa-report.md: {exists — verdict | not run}
- design-review.md: {exists — N issues, M warnings | not run}

## Context summary

{2-5 sentences. What a cold-start agent needs to know to resume
with good judgment, not just mechanical compliance.

Include:
- Why this cycle exists (the pain, from Round 0 framing)
- The key trade-off or design choice that shapes everything
- What the user cares about most
- Anything surprising or non-obvious about the approach

Exclude:
- Anything already in spec.md or plan.md (don't duplicate)
- Implementation details (the code speaks for itself)
- Generic statements ("The user wants high quality")

Max 200 words.}

## Decisions so far

{Bulleted list of key decisions from decisions.md for this cycle.
Not all entries — just the ones that affect how a resuming agent
should behave.}

## Open questions

{What's unresolved. What the previous agent was thinking about but
didn't get to decide. What the user seemed uncertain about.}

## Provenance

{Git provenance — populated by git commands at every manifest write.

Before writing this section, run: `git rev-parse --git-dir 2>/dev/null`

IF git is available (exit code 0):

| Key | Value |
|-----|-------|
| Repo | `[git remote get-url origin]` |
| Branch | `[git branch --show-current]` |
| Commit | `[git rev-parse --short HEAD]` |
| Working tree | `[clean or dirty — from git status --porcelain]` |

IF git is NOT available (exit code ≠ 0, or no .git directory):

Git: not available (project is not a git repository)

Values MUST come from fresh git commands, not memory or previous manifests.
Git absence is normal — write "Git: not available" and move on.}

## Handoff guidance

{Specific instructions for the next agent. Not generic advice —
concrete, natural-language judgment in 2+ sentences.

The handoff MUST contain information NOT present in spec.md, plan.md,
or decisions.md — specifically: user priorities inferred from
conversation tone, constraints mentioned verbally but not formally
captured, and your judgment about what matters most next.

Good example:
  "Create the implementation plan from the approved spec. The user
  specifically requested that the scoring model be reusable across
  listing types — this isn't in the spec but was stated during
  Round 2 elicitation. The user's tone suggested this is a strong
  preference, not a nice-to-have. Start by reading spec.md Section 3
  and the scoring model constraint in decisions.md entry #2."

Bad examples (contract violations):
  - "Continue with implementation."
  - "See spec.md for next steps."
  - A bullet list that restates the spec's requirements.

Max 150 words.}
```

# Rules

## Provenance contract

WHEN: Manifest is written or updated (every manifest write — checkpoints,
      session breaks, and any other manifest update)
CHECK: Agent MUST run `git rev-parse --git-dir 2>/dev/null` to detect
       whether the project uses git.

       IF git is available AND project is a git repository:
         Provenance section MUST contain non-empty Repo, Branch,
         Commit, and Working tree values.
         Values MUST be obtained from git commands, not from memory.

       IF git is NOT available OR project is NOT a git repository:
         Provenance section MUST contain: "Git: not available"
         or "Git: not a repository".
         The manifest remains valid. No workflow is blocked.
         No error, no warning — this is normal and expected.

       Git absence MUST NEVER:
         - Block manifest creation
         - Block /continue or Auto-Pickup
         - Trigger an error or warning to the user
         - Cause any workflow to behave differently
         Sage works identically with or without git. Provenance is
         additive context when available, not a dependency.

BECAUSE: Provenance adds verification value when git exists —
         it lets the next agent confirm it's on the same branch
         and commit. But provenance is supplementary to the
         manifest's core purpose (context transfer). A non-git
         project still needs manifests, handoff guidance, and
         session resilience. Git absence must never block these.

BLOCKED RATIONALIZATIONS:
- "We're on the main branch, provenance is obvious" — obvious to you,
  not to the next agent instance. Write it.
- "Git state hasn't changed since last checkpoint" — git state can
  change between sessions (other devs, CI, rebases). Capture it fresh.
- "Git isn't set up yet, I'll add provenance later" — write
  "Git: not available" now. Don't leave the section empty.

## Manifest before session break contract

WHEN: Session is ending (user says stop, context budget pressure,
      [N] selected at any checkpoint)
CHECK: manifest.md MUST exist in `.sage/work/[cycle-id]/` with
       updated phase, status, context summary, and handoff guidance.
       The manifest MUST be written BEFORE the session ends.
BECAUSE: If context is lost without a manifest, the next agent
         starts cold. The manifest is the bridge between sessions.

BLOCKED RATIONALIZATIONS:
- "The user didn't ask for a session break" — context budget pressure
  is a session break whether the user asked or not.
- "I'll finish this task first, then write the manifest" — if you run
  out of context mid-task, the manifest doesn't exist. Write it NOW.
- "There's nothing important to capture" — that assessment is the
  rationalization. Write what you know; the next agent decides what's
  important.

## Anti-lazy-manifest contract

Context summary MUST NOT be:
- A copy of the spec's title or description
- "See spec.md for details"
- Generic guidance ("Continue with implementation")

The context summary must contain information that is NOT already
present in spec.md, plan.md, or decisions.md. It captures
**judgment**, not facts.

BLOCKED RATIONALIZATIONS:
- "The spec already captures everything" — the manifest captures judgment,
  not facts. What the spec doesn't say is what matters most.
- "I'll update the manifest later" — later means never. Context is freshest
  now, at the checkpoint.
- "The conversation history is enough" — conversation is ephemeral.
  The next agent gets a fresh context window. Disk is truth.
- "This is a short session, no manifest needed" — session length doesn't
  predict whether context will be lost. Write it anyway.
- "The git diff shows what changed" — diffs show what, not why.
  The manifest captures the reasoning the diff can't.

## Handoff guidance contract

WHEN: Handoff guidance is written
CHECK: Handoff guidance MUST be a natural-language paragraph (not a
       one-liner). It MUST contain information that is NOT present
       in spec.md, plan.md, or decisions.md — specifically: user
       priorities inferred from conversation tone, constraints
       mentioned verbally but not formally captured, and the agent's
       judgment about what matters most for the next step.
       The guidance MUST be 2+ sentences.
BECAUSE: A handoff that says "continue with implementation" adds
         nothing. The value is capturing what the artifacts don't:
         the reasoning, the user's implicit priorities, the
         non-obvious context.

BLOCKED RATIONALIZATIONS:
- "The spec captures everything" — specs capture requirements,
  not judgment. Write the judgment.
- "Next step is obvious from the phase" — obvious to you,
  in your current context window. The next agent starts fresh.
- "I'll write detailed guidance later" — later is a fresh context
  window. The judgment you have now will be gone.
- "The manifest is already long enough" — handoff guidance is the
  highest-value section. Length elsewhere should shrink, not this.
- "The user didn't mention anything beyond the spec" — then write
  what you observed: their tone, their priorities, what they
  emphasized. That IS the guidance.

## Size constraints

- Context summary: 2-5 sentences, max 200 words
- Handoff guidance: 1-4 bullet points, max 150 words

If summary is longer → it's trying to replace the spec.
If guidance is longer → the cycle needs a spec update, not notes.
