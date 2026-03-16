# Common Pitfalls in JTBD Analysis

## Purpose

Mistakes that both human analysts and LLMs consistently make when conducting
JTBD analysis. Check this list during quality review (Step 5) to catch
problems before they reach stakeholders.

## Confusing Jobs with Solutions

**Symptom:** "Use Slack to communicate," "Build a dashboard," "Implement AI analytics."

**Root cause in LLMs:** Training data is dominated by product descriptions and
feature announcements. The LLM defaults to solution language because that's
what it's seen most.

**Fix:** Apply the "5 Whys." "I need Slack" → Why? → "To get quick answers" →
Why? → "To avoid project delays." The job is "get timely answers to unblock
work." Quick test: would this statement make sense 20 years ago?

## Generic Outcomes

**Symptom:** "Save time," "Improve efficiency," "Better collaboration" appear
in every analysis regardless of domain.

**Root cause in LLMs:** Without grounding in specific performer context, LLMs
generate plausible-sounding but undifferentiated outcomes. These are the JTBD
equivalent of lorem ipsum.

**Fix:** Every outcome must pass the specificity test: could this statement
appear in an analysis of a DIFFERENT product for DIFFERENT performers? If yes,
it's too generic. "Minimize the time it takes to identify a blocked task
across distributed team members" is specific. "Save time on project management"
is generic.

## Ignoring Emotional and Social Jobs

**Symptom:** Only functional tasks documented. Analysis reads like a process
map with no human dimension.

**Root cause in LLMs:** Training data contains far more functional content than
emotional or social content. LLMs skip these dimensions unless explicitly
prompted.

**Fix:** Always ask: "How would the performer feel if this job went perfectly?"
and "Who notices when this job goes well or badly?" Don't fabricate emotional
jobs — they must come from research or be flagged as assumptions.

## Fabricating Without Flagging

**Symptom:** Analysis reads as confidently validated but is built entirely
from internal assumptions.

**Root cause in LLMs:** LLMs present information with uniform confidence.
They don't naturally distinguish "I'm confident about this because the user
provided research data" from "I'm generating plausible content from training
data patterns."

**Fix:** Every analysis must state its evidence basis. If built from research,
cite the source (interviews, surveys, tickets). If built from assumptions,
label every section: "Hypothesized — needs validation." The quality check step
must explicitly verify evidence grounding.

## Treating All Pains as Equal

**Symptom:** 15-20 pains listed with no ranking or differentiation.

**Root cause in LLMs:** LLMs are trained on list-making, not prioritization.
Generating a comprehensive list feels complete; ranking requires judgment that
the LLM avoids.

**Fix:** Force ranking. Apply the forcing question: "If we solved only ONE
pain, which would most drive someone to switch from their current solution?"
For precision, use opportunity scoring on desired outcome statements.

## No Job Performer Defined

**Symptom:** Analysis discusses "users" without specifying who. Or conflates
the end user with the buyer.

**Root cause:** In LLM training data, "users" is the default term. The
distinction between performer, buyer, and approver is rarely made in the
blog posts and articles that dominate training data.

**Fix:** Name the performer by role and context before any analysis begins.
Then explicitly distinguish buyer and approver. If you design for the buyer's
needs but neglect the performer's, you get shelfware — purchased but not used.

## Missing Circumstances

**Symptom:** Jobs stated in a vacuum: "manage a project" with no context.

**Fix:** Identify 3-5 circumstances: time constraints, environment, available
resources, emotional state, who else is involved. Circumstances turn a generic
job into an actionable design target. "Manage a project" is a job. "Coordinate
a distributed team across 3 time zones during a deadline crunch" is a
designable problem.

## Wrong Abstraction Level

**Symptom:** Job is either an aspiration ("live a fulfilling life") or a UI
task ("click submit").

**Fix:** Match the level to your goal. Strategy decisions → big job. Feature
decisions → little job. UX decisions → micro-job. Navigate with "Why?" (up)
and "How?" (down).

## Troubleshooting

**"Everything looks correct but isn't useful."** Check specificity. Are pains
stated with numbers and consequences? Are circumstances specific enough to
constrain the solution space?

**"Too many jobs, can't focus."** Zoom out — group micro-jobs under a single
big job. Pick one based on strategic fit and unmet need intensity.

**"Stakeholders disagree on the main job."** Go back to the job performer.
Once you agree on WHO, the job usually clarifies.

**"Customer asks for features, not jobs."** Normal. For every feature request,
ask "What would that help you accomplish?" three times.

**"No budget for research."** Mine support tickets and NPS comments. Interview
internal customer-facing teams. Analyze competitor reviews. Label output as
hypothesized. See research-methods.md for proxy approaches.
