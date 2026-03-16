---
name: spec-minimal
type: spec
variant: minimal
version: "1.0.0"
description: Lightweight specification for BUILD mode. Three sections from guided elicitation.
mode: build
sections: [intent, boundaries, acceptance-criteria, affected-areas]
---

# {feature_name}

**Deliverable:** code | document | mixed

[SECTION: intent]
## Intent

{what_and_why}

**Actor:** {who_uses_this}
**Trigger:** {when_they_use_it}
**Outcome:** {what_value_it_delivers}
[/SECTION]

[SECTION: boundaries]
## Boundaries

**This feature WILL:**
{will_do_list}

**This feature WILL NOT:**
{will_not_do_list}

**Constraints:**
{non_functional_requirements}
[/SECTION]

[SECTION: acceptance-criteria]
## Acceptance Criteria

<!-- GUIDANCE: Every criterion must be testable. "Works well" is NOT testable.
"Returns 200 OK with user.id in JSON body" IS testable. If you can't write
a test for it, it's not a criterion — it's a wish. -->

{acceptance_criteria_numbered_list}
[/SECTION]

[SECTION: affected-areas]
## Affected Areas

<!-- GUIDANCE: Populated from codebase-scan. Lists files, modules, and
dependencies that this feature touches. -->

{affected_files_and_modules}
[/SECTION]
