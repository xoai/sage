# Ontology Integration

How self-learning and the ontology skill work together. The ontology
skill is optional — self-learning works fully without it. But when both
are active, the graph enables targeted recall and richer review.

## Linking Learnings to Entities

When capturing a learning, if you know the relevant ontology entity
(a task, module, or service), link them via `sage_memory_link`:

```
sage_memory_link(
  source_id: "<learning_memory_id>",
  target_id: "<entity_memory_id>",
  relation: "applies_to"
)
```

One call. The learning is now traversable from the entity.

### Discovering Entity IDs

If the ontology skill is active, search for the relevant entity:

```
sage_memory_search(
  query: "payment timeout",
  filter_tags: ["ontology", "entity", "task"]
)
→ [Task:task_a1b2] Fix payment timeout in checkout flow
→ use the memory ID from this result
```

Don't search for an entity if you don't already suspect one exists. The
link is a bonus — omitting it just means the learning relies on keyword
search instead of graph traversal. Both work.

## Targeted Recall

### Graph-Based (recommended)

When you know the current task's ontology entity:

```
sage_memory_graph(
  id: "<task_entity_memory_id>",
  relation: "applies_to",
  direction: "inbound",
  depth: 1
)
→ returns all learnings linked to this task
```

More precise than keyword search — finds learnings even when they use
different vocabulary than the task description.

### Keyword Fallback

When no entity exists or as a supplement:

```
sage_memory_search(
  query: "<task keywords>",
  filter_tags: ["self-learning"],
  limit: 5
)
```

## Hot Spot Analysis

Entities with many linked learnings are the most mistake-prone areas:

```
sage_memory_graph(
  id: "<module_entity_id>",
  relation: "applies_to",
  direction: "inbound",
  depth: 1
)
→ count results
```

Flag when appropriate: "The billing module has 8 linked learnings —
more than any other area. Extra caution recommended."

## Level 2: Learning as Entity Type (Future)

When learnings need their own relationships (supersession chains,
causal links, shared root causes), model them as ontology entities.
Don't implement until 50+ learnings need relationship tracking.

## Skill Contract

```yaml
ontology:
  reads: [Task, Project, Document]
  writes: [Learning]
  relations: [applies_to, supersedes, related_to]
```
