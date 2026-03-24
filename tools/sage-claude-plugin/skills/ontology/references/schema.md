# Schema Reference

Entity types, relation types, and constraints.

## Core Entity Types

Five types ship by default. Extend via `[Schema:*]` entries for
project-specific types.

### Task

```yaml
required: [title, status]
enums:
  status: [open, in_progress, blocked, done, cancelled]
  priority: [low, medium, high, urgent]
optional: [description, assignee, due, estimate_hours, tags]
```

### Person

```yaml
required: [name]
optional: [email, phone, role, notes, tags]
```

### Project

```yaml
required: [name]
enums:
  status: [planning, active, paused, completed, archived]
optional: [description, start_date, end_date, tags]
```

### Event

```yaml
required: [title, start]
constraint: if end exists, end >= start
optional: [description, end, location, status]
```

### Document

```yaml
required: [title]
optional: [path, url, summary, tags]
```

## Additional Types

Available but not validated by default. Add required-property rules
via `[Schema:*]` entries if needed.

- **Goal** — `required: [description]`
- **Note** — `required: [content]`
- **Organization** — `required: [name]`
- **Credential** — `required: [service, secret_ref]`,
  `forbidden: [password, secret, token, key, api_key]`

## Relation Types

| Relation | From | To | Cardinality | Acyclic |
|----------|------|----|-------------|---------|
| has_owner | Project, Task | Person | many_to_one | no |
| assigned_to | Task | Person | many_to_one | no |
| has_task | Project | Task | one_to_many | no |
| has_goal | Project | Goal | one_to_many | no |
| part_of | Task, Document, Event | Project | many_to_one | no |
| blocks | Task | Task | many_to_many | **yes** |
| depends_on | Task, Project | Task, Project, Event | many_to_many | **yes** |
| member_of | Person | Organization | many_to_many | no |
| mentions | Document, Message, Note | Person, Project, Task, Event | many_to_many | no |
| follows_up | Task, Event | Event, Message | many_to_one | no |
| attendee_of | Person | Event | many_to_many | no |

### Cardinality Rules

- **many_to_one**: Source entity can have at most one outgoing relation
  of this type. Before storing, check for existing. Replace if found.
- **one_to_many**: Target entity can have at most one incoming relation
  of this type. Before storing, check for existing. Warn if found.
- **many_to_many**: No limit.

### Acyclicity Rules

`blocks` and `depends_on` must not form cycles. Before creating
either relation, verify no path exists from target back to source
through existing relations of the same type.

## Custom Relations

If the project needs a relation not listed here, create it freely.
Unknown relation types pass validation — they're only checked if
a spec exists. Document custom relations in a `[Schema:*]` entry:

```
sage_memory_store:
  title: "[Schema:mentors] Custom relation type"
  content: '{"rel":"mentors","from_types":["Person"],"to_types":["Person"],"cardinality":"many_to_many","acyclic":false}'
  tags: ["ontology", "schema"]
```

## Extending Entity Types

Store a schema extension entry:

```
sage_memory_store:
  title: "[Schema:Sprint] Custom entity type"
  content: '{"type":"Sprint","required":["name","start","end"],"enums":{"status":["planning","active","closed"]}}'
  tags: ["ontology", "schema"]
```

The agent searches `tags=["ontology","schema"]` when encountering
an unknown type and applies validation rules from matching entries.

The `graph_check.py` script validates against the core schema.
Custom types are validated only by the agent inline — the script
treats unknown types permissively.
