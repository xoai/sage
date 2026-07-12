# The platform capability contract (schema v2)

**What a `platform.yaml` is now:** a set of claims about what Sage can *enforce*
on a platform, each of which something checks.

**What it used to be:** a feature list nobody read. `claude-code/platform.yaml`
declared `supported-os: [linux, macos, windows]`; nothing has ever tested
Windows. It declared `tier: 1` because somebody typed a 1. Nothing in the entire
build pipeline parsed these files — `run_generators()` resolved platforms by path
convention and never opened them.

That is the same failure this whole program exists to correct — a claim with no
mechanism behind it — sitting in the file that describes the mechanisms.

---

## The vocabulary

Seven capabilities. They are not features; they are the **preconditions of
enforcement**. Each one, if false, takes something specific away from Sage.

| Capability | The question it answers | What Sage loses without it |
|---|---|---|
| `context-injection` | Can the eager core reach the model at session start? | Everything. Below this, Sage cannot run at all. |
| `command-delivery` | Slash commands, or an equivalent explicit invocation? | Workflows must be read as files by hand. |
| `native-skill-discovery` | Are description-triggered skills fetched on demand? | ADR-9's delivery model. The generator must INLINE every skill into the eager layer, which grows accordingly. |
| `pre-tool-veto` | Can a hook **block** a tool call, with a reason the model sees? | **The product.** Rules 3 and 5 become prose, and the v1.2.1 eval measured what prose alone is worth: nothing. |
| `post-tool-events` | Can completed tool calls be observed? | The audit trail. A degraded run stops being distinguishable from a clean one. |
| `subagent-dispatch` | Fresh-context task delegation? | Independent review. Every reviewer is the agent that wrote the code. |
| `session-events` | Start/stop lifecycle? | Auto-pickup of an active cycle. |

`pre-tool-veto` is the one that matters most, and the old schema had **no word
for it**. It had `hooks: true` — which conflates "we can watch" with "we can
stop", and those are the two different things that decide whether Sage is a
framework or a suggestion.

## Values

Each capability is `true`, `false`, or `attested`.

- **`true`** — a conformance check proves it, for free, in CI.
- **`false`** — honest. A `false` costs you a tier and costs the user a feature,
  and that is strictly better than a `true` that is not so.
- **`attested`** — it is real, but no free check can prove it, so it is backed by
  an **evidence file with a transcript and an expiry** (C15).

`attested` is the honest middle, and it is not a way to write `true` without
doing the work. An attestation must exist, must parse, must point at a real file,
and must not be expired — conformance level 3 checks exactly that, and an expired
attestation fails. It is a *loan* against a capability, not a gift.

## Tier is derived, never declared

```
A  =  pre-tool-veto ∧ post-tool-events ∧ subagent-dispatch
B  =  pre-tool-veto ∧ context-injection
C  =  context-injection
      (below C: unsupported — Sage cannot deliver its instructions at all)
```

| Tier | What the user actually gets |
|---|---|
| **A** | The full quality chain. Edits are blocked before a spec or a test exists; reviews are independent; degradation is logged by a script. |
| **B** | Mechanical gates, no subagent chain. The gates hold. The reviews are the agent reviewing itself, and Sage says so. |
| **C** | Prose, plus gate scripts you run yourself. Nothing blocks anything. |

**A tier you can type is a tier you can be wrong about.** `contract.py` derives it
from the capabilities, and if a platform wants a better tier it has to acquire a
capability rather than edit a number. The legacy hand-set `tier:` field is
accepted for one release, and `--check` fails if it disagrees with the derived
value.

## Schema

```yaml
---
name: claude-code
description: >
  One paragraph. What this platform is, and what Sage can honestly do on it.
contract-version: 2
maintainer: "sage-core"        # who answers when conformance goes red (R113)

capabilities:                  # each: true | false | attested
  context-injection: true
  command-delivery: true
  native-skill-discovery: attested
  pre-tool-veto: attested
  post-tool-events: true
  subagent-dispatch: true
  session-events: true

attestations:                  # required for EVERY `attested` value
  - capability: pre-tool-veto
    evidence: docs/attestations/claude-code-hooks-in-subagents-2026-07-12.md
    verified: 2026-07-12
    expires-release: "1.4"     # re-attest each minor (C15)
    note: >
      Why this is attested rather than true.

supported-os: [linux, macos]   # what has actually been RUN, not what might work
command-prefix: "/sage"
install-method: plugin-marketplace
---
```

Declaring all seven capabilities is mandatory. **`false` is an answer; silence is
not.** A missing capability fails `--check`, because "we didn't think about it"
and "it doesn't have it" look identical in a file and mean very different things
to a user choosing a platform.

## Who reads it

- **`contract.py --check`** — every contract parses, tiers derive, no legacy
  mismatches, every attestation is real and unexpired. CI, every PR.
- **`develop/conformance/`** — checks the declarations against reality (P4-T2).
- **`gen_truth_table.py`** — generates the README's enforcement table from the
  contracts (P4-T5). Hand-editing that table fails CI.
- **The generators** — `native-skill-discovery` decides whether skills are
  emitted or inlined; `pre-tool-veto` decides whether hooks are installed;
  `subagent-dispatch` decides whether `--subagents` is available at all (R97).

That last one is the point of the whole exercise. The contract is not
documentation *about* the platform layer — it is the input *to* it.

## Adding a platform

Porting Sage means **making the conformance suite pass**, not petitioning core.
See `docs/porting-sage.md`. The short version:

1. Write a `platform.yaml`, schema v2, with honest values. Most will be `false`
   at first. That is a normal starting position, not a failure.
2. Run `develop/conformance/run-conformance.sh <your-platform>`.
3. Fix what fails, or change the `true` to a `false` and accept the tier.
4. Name yourself in `maintainer:`.

A capability that no check can prove and no attestation backs **fails
conformance**. The fix is a check, an attestation, or an honest `false` — never a
sentence in a README asserting it works.
