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
  Also trigger when the memory skill is active and the agent needs typed
  structure beyond flat prose.
version: "1.0.0"
type: process
---

# Ontology

Typed knowledge graph on sage-memory. Entities and relations stored as
separate memory entries — searchable by BM25, zero file I/O, zero
consistency risk.

**Part of the unified knowledge system.** Ontology is a facet of the
memory skill — it stores through sage-memory with the `ontology` tag.
During recall, ontology entries surface alongside regular knowledge and
self-learning entries, giving the agent structural context (what depends
on what, who owns what) in addition to prose understanding.

**Prerequisite:** sage-memory MCP tools (`sage_memory_store`, `sage_memory_search`,
`sage_memory_update`, `sage_memory_delete`). If unavailable, degrade gracefully.

## Core Model

Two kinds of memory entries:

```
Entity:   [Task:task_a1b2]  "Fix payment timeout"    → the node
Relation: [Rel:blocks]      "task_a1b2 → task_f3a4"  → the edge
```

Entities hold properties. Relations are independent entries linking
two entities. One write per relation — no bidirectional update, no
consistency risk.

## Encoding

**Read:** `references/encoding.md` for full format and examples.

### Entity

```
sage_memory_store:
  title: "[Task:task_a1b2] Fix payment timeout in checkout flow"
  content: '{"id":"task_a1b2","type":"Task","properties":{"title":"Fix payment timeout","status":"open","priority":"high"}}'
  tags: ["ontology", "entity", "task", "billing", "payments"]
  scope: "project"
```

### Relation

```
sage_memory_store:
  title: "[Rel:blocks] Fix payment timeout → Deploy checkout page"
  content: '{"from_id":"task_a1b2","from_type":"Task","rel":"blocks","to_id":"task_f3a4","to_type":"Task"}'
  tags: ["ontology", "rel", "blocks", "edge:task_a1b2", "edge:task_f3a4"]
  scope: "project"
```

### ID format

`{type_prefix}_{8_hex}` — prefix = first 4 lowercase chars of type.

```
Task → task_a1b2c3d4    Person → pers_e5f6a7b8
Project → proj_c9d0e1f2  Event → even_a3b4c5d6
```

## Session Bootstrap

At session start (or first ontology trigger), probe whether a graph
exists:

```
sage_memory_search: tags=["ontology"], limit=5
```

**Results found:** A graph exists. Note the types and domains visible
in the results. Use this context to inform subsequent operations —
you know the graph's vocabulary and shape without loading everything.

**No results:** No graph yet. This is normal for a new project.
Proceed without graph context. The graph grows organically as the
agent creates entities during work.

**Don't announce this probe.** If the graph exists, use its context
naturally. If it doesn't, say nothing about ontology — just work
normally. Same principle as the memory skill's "empty first session."

## Operations

### Create entity

1. Generate ID: `f"{type.lower()[:4]}_{uuid4().hex[:8]}"`
2. Validate: check required properties, enum values (see Validation)
3. `sage_memory_store` with encoding above

### Search

```
sage_memory_search: "open tasks billing"                                     ← natural language
sage_memory_search: query="task_a1b2", tags=["ontology", "entity"]           ← exact ID
sage_memory_search: query="tasks in billing", tags=["ontology", "entity", "task"]  ← typed
```

**FTS5 safety:** Entity IDs (`task_a1b2`) are plain alphanumeric
tokens — always safe to search. Never search for the bracket title
directly (`[Task:task_a1b2]`) as brackets are FTS5 special characters.
Search by the bare ID with entity tags instead. Brackets exist in
titles for human readability only, not for query use.

### Create relation

1. Validate: check type compatibility, cardinality (see Validation)
2. For `blocks` / `depends_on`: check no cycle (see Validation)
3. Single `sage_memory_store` with relation encoding

One MCP call. No second entity to update. No half-link risk.

### Find relations

```
sage_memory_search: tags=["ontology", "rel", "edge:task_a1b2"]          ← all relations for entity
sage_memory_search: tags=["ontology", "rel", "blocks", "edge:task_a1b2"] ← blocks from/to entity
sage_memory_search: tags=["ontology", "rel", "blocks"]                   ← all blocks relations
```

### Traverse

"What tasks does project X have?"

1. `sage_memory_search: tags=["ontology", "rel", "has_task", "edge:proj_e5f6"]`
   → returns relation entries with to_id for each task
2. If full task details needed:
   `sage_memory_search: query="{to_id}", tags=["ontology", "entity", "task"]`

For display-only: relation titles contain human-readable labels,
often sufficient without fetching the target entity.

### Delete relation

`sage_memory_delete` the relation entry. Done. No second entity to clean up.

### Delete entity

1. `sage_memory_search: tags=["ontology", "rel", "edge:{entity_id}"]`
   → find all relations involving this entity
2. `sage_memory_delete` each relation
3. `sage_memory_delete` the entity

## Validation

### Agent-inline (every write, no script)

**Required properties:**

| Type | Required |
|------|----------|
| Task | title, status |
| Person | name |
| Project | name |
| Event | title, start |
| Document | title |

**Enum values:**

| Field | Allowed |
|-------|---------|
| Task.status | open, in_progress, blocked, done, cancelled |
| Task.priority | low, medium, high, urgent |
| Project.status | planning, active, paused, completed, archived |

**Relation type rules:**

| Relation | From → To | Cardinality |
|----------|-----------|-------------|
| has_owner | Project,Task → Person | many_to_one |
| has_task | Project → Task | one_to_many |
| assigned_to | Task → Person | many_to_one |
| blocks | Task → Task | many_to_many, **acyclic** |
| part_of | Task,Document → Project | many_to_one |
| depends_on | Task,Project → Task,Project | many_to_many, **acyclic** |

**Cardinality check:** For `many_to_one`, before storing a relation,
search for existing relations of the same type from the same source.
If one exists, replace it — don't create a duplicate.

**Credential safety:** Never store `password`, `secret`, `token`,
`api_key` as properties. Use `secret_ref` pointing to external storage.

On validation failure: inform the user, suggest correction, don't store.

### Cycle check (before `blocks` / `depends_on` only)

**Small graph (< 20 edges of that type):** Trace manually. Follow
the chain from target: does it lead back to source? If yes, reject.

**Larger graph:** Pull all relation entries of that type from memory,
pipe to the checker script:

```bash
echo '{"entities":[...],"relations":[...]}' | python3 scripts/graph_check.py --check cycles
```

**Read:** `scripts/graph_check.py` header for input format.

### Audit (on demand)

Run full consistency check across all ontology entries:

1. `sage_memory_search: tags=["ontology"]` — pull all entries
2. Pipe to `python3 scripts/graph_check.py --check all`
3. Review errors. Repair: delete broken relations, fix missing
   properties via `sage_memory_update`.

## Planning as Graph Transformation

Model plans as a sequence of validated graph operations:

```
Plan: "Set up feature project with tasks"

1. CREATE Project { name: "Dark mode", status: "planning" }
2. CREATE Task { title: "Audit color tokens", status: "open" }
3. CREATE Task { title: "Update theme config", status: "open" }
4. RELATE has_task: Project → Task1
5. RELATE has_task: Project → Task2
6. RELATE blocks: Task1 → Task2
7. VALIDATE: no cycles ✓, cardinality ✓
8. COMMIT: 3 sage_memory_store (entities) + 3 sage_memory_store (relations)
```

Six MCP calls total. In v0.2's bidirectional design, the same plan
would take 12 calls (3 entities + 3 relations × 3 updates each).

## Extending Types

The core types (Task, Person, Project, Event, Document) cover most
needs. To add a custom type, store a schema extension:

```
sage_memory_store:
  title: "[Schema:Experiment] Custom entity type"
  content: '{"type":"Experiment","required":["hypothesis","status"],"enums":{"status":["planned","running","concluded"]}}'
  tags: ["ontology", "schema"]
```

The agent searches for `tags=["ontology","schema"]` when encountering
an unknown type and applies those validation rules.

## Skill Contract

Skills using ontology should declare in their SKILL.md:

```yaml
ontology:
  reads: [Task, Project]
  writes: [Task]
```

This enables cross-skill coordination through the graph.

## Complementary to Memory Skill

- **Memory skill** → prose insights ("billing uses sagas because...")
- **Ontology** → structured facts (Task X blocks Task Y, owned by Z)

Use both. They serve different retrieval needs.

## References

- `references/encoding.md` — Full format, examples, search patterns
- `references/schema.md` — All types, relations, constraints
- `scripts/graph_check.py` — In-memory structural validator
