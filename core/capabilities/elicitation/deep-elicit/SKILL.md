---
name: deep-elicit
description: >
  Comprehensive requirements elicitation through Socratic conversation,
  producing a product brief with problem, users, scope, and success criteria
  in ~10 minutes. Use when starting a new product, designing a system from
  scratch, planning a major redesign, or when the user says "I want to build",
  "new project", or "help me plan this product".
version: "1.0.0"
modes: [architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [elicitation, requirements, architecture, discovery]
inputs: [codebase-context-or-nothing]
outputs: [product-brief, personas, constraints]
-->

# Deep Elicit

Guide the human through comprehensive discovery of what they're building and why.
Not a form to fill — a conversation that surfaces the important decisions.

**Core Principle:** The most expensive bugs are requirements bugs. Spending 10 minutes
on elicitation saves days of rework. But spending 60 minutes loses the human's attention.
Be thorough AND efficient.

## When to Use

ARCHITECT mode, before architecture or planning. When:
- Building a new product or system from scratch
- Major platform redesign or migration
- The scope is large enough that getting the design wrong is costly

Do NOT use when:
- BUILD mode (use `quick-elicit` instead — faster, less thorough)
- The human has already written a detailed brief (accept it, validate it)

## Process

### Round 1: Problem Space (3 minutes)

Start with the WHY, not the WHAT. Ask:

1. **"What problem are you solving? Who has this problem?"**
   Get the core pain point and who feels it. "I want to build a task app" is not
   enough — "My team loses track of client deliverables across 5 projects" is better.

2. **"What happens if this problem isn't solved? What are people doing now?"**
   Understand urgency and current alternatives. This grounds the conversation
   in reality — are people using spreadsheets? A competitor? Nothing?

3. **"What does success look like in 3 months?"**
   Concrete, measurable. Not "users love it" but "50 active teams managing
   projects, 80% weekly retention."

Draft and show:
```
PROBLEM BRIEF:
  Problem: [specific pain point]
  Who: [target users — be specific]
  Current alternative: [what they do today]
  Success: [measurable 3-month goal]
```

"Does this capture the real problem? Anything to adjust?"

**Premise challenge (after Problem Brief is confirmed):**

Before moving to Round 2, surface 2-3 implicit premises in the user's
framing. Present as brief observations:

```
Before we scope this — I see a few assumptions worth examining:

1. [Premise]: [one sentence stating the assumption]
   → [one sentence describing why it might be wrong]

2. [Premise]: [one sentence stating the assumption]
   → [one sentence describing why it might be wrong]

3. [Premise]: [one sentence stating the assumption]
   → [one sentence describing why it might be wrong]

Do these hold, or should we adjust our framing?
```

deep-elicit can challenge 2-3 premises (vs. quick-elicit's 1-2) because
the architect workflow operates at higher stakes and the user expects a
more thorough examination.

**What counts as a premise:** The framing of the problem itself, the
assumed solution category, the assumed scope, the assumed user, the
assumed timeline. NOT technical choices — those come in Round 2/3.

**Record the framing decision** in the brief's Vision section and
prepend to `.sage/decisions.md`:

```
### YYYY-MM-DD — Framing: [initiative]
[Chose framing]. Pain: [pain]. Challenged: [premise names].
(deep-elicit Round 1)
```

### Round 2: Scope and Priorities (3 minutes)

Now narrow from problem to solution:

4. **"If you could only ship THREE features for launch, what are they?"**
   Forces ruthless prioritization. Everything else is post-launch.

5. **"What should this explicitly NOT do? What's tempting but out of scope?"**
   Boundaries prevent scope creep. "We won't build a mobile app for v1" is
   a useful constraint.

6. **"Are there constraints I should know? Budget, timeline, team size,
   compliance, existing systems to integrate with?"**
   Non-functional requirements surface here — security, performance, scale,
   accessibility, regulatory.

Draft and show:
```
SCOPE:
  Must have (launch): [3 features]
  Won't have (v1): [explicit exclusions]
  Constraints: [non-functional requirements]
```

### Round 3: Users and Flows (3 minutes)

7. **"Walk me through the most important user flow, step by step."**
   Get the happy path. "User signs up → creates a project → adds tasks →
   assigns to team → dashboard shows status." This becomes the architecture driver.

8. **"Who else uses this besides the primary user? (admin, viewer, API consumer?)"**
   Multiple user types = different permission models, different UI surfaces.

9. **"What's the most complex or risky part of this?"**
   The human usually knows where the dragons are. This is where architecture
   attention should focus.

Draft and show:
```
USERS:
  Primary: [who, what they do]
  Secondary: [other user types]

KEY FLOW:
  1. [step] → 2. [step] → 3. [step] → ...

HIGH RISK AREAS:
  - [identified complexity]
```

### Output: Product Brief

Combine all rounds into `.sage/work/<YYYYMMDD>-<slug>/brief.md`:

```markdown
# Product Brief: [name]

## Problem
[from Round 1]

## Users
[from Round 3]

## Success Criteria
[measurable, from Round 1]

## Scope
### Must Have (Launch)
[from Round 2]

### Won't Have (v1)
[from Round 2]

## Key User Flow
[from Round 3]

## Constraints
[from Round 2]

## High Risk Areas
[from Round 3]
```

Show the complete brief. Wait for approval.
"Here's the product brief. This is the foundation for architecture and planning.
Ready to proceed, or anything to adjust?"

## Rules

**MUST (violation = bad brief or lost trust):**
- MUST NOT ask more than 10 questions total across all rounds.
- MUST NOT ask yes/no questions — they produce shallow answers.
- MUST draft output after each round so the human can course-correct early.
- MUST make success criteria measurable — "users love it" → "80% weekly retention."

**SHOULD (violation = suboptimal elicitation):**
- SHOULD ask ONE follow-up for specificity if the human gives vague answers, then move on.
- SHOULD note technology opinions as constraints — don't argue during elicitation.
- SHOULD flag scope issues early: "This sounds like it could take months.
  Want to identify a smaller first version we can ship sooner?"

**MAY (context-dependent):**
- MAY compress to fewer rounds if the human has clearly thought deeply about the problem.
- MAY skip Round 3 (users/flows) if the product is a developer tool with a single user type.

## Failure Modes

- **Human wants to skip to coding:** "I understand the urgency. Let me ask 3 quick
  questions so we build the right thing. Takes 2 minutes." If they insist, respect it
  and switch to BUILD mode with quick-elicit.
- **Requirements are genuinely unclear:** That's OK. Note the unknowns explicitly
  in the brief. "TBD: authentication approach — depends on whether SSO is required."
  Better to acknowledge uncertainty than to guess.
- **Conflicting requirements surface:** Don't resolve them. Present: "These two
  requirements conflict: [X] and [Y]. Which takes priority?"
- **Scope is enormous:** Suggest phased delivery. "This is a 6-month project.
  Let's define Phase 1 (what ships in 4 weeks) and Phase 2 (what comes after)."
