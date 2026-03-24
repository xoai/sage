# PRD Methodology

## Purpose

Provides the structured methodology for writing a Product Requirements Document
(PRD) that is grounded in customer jobs and outcomes, not feature wish lists.
Read this before writing any PRD. It covers the anatomy of a good PRD, how it
connects to JTBD analysis, and what distinguishes expert-quality requirements
from generic ones.

## What a PRD Is

A PRD defines WHAT to build and WHY, without specifying HOW to build it. It is
a bridge between discovery (understanding the problem) and delivery (building
the solution). The PRD answers:

1. **What problem are we solving?** — Grounded in the JTBD analysis, not
   stakeholder opinions
2. **For whom?** — The specific job performer and segment
3. **What does success look like?** — Measurable outcomes tied to desired
   outcome statements from JTBD
4. **What is in scope and out of scope?** — Explicit boundaries
5. **What are the requirements?** — Structured, prioritized, testable

A PRD is NOT:
- A feature spec (that's the engineer's job — the PRD defines the problem)
- A project plan (no timelines, no resource allocation)
- A design document (no wireframes, no interaction details)
- A business case (no financial projections, no market sizing)

## When to Write a PRD

Write a PRD when:
- A JTBD analysis has identified high-opportunity outcomes (score ≥12)
- The team needs to align on scope before engineering or design begins
- Multiple solutions are possible and the team needs criteria to choose
- The initiative is complex enough that "just build it" would lead to rework

Skip the PRD when:
- The change is a bug fix or minor UI adjustment
- The team has strong shared context and the scope is obvious
- You're in early discovery and the problem isn't validated yet

## Connection to JTBD

The PRD inherits from the JTBD analysis:

| JTBD Output | PRD Input |
|---|---|
| Job performer | Target user segment |
| Main job statement | Problem statement framing |
| Desired outcome statements (high-opportunity) | Requirements source |
| Pains (specific) | Problem evidence |
| Job process map stages | User journey context |
| Emotional/social jobs | Experience requirements |
| Validation status | Confidence level for the PRD |

**Critical principle:** Every requirement in the PRD must trace back to a
desired outcome or pain from the JTBD analysis. If a requirement doesn't
connect to a customer need, it doesn't belong in the PRD. This is the single
most important quality criterion.

## Anatomy of a PRD

### 1. Problem Statement

Two paragraphs maximum. Describes:
- Who is experiencing the problem (job performer)
- What they're trying to accomplish (main job)
- Why current solutions fail (top pains)
- What the opportunity is (highest-scoring desired outcomes)

Source: directly from the JTBD analysis. Don't rewrite — reference.

### 2. Goals and Success Metrics

- **Primary goal:** One sentence. What this initiative achieves for the user.
- **Success metrics:** 2-4 measurable outcomes. Each maps to a desired outcome
  statement from JTBD. Include baseline, target, and measurement method.
- **Non-goals:** Explicitly state what this PRD does NOT try to achieve.
  This is as important as goals — it prevents scope creep.

### 3. User Segments and Context

Brief summary of who this is for, with circumstances that trigger the job.
If the JTBD analysis identified multiple segments, specify which this PRD
targets and why.

### 4. Requirements

Organized by priority tier (MoSCoW: Must/Should/Could/Won't). Each
requirement follows the job story format (see `requirements-writing.md`).

Group requirements by job process stage when possible — this creates a
natural narrative flow that mirrors the user's experience.

### 5. Constraints and Dependencies

- Technical constraints (platform limitations, data availability, APIs)
- Business constraints (regulatory, timeline, resource)
- Dependencies on other teams or initiatives
- Assumptions that, if wrong, invalidate the requirements

### 6. Open Questions

Unresolved decisions that need input before or during implementation.
Each question has an owner and a target date for resolution. A PRD with
no open questions is suspicious — it means the author hasn't thought hard
enough about uncertainty.

### 7. Out of Scope

Explicit list of what is NOT included in this initiative. Each out-of-scope
item should briefly explain why it's excluded (deferred to later, different
team, not validated yet, etc.).

## PRD Sizing

PRDs come in different sizes depending on the initiative:

**Light PRD (1-2 pages):** For well-understood problems with clear scope.
Covers problem statement, 3-5 requirements, success metrics, and out of scope.
Appropriate for BUILD mode features.

**Full PRD (3-6 pages):** For complex initiatives with multiple requirements,
cross-team dependencies, and uncertain scope boundaries. Includes all sections.
Appropriate for ARCHITECT mode initiatives.

**Epic PRD (7+ pages):** Usually a sign that the initiative should be split
into multiple PRDs. If you need 7+ pages, you're likely mixing multiple
problems or multiple user segments. Split first, then write focused PRDs.

## The Problem-Solution Gap

The most important skill in PRD writing is maintaining separation between
problem space and solution space:

**Problem space (belongs in PRD):**
- "Users need to know if their spending in a specific category has exceeded
  their personal threshold"

**Solution space (does NOT belong in PRD):**
- "Show a red warning banner when spending exceeds 80% of the monthly average"

The PRD defines the requirement ("know if spending exceeded threshold").
The design team determines the solution (banner, notification, color change).
The engineering team determines the implementation (real-time calculation,
batch job, ML model).

When PRDs include solutions, they:
- Constrain the team to one approach before exploring alternatives
- Create arguments about implementation details instead of problem clarity
- Become outdated faster (solutions change; problems don't)

Exception: If a specific solution IS the requirement (e.g., "support Apple
Pay" due to a partnership agreement), state it clearly as a constraint,
not a requirement.

## LLM Failure Modes

### 1. Feature List Masquerading as Requirements

**What happens:** The LLM produces a bullet list of features ("Add
notification system, Create dashboard, Build categorization engine") instead
of problem-grounded requirements.

**Root cause:** LLMs default to generating solutions when asked for
"requirements." Without JTBD grounding, there's no problem to anchor the
requirements to.

**Fix:** Every requirement must start with "When [situation], [performer]
wants to [desired outcome], so that [expected benefit]." If it can't be
written in this format, it's a solution, not a requirement.

### 2. Missing Prioritization

**What happens:** All requirements are listed as equally important, or the
LLM uses vague language like "nice to have" without structured prioritization.

**Root cause:** LLMs avoid making hard choices. Everything seems important
when there's no framework for deciding.

**Fix:** Use MoSCoW with strict limits: Must-haves ≤40% of requirements.
The opportunity score from JTBD provides the ranking signal — highest
opportunity outcomes become Must-haves.

### 3. Untestable Acceptance Criteria

**What happens:** Criteria like "the system should be fast" or "the
experience should be intuitive" that can't be verified.

**Root cause:** LLMs generate qualitative descriptions instead of
quantitative thresholds.

**Fix:** Every acceptance criterion must have a measurable condition.
"The insight loads within 2 seconds" is testable. "The insight is helpful"
is not.

### 4. Scope Creep Through Generality

**What happens:** Requirements are written so broadly that they encompass
far more work than intended. "Users should be able to manage all their
expenses" could mean anything from a simple summary to a full accounting
system.

**Root cause:** LLMs default to comprehensive descriptions. Without
explicit boundaries, they over-scope.

**Fix:** The "Out of Scope" section is mandatory and must be specific.
For every requirement, ask: "What is this requirement NOT asking for?"

### 5. No Connection to Evidence

**What happens:** The PRD makes confident assertions about user needs
without citing the source — interview quotes, survey data, analytics,
or JTBD analysis.

**Root cause:** LLMs are confident by default. They don't distinguish
between validated knowledge and hypothesis.

**Fix:** Every claim in the Problem Statement and Goals sections must
cite its source. "Users need X (JTBD analysis, outcome #3, score: 15)"
or "33% of non-users cite 'no need' as the reason (Exhibit 5, survey
n=398)." If there's no source, label it as an assumption.
