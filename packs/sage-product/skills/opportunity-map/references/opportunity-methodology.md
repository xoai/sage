# Opportunity Mapping Methodology

## Purpose

Provides the structured methodology for assessing which discovered opportunities
to pursue, how they connect to product capabilities, and in what order to
address them. Read this before producing any opportunity map. It covers the
assessment framework, capability mapping, sequencing logic, and the
decision criteria for pursue/monitor/defer.

## What Opportunity Mapping Is

Opportunity mapping is the structured transition from "we understand the
customer's unmet needs" to "here's what we should commit to and why."

It takes discovery outputs (JTBD outcomes, Lean Canvas hypotheses, research
findings — any structured understanding of customer needs) and filters them
through the organization's reality: capabilities, constraints, competitive
position, dependencies, and strategic context.

The output is NOT a roadmap (that's delivery) or a strategy document (that's
too broad). It's a **decision rationale**: which opportunities to pursue, which
to defer, and the reasoning behind each choice — grounded in both customer
evidence and organizational capability.

## When to Use

- After a JTBD analysis or other discovery work has identified multiple
  opportunities and the team needs to decide where to focus
- At planning cycles (quarterly, semi-annually) when reassessing priorities
  against new data
- When competitive landscape changes invalidate previous assumptions
- When new capabilities (technical, operational, partnership) open
  previously infeasible opportunities

## Inputs

Opportunity mapping accepts outputs from various discovery frameworks:

| Discovery Method | What It Provides | How It Maps |
|---|---|---|
| JTBD analysis | Desired outcomes with opportunity scores | Each outcome is a candidate opportunity |
| Lean Canvas | Hypotheses with risk levels | Each high-risk hypothesis is an opportunity to de-risk |
| User research | Identified pains, unmet needs | Each need is a candidate opportunity |
| Market analysis | Market gaps, trends | Each gap is a candidate opportunity |
| Competitive analysis | Competitor weaknesses, unserved segments | Each weakness is a candidate opportunity |

The common input format across all sources: **a need or opportunity with
some measure of importance and current satisfaction.**

If opportunity scoring hasn't been done in discovery, the first step of
mapping is to score. Without scores, all opportunities look equal and
prioritization becomes political rather than evidence-based.

## The Assessment Framework

### Step 1: Score (If Not Already Done)

If discovery outputs include opportunity scores (e.g., from JTBD's
Importance + max(Importance - Satisfaction, 0) formula), use them directly.

If not, apply a lightweight scoring:

**Importance:** How critical is this need to the job performer? (1-10)
- 10 = Job fails completely without this
- 7 = Job is significantly harder without this
- 4 = Nice to have, job still works
- 1 = Barely relevant

**Satisfaction:** How well do current solutions (including ours) serve
this need? (1-10)
- 10 = Perfectly served, no gap
- 7 = Mostly served, minor frustrations
- 4 = Partially served, significant gaps
- 1 = Completely unserved

**Opportunity = Importance + max(Importance - Satisfaction, 0)**
- ≥15 = Critical opportunity (high importance, poorly served)
- 12-14 = Significant opportunity
- 10-11 = Moderate opportunity
- <10 = Low opportunity (either unimportant or already well-served)

### Step 2: Assess Capability Fit

For each scored opportunity, evaluate the organization's ability to serve it.
This is the inside-out lens that discovery doesn't provide.

**Capability assessment questions:**

1. **Do we have a relevant existing capability?**
   - Existing feature that partially addresses this? (extend)
   - Existing data or infrastructure that enables this? (leverage)
   - Existing team expertise in this area? (apply)
   - Nothing — would need to build from scratch? (invest)

2. **What's our unique advantage?**
   - Do we have data competitors don't? (data moat)
   - Do we have distribution competitors lack? (reach advantage)
   - Do we have a user relationship that enables this? (trust advantage)
   - Is there a technical capability we've built that's hard to replicate? (tech moat)
   - No unique advantage — anyone could do this? (commodity)

3. **What's the effort level?**
   - Quick win (days to weeks, existing team)
   - Moderate effort (weeks to months, may need additional resources)
   - Major investment (months to quarters, cross-team coordination)
   - Foundational (requires new capabilities that don't exist yet)

Capture this as a simple matrix, not a formal scoring model. The goal is
structured judgment, not false precision.

### Step 3: Map Dependencies

Opportunities rarely exist in isolation. The job process map from JTBD
provides the natural dependency structure:

- **Sequential dependencies:** Solving "accurate categorization" is a
  prerequisite for "personal spending threshold." You can't detect
  thresholds if categories are wrong.

- **Enablement dependencies:** Solving "post-transaction insight
  relevance" enables (but doesn't require) "spending trend awareness."
  Doing one makes the other easier.

- **Shared foundations:** Multiple opportunities may require the same
  underlying capability. Building it once unlocks several opportunities.

Map these as a simple directed graph:
```
Opportunity A ──requires──▶ Opportunity B
Opportunity C ──enables───▶ Opportunity D
Opportunity A ┐
               ├──require──▶ Foundation X
Opportunity C ┘
```

Dependencies affect sequencing even when they don't affect scoring.
A moderately-scored opportunity that enables three high-scored opportunities
may deserve earlier attention.

### Step 4: Cluster and Decide

Group opportunities by natural themes:

- **Capability cluster:** Opportunities that share the same underlying
  capability investment
- **Segment cluster:** Opportunities that serve the same user segment
- **Journey cluster:** Opportunities that address adjacent steps in the
  job process map

For each cluster, make the decision:

**Pursue (commit resources now):**
- High opportunity score (≥12)
- Strong capability fit (existing capability to extend, or unique advantage)
- Dependencies resolved or resolvable
- Aligns with current strategic direction

**Monitor (track but don't commit yet):**
- High opportunity score but weak capability fit
- Strong capability fit but moderate opportunity score
- Dependencies on other work that hasn't started
- Needs more data before committing (confidence too low)

**Defer (explicitly not now, with rationale):**
- Low opportunity score relative to alternatives
- Would require building fundamentally new capabilities
- Served well enough by current solutions or competitors
- Strategic misalignment (important but not our job)

**The hardest decision is "monitor" vs "pursue."** The temptation is to
pursue everything that scores well. But pursuing too many opportunities
simultaneously dilutes focus and slows all of them. The discipline of
opportunity mapping is choosing 2-3 to pursue and having the rationale
to defer the rest.

### Step 5: Sequence

For the "pursue" opportunities, determine order:

**Sequencing criteria (in priority order):**

1. **Dependencies first:** If A requires B, B comes first regardless of
   score
2. **Quick wins before bets:** If two opportunities have similar scores
   but one is a quick win and the other is a major investment, the quick
   win goes first (builds momentum, generates learning)
3. **Foundation before features:** If a foundational capability unlocks
   multiple opportunities, build it first even if no single opportunity
   justifies it alone
4. **Highest confidence first:** If one opportunity is validated and
   another is hypothesized, the validated one goes first (lower risk)
5. **Highest opportunity score as tiebreaker:** All else equal, higher
   score wins

## The Opportunity Map (Deliverable)

The output is a structured document with:

1. **Opportunity landscape:** All scored opportunities in a visual or
   tabular format showing score, capability fit, and decision
2. **Pursue rationale:** For each "pursue" opportunity — why this one,
   what's our advantage, what's the expected outcome
3. **Dependency map:** How pursue opportunities relate to each other
4. **Sequence with rationale:** Ordered list with the reasoning for
   the order
5. **Monitor list:** What we're watching and what signal would trigger
   a "pursue" decision
6. **Defer list:** What we're explicitly not doing and why
7. **Confidence assessment:** Per-opportunity confidence levels with
   recommended validation activities for low-confidence items
8. **Review trigger:** When to revisit this map (time-based: quarterly,
   or event-based: after research completes, after competitor moves)

## Living Document

Unlike a JTBD analysis (which changes when the customer's job changes,
i.e., rarely) or a PRD (which is scoped to a specific initiative), the
opportunity map is expected to change regularly:

- **Monthly/quarterly:** Review scores against new data. Has satisfaction
  changed? Has importance shifted?
- **After research:** Validation activities increase or decrease confidence.
  A "monitor" item might become "pursue" after interviews confirm the need.
- **After competitive moves:** A competitor serving an opportunity well
  changes the satisfaction score and may shift priority.
- **After shipping:** Delivering on one opportunity changes the landscape —
  dependencies are resolved, related opportunities may rise in priority.

The opportunity map should include a "last reviewed" date and explicit
review triggers so the team knows when to update it.

## LLM Failure Modes

### 1. Treating All Opportunities as Equal

**What happens:** The LLM lists all opportunities from the JTBD analysis
and recommends pursuing all of them, or uses vague language like "these
are all important areas to focus on."

**Root cause:** LLMs avoid making hard choices. Prioritization requires
saying "not this, not now" — which feels like a negative judgment.

**Fix:** Force the decision framework: every opportunity must be labeled
pursue/monitor/defer. Limit "pursue" to 2-4 items. If there are more
than 4 "pursue" items, the mapping isn't done — push harder on trade-offs.

### 2. Ignoring Capability Fit

**What happens:** Opportunities are ranked purely by customer need (the
outside-in score) without considering whether the organization can
actually deliver. A need might score 15 but require capabilities that
would take 2 years to build.

**Root cause:** LLMs don't have access to inside-out information unless
the user provides it. They default to the data they have (customer needs).

**Fix:** Step 2 (capability assessment) is mandatory, not optional. If
the user hasn't provided capability context, ask for it before proceeding.
"What are your team's core technical capabilities? What data do you have
access to? What's your approximate capacity?"

### 3. Linear Ranking Without Dependencies

**What happens:** Opportunities are sorted by score and presented as a
sequential list: do #1 first, then #2, then #3. But #3 might be a
prerequisite for #1.

**Root cause:** LLMs default to sorting algorithms. Dependencies require
graph thinking, which doesn't come naturally from a ranked list.

**Fix:** Step 3 (dependency mapping) must happen before Step 5
(sequencing). The sequence is NOT the score ranking — it's the
dependency-resolved order.

### 4. Solution Creep

**What happens:** While mapping opportunities, the LLM starts describing
solutions. "For opportunity X, we should build a notification system
that..." — this jumps from opportunity assessment into delivery.

**Root cause:** LLMs are trained to be helpful by providing solutions.
Assessment feels incomplete without a solution.

**Fix:** The opportunity map describes WHAT to pursue and WHY, not HOW
to solve it. Solution direction (a brief note on general approach) is
acceptable. Detailed solution design belongs in the PRD.

### 5. Missing the "Do Nothing" Baseline

**What happens:** Every opportunity is assessed against an ideal state,
not against the current trajectory. Sometimes the current solution is
"good enough" and the opportunity cost of pursuing an improvement is
higher than the improvement's value.

**Root cause:** LLMs don't naturally consider opportunity cost. They
evaluate each item in isolation rather than against alternatives —
including the alternative of doing nothing.

**Fix:** For each "pursue" recommendation, explicitly answer: "What
happens if we don't do this? How does the current trajectory play out?"
Sometimes the honest answer is "users will be fine, and we should spend
our resources elsewhere."
