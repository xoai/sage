# The manifest's state is model-authored prose, and it drifts from the tree

**Status: FIXED in v1.3.2** (state drift) **and v1.3.4** (judgment drift).
`runtime/tools/manifest.py` + `sage-manifest-sync.sh` (PostToolUse) fixed the
machine fields; `manifest.py resume` + the resume authority order
(cycle-protocol.md) + the `blocked_on:` requirement fixed the half this document
ends on — "the resume scenario did not improve" — which was two distinct things:
mostly budget truncation (later corrected: the resume scenario was 3/3 all along),
plus one real, under-budget refusal — the manifest's *prose* drifting from its
authority, a dead session's hedge inherited as law. See `docs/eval-baseline.md`.
Kept as the record of what was found and what was deliberately *not* automated.
**Found by:** the resume-fidelity scenario, first real run, N=3. See
`docs/eval-baseline.md`.

## What happened

Three runs of the *identical* cycle. All three completed all three tasks and
committed them. The manifest recorded three **different** states:

| run | `phase` | `gate_state` | work actually done? |
|---|---|---|---|
| 1 | quality-gates | `gates-passed` | ✓ all 3 tasks |
| 2 | quality-gates | **`plan-approved`** | ✓ all 3 tasks |
| 3 | complete | `complete` | ✓ all 3 tasks |

**Run 2 is the bug.** `gate_state: plan-approved` means *"plan approved, no tasks
started."* All three tasks were implemented, tested, and committed. A session
resuming from that manifest would read "no tasks started" and redo the work.

The artifact that exists to carry work across a context boundary had drifted from
the tree it describes — which is the one thing it must never do.

## Why

There is no enum and no state machine. `gate_state` is written by the model, in
prose, from judgment. Three runs produced three vocabularies, and nothing checks
any of them against reality.

**This is the same bug v1.3.0 found in the task ledger** — *"the entire evidence
base for 'every task was independently reviewed' was being produced by the model's
goodwill; in two runs of three it simply was not written."* The fix there was
`ledger.py`: generate it. The sub-agent scenario went 1/3 → 3/3.

Same bug. Same place. Same fix.

## The fix — shipped

`gate_state` is generated now. A PostToolUse hook advances the manifest the moment
source is written under an active `plan-approved` cycle: it fires **because** the
agent wrote code, and the firing **is** the evidence. No goodwill required, and none
accepted.

**What it refuses to do, and this matters as much as what it does:** it will not award
`gates-passed` or `complete`. Those are *approval* states — a human grants them, or the
quality-locked loop does after the gates actually run. A hook that advanced a cycle to
`gates-passed` because the files looked finished would forge the signature the gate
exists to collect, which is a worse bug than the one being fixed.

**Fact is mechanical. Approval is not.**

Result (resume scenario, sage, N=3, re-run with the hook):

| | before | after |
|---|---|---|
| manifest coherent with the tree | 2/3 | **3/3** |
| `gate_state` values seen | `gates-passed`, **`plan-approved`**, `complete` | `building`, `gates-passed`, `building` |
| **Resume scenario overall** | 2/3 | **2/3 — unchanged** |

**The resume scenario did not improve, and that is worth stating plainly.** The
manifest has not lied since. But in one run of three Sage still failed to *finish the
work* — a different failure, which ceremony cost causes and a hook cannot fix.
`manifest.py check` now fails a manifest that contradicts its own tree, so this
cannot silently regress. (That 2/3 was later corrected to 3/3 — the shortfall was
budget truncation, not resume infidelity; see `docs/eval-baseline.md`.)

## The original plan, for the record

1. **An enum.** `gate_state` and `phase` get defined, legal values. A manifest
   carrying anything else is invalid.
2. **Generate it, don't ask for it.** A `manifest.py` that derives state from what
   is *true* — tasks in the plan vs. deliverables in the tree vs. gates that have
   actually run — rather than from what the model believes.
3. **A coherence check.** A manifest claiming `plan-approved` while the plan's
   deliverables exist in the tree is a contradiction. Something should fail loudly
   rather than let the next session inherit a lie.
4. **The resume scenario is already the regression test.** It catches this today.
   It should go 2/3 → 3/3.

## Until then

The README's session-continuity claim cites the measurement instead of asserting the
capability. House rule: *"if a rule matters, make it code. If you can't, don't claim
it."*

## Also worth knowing

A bare agent with the same files resumed correctly **3/3**. Sage managed **2/3** at
roughly **3.6× the spend**, and needed an extra turn to get there. The ceremony is
not currently buying what it costs. (The 2/3 itself was later corrected — budget
truncation; see eval-baseline. The cost ratio stood.)
