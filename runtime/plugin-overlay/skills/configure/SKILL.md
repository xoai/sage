---
name: configure
description: >
  Configure Sage preset and project settings. Switch between base,
  startup, enterprise, or opensource constitution presets. Use when
  the user says "configure sage", "change preset", or "sage settings".
disable-model-invocation: true
---

# Configure Sage

Set up project-level Sage configuration.

## Step 1: Read Current Config

Read `.sage/config.yaml` if it exists. If not, note: "No project
config found. Using base preset (default)."

## Step 2: Present Options (Zone 1)

Sage: Current preset: {current or "base (default)"}

[1] Base — TDD, no silent failures, simple first, document decisions
[2] Startup — velocity-focused, lighter process, ship fast
[3] Enterprise — compliance, audit trails, security-first
[4] Open Source — contributor-friendly, RFC process, public decisions

Pick 1-4, or describe what you need.

## Step 3: Apply Preset

Write the choice to `.sage/config.yaml`:

```yaml
preset: {chosen-preset}
```

If `.sage/` doesn't exist, create it with:
- config.yaml (with preset)
- decisions.md (empty template)

## Step 4: Confirm

Sage: Preset updated to {preset}. Start a new session or reload
the plugin to apply the new rules.

The {preset} preset adds these principles on top of base:
{list key additions from the chosen preset}

Type a command, or describe what you want to do next.

## Preset Summaries

**Base** (default): TDD first, no silent failures, simplest solution
first, document decisions, work in the open. Applied to all projects.

**Startup**: Bias toward shipping. Reduce ceremony for small changes.
Speed > perfection for v1. But: never skip tests, never skip root
cause analysis. Fast doesn't mean reckless.

**Enterprise**: Every change auditable. Security review on auth/data
changes. Compliance evidence in artifacts. Approval chains documented.
Change management discipline.

**Open Source**: Changes proposed as RFCs. Public decision log.
Contributor-friendly: explain WHY in every decision. Breaking changes
get migration guides. Backward compatibility by default.

## Cost controls — the close-out economy

Top-level `.sage/config.yaml` keys that trim the resume-session tax the
2026-07-15 profile measured. They apply on a **resumed** cycle's close-out only
(a session that started from `manifest.py resume`); a first-session build always
runs full rigor. Each has a safe default and can be restored to the old behavior.
Details: `core/workflows/_shared/cycle-protocol.md` § "Resume close-out economy".

| Key | Default | Effect | Restore old behavior |
|---|---|---|---|
| `gate_review` | `combined` | Judgment gates 1–3 reach an independent verdict via ONE adversarial reviewer instead of a dispatch per gate. | `per-gate` (a reviewer per gate) or `off` (self-review) |
| `batch_bookkeeping` | `true` | Memory writes and prose checkpoints deferred to the checkpoint, not emitted per task. The manifest bridge is never batched. | `false` |
| `trust_inherited_red` | `true` | On resume, a test the prior session already recorded as written-and-failing is not re-run just to re-witness the failure. Never applies to a test this session writes. | `false` |
| `resume_memory` | `skip` | On resume close-out, skip the memory search/store — the brief already carries the context and L2 measured its value at this horizon as null. | `keep` (the bet that memory compounds over dozens of sessions) |
| `resume_test_cadence` | `lean` | On resume close-out, run the targeted test per step and the full suite ONCE at close-out, not per task. The closing full-suite run is never skipped. | `full` (whole suite at every step) |

What these never touch: the deterministic script gates (they always run, and are
the evidence base), the final full-suite verification, at least one independent
whole-change review, and per-task commits. The balance is rigor front-loaded on
the session that does the design, not re-purchased by the session that finishes a
small delta.

When a user asks to "make Sage cheaper on resume" / "reduce the resume cost", these
are the levers; when they want "maximum rigor regardless of cost", set
`gate_review: per-gate`, `batch_bookkeeping: false`, `trust_inherited_red: false`,
`resume_memory: keep`, `resume_test_cadence: full`.

## Review loop — the `review_loop:` block

v2 — the default since the flip criteria were measured (E16–18 N=3,
calibration recall/precision 1.0) — puts the review-revise verdict in code:
reviewer findings land in a machine-owned ledger (`runtime/tools/review.py`,
at `.sage/work/<slug>/review-ledger.json`) and `sage_flags.py` computes every
CONTINUE/ESCALATE/STOP from ledger facts. Findings that cite nothing and
demonstrate nothing are capped at substantive and never block. Projects
initialized before the flip are pinned to `mode: v1` by `sage update`
(nothing changes mid-initiative); delete the pin or set `v2` to opt in.

| Key | Default | Effect | Restore v1 behavior |
|---|---|---|---|
| `mode` | `v2` | The ledger loop; the reviewer loses the verdict. | `v1` (the whole block below is then inert) |
| `major_budget` | `0` | Open majors tolerated at stop. | n/a (v1 majors always block) |
| `iteration_cap` | `5` | Hard round cap; at cap every open entry needs a disposition. | v1 value: `10` |
| `escalate_after_stalls` | `2` | Consecutive non-improving rounds before ESCALATE. | v1: 3 identical counts |
| `witness_capping` | `true` | Uncited + unwitnessed critical/major stored as substantive. | `false` (severity as reported) |
| `scope_check` | `true` | Fix commits checked against the finding's anchor scope. | `false` |
| `review_model` | `inherit` | `cheap` routes checklist passes down-model — savings **unclaimed** until measured. | `inherit` |

While `hard_enforcement: true` and `mode: v2`, the config-gate treats
`mode` and `witness_capping` as enforcement keys: an agent cannot soften
its own review floor (a human edits the file outside the agent).
