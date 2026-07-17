# opencode Tier-A capabilities — attested 2026-07-17

Follow-up to the 2026-07-12 investigation, which left opencode at Tier C with
`pre-tool-veto` proven "up to the last link". All three Tier-A capabilities are
now attested with an instrumented transcript (raw log:
`.sage/docs/development/opencode-tierA-attested-2026-07-17.log`). Every probe
logs each firing, so nothing-happened and it-happened are distinguishable — the
rule the July investigation was built on.

Probed with opencode 1.15.3, plugin API `@opencode-ai/plugin`. The capability
attestations are model-independent (they concern whether the platform's plugin
API fires hooks, not model quality); the probe session ran on the platform's
configured model.

## 1. pre-tool-veto — attested
`.opencode/plugin/sage.js` bridges `tool.execute.before` → `sage-spec-gate.sh`
(paths parsed out of `apply_patch`'s `patchText`, the gap the July probe found).
In a pre-spec cycle, asked to edit source:

    tool.execute.before fires → sage-spec-gate.sh exit 2 → throw → EDIT BLOCKED

The edit-being-blocked transcript C15 requires. (Prior log:
`opencode-veto-attested-2026-07-17.log`.)

## 2. post-tool-events — attested
`tool.execute.after` fires after every tool with the result payload:

    before tool=read
    AFTER tool=read callID=call_00_… outputLen=148

The payload (tool, callID, args, output) is the PostToolUse shape Sage's
recorders need — manifest-sync, degradation-log, verify-tracker.

## 3. subagent-dispatch — attested
A `reviewer` subagent (`.opencode/agent/reviewer.md`, `mode: subagent`) was
dispatched via the built-in `task` tool:

    before tool=task
    session.next.agent.switched → agent="reviewer"   (a NEW session id)
    AFTER tool=task outputLen=3770

The reviewer ran in its own session and returned an independent review — Sage's
ADR-10 quality chain (independent reviewer) has a mechanism here.

## The load-bearing bonus: hooks fire INSIDE the subagent
Between task-dispatch and task-return, the reviewer's OWN read fired the hooks:

    before tool=read / AFTER tool=read outputLen=148   (child session)

So a dispatched subagent is NOT an enforcement escape hatch — the veto and the
config-gate apply inside it. This is the exact property the claude-code
"hooks-in-subagents" attestation turns on, and it holds on opencode too.

## Derivation
ADR-11: Tier A = pre-tool-veto ∧ post-tool-events ∧ subagent-dispatch. All three
attested. opencode's platform capabilities support Tier A. (Delivery is gated on
Sage shipping the adapter that uses them — the generator work, tracked
separately.)

verified: 2026-07-17 · expires-release: "1.5" · re-probe on opencode major bumps
