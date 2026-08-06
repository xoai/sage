# Attestation: Hermes Tier A (LIVE-PROBED)

**Date:** 2026-08-05
**Capabilities attested:** pre-tool-veto, post-tool-events, subagent-dispatch (the Tier A set)
**Plus:** context-injection, command-delivery, native-skill-discovery, session-events
**Expires:** Release 1.5
**Probe:** `develop/conformance/probes/hermes-gates-probe.py` (rerunnable)

## Status: ATTESTED BY LIVE PROBE

This closes the former `hermes-tier-b-PENDING.md`. Every capability below was
exercised live on 2026-08-05 against the plugin at
`G:\hermes\profiles\rei-stewart\plugins\sage` — not inferred from a code review.

## Transcript 1 — gate veto probe (pre-tool-veto + post-tool-events)

Probe: `python develop/conformance/probes/hermes-gates-probe.py G:\hermes\tmp-sage-tier-a-probe`
The probe calls the plugin's actual `_on_pre_tool_call` / `_on_post_tool_call`
entry points — the exact functions Hermes invokes — against a real scratch
`.sage` project (git repo, tracked test suite, pre-spec cycle).

```
── pre_tool_call probes (what the model sees BEFORE the tool runs) ──
  PASS spec-gate blocks pre-spec source edit: BLOCKED — Sage spec-gate: cycle "probe-cycle" is pre-spec. Rule 3: spec.md must exist and
  PASS secrets-gate blocks hardcoded key: BLOCKED — sage-secrets-gate: this edit hardcodes an sk-… API key into app.py — credentials never go into files (constitu
  PASS config-gate blocks self-disarmament: BLOCKED — sage-config-gate: this would turn OFF enforcement that is currently on — an agent under enforcement cannot dis
  PASS tdd-gate blocks code-without-test: BLOCKED — Sage TDD gate: tests before code — no test has been written for this change.
  PASS bookkeeping-gate blocks hand-edited manifest: BLOCKED — sage-bookkeeping-gate: don't hand-edit .sage/work/probe-cycle/manifest.md during an active cycle — apply the w
  PASS verify-gate blocks unverified commit: BLOCKED — sage-verify-gate: source changed after the last test run — the verify-before-claiming rule, made mechanical.

── post_tool_call probes (observers, must never block) ──
  PASS verify-tracker state: {'last_source_edit': ..., 'last_test_run': ...}
  PASS commit allowed after fresh test run: allowed
  PASS R29 degradation logged to decisions.md

── duplicate-key self-disarmament probes (maintainer review, 2026-08-05) ──
  PASS main reader stays armed on contradictory config: True
  PASS gates still veto under contradictory config: BLOCKED — sage-secrets-gate
  PASS config-gate refuses contradictory write_file: BLOCKED — sage-config-gate
  PASS config-gate refuses contradictory append-by-patch: BLOCKED — sage-config-gate

13 passed, 0 failed
```

### Maintainer review fix (2026-08-05)

Upstream review (PR #40) reproduced a self-disarmament bypass in the first
port: `_config()` read last-wins while `_cfg_read_flag()` read first-wins, so
an appended duplicate `hard_enforcement: false` left the config-gate seeing
"still enabled" while the main reader disarmed. Fixed by making both readers
first-wins (matching the canonical sage-config-gate.sh) and porting
`contradictory_flag()` into `_cfg_weaker`, so a both-values config is refused
at write time in both the whole-file and append-by-patch forms. Probes 10–13
above are the regression tests; the naive single-line flip was already caught
by probe 3 before the fix.

Six gates veto with model-visible messages (Hermes contract: return
`{"action": "block", "message": ...}` from `pre_tool_call`). The observers
record evidence and never block. The R29 degradation audit auto-logs a
skipped QA to `.sage/decisions.md`. The commit-time verify-gate both
blocks unverified commits AND releases them once tests run — the
discipline, not just the refusal.

## Transcript 2 — subagent-dispatch (live delegate_task)

On 2026-08-05 the implementing agent dispatched Hermes-native
`delegate_task` (delegation id `deleg_1f066fc7`, transcript archived at
`G:\hermes\profiles\rei-stewart\cache\delegation\live\deleg_1f066fc7\task-0.log`)
with a read-only independent-review brief — the same pattern Sage's
`sage-review` skill prescribes. A fresh-context subagent (no prior session
knowledge) reviewed the plugin and returned:

```
## Independent Review Verdict: APPROVE

### Verification against __init__.py
1. register(ctx) does not call ctx.register_command — Confirmed
2. All three hooks are registered — Confirmed
3. Bundled skills are registered via ctx.register_skill — Confirmed

### sage-review SKILL.md check
4. Instructs delegate_task for independent review — Confirmed

Score: 5/5 checks confirmed
```

This is exactly the Tier A shape: implementation by one context,
independent review by a fresh context, verdict recorded. The plugin's own
review loop (sage-review skill + HERMES_DELEGATION_NOTE in the platform
adapter) prescribes `delegate_task` for every `Task tool` / independent-
review / auto-QA step, and the manifest's R101 ledger guard refuses
`gates-passed` on subagent cycles whose tasks are not done+approved by an
independent reviewer.

## Capability-by-capability

| Capability | Value | Evidence |
|---|---|---|
| pre-tool-veto | attested | Transcript 1 — six gates block with model-visible messages |
| post-tool-events | attested | Transcript 1 — verify-tracker state, R29 audit to decisions.md |
| subagent-dispatch | attested | Transcript 2 — live delegate_task, independent 5/5 APPROVE |
| context-injection | attested | `pre_llm_call` injects eager core for CLI; gateway gets session-pickup.md via hooks/sage-session/ session:start |
| command-delivery | attested | Native skill slash commands `/sage-*` generated from registered skills (verified in-session 2026-08-05; plugin-registered bare command stubs were removed after colliding with them) |
| native-skill-discovery | attested | 21 skills registered via `ctx.register_skill()`; visible in the session skill index and invocable as `/sage-*` |
| session-events | attested | Gateway session:start/end via hooks/sage-session/; CLI equivalent via pre_llm_call |

## Known limitations (honest fine print)

- The Level-1 conformance checker was claude-code-shaped: it graded
  plugin-API platforms on generated hook files they don't have (R112).
  Fixed in this same changeset — `run-conformance.sh` now defers to Level-3
  attestation when the contract declares `hooks-config: null` /
  `skills-dir: null`.
- Hermes `delegate_task` has no toolset-restriction parameter; the
  reviewer's read-only stance is prompt-enforced. Sage's skill instructs
  verifying `git status` unchanged before accepting a verdict.
- `write_file`/`patch` are the gated edit surfaces; `terminal` is gated for
  config-evasion + verify-gate only (same documented hole the claude-code
  hooks have).

**Tier derivation:** pre-tool-veto ∧ post-tool-events ∧ subagent-dispatch
= **Tier A**, derived by `contract.py`, never declared.
