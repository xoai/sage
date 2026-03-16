# Formulation Rules and Quality Checks

## Purpose

Precise rules for writing job statements, desired outcome statements, and
pains/gains. Use as a checklist during and after analysis to catch common
quality issues.

## Job Statement Rules

Format: **verb + object + contextual clarifier**

Good: "Coordinate work across a cross-functional team to deliver a project on time"
Bad: "Use Jira to manage tasks" (contains solution)

### Validation Checklist

- [ ] Starts with an action verb (not "help me..." or "be able to...")
- [ ] Solution-agnostic — no product names, no technology references
- [ ] Stable over time — would make sense 20 years ago and 20 years from now
- [ ] Has a clear "done" state — you can tell when the job is finished
- [ ] Contains no adjectives that are actually needs ("quickly," "easily," "accurately")
- [ ] Atomic — one job per statement (no AND/OR compounds)

### Abstraction Levels

| Too Broad (aspiration) | Right Level (big job) | Too Narrow (micro-job) |
|---|---|---|
| "Be financially secure" | "Plan long-term retirement savings" | "Enter a number into a cell" |
| "Be a better professional" | "Develop expertise in a new domain" | "Click the enroll button" |
| "Run a successful business" | "Manage monthly expenses to maintain profitability" | "Categorize a receipt" |

Navigate with: "Why?" moves up in abstraction. "How?" moves down.
Match level to your goal: Strategy → big job. Feature → little job. UX → micro-job.

## Desired Outcome Statement Rules

Format: **direction + measure + object + clarifier**

Based on Ulwick's ODI framework as documented by Kalbach.

### The Four Elements

**Direction:** How does the performer want to change conditions? Verbs:
minimize, maximize, reduce, increase, decrease, lower, raise.

**Measure:** What is the unit of success? Common measures: time, likelihood,
ability, number, effort, frequency, accuracy, risk. May be subjective but
should be as concrete as possible.

**Object:** What is being affected? The thing under control that will change
when the job is done better.

**Clarifier:** What additional context is needed? Describes the circumstance
or condition in which the outcome matters.

### Examples

| Direction | Measure | Object | Clarifier |
|---|---|---|---|
| Minimize | the time it takes | to identify a blocked task | across distributed team members |
| Increase | the likelihood | of getting permission | from a boss to attend |
| Reduce | the effort required | to summarize conference insights | for sharing with colleagues |
| Maximize | the ability | to remember relevant content | from conference presentations |
| Minimize | the likelihood | of discovering a risk | after it causes a delay |

### Validation Checklist

- [ ] Starts with a direction word (minimize, maximize, reduce, increase)
- [ ] Contains a measurable unit (time, likelihood, ability, effort, frequency)
- [ ] Solution-agnostic — no tools, features, or technologies mentioned
- [ ] Atomic — one concept per statement (split any AND/OR)
- [ ] Includes contextual clarifier for specificity
- [ ] Attached to a specific job map stage

### Common Mistakes

| Bad | Issue | Good |
|---|---|---|
| "Make reports faster" | Vague, no structure | "Minimize the time it takes to generate an accurate status report" |
| "Better collaboration" | Not measurable | "Increase the likelihood that all team members have current project context" |
| "Use AI to predict risks" | Contains solution | "Minimize the likelihood of discovering a risk after it causes a delay" |
| "Reduce cost and improve quality" | Compound | Split into two separate statements |
| "Easily manage tasks" | Adverb is a need, not a format | "Minimize the effort required to update task status" |

## Pain/Gain Validation

### Pains — Quality Criteria

- [ ] **Specific:** "Team updates status in 3 different tools" — not "tools are bad"
- [ ] **Grounded in behavior:** Describes what happens, not abstract opinion
- [ ] **Includes consequence:** Why it matters — the time/money/effort cost
- [ ] **Not a disguised solution:** "We need a dashboard" is a solution. "Can't
      see cross-project status without opening 4 tools" is a pain.
- [ ] **Quantified where possible:** "3 hours/week" rather than "a lot of time"

### Gains — Quality Criteria

- [ ] **Measurable or observable:** "Complete the task in under 3 clicks" — not "better UX"
- [ ] **Tied to the job:** "Identifies at-risk items before delays" — not "has AI"
- [ ] **Differentiated:** Would this distinguish one solution from another?
- [ ] **Realistic:** Achievable with current technology and constraints

## Overall Analysis Checklist

Run this after completing any JTBD analysis:

- [ ] Job performer defined and distinguished from buyer
- [ ] Main job follows verb + object + clarifier, no embedded solutions
- [ ] Emotional and social jobs captured separately from functional
- [ ] Circumstances provide specific context (when, where, constraints)
- [ ] Current solutions documented including workarounds and "doing nothing"
- [ ] Job map covers all relevant stages with friction points identified
- [ ] Pains grounded in research or explicitly flagged as assumptions
- [ ] Gains specific enough that a product team could verify them
- [ ] No statement confuses a job with a solution
- [ ] Needs prioritized by intensity, not just listed
- [ ] Different performer segments considered
- [ ] Output labeled as "validated" or "hypothesized — needs validation"
