# Interview Methodology

## Purpose

Provides the structured methodology for planning and designing qualitative
user interviews. Covers interview types, when to use each, participant
selection, sample sizing, bias avoidance, and synthesis approaches. Read
this before designing any interview research.

## Interview Types and When to Use Each

### Discovery Interview

**Purpose:** Understand how people currently experience a problem space.
Broad exploration — you don't know what you don't know yet.

**When to use:**
- Early in the product cycle when the problem space is poorly understood
- When entering a new market or segment
- When JTBD analysis needs grounding in real stories
- When you have hypotheses but no qualitative evidence

**What it produces:** Stories about how people experience the problem today,
workarounds they use, emotional responses, unmet needs you didn't anticipate.

**Duration:** 45-60 minutes

### Switch Interview (Moesta Method)

**Purpose:** Understand why someone recently changed their behavior — started
using a new product, stopped using an old one, or changed how they solve a
problem. Uncovers the four forces of progress.

**When to use:**
- When you need to understand what triggers adoption or abandonment
- When JTBD hypotheses about switching forces need validation
- When designing messaging or onboarding
- When understanding competitive dynamics from the user's perspective

**What it produces:** The "timeline" of the switch — first thought, passive
looking, active looking, decision, first use, ongoing use. The four forces:
push (problems with current solution), pull (attraction to new solution),
anxiety (fears about switching), habit (comfort with current solution).

**Duration:** 30-45 minutes

### Contextual Inquiry

**Purpose:** Observe how people actually use a product or perform a task in
their real environment. What they do often differs from what they say they do.

**When to use:**
- When you need to understand the actual workflow, not the reported workflow
- When friction points are suspected but not identified
- When designing for a specific context (mobile, noisy environment, multitasking)
- When current product data shows unexpected behavior patterns

**What it produces:** Observed behaviors, workarounds, pain points that users
don't articulate (because they've normalized them), environmental factors that
affect usage.

**Duration:** 60-90 minutes (includes observation + debrief)

### Evaluative Interview (Concept/Prototype Testing)

**Purpose:** Get feedback on a specific solution direction — concept, prototype,
mockup — before committing to build it.

**When to use:**
- When opportunity map identifies a "pursue" item and you need to validate
  the solution direction before writing a PRD
- When you have 2-3 solution approaches and need signal on which resonates
- When a shipped feature isn't performing as expected

**What it produces:** Reactions to specific concepts, comprehension issues,
preference signals, unintended interpretations, feature-level feedback.

**Duration:** 30-45 minutes

## Participant Selection

### Who to Interview

The right participants depend on the interview type:

| Interview Type | Who to Recruit |
|---|---|
| Discovery | People who experience the problem, whether or not they use your product |
| Switch | People who recently (within 3 months) changed their behavior — started using your product, stopped using it, or switched from a competitor |
| Contextual inquiry | Current users in their real environment, ideally with varying usage levels |
| Evaluative | People from your target segment who haven't seen the concept before |

### Screener Design

A screener is a short questionnaire that filters participants. Good screeners:

- **Screen for behavior, not opinion.** "How many times did you check your
  spending last month?" (behavior) vs "Do you care about managing expenses?"
  (opinion — everyone says yes)
- **Include disqualification criteria.** People in the industry, friends/family
  of the team, professional research participants, people who don't match
  the target segment
- **Use a "dummy" question.** Include one option that no real target user would
  choose, to catch inattentive respondents
- **Keep it short.** 5-8 questions maximum. Long screeners attract people who
  are motivated by the incentive, not the topic

### Sample Size

Qualitative research doesn't need statistical significance — it needs
thematic saturation (when new interviews stop revealing new themes).

**General guidelines:**
- Discovery interviews: 8-12 participants. Saturation typically occurs
  around 8-10 for a well-defined segment
- Switch interviews: 8-12 participants (Moesta's recommendation). Need
  enough to see patterns in the forces
- Contextual inquiry: 5-8 participants. Observation produces denser data
  per session
- Evaluative interviews: 5-8 participants per concept. Nielsen's research
  shows ~5 users find ~80% of usability issues

**When you need fewer:** Highly homogeneous segment, narrow topic, follow-up
to existing research

**When you need more:** Multiple segments to compare, broad topic, no prior
research, high-stakes decision

## Interview Flow Structure

Regardless of type, every interview follows a common structure:

### 1. Opening (5 minutes)
- Introduce yourself and the purpose (vague enough to avoid leading)
- Establish ground rules: no right answers, you're learning from them,
  they can skip any question
- Ask permission to record (if applicable)
- Start with an easy warm-up question (about them, not the topic)

### 2. Context Setting (5-10 minutes)
- Understand their background relevant to the topic
- Establish their current situation before diving into specifics
- Build rapport — this makes the rest of the interview more honest

### 3. Core Exploration (20-40 minutes)
- Type-specific questions (see interview guide patterns)
- Follow the participant's story, don't force your structure
- Probe with "tell me more about that" and "why" — not leading questions

### 4. Specific Probes (5-10 minutes)
- Questions about specific topics you need to cover
- Concept reactions (if evaluative)
- These come AFTER open exploration to avoid anchoring

### 5. Closing (5 minutes)
- "Is there anything I didn't ask about that you think is important?"
- "Who else should I talk to?" (snowball recruiting)
- Thank them, explain what happens next

## Bias Avoidance

### Interviewer Biases

| Bias | What Happens | How to Avoid |
|---|---|---|
| Confirmation bias | You hear what confirms your hypothesis | Write down your hypotheses BEFORE interviews. Actively look for disconfirming evidence |
| Leading questions | "Don't you think the dashboard is confusing?" | Ask open questions: "How did you feel about the dashboard?" |
| Anchoring | First interview shapes how you hear all subsequent ones | Synthesize after ALL interviews, not during. Take notes without interpreting |
| Social desirability | Participant says what they think you want to hear | Ask about past behavior, not future intentions. "What did you do?" not "Would you use this?" |
| Recency bias | Latest interviews disproportionately influence conclusions | Weight all interviews equally in synthesis. Use structured analysis |

### Question Biases

**Leading:** "How much did you like the new feature?" (assumes they liked it)
→ Fix: "What was your experience with the new feature?"

**Double-barreled:** "Was the app easy to use and helpful?" (two questions)
→ Fix: Ask separately

**Hypothetical:** "Would you use this if it had X?" (people can't predict
their future behavior)
→ Fix: "Tell me about a time when you needed X"

**Loaded:** "How do you cope with the terrible expense tracking tools?"
(assumes tools are terrible)
→ Fix: "How do you currently track your expenses?"

## Synthesis

### During Interviews (Notes)

- Capture quotes verbatim when possible (mark with quotation marks)
- Note behaviors and emotions separately from statements
- Flag surprises — anything that contradicts your assumptions
- Don't interpret during the interview — just capture

### After All Interviews (Analysis)

**Step 1: Extract observations.** Go through each interview and pull out
individual observations — one per sticky note or row. An observation is a
specific thing someone said, did, or felt. Not your interpretation.

**Step 2: Cluster.** Group observations that describe the same phenomenon.
The groups become your themes. Let the themes emerge from the data — don't
start with predetermined categories.

**Step 3: Name themes.** Each cluster gets a name that captures the insight,
not just the topic. "Users check spending after emotional triggers" is an
insight. "Spending" is a topic.

**Step 4: Quantify within qualitative.** Count how many participants
exhibited each theme. "7 of 10 participants described checking spending
after an emotional trigger" is more useful than "many participants."

**Step 5: Identify implications.** For each theme, ask: "So what? What
does this mean for our product decisions?" Connect themes back to the
JTBD outcomes or opportunity map that motivated the research.

## LLM Failure Modes

### 1. Generic Questions

**What happens:** The LLM produces questions like "What do you like about
our product?" or "How could we improve?" — questions any intern could write.

**Root cause:** Without methodology grounding, LLMs default to the most
common interview questions from their training data.

**Fix:** Every question must connect to a specific research objective. The
interview guide should list the objective next to each question block:
"Objective: Understand the trigger for checking spending → Questions 4-6."

### 2. Too Many Questions

**What happens:** The guide has 30+ questions, making the interview feel
like an interrogation and leaving no time for follow-up.

**Root cause:** LLMs are thorough by default. They generate questions for
every possible angle without considering time constraints.

**Fix:** Limit core questions to 8-12. The rest of the time is for
follow-up probes that emerge naturally from the participant's answers.

### 3. Missing the Story Arc

**What happens:** Questions jump between topics without building a narrative.
The participant never gets into a storytelling flow.

**Root cause:** LLMs generate questions as independent items, not as a
conversation flow.

**Fix:** Structure the guide as a journey: past → present → future, or
trigger → action → outcome. Each section flows naturally into the next.

### 4. Asking About Future Behavior

**What happens:** "Would you use a feature that shows your spending
threshold?" — people cannot reliably predict their future behavior.

**Root cause:** It's the most natural way to ask about a concept. But
research consistently shows stated intent doesn't predict behavior.

**Fix:** Ask about past behavior and current workarounds. "Tell me about
a time when you felt you were spending too much in a category. What did
you do?" The past behavior reveals the need without hypothetical bias.

### 5. No Analysis Framework

**What happens:** The guide covers what to ask but not how to make sense
of the answers. The PM conducts great interviews but then stares at 10
pages of notes with no systematic way to extract insights.

**Root cause:** LLMs focus on the interview itself, not the end-to-end
research process.

**Fix:** The deliverable must include the analysis framework — not just
the guide. What themes to look for, how to cluster observations, how to
connect findings back to the original research questions.
