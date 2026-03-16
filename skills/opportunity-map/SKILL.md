---
name: opportunity-map
description: >
  Produces an opportunity map that assesses discovered customer needs against
  product capabilities, determines which to pursue, and sequences them. Takes
  any discovery output (JTBD analysis, research findings, lean canvas) as
  input and applies inside-out assessment to produce pursue/monitor/defer
  decisions. Use when the user asks what to focus on, what to build next,
  which opportunities to prioritize, or how to sequence product work. Also
  triggers when the user says "help me decide what to pursue" or "we have
  too many opportunities, help us focus." Do NOT use for detailed requirements
  (that's PRD) or for understanding customer needs (that's discovery).
version: "1.1.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [product-management, opportunity, prioritization, planning, sequencing]
inputs: [discovery-output]
outputs: [opportunity-map]
requires: []
-->

# Opportunity Map

Produce a structured assessment of which discovered opportunities to pursue,
based on both customer evidence (outside-in) and organizational capability
(inside-out). The output is a living decision document — expected to be
reviewed and updated regularly as new data arrives.

**Deliverable type:** document

## Mode Behaviors

**FIX (update):** Update an existing opportunity map with new information —
revised scores after research, changed decisions after a competitor move,
resolved dependencies after shipping a feature. Don't re-run the full
assessment. Update the affected scores/decisions, adjust sequencing if needed,
and note what changed and why. Minutes.

**BUILD (light):** Quick assessment. Score the top 3-5 opportunities from
discovery, do a lightweight capability check (existing capability? unique
advantage?), make pursue/defer decisions without detailed dependency mapping
or sequencing rationale. Produces a focused decision sufficient to move into
a PRD. 10-15 minutes.

**ARCHITECT (full):** Complete assessment. All opportunities scored with
capability fit, full dependency map, detailed sequencing with rationale,
monitor/defer lists with signals, confidence tracking per opportunity,
review plan with triggers. The comprehensive decision document. 30-45 minutes.

## When to Use

- After discovery work (JTBD, research, lean canvas) has identified multiple
  opportunities and the team needs to decide where to focus
- At planning cycles when reassessing priorities against new data
- When the competitive landscape shifts or new capabilities emerge
- When a PM says "we have all these needs — what should we actually do?"

## Prerequisites

This skill requires structured discovery output. Accepted inputs:

- **JTBD analysis:** Desired outcomes with opportunity scores (ideal)
- **Research findings:** Identified needs with importance/satisfaction signals
- **Lean Canvas:** Hypotheses with risk levels
- **Any structured list of customer needs with some measure of priority**

If the input has opportunity scores (Importance + Satisfaction → Score),
use them directly. If not, Step 1 applies lightweight scoring.

If NO discovery work exists: recommend running a discovery skill first
(e.g., `jtbd`). Opportunity mapping without customer evidence produces
opinion-based prioritization — flag this prominently if the user insists.

## Process

### Step 0: Gather Context

**Read first:** `references/opportunity-methodology.md`

Confirm with the user in ONE message:

1. **Discovery input:** Which analysis is this based on? Where are the
   scored opportunities?
2. **Capability context:** What are the team's core technical capabilities?
   What data, infrastructure, or distribution advantages exist? What's the
   approximate team capacity and timeline horizon?
3. **Strategic context:** What direction has leadership set? Are there
   constraints or mandates that override pure opportunity scoring?
4. **Scope:** Is this for a specific feature area, an entire product, or
   a new product? (Affects the granularity of assessment)

If the user provides discovery output but no capability context, ask for
it explicitly: "The opportunity scores tell me what customers need. To
assess which opportunities YOU should pursue, I need to understand your
capabilities and constraints. What does your team do well? What data or
technology advantages do you have?"

### Step 1: Score Opportunities

If discovery output includes opportunity scores, import them directly.

If not, walk through each identified need and apply the lightweight
scoring from `references/opportunity-methodology.md`:
- Importance (1-10): How critical is this need to the job performer?
- Satisfaction (1-10): How well do current solutions serve this need?
- Opportunity = Importance + max(Importance - Satisfaction, 0)

Tag each opportunity's confidence level based on the evidence behind it:
- **High:** Validated by quantitative data (survey n≥100) or multiple
  qualitative sources (8+ interviews)
- **Medium:** Supported by limited qualitative data (3-7 interviews) or
  consistent indirect signals (metrics, behavioral data)
- **Low:** Hypothesized from context or 1-2 data points — needs validation

Present the scored landscape to the user for review before proceeding.
Scores are judgment calls — the user may adjust based on context the
discovery didn't capture.

### Step 2: Assess Capability Fit

For each opportunity scoring ≥10, assess organizational capability:

**Three questions per opportunity:**

1. **Existing capability:** What do we already have that serves this need,
   even partially? (Feature, data, infrastructure, expertise)
2. **Unique advantage:** What do we have that competitors can't easily
   replicate? (Data moat, distribution, trust, technology)
3. **Effort level:** How much work to address this opportunity?
   (Quick win / Moderate / Major / Foundational)

Capture as a capability assessment table. Keep it structured but
qualitative — false precision is worse than honest judgment here.

If the user hasn't provided enough capability context, this step will
surface the gaps: "I can't assess capability fit for opportunity O3
because I don't know what transaction data you have access to. Can you
clarify?"

### Step 3: Map Dependencies

Examine the relationships between opportunities:

- **Requires:** O1 can't work without O3 being solved first
- **Enables:** Solving O2 makes O4 significantly easier or more valuable
- **Shares foundation:** O1 and O2 both need the same underlying capability

The job process map from JTBD (if available) provides the natural dependency
structure — needs at earlier job stages often need to be addressed before
needs at later stages.

Document as a simple dependency map (text or diagram). Identify:
- Any "foundation" capabilities that multiple opportunities depend on
- Any circular dependencies (these indicate the opportunities may need to
  be tackled as one initiative)
- Any opportunities that are independent (can be pursued in parallel)

### Step 4: Decide

For each opportunity, assign one of three decisions:

**Pursue** (limit to 2-4 opportunities):
- High opportunity score (≥12)
- Strong or buildable capability fit
- Dependencies resolved or resolvable within the planning horizon
- For each: document WHY pursue, WHAT's our advantage, WHAT happens if
  we don't (the do-nothing alternative)

**Monitor** (track, don't commit):
- High score but weak capability fit, or
- Strong fit but moderate score, or
- Key dependency not yet resolved, or
- Confidence too low — needs validation first
- For each: document WHAT signal would change this to "pursue"

**Defer** (explicitly not now):
- Low score relative to alternatives, or
- Requires fundamentally new capabilities we can't build in the horizon, or
- Already well-served by competitors, or
- Strategic misalignment
- For each: document WHY deferred and WHEN to reconsider

**Hard rule:** If more than 4 opportunities are "pursue," push back.
"You've selected [N] opportunities to pursue. With [team size/capacity],
this means each gets roughly [fraction] of available resources. Is that
enough to make real progress on any of them? Consider: which 2-3 would
you pursue if you could only pick that many?"

### Step 5: Sequence

For the "pursue" opportunities, determine order using the criteria from
`references/opportunity-methodology.md`:

1. Dependencies first (B before A if A requires B)
2. Quick wins before bets (build momentum and learning)
3. Foundation before features (shared capabilities first)
4. Higher confidence before lower (lower risk first)
5. Higher score as tiebreaker

For each position in the sequence, explain why it's in that order.
The rationale matters more than the ranking — it helps the team
understand and commit to the plan.

### Step 6: Define Review Plan

The opportunity map is a living document. Define:

- **Next scheduled review date** (typically quarterly, or end of current
  planning cycle)
- **Event-based triggers** for earlier review:
  - Research results that change confidence levels
  - Competitor launch that shifts satisfaction scores
  - Shipped feature that resolves dependencies
  - Strategic direction change from leadership
  - Team capacity change

### Step 7: Quality Check

Before presenting, validate:

- [ ] Every opportunity has a score, confidence level, and decision
- [ ] No more than 4 opportunities are "pursue"
- [ ] Every "pursue" has a rationale including do-nothing alternative
- [ ] Every "monitor" has a specific trigger signal
- [ ] Every "defer" has a rationale and reconsider condition
- [ ] Dependencies are mapped and reflected in sequencing
- [ ] Capability context from the user informed the assessment
- [ ] Confidence levels are tagged per opportunity with validation needs
- [ ] Review plan is defined with date and event triggers

## Output

Save to `.sage/docs/opportunity-map.md` using the
template from `templates/opportunity-map-template.md`.

Update `.sage/journal.md`: append a change log entry recording pursue/
monitor/defer decisions, key rationale, and sequencing. Update the
"Current Artifacts" section.

Present to user: "Here's the opportunity map. I recommend pursuing [N]
opportunities: [X, Y, Z]. [X] comes first because [rationale]. [M]
opportunities are on the monitor list — the key signal to watch is
[signal]. Want to discuss any of the decisions?"

## Rules

**MUST:**
- MUST read `references/opportunity-methodology.md` before starting
- MUST have structured discovery output as input — mapping without
  customer evidence produces opinion-based prioritization
- MUST gather capability context from the user — opportunity scores
  alone don't tell you what to pursue (outside-in without inside-out
  produces wish lists)
- MUST limit "pursue" to 2-4 opportunities — if everything is a
  priority, nothing is
- MUST include the do-nothing alternative for every "pursue" decision —
  this prevents pursuing opportunities that don't justify the cost
- MUST define a review plan — the opportunity map expires
- MUST tag confidence per opportunity and recommend validation for
  low-confidence items

**SHOULD:**
- SHOULD present the scored landscape to the user for review before
  making decisions (scores are judgment calls)
- SHOULD use the job process map (from JTBD) to inform dependency
  mapping when available
- SHOULD identify foundation capabilities that unlock multiple
  opportunities
- SHOULD note when an opportunity moves from "monitor" to "pursue"
  would require additional discovery work

**MAY:**
- MAY produce a lightweight map in BUILD mode (fewer opportunities,
  simpler assessment) when scope is a single feature area
- MAY include brief solution direction notes (1-2 sentences per
  opportunity) to help evaluate feasibility — but not detailed solutions
- MAY recommend specific discovery or research skills to run for
  low-confidence opportunities

## Failure Modes

- **No capability context provided:** Don't produce a map with only
  outside-in scores. Ask for capability context first. If the user can't
  provide it, the map will note "capability fit unassessed" for all
  opportunities and recommend the user complete this assessment with
  their team.

- **All opportunities score high:** This usually means the satisfaction
  scores are too uniformly low (common when the product is new or the
  category is immature). Differentiate by asking: "Among these, which
  need do users complain about MOST vocally?" or "Which of these, if
  solved, would be the strongest reason to choose your product?"

- **User wants to pursue everything:** This is the most common failure
  mode in real PM work. Push back with: "Pursuing [N] opportunities with
  [capacity] means each gets [fraction] of focus. History suggests this
  produces mediocre progress on everything rather than breakthrough
  progress on anything. Which 2-3 would move the needle most?"

- **Discovery input is a feature list, not needs:** If the user provides
  "we want to build: notification system, dashboard, AI categorization"
  instead of customer needs, redirect: "These sound like solutions. Let's
  back up — what customer needs do these address? Running a JTBD analysis
  would give us the needs to map these solutions against."

- **Opportunity map becomes a one-time artifact:** Remind the user that
  the map is designed to be reviewed regularly. "This map reflects what
  we know today. I've set a review trigger for [date/event]. When new
  data comes in, we should revisit the scores and decisions."
