# Sage Templates

Document shapes. The skeleton that skills fill in.

## Philosophy

Templates are separate from skills because **different teams want different
document shapes for the same type of output.** A startup's spec is three sections.
An enterprise's is twelve. Both use the same `specify` skill — just with different
templates.

Templates **channel agent behavior.** This is Spec-Kit's insight: a blank text field
produces vague output. A structured template with `[SECTION: acceptance-criteria]` and
`<!-- GUIDANCE: each criterion must be testable -->` produces specific, verifiable output.
Template design is a form of prompt engineering — the structure itself shapes quality.

Templates should be **skeletons, not finished documents.** Short templates produce
better output because they leave room for the agent to think rather than constraining
it into filling boxes. A template with 50 required fields becomes a checkbox exercise.
A template with 5 required sections becomes a thinking framework.

Templates use **named sections** (`[SECTION: name]...[/SECTION]`) so the context loader
can load only the relevant section, not the entire template. A skill working on
acceptance criteria loads only that section, preserving context budget for the actual work.

## Available Templates

| Type | Variant | Mode | Sections |
|------|---------|------|----------|
| [spec/minimal](spec/minimal.spec-template.md) | minimal | build | intent, boundaries, acceptance-criteria, affected-areas |
| [spec/full](spec/full.spec-template.md) | full | architect | problem, personas, stories, requirements, non-functional, boundaries, metrics, risks |
| [plan/standard](plan/standard.plan-template.md) | standard | all | constitution-constraints, tech-decisions, task-breakdown |
| [architecture/adr](architecture/decision-template.md) | adr | architect | context, options, decision, consequences |

## Placeholder Syntax

- `{snake_case}` — agent fills from context
- `{?optional_field}` — agent may omit
- `[SECTION: name]...[/SECTION]` — named section for partial loading
- `<!-- GUIDANCE: ... -->` — invisible instruction for the agent

## Replacing Templates

See `develop/contracts/template.contract.md`. Create with `replaces: <n>` in frontmatter.
Ensure the replacement has at least the same named sections so skills that reference
specific sections still work.
