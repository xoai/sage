---
name: prd
description: >
  Produces a Product Requirements Document (PRD) grounded in JTBD outcomes.
  Takes a JTBD analysis as input and transforms high-opportunity outcomes into
  structured, prioritized, testable requirements. Use when the user mentions
  PRD, product requirements, product spec, requirements document, or asks
  what to build based on a JTBD analysis. Also triggers when the user wants
  to define scope for an initiative, align a team on what to build, or
  translate customer needs into product requirements. Do NOT use for technical
  design documents, project plans, or feature specs that prescribe solutions.
version: "1.1.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [product-management, prd, requirements, specification, scope]
inputs: [jtbd-analysis]
outputs: [prd]
requires: [jtbd]
-->

# Product Requirements Document

Produce a brief that is grounded in JTBD outcomes, not feature wish lists.
Every requirement traces back to a customer need. The output is a document
deliverable — not code.

**Deliverable type:** document

## Mode Behaviors

**FIX (update):** Update specific parts of an existing PRD — revise
requirements after new research, update acceptance criteria after design
review, add/remove scope items after stakeholder feedback. Don't rewrite
the whole document. Locate the section, make the change, update the
traceability table if affected. Minutes.

**BUILD (light):** Light PRD (1-2 pages). Problem statement, 3-5
requirements in job story format with acceptance criteria, success metrics,
and out-of-scope list. Skip detailed constraints, open questions, and the
appendix. Sufficient for well-scoped features where the team has strong
shared context. 15 minutes.

**ARCHITECT (full):** Full PRD (3-6 pages). All seven sections: problem
statement with evidence, goals and success metrics with baselines and
targets, segments and context, requirements with traceability table and
MoSCoW tiers, constraints and dependencies, open questions with owners,
out-of-scope with rationale. 30-45 minutes.

## When to Use

- A JTBD analysis exists with identified high-opportunity outcomes (score ≥12)
- The team needs to align on scope before engineering or design begins
- The user asks to define what to build based on JTBD findings
- The user wants to translate customer needs into actionable requirements
- Multiple solutions exist and the team needs criteria for choosing

## Prerequisites

This skill requires a JTBD analysis as input. If no JTBD analysis exists:
1. Check if a JTBD analysis file exists (`.sage/docs/jtbd-analysis.md`)
2. If not, recommend running the `jtbd` skill first
3. If the user insists on proceeding without JTBD, produce a brief but label
   every requirement as "ungrounded — no JTBD source" and flag this in the
   deliverable header

## Process

### Step 0: Locate JTBD Input

Find the JTBD analysis that this PRD will be grounded in. Confirm with the
user:
- Which JTBD outcomes to focus on (usually the top 2-3 by opportunity score)
- Which user segment to target (if the JTBD identified multiple)
- What scope level is appropriate (light PRD for BUILD, full PRD for ARCHITECT)

If the user provides all of this upfront, proceed. If not, ask in ONE message.

### Step 1: Frame the Problem

**Read first:** `references/prd-methodology.md` (Problem Statement section)

Write the problem statement using ONLY information from the JTBD analysis:
- Job performer → who is affected
- Main job statement → what they're trying to accomplish
- Top pains (with evidence) → why current solutions fail
- Highest-opportunity outcomes → what the opportunity is

Every claim must cite its source (JTBD outcome #, survey data, interview
quote). If the JTBD analysis is labeled "hypothesized," carry that label
forward.

### Step 2: Define Goals and Success Metrics

**Read first:** `references/prd-methodology.md` (Goals and Success Metrics)

Derive the primary goal from the main job statement. Derive success metrics
from the desired outcome statements:

- Each high-opportunity outcome (≥12) becomes a candidate success metric
- Translate the outcome's "direction + measure" into a measurable metric
- Establish baseline (from JTBD data or current analytics) and target
- Specify measurement method

Write non-goals explicitly. Ask: "What might someone expect this initiative
to do that it will NOT do?" Non-goals prevent scope creep.

### Step 3: Write Requirements

**Read first:** `references/requirements-writing.md` (all sections)

Requirements are written for TWO audiences: humans (PMs, designers,
stakeholders who read the brief to understand what we're building and why)
and agents (AI or developers who translate requirements into implementation).
Write for the human reader first — clear language, customer perspective,
evident reasoning. The structure also serves agents — Given/When/Then
scenarios translate directly into tests.

#### Job Stories (User-Facing Requirements)

For each high-opportunity desired outcome from the JTBD analysis, write a
requirement with these parts:

1. **Job story:** Convert the JTBD outcome into a job story:
   "When [situation from job map], [performer] wants to [outcome], so that
   [benefit from emotional/functional job]." The job story leads because
   the requirement exists to serve a customer need.

2. **Why this priority:** Justify the MoSCoW priority with evidence — the
   opportunity score, what depends on this requirement, and why this tier.
   Assign priority using:
   - Opportunity score ≥15 → Must have (unless constrained)
   - Opportunity score 12-14 → Should have
   - Opportunity score 10-11 → Could have
   - Below 10 → Won't have (this time)

3. **Delivers value independently:** State whether this requirement
   provides user value on its own (can be shipped and demoed independently)
   or is foundational (enables other requirements but isn't user-visible
   alone). This maps directly to milestones in the implementation plan —
   requirements that deliver value independently are natural ship points.

4. **Acceptance scenarios:** Write testable Given/When/Then scenarios.
   Include at least one boundary or negative case per requirement (what
   happens when conditions aren't met). Each scenario should be specific
   enough that a developer can turn it directly into a test.

5. **Inline clarification markers:** When a requirement contains an
   unresolved decision, mark it INLINE with ⚠️ NEEDS CLARIFICATION (Q[N])
   right where the ambiguity lives. Don't leave ambiguity discoverable
   only in the Open Questions table — make it visible where it matters.

#### Functional Requirements (System-Level Constraints)

Some requirements are system-level: performance thresholds, accuracy
targets, processing windows, data retention rules. These don't fit
naturally into job story format because they describe system behavior,
not user experiences.

Write these separately as "System must [capability] when [condition]"
statements. Include priority and inline clarification markers where
needed. These complement job stories — job stories define what users
experience, functional requirements constrain how the system delivers it.

#### Edge Cases

After writing individual requirements, identify cross-cutting boundary
conditions that affect multiple requirements. "What happens when..." and
"How does the system handle..." questions that don't fit neatly into a
single requirement's acceptance scenarios.

#### Requirements Overview Table

Build the overview table linking each requirement to its JTBD source,
priority, and whether it delivers value independently. This is the
quick-scan summary for stakeholders who don't read every requirement.

Enforce the limit: Must-haves ≤40% of total requirements (job stories +
functional requirements combined).

### Step 4: Define Boundaries

Identify constraints and dependencies:
- What technical limitations affect these requirements?
- What business constraints exist (timeline, resources, regulatory)?
- What depends on other teams or initiatives?
- What assumptions, if wrong, invalidate the requirements? For each
  assumption, state the consequence: "If wrong: [what changes]"

Write the "Out of Scope" section explicitly. For each major capability NOT
included, explain why and when to revisit.

Identify open questions — unresolved decisions that need answers before or
during implementation. Each question needs an owner, a deadline, AND a
"Where it appears" column pointing to the inline ⚠️ marker in the
requirement that contains the ambiguity.

### Step 5: Quality Check

**Read first:** `references/requirements-writing.md` (Quality Checklist)

Before presenting the brief, validate:

- [ ] Every requirement traces to a JTBD outcome or documented pain
- [ ] Every requirement leads with a job story (customer perspective, not system perspective)
- [ ] Every requirement has a "Why this priority" justification with evidence
- [ ] Every requirement states whether it delivers value independently
- [ ] No requirement specifies a solution (only the problem/need)
- [ ] Must-haves ≤40% of total requirements (job stories + FRs combined)
- [ ] Every requirement has acceptance scenarios in Given/When/Then format
- [ ] Every requirement has at least one negative/boundary scenario
- [ ] Unresolved decisions are marked INLINE (⚠️ NEEDS CLARIFICATION) AND in the Open Questions table
- [ ] System-level constraints are captured as functional requirements, not forced into job stories
- [ ] Problem statement cites evidence (not assertions)
- [ ] Non-goals and out-of-scope are explicit
- [ ] Open questions have owners, deadlines, and "Where it appears" references
- [ ] JTBD validation status carried forward (validated vs hypothesized)
- [ ] A human reader with no context can understand the brief by reading sections 1-3

If issues are found, fix before presenting.

## Output

Save to `.sage/work/<YYYYMMDD>-<slug>/brief.md` using the template from
`templates/prd-template.md`.

Append to `.sage/decisions.md` recording the brief
scope (which opportunity, how many requirements per priority tier),
key decisions, and open questions. Update the "Current Artifacts" section
to list the new file as Active.

Present to user: "Here's the brief grounded in the JTBD analysis. The
[N] Must-have requirements target the top unmet needs: [X, Y, Z]. There
are [M] open questions that need resolution before implementation. Want
to refine any section?"

## Rules

**MUST:**
- MUST read `references/prd-methodology.md` before writing any PRD
- MUST have a JTBD analysis as input — requirements without job-grounding
  produce feature lists, not product requirements
- MUST trace every requirement back to a JTBD outcome or documented pain —
  ungrounded requirements are the primary failure mode
- MUST write acceptance criteria that are measurable — "the insight is
  helpful" is not a criterion; "≥60% of test users rate the insight as
  relevant" is
- MUST enforce MoSCoW limits — Must-haves ≤40% of requirements
- MUST include non-goals and out-of-scope sections — these are as important
  as the requirements themselves
- MUST carry forward the JTBD validation status — a brief based on hypothesized
  JTBD is itself hypothesized

**SHOULD:**
- SHOULD group requirements by job process stage for natural narrative flow
- SHOULD include at least one negative/boundary acceptance criterion per
  requirement (what happens when conditions aren't met)
- SHOULD write "Won't have" items to acknowledge deferred requests
- SHOULD identify open questions with owners and deadlines

**MAY:**
- MAY produce a light PRD (1-2 pages) in BUILD mode when scope is clear
- MAY include an appendix with the JTBD summary for readers who haven't
  seen the full analysis
- MAY reference specific data from the JTBD analysis (opportunity scores,
  survey percentages, interview quotes) as evidence

## Failure Modes

- **No JTBD input available:** Don't produce an ungrounded PRD. Recommend
  running the `jtbd` skill first. If the user insists, proceed but label
  every requirement as "ungrounded" and flag this prominently.

- **JTBD analysis has no high-opportunity outcomes:** The JTBD either
  didn't find significant unmet needs (rare) or didn't apply opportunity
  scoring. Ask the user to apply scoring to the outcomes before proceeding.

- **Requirements drift into solution space:** The most common failure mode
  during writing. Check: does the requirement mention any specific UI
  element, technology, or implementation approach? If yes, rewrite as the
  underlying need. "Show a red banner" → "Communicate that spending
  exceeds threshold."

- **Everything is a Must-have:** Push back. "If everything is a Must,
  nothing is. Which 2-3 outcomes would make this initiative fail if
  unaddressed?" Those are the Musts. Everything else is Should or Could.

- **Stakeholder adds requirements without JTBD backing:** Ask: "Which
  customer need does this address?" If they can point to a pain or outcome,
  add it with the trace. If they can't, add it to the open questions or
  out-of-scope with a note: "Needs customer validation before inclusion."

## Quality Criteria

**Communication style:** Product language. Emphasize user impact,
business value, and measurable outcomes. Requirements should be
understandable by non-technical stakeholders.

Good PRD output:
- Every requirement traces back to a JTBD outcome or validated insight
- Requirements are solution-free — describe the need, not the implementation
- MoSCoW prioritization is honest — not everything is Must-have
- Acceptance criteria are testable — you can verify pass/fail
- Edge cases and error states are addressed, not just happy paths
- Ungrounded requirements (no research backing) are flagged explicitly
- The document is complete enough that an engineer can estimate scope

## Self-Review

Before presenting your output, check each quality criterion above.
For each, confirm it's met or note what's missing. Present your
findings AND your self-assessment:

"Self-review: [X/Y criteria met]. [Note any gaps and why they exist.]"
