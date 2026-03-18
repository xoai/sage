---
name: memory
description: >
  Integrates sage-memory into Sage workflows. Teaches the agent when to
  remember (store findings during work), when to recall (search memory at
  session start and task start), and how to learn (structured knowledge
  capture via sage learn). Use when the user mentions memory, remember,
  recall, learn, capture knowledge, onboard to codebase, or when starting
  any session where sage-memory MCP tools are available.
version: "1.0.0"
type: process
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [memory, knowledge, persistence, learning, recall]
inputs: [sage-memory-mcp, project-files]
outputs: [memory-entries, knowledge-reports]
requires: []
-->

# Memory

Make knowledge persistent across sessions. Three layers — two automatic,
one user-triggered.

**Prerequisite:** sage-memory MCP server configured. If memory tools are
not available, degrade gracefully — proceed without memory, never block
work.

## Layer 1: Automatic Recall

At session start and task start, search memory for relevant context.
This happens inside the navigator's "Read the Room" phase.

### When to Search

- **Session start.** Before reading files, search memory for the project's
  architecture, conventions, and recent decisions. Memory is cheaper than
  re-reading source code.
- **Task start.** When the user describes a new task, search for relevant
  prior work — past research, related debugging insights, architecture
  decisions that constrain the approach.
- **Skill activation.** When a skill activates (JTBD, UX audit, build),
  search for prior findings in that domain.

### How to Search

Use `memory_search` with natural language queries. Use domain vocabulary
that matches how memories were written.

```
memory_search: "billing service architecture patterns"
memory_search: "authentication decisions JWT sessions"
memory_search: "user research findings onboarding"
```

### Reporting What You Found

After searching, report transparently:

**When memories are found:** State what you know from previous sessions
and how it informs the current task. Be specific — "From previous work,
I know this project uses a saga pattern for payments with compensating
transactions" not "I found some relevant context."

**When no memories are found:** Say nothing about memory. Don't announce
"I searched memory and found nothing." Just proceed normally.

**Always attribute.** If a recommendation comes from memory rather than
from reading current code, say so. "Based on what we learned in previous
sessions..." This builds trust and lets the user correct stale knowledge.

## Layer 2: Automatic Remember

During any workflow, store valuable findings that would help in future
sessions. This happens naturally — no user action required.

### What to Store

Store **insights**, not **facts**. Store what requires understanding,
not what can be re-read from source code.

**SHOULD store:**
- Architecture decisions with rationale ("chose event sourcing because
  of audit requirements — see ADR-003")
- Discovered conventions ("all API handlers follow request → validate →
  process → respond pattern, validation in separate schema files")
- Non-obvious behavior ("the cron job runs at UTC midnight but the billing
  cycle closes at PST midnight — 8 hour offset matters")
- Debugging root causes ("504 timeouts on /api/reports were caused by
  N+1 queries in the ORM, fixed with eager loading")
- Domain knowledge from research ("user interviews showed 3 distinct
  segments: power users who batch-process, casual users who check weekly,
  admin users who configure but rarely use")
- Integration gotchas ("Stripe webhook signatures require the RAW body,
  not parsed JSON — Express body parser must be skipped for that route")

**SHOULD NOT store:**
- Anything re-readable from source code ("this file exports 3 functions")
- Temporary task state (that's for `.sage/progress.md`)
- Obvious patterns ("uses React with TypeScript")
- Trivial fixes ("fixed a typo in line 42")
- User preferences or style (that's for global scope, not project)

### How to Store

Write memories that retrieve well. sage-memory uses BM25 keyword search
with 91% recall on LLM-authored content — but only if the content uses
consistent domain vocabulary.

**Title:** 5-15 words, specific and descriptive.
```
Good: "Payment saga orchestration via PaymentOrchestrator with 3 services"
Bad:  "How payments work"
```

**Content:** Explain what AND why. Use the project's actual class names,
function names, and domain concepts. Include enough context that the
memory is useful without reading the source.

**Tags:** 2-5 domain keywords. Technology, area, concept.
```
Good: ["billing", "saga", "payments", "architecture"]
Bad:  ["code", "important", "backend"]
```

**Scope:** `project` for codebase-specific knowledge (default). `global`
for patterns that apply across all your projects.

### When to Store

Store at natural completion points, not continuously:

- After completing a skill workflow (JTBD → store key findings)
- After resolving a non-trivial bug (store root cause and fix)
- After making an architecture decision (store decision + rationale)
- After discovering a project convention (store the pattern)
- After research produces insights (store the insights, not raw data)

**Deduplication.** sage-memory deduplicates by content hash. Don't worry
about storing something twice — the system handles it. But do check:
before storing, briefly search to see if similar knowledge exists. If it
does, consider updating the existing entry (`memory_update`) rather than
creating a near-duplicate.

## Layer 3: Deliberate Learning (`sage learn`)

User-triggered structured knowledge capture. Produces two outputs:

1. **Memory entries** → stored in sage-memory (agent-searchable, persistent)
2. **Knowledge report** → saved to `.sage/docs/memory-{name}.md`
   (human-readable, shareable, reviewable)

### Broad Scan: `sage learn`

Scan the whole project to build foundational understanding.

**Process:**
1. Read project structure, README, config files, entry points
2. Identify: stack, architecture style, key modules, conventions
3. Trace a few representative flows (e.g., main API request path)
4. Store 10-20 memories covering architecture, stack, conventions,
   key modules, and any non-obvious patterns
5. Produce a knowledge report at `.sage/docs/memory-{project-name}.md`

**Duration:** 5-10 minutes. The goal is orientation, not exhaustive
understanding. Depth comes from working on the codebase.

### Deep Dive: `sage learn <path>`

Go deep on one area — a module, service, feature, or subsystem.

**Process:**
1. Read all files in the target path
2. Trace dependencies up to depth 3 (track visited nodes, avoid loops)
3. Map: purpose, key components, data flow, patterns, error handling
4. Identify: risks, technical debt, non-obvious behavior, gotchas
5. Store 5-10 focused memories for this area
6. Produce a knowledge report at `.sage/docs/memory-{name}.md`

**Duration:** 10-20 minutes depending on complexity.

### Knowledge Reports

**Read:** `references/knowledge-report.md` for the full guide.

Reports are flexible — adapt structure to what was found. Not a rigid
template. But they follow a general shape:

- **Overview** — what this is, its role, key characteristics
- **Architecture & Patterns** — structure, design patterns, data flow
- **Key Components** — important pieces, what they do, how they connect
- **Diagrams** — mermaid when they clarify (dependency trees, data flows,
  sequence diagrams)
- **Insights** — risks, strengths, technical debt, non-obvious behavior
- **Recommendations** — improvements, areas to investigate, open questions
- **Metadata** — date, scope, files analyzed, memories stored

The report is the comprehensive version. Memory entries are the distilled,
searchable version. They reference each other.

## Quality Principles

**Memory is not a log.** Don't store everything. Store what changes how
you'd approach the next task. If deleting a memory wouldn't change any
future decision, it shouldn't exist.

**Specificity retrieves.** "Payment saga with compensating transactions
via saga_rollback_handlers" retrieves. "How payments work" doesn't.
Use the project's actual vocabulary — class names, function names,
domain terms.

**Insights over facts.** "The billing module uses a saga pattern" is a
fact. "The billing module uses a saga pattern because the team needed
atomic multi-service operations with audit trails, and event sourcing was
rejected for complexity" is an insight. Store insights.

**Recency matters.** When knowledge becomes stale (code refactored,
architecture changed), update or delete old memories. Stale memories are
worse than no memories — they cause confident wrong answers.

## Complementary Skills

Memory works alongside two other sage-memory skills. All three share
the same backend but serve different purposes:

- **memory** (this skill) → prose knowledge: architecture, conventions,
  domain insights, research findings
- **self-learning** → agent mistakes and meta-knowledge: what went wrong,
  what to avoid, prevention rules that change future behavior
- **ontology** → structured facts and relationships: typed entities
  (Task, Person, Project), relations (blocks, assigned_to, depends_on),
  graph queries

Each works standalone. Together they give the agent comprehensive
cross-session intelligence: understanding (memory), behavioral
improvement (self-learning), and structured relationships (ontology).

## Failure Modes

**Memory not available.** sage-memory MCP server not configured. Degrade
gracefully — proceed without memory, never error or block. Don't tell the
user to install memory unless they specifically ask about persistence.

**Empty memories on first session.** No prior knowledge exists. This is
normal. Don't announce it. The navigator proceeds with normal file reading.
Memories accumulate as the user works.

**Stale memories.** Knowledge from months ago may not reflect current code.
When memory provides context, verify against current source before relying
on it. If you discover a memory is wrong, update or delete it.

**Overstoring.** Agent stores 50 memories per session, cluttering search
results with noise. SHOULD store 3-8 memories per significant task
completion. Quality over quantity.

**Understoring.** Agent never stores anything. Every session starts from
scratch. This defeats the purpose. At minimum, store after: architecture
discoveries, debugging breakthroughs, convention identification, and
research insights.
