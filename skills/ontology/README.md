# ontology

Typed knowledge graph for AI coding assistants. Built on [sage-memory](https://github.com/sage-memory/sage-memory).

sage-memory gives your AI assistant long-term prose memory — architecture decisions, debugging insights, conventions. ontology adds a structured layer on top: entities with types, properties, and relations. Your assistant doesn't just remember *things* — it remembers how they connect.

- **Zero extra dependencies** — uses sage-memory as its storage backend, nothing else to install
- **Sub-millisecond operations** — entity create, relation create, and ID lookup all under 1ms
- **Zero consistency risk** — relations are independent entries, not embedded in both endpoints
- **5 core types, extensible** — Task, Person, Project, Event, Document out of the box; add your own via schema entries
- **913 lines total** — 1 instruction file, 2 references, 1 validation script

```
sage-memory entries:
  [Task:task_a1b2]  "Fix payment timeout"                  ← entity (the node)
  [Rel:blocks]      "Fix payment timeout → Deploy checkout" ← relation (the edge)

Your assistant searches, traverses, and validates — all through sage-memory's MCP tools.
```

## When Ontology Works Best

Ontology is not a replacement for sage-memory's prose entries. It's a complement. Here's when each one fits.

### Use ontology for things that have identity and relationships

Your project has people, tasks, services, dependencies — things that *are* something and *relate* to other things. Ontology gives these structure.

**Dependency tracking.** "Task A blocks Task B, which blocks the release." The agent stores this as typed, validated relations. Next session, when you ask "what's blocking the release?", it traverses the graph — not guessing from prose, but following actual edges. Cycle detection prevents impossible dependency loops before they're committed.

**Team and ownership mapping.** "Alice owns the billing module, Bob owns auth, the payment service depends on both." When the agent needs to modify billing code, it knows from the graph who to flag, what depends on this module, and what downstream tasks might be affected.

**Cross-skill coordination.** A JTBD skill discovers user segments and stores them as entities. A UX audit skill later queries those segments to ground its evaluation. An email skill creates a Commitment entity ("send report by Friday"); a task skill picks up pending Commitments and converts them to Tasks. Skills don't talk to each other directly — they coordinate through the graph.

**Multi-step planning.** "Set up a new feature project with 3 tasks, assign owners, link dependencies." The agent models this as a sequence of validated graph operations — create entities, create relations, check constraints — then executes them as a batch. Each step is verified before committing.

**Structured project context.** When onboarding to a new codebase, the agent can build a lightweight graph of key services, their owners, and their dependencies. This graph persists across sessions and gives future queries instant structural context rather than re-reading source files.

### Use sage-memory prose for everything else

**Architecture understanding.** "The billing service uses a saga pattern with compensating transactions because the team needed atomic multi-service operations with audit trails." This is an insight — rich, contextual, full of rationale. It doesn't fit in a property bag.

**Debugging insights.** "504 timeouts on /api/reports were caused by N+1 queries in the ORM, fixed with eager loading." The value is the narrative, not the structure.

**Conventions and patterns.** "All API handlers follow the validate → process → respond pattern with Zod schemas." This is a description of how code works, not a node in a graph.

**Domain knowledge from research.** "User interviews showed 3 distinct segments: power users who batch-process, casual users who check weekly, admin users who configure." The prose format with context and nuance is what makes this retrievable and useful.

### The decision rule

Ask: **does the relationship between things matter more than the description of the thing?**

- Yes → ontology (entity + relations)
- No → sage-memory prose entry
- Both → store the insight as prose, store the structural fact as an entity, let BM25 find whichever one matches the query

## How It Works

### Two kinds of entries, one storage backend

Everything lives in sage-memory. Ontology uses a consistent encoding convention to store entities and relations as regular memory entries with structured content and typed tags.

**Entities** store properties:

```
memory_store:
  title: "[Task:task_a1b2] Fix payment timeout in checkout flow"
  content: '{"id":"task_a1b2","type":"Task","properties":{"title":"Fix payment timeout","status":"open","priority":"high"}}'
  tags: ["ontology", "entity", "task", "billing"]
```

**Relations** store edges between entities:

```
memory_store:
  title: "[Rel:blocks] Fix payment timeout → Deploy checkout page"
  content: '{"from_id":"task_a1b2","from_type":"Task","rel":"blocks","to_id":"task_f3a4","to_type":"Task"}'
  tags: ["ontology", "rel", "blocks", "edge:task_a1b2", "edge:task_f3a4"]
```

Relations are first-class entries — not embedded inside entities. Creating a relation is 1 MCP call. Deleting a relation is 1 MCP call. No bidirectional updates, no half-link risk, no consistency repair needed.

### Search works naturally

Because everything is a sage-memory entry with BM25-indexed content, you get natural language search over structured data for free:

```
"open tasks in billing"     → finds tasks by content match
"what blocks the release"   → finds blocking relations by title match
"Alice Chen"                → finds the person entity
```

Tag-based filtering narrows results by type:

```
tags=["ontology", "entity", "task"]                    → all tasks
tags=["ontology", "rel", "blocks", "edge:task_a1b2"]  → blocks involving task_a1b2
```

### Validation is layered

**Agent-inline (every write, 0ms):** Required properties, enum values, cardinality constraints. The agent checks these before calling `memory_store`. No script, no subprocess. Covers ~90% of validation.

**Agent-traced (structural, 0ms):** For small dependency subgraphs (< 20 edges), the agent traces cycles manually by following relation chains. No script needed.

**Script-checked (on demand, ~5-50ms):** For large graphs or full audits, pipe entities and relations as JSON to `scripts/graph_check.py`. Iterative DFS cycle detection, cardinality validation across the full graph, required property completeness. Zero dependencies, zero file I/O.

## Setup

ontology is a skill that works alongside sage-memory. You need sage-memory configured as an MCP server — ontology uses its tools (`memory_store`, `memory_search`, `memory_update`, `memory_delete`) for all persistence.

Add the ontology skill to your agent's skill directory:

```
your-project/
├── .sage-memory/         ← sage-memory database (auto-created)
├── skills/
│   └── ontology/
│       ├── SKILL.md      ← agent instructions
│       ├── references/
│       │   ├── encoding.md   ← full encoding format and examples
│       │   └── schema.md     ← entity types, relation types, constraints
│       └── scripts/
│           └── graph_check.py  ← structural validator
└── src/
```

No configuration. The agent reads SKILL.md when ontology triggers and follows the encoding convention to store and retrieve graph data through sage-memory.

## Performance

Benchmarked with a sage-memory simulator (SQLite + FTS5) across 8 stress scenarios.

### Core operations (p50 latency)

| Scale | Create entity | Create relation | Search by ID | NL search | Find relations |
|-------|--------------|----------------|-------------|-----------|---------------|
| 90 entries | 0.15ms | 0.03ms | 0.09ms | 0.13ms | 0.02ms |
| 900 entries | 0.12ms | 0.04ms | 0.08ms | 0.20ms | 0.20ms |
| 9K entries | 0.09ms | 0.05ms | 0.34ms | 1.4ms | 2.1ms |
| 90K entries | 0.10ms | 0.05ms | 0.13ms | 13ms | 25ms |

Write throughput holds at ~10K entities/sec and ~30K relations/sec regardless of scale. ID lookup stays sub-millisecond at all scales.

### Agent session simulation

210 mixed operations (50 creates, 40 relations, 100 searches, 20 traversals) on a 290-entry graph:

```
Total session:  14ms
Create entity:  0.048ms p50
Create relation: 0.023ms p50
Search:         0.061ms p50
Traverse:       0.148ms p50
```

### Cycle detection

| Chain depth | No cycle | With cycle | v0.2 (recursive) |
|-------------|----------|-----------|----------------|
| 500 | 0.36ms | 0.28ms | 7.2ms |
| 1,000 | 0.80ms | 0.59ms | **stack overflow** |
| 5,000 | 5.0ms | 4.3ms | **stack overflow** |
| 10,000 | 10.9ms | 9.5ms | **stack overflow** |

v0.3 uses iterative DFS with O(V+E) time and O(V) memory. No recursion limit.

## Architecture

```
4 files · 913 lines · 0 dependencies beyond sage-memory

ontology/
├── SKILL.md              277 lines  Agent instructions, encoding convention, validation rules
├── references/
│   ├── encoding.md       231 lines  Full entity/relation format, search patterns, examples
│   └── schema.md         121 lines  5 core types, 11 relation types, extension pattern
└── scripts/
    └── graph_check.py    284 lines  In-memory structural validator (cycles, cardinality)
```

### Design decisions

**Relations as first-class entries.** The original ontology skill embedded relations inside both endpoint entities — creating a relation required updating two entries atomically. If one update failed, you got a half-link with no detection or repair. Making relations independent entries means 1 write per relation, 1 delete per relation, zero consistency risk.

**Bare ID search, bracket titles.** Entity titles use brackets for human readability (`[Task:task_a1b2] Fix payment timeout`), but search uses bare entity IDs with tag filters (`query="task_a1b2", tags=["ontology","entity"]`). FTS5 treats brackets as special syntax — searching by bracket title throws a syntax error. The bare ID is a plain alphanumeric token that FTS5 handles natively.

**Agent-inline validation over script validation.** The validation script adds ~90ms of Python subprocess startup overhead per invocation. Since 90% of validation is simple property/enum/cardinality checks, the agent does these inline before calling `memory_store` — zero overhead. The script exists for structural checks (cycle detection across large graphs) that the agent can't trace manually.

**Five core types, not fourteen.** The original ontology defined 14 entity types. Most projects use 3-4. Shipping fewer types with an extension mechanism (`[Schema:*]` entries) keeps the schema lean and the SKILL.md short while allowing any project to add what it needs.

**Session bootstrap probe.** At session start, the agent runs `memory_search: tags=["ontology"], limit=5`. If results come back, a graph exists and the agent adapts. If nothing, it proceeds normally. The graph shouldn't announce itself when it doesn't exist.

## What Ontology Is Not

**Not a project management tool.** It doesn't have a UI, notifications, or workflow automation. It's a knowledge structure that helps the AI assistant understand relationships in your project.

**Not a database.** It's designed for 50-2,000 entities per project — the knowledge an AI assistant accumulates while working on a codebase. It's not meant for storing application data or replacing SQLite/Postgres.

**Not a replacement for sage-memory prose.** Insights, rationale, debugging narratives, convention documentation — these belong in regular sage-memory entries. Ontology adds structure for things that have identity and relationships. Use both.

## License

MIT
