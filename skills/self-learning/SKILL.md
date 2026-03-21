---
name: self-learning
description: >
  Captures agent mistakes, corrections, and discovered gotchas so they are
  not repeated. Use when: (1) a command or operation fails unexpectedly,
  (2) the user corrects the agent, (3) the agent discovers non-obvious
  behavior through debugging, (4) an API or tool behaves differently than
  expected, (5) a better approach is found for a recurring task. Also
  searches past learnings before starting tasks to avoid known pitfalls.
  Activate alongside the memory skill — they share sage-memory but serve
  different purposes (memory = codebase knowledge, self-learning = agent
  mistakes and gotchas). Also trigger on "sage review" or "review learnings"
  to curate and improve the learning database.
version: "1.0.0"
type: process
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [learning, self-improvement, mistakes, gotchas, corrections]
inputs: [sage-memory-mcp, project-files]
outputs: [learning-entries, team-learnings-export, review-reports]
requires: []
-->

# Self-Learning

Learn from mistakes. Don't repeat them.

This skill captures what went wrong, what was non-obvious, and what the
agent should do differently next time. Every learning includes a
**prevention rule** — a forward-looking instruction that changes future
behavior, not just a record of what happened.

**Part of the unified knowledge system.** Self-learning is a facet of
the memory skill — it stores through sage-memory with the `learning`
tag. During recall, learning entries surface as warnings alongside
regular knowledge and ontology entries, alerting the agent to past
mistakes in the area being worked on.

**Prerequisite:** sage-memory MCP server preferred. If memory tools are
not available, operate without persistence — never block work because
storage is unavailable.

## How It Relates to the Memory Skill

The memory skill stores **codebase knowledge** — architecture, patterns,
conventions, domain insights. Self-learning stores **agent mistakes and
meta-knowledge** — what went wrong, what was non-obvious, what to avoid.

They share sage-memory as a backend. Self-learning entries are
distinguished by the `learning` tag, which the navigator uses to
surface them as warnings during recall.

## Recall: Search Before You Work

At task start, search for learnings relevant to the current task. This
happens alongside (not inside) the memory skill's recall.

**When to search:**
- Before writing code that touches an area with past issues
- Before using a third-party API or library
- When the task resembles something that went wrong before

**How to search:**

```
sage_memory_search: query="<task-relevant terms>", filter_tags=["self-learning"]
```

Always include `filter_tags: ["self-learning"]` to retrieve only learnings,
not codebase knowledge. This applies a hard filter (AND logic) before
BM25 ranking — entries without the `self-learning` tag are excluded
from results entirely.

**Targeted recall with ontology:** If the ontology skill is active and
you know the current task's entity ID, search by edge tag for precision:

```
sage_memory_search: filter_tags=["self-learning", "edge:task_a1b2"]
```

This finds learnings specifically linked to that task — more precise than
keyword search. See `references/ontology-integration.md` for details.

**Reporting what you found:**

When learnings are found, report the **prevention rule**, not the
incident history. Say: "Before working with Stripe webhooks, verify that
body parsing middleware is skipped for the webhook route." Not: "Last
time, the agent made a mistake with Stripe webhooks."

When nothing is found, say nothing. Don't announce empty results.

## Capture: Detect and Store

When something goes wrong or something non-obvious is discovered, store
a learning. **Read** `references/capture-patterns.md` for the full
trigger list and examples.

### Five Learning Types

| Type | Trigger |
|------|---------|
| `gotcha` | Non-obvious behavior discovered through debugging |
| `correction` | User corrected the agent ("No, that's wrong...") |
| `convention` | Undocumented project/team pattern discovered |
| `api-drift` | API/library behaves differently than training data |
| `error-fix` | Recurring error with a known solution |

### How to Store

**Read** `references/storage-conventions.md` for the full convention.
Quick reference:

**Title:** `[LRN:<type>] <specific description>`
```
[LRN:gotcha] Stripe webhook requires raw body before JSON parsing
[LRN:correction] This project uses pnpm not npm
[LRN:api-drift] OpenAI removed functions param — use tools instead
```

**Content:** Four-part structure:

1. **What happened** — the symptom or situation
2. **Why it was wrong** — root cause or misconception
3. **What's correct** — the right approach
4. **Prevention rule** — what to check *before* this happens again

The prevention rule is the most important part. It transforms the
learning from an incident log into a behavioral instruction.

**Tags:** Always `["self-learning", "<type>", ...domain keywords]`
```
tags: ["self-learning", "gotcha", "stripe", "webhooks"]
tags: ["self-learning", "correction", "pnpm", "package-manager"]
```

If the ontology skill is active and the learning relates to a known
entity, add `edge:{entity_id}` to tags for targeted recall.

**Scope:** `project` for project-specific learnings (default). `global`
for patterns that apply across all projects.

**Full example with prevention rule:**
```
sage_memory_store:
  title: "[LRN:gotcha] Stripe webhook requires raw body before JSON parsing"
  content: >
    What happened: Webhook signature verification failed with 400
    "No signatures found matching the expected signature."
    Why: Express body parser replaced raw body with parsed JSON before
    the Stripe SDK could verify the signature. The error message is
    misleading — suggests wrong secret, not wrong body format.
    What's correct: Use express.raw({type: 'application/json'})
    middleware for the webhook route, before the global body parser.
    Prevention: Before implementing any webhook handler that verifies
    signatures (Stripe, GitHub, Twilio), check whether the verification
    SDK requires the raw request body. If yes, ensure body parsing
    middleware is skipped or deferred for that route.
  tags: ["self-learning", "gotcha", "stripe", "webhooks", "api"]
  scope: "project"
```

### When NOT to Store

Ask: "Would this change how I approach a future task?"

**Don't store:** typo fixes, trivial errors with obvious causes, anything
re-readable from source code, temporary task state, things the user just
told you this session (they know).

**Do store:** anything that took investigation to discover, anything the
user had to correct, any behavior that contradicts training data, any
pattern that isn't documented.

**Budget:** 2-5 learnings per significant task. Quality over quantity.

### Search Before Store

Before creating a new learning, search for similar existing ones:

```
sage_memory_search: query="<key terms from the learning>", filter_tags=["self-learning"]
```

If a similar learning exists, **update it** (`sage_memory_update`) rather than
creating a near-duplicate. Enrich the existing entry with new context.

If 3+ similar learnings exist across different projects, this is a
recurring pattern — consider promoting to global scope. **Read**
`references/promotion-rules.md` for escalation criteria.

## Review: Curate and Improve

Triggered by the user saying "sage review" or "review learnings." This
is a deliberate curation workflow that keeps the learning database
sharp. **Read** `references/review-workflow.md` for the full process.

**Quick reference:**

1. **Inventory** — List all learnings by type, recency, and domain
2. **Cluster** — Group related learnings (same library, same module)
3. **Stale check** — Flag learnings referencing changed code or outdated APIs
4. **Consolidate** — Merge similar learnings into comprehensive entries
5. **Promote** — Identify learnings ready for scope escalation
6. **Report** — Produce a summary of actions taken

The review is the quality mechanism. Without it, learnings accumulate
without curation and gradually lose value.

## Promote: Scope Escalation

Learnings start at project scope. When they prove broadly applicable,
promote to global scope. When they're valuable for the team, export to
shared files. **Read** `references/promotion-rules.md` for the full
rules.

**Quick reference:**

**Project → Global:** The learning applies beyond this codebase. Store a
rephrased, context-independent version at `scope: "global"`.

**Global → Team:** The learning would help other developers. Export to
a shared file in the repo. **Read** `references/team-sharing.md` for
export format.

## Storage Fallback

**Try MCP first:** call `sage_memory_store` with the `learning` tag.

**If MCP is not available,** fall back to `.sage-memory/` files using
the format defined in the memory skill. Use `type: learning` in the
frontmatter.


## Quality Principles

**Prevention over documentation.** Every learning should answer: "What
should I check *before* this happens again?" If you can't write a
prevention rule, the learning isn't actionable enough.

**Specificity retrieves.** "[LRN:gotcha] Stripe webhook requires raw body
before JSON parsing" retrieves. "[LRN:gotcha] API issue" does not.

**Freshness matters.** When code changes make a learning obsolete, update
or delete it. Stale learnings cause confident wrong actions. Use the
review workflow to catch staleness.

**Learnings are not memories.** Don't store codebase facts as learnings.
"The billing module uses saga pattern" is a memory. "The billing module
uses saga pattern — agent incorrectly assumed REST and broke the
compensation chain" is a learning.

## References

- `references/capture-patterns.md` — Triggers, examples, prevention rules
- `references/storage-conventions.md` — sage-memory format, fallback format
- `references/promotion-rules.md` — Scope escalation criteria
- `references/team-sharing.md` — Export formats for teams
- `references/review-workflow.md` — The sage review curation process
- `references/examples.md` — Complete end-to-end scenarios
- `references/ontology-integration.md` — Graph integration for targeted recall
