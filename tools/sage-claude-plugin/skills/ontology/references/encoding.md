# Encoding Reference

How ontology entities and relations map to sage-memory entries.

## Design Principle

Entities and relations are **separate entries**. A relation is not
embedded inside its endpoints — it's an independent memory entry with
its own tags. This means:

- Creating a relation = 1 `sage_memory_store` call (not 2 updates)
- Deleting a relation = 1 `sage_memory_delete` call (not 2 updates)
- No half-links, no consistency risk, no repair needed
- Relations are independently searchable by type, by endpoint, or
  by natural language

## Entity Format

```
sage_memory_store:
  title:   "[{Type}:{id}] {descriptive title}"
  content: JSON string (see below)
  tags:    ["ontology", "entity", "{type_lower}", ...domain_tags]
  scope:   "project" | "global"
```

Content JSON:

```json
{
  "id": "task_a1b2c3d4",
  "type": "Task",
  "properties": {
    "title": "Fix payment timeout in checkout flow",
    "status": "open",
    "priority": "high",
    "assignee": "pers_e5f6a7b8"
  }
}
```

Entities contain **only properties** — no relation arrays. Relations
live in their own entries.

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

```
sage_memory_store:
  title:   "[Rel:{rel_type}] {source_label} → {target_label}"
  content: JSON string (see below)
  tags:    ["ontology", "rel", "{rel_type}", "edge:{from_id}", "edge:{to_id}"]
  scope:   same as the entities it connects
```

Content JSON:

```json
{
  "from_id": "task_a1b2",
  "from_type": "Task",
  "rel": "blocks",
  "to_id": "task_f3a4",
  "to_type": "Task"
}
```

### Tag Design

The `edge:{id}` tags are the graph's index. They enable:

- `tags=["edge:task_a1b2"]` → all relations involving task_a1b2
- `tags=["rel", "blocks", "edge:task_a1b2"]` → blocks from/to task_a1b2
- `tags=["rel", "blocks"]` → all blocks relations in the project

This replaces the manual adjacency lists of v0.2. sage-memory's tag
filtering does the index lookup.

### Relation Examples

**blocks (Task → Task):**
```
title:   "[Rel:blocks] Fix payment timeout → Deploy checkout page"
content: {"from_id":"task_a1b2","from_type":"Task","rel":"blocks","to_id":"task_f3a4","to_type":"Task"}
tags:    ["ontology", "rel", "blocks", "edge:task_a1b2", "edge:task_f3a4"]
```

**has_task (Project → Task):**
```
title:   "[Rel:has_task] Billing v2 → Fix payment timeout"
content: {"from_id":"proj_c9d0","from_type":"Project","rel":"has_task","to_id":"task_a1b2","to_type":"Task"}
tags:    ["ontology", "rel", "has_task", "edge:proj_c9d0", "edge:task_a1b2"]
```

**assigned_to (Task → Person):**
```
title:   "[Rel:assigned_to] Fix payment timeout → Alice Chen"
content: {"from_id":"task_a1b2","from_type":"Task","rel":"assigned_to","to_id":"pers_e5f6","to_type":"Person"}
tags:    ["ontology", "rel", "assigned_to", "edge:task_a1b2", "edge:pers_e5f6"]
```

## Search Patterns

### Entity lookup

```
sage_memory_search: query="task_a1b2", tags=["ontology","entity"]            → exact ID (FTS5-safe)
sage_memory_search: "Fix payment timeout"                                     → by content
sage_memory_search: query="open tasks", tags=["ontology","entity","task"]     → by type
sage_memory_search: query="Alice Chen", tags=["ontology","entity","person"]   → person by name
```

**FTS5 safety:** Always search by bare entity ID + tag filter, never
by bracket title. The ID `task_a1b2` is a plain alphanumeric token
that FTS5 handles natively. Brackets in titles are for human
readability in sage-memory's list view — not for query use.

### Relation lookup

```
sage_memory_search: tags=["ontology","rel","edge:task_a1b2"]               → all relations for entity
sage_memory_search: tags=["ontology","rel","blocks","edge:task_a1b2"]      → blocks involving entity
sage_memory_search: tags=["ontology","rel","has_task","edge:proj_c9d0"]    → tasks in project
sage_memory_search: tags=["ontology","rel","assigned_to","edge:pers_e5f6"] → assignments to person
```

### Traversal: "What tasks does project X have?"

```
Step 1: sage_memory_search tags=["ontology","rel","has_task","edge:proj_c9d0"]
  → returns: [Rel:has_task] Billing v2 → Fix payment timeout
             [Rel:has_task] Billing v2 → Migrate Stripe SDK
  → parse content → to_id = task_a1b2, task_x9y8

Step 2 (if full details needed):
  sage_memory_search: query="task_a1b2", tags=["ontology","entity"]
  sage_memory_search: query="task_x9y8", tags=["ontology","entity"]
```

Often step 1 alone is sufficient — the relation title contains
human-readable labels for both endpoints.

### Traversal: "What blocks task X?"

```
sage_memory_search: tags=["ontology","rel","blocks","edge:task_f3a4"]
  → returns all blocks relations involving task_f3a4
  → filter: where to_id == "task_f3a4" (incoming blocks)
  → from_id values are the blockers
```

## Creating a Relation — Step by Step

Example: task_a1b2 blocks task_f3a4.

**1. Validate type compatibility:**
`blocks` allows Task → Task. Both are Tasks. OK.

**2. Validate cardinality:**
`blocks` is many_to_many. No limit. OK.

**3. Check for cycles (acyclic relation):**
Search: `tags=["ontology","rel","blocks"]` → get all blocks relations.
Trace from task_f3a4 forward: does any chain lead back to task_a1b2?
If yes → reject. If no → proceed.

**4. Store:**
```
sage_memory_store:
  title: "[Rel:blocks] Fix payment timeout → Deploy checkout page"
  content: {"from_id":"task_a1b2","from_type":"Task","rel":"blocks","to_id":"task_f3a4","to_type":"Task"}
  tags: ["ontology","rel","blocks","edge:task_a1b2","edge:task_f3a4"]
```

One call. Done.

## Deleting a Relation

```
sage_memory_search: query="task_a1b2 blocks task_f3a4", tags=["ontology","rel","blocks"]
  → find the entry
sage_memory_delete: {id}
```

One search + one delete. No other entities to update.

## Deleting an Entity

```
sage_memory_search: tags=["ontology","rel","edge:task_a1b2"]
  → find all relations involving this entity
sage_memory_delete each relation
sage_memory_delete the entity
```

## Performance

| Operation | MCP calls | Notes |
|-----------|-----------|-------|
| Create entity | 1 | Single store |
| Create relation | 1 | Single store |
| Find entity by ID | 1 | Search by bare ID + entity tag |
| Find all relations for entity | 1 | Search by edge tag |
| Traverse N relations + get details | 1 + N | Tag search + N ID lookups |
| Delete relation | 1-2 | Search + delete |
| Delete entity + relations | 1 + R + 1 | Find R relations, delete all |

Compare with v0.2 bidirectional design: creating a relation was
2 searches + 2 updates = 4 calls. Now it's 1 call.
