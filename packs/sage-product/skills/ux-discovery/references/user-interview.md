---
name: user-interview
description: >
  Designs complete user interview research packages: research brief, screener,
  interview guide, and analysis framework. Supports discovery interviews,
  switch interviews, contextual inquiry, and evaluative interviews. Use when
  the user needs to validate JTBD hypotheses, test a concept with users,
  understand switching behavior, or observe how users interact with a product.
  Also triggers when the user says "I need to talk to users," "help me plan
  user interviews," "write an interview guide," "I need to validate this
  assumption," or "design a research study." Do NOT use for quantitative
  research (surveys, A/B tests) or for conducting the research itself.
version: "1.1.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [product-management, research, interview, qualitative, planning, validation]
inputs: [research-need]
outputs: [research-brief]
requires: []
-->

# User Interview Design

Design complete interview research packages that help PMs learn what they
need to learn, efficiently and without bias. The skill plans the research
and provides supporting materials — the PM conducts the interviews.

**Deliverable type:** document

## Mode Behaviors

**FIX (update):** Adjust an existing research brief or interview guide —
add/remove questions based on pilot interview feedback, update screener
criteria after recruitment difficulty, revise analysis framework after
early findings. Don't redesign the study. Minutes.

**BUILD (light):** Quick guide for rapid validation. One research objective,
5-8 core questions, basic screener (2-3 questions), simplified analysis
framework (themes to watch for + completion criteria). Skip detailed
logistics and the full synthesis template. Produces a guide the PM can
use for 3-5 quick interviews. 10-15 minutes.

**ARCHITECT (full):** Complete research package. Full brief with objectives
tied to upstream artifacts, detailed screener (4-6 questions), 8-12 core
questions with probes and section-to-objective mapping, full analysis
framework with synthesis template, logistics timeline, and follow-up study
recommendations. 30 minutes.

## When to Use

- JTBD analysis or opportunity map has low-confidence claims that need
  qualitative validation
- The team needs to understand user behavior before committing to a
  solution direction
- A concept or prototype needs user feedback before PRD
- Switching behavior or adoption/abandonment patterns need investigation
- The PM says "I need to talk to users" but isn't sure how to structure it

## Prerequisites

The skill works best with a clear research need. Accepted inputs:

- **Low-confidence claims from JTBD:** "The main job statement is hypothesized
  — validate with switch interviews"
- **Opportunity map decisions:** "Opportunity O2 is 'monitor' pending user
  validation — design the validation study"
- **PRD open questions:** "We don't know if users would accept AI-inferred
  spending thresholds — test the concept"
- **Direct research need:** "We're entering a new market and need to
  understand how people currently manage [X]"

If the user has no specific research need, help them identify one by
reviewing upstream artifacts for low-confidence claims or open questions.

## Process

### Step 0: Understand the Research Need

Confirm with the user in ONE message:

1. **What do you need to learn?** The specific questions this research
   should answer. Not "understand users better" — that's too vague.
   Push for specifics: "What decision will this research inform?"
2. **What do you already know?** Existing evidence — JTBD analysis,
   analytics, prior research, team assumptions. This prevents researching
   what's already known.
3. **Who are the users?** Target segment from JTBD or opportunity map.
   If no segment is defined, this needs to be established first.
4. **What's the context?** Is this pre-build validation? Post-ship
   evaluation? New market discovery? The context determines the
   interview type.

### Step 1: Select Interview Type

**Read first:** `references/interview-methodology.md` (Interview Types)

Based on the research need, recommend the appropriate type:

| Research Need | Interview Type |
|---|---|
| "We need to understand how people experience this problem" | Discovery interview |
| "We need to understand why users switched to/from our product" | Switch interview |
| "We need to see how users actually use the product" | Contextual inquiry |
| "We need feedback on this concept/prototype before building" | Evaluative interview |

If the need could be served by multiple types, recommend the one that
best answers the primary research question and explain the trade-off.

If the need is better served by quantitative research (survey, A/B test,
behavioral analytics), say so: "This question is better answered by
[quantitative method] because [reason]. The user-interview skill covers
qualitative methods. [Recommendation for next steps]."

### Step 2: Design the Research Brief

Define the study parameters:

**Research objectives:**
- Primary question (the ONE thing we must learn)
- Secondary questions (2-4 additional learning goals)
- Connection to upstream work (which JTBD claim, opportunity, or PRD
  question does this validate?)

**Participant criteria:**
- Who to recruit (behavior-based criteria, not demographics)
- Who to exclude (industry insiders, team connections, etc.)
- Sample size with rationale (typically 5-12 depending on type)

**Screener design:**
- 4-6 screening questions focused on behavior and recency
- Include one disqualification criterion for inattentive respondents
- Every question screens for something specific — no filler

### Step 3: Write the Interview Guide

**Read first:** `references/interview-guide-patterns.md`

Select the appropriate pattern for the chosen interview type and
customize it to the specific research objectives:

1. **Map research objectives to guide sections.** Each section of the
   guide should connect to a specific objective. If a section doesn't
   serve an objective, remove it.

2. **Write 8-12 core questions.** Not more. The rest of the time is for
   follow-up probes that emerge from the conversation. A guide with 25
   questions becomes an interrogation.

3. **Sequence questions as a conversation.** Start broad and open
   (context, current behavior), move to specific (pain points, decisions),
   end with reflection (what would they change, what did we miss).

4. **Write probes for each question.** Not a script — prompts for the
   interviewer when they need to dig deeper. "Tell me more about that,"
   "Can you give a specific example?"

5. **Include the opening and closing scripts.** The opening sets the tone
   (no right answers, learning from them). The closing captures what the
   guide missed ("anything I should have asked?").

### Step 4: Design the Analysis Framework

**Read first:** `references/interview-methodology.md` (Synthesis section)

Define how the PM will make sense of the interview data:

1. **Theme categories:** Based on research objectives, suggest 3-5
   theme categories to watch for. But emphasize: let themes emerge
   from the data, don't force observations into predetermined buckets.

2. **Synthesis process:** Step-by-step instructions for going from
   raw interview notes to actionable findings.

3. **Completion criteria:** How does the PM know when they've learned
   enough? Typically: primary question answered with evidence from
   ≥N participants, and thematic saturation reached (last 2 interviews
   added no new themes).

4. **Connection back to upstream:** How findings feed back into the
   JTBD analysis, opportunity map, or PRD. "If interviews confirm
   [hypothesis], update opportunity O2 from 'monitor' to 'pursue.'
   If they disconfirm it, update the JTBD outcome score."

### Step 5: Add Logistics

- Estimated timeline (recruitment through findings)
- Resources needed (recording setup, note-taker, incentive budget)
- Recruitment method recommendations

### Step 6: Quality Check

Before presenting, validate:

- [ ] Research objectives are specific enough to answer with interviews
- [ ] Interview type matches the research need
- [ ] Participant criteria are behavior-based, not demographic-based
- [ ] Screener is 4-6 questions with clear qualify/disqualify criteria
- [ ] Interview guide has 8-12 core questions, not more
- [ ] Questions are open-ended, not leading or hypothetical
- [ ] Guide follows a conversational arc (broad → specific → reflective)
- [ ] Every guide section connects to a research objective
- [ ] Analysis framework defines how to synthesize findings
- [ ] Completion criteria define "done" (what evidence, how many participants)
- [ ] Findings connect back to upstream artifacts (JTBD, opportunity map, PRD)

## Output

Save to `.sage/docs/research-brief-<slug>.md` using the
template from `templates/research-brief-template.md`.

Append key decisions to `.sage/decisions.md` recording the
research objectives, participant criteria, and what upstream claims this
study validates. Update the "Current Artifacts" section.

Present to user: "Here's the research brief for [study name]. It uses
[interview type] with [N] participants targeting [segment]. The primary
question is: '[question]'. The guide has [N] core questions covering
[sections]. Want to review the questions or adjust the scope?"

## Rules

**MUST:**
- MUST read `references/interview-methodology.md` and
  `references/interview-guide-patterns.md` before designing any study
- MUST connect the research need to a specific decision — "understand
  users better" is not a valid research objective
- MUST design screeners based on behavior, not demographics or opinions
- MUST limit core interview questions to 8-12 — more than that
  produces an interrogation, not a conversation
- MUST include an analysis framework — the guide without a synthesis
  plan produces interviews that go nowhere
- MUST write open-ended questions — no leading, no hypothetical,
  no double-barreled questions
- MUST define completion criteria — how does the PM know when they've
  learned enough?

**SHOULD:**
- SHOULD include probe suggestions for each core question
- SHOULD note which research objectives each guide section addresses
- SHOULD recommend a pilot interview (1 participant, not counted in
  sample) to test the guide before full recruitment
- SHOULD flag when quantitative methods would better serve the need
- SHOULD connect findings back to specific upstream claims or decisions

**MAY:**
- MAY produce a lightweight guide in BUILD mode (fewer questions,
  simpler brief) for quick validation studies
- MAY suggest recruitment channels based on the target segment
- MAY provide tips for conducting interviews (rapport building,
  note-taking, bias avoidance) as supplementary material
- MAY recommend combining interview types in one study (e.g., discovery
  interview with evaluative segment at the end) when appropriate

## Failure Modes

- **User has no specific research question:** Don't produce a generic
  study. Help the PM identify what they need to learn: "What decision
  are you trying to make? What's the biggest uncertainty?" If they still
  can't articulate it, recommend reviewing the JTBD or opportunity map
  for low-confidence claims.

- **Research question is better suited to quantitative methods:** If the
  PM needs "how many users do X" or "which of these two options performs
  better in production," interviews aren't the right tool. Flag it:
  "This question needs quantitative data — a survey (n≥100) or an A/B
  test would give you reliable numbers. Interviews tell you why, not
  how many."

- **Target segment is undefined:** If the PM can't describe who to
  interview beyond "our users," the segment definition is too vague.
  Recommend running the JTBD skill to define the job performer first,
  or at minimum establish behavioral criteria: "users who have done
  [specific behavior] in the last [timeframe]."

- **PM wants to test everything in one study:** A guide with 4 research
  objectives and 25 questions will produce shallow answers to everything
  and deep answers to nothing. Push for focus: "Which of these questions
  is the highest-stakes decision? Let's design the study around that one,
  and address the others in a follow-up."

- **Guide becomes an interrogation:** If the question count exceeds 12,
  the guide is too long. Cut by asking: "Which of these questions could
  be answered by the probes from other questions?" Often the answer to
  Q7 naturally emerges from the follow-up to Q4.
