---
name: ontology
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

| Relation | From → To | Cardinality | Acyclic |
|----------|-----------|-------------|---------|
| has_owner | Project,Task → Person | many_to_one | no |
| has_task | Project → Task | one_to_many | no |
| assigned_to | Task → Person | many_to_one | no |
| blocks | Task → Task | many_to_many | **yes** |
| part_of | Task,Document → Project | many_to_one | no |
| depends_on | Task,Project → Task,Project | many_to_many | **yes** |

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
