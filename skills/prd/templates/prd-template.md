# PRD: [Initiative Name]

**Status:** [Draft | Review | Approved]
**Author:** [Name]
**Date:** [Date]
**JTBD Source:** [Link or reference to the JTBD analysis this PRD is grounded in]
**Confidence:** [Validated | Hypothesized — needs validation]

---

## 1. Problem Statement

<!-- Write for a human reader who has 2 minutes. A stakeholder, a new team
member, or a designer should be able to read this section and understand
WHY this initiative exists. Lead with the user, not the system. -->

[Two paragraphs maximum. Who is experiencing the problem? What are they
trying to accomplish? Why do current solutions fail? What is the opportunity?

Cite sources: JTBD analysis outcomes, survey data, interview quotes,
analytics. Every claim needs a source.]

## 2. Goals and Success Metrics

**Primary goal:** [One sentence — what this initiative achieves for the user]

**Success metrics:**

| Metric | Baseline | Target | Measurement Method |
|--------|----------|--------|--------------------|
| [User outcome metric — tied to JTBD outcome] | [Current value] | [Target value] | [How to measure] |
| [System performance metric] | [Current value] | [Target value] | [How to measure] |
| [Business impact metric] | [Current value] | [Target value] | [How to measure] |

**Non-goals:**
- [What this initiative explicitly does NOT try to achieve]
- [Why — deferred, different team, not validated, etc.]

## 3. User Segments and Context

**Target segment:** [From JTBD — job performer definition]

**Triggering circumstances:**
- [When does the job arise? From JTBD job process map]

**Current solutions hired:**
- [What do they use today? From JTBD]

## 4. Requirements

<!-- Requirements are organized in two groups:
     - Job stories: user-facing needs, grounded in JTBD outcomes
     - Functional requirements: system-level constraints and capabilities
     Both are prioritized using MoSCoW. Job stories lead because the PRD
     exists to serve customer needs. -->

### Overview

| # | Summary | Source | Priority | Shippable Alone? |
|---|---------|--------|----------|:----------------:|
| R1 | [Brief description] | [JTBD outcome or pain] | Must | No — foundational |
| R2 | [Brief description] | [JTBD outcome or pain] | Must | Yes |
| R3 | [Brief description] | [JTBD outcome or pain] | Should | Yes |
| R4 | [Brief description] | [Pain or constraint] | Should | No — enhances R2 |
| FR1 | [System constraint] | [Technical/business need] | Must | N/A |
| FR2 | [System constraint] | [Technical/business need] | Should | N/A |

<!-- "Shippable Alone?" indicates whether this requirement delivers user
value independently. Requirements marked "Yes" map to natural milestones
in the implementation plan. Requirements marked "No" are foundational —
they enable other requirements but don't deliver visible value on their own.
Functional requirements are marked N/A — they constrain how the system
works, not what users experience. -->

### Must Have

#### R1: [Requirement title] (Must — Opp: [score])

**Job story:** When [situation from job process map], [performer] wants to
[desired outcome], so that [expected benefit from emotional/functional job].

**Why this priority:** [Why Must, not Should or Could. What evidence supports
this priority. What depends on this. Reference JTBD outcome by number.]

**Delivers value independently:** [Yes — describe what users can do / No —
foundational capability that enables R2, R3.]

**Acceptance scenarios:**
1. Given [initial state / precondition],
   when [user action or system event],
   then [expected outcome — measurable, observable].

2. Given [different state — edge case or boundary],
   when [action],
   then [expected outcome].

3. Given [negative case — what should NOT happen],
   when [action that might trigger wrong behavior],
   then [system correctly handles the case].

<!-- Mark any unresolved decisions INLINE:
   "the system computes a personal baseline using
   ⚠️ NEEDS CLARIFICATION (Q1): statistical method not decided —
   median, weighted average, or percentile?"
   This makes the ambiguity visible where it matters, not just in the
   Open Questions table at the end. -->

#### R2: [Requirement title] (Must — Opp: [score])

**Job story:** When [situation], [performer] wants to [outcome], so that
[benefit].

**Why this priority:** [Evidence and reasoning]

**Delivers value independently:** [Yes/No — explain]

**Acceptance scenarios:**
1. Given ..., when ..., then ...
2. Given ..., when ..., then ...

### Should Have

#### R3: [Requirement title] (Should — Opp: [score])

[Same structure as above: job story, why this priority, delivers value
independently, acceptance scenarios]

### Could Have

#### R4: [Requirement title] (Could — Opp: [score])

[Same structure]

### Won't Have (This Time)

- **[Feature/capability explicitly deferred]** — [Rationale: why excluded,
  when to revisit]

### Functional Requirements

<!-- System-level constraints that don't map to user experiences. These
describe what the system MUST do to support the job stories above.
Use when the constraint is technical, performance-related, or operational. -->

- **FR1:** [System capability or constraint, e.g., "System must compute
  baselines within the nightly processing window (< 4 hours)"]
  Priority: [Must/Should/Could]

- **FR2:** [System capability or constraint, e.g., "System must maintain
  ≥85% categorization accuracy across all transaction types"]
  Priority: [Must/Should/Could]
  ⚠️ NEEDS CLARIFICATION (Q[N]): [Inline marker if unresolved]

### Edge Cases

<!-- What happens at the boundaries? These are scenarios that don't fit
neatly into a single requirement but affect multiple requirements. -->

- What happens when [boundary condition, e.g., "user has transactions in
  50+ categories — do we compute baselines for all?"]?
- How does the system handle [error scenario, e.g., "categorization
  service is down during a transaction"]?

## 5. Constraints and Dependencies

**Technical constraints:**
- [Platform, data, API limitations]

**Business constraints:**
- [Regulatory, timeline, resource constraints]

**Dependencies:**
- [Other teams, initiatives, or systems]

**Assumptions (if wrong, the PRD needs revision):**
- [Assumption 1] — if wrong: [consequence]
- [Assumption 2] — if wrong: [consequence]

## 6. Open Questions

<!-- Every ⚠️ NEEDS CLARIFICATION marker in the requirements above should
have a corresponding row here with an owner and deadline. -->

| # | Question | Where It Appears | Owner | Target Date |
|---|----------|-----------------|-------|-------------|
| Q1 | [Unresolved decision] | R1 acceptance scenario 1 | [Who decides] | [When] |
| Q2 | [Unresolved decision] | FR2 | [Who decides] | [When] |

## 7. Out of Scope

- **[Specific capability not included]** — [Why excluded, when to revisit]
- **[Specific capability not included]** — [Why excluded]

---

## Appendix: JTBD Summary

<!-- This section gives any reader — PM, developer, designer, stakeholder —
the customer context without requiring them to read the full JTBD analysis.
Write it for a human who will never open the JTBD file. -->

**Job performer:** [Who — segment definition from JTBD]

**Main job:** [The main functional job statement]

**Top desired outcomes this PRD addresses:**

| # | Desired Outcome | Opp Score | PRD Requirement |
|---|----------------|:---------:|-----------------|
| [JTBD #] | [Outcome statement] | [Score] | R1, R2 |
| [JTBD #] | [Outcome statement] | [Score] | R3 |

**Key insight:** [One sentence — the most important thing the JTBD revealed
that shaped this PRD's approach]

## Handoff to Engineering

<!-- This section tells the engineering team how to use this PRD. -->

This PRD is ready for technical specification. To proceed:

1. Sage's specify skill will detect this PRD and use it as input
   (skipping elicitation — requirements are already defined)
2. Resolve the Open Questions (§6) as engineering decisions
3. Produce a technical spec addressing requirements R1-R[N] and FR1-FR[N]
4. Each acceptance scenario becomes a test case in the implementation plan
5. Requirements marked "Delivers value independently: Yes" map to
   natural milestones in the plan
