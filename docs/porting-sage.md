# Porting Sage to a new platform

**The definition of done is that the conformance suite passes.** Not a review,
not an argument, not a PR discussion about whether your platform "supports
hooks". You make the checks pass, and the tier falls out.

That is deliberate, and it is the opposite of how most frameworks handle this.
Sage's claims are *enforcement* claims — "an edit is blocked until a test
exists", "the review is independent" — and an unverified enforcement claim is
worse than no claim. It tells a user they are protected when they are not. So the
contribution surface is a suite you can run, rather than a maintainer you have to
convince.

---

## 1. Write the contract

`runtime/platforms/community/<your-platform>/platform.yaml`, schema v2. Full
schema: [`runtime/platforms/CONTRACT.md`](../runtime/platforms/CONTRACT.md).

The seven capabilities are not features. They are the preconditions of
enforcement, and each `false` takes something specific away:

| Capability | Without it, Sage loses |
|---|---|
| `context-injection` | Everything. Below this, Sage cannot run at all. |
| `command-delivery` | Explicit invocation. Workflows must be opened by hand. |
| `native-skill-discovery` | On-demand delivery. Skills must be **inlined**, and the instructions file grows. |
| `pre-tool-veto` | **The product.** Rules become prose, and prose was measured at zero. |
| `post-tool-events` | The audit trail. A degraded run stops being distinguishable from a clean one. |
| `subagent-dispatch` | Independent review. Every reviewer is the agent that wrote the code. |
| `session-events` | Auto-pickup of an active cycle. |

**Start with everything `false`.** That is not pessimism, it is the correct
starting position: an unchecked capability is worth `false`. You will turn them
on one at a time, and each one you turn on you will have to prove.

Declare all seven. `false` is an answer; **silence is not**, and `--check` fails
on a missing key. "We didn't think about it" and "it doesn't have it" look
identical in a file and mean very different things to a user choosing a platform.

## 2. Write the generator

`runtime/platforms/community/<your-platform>/setup/generate-<your-platform>.sh`,
taking the project root as `$1`.

Most of it is shared, and you should not rewrite any of it:

```bash
source "$(dirname "$0")/../../../_shared/instructions-body.sh"
source "$(dirname "$0")/../../../_shared/constitution.sh"
source "$(dirname "$0")/../../../_shared/system-skills.sh"

emit_instructions_body > "$OUT"                       # the eager core
CONST="$(build_constitution_section "$CORE" "$PROJECT_SAGE")"   # merge the constitution
# … substitute __CONSTITUTION_PLACEHOLDER__ …
emit_system_skills_inline "$CORE" >> "$OUT"           # IF you have no skill discovery
```

**That last line is not optional if `native-skill-discovery: false`.** ADR-9
moved ~220 lines out of the eager body and into skills. If your platform can
neither fetch them nor inline them, your users do not have that content — while
their instructions file still points at it ("→ the sage-gates skill") as though
they did.

All four community platforms shipped exactly that bug, and the conformance suite
is what found it. Do not rediscover it.

## 3. Declare where your artifacts land

```yaml
artifacts:
  instructions: GEMINI.md          # what your platform reads
  commands-dir: .gemini/commands   # omit if command-delivery is false
  skills-dir: .agent/skills        # omit if native-skill-discovery is false
  hooks-config: .claude/settings.json
```

Conformance reads this rather than assuming claude-code's layout. Get it wrong
and the suite will tell you it looked in the wrong place — which is a much better
failure than the suite quietly checking nothing.

## 4. Run conformance

```bash
develop/conformance/run-conformance.sh <your-platform> --level 1,3 --report
```

**Level 1** generates a real project and looks at what came out. If you declared
`command-delivery: true`, there had better be commands in the directory you named.

Note that it checks your **`false`s too**. A platform declaring
`command-delivery: false` must not be quietly shipping commands. A contract that
lies in the *safe* direction is still lying, and the user still cannot trust its
next line.

**Level 3** validates attestations. **Level 2** (live probes) costs money and runs
in the release workflow.

## 5. Fix what fails — three legitimate options, and no fourth

1. **Make the check pass.** Best outcome. Your platform gains a capability.
2. **Attest it.** For something real that no free check can reach: an evidence
   file with a transcript and an `expires-release`. It is a *loan* against the
   claim, not a gift — when it matures, conformance goes red until someone
   re-probes it.
3. **Change the `true` to a `false`.** Entirely respectable. You lose a tier and
   your users lose a feature — and they lose it *knowingly*, which is worth more
   than a feature they think they have.

There is no fourth option. In particular there is no "document it in the README
and move on": a capability that no check can prove and no attestation backs
**fails conformance**, and that sentence in the README is exactly what Sage spent
v1.2.0 deleting from its own documentation after the eval caught it being false.

## 6. Claim the platform

```yaml
maintainer: "your-github-handle"
```

This is what makes the lifecycle clock mean something. **A platform that fails
conformance for two consecutive minor releases is dropped from the generated
docs** (R113). `maintainer: unclaimed` means nobody answers when it goes red, and
that is how a port quietly becomes an advertised promise nobody is keeping.

---

## What tier you will get, and why you probably cannot reach A

```
A  =  pre-tool-veto ∧ post-tool-events ∧ subagent-dispatch
B  =  pre-tool-veto ∧ context-injection
C  =  context-injection
```

Tier is **derived**, never declared. If you want a better tier, you acquire a
capability — you do not edit a number. (The old schema let you type `tier: 1`,
and claude-code's said exactly that, because someone had typed a 1.)

**`pre-tool-veto` is the wall.** Every one of the four current community
platforms is Tier C, and all four for the same reason: no hook surface, so
nothing can block an edit. If your platform cannot let an external process reject
a tool call *before it happens*, Sage cannot enforce anything on it, and no amount
of prose in the instructions file changes that. The v1.2.1 eval measured a
framework whose rules were prose and found a behavioral delta of zero. That is
what Tier C is.

This is worth saying plainly because it is the most useful thing a prospective
porter can know: **if you are choosing which capability to fight for, fight for
the veto.** Everything else is a convenience. That one is the product.
