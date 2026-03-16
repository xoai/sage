# Template Contract

**Version:** 1.0.0
**Status:** Stable

A template defines the SHAPE of an output document. Templates are used by skills
to produce consistent, structured artifacts (specs, plans, tasks, architecture docs, etc.).

Templates are separate from skills because different teams want different document shapes
for the same type of output. A startup's spec template is sparse. An enterprise's is
comprehensive. The `specify` skill works with either.

---

## Required File Structure

```
develop/templates/<document-type>/
└── <variant>.template.md       # REQUIRED — Template definition
```

Templates are single files grouped by document type. Each type can have multiple
variants for different contexts.

---

## Required Frontmatter

```yaml
---
# REQUIRED FIELDS
name: <string>               # Template identifier, kebab-case
type: <string>               # Document type: spec, plan, tasks, architecture, adr, review, retro
variant: <string>            # Variant name: minimal, full, brownfield, etc.
version: <semver>
description: <string>        # When to use this variant

# OPTIONAL FIELDS
mode: <string>               # Which mode typically uses this: fix, build, architect
                             # If omitted, the template is available in all modes.
replaces: <string>           # Name of the default template this replaces
sections: [<string>, ...]    # Named sections for partial loading
                             # Skills can request specific sections, not the whole template.
---
```

---

## Template Body Structure

Templates use placeholder syntax to mark where the agent fills in content:

```markdown
---
(frontmatter)
---

# {title}

## Intent
{what_and_why}

## Boundaries
{what_this_does_not_do}

## Acceptance Criteria
{how_we_know_it_works}
```

### Placeholder Conventions

- `{snake_case}` — Agent fills this based on elicitation or context
- `{?optional_field}` — Agent may omit if not relevant
- `[SECTION: name]...[/SECTION]` — Named section that can be loaded independently
- `<!-- GUIDANCE: ... -->` — Invisible instruction for the agent (not rendered in output)

```markdown
[SECTION: acceptance-criteria]
## Acceptance Criteria

<!-- GUIDANCE: Each criterion must be testable. "Works well" is not testable.
"Returns 200 OK with JSON body containing user.id" is testable. -->

{acceptance_criteria}
[/SECTION]
```

---

## Behavioral Contract

Templates MUST:

1. Use **placeholder syntax** consistently. No free-form "fill in here" instructions.
2. Include **guidance comments** for non-obvious sections.
3. Be **self-documenting**. A contributor reading the template should understand what
   goes in each section without reading external documentation.
4. Work with the **skills that reference them**. If the `specify` skill expects a
   template with sections `intent`, `boundaries`, and `acceptance-criteria`, the
   template MUST have those sections.

Templates MUST NOT:

1. Contain **logic or conditionals**. Templates are shapes, not programs.
   If a section is sometimes needed and sometimes not, use `{?optional_field}`.
2. **Hard-code technology choices**. Templates are technology-agnostic.
   "## API Endpoints" assumes a web API — use "## Interfaces" instead.
3. Be **longer than necessary**. The template is a skeleton, not a finished document.
   Shorter templates produce better output because they leave room for the agent
   to think, rather than constraining it into filling boxes.

---

## Default Templates

| Type | Variant | Mode | Purpose |
|------|---------|------|---------|
| spec | minimal | build | Intent + boundaries + acceptance (3 sections) |
| spec | full | architect | Complete PRD with personas, metrics, risks |
| spec | brownfield | build | For changes to existing systems (includes current-state) |
| plan | minimal | build | Ordered task list with file paths |
| plan | full | architect | Architecture + decision records + research + task breakdown |
| tasks | standard | all | Task breakdown with dependencies and parallel markers |
| architecture | standard | architect | System design with decision records |
| adr | standard | architect | Architectural Decision Record |
| review | standard | all | Code review report |
| retro | standard | architect | Sprint retrospective |

---

## Override / Replacement

To replace a default template:

1. Create a template with `replaces: <default-template-name>` in frontmatter.
2. Place in `.sage/develop/templates/` (project) or `community/develop/templates/` (community).
3. Ensure the replacement has at least the same named sections as the original,
   so skills that reference specific sections still work.

Adding new variants does not require replacing defaults — just create additional
template files. Skills select the appropriate variant based on the active mode
and context.
