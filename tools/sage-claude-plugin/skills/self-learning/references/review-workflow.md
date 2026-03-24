# Review Workflow

The `sage review` process for curating and improving the learning
database. Run periodically or at natural breakpoints — after completing
a feature, before starting a new sprint, or when the user asks.

## When to Review

- User says "sage review" or "review learnings"
- Before starting a major new task (quick scan)
- After completing a multi-session feature
- When the learning count in a domain exceeds 10 (getting noisy)
- Weekly during active development (if the user opts in)

## The Review Process

Six steps, in order. Each step builds on the previous one.

### Step 1: Inventory

Pull all learnings and build a picture of the collection.

```
sage_memory_search: query="LRN", filter_tags=["self-learning"], limit=50
```

Group results by:
- **Type:** How many gotchas, corrections, conventions, api-drift, error-fix?
- **Domain:** Which libraries, modules, or areas have the most learnings?
- **Scope:** How many are project vs global?
- **Recency:** When were they last updated?

Present a summary table to the user:

```
Learning Inventory (project: my-saas)
─────────────────────────────────────
Total: 23 learnings (18 project, 5 global)

By type:
  gotcha:     9  │  correction:  5  │  convention: 4
  error-fix:  3  │  api-drift:   2

By domain:
  stripe (6)  │  auth (4)  │  docker (3)  │  database (3)
  api (2)     │  other (5)

Oldest: [LRN:correction] pnpm not npm (42 days ago)
Newest: [LRN:gotcha] Redis timeout on large sets (2 days ago)
```

### Step 2: Cluster

Identify groups of related learnings — multiple entries about the same
library, module, or problem area.

**Detection:** Look for learnings that share 2+ domain tags, reference
the same files, or address the same library/API.

**Report clusters to the user:**

```
Clusters found:
  Stripe (6 learnings) — webhooks, payments, signatures, retry logic
  Auth (4 learnings) — JWT refresh, token storage, middleware order
  Docker (3 learnings) — platform mismatch, layer caching, network mode
```

Clusters with 3+ learnings are consolidation candidates (Step 4).

### Step 3: Stale Check

Identify learnings that may no longer be accurate.

**Check for:**

- **Referenced files that no longer exist.** The learning mentions
  `src/api/webhooks/stripe.ts` but that file was moved or deleted.
  Search the project for the file path mentioned in the learning.

- **Outdated library versions.** The learning references "OpenAI v1.x"
  but the project now uses v2.x. Check package.json or requirements.txt
  for current versions of libraries mentioned in learnings.

- **Resolved issues.** The learning describes a bug or workaround that
  may have been fixed upstream. For `error-fix` and `gotcha` types,
  consider whether the root cause still exists.

- **Superseded conventions.** The learning documents a convention that
  may have changed. For `convention` type, spot-check a few current
  files to see if the pattern still holds.

**Report stale candidates to the user:**

```
Potentially stale:
  [LRN:gotcha] Redis timeout on large SMEMBERS — redis.conf may have
    changed since this was logged. Verify timeout settings.
  [LRN:error-fix] Docker platform mismatch — project now uses
    multi-arch builds (Dockerfile updated 2 weeks ago). May be resolved.
```

**Actions:** For each stale candidate:
- If still valid → keep as-is
- If partially valid → `sage_memory_update` with current information
- If fully obsolete → `sage_memory_delete`

Always confirm with the user before deleting.

### Step 4: Consolidate

Merge related learnings within a cluster into a single comprehensive
entry.

**When to consolidate:**
- 3+ learnings about the same library or module
- Learnings that address different symptoms of the same root cause
- Incremental discoveries that build on each other

**Process:**

1. Read all learnings in the cluster
2. Extract the unique insights from each
3. Write a single comprehensive learning that covers all of them
4. Include a prevention rule that addresses the full scope
5. `sage_memory_store` the consolidated entry
6. `sage_memory_delete` the individual entries (with user confirmation)

**Example consolidation:**

Before (3 separate learnings):
```
[LRN:gotcha] Stripe webhook requires raw body
[LRN:error-fix] Stripe signature verification returns misleading 400
[LRN:gotcha] Stripe webhook retry sends same event ID
```

After (1 consolidated learning):
```
Title: [LRN:gotcha] Stripe webhook integration — body parsing, signatures, and retries
Content:
  Three gotchas when integrating Stripe webhooks:
  (1) Signature verification requires the raw request body. Skip body
  parsing middleware for the webhook route.
  (2) Verification failure returns 400 "No signatures found" — this
  misleadingly suggests a wrong secret when the actual cause is parsed body.
  (3) Stripe retries failed webhook deliveries with the same event ID.
  The handler must be idempotent — check event ID before processing.
  Prevention: When implementing Stripe webhooks: (a) use express.raw()
  for the route, (b) store processed event IDs to prevent duplicates,
  (c) if verification fails, check body format before checking secret.
```

### Step 5: Promote

Identify learnings ready for scope escalation based on the criteria
in `references/promotion-rules.md`.

**Scan for:**

- **Global promotion candidates:** Project-scope learnings that are
  context-independent and reusable (especially `api-drift` and
  `error-fix` types).

- **Team sharing candidates:** Learnings that document conventions,
  recurring gotchas, or setup requirements that affect the whole team.

- **CLAUDE.md candidates:** Learnings so critical they should be in the
  system prompt — build commands, package manager, deployment blockers.

**Report promotion candidates:**

```
Promotion candidates:
  → Global: [LRN:api-drift] OpenAI tools param (applies to any project)
  → Global: [LRN:error-fix] Docker platform mismatch (cross-project)
  → Team:   [LRN:convention] API response envelope (team should know)
  → CLAUDE.md: [LRN:correction] pnpm not npm (affects every session)
```

Execute promotions with user confirmation.

### Step 6: Report

Summarize what was done. Save the report to `.sage/reviews/` for
reference.

```markdown
# Learning Review — 2026-03-17

## Summary
- Reviewed: 23 learnings
- Stale removed: 2
- Consolidated: 6 → 2 (Stripe cluster, Auth cluster)
- Promoted to global: 2
- Promoted to team file: 1
- Promoted to CLAUDE.md: 1

## Actions Taken
- Deleted: [LRN:error-fix] Docker platform mismatch (resolved by multi-arch builds)
- Deleted: [LRN:gotcha] Stale Redis config reference (file moved)
- Consolidated: 3 Stripe learnings → 1 comprehensive entry
- Consolidated: 3 Auth learnings → 1 comprehensive entry
- Promoted: [LRN:api-drift] OpenAI tools param → global scope
- Promoted: [LRN:error-fix] Docker ARM64 → global scope
- Exported: [LRN:convention] API envelope → .sage/team-learnings.md
- Exported: [LRN:correction] pnpm → CLAUDE.md § Build & Dependencies

## Current State
- Total learnings: 17 (was 23)
- Project scope: 12  │  Global scope: 5
- Database is clean, no known stale entries.
```

## Quick Review (Abbreviated)

For a fast check before a task (not a full review):

1. Search for learnings related to the task's domain
2. Check if any look stale
3. Report relevant prevention rules

No consolidation, no promotion, no report. Just a quick scan.

```
sage_memory_search: query="<task domain>", filter_tags=["self-learning"], limit=10
```

Report: "Found 3 relevant learnings. Key prevention rules: (1) skip
body parser for webhook routes, (2) check event ID for idempotency."

## Ontology-Enhanced Review

If the ontology skill is active, the review can leverage graph context:

- **Orphaned learnings:** Learnings with `edge:` tags pointing to
  deleted ontology entities. These are strong stale candidates.

- **Hot spots:** Ontology entities (tasks, modules) with the most
  incoming `edge:` links from learnings. These are the most
  mistake-prone areas — worth flagging to the user.

- **Learning coverage:** Which ontology entities (projects, key tasks)
  have zero linked learnings? These are uncharted areas — not
  necessarily a problem, but worth noting if they're complex.
