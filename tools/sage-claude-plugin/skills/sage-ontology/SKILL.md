---
name: sage-ontology
description: >
  Typed knowledge graph stored in sage-memory. Use when creating or querying
  structured entities (Person, Project, Task, Event, Document), linking
  related objects, checking dependencies, planning multi-step actions as
  graph transformations, or when skills need to share structured state.
  Trigger on "remember that X is Y", "what do I know about", "link X to Y",
  "show dependencies", "what blocks X", entity CRUD, cross-skill data
  access, or any request involving structured relationships between things.
version: "1.2.0"
type: process
---

<!--
  Fallback copy — sage's vendored prose for users without the
  sage-memory MCP package installed.

  Canonical version: ships with sage-memory >= 0.8.0 and is deployed
  automatically by `sage update` (which runs `sage-memory
  install-skills` when the package is present). Edits here only
  affect users who don't have sage-memory installed.

  To override locally for everyone: create a project-level skill
  under .claude/skills/ with a different name.
-->

# Ontology

Typed knowledge graph. Entities stored as memories, relationships stored
as edges — searchable, traversable, persistent.

**Part of the unified knowledge system.** Ontology entries surface
alongside regular knowledge and self-learning entries during recall.

## Capabilities by Backend

| Capability | MCP | Files |
|------------|-----|-------|
| Create entities | ✅ `sage_memory_store` | ✅ `.sage-memory/ont-*.md` files |
| Search entities | ✅ BM25 + tag filter | ⚠️ filename scan + read |
| Update entities | ✅ `sage_memory_update` | ✅ edit file |
| Delete entities | ✅ CASCADE removes edges | ✅ delete file + clean relations |
| Create relations | ✅ `sage_memory_link` | ✅ `relations:` in entity file |
| Multi-hop traversal | ✅ `sage_memory_graph` | ❌ not available |
| Cycle detection | ✅ built into graph tool | ⚠️ manual trace |
| Browse by type | ✅ `sage_memory_list` | ✅ scan `ont-` files |

**How to detect backend:** At session start, call `sage_memory_set_project`
with the project root path. If it responds, use MCP. If not, use
`.sage-memory/` files.

**Agent-driven extraction (0.9+).** Ontology entities are populated
primarily by passing `entities` and `relations` to `sage_memory_store`
from the calling agent:

```
sage_memory_store(
  content: "...",
  entities: [{name: "PaymentOrchestrator", type: "CONCEPT"}],
  relations: [{from: "PaymentOrchestrator", to: "Stripe", rel: "depends_on"}]
)
```

The background worker is a fallback that runs only when an LLM API
key is configured AND the agent didn't pass an extraction payload.
Prefer the agent-driven path: your model has the full conversational
context, the worker only sees the stored content.

## Core Model

**Entities** hold properties. **Relations** connect two entities with a
typed, directed edge.

```
Entity:   [Task:task_a1b2] "Fix payment timeout"
Relation: task_a1b2 —blocks→ task_f3a4
```

## Entity Operations

### Create Entity

**With MCP:**
```
sage_memory_store(
  title: "[Task:task_a1b2] Fix payment timeout in checkout flow",
  content: '{"id":"task_a1b2","type":"Task","properties":{"title":"Fix payment timeout","status":"open","priority":"high"}}',
  tags: ["ontology", "entity", "task", "billing", "checkout"],
  scope: "project"
)
```

**With files:**
```
File: .sage-memory/ont-task-a1b2-fix-payment-timeout.md

---
tags: [ontology, entity, task, billing, checkout]
type: ontology
scope: project
entity_id: task_a1b2
entity_type: Task
created: 2026-03-20
---

{"id":"task_a1b2","type":"Task","properties":{"title":"Fix payment timeout","status":"open","priority":"high"}}
```

**Filename convention:** `ont-{type}-{id}-{short-description}.md`

**ID format:** `{type_prefix}_{8_hex}` — e.g., `task_a1b2c3d4`,
`pers_e5f6a7b8`, `proj_c9d0e1f2`

### Search Entities

**With MCP:**
```
sage_memory_search(query: "task_a1b2", filter_tags: ["ontology", "entity"])
sage_memory_search(query: "open tasks billing", filter_tags: ["ontology", "entity", "task"])
```

**FTS5 safety:** Search by bare entity ID, never by bracket title.

**With files:** Scan `.sage-memory/` for `ont-` prefixed files. Filter
by type: `ont-task-*` for tasks, `ont-pers-*` for persons. Read matching
files to check properties.

### Browse All Entities

**With MCP:** `sage_memory_list(tags: ["ontology", "entity", "task"])`

**With files:** List all `ont-task-*.md` files in `.sage-memory/`.

### Delete Entity

**With MCP:** `sage_memory_delete(id: "<entity_memory_id>")` — CASCADE
automatically removes all edges.

**With files:** Delete the entity file. Then scan other `ont-*.md` files
for `relations:` entries referencing this entity's ID and remove them.

## Relation Operations

### Create Relation

**With MCP:**
```
sage_memory_link(
  source_id: "<source_memory_id>",
  target_id: "<target_memory_id>",
  relation: "blocks",
  properties: {"reason": "payment flow must complete first"}
)
```

One call. Validation before creating:
1. Check type compatibility (see schema reference)
2. Check cardinality (many_to_one → replace existing if found)
3. For `blocks`/`depends_on` → cycle check via `sage_memory_graph`

**With files:** Add a `relations:` section to the source entity's file:

```
File: .sage-memory/ont-task-a1b2-fix-payment-timeout.md

---
tags: [ontology, entity, task, billing, checkout]
type: ontology
scope: project
entity_id: task_a1b2
entity_type: Task
created: 2026-03-20
relations:
  - rel: blocks
    target: task_f3a4
    target_type: Task
  - rel: assigned_to
    target: pers_e5f6
    target_type: Person
---

{"id":"task_a1b2","type":"Task","properties":{"title":"Fix payment timeout","status":"open","priority":"high"}}
```

Relations live inside the source entity's frontmatter. This is
denormalized but avoids separate relation files and works without a
database. To find what blocks task_f3a4, scan all `ont-task-*.md` files
for `relations:` entries with `target: task_f3a4`.

### Delete Relation

**With MCP:**
```
sage_memory_link(
  source_id: "<source_id>", target_id: "<target_id>",
  relation: "blocks", delete: true
)
```

**With files:** Edit the source entity file — remove the relation entry
from the `relations:` list.

### Cycle Check

**With MCP:**
```
sage_memory_graph(
  id: "<target_memory_id>",
  relation: "blocks",
  direction: "outbound",
  depth: 5
)
```
If source_id appears in results → cycle → reject.

**With files:** Manually trace the chain. Read target's file → check its
`relations:` for outbound `blocks` → follow to next entity → repeat.
If you return to the source, it's a cycle. Practical for graphs under
20 edges of that type.

## Graph Traversal (MCP only)

### What tasks does project X have?
```
sage_memory_graph(id: "<project_id>", relation: "has_task", direction: "outbound", depth: 1)
```

### What blocks task X, and what blocks those?
```
sage_memory_graph(id: "<task_id>", relation: "blocks", direction: "inbound", depth: 2)
```

### Full neighborhood
```
sage_memory_graph(id: "<entity_id>", direction: "both", depth: 1)
```

**With files:** Multi-hop traversal is not available. Use single-hop
lookups by scanning `relations:` in entity files. For tasks in a project,
scan all `ont-task-*.md` files for `relations:` entries like
`{rel: part_of, target: <project_id>}`.

## Planning as Graph Transformation

```
Plan: "Set up feature project with tasks"

1. CREATE Project → sage_memory_store (or file)
2. CREATE Task1 → sage_memory_store (or file)
3. CREATE Task2 → sage_memory_store (or file)
4. RELATE has_task: Project → Task1 → sage_memory_link (or add to file)
5. RELATE has_task: Project → Task2 → sage_memory_link (or add to file)
6. RELATE blocks: Task1 → Task2 → sage_memory_link (after cycle check)
7. VALIDATE: no cycles ✓, cardinality ✓
```

### Validating a planned mutation with `graph_check.py`

`scripts/graph_check.py` is a zero-dependency Python validator. Pipe
it a JSON document describing the entities and proposed relations to
get a structural OK / FAIL plus a list of violations. Use it before
the agent calls `sage_memory_link` for a non-trivial plan.

```bash
python3 scripts/graph_check.py <<'EOF'
{
  "entities": [
    {"id": "proj_c9d0", "type": "Project"},
    {"id": "task_a1b2", "type": "Task"},
    {"id": "task_f3a4", "type": "Task"}
  ],
  "relations": [
    {"from": "proj_c9d0", "to": "task_a1b2", "rel": "has_task"},
    {"from": "proj_c9d0", "to": "task_f3a4", "rel": "has_task"},
    {"from": "task_a1b2", "to": "task_f3a4", "rel": "blocks"}
  ]
}
EOF
```

Exit code 0 = valid; 1 = violations (printed as JSON to stdout).
Checks type compatibility, cardinality, and acyclicity for `blocks`
and `depends_on` chains. See the script's docstring for the full
input schema.

## Validation Rules

### Required Properties

| Type | Required |
|------|----------|
| Task | title, status |
| Person | name |
| Project | name |
| Event | title, start |
| Document | title |

### Relation Types

The full controlled vocabulary lives in
[`references/schema.md`](references/schema.md). All 11 built-in
relations:

| Relation | From → To | Cardinality | Acyclic |
|----------|-----------|-------------|---------|
| has_owner | Project, Task → Person | many_to_one | no |
| assigned_to | Task → Person | many_to_one | no |
| has_task | Project → Task | one_to_many | no |
| has_goal | Project → Goal | one_to_many | no |
| part_of | Task, Document, Event → Project | many_to_one | no |
| blocks | Task → Task | many_to_many | **yes** |
| depends_on | Task, Project → Task, Project, Event | many_to_many | **yes** |
| member_of | Person → Organization | many_to_many | no |
| mentions | Document, Message, Note → Person, Project, Task, Event | many_to_many | no |
| follows_up | Task, Event → Event, Message | many_to_one | no |
| attendee_of | Person → Event | many_to_many | no |

Custom relation strings are accepted by `sage_memory_link` but only
the 11 above are validated by `graph_check.py`. Stick to the
controlled vocabulary unless the project clearly needs an extension.

**Credential safety:** Never store `password`, `secret`, `token`,
`api_key` as properties.

### Extending Types

Store a schema extension for custom types (works with both backends):

**With MCP:**
```
sage_memory_store(
  title: "[Schema:Sprint] Custom entity type",
  content: '{"type":"Sprint","required":["name","start","end"]}',
  tags: ["ontology", "schema"]
)
```

**With files:**
```
File: .sage-memory/ont-schema-sprint.md

---
tags: [ontology, schema]
type: ontology
---

{"type":"Sprint","required":["name","start","end"],"enums":{"status":["planning","active","closed"]}}
```

## References

- `references/encoding.md` — Full format, examples, search patterns
- `references/schema.md` — All types, relations, constraints
- `scripts/graph_check.py` — Structural validator
