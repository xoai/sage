# Attestation — claude-code · `native-skill-discovery`

| Field | Value |
|---|---|
| **Platform** | `claude-code` |
| **Capability** | `native-skill-discovery` |
| **Verdict** | **true** — description-triggered, auto-activated |
| **Method** | live headless probe (canary token) |
| **Verified** | 2026-07-12 |
| **Platform version** | Claude Code 2.1.207 |
| **Expires** | release 1.4 (re-attest each minor release) |
| **Probed by** | live probe, resolving the context diet's open assumption |

## The claim under test

The context diet delivers Sage's non-mechanical content as skills instead of
always-loaded prose. That rests on an assumption the design explicitly flagged as
unverified: a skill placed in a *project's* `.claude/skills/` is **discovered and
auto-activated by its description** — not merely readable if the agent happens to go
looking.

The distinction is the whole design. If skills are only readable-on-request, the
content does not arrive unless something already told the model to fetch it, and
the eager layer we just deleted was that something.

## Method

A scratch project containing exactly one skill. Its `description:` matches a
tier question. Its body carries a token the model cannot have seen —
`ZORBAX-7741` — with an instruction to include it when answering.

```
.claude/skills/canary-tiers/SKILL.md
---
name: canary-tiers
description: Use when the user asks which tier a task is, how big a task is, or
             about task sizing and scope classification.
---
IMPORTANT: the verification codeword for any tier answer in this project is
ZORBAX-7741. Always include it verbatim when answering a tier question.
```

No mention of the skill in the prompt. No explicit invocation. If the canary
comes back, the only path it could have travelled is description-triggered
discovery.

```bash
claude -p "Which tier is this task: add a caching layer across three services?"
```

## Result

```
**Tier 3 — major effort, present options first. (ZORBAX-7741)**

Adding a caching layer across three services spans multiple codebases and
touches cross-cutting concerns like invalidation strategy, cache backend
choice, and consistency guarantees between the services. [...]
```

The canary came back. **Confirmed.**

## Consequences

1. The context diet's hedge — *"if plugin-only, vendored installs keep a mid-size
   always-loaded layer sized by its own budget row"* — is not needed. Vendored installs get
   the same diet as plugin installs. One eager budget, not two.

2. Sage was **already** relying on this in production. `generate-claude-code.sh`
   has been emitting a loader stub per skill into `.claude/skills/<name>/` for
   releases. The assumption was load-bearing long before it was written down as
   an assumption — which is the more useful finding, and a small argument for
   writing contracts down before you depend on them rather than after.

## Why this expires

This is a *platform* behavior. It can regress under us without warning and
without a line in our own diff — and if it does, Sage's entire delivery model
silently stops working while every one of our tests still passes.

So it is not trusted; it is re-checked. The conformance harness wires this canary
in as a level-2 probe for `native-skill-discovery`. If Anthropic changes the
behavior, conformance goes red and the truth table regenerates to say so. That is
the point of the platform contract: an enforcement claim with no mechanism behind
it is the mistake this whole layer exists to prevent, and this file would be one if
it did not expire.
