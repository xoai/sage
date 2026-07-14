---
name: manifest
type: manifest
variant: standard
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
blocked_on: ""          # REQUIRED when status: blocked — the question, the
                        # options, and whose call it is. manifest.py check fails
                        # a blocked cycle without it: a blocker nobody can name
                        # is a hesitation the next session inherits as law.
tier: standard          # tier1 | standard | large — scope of the cycle
gate_state: pre-spec    # pre-spec | spec-approved | plan-approved | building | gates-passed | complete
created: YYYY-MM-DD
updated: YYYY-MM-DD HH:MM
execution_mode: inline       # inline | subagent | inline (subagents-unavailable)
flags:
  quality_locked: false        # resolved value (flag or config-default)
  autonomous: false            # resolved value (flag or config-default)
  subagents: false             # resolved value (flag or config-default)
tasks: []                      # the task ledger — subagent execution only (R101).
                               # Omit entirely in inline mode; an absent ledger
                               # disables the gates-passed guard, which is what
                               # keeps pre-1.3.0 cycles working.
quality_locked_history: []     # per-checkpoint review/revise iterations (when active)
autonomous_decisions: []       # per-phase counts of decisions made vs asked (when active)
auto_picked_checkpoints: []    # checkpoints auto-resolved when both flags active;
                               # each entry has phase, decision, timestamp, reason,
                               # and flag_sources: { quality_locked: flag|config,
                               #                    autonomous: flag|config }
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

## Task ledger

{Subagent execution only. Omit this section entirely in inline mode.

The machine-readable copy lives in the frontmatter `tasks:` block; this is the
human-readable view of the same thing.

| Task | Status | Attempts | Review | Commits |
|---|---|---:|---|---|
| 1 — {title} | done | 1 | approved | `abc1234..def5678` |
| 2 — {title} | in-progress | 2 | pending | — |

A task is FINISHED when an independent reviewer approved it — not when the
implementer said it was done. Those are different claims, they are recorded in
different columns, and the spec-gate hook will not let the cycle reach
`gate_state: gates-passed` while they disagree.

The attempts column is the one to read at the end. A task with three implementer
attempts and two review rounds is usually not a task that was hard — it is a task
whose PLAN was wrong, and the branch reviewer is told to say so.}

## Decisions so far

{Bulleted list of key decisions from decisions.md for this cycle.
Not all entries — just the ones that affect how a resuming agent
should behave.}

## Open questions

{ONLY questions the artifacts do not answer. Never restate a question a
recorded decision already answers — cite the decision instead; if a decision
sanctions several options, choosing among them is the resuming agent's job,
not an open question. These lines are judgment, not orders: they expire
against decisions.md and the live user (see cycle-protocol.md § Resume
authority order).}

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

## Flag state

{If `flags.quality_locked` or `flags.autonomous` is true, summarize
the current effect:

- `--quality-locked`: review/revise iterations so far, per checkpoint
- `--autonomous`: total decisions made autonomously, total asked back
- Auto-picked checkpoints (only when BOTH flags active): list each
  with phase, decision, and timestamp. Cross-reference decisions.md
  entries for the long-form audit trail.

If both flags are false, omit this section entirely.}

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

## Task ledger contract (R101, subagent execution)

WHEN: A cycle runs under subagent execution (`execution_mode: subagent`).
CHECK: The frontmatter carries a `tasks:` ledger, one entry per plan task, each
       with `id`, `status` (pending|in-progress|done|blocked), `attempts`,
       `review` (pending|approved|findings), and `commits` (the range).
       The cycle may not reach `gate_state: gates-passed` while any entry is not
       BOTH `status: done` AND `review: approved`.

BECAUSE: The orchestrator does not write the code and does not read the diffs. It
         has exactly one source of truth about what happened inside its
         subagents, and this is it. If the ledger can say "done" on the strength
         of an implementer's own report, then the independent review that
         justifies the entire cost of subagent execution is optional — and the
         thing you paid a whole extra context per task for is a formality.

         `gates-passed` is the guarded transition rather than `complete` because
         gates-passed is the state that ASSERTS the quality chain ran. A cycle
         that reaches it with an unreviewed task has already made a false claim,
         and that claim is then read as true by /continue, by the branch
         reviewer, and by the next session.

BLOCKED RATIONALIZATIONS:
- "The implementer said it was done and its tests passed" — the implementer is
  the one agent in the system that cannot review its own work, which is why it
  was given a reviewer.
- "The reviewer only had Minor findings, so it's approved" — Minor findings do
  not block, and `review: approved` is what records that. Write it down.
- "It's a small task" — then the review is cheap. This is not the argument you
  think it is.
- "I'll fill in the ledger at the end" — a ledger written from memory at the end
  is a story about what happened, not a record of it.

## Machine state contract (tier, gate_state)

WHEN: The manifest is created or updated at any checkpoint.
CHECK: `tier` and `gate_state` are set to values a tool can read without
       parsing prose. They are maintained alongside `phase`/`status`, not
       instead of them — `phase` is for humans and `/continue`; `gate_state`
       is the single machine-readable answer to "may implementation proceed?"

       `gate_state` advances monotonically through the cycle:

       | Transition (checkpoint)                | gate_state      |
       |----------------------------------------|-----------------|
       | manifest created (framing / brief)     | `pre-spec`      |
       | spec approved `[A]`                     | `spec-approved` |
       | plan approved `[A]`                     | `plan-approved` |
       | build-loop entered                      | `building`      |
       | all quality gates passed                | `gates-passed`  |
       | completion checkpoint (Step 8 / final)  | `complete`      |

       `tier` records scope: `tier1` (trivial — no manifest is created at all,
       see below), `standard`, or `large`.

BECAUSE: The Claude Code spec-gate hook
         (`runtime/platforms/claude-code/hooks/sage-spec-gate.sh`) blocks
         source-file edits while a cycle is `pre-spec`, enforcing Rule 3
         (spec-before-code) mechanically rather than by prose alone. It reads
         `gate_state` from this frontmatter. A manifest that never advances
         past `pre-spec` will keep blocking edits — so the field must be moved
         forward at each checkpoint, exactly as `status` already is.

         Tier-1 work never creates a manifest; "no manifest" is the hook's
         signal that no cycle is active and edits are unrestricted. That is the
         Tier-1 escape hatch, unchanged by this contract.

BLOCKED RATIONALIZATIONS:
- "I updated status, that's enough" — the hook reads `gate_state`, not
  `status`. Both move at every checkpoint.
- "The spec is written, gate_state can stay pre-spec until I get to it" —
  gate_state gates the *next* edit. Advance it when the spec is approved, not
  later.

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
