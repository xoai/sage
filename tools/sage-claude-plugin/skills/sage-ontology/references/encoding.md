# Encoding Reference

How ontology entities and relations map to sage-memory.

## Design Principle

- **Entities** are memories. Use `sage_memory_store` with ontology
  tags and structured content.
- **Relations** are real graph edges. Use `sage_memory_link` to
  create them and `sage_memory_graph` to traverse them. Edges live
  in their own database table (not as memory entries) and CASCADE
  when either endpoint is deleted.

This is a single MCP call per operation. No half-links, no manual
adjacency lists, no repair logic.

## Entity Format

```
sage_memory_store:
  title:   "[{Type}:{id}] {descriptive title}"
  content: JSON string (see below)
  tags:    ["ontology", "entity", "{type_lower}", ...domain_tags]
  scope:   "project" | "global"
```

The returned `memory_id` is what `sage_memory_link` later wires
edges to. The `id` inside `content` is an agent-side identifier
(used inside titles and prose); the `memory_id` returned by store
is what the graph indexes on.

Content JSON:

```json
{
  "id": "task_a1b2c3d4",
  "type": "Task",
  "properties": {
    "title": "Fix payment timeout in checkout flow",
    "status": "open",
    "priority": "high"
  }
}
```

Entities contain **only properties** — relations are not embedded
inside endpoints. The graph is owned by `sage_memory_link`.

### Entity Examples

**Task:**
```
title:   "[Task:task_a1b2] Fix payment timeout in checkout flow"
content: {"id":"task_a1b2","type":"Task","properties":{"title":"Fix payment timeout in checkout flow","status":"open","priority":"high"}}
tags:    ["ontology", "entity", "task", "billing", "checkout"]
```

**Person:**
```
title:   "[Person:pers_e5f6] Alice Chen — backend lead"
content: {"id":"pers_e5f6","type":"Person","properties":{"name":"Alice Chen","email":"alice@example.com","role":"Backend Lead"}}
tags:    ["ontology", "entity", "person", "backend"]
```

**Project:**
```
title:   "[Project:proj_c9d0] Billing v2 migration"
content: {"id":"proj_c9d0","type":"Project","properties":{"name":"Billing v2 migration","status":"active","description":"Migrate to saga-based architecture"}}
tags:    ["ontology", "entity", "project", "billing", "migration"]
```

## Relation Format

Use `sage_memory_link` — a single MCP call that creates a typed,
directed edge in the `edges` table.

```
sage_memory_link:
  source_id: "<memory_id of from-entity>"
  target_id: "<memory_id of to-entity>"
  relation:  "blocks" | "depends_on" | "has_task" | "assigned_to" | "part_of" | "contains" | "relates_to" | <custom>
  properties: { "confidence": 0.9, ... }   # optional JSON
  scope:     "project" | "global"           # defaults to project
```

Built-in relation types are listed for guidance; any string is
accepted. See [schema.md](schema.md) for the full controlled
vocabulary and which entity types each relation connects.

### Relation Examples

**blocks (Task → Task):**
```
sage_memory_link:
  source_id: "mem_payment_timeout"  # memory_id of [Task:task_a1b2]
  target_id: "mem_deploy_checkout"  # memory_id of [Task:task_f3a4]
  relation:  "blocks"
```

**has_task (Project → Task):**
```
sage_memory_link:
  source_id: "mem_billing_v2"        # memory_id of [Project:proj_c9d0]
  target_id: "mem_payment_timeout"   # memory_id of [Task:task_a1b2]
  relation:  "has_task"
```

**assigned_to (Task → Person):**
```
sage_memory_link:
  source_id: "mem_payment_timeout"
  target_id: "mem_alice"
  relation:  "assigned_to"
  properties: { "since": "2026-05-01" }
```

## Search Patterns

### Entity lookup

```
sage_memory_search: query="task_a1b2", filter_tags=["ontology","entity"]            → exact ID
sage_memory_search: query="Fix payment timeout"                                       → by content
sage_memory_search: query="open tasks", filter_tags=["ontology","entity","task"]      → by type
sage_memory_search: query="Alice Chen", filter_tags=["ontology","entity","person"]    → person by name
```

**FTS5 safety:** Search by bare entity ID + tag filter, never by
bracket title. The ID `task_a1b2` is a plain alphanumeric token that
FTS5 handles natively. Brackets in titles are for human readability,
not for query use.

### Relation traversal

```
sage_memory_graph: id="<memory_id>", direction="outbound", depth=1
  → all edges OUT of this entity (one hop)

sage_memory_graph: id="<memory_id>", direction="inbound", relation="blocks"
  → all entities that block this one

sage_memory_graph: id="<memory_id>", direction="both", depth=2
  → 2-hop neighborhood in any direction
```

Returns memory nodes + edges with their properties. No tag-search
parsing required; the graph index does the work.

### Traversal: "What tasks does project X have?"

```
sage_memory_graph: id="<memory_id of project>", relation="has_task", direction="outbound", depth=1
  → returns all Task entities reachable via has_task
```

One call. Endpoints come back as full memory rows.

### Traversal: "What blocks task X?"

```
sage_memory_graph: id="<memory_id of task>", relation="blocks", direction="inbound", depth=1
  → returns all entities that block this task
```

## Creating a Relation — Step by Step

Example: task_a1b2 blocks task_f3a4.

**1. Get the memory_ids** for both entities (search by entity ID).

**2. Validate type compatibility** (see schema.md). `blocks`
allows Task → Task. Both are Tasks. OK.

**3. Check for cycles** if the relation is declared acyclic.
Use `sage_memory_graph(id=target, relation="blocks",
direction="outbound", depth=5)` and verify the source is not
reachable. Or use the `scripts/graph_check.py` helper (see
SKILL.md).

**4. Create the edge:**
```
sage_memory_link:
  source_id: "<memory_id of task_a1b2>"
  target_id: "<memory_id of task_f3a4>"
  relation: "blocks"
```

One call. Done.

## Deleting a Relation

```
sage_memory_link:
  source_id: "<memory_id of task_a1b2>"
  target_id: "<memory_id of task_f3a4>"
  relation: "blocks"
  delete: true
```

The `delete: true` flag removes the edge. No memory deletion
involved.

## Deleting an Entity

```
sage_memory_delete: <memory_id>
```

Edges CASCADE automatically when either endpoint is deleted (per
the `edges` table foreign keys). No manual edge cleanup needed.

## Performance

| Operation | MCP calls | Notes |
|-----------|-----------|-------|
| Create entity | 1 | `sage_memory_store` |
| Create relation | 1 | `sage_memory_link` |
| Find entity by ID | 1 | `sage_memory_search` |
| Traverse N edges (one hop, any direction) | 1 | `sage_memory_graph` returns nodes + edges |
| Traverse multi-hop subgraph | 1 | Same; set `depth` (1-5) |
| Delete relation | 1 | `sage_memory_link` with `delete: true` |
| Delete entity (with edges) | 1 | Edges CASCADE via FK |

## Historical note

Pre-0.5 sage-memory had no graph primitives; relations were
emulated by storing tagged "edge entries" and indexing via tag
filters (`edge:<id>` tag pairs). That pattern is fully replaced by
`sage_memory_link` + the `edges` table as of 0.5.0. If you see
`edge:<id>` tags in an older project DB, they're harmless but
won't participate in `sage_memory_graph` traversal — re-emit them
as real edges if you need graph queries to find them.
