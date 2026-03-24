# Jobs-to-be-Done Methodology

## Purpose

Provides the structured methodology for conducting a JTBD analysis. Read this
before starting any JTBD work. It covers the key concepts, the two schools of
thought, and how they complement each other.

## Two Schools, One Framework

JTBD has two major interpretations that practitioners should understand:

**Outcome-Driven Innovation (Ulwick):** Focuses on the core functional job as
a process with measurable steps. Jobs are activities with desired outcomes
that can be quantified through importance/satisfaction surveys. Strength:
precision, quantitative prioritization, systematic. Best for: roadmap
prioritization, competitive analysis, large-scale opportunity sizing.

**Jobs-as-Progress (Christensen, Moesta, Klement):** Focuses on the progress
a person is trying to make in their life. Emphasizes the emotional and social
dimensions of switching, the forces that drive and resist change. Strength:
narrative, motivation, demand-side understanding. Best for: understanding why
people switch, messaging, early discovery, go-to-market strategy.

These are not competing — they address different questions. Use ODI when you
need to know WHAT specific outcomes are underserved. Use Jobs-as-Progress when
you need to know WHY people change behavior. A complete JTBD analysis draws
from both.

## Core Concepts

**Job Performer:** The person executing the job. Defined by role and context,
not demographics. Distinct from the buyer (who pays), the approver (who
authorizes), and the audience (who consumes the output). Getting this wrong
cascades through the entire analysis — the wrong performer means the wrong
job, the wrong pains, the wrong product.

**Main Job Statement:** A concise description of what the performer is trying
to accomplish. Format: verb + object + contextual clarifier. Must be
solution-agnostic (no product names, no technology), stable over time (would
make sense 20 years ago and 20 years from now), and have a clear "done" state.

**Job Map:** The universal process structure for how any job gets done. Eight
stages adapted from Ulwick/Bettencourt: Define → Locate → Prepare → Confirm →
Execute → Monitor → Modify → Conclude. Each job instantiates these stages
differently. The map provides the scaffold for systematically uncovering needs
at each stage.

**Desired Outcome Statements:** The metrics performers use to measure success
at each job stage. Format: direction + measure + object + clarifier. Example:
"Minimize the time it takes to identify a blocked task." Outcomes are
solution-agnostic, measurable, and stable. A thorough analysis produces
50-150; a lightweight pass produces 15-30.

**Pains and Gains:** A more accessible framing of needs (from Osterwalder's
Value Proposition Canvas). Pains are obstacles, costs, and frustrations. Gains
are expectations, savings, and improvements. Use for early discovery and
workshops. Graduate to desired outcome statements when quantitative
prioritization is needed.

**Forces of Progress (Moesta/Klement):** Four forces that drive or resist
switching behavior:
- Push: frustration with the current situation
- Pull: attraction to a new solution's promise
- Anxiety: fear about the new solution (will it work? learning curve?)
- Habit: comfort with the existing way (even if suboptimal)

All four must be understood to predict adoption. A product with strong pull
but unaddressed anxiety won't get hired. A product in a market with weak push
won't create demand regardless of how good it is.

**Buying Timeline (Moesta):** Six stages of the decision journey: First
Thought → Passive Looking → Active Looking → Deciding → Onboarding → Ongoing
Use. Each stage has trigger events that move people forward. Understanding
the timeline reveals where demand originates and what catalyzes action.

**Emotional and Social Jobs:** Parallel to the functional job. Emotional jobs
describe how the performer wants to feel (confident, in control, relieved).
Social jobs describe how they want to be perceived (competent, reliable,
innovative). These are captured separately from functional jobs but influence
adoption and satisfaction significantly.

**Related Jobs:** Adjacent objectives the performer handles alongside the main
job. These reveal cross-sell opportunities and integration points. A person
whose main job is "prepare a meal" has related jobs like "clean up after
cooking" and "plan grocery shopping."

## Opportunity Scoring (Ulwick)

The quantitative method for prioritizing unmet needs:

```
Opportunity = Importance + max(Importance - Satisfaction, 0)
```

- Importance: how critical this outcome is to the performer (1-10)
- Satisfaction: how well current solutions deliver on this outcome (1-10)
- Scores above 12: significant opportunity
- Scores above 15: critical opportunity (high importance, low satisfaction)

This transforms subjective needs into ranked priorities. Use it when you need
data-driven decisions about what to build next, or when stakeholders disagree
about priorities.

## Common LLM Failure Modes

When LLMs perform JTBD analysis without guidance, they consistently fail in
these ways:

1. **Embed solutions in job statements.** "Use AI to track expenses" instead
   of "track expenses accurately." The LLM's training is dominated by product
   descriptions, so it defaults to solution language.

2. **Generate generic outcomes.** "Improve efficiency" and "save time" appear
   in every analysis regardless of domain. These are symptoms of the LLM not
   grounding in specific performer context.

3. **Skip emotional/social jobs.** LLMs default to functional analysis because
   their training data has more functional content. Emotional and social jobs
   require explicit prompting and research grounding.

4. **Confuse the performer with the buyer.** Enterprise analyses routinely
   optimize for the buyer (IT procurement) instead of the performer (the
   actual user), producing products that get purchased but not adopted.

5. **List without prioritizing.** LLMs generate comprehensive lists but
   resist ranking, producing 20 equally-weighted pains instead of the
   crucial 3 that drive switching. Without prioritization, the output
   isn't actionable.

6. **Assume instead of admitting uncertainty.** LLMs fill in details
   confidently when the truth is "this needs research." A good JTBD analysis
   labels assumptions explicitly and flags what needs validation.

## Sources

This methodology synthesizes frameworks from:

- Anthony Ulwick, "Jobs to be Done: Theory to Practice" — ODI process,
  outcome statements, opportunity scoring, job map structure
- Clayton Christensen, "Competing Against Luck" — Jobs theory, milkshake
  story, hiring/firing metaphor, integration around jobs
- Jim Kalbach, "The Jobs to Be Done Playbook" — Practical templates, job
  stories, universal job map, outcome statement notation
- Bob Moesta, "Demand-Side Sales 101" — Four forces, buying timeline,
  switch interviews, demand-side thinking
- Alan Klement, "When Coffee and Kale Compete" — Jobs-as-Progress,
  system of progress, forces of progress, competitive framing
