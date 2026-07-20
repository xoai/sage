---
name: adr-standard
type: architecture
variant: adr
version: "1.0.0"
description: Architectural Decision Record. Documents a significant technical decision with context, options, and consequences.
mode: architect
sections: [context, options, decision, consequences]
---

# decision record-{NNN}: {decision_title}

**Date:** {date}
**Status:** Proposed | Accepted | Deprecated | Superseded by decision record-{NNN}

[SECTION: context]
## Context

{why_this_decision_is_needed}
{what_forces_are_at_play}
{what_constraints_exist_from_constitution}
[/SECTION]

[SECTION: options]
## Options Considered

<!-- GUIDANCE: Minimum 2 options. For each: what it is, pros, cons.
Be honest about trade-offs — an option with no cons wasn't evaluated fairly. -->

### Option A: {name}
{description}
- **Pros:** {advantages}
- **Cons:** {disadvantages}

### Option B: {name}
{description}
- **Pros:** {advantages}
- **Cons:** {disadvantages}

{?additional_options}
[/SECTION]

[SECTION: decision]
## Decision

We will use **Option {X}** because {primary_rationale}.

{additional_reasoning}
[/SECTION]

[SECTION: consequences]
## Consequences

**Positive:**
{benefits_of_this_decision}

**Negative:**
{trade_offs_accepted}

**Follow-up actions:**
{tasks_that_result_from_this_decision}
[/SECTION]
