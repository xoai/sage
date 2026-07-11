# The eager diet map

**What this is:** every block of the generated `CLAUDE.md`, classified for
ADR-9. This is the maintainer's veto point (R88) — the cheap place to disagree,
before any content moves and any eval budget is spent.

**Measured, not assumed.** Line numbers below come from the *generated* file
(`bash -c 'source runtime/platforms/_shared/instructions-body.sh; emit_instructions_body'`
with the `base` constitution spliced in), not from the source template. The
generated total is **398 lines / ~4,433 tokens**, paid on every turn of every
session. That matches `develop/validators/budgets.yaml` and the README's
corrected figure.

**The target** is ≤180 lines (02-brief §5).

---

## The two blocks that are the problem

Before the table, the shape of it. Two blocks are 36% of the file:

| Block | Lines | % of eager |
|---|---:|---:|
| Rule 0: Route Every Request | 85 | 21% |
| Workflow Gates | 60 | 15% |
| *everything else (19 blocks)* | *253* | *64%* |

Rule 0 is 85 lines because it carries a three-layer routing chain, a tier
classifier, a confirmation format, and four worked examples. A model needs the
routing *trigger* on every turn. It needs the worked examples on the turns
where it is actually routing — which is a minority of turns, and exactly the
condition a description-triggered skill is for.

Workflow Gates is 60 lines describing checks that a **hook already enforces**.
The spec-gate hook blocks the edit whether or not the model read the paragraph.
This is the clearest instance of ADR-9's rule: *nothing enforced by a hook needs
more than a pointer in eager prose.*

---

## Classification

`EAGER-CORE` — must be seen before the first token.
`SKILL:<name>` — moves to a description-triggered system skill.
`DELETE` — redundant with a hook, the README, or the platform itself.

| # | Block | Lines | Class | Why |
|---|---|---:|---|---|
| 1 | `# Sage — Project Instructions` (identity) | 8 | **EAGER-CORE** (→6) | The model must know what it is before it answers anything. Untestable by construction, and kept anyway — see the honesty note below. |
| 2 | `## Process Constitution` (framing) | 5 | **EAGER-CORE** (→1) | Five lines of preamble for a list. Compresses to a sentence. |
| 3 | `### Rule 0: Route Every Request` | 85 | **split** | The one block that must be split rather than moved. See breakdown below. |
| 4 | `### Rule 1A: Memory Before Work` | 20 | `SKILL:sage-using-memory` | Includes a paragraph on MCP parameter *types* (`limit` is an int, not a string). That is reference material consulted when calling the tool — the definition of on-demand. Eager keeps a one-line pointer. |
| 5 | `### Workflow Gates` | 60 | `SKILL:sage-gates` | Enforced by `sage-spec-gate.sh` (blocks source edits pre-spec) and `sage-tdd-gate.sh` (blocks code before tests). Eager keeps two one-liners *naming those hooks*. The fix/architect gate prose has no hook and moves whole. |
| 6 | `### Rule 1: State First` | 9 | **EAGER-CORE** (→7) | Auto-pickup of an active cycle. ADR-9 keeps this explicitly: it fires on turn one, before any skill could be triggered. |
| 7 | `### Rule 2: Skills Before Assumptions` | 8 | **EAGER-CORE** (→rewritten) | This *becomes* the dispatcher rule (R91). It is the block the whole design now rests on: if it fails to fire, nothing else loads. Rewritten in Superpowers' "before ANY response" form, with attribution. |
| 8 | `### Rule 3: Document Decisions` | 9 | **EAGER-CORE** (→1) + `SKILL:sage-constitution` | Hook-enforced (spec-gate). One-liner naming the hook; full text in the skill. |
| 9 | `### Rule 4: Checkpoints Are Sacred` | 11 | **EAGER-CORE** (→4) + `SKILL:sage-checkpoints` | The `[A]/[R]` contract is the user-facing protocol and stays. The rationalization prose moves. |
| 10 | `### Rule 5: Verify Before Claiming Done` | 20 | **EAGER-CORE** (→1) + `SKILL:sage-gates` | Hook-enforced (spec-gate's completion guard blocks `complete` before `gates-passed`). The 14-line self-check list is what the gate scripts already do mechanically. |
| 11 | `### Rule 6: Capture Corrections` | 12 | `SKILL:sage-using-memory` | Triggered by an event ("the user corrected you"), not needed on turns where no correction happened. |
| 12 | `### Rule 7: Record Decisions at Checkpoints` | 30 | `SKILL:sage-decisions` | 30 lines on decision-log placement, prepend order, and archive rotation. Consulted at checkpoints; irrelevant on every other turn. |
| 13 | `## Engineering Principles` (constitution) | 9 | **EAGER-CORE** (→11) + `SKILL:sage-constitution` | Kept, and *grown* by 2 lines: each principle gains the name of the hook or gate that enforces it, so "tests before code" reads as a mechanism rather than a wish. Project additions move to the skill. |
| 14 | `## Learning Triggers` | 15 | `SKILL:sage-using-memory` | Six trigger conditions + a storage format. Reference material. |
| 15 | `## Deep Process Intelligence` | 6 | **DELETE** | A pointer to sage-navigator. The dispatcher rule (block 7) subsumes it — that is what a dispatcher rule *is*. |
| 16 | `## Communication Style` | 7 | **EAGER-CORE** (→3) | "Sage →" at navigation moments. E6 greps for it, so it is load-bearing and measured. Keep the two rules, drop the gloss. |
| 17 | `## Interaction Zones` | 29 | `SKILL:sage-checkpoints` | Four zone formats with footers. Needed when composing a checkpoint, which is a minority of turns. Eager keeps `[A]/[R]/[C]`. |
| 18 | `## Commands` | 19 | **DELETE** | The platform already lists the generated `.claude/commands/` in its own `/` menu, with these same descriptions. Nineteen lines to duplicate a menu the user can see. **Capability-gated:** platforms without `command-delivery` (ADR-11) keep it — the generic generator re-inlines it. |
| 19 | `## Enforcement (platform-dependent)` | 16 | **DELETE** | Duplicates the README's enforcement truth table — which Phase 4 (R111) *generates* from the capability contract. A hand-written copy of a generated table is exactly the drift this program exists to kill. |
| 20 | `## Available Skills` | 13 | **DELETE** | Prose listing skill *categories*, not skills. On a platform with native description-triggered discovery, the skill descriptions ARE the index. This block is ADR-9's argument stated against itself. |
| 21 | `## Project State` | 7 | **EAGER-CORE** (→5) | The `.sage/` layout. Auto-pickup (block 6) cannot work without knowing where to look. |

### Block 3 breakdown — Rule 0, split four ways

The routing block is the only one that cannot be classified whole. Splitting it
is also the largest single risk in Phase 2, because E6 (mode detection) grades
routing from free text.

| Part | Lines | Class | Why |
|---|---:|---|---|
| Keyword → workflow map | 14 | **EAGER-CORE** | The trigger itself. If this is not in front of the model, nothing routes, and the skill that would have taught it to route never fires — a bootstrap problem no description can solve. **This is the line we do not cross.** |
| Three-layer chain (keyword → sub-agent classifier → in-context fallback) | 22 | `SKILL:sage-routing` | Depth. Consulted when layer 1 misses. |
| Confirmation / Zone-1 format | 12 | `SKILL:sage-routing` | Formatting a menu, at the moment a menu is being formatted. |
| Tier classification | 10 | `SKILL:sage-tiers` | Eager keeps three one-liners (Tier 1/2/3 in a sentence each); the "bias toward Standard scope" guidance and the escalation rules move. |
| Four worked examples | 25 | `SKILL:sage-routing` | Twenty-five lines of examples, paid every turn, read on almost none. |
| Compliance note | 2 | **EAGER-CORE** | One line. |

---

## The new eager core

| Block | Lines |
|---|---:|
| Identity | 6 |
| Dispatcher rule + rationalization table (R91) | 32 |
| Routing: keyword map + pointer to `sage-routing` | 18 |
| Auto-pickup + project state | 12 |
| Constitution, one line each, naming the enforcing hook | 13 |
| Tiers, one line each, + pointer to `sage-tiers` | 7 |
| Checkpoint contract `[A]/[R]/[C]` + pointer to `sage-checkpoints` | 14 |
| Rule one-liners naming their hooks (Rules 3, 5) | 4 |
| Communication style | 3 |
| Skill index pointer | 6 |
| Frontmatter / regeneration notice | 5 |
| **Total** | **~120** |

Against a 180 budget. The headroom is deliberate: the dispatcher rule is the
single point of failure for everything else, and if E11 says it needs to be
louder, there is room to make it louder without re-opening the budget.

## The seven system skills

Sources at `core/system-skills/<name>/SKILL.md`. The `description:` is the
product — it is the trigger, and it is written from the user-utterance side
(what someone would actually type), not from the maintainer's side.

| Skill | Absorbs blocks | Triggers on |
|---|---|---|
| `sage-routing` | 3 (chain, confirmation, examples) | "which workflow", "what should I run", ambiguous multi-surface asks |
| `sage-tiers` | 3 (tier classification) | "how big is this", "which tier", scope questions |
| `sage-using-memory` | 4, 11, 14 | "remember", "store this", "what do we know about", corrections |
| `sage-checkpoints` | 9, 17 | approvals, "[A]", presenting deliverables, zone footers |
| `sage-gates` | 5, 10 | "gates", "why was I blocked", spec/plan file checks, verification |
| `sage-constitution` | 8, 13 (full text + project additions) | "principles", "constitution", "is this allowed" |
| `sage-decisions` | 12 | "record this decision", "why did we", ADRs, decision log |

## Move batches (R92)

Each batch: move → regenerate → `context_budget.py --report` → ratchet
budgets down → `--offline-check` → 🧪 full run (E1–E8 + E11) → merge only on
zero regression.

| Batch | Moves | Eager after | Risk |
|---|---|---:|---|
| 1 (P2-T6) | memory (4, 11, 14) + tiers (part of 3) | ~341 | Low. Nothing in the enforcement spine. E11 prompts 2 and 3 cover it directly. |
| 2 (P2-T7) | routing depth (3) + checkpoints (9, 17) | ~255 | **High.** This is where E6 lives. If routing regresses, this batch reverts. |
| 3 (P2-T8) | gates (5, 10) + constitution (8, 12, 13) + the four DELETEs | ~120 | Medium. Hook-enforced, so a prose regression should not change behavior — which is itself the prediction being tested. If E1/E7 regress here, ADR-9's central claim is wrong and we will have found that out for the price of one batch. |

Batch 3 is the one worth watching. Its content is the content the eval already
said was doing nothing. If deleting it changes nothing, the thesis holds and the
tokens were waste. If deleting it regresses E1 or E7, then the prose was load-
bearing after all, the hooks are not as sufficient as v1.2.0 claimed, and that
is a far more interesting result than a smaller context window.

---

## Two honesty notes

**1. Identity survives on an argument that cannot be tested.** Block 1 stays
eager because a model must know what it is before the first token, and no skill
can trigger on a turn that has not happened yet. That is a real argument. It is
also unfalsifiable by the current suite, and it is the same *shape* of argument
that justified the 398 lines we are now deleting. Six lines is a cheap bet, but
it is a bet, and it should be labelled as one rather than dressed up as a
finding.

**2. The generic platform cannot do any of this.** It has no skill discovery —
and, as it turns out, no generator either: `runtime/platforms/generic/CLAUDE.md`
is a hand-written 101-line file that has drifted badly from the real one
(it still describes "Modes" and `.sage/skills/` paths that no longer exist).
Nothing emits it. ADR-9 assumed a generic generator that inlines skill content;
there isn't one. That gap is recorded here and closed in P2-T4, which builds the
generator the ADR assumed — because a platform whose instructions file is
maintained by hand is a platform whose instructions file is already wrong.
