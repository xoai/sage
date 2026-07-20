---
name: spec-full
type: spec
variant: full
version: "1.0.0"
description: Comprehensive PRD for ARCHITECT mode. Full requirements with personas, metrics, and risks.
mode: architect
sections: [problem, personas, stories, requirements, non-functional, boundaries, metrics, risks]
---

# {product_or_feature_name}

**Version:** {version}
**Author:** {human_name_or_team}
**Date:** {date}
**Status:** Draft | Approved
**Deliverable:** code | document | mixed

<!-- GUIDANCE: Set deliverable type based on what this spec produces.
  code = source code (components, APIs, scripts) → plan uses TDD + code gates
  document = written artifacts (PRD, analysis, strategy) → plan uses draft + checklist
  mixed = some tasks produce code, some produce documents → plan marks each task
-->

[SECTION: problem]
## Problem Statement

**What problem exists?**
{problem_description}

**Who has this problem?**
{affected_users_or_stakeholders}

**How painful is it?**
{impact_and_urgency}

**What happens if we don't solve it?**
{cost_of_inaction}
[/SECTION]

[SECTION: personas]
## User Personas

<!-- GUIDANCE: "Users" is not a persona. Each persona is a distinct type of
person with different goals, constraints, and pain points. 2-4 personas
is typical. More than 5 usually means the scope is too broad. -->

### Persona: {persona_name}
- **Role:** {who_they_are}
- **Goal:** {what_they_want_to_achieve}
- **Pain points:** {what_frustrates_them_today}
- **Constraints:** {limitations_they_operate_under}

{repeat_for_each_persona}
[/SECTION]

[SECTION: stories]
## User Stories

<!-- GUIDANCE: Format: "As [persona], I want to [action] so that [outcome]."
Each story should be independently deliverable and testable. Group by persona. -->

### {persona_name} Stories

- US-{NNN}: As {persona}, I want to {action} so that {outcome}.
- US-{NNN}: As {persona}, I want to {action} so that {outcome}.

{repeat_for_each_persona}
[/SECTION]

[SECTION: requirements]
## Functional Requirements

<!-- GUIDANCE: Each requirement gets a unique ID (FR-NNN) for traceability.
Requirements must be specific and testable. "The system should be user-friendly"
is NOT a requirement. "The login form displays validation errors inline within
200ms of field blur" IS a requirement. -->

- FR-{NNN}: {specific_testable_requirement}
- FR-{NNN}: {specific_testable_requirement}

{requirements_list}
[/SECTION]

[SECTION: non-functional]
## Non-Functional Requirements

<!-- GUIDANCE: Pull from the constitution first — many NFRs are already
defined there. Only add project-specific NFRs here. Include measurable
targets wherever possible. -->

### Performance
- NFR-{NNN}: {performance_requirement_with_target}

### Security
- NFR-{NNN}: {security_requirement}

### Scalability
- NFR-{NNN}: {scalability_requirement_with_target}

### Accessibility
- NFR-{NNN}: {accessibility_requirement}

{?additional_nfr_categories}
[/SECTION]

[SECTION: boundaries]
## Boundaries

**In scope:**
{in_scope_list}

**Out of scope:**
<!-- GUIDANCE: Being explicit about what you WON'T build is as important as
defining what you will. This prevents scope creep during implementation. -->
{out_of_scope_list}
[/SECTION]

[SECTION: metrics]
## Success Metrics

<!-- GUIDANCE: How will we know this worked? Quantitative where possible.
"Users like it" is not a metric. "DAU increases 20% within 30 days" is. -->

{success_metrics_list}
[/SECTION]

[SECTION: risks]
## Risks and Assumptions

<!-- GUIDANCE: What could go wrong? What are we assuming to be true?
For each risk: probability, impact, and mitigation. -->

### Risks
- {risk}: Probability {H/M/L}, Impact {H/M/L}. Mitigation: {mitigation}.

### Assumptions
- {assumption_that_if_wrong_changes_the_plan}

{risks_and_assumptions}
[/SECTION]
