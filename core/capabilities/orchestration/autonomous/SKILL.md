---
name: autonomous
description: >
  When --autonomous is active, skip user-facing elicitation rounds.
  The agent makes elicitation decisions from memory, codebase patterns,
  constitution principles, and prior cycle context. Every decision
  cites its source. Substantive decisions with no signal fall back
  to asking the user.
version: "1.0.0"
type: process
---

# Autonomous Mode

When the workflow has `autonomous_mode: true` (set by `--autonomous`
flag, see flag-parser/SKILL.md), elicitation rounds are skipped in
favor of agent-driven decisions backed by explicit context sources.

The artifact structure is unchanged — brief.md, spec.md, plan.md still
exist with the same sections. What changes is HOW their content is
populated.

## The Three Goals

1. **Right thing for short-term:** the change is concretely useful now
2. **Right thing for long-term:** the change ages well — doesn't trap
   future work, doesn't violate principles
3. **Reasoning visible:** every decision cites memory, codebase, or
   principle so the user can challenge what's been decided

## Mandatory Pre-Flight Context Gathering

Before producing any artifact, gather context. This is not optional —
the autonomous mode's quality depends entirely on the inputs.

### 1. Memory search (3 queries minimum)

- Domain keywords from the goal + general search, limit 10
- Same query with filter_tags ["self-learning"], limit 10
- Same query with filter_tags ["ontology"], limit 5

Parameter types: query is a string, limit is an integer, filter_tags
is an array of strings. Not JSON strings — actual types.

### 2. Codebase scan

Activate codebase-scan skill at
`sage/core/capabilities/elicitation/codebase-scan/SKILL.md`.

- Read `.sage/conventions.md` if present
- Stack detection (package files, framework signals)
- Scan the area the change touches
- Note test conventions, error handling patterns, file structure

### 3. Constitution + principles load

- Read `.sage/constitution.md` (preset + project additions)
- Load `sage/core/capabilities/execution/coding-principles/SKILL.md`
- Note which principles apply most strongly to this domain

### 4. Prior work scan

- Read last 20 entries of `.sage/decisions.md`
- Scan `.sage/work/*/manifest.md` for active or recent related cycles
- Read `handoff` fields from related artifacts

## Decision Protocol

For each elicitation question the workflow would normally ask (framing,
intent, scope, boundaries, constraints, criteria, risks, approach,
task ordering, etc.), the agent:

1. Reviews the pre-flight context for relevant signals
2. Picks the answer that best aligns with:
   - (a) Past corrections in memory (avoid repeat mistakes)
   - (b) Codebase conventions (match existing patterns)
   - (c) Constitution principles (TDD, no silent failures, etc.)
   - (d) Long-term maintainability (avoid future traps)
3. Records the decision with a `rationale` field citing the source
4. If no signal exists for the decision AND the decision is
   substantive, the agent FALLS BACK to asking the user that
   specific question (not the whole elicitation)

## Confidence Threshold

A decision is "confident" when AT LEAST ONE of these holds:

| Signal | Example |
|--------|---------|
| Direct memory hit | Correction or convention exactly matching the question |
| Strong codebase pattern | 3+ existing examples of the same approach |
| Constitution principle | A principle directly speaks to this decision |
| Prior decision | Same initiative/cycle has already decided this |
| Single-option safety | Only one safe choice exists (e.g., "validate inputs") |

A decision is "unconfident" when:
- No memory entries on this topic
- Codebase has no precedent OR conflicting precedents
- Constitution is silent
- No prior decision applies
- Multiple safe choices exist with real trade-offs

## When to Ask vs Decide

- **Confident + substantive decision** → DECIDE, document rationale
- **Confident + cosmetic decision** → DECIDE silently, no rationale needed
- **Unconfident + substantive decision** → ASK the user (specific question, not whole elicitation)
- **Unconfident + cosmetic decision** → DECIDE with reasonable default, document the default in the rationale block

"Substantive" means: affects behavior, API, architecture, or long-term
maintenance. Examples: data model choices, auth approach, error handling
strategy, API contract decisions.

"Cosmetic" means: doesn't affect behavior or maintenance. Examples:
file naming within an established pattern, comment phrasing, ordering
of internal helpers.

## Rationale Block Format

Every artifact produced under `--autonomous` includes a rationale
block at the top, after the frontmatter:

```markdown
## Recommendation Rationale

This artifact was produced with `--autonomous`. Key decisions:

- **{Decision label}:** {Choice made} — {citation: memory entry,
  codebase pattern, principle, or "default — no signal"}
- **{Decision label}:** {Choice made} — {citation}
- **{Decision label}:** {Choice made} — {citation}

**Tradeoffs accepted:**
- Short-term: {immediate cost or constraint}
- Long-term: {future risk or maintenance burden}
- Why this is the right balance: {1 sentence}

**Decisions asked back to user:** {list of questions, or "None"}
```

Keep the block to ≤10 bullet decisions. If more decisions were made,
group related ones. Detailed rationale goes in `decisions.md`, not in
the artifact.

## Question Surface Format

When the agent hits unconfident substantive decisions, present them
as a Zone 1 choice block BEFORE producing the artifact:

```
Sage: --autonomous hit 2 decisions I can't recommend confidently.

[Q1] {Question}
     {Why I can't decide: no memory, no codebase pattern, etc.}
     {Why it's substantive: affects security / API contract / etc.}

[Q2] {Question}
     {Same reasoning}

Answer 1-2 inline, or pick [D] Default — I'll use my best guesses
and document them as project decisions.
```

If user picks [D], the agent documents the defaults in the rationale
block AND prepends a decision to decisions.md so the choices are
visible for review.

## Auto-Pick at Checkpoints (when combined with --quality-locked)

When BOTH `--autonomous` AND `--quality-locked` are active, the user
has signaled "decide the best approach yourself AND don't stop until
clean." Asking them to manually pick `[A] Review` at every approval
checkpoint contradicts both flags. At normal approval checkpoints
where the choices are `[A] Review / [S] Skip review / [R] Revise /
[N] New session`, only `[A] Review` is consistent with both flags:

| Option | Consistent with `--autonomous --quality-locked`? |
|--------|-------------------------------------------------|
| `[A] Review` | ✅ Triggers quality-locked loop |
| `[S] Skip review` | ❌ Defeats `--quality-locked` |
| `[R] Revise` | ❌ Requires user input — contradicts `--autonomous` |
| `[N] New session` | ❌ Requires user input |

**Auto-pick `[A] Review`** at normal approval checkpoints when both
flags are active. This is not bypassing a decision — it's the
deterministic conclusion of the user's stated intent.

### How to render the auto-pick

Print a clear notice in place of the prompt:

```
Sage: Auto-proceeding with [A] Review.
  Reason: --autonomous --quality-locked both active. [A] is the only
  option consistent with both flags.
  Logged to: .sage/work/<cycle>/manifest.md (auto_picked_checkpoints)
  Override: interrupt this session and re-run without one of the flags.
```

Then run the [A] Review path (sub-agent review → quality-locked loop)
without waiting for input.

### Where the auto-pick does NOT apply

Exception checkpoints still require user input even with both flags
active. These represent moments where automated continuation could
hide a real problem:

- **Quality-locked cap-reached** (`[F] Force / [R] Revise manually /
  [E] Escalate / [A] Abort`) — 10 iterations without convergence
  means structural issues. User judgment required.
- **Quality-locked stuck-escalation** (`[E] Escalate / [C] Continue /
  [R] Revise manually`) — 3 iterations with no improvement.
  Architecture-level question.
- **Autonomous unconfident-decision questions** (the `[Q1]/[Q2]` block
  that surfaces when the agent can't recommend a substantive decision)
  — by definition, the agent is asking because it doesn't know.
- **Sub-agent unavailable warnings** — degraded mode notice must be
  user-acknowledged so they know quality is reduced.

For all of the above, present the full prompt and wait. Do NOT auto-pick.

### Logging contract (mandatory)

Every auto-picked checkpoint is logged to TWO places:

**1. manifest.md frontmatter** — add the entry under
`auto_picked_checkpoints`:

```yaml
auto_picked_checkpoints:
  - phase: spec
    checkpoint: spec-approval
    decision: A
    timestamp: 2026-05-15T14:23:18Z
    reason: "--autonomous --quality-locked both active"
  - phase: plan
    checkpoint: plan-approval
    decision: A
    timestamp: 2026-05-15T14:31:47Z
    reason: "--autonomous --quality-locked both active"
```

This is machine-readable and lets `/continue` understand exactly which
checkpoints proceeded without user interaction.

**2. decisions.md** — prepend a human-readable entry (per Rule 7):

```markdown
### 2026-05-15 14:23 — Auto-pick: [A] Review at spec checkpoint
Flags active: --autonomous --quality-locked
Effect: Triggered quality-locked review loop (results in manifest
  under quality_locked_history.spec).
Override: re-run /build without --autonomous (or --quality-locked)
  to restore manual approval at this checkpoint.
```

**Both writes happen BEFORE the [A] Review action runs.** This way, if
the review loop crashes or the user interrupts, the audit trail still
shows the auto-pick happened and why.

### Why log so verbosely

The user trusted the flags to make decisions for them. The contract
back to the user is: every auto-pick is traceable, reviewable, and
reversible by inspecting `.sage/work/<cycle>/`. No hidden behavior.

## Conflict Handling

If memory says X but codebase pattern says Y:
- Pick the more recent signal (memory entry date vs codebase last-modified)
- Log BOTH sources in the rationale block
- Surface the conflict explicitly: "Memory said X, codebase said Y, chose X because newer."

If the user later corrects the autonomous decision, the new correction
is stored as a learning (`[LRN:correction]`) so future autonomous runs
have better signal.

## Per-Phase Decision Counting

After each phase, the workflow updates the manifest:

```yaml
autonomous_decisions:
  - phase: brief
    decided: 4
    asked: 0
    sources: { memory: 2, codebase: 1, principle: 1 }
  - phase: spec
    decided: 8
    asked: 1
    sources: { memory: 5, codebase: 2, principle: 1, default: 0 }
  - phase: plan
    decided: 12
    asked: 0
    sources: { memory: 3, codebase: 6, principle: 2, prior: 1 }
```

This makes the autonomy budget visible — high "asked" counts suggest
the agent should defer to human elicitation, low counts suggest the
context was rich enough.

## Failure Modes

- **Empty memory + empty codebase + no prior work:** the autonomous
  agent has nothing to ground decisions in. Falls back to asking the
  goal-level question only, then proceeds with documented defaults.
  The rationale block lists every decision as "default — no signal".
- **All decisions hit confidence threshold gaps:** if every substantive
  decision requires asking, the workflow degrades to interactive
  elicitation and notes: "Autonomous mode found insufficient context.
  Switching to interactive elicitation."
- **User contradicts a decision after artifact approval:** treat as
  a correction. Store as `[LRN:correction]` so future runs avoid the
  same pattern.

## Scope Preservation

Autonomous decisions cannot:
- Skip the spec-before-code rule (spec.md must still exist on disk)
- Bypass approval checkpoints (user still approves the final artifact)
- Modify .sage/work/ outside the current cycle's directory
- Modify files outside the workflow's natural scope

The agent's autonomy is over CONTENT, not PROCESS. Process rules
(Rule 0-7, anti-deferral, memory-first, etc.) still apply.

## Quality Criteria

- Pre-flight context gathering is complete (all 4 sources checked)
- Every decision has a citation OR is explicitly marked "default — no signal"
- Substantive unconfident decisions are surfaced as questions, not guessed
- Rationale block names sources (memory key, file path, principle number)
- Tradeoffs section addresses BOTH short-term and long-term
- The user can challenge any decision via [D] Discuss at checkpoint
