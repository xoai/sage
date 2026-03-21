---
name: memory
description: >
  Integrates sage-memory into Sage workflows. Teaches the agent when to
  remember (store findings during work), when to recall (search memory at
  session start and task start), and how to learn (structured knowledge
  capture via sage learn). Use when the user mentions memory, remember,
  recall, learn, capture knowledge, onboard to codebase, or when starting
  any session where sage-memory MCP tools are available.
version: "1.2.0"
type: process
---

# Memory

Make knowledge persistent across sessions. Three layers — two automatic,
one user-triggered. Works with sage-memory MCP (full capability) or
filesystem fallback (reduced but functional).

## Capabilities by Backend

| Capability | MCP | Files |
|------------|-----|-------|
| Store knowledge | ✅ `sage_memory_store` | ✅ `.sage-memory/` files |
| Search by keyword | ✅ BM25 ranked | ⚠️ filename scan only |
| Update existing | ✅ `sage_memory_update` | ✅ edit file |
| Delete | ✅ `sage_memory_delete` | ✅ delete file |
| Browse / list | ✅ `sage_memory_list` with tag filter | ✅ directory listing |
| Link related memories | ✅ `sage_memory_link` | ❌ skip |
| Graph traversal | ✅ `sage_memory_graph` | ❌ skip |
| Tag filtering | ✅ `filter_tags` | ⚠️ frontmatter scan |
| Deduplication | ✅ SHA-256 automatic | ⚠️ manual (check filenames) |

**How to detect backend:** At session start, call `sage_memory_set_project`
with the current project root path. If it responds, use MCP for the rest
of the session. If the call fails or the tool doesn't exist, fall back to
`.sage-memory/` files. Don't announce either outcome — just use whichever
works.

## File Fallback Format

All three skills (memory, ontology, self-learning) share the same
directory and file format when MCP is unavailable.

**Location:** `.sage-memory/` at the project root.

```
.sage-memory/
├── payment-saga-orchestration.md
├── jwt-auth-refresh-tokens.md
├── lrn-stripe-webhook-raw-body.md
├── ont-task-a1b2-fix-payment-timeout.md
└── ...
```

**Filename** = kebab-case title (the primary retrieval key without MCP).
Prefix with `lrn-` for learnings, `ont-` for ontology entries, no
prefix for regular knowledge.

**Each file:**
```markdown
---
tags: [billing, architecture, saga]
type: knowledge
scope: project
created: 2026-03-20
---

The billing service uses a saga pattern for multi-step payment
processing. PaymentOrchestrator coordinates between StripeGateway,
LedgerService, and NotificationService.
```

**type values:** `knowledge` (default), `learning`, `ontology`

**Recall without MCP:** Read the `.sage-memory/` directory listing.
Filenames are titles — scan them for relevance. Read only the files
that match the current task. For learnings, look for `lrn-` prefix.
For ontology, look for `ont-` prefix.

## Layer 1: Automatic Recall

At session start and task start, search for relevant context.

### When to Search

- **Session start.** First, call `sage_memory_set_project` with the
  current project root path. Then search for architecture, conventions,
  recent decisions. Memory is cheaper than re-reading source code.
- **Task start.** Search for related prior work, debugging insights,
  architecture decisions that constrain the approach.
- **Skill activation.** Search for prior findings in the activated domain.

### How to Search

**With MCP:**
```
sage_memory_search(query: "billing service architecture patterns", limit: 5)
```

Use `filter_tags` for namespace isolation, `tags` for soft boosting:
```
sage_memory_search(query: "auth patterns", filter_tags: ["self-learning"], limit: 5)
sage_memory_search(query: "checkout flow", tags: ["billing"], limit: 5)
```

**With files:** Read the `.sage-memory/` directory listing. Identify
filenames relevant to the current task. Read those files for content.
For a broad search, list all files and scan names. For focused search,
look for specific keywords in filenames.

### Enriched Recall with Graph (MCP only)

When you find a key memory via search, expand context:
```
sage_memory_graph(id: "<memory_id>", direction: "outbound", depth: 1)
```

This reveals what the memory depends on or connects to. One call
replaces N sequential searches. **Skip this step when using files.**

### Reporting What You Found

**Memories found:** State what you know from previous sessions. Be
specific — "From previous work, I know this project uses a saga pattern
for payments with compensating transactions."

**Nothing found:** Say nothing. Don't announce empty results.

**Always attribute.** "Based on what we learned in previous sessions..."

## Layer 2: Automatic Remember

During any workflow, store valuable findings for future sessions.

### What to Store

Store **insights**, not **facts**. Store what requires understanding.

**SHOULD store:** architecture decisions with rationale, discovered
conventions, non-obvious behavior, debugging root causes, domain
knowledge from research, integration gotchas.

**SHOULD NOT store:** anything re-readable from source code, temporary
task state, obvious patterns, trivial fixes, user preferences (global
scope).

### How to Store

**With MCP:**
```
sage_memory_store(
  content: "The billing service uses a saga pattern for multi-step payment
  processing. PaymentOrchestrator coordinates between StripeGateway,
  LedgerService, and NotificationService.",
  title: "Payment saga orchestration via PaymentOrchestrator with 3 services",
  tags: ["billing", "saga", "payments", "architecture"],
  scope: "project"
)
```

**With files:** Create a file in `.sage-memory/`:
```
File: .sage-memory/payment-saga-orchestration.md

---
tags: [billing, saga, payments, architecture]
type: knowledge
scope: project
created: 2026-03-20
---

The billing service uses a saga pattern for multi-step payment
processing. PaymentOrchestrator coordinates between StripeGateway,
LedgerService, and NotificationService.
```

### Linking Related Memories (MCP only)

When storing memories about connected components, create edges:
```
sage_memory_link(
  source_id: "<payment_service_id>",
  target_id: "<stripe_gateway_id>",
  relation: "depends_on"
)
```

**With files:** Skip linking. Mention related entries in the content
body if the connection is important: "Related: see jwt-auth-refresh-tokens
for the authentication layer this service uses."

### Writing Retrievable Content

**Title:** 5-15 words, specific. Good: "Payment saga orchestration via
PaymentOrchestrator with 3 services." Bad: "How payments work."

**Content:** Explain what AND why. Use the project's actual class names,
function names, domain concepts.

**Tags:** 2-5 domain keywords.

**Budget:** 3-8 memories per significant task. Quality over quantity.

## Layer 3: Deliberate Learning (`sage learn`)

User-triggered structured knowledge capture. Produces:
1. **Memory entries** (stored via MCP or files)
2. **Knowledge report** (`.sage/docs/memory-{name}.md`)

### Broad Scan: `sage learn`

1. Read project structure, README, config files, entry points
2. Identify: stack, architecture style, key modules, conventions
3. Trace a few representative flows
4. Store 10-20 memories covering architecture, stack, conventions,
   key modules, and non-obvious patterns
5. **MCP only:** Link related memories using `sage_memory_link` to build
   a navigable architecture graph. **Files:** mention connections in
   content instead.
6. Produce a knowledge report at `.sage/docs/memory-{project-name}.md`

### Deep Dive: `sage learn <path>`

1. Read all files in the target path
2. Trace dependencies up to depth 3
3. Map: purpose, key components, data flow, patterns, error handling
4. Identify: risks, technical debt, non-obvious behavior
5. Store 5-10 focused memories
6. **MCP only:** Build dependency graph via `sage_memory_link`. **Files:**
   note dependencies in content.
7. Produce a knowledge report at `.sage/docs/memory-{name}.md`

### Knowledge Reports

**Read:** `references/knowledge-report.md` for the full guide.

Flexible structure. General shape: Overview, Architecture & Patterns,
Key Components, Diagrams (mermaid), Insights, Recommendations, Metadata.

## Unified Knowledge Facets

Memory, ontology, and self-learning are three facets of ONE knowledge
system. Differentiation through tags (MCP) or `type` field (files):

| Facet | MCP tags | File type | Purpose |
|-------|----------|-----------|---------|
| Knowledge | domain tags | `knowledge` | Architecture, conventions |
| Structure | `["ontology", ...]` | `ontology` | Entity relationships |
| Warnings | `["self-learning", ...]` | `learning` | Mistakes, gotchas |

## Quality Principles

**Memory is not a log.** Store what changes future decisions.

**Specificity retrieves.** Use actual project vocabulary.

**Insights over facts.** Store the WHY, not just the WHAT.

**Recency matters.** Update or delete stale memories.

## References

- `references/knowledge-report.md` — Knowledge report guide
- `references/memory-patterns.md` — Good/bad memory examples
