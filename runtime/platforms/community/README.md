# Community platforms

Sage generates for these. It does not enforce on them.

| Platform | Tier | Maintainer | Conformance |
|---|---|---|---|
| antigravity | C | *unclaimed* | [2026-07-12](../../../develop/conformance/reports/antigravity-2026-07-12.md) |
| codex | C | *unclaimed* | [2026-07-12](../../../develop/conformance/reports/codex-2026-07-12.md) |
| gemini-cli | C | *unclaimed* | [2026-07-12](../../../develop/conformance/reports/gemini-cli-2026-07-12.md) |
| opencode | C | *unclaimed* | [2026-07-12](../../../develop/conformance/reports/opencode-2026-07-12.md) |

**All four are Tier C, and all four are Tier C for the same reason:** none of
them has a hook surface. Nothing can block an edit. Every Sage rule on these
platforms is prose — and the v1.2.1 eval measured what prose alone is worth,
which is why the tier is what it is rather than a matter of opinion.

Their capability contracts are full of `false`. That is not a slight. **An
unchecked capability is worth `false`**, and most of these have never been
checked against a real session. Antigravity's own docs claim a skills system and
parallel agents; both may well work; neither has been verified by Sage. Under
ADR-11 that means we do not have them.

## The lifecycle policy (R113)

**A platform that fails conformance — or whose attestations have all expired —
for two consecutive minor releases is dropped from the generated docs.** Its
directory stays, it gains a `STATUS.md` marking it dormant, and it stops being
generated.

This is not punitive. It is the only honest option. A platform that has rotted
and still appears in the support matrix is a promise Sage cannot keep, and a user
who picks it because it was listed has been misled by us rather than by the
platform.

`maintainer: unclaimed` in all four contracts is the real risk here. Nobody
answers when these go red. The two-release clock is what stops "unclaimed" from
quietly becoming "unmaintained but still advertised".

## Promotion — how a community platform gets better

Porting Sage means **making the conformance suite pass**. Not petitioning core.

```bash
develop/conformance/run-conformance.sh <platform> --level 1,3 --report
```

1. **Fix what fails**, or change the `true` to a `false` and accept the tier. A
   `false` costs you a tier and costs your users a feature; a `true` that is not
   so costs them their trust in every other line of the contract.
2. **Attest what cannot be checked for free.** An `attested` value needs an
   evidence file with a transcript and an expiry (C15). It is a loan against a
   claim, not a gift — expire it and conformance goes red.
3. **Claim `maintainer:`.** Put your name in the contract. That is what makes the
   two-release clock mean something.

A capability that no check can prove and no attestation backs **fails
conformance**. The fix is a check, an attestation, or an honest `false` — never a
sentence in a README asserting that it works. That sentence is what Sage spent
v1.2.0 removing from its own documentation.

## What "Tier C" actually means for a user

- Gate scripts still run. They need only bash and python3, and they are installed
  to `.sage/gates/`. **You have to run them yourself** — nothing fires them.
- The full reference content is **inlined** into the instructions file, because
  there is no discovery mechanism to fetch it on demand. That file is
  correspondingly large, and that is the honest cost of a platform that cannot
  fetch.
- `--subagents` will **refuse, loudly**, and record the refusal in
  `decisions.md`. You get the inline build loop, and you are told so.
- Rules 3 and 5 — spec before code, verify before claiming done — are enforced by
  the model reading them. On Claude Code they are enforced by scripts that block
  the edit. That difference is the whole tier.
