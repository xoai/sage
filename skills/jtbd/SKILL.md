---
name: jtbd
description: >
  Produces a structured Jobs-to-be-Done analysis: job performer, main job,
  job process map, pains/gains, and desired outcome statements. Use when the
  user mentions jobs to be done, JTBD, customer jobs, unmet needs, pains and
  gains, switch interviews, outcome-driven innovation, desired outcomes, or
  asks why customers hire or fire a product. Also triggers when the user wants
  to understand what job a product solves, conduct customer discovery,
  reposition a product around needs, define unmet needs for a roadmap,
  analyze competitors through a jobs lens, or create messaging grounded in
  customer objectives. Do NOT use for general market sizing, feature
  prioritization without a customer-needs lens, or persona creation based
  on demographics alone.
version: "1.1.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [product-management, jtbd, customer-jobs, discovery, needs]
inputs: [product-context]
outputs: [jtbd-analysis]
requires: []
-->

# Jobs-to-be-Done Analysis

Produce a structured JTBD analysis grounded in canonical methodology from
Ulwick, Christensen, Moesta, Kalbach, and Klement. The output is a document
deliverable — not code.

**Deliverable type:** document

## Mode Behaviors

**FIX (update):** Update specific claims in an existing JTBD analysis with new
evidence — new interview data, updated survey results, changed metrics, or
corrected assumptions. Don't re-run the full process. Locate the claim, update
it, adjust confidence level, and note what changed and why. Minutes, not hours.

**BUILD (light):** Quick job framing. Run Steps 0-2 (context, job performer,
main job) and a lightweight Step 4 (top 3-5 pains/gains, no formal desired
outcome statements). Skip the full job process map (Step 3) and opportunity
scoring (Step 5-6). Produces a focused analysis sufficient to ground a PRD
or guide a quick prioritization decision. 15-20 minutes.

**ARCHITECT (full):** Complete 6-step process. Full job process map, all desired
outcome statements with opportunity scoring, validation needs identified,
strategic implications documented. The comprehensive analysis that grounds
a product strategy. 45-60 minutes.

## When to Use

- User asks for a JTBD analysis, customer jobs analysis, or needs discovery
- Product team needs to understand what job their product is hired for
- Roadmap prioritization needs customer-grounded evidence
- Competitive analysis needs a jobs lens (not feature comparison)
- Repositioning or messaging work needs customer motivation framing

## Process

### Step 0: Establish Product Context

Read `templates/jtbd-context-template.md`.

If the user has not provided product context, ask for it in ONE message:
1. What the product does, who it's for, what stage it's at
2. Who they believe the target job performer is
3. What they already know from customer feedback or research
4. What decision this analysis should inform

If context is provided but thin (e.g., "B2B SaaS" with no specifics), ask
the user to elaborate on the gaps before proceeding. A vague context produces
a generic analysis — the most common failure mode.

### Step 1: Define Job Performer and Context

**Read first:** `references/jtbd-methodology.md` (Core Concepts section)

Identify who executes the job. Distinguish from the buyer.

Capture:
- **Job performer:** Role and context (not demographics)
- **Buyer/Approver:** Who makes and authorizes the purchase decision
- **Audience:** Who consumes the output of the job
- **Circumstances:** When, where, and under what constraints the job arises.
  Jobs without circumstances aren't actionable.
- **Current solutions hired:** What do they use today? Include non-obvious
  alternatives — spreadsheets, workarounds, manual processes, doing nothing.

If the user hasn't done research, recommend methods from
`references/research-methods.md` and offer to proceed with hypothesized data
(clearly labeled).

### Step 2: Formulate the Main Job Statement

**Read first:** `references/formulation-rules.md` (Job Statement Rules)

Format: **verb + object + contextual clarifier**

Good: "Coordinate work across a cross-functional team to deliver a project on time"
Bad: "Use Slack to communicate" (solution embedded)

Apply the level check: use "Why?" to move up in abstraction, "How?" to move
down. Match the level to the decision the analysis informs — strategy needs
big jobs, feature design needs little jobs.

Also capture:
- **Related jobs** (adjacent objectives during the main job)
- **Emotional jobs** (how the performer wants to feel or avoid feeling)
- **Social jobs** (how they want to be perceived, and by whom)

### Step 3: Map the Job Process

Break the main job into stages using the universal scaffold:

1. **Define** — Plan objectives and approach
2. **Locate** — Gather inputs, information, materials
3. **Prepare** — Set up and organize
4. **Confirm** — Ensure everything is ready
5. **Execute** — Perform the core activity
6. **Monitor** — Check progress and quality
7. **Modify** — Adjust when something changes
8. **Conclude** — Finish, wrap up, hand off

Adapt labels to the specific job. Keep labels as single-word verbs where
possible. For each stage, note what the performer is trying to accomplish
and where friction exists. The map organizes where to probe for needs in
Step 4.

### Step 4: Capture Needs

Walk through each stage of the job map and capture what goes wrong and what
ideal looks like.

**Default approach: Pains and Gains**

Use for most analyses — accessible, workshop-friendly, sufficient for early
discovery and roadmap input.

- **Pains:** Challenges (obstacles), costliness (be specific — "3 hours/week"),
  common mistakes, unresolved problems with current solutions
- **Gains:** Expectations (exceeding current), savings (measurable),
  adoption factors, life improvements

**For higher rigor: Desired Outcome Statements**

**Read first:** `references/formulation-rules.md` (Desired Outcome Statement Rules)

Use when needs must be quantitatively prioritizable — roadmap trade-offs,
surveys, competitive scoring.

Format: **direction + measure + object + clarifier**
- "Minimize the time it takes to identify a blocked task"
- "Reduce the likelihood of missing a cascading impact when a deadline changes"

Attach outcomes to job map stages. A thorough pass yields 50-150; a
lightweight pass yields 15-30.

### Step 5: Quality Check

**Read first:** `references/pitfalls.md`

Before presenting results, validate against the overall analysis checklist
from `references/formulation-rules.md`. If issues are found, fix and re-check.

Critical checks:
- Job performer defined and distinguished from buyer
- Main job follows format, no embedded solutions
- Pains are specific (numbers, frequencies, consequences) — not "tools are bad"
- No statement confuses a job with a solution
- Needs are prioritized, not just listed
- Analysis labeled as "validated" or "hypothesized — needs validation"

### Step 6: Prioritize and Identify Implications

Rank pains by intensity (acute + frequent → highest priority). Separate
must-have gains from nice-to-haves.

If using desired outcome statements, apply opportunity scoring:
```
Opportunity = Importance + max(Importance - Satisfaction, 0)
```
Scores above 12 = significant. Above 15 = critical.

Check whether different performer segments have different unmet needs.

Surface implications for:
- **Product strategy:** What to build/improve based on top unmet needs
- **Messaging:** How to speak about the product in job terms, not features
- **Competitive positioning:** Where current solutions fall short on
  highest-opportunity outcomes
- **Validation needs:** Which assumptions still need quantitative confirmation

## Output

Save to `.sage/docs/jtbd-analysis.md` using the template
from `templates/jtbd-analysis-template.md`. See `examples/jtbd-sample.md`
for a worked example.

Update `.sage/journal.md`: append a change log entry recording what was
produced, key findings, confidence level, and recommended next steps.
Update the "Current Artifacts" section to list the new file as Active.

Present to user: "Here's the JTBD analysis. The top 3 unmet needs are [X, Y, Z].
Want to refine any section, or should we use this to inform [the next step]?"

## Rules

**MUST:**
- MUST read `references/jtbd-methodology.md` before starting any analysis
- MUST distinguish job performer from buyer — designing for the wrong person
  cascades through the entire analysis
- MUST validate every job statement against formulation rules — no embedded
  solutions, no adjectives-as-needs, no compound statements
- MUST label the analysis as "validated" (based on research) or "hypothesized —
  needs validation" (based on assumptions)
- MUST prioritize needs, not just list them — an unprioritized list is not
  actionable

**SHOULD:**
- SHOULD use both Pains/Gains AND Desired Outcome Statements when the analysis
  informs roadmap decisions — Pains/Gains for accessibility, outcomes for precision
- SHOULD capture the four forces (push, pull, anxiety, habit) when analyzing
  switching behavior or competitive positioning
- SHOULD include the buying timeline when the analysis informs go-to-market
  strategy or messaging
- SHOULD ask the user to provide or validate circumstances — don't invent
  them from assumptions

**MAY:**
- MAY skip Desired Outcome Statements for early-stage discovery where
  Pains/Gains provide sufficient clarity
- MAY use a lighter job map (Define, Execute, Monitor, Conclude) for simple
  consumer jobs where the full 8-stage map is overkill
- MAY recommend specific research methods from `references/research-methods.md`
  when the user has access to customers

## Failure Modes

- **User provides no product context:** Don't proceed. Ask for context first.
  A JTBD analysis without grounding produces generic output.
- **User wants JTBD for "all users":** Push back. "All users" is not a job
  performer. Ask who specifically performs the job and in what circumstances.
- **Analysis produces only generic outcomes:** The context is too thin or
  the analysis isn't grounded in specific performer behavior. Add more
  circumstance detail, or recommend research before continuing.
- **Stakeholders disagree on the main job:** Go back to job performer
  definition. Once you agree on WHO, the job usually clarifies.
- **User wants features, not jobs:** Redirect: "Let's understand what your
  customers are trying to accomplish first, then we can map features to
  those jobs. This ensures we build what matters most."
