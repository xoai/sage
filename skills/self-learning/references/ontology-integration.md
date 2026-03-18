# Ontology Integration

How self-learning and the ontology skill work together. The ontology
skill is optional — self-learning works fully without it. But when both
are active, the graph enables targeted recall and richer review.

## Level 1: Edge Tag Cross-Referencing (Current)

The ontology skill uses `edge:{entity_id}` tags on relation entries to
build a traversal index. Self-learning reuses this convention to link
learnings to ontology entities.

### How to Link

When capturing a learning, if you know the relevant ontology entity ID
(a task you're working on, a project, a person who flagged the issue),
add `edge:{entity_id}` to the learning's tags:

```
memory_store:
  title: "[LRN:gotcha] ReportBuilder N+1 query causes timeout"
  content: "..."
  tags: ["self-learning", "gotcha", "database", "edge:task_a1b2"]
  scope: "project"
```

### How to Discover Entity IDs

If the ontology skill is active, search for the relevant entity:

```
memory_search: query="payment timeout", tags=["ontology", "entity", "task"]
→ [Task:task_a1b2] Fix payment timeout in checkout flow
```

Use the ID from the result in the learning's `edge:` tag.

Don't search for an entity ID if you don't already know one exists. The
edge tag is a bonus — omitting it just means the learning relies on
keyword search instead of graph traversal. Both work.

### Targeted Recall

During recall, if you know the current task's ontology ID, use it:

```
memory_search: filter_tags=["self-learning", "edge:task_a1b2"]
```

This returns only learnings directly linked to that task — higher
precision than a keyword search. If no edge-linked learnings exist,
fall back to keyword search as normal.

### What This Enables

**Task-scoped learnings.** "Show me what went wrong last time someone
worked on this task."

**Module-scoped learnings.** If ontology tracks modules as entities,
`edge:mod_billing` tags collect all billing-related learnings.

**Person-linked learnings.** If a user flags issues frequently, link
their corrections to their person entity. During review, you can see
which person's feedback generated the most learnings.

**Cross-query.** Ontology's standard traversal finds all edges for an
entity: `tags=["ontology", "rel", "edge:task_a1b2"]`. By also using
`edge:task_a1b2` in learning tags, a single edge tag search returns
both ontology relations AND learning links. The agent distinguishes
them by the presence of `self-learning` vs `ontology` in the tags.

## Level 2: Learning as Entity Type (Future)

When learnings become complex enough to need their own relationships
(supersession chains, causal links between learnings, shared root
causes), they can be modeled as ontology entities.

### Schema Extension

Pre-register the Learning type for future use:

```
memory_store:
  title: "[Schema:Learning] Custom entity type for self-learning"
  content: '{"type":"Learning","required":["title","type","prevention"],"enums":{"type":["gotcha","correction","convention","api-drift","error-fix"],"status":["active","stale","superseded","promoted"]}}'
  tags: ["ontology", "schema"]
```

### Potential Relations

| Relation | From | To | Purpose |
|----------|------|----|---------|
| applies_to | Learning | Task, Project, Document | Links learning to what it's about |
| supersedes | Learning | Learning | Newer learning replaces older one |
| caused_by | Learning | Task, Event | What triggered the discovery |
| related_to | Learning | Learning | Shared root cause or theme |

### When to Upgrade

Don't implement Level 2 until:
- The project has 50+ learnings that need relationship tracking
- Review workflow reveals learnings that need supersession chains
- Cross-skill coordination needs Learning entities (e.g., a reporting
  skill that queries learning patterns)

Level 1 (edge tags) handles most needs. Upgrade when evidence demands.

## Skill Contract

If self-learning adopts Level 2 ontology integration, it would declare:

```yaml
ontology:
  reads: [Task, Project, Document]
  writes: [Learning]
  relations: [applies_to, supersedes, related_to]
```

This tells other skills: "self-learning produces Learning entities you
can query through the graph."

## Review Enhancements With Ontology

When both skills are active, the review workflow gains graph-aware
capabilities:

**Orphan detection.** Learnings tagged with `edge:{entity_id}` where
the entity has been deleted. These are strong stale candidates — the
context they reference no longer exists.

**Hot spot analysis.** Entities with the most `edge:` links from
learnings are the most mistake-prone areas. Worth flagging to the user:
"The billing module has 8 linked learnings — more than any other area."

**Coverage gaps.** Ontology entities (especially active tasks and
projects) with zero linked learnings. Not necessarily a problem, but
if they're complex areas, they might be uncharted territory worth
extra caution.
