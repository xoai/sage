# Requirements Writing

## Purpose

Precise rules for writing requirements that are grounded in customer jobs,
testable, and prioritized. Use as a reference during PRD authoring and as
a checklist during review.

## Requirement Formats

### Job Stories (Preferred)

Format: **When [situation], [performer] wants to [desired outcome], so that
[expected benefit].**

This is the recommended format because it directly connects to the JTBD
analysis — the situation comes from the job process map, the desired outcome
from the outcome statements, and the benefit from the emotional/functional
job.

Good:
- "When a user completes a payment at a merchant, they want to immediately
  see how this transaction relates to their monthly spending in that
  category, so that they can assess whether their spending is on track."
- "When a user opens the expense summary at month-end, they want to see
  which categories exceeded their typical spending level, so that they
  can decide where to adjust next month."

Bad:
- "As a user, I want to see a notification after payment" (no situation
  context, no outcome, no benefit — this is a feature request)
- "The system should display spending insights" (passive voice, no
  performer, untestable)

### User Stories (Acceptable)

Format: **As a [performer], I want to [action], so that [benefit].**

Acceptable when the JTBD context is well-understood and the story is
specific enough. Less preferred because it doesn't encode the triggering
situation, which makes prioritization harder.

Good:
- "As a Minimalist user, I want to know if my dining spending this month
  is higher than usual, so that I feel in control of my finances."

Bad:
- "As a user, I want to manage my expenses" (too broad, not testable,
  no specific outcome)

### Functional Requirements (For Technical Constraints)

Format: **The system shall [capability] when [condition].**

Use for non-negotiable technical requirements, performance thresholds,
or integration specifications. Not for user-facing features.

Good:
- "The system shall categorize a new transaction within 3 seconds of
  transaction completion."
- "The system shall maintain ≥85% categorization accuracy across all
  transaction types."

Bad:
- "The system shall be fast" (unmeasurable)
- "The system shall use AI for categorization" (specifies solution,
  not requirement)

## Connecting Requirements to JTBD

Every requirement must trace back to the JTBD analysis. The traceability
chain:

```
Desired Outcome Statement (from JTBD)
  → Requirement (in PRD — job story format)
    → Acceptance Scenarios (Given/When/Then — testable)
```

### The Requirement Format

Each requirement in the PRD follows a consistent structure that keeps the
customer perspective front and center:

```markdown
#### R1: [Title] (Priority — Opp: [score])

**Job story:** When [situation from job process map], [performer] wants
to [desired outcome], so that [benefit from emotional/functional job].

**Why this priority:** [Evidence-based justification. What JTBD outcome
drives this. What depends on this. Why this priority tier, not higher
or lower.]

**Independent test:** [How to verify this requirement on its own, without
other requirements being complete. Maps to implementation milestones.]

**Acceptance scenarios:**
1. Given [precondition], when [action], then [expected outcome].
2. Given [edge case], when [action], then [correct handling].
3. Given [negative case], when [action], then [appropriate response].
```

**Why this structure:**

The **job story** leads because the requirement exists to serve a customer
need, not a system capability. Anyone reading the PRD — PM, developer,
designer, stakeholder — thinks from the customer's perspective first.

**Why this priority** forces the writer to justify the priority with
evidence from the JTBD analysis, not with opinion or authority. A
requirement without justification is a requirement that might not
belong.

**Independent test** ensures the requirement can be verified on its own.
This directly maps to the milestone structure in implementation plans —
if a requirement can be independently tested, it can be independently
shipped.

**Acceptance scenarios** use Given/When/Then because each scenario is
a script that a developer, QA engineer, or AI agent can execute directly.
Every scenario should include at least one boundary or negative case
(what happens when conditions AREN'T met).

### Example Chain

Desired outcome: "Maximize the likelihood that a post-transaction insight
is personally relevant" (Opportunity score: 15)

→ Requirement:

#### R2: Threshold-based insight at post-transaction (Must — Opp: 15)

**Job story:** When a Minimalist user completes a payment and their spending
in that category is approaching or exceeding their personal baseline, they
want to see a contextual insight that relates this transaction to their
personal pattern, so that the insight is actionable rather than generic.

**Why this priority:** Tied for highest opportunity score (15). This is the
highest-leverage intervention point — the post-transaction moment is when
the user's attention is already on the app. Depends on R1 (personal
baseline computation). JTBD Outcome: "Maximize post-transaction insight
relevance."

**Delivers value independently:** No — foundational capability that enables
R2 (threshold insight) and R3 (baseline comparison). Can be verified by
checking that baselines exist in the data store, but users see no change
until R2 or R3 ships.

**Acceptance scenarios:**
1. Given a user with a personal baseline of 1.2M for Dining and current
   month spending of 1.0M (83%),
   when they complete a Dining transaction of 100K,
   then the transaction result shows an insight referencing their personal
   pattern (e.g., "91% of your typical monthly Dining").

2. Given a user with a personal baseline for Dining and current month
   spending at 30% of baseline,
   when they complete a Dining transaction,
   then no threshold insight is shown (spending is within normal range).

3. Given a user with no personal baseline for Transport (insufficient data),
   when they complete a Transport transaction,
   then the insight falls back to the current generic comparison format.

4. Given a user whose transaction was categorized with low confidence,
   when the transaction completes,
   then no threshold insight is shown for that transaction (avoid showing
   a personalized insight based on a potentially wrong category).

### Traceability Table

Include a traceability table in every PRD. The "Shippable Alone?" column
indicates whether the requirement delivers user value independently — this
maps directly to implementation milestones:

| # | Summary | JTBD Source | Opp | Priority | Shippable Alone? |
|---|---------|-------------|:---:|----------|:----------------:|
| R1 | Personal baseline computation | Outcome: "Determine threshold" | 15 | Must | No — foundational |
| R2 | Threshold insight at transaction | Outcome: "Insight relevance" | 15 | Must | Yes |
| R3 | Baseline in comparison view | Outcome: "Compare against baseline" | 12 | Should | Yes |
| FR1 | Baseline computation under 4 hours | Processing constraint | — | Must | N/A |

If a requirement has no JTBD source, it needs justification (business
constraint, technical requirement, regulatory mandate). If it can't be
justified, remove it.

## Inline Clarification Markers

When a requirement contains an unresolved decision, mark it INLINE where
the ambiguity lives — not just in the Open Questions table at the end.

**Format:** ⚠️ NEEDS CLARIFICATION (Q[N]): [what's unresolved]

**Example:**

"The system computes a personal baseline using ⚠️ NEEDS CLARIFICATION
(Q1): statistical method not decided — median, weighted average, or
percentile-based approach."

Every inline marker must have a corresponding row in the Open Questions
table (§6) with an owner and deadline. The inline marker makes the
ambiguity visible where it matters. The table tracks resolution.

**Why inline, not just in the table:** A developer reading R1 sees the
clarification marker immediately and knows not to make assumptions about
the statistical method. Without the inline marker, they might read R1,
assume "average," and discover Q1 only if they read section 6 — which
they might not.

## Functional Requirements

Some requirements are system-level constraints: performance thresholds,
accuracy targets, processing windows, data retention rules, security
policies. These describe how the system behaves, not what users experience.

**When to use functional requirements:**

- Performance: "System must compute baselines within the nightly window"
- Accuracy: "System must maintain ≥85% categorization accuracy"
- Scalability: "System must handle 1000 concurrent baseline queries"
- Data: "System must retain baseline history for 12 months"
- Security: "System must not expose individual spending data cross-user"

**Format:** "System must [capability] when [condition]." with priority.

**When NOT to use functional requirements:** If the constraint is
user-facing ("users want to see their baseline"), write it as a job
story. Functional requirements are for constraints the user never sees
directly.

Functional requirements complement job stories. Job stories say WHAT
users experience. Functional requirements constrain HOW the system
delivers it. Both live in the PRD, but job stories come first.

## Edge Cases

After individual requirements and functional requirements, identify
cross-cutting boundary conditions:

- What happens at data boundaries? (user with 50+ categories, user with
  exactly 3 months of data, user with one huge transaction)
- What happens when systems fail? (categorization service down, baseline
  computation fails mid-run)
- What happens with unusual inputs? (negative transaction amounts, refunds,
  duplicate transactions)

Edge cases may already be covered by individual acceptance scenarios. This
section catches the ones that span multiple requirements.

## Writing for Two Audiences

PRD artifacts are read by both humans and agents. Write for the human
first — a PM, designer, or stakeholder should understand the PRD without
any Sage knowledge. The structure also serves agents — Given/When/Then
scenarios translate directly to tests, inline markers flag unresolved
decisions, and the traceability table enables automated checking.

**For human readers:**
- Problem statement (§1) should be understandable in 2 minutes with zero
  context about the product's internals
- "Why this priority" should make sense to a stakeholder who hasn't read
  the JTBD analysis
- The JTBD Summary appendix should give enough context that someone who
  has never opened the JTBD file understands the customer perspective

**For agent readers:**
- Given/When/Then scenarios are directly translatable to test cases
- Inline ⚠️ markers flag decisions that must be resolved before implementing
- "Delivers value independently" maps to milestones in the plan
- The traceability table enables automated requirement-to-outcome checking

## Writing Acceptance Criteria

### The SMART Test

Every acceptance criterion must be:
- **Specific:** What exactly is being tested?
- **Measurable:** What is the pass/fail threshold?
- **Achievable:** Can engineering verify this in a test?
- **Relevant:** Does this connect to the requirement's intent?
- **Time-bound:** When/how often does this condition apply?

### Common Formats

**Given-When-Then (behavioral):**
- Given a user has completed ≥10 transactions in "Dining" this month
- When they complete another Dining transaction
- Then the transaction result screen shows: "Dining this month: [amount],
  [X]% [higher/lower] than your typical month"

**Threshold (performance):**
- The insight calculation completes within 2 seconds of transaction
  confirmation
- Categorization accuracy ≥85% across all transaction types, measured
  weekly

**Negative (boundary):**
- If the user has fewer than 3 transactions in a category, no comparison
  insight is shown for that category (insufficient data)
- If the categorization confidence is below 70%, the transaction is
  labeled "Uncategorized" rather than showing a potentially wrong category

### Anti-Patterns in Acceptance Criteria

| Anti-Pattern | Example | Fix |
|---|---|---|
| Vague quality | "Insights should be helpful" | "≥60% of test users rate insight as relevant" |
| Solution-specific | "Show a red banner" | "Communicate that spending exceeds threshold" |
| Missing threshold | "System should be fast" | "Response time <2s at p95" |
| Subjective | "UI should be intuitive" | "New users complete task without help in ≤30s" |
| No negative case | Only happy-path criteria | Add: "If data insufficient, show [fallback]" |

## Prioritization

### MoSCoW Framework

**Must have (≤40% of requirements):**
- Without this, the initiative fails to deliver its primary value
- Maps to JTBD outcomes with opportunity score ≥15
- Non-negotiable for launch

**Should have (≤30% of requirements):**
- Important but the initiative still delivers value without it
- Maps to JTBD outcomes with opportunity score 12-14
- Include if timeline permits

**Could have (≤20% of requirements):**
- Desirable enhancement, not essential
- Maps to JTBD outcomes with opportunity score 10-11
- Include only if no trade-off with Must/Should

**Won't have (this time):**
- Explicitly out of scope for this initiative
- Move to backlog with rationale
- Prevents scope creep by acknowledging the request while deferring it

### Prioritization Rules

1. **JTBD opportunity score is the primary ranking signal.** Higher
   opportunity = higher priority. Don't override this with stakeholder
   preferences unless there's a business constraint.

2. **Limit Must-haves ruthlessly.** If everything is a Must, nothing is.
   The discipline of prioritization IS the value of the PRD — it forces
   the team to focus.

3. **Won't-haves are not failures.** They show strategic discipline.
   A PRD that says "we considered X and decided not to include it because
   Y" is stronger than one that ignores X.

4. **Dependencies affect priority.** A Could-have that enables three future
   Must-haves may deserve promotion. Document the dependency chain.

## Quality Checklist

### Problem Statement
- [ ] Identifies the job performer (from JTBD)
- [ ] States the main job (from JTBD)
- [ ] Cites specific pains with evidence (numbers, quotes, data)
- [ ] Identifies the opportunity (highest-scoring outcomes)
- [ ] Two paragraphs or fewer

### Requirements
- [ ] Every requirement uses job story or user story format
- [ ] Every requirement traces to a JTBD outcome or documented pain
- [ ] No requirement specifies a solution (only the problem/need)
- [ ] Requirements are prioritized using MoSCoW with strict limits
- [ ] Must-haves ≤40% of total requirements

### Acceptance Criteria
- [ ] Every requirement has ≥1 acceptance criterion
- [ ] Every criterion is measurable (has a pass/fail threshold)
- [ ] Negative/boundary cases are included
- [ ] No criterion specifies implementation approach

### Scope
- [ ] Non-goals explicitly stated
- [ ] Out-of-scope items listed with rationale
- [ ] Open questions identified with owners

### Evidence
- [ ] Problem statement cites sources (JTBD, surveys, analytics, interviews)
- [ ] Success metrics have baselines and targets
- [ ] Assumptions are explicitly labeled
- [ ] JTBD validation status carried forward (validated vs hypothesized)
