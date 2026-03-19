---
name: jobs-to-be-done
description: >-
  Systematically uncovers customer jobs, pains, and gains using the
  Jobs-to-be-Done framework. Produces structured JTBD analyses with job
  performer definitions, job process maps, pains/gains, and desired outcome
  statements. Use when the user mentions jobs to be done, JTBD, customer
  jobs, unmet needs, pains and gains, value proposition canvas, switch
  interviews, outcome-driven innovation, desired outcomes, or asks why
  customers hire or fire a product. Also triggers when the user wants to
  understand what job a product solves, conduct customer discovery,
  reposition a product around needs, define unmet needs for a roadmap,
  analyze competitors through a jobs lens, or create messaging grounded in
  customer objectives. Do NOT use for general market sizing, feature
  prioritization without a customer-needs lens, or persona creation based
  on demographics alone.
metadata:
  version: 1.3.0
  category: product-management
---

# Jobs-to-be-Done

Produce a structured JTBD analysis: job performer, main job, circumstances, job process map, pains/gains, and (optionally) desired outcome statements.

## Workflow

Copy this checklist and track progress:

```
JTBD Analysis Progress:
- [ ] Step 0: Check product context
- [ ] Step 1: Define job performer and context
- [ ] Step 2: Formulate the main job statement
- [ ] Step 3: Map the job process
- [ ] Step 4: Capture needs (pains/gains)
- [ ] Step 5: Quality check
- [ ] Step 6: Prioritize and identify implications
```

### Step 0: Check product context

Before starting the analysis, read [context.md](context.md).

- **If context.md has no `[TODO]` markers**: All sections are filled in. Use this context to ground the entire analysis — it defines the product, segment, known insights, and scope. Proceed to Step 1.
- **If context.md has `[TODO]` markers in some sections**: Those sections are not yet filled in. Before proceeding, ask the user to provide the missing information. Present all missing sections in a single message — don't ask one at a time.
- **If context.md is entirely unfilled or the file doesn't exist**: Ask the user to provide product context before starting. Specifically, request: (1) what the product does and what stage it's at, (2) who they believe the target job performer is, (3) what they already know from customer feedback or research, and (4) what decision this analysis should inform. Gather everything in one exchange.

After context is established, verify each section is specific enough to ground the analysis. A product description of "B2B SaaS" alone is too thin — it should say what the product does, for whom, and what stage it's at. If any section is present but too vague to be useful, ask the user to elaborate on those specific sections before proceeding.

### Step 1: Define job performer and context

If context.md provided a target segment and existing knowledge, use that as a starting point — refine and deepen it, don't repeat it. If working assumptions were listed, treat them as hypotheses to pressure-test throughout the analysis, not facts to build on.

Identify who executes the job. Distinguish from the buyer — they have different needs.

**Capture:**
- **Job performer**: Role and context (not demographics). "Project lead managing a distributed team of 8–12 engineers" — not "35-year-old male." Demographics correlate with buying but don't cause it.
- **Buyer/Approver**: Who makes and authorizes the purchase decision
- **Audience**: Who consumes the output of the job
- **The struggling moment**: What specific event or frustration triggered the desire for change? Without a struggling moment, there's no demand. "I realized I was sleeping on the recliner every night because our mattress was so bad" is a struggling moment. "People need better mattresses" is a supply-side assumption.
- **Circumstances**: When, where, and under what constraints the job arises. Jobs without context aren't actionable. "Get breakfast on the go while late for work" is specific enough to design for; "get breakfast" is not.
- **Current solutions hired**: What do they use today? Competition is defined by customers, not product categories — it includes any solution that serves the same progress. A project management tool might compete with WhatsApp groups, spreadsheets, and weekly meetings, not just other PM software. Include workarounds, manual processes, and doing nothing. Note **compensatory behaviors** — when customers use products in unintended ways, it signals unmet jobs.

If the user hasn't done research, recommend methods from [references/research-methods.md](references/research-methods.md).

### Step 2: Formulate the main job statement

A job can be framed as a task to accomplish (Ulwick: "restore blood flow in a blocked artery") or as a transformation the performer seeks (Klement: "become someone who can grow my company beyond 5 employees"). Both are valid — task framing works well for functional analysis; transformation framing reveals deeper emotional motivations and helps with messaging. Use whichever fits the situation, or both.

**Format: verb + object + clarifier**

- Good: "Coordinate work across a cross-functional team to deliver a project on time"
- Bad: "Use Slack to communicate" (contains solution), "Be more productive" (too vague, no end state), "Quickly manage finances" (adjective is a need, not part of the job)

A well-formed job is solution-agnostic, stable over time, and has a clear "done" state.

Use "Why?" to move up in abstraction, "How?" to move down:
- **Aspiration**: "Be financially secure" — too broad for product scope
- **Big job**: "Plan long-term retirement savings" — good for product strategy
- **Little job**: "Evaluate investment fund performance" — good for a feature
- **Micro-job**: "Compare two fund fact sheets" — good for UX

Also capture **related jobs** (adjacent objectives) and **emotional/social jobs** (how the performer wants to feel and be perceived). Formulation rules: see [references/quality-checks.md](references/quality-checks.md).

### Step 3: Map the job process

Break the main job into stages. Use this universal scaffold and adapt:

1. **Define** — Plan objectives and approach
2. **Locate** — Gather inputs, information, materials
3. **Prepare** — Set up and organize
4. **Execute** — Perform the core activity
5. **Monitor** — Check progress and quality
6. **Modify** — Adjust when something changes
7. **Conclude** — Finish and wrap up
8. **Share** — Communicate results or hand off

For each stage, note what the performer is trying to accomplish and where friction exists. The map organizes where to probe for needs in Step 4.

### Step 4: Capture needs

Walk through each stage of the job map and capture what goes wrong and what ideal looks like.

**Default: Pains and Gains** (from the Value Proposition Canvas)

Use this for most analyses — it's accessible, workshop-friendly, and sufficient for early discovery and roadmap input.

- **Pains**: Challenges, costliness (be specific — "3 hours/week"), common mistakes, unresolved problems
- **Gains**: Expectations, savings (measurable), adoption factors, life improvement

Use `template.md` for the full fill-in structure. See `examples/sample.md` for worked examples.

**Also analyze: The Four Forces of Progress** (from Moesta)

Pains and gains capture what's wrong and what's desired, but they miss what *blocks people from switching*. The four forces determine whether someone actually acts:

1. **Push** — Frustration with the current situation (drives change)
2. **Pull** — Magnetism of a new, better solution (drives change)
3. **Anxiety** — Fear and uncertainty about the new solution (blocks change)
4. **Habit** — Comfort and inertia of the current way (blocks change)

People switch only when (Push + Pull) > (Anxiety + Habit). In practice, reducing anxiety often unlocks more demand than adding features. Casper disrupted mattresses not by building a better mattress, but by eliminating the anxiety of buying one (100-day returns, no showroom pressure, bed-in-a-box delivery).

For each force, probe functional, emotional, and social dimensions. See [references/forces-and-timeline.md](references/forces-and-timeline.md) for detail and interview questions.

**For higher rigor: Desired Outcome Statements** (from Ulwick's ODI)

Use when needs must be quantitatively prioritizable — roadmap trade-offs, surveys, competitive scoring.

Format: **direction + measure + object + clarifier**
- "Minimize the time it takes to identify a blocked task"
- "Reduce the likelihood of missing a cascading impact when a deadline changes"

Attach outcomes to job map stages. A thorough pass yields 50–150; a lightweight pass yields 15–30. See [references/quality-checks.md](references/quality-checks.md) for formulation rules.

### Step 5: Quality check

Before presenting results, validate against this checklist. If issues are found, fix and re-check.

```
Quality Validation:
- [ ] Job performer is defined and distinguished from buyer
- [ ] Main job follows verb + object + clarifier, no embedded solutions
- [ ] Emotional/social jobs are separate from functional jobs
- [ ] A struggling moment is identified — not just generic circumstances
- [ ] Current solutions documented including workarounds and non-obvious competitors
- [ ] Pains are specific (numbers, frequencies, consequences) — not "tools are bad"
- [ ] Gains are measurable or observable — not "better UX"
- [ ] No statement confuses a job with a solution (supply-side test: would an engineer write this, or a customer?)
- [ ] Forces of progress analyzed — especially anxiety and habit blocking the switch
- [ ] Needs are prioritized, not just listed
- [ ] Analysis is consistent with scope and constraints from context.md (if provided)
- [ ] Working assumptions from context.md are explicitly confirmed, challenged, or refined
```

If the analysis was built from assumptions rather than research, flag this explicitly. See [references/pitfalls.md](references/pitfalls.md) for common mistakes.

### Step 6: Prioritize and identify implications

Rank pains by intensity (acute + frequent → highest priority). Separate must-have gains from nice-to-haves. Identify which forces of progress represent the biggest levers — often, reducing anxiety or breaking habit unlocks more demand than amplifying push or pull.

If using desired outcome statements, apply **opportunity scoring**: Opportunity = Importance + max(Importance − Satisfaction, 0). Scores above 12 are significant; above 15 are critical.

Check whether different performer segments have different unmet needs. Then surface implications for product strategy, messaging, and competitive positioning. For go-to-market implications, map findings to the **buying timeline** (First Thought → Passive Looking → Active Looking → Deciding → Onboarding → Ongoing Use) — see [references/forces-and-timeline.md](references/forces-and-timeline.md).

Frame value in terms of progress, not just outcomes. Progress is continuous — customers evaluate whether things are getting better at every touchpoint, not just at the end. A product that delivers an ongoing feeling of progress retains customers; one that delivers only a final outcome gets churned.

---

## Key Principles

These are reminders, not explanations — apply them as quality filters throughout the workflow.

- **Separate jobs from solutions.** "Communicate with my team" is a job. "Use Slack" is a solution.
- **Demand-side, not supply-side.** Describe the customer's struggle and desired progress, not your product's features. If an engineer would write the statement, it's supply-side. If a customer would say it, it's demand-side.
- **The struggling moment is the seed.** Without a specific struggling moment, there's no demand. People don't buy when they're comfortable — they buy when something in their life stops working.
- **Functional first, then emotional.** Solve the functional job before layering emotional/social dimensions.
- **Jobs are stable; solutions change.** If the job statement wouldn't make sense 50 years ago, it probably contains an embedded solution.
- **Competition is defined by customers.** They use progress as their criterion, not product categories. When someone starts using a solution for a job, they stop using something else — it's a zero-sum game.
- **People convince themselves; you convince them of nothing.** Reduce anxiety and break habit to unlock demand. Adding features often increases anxiety rather than reducing it.
- **Depth over breadth.** A thorough analysis of one well-defined job beats a shallow pass on five vague ones.

---

## References

**Bundled files** (one level deep — read as needed):
- [context.md](context.md) — Product and market context (fill in before distributing, or leave for user to provide)
- [template.md](template.md) — Fill-in template for JTBD analysis
- [examples/sample.md](examples/sample.md) — Worked examples (good and bad)
- [references/quality-checks.md](references/quality-checks.md) — Formulation rules and validation criteria
- [references/forces-and-timeline.md](references/forces-and-timeline.md) — Four Forces of Progress and the buying timeline
- [references/pitfalls.md](references/pitfalls.md) — Common mistakes and troubleshooting
- [references/research-methods.md](references/research-methods.md) — Switch interviews, outcome-driven interviews, contextual inquiry

**Theoretical foundations**: Christensen (*Competing Against Luck*), Ulwick (*Jobs to be Done: Theory to Practice*), Kalbach (*The Jobs to be Done Playbook*), Moesta (*Demand-Side Sales 101*), Klement (*When Coffee and Kale Compete*), Osterwalder (*Value Proposition Design*).
