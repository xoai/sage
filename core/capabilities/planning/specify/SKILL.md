---
name: specify
description: >
  Structures elicitation output into a formal specification defining WHAT to
  build and WHY. Use after quick-elicit or deep-elicit completes, or when the
  user provides requirements and says "write a spec", "define requirements",
  "create a PRD", or "specify this feature".
version: "1.0.0"
modes: [build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [specification, requirements, planning, prd]
inputs: [codebase-context]
outputs: [spec]
-->

# Specify

Define WHAT to build and WHY — without deciding HOW (technology choices).

**Core Principle:** Specifications are the source of truth. Code serves the spec,
not the other way around. A clear spec prevents more bugs than any testing framework.
The same spec can produce multiple implementations on different branches.

## Deliverable Type

Every spec declares what it produces. Infer this from context:

```markdown
Deliverable: code | document | mixed
```

**Code:** The output is source code — components, APIs, scripts, configs. This is
the default. The plan will use TDD, implementation, commits, and full quality gates.

**Document:** The output is a written artifact — a PRD, competitive analysis,
strategy doc, content brief, report. The plan will use drafting, review against
criteria, and checklist verification. No TDD, no code gates.

**Mixed:** Some tasks produce code, some produce documents. A site audit produces
a findings document; the fixes produce code. The plan marks each task with its
type and applies the appropriate workflow per task.

How to infer: if the user says "write", "draft", "analyze", "research", "audit",
"create a document/report/brief/PRD" → likely document. If they say "build",
"implement", "add", "fix", "create a feature/page/component" → likely code. If
they say "audit and fix", "research then implement" → likely mixed. When unclear, ask.

## When to Use

At the start of BUILD or ARCHITECT workflows, after codebase-scan and elicitation.
The elicitation output (from quick-elicit or deep-elicit) becomes the raw input
for a structured spec.

## Step 0: Check for Existing PRD

Before running elicitation, check if a PRD already exists for this initiative:

- Look in `.sage/work/<YYYYMMDD>-<slug>/brief.md`
- Look in `.sage/docs/` for briefs that cover this work

**If a PRD exists → PRD-to-Spec path (skip elicitation):**

The PRD already defines WHAT to build and WHY. The specify skill's job becomes:
translate the PRD into a technical spec that defines HOW.

1. **Load the PRD.** Read the requirements (job stories R1-RN), functional
   requirements (FR1-FRN), acceptance scenarios, constraints, and dependencies.

2. **Resolve open questions.** The PRD's ⚠️ NEEDS CLARIFICATION markers
   (Q1-QN) are engineering decisions that must be resolved before implementation.
   For each open question:
   - Analyze the options (the PRD usually describes the alternatives)
   - Consider the constraints section and the codebase context
   - Make the decision and record it as a decision record in `.sage/docs/`
   - Update the spec with the resolved decision

3. **Design the technical architecture.** For each PRD requirement, determine:
   - What components, services, or modules implement it
   - What data model supports it
   - What APIs connect the components
   - Build a component map: R1 → [components], R2 → [components], etc.

4. **Map "Delivers value independently" to milestones.** Requirements marked
   "Yes" in the PRD's "Shippable Alone?" column become natural milestone
   boundaries. Requirements marked "No" (foundational) come first. The spec
   should note the milestone structure for the plan skill to consume.

5. **Write the spec** using the standard template but with:
   - PRD reference in the header (link to the PRD file)
   - Architecture decisions section with decision records resolving open questions
   - Component map linking each PRD requirement to technical components
   - Milestone structure derived from the PRD's "Shippable Alone?" flags
   - Acceptance scenarios from the PRD carried forward as test specifications

6. **Show to human for approval.** "Here's the technical spec based on the
   PRD. I've resolved the open questions as follows: [summary]. The component
   map traces every requirement to its implementation. Ready to plan?"

**If no PRD exists → standard elicitation path (current behavior):**

Proceed with BUILD or ARCHITECT mode elicitation as described below.

## Process by Mode

### BUILD Mode: Lightweight Spec

Input: Quick-elicit output (intent + boundaries + acceptance criteria)

1. Structure the elicitation output into the minimal spec template:
   - **Intent:** What and why (from Round 1)
   - **Deliverable:** code, document, or mixed (inferred from context)
   - **Boundaries:** What this does and does NOT do (from Round 2)
   - **Acceptance Criteria:** Testable success conditions (from Round 3)
   - **Affected Areas:** Files/modules identified by codebase-scan (for code),
     or output documents and their sections (for document)

2. Check against constitution — does any requirement conflict with project principles?
   If so, flag the conflict and ask the human to resolve.

3. Save to `.sage/work/<YYYYMMDD>-<slug>/spec.md`

4. Show to human for final approval: "Here's the spec. Ready to plan, or adjustments needed?"

### ARCHITECT Mode: Comprehensive PRD

Use the full spec template. Guide the human through:

1. **Problem Statement:** What problem exists? Who has it? How painful is it?
   Use Socratic questioning — ask WHY until you reach the real problem.

2. **User Personas:** Who are the distinct users? What are their goals, constraints,
   and pain points? Push for specificity — "users" is not a persona.

3. **User Stories:** For each persona, what stories describe their interactions?
   Format: "As [persona], I want to [action] so that [outcome]."

4. **Functional Requirements:** What must the system do? Be explicit and testable.
   Each requirement gets a unique ID for traceability.

5. **Non-Functional Requirements:** Performance, security, scalability, accessibility,
   compliance. Pull from the constitution — many of these are already defined there.

6. **Boundaries:** What is explicitly OUT of scope? What will NOT be built?
   This prevents scope creep during implementation.

7. **Success Metrics:** How will we know this worked? Quantitative where possible.

8. **Risks:** What could go wrong? What assumptions are we making?

Present each section for validation before proceeding to the next. The human
must approve each section — don't rush through to get to implementation.

Save to `.sage/work/<YYYYMMDD>-<slug>/spec.md` (or `.sage/specs/brief.md` for
project-level briefs).

## Rules

- NEVER include technology choices in the spec. "The system authenticates users"
  is a requirement. "Use JWT with RS256" is an implementation detail for the plan.
- NEVER write vague requirements. "The system should be fast" is not testable.
  "API response time < 200ms at p95" is testable.
- ALWAYS check the spec against the constitution before saving.
- ALWAYS get human approval before proceeding to planning.
- In ARCHITECT mode, ALWAYS present sections one at a time. Don't dump a 10-page
  document and ask "does this look right?" — nobody reads that.
- If the human says "just build it," respect that. Create a minimal spec from
  what they said and note that it was created with minimal elicitation. Proceed.

## Failure Modes

- **Requirements are contradictory:** Don't resolve them yourself. Present the
  contradiction clearly with both requirements side by side. Ask the human which takes priority.
- **Scope is too large for BUILD mode:** Recommend ARCHITECT mode. Don't try to
  squeeze enterprise complexity into a minimal spec.
- **Human can't articulate what they want:** That's normal. Use questions: "What
  does a user see first?" "What happens when they click X?" "What would make you
  say this is done?" Walk them through the user journey.
- **Existing spec from a previous session:** Load it, show what exists, ask what
  has changed. Don't re-elicit from scratch.
- **PRD has unresolvable open questions:** Some questions (like Q3 in the QLCT
  PRD: "what ratio triggers the insight?") need data analysis or user testing
  that can't happen during specification. Flag these as "deferred to
  implementation" with a sensible default and a plan to validate. Don't block
  the spec on questions that need production data.
- **PRD requirements conflict with technical reality:** The PRD was written in
  the problem space. If a requirement is technically infeasible (e.g., "compute
  baselines in real-time" when the data pipeline only runs nightly), this is an
  implementation-level change. Update the spec to reflect what's technically
  possible, note the deviation from the PRD, and inform the PM. If the change
  alters WHAT users experience (not just HOW), it's a domain-level change —
  flag to the PM before proceeding.
- **PRD is missing information the spec needs:** The PRD defines WHAT, not HOW.
  Some technical questions (data model, API design, component architecture) are
  legitimately absent from the PRD. These are decisions for the specify skill
  to make, not gaps in the PRD.
