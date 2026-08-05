---
name: sage-using-memory
description: Sage's persistent memory. Use when the user says remember this, store this, don't forget, note for next time, what do we know about X, have we seen this before — and whenever the user corrects you, an approach fails repeatedly, or you discover a non-obvious gotcha worth keeping.
version: "1.0.0"
type: system
---

# Using memory

Sage has its own memory. It is **not** the platform's native memory
(`MEMORY.md`, feedback files, and the like). Storing a Sage learning in the
platform's memory puts it where no other Sage session will look for it.

**Storage target:** the `sage_memory_store()` MCP tool.
**Fallback:** `.sage-memory/` markdown files when the MCP server is unavailable.

## Search before work (Rule 1A)

Before writing a spec, a plan, or an ADR — or before starting an investigation
— search memory. This is mandatory for Standard+ work and skipped only for
Tier 1.

**Two searches minimum:**

1. **Domain search** — the task's domain keywords, `limit: 5`.
2. **Self-learning search** — the same query with `filter_tags: ["self-learning"]`,
   `limit: 5`.

The second search is the one people skip, and it is the one that pays. It is
where "we tried that and it did not work" lives.

### Parameter types (get these right or the call fails)

The MCP schema is strict, and the failure mode is a confusing error rather than
a graceful degradation:

| Parameter | Type | Pass | Do not pass |
|---|---|---|---|
| `query` | string | `"cache eviction"` | — |
| `limit` | **integer** | `5` | `"5"` |
| `filter_tags` | **array of strings** | `["self-learning"]` | `'["self-learning"]'` |
| `tags` | **array of strings** | `["gotcha", "redis"]` | `'["gotcha"]'` |

## Capture corrections (Rule 6)

When a learning moment happens, store it **before proceeding**. This is
automatic, not optional — the correction you do not write down is the one you
repeat in three weeks with a straight face.

### What counts as a learning moment

| Trigger | Type |
|---|---|
| **The user corrects your approach** | `correction` — MANDATORY, never skip |
| You tried 3+ approaches before one worked | `gotcha` |
| Root cause turned out to be non-obvious | `gotcha` |
| You discovered an undocumented project convention | `convention` |
| An API or library behaved differently than expected | `api-drift` |
| A test failed for a non-obvious reason | `error-fix` |

### Format

- **Title:** prefixed `[LRN:<type>]`
- **Content:** four parts — what happened · why it was wrong · what is correct ·
  the prevention rule
- **Tags:** `self-learning` + the type + domain keywords

The four-part body matters more than it looks. "Redis eviction is LRU here" is
a fact and will be forgotten. "We used LFU, it thrashed under burst traffic
because the counters never decayed, so this codebase pins LRU — check
`cache.py` before changing eviction" is a rule, and it survives.

## Why the store call comes before the next step

The temptation is to finish the task and store the learning afterwards. There
is no afterwards. The session ends, the context window closes, and the learning
that existed only as an intention is gone. Store it while it is still true.
