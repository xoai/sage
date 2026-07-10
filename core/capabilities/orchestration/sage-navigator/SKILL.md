---
name: sage-navigator
description: >
  Offers validated Sage workflow choices when the user explicitly invokes
  /sage, accepts routing advice, asks what to do next, or resumes an active run.
  It never auto-starts a workflow from task keywords.
version: "2.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: explicit-or-active
tags: [orchestration, navigation, routing, composition]
inputs: [run-state, route-catalog, composition-catalog, user-intent]
outputs: [workflow-options, composition-choice, state-update]
composition:
  contract: composition/v1
  id: sage-navigator
  atomic: false
  provides:
    - capability: workflow.navigate
      role: owner
      combine: exclusive
-->

# Sage Navigator

Sage Navigator is optional guidance, not an always-on gatekeeper. Use it when
the user explicitly invokes `/sage`, accepts a validated advisory route, asks
for process guidance, or has an active Sage run to resume.

## Authority

1. Explicit installed slash commands are authoritative.
2. Persisted active-run state continues the current workflow.
3. Runtime advisory context may suggest a route; the user may accept, combine,
   or ignore it.
4. Plain prose never starts, switches, cancels, or strictly gates a workflow.

Do not classify by keyword. Do not invent a route or agent profile that is not
present in the compiled catalogs.

## Process

### 1. Orient

- Read the active run and matching `.sage/work/` state when one exists.
- Use bounded recall already supplied by the configured recall owner. Do not
  query a second memory backend "just in case."
- If no run is active, do not create state until the user selects an installed
  route.

### 2. Inspect validated choices

Read the compiled route catalog. Offer only installed workflow targets. If the
user requested a specific slash command, proceed directly. If the user asked
for guidance, present a small set of semantically relevant choices and explain
the tradeoff; do not pretend a suggestion is binding.

### 3. Resolve composition

For the selected workflow, use the compiled composition plan:

- one owner per required capability;
- only selected compatible augmenters, validators, and observers;
- user/project policy overrides workflow defaults;
- multiple unresolved exclusive owners require a user choice;
- a named external method or domain skill may combine when its declared role is
  compatible.

Compatibility is eligibility, not activation. Never load every installed skill.

### 4. Select execution topology

Use direct work by default. Select synchronous delegation or durable Kanban only
from an exact supported flag or explicit confirmation. Delegation is bounded
fan-out; Kanban is a durable task graph with orchestrator and worker roles.

### 5. Continue or hand off

Record explicit workflow transitions and composition choices. During an active
run, suppress inferred rerouting until the user switches or cancels. At a
terminal, verify evidence, run the learning/reflection lifecycle, and leave a
durable handoff when the workflow declares one.

## Output

At a genuine choice point, show the installed options, selected capability
owners, and any explicitly selected helpers. Otherwise proceed without adding a
Sage menu or approval gate to ordinary conversation.

## Failure Modes

- **Keyword auto-routing:** treat as non-authoritative and use validated advice.
- **Missing catalog target:** fail open and recommend regenerating Sage surfaces.
- **Ambiguous owner:** ask the user; never select silently.
- **Backend unavailable:** omit recall context and continue.
- **Active run plus new prose:** keep the active run until explicit switch/cancel.
