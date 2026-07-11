# Cycle protocol (shared by /build, /fix, /architect)

The delivery workflows share a common cycle discipline. Each workflow's own file
keeps the parts that genuinely differ (its Auto-Pickup routing, its Manifest
Lifecycle gate_state mapping, its Phase Announcement names); this file is the one
place the *shared* rules live.

## Decision-log target (Rule 7)

"decisions.md" in a delivery workflow means the initiative's log at
`.sage/work/[initiative]/decisions.md`. The global `.sage/decisions.md` is only
for cross-initiative decisions. Readers check the initiative log first, then fall
back to the global file.

## Manifest gate_state discipline

The manifest's `gate_state` is the machine field the Claude Code spec-gate hook
reads (see the manifest template's "Machine state contract"). Advance it at every
checkpoint — pre-spec → spec-approved → plan-approved → building → gates-passed →
complete — in lockstep with `status`. A stale `pre-spec` keeps the hook blocking
the very work just approved; a `complete` set before `gates-passed` is blocked by
the completion guard (Rule 5).

## Phase announcements

Announce each phase transition before doing its work, with the cycle id (the
`.sage/work/` directory name), e.g. `Sage: Entering DELIVER phase [cycle-id] —
<what this phase does>`. Each workflow lists its own phase set.

## Session-break contract

At any `[N]` / context-budget break, write the manifest (phase, status,
gate_state, context summary, handoff guidance) BEFORE ending — the manifest is
the bridge between sessions.
