# Interview Guide Patterns

## Purpose

Specific question patterns, sequences, and probing techniques for each
interview type. Use alongside `interview-methodology.md` when constructing
interview guides. The methodology reference covers when and why; this
reference covers the specific how.

## Discovery Interview Pattern

### Objective
Understand how people currently experience the problem space — their goals,
behaviors, frustrations, and workarounds.

### Question Sequence

**Context (warm-up, 5 min):**
1. "Tell me a bit about yourself and your [relevant context]."
   *Goal: establish rapport and understand background*

**Current behavior (core, 15-20 min):**
2. "Walk me through how you currently [main activity related to the job]."
   *Goal: understand the actual process, not the idealized version*
3. "When was the last time you did [activity]? Tell me what happened."
   *Goal: anchor to a specific recent instance for concrete detail*
4. "What tools or methods do you use for [activity]? How did you end up
   with those?"
   *Goal: understand the current solution landscape from the user's POV*
5. "What's the hardest part about [activity]?"
   *Goal: identify pain points*

**Emotional exploration (10 min):**
6. "How do you feel when [activity] goes well? What about when it doesn't?"
   *Goal: uncover emotional jobs*
7. "What would be different in your life if [activity] was effortless?"
   *Goal: understand the aspiration behind the job*

**Workarounds and adaptations (10 min):**
8. "Have you ever tried to change how you [activity]? What happened?"
   *Goal: understand past attempts and why they succeeded or failed*
9. "Is there anything you've started doing yourself to make [activity]
   easier? Any tricks or shortcuts?"
   *Goal: uncover compensatory behaviors — these are innovation signals*

**Closing:**
10. "If you could wave a magic wand and change one thing about how you
    [activity], what would it be?"
    *Goal: priority signal — what matters most*

### Key Probes
- "Tell me more about that."
- "You mentioned [X] — what did you mean by that?"
- "How did that make you feel?"
- "What happened next?"
- "Can you give me a specific example?"

## Switch Interview Pattern (Moesta Method)

### Objective
Understand the timeline and forces behind a recent behavior change —
starting or stopping use of a product/solution.

### The Timeline Framework

The interview reconstructs the switch timeline:
```
First Thought → Passive Looking → Active Looking → Decision → First Use → Ongoing
```

At each stage, uncover the four forces:
- **Push:** What was wrong with the old way?
- **Pull:** What attracted them to the new way?
- **Anxiety:** What worried them about switching?
- **Habit:** What kept them comfortable with the old way?

### Question Sequence

**Set the stage (5 min):**
1. "I'd like to understand how you came to [start/stop using X]. Can you
   take me back to the very beginning — what was going on in your life
   when you first thought about [changing]?"
   *Goal: find the "first thought" moment*

**Push forces (10 min):**
2. "Before you [switched], what was your situation like? What were you
   using?"
3. "What was frustrating about that? Was there a specific moment when
   you thought 'I need to find something better'?"
   *Goal: identify the push — the "struggling moment"*
4. "How long had you felt that way before you actually did something
   about it?"
   *Goal: understand the gap between dissatisfaction and action*

**Passive and active looking (10 min):**
5. "How did you first hear about [new solution]? What caught your
   attention?"
6. "Did you look at other options? What did you compare?"
7. "What made [new solution] stand out from the alternatives?"
   *Goal: understand the pull forces and evaluation criteria*

**Decision and anxiety (10 min):**
8. "Was there anything that almost stopped you from making the switch?
   Any concerns or hesitations?"
   *Goal: identify anxiety forces*
9. "What finally tipped you over the edge to actually [switch]?"
   *Goal: find the deciding factor*
10. "Was there anything you missed about the old way?"
    *Goal: identify habit forces*

**Aftermath (5 min):**
11. "Now that you've been [using new solution] for a while, how has it
    matched your expectations?"
12. "What surprised you — good or bad?"
    *Goal: understand post-switch reality vs expectations*

### Key Probes for Switch Interviews
- "Take me back to that moment — where were you? What were you doing?"
  (sensory detail anchors memory)
- "Who else was involved in the decision?"
- "What would have happened if you'd done nothing?"
- "When you say [vague term], what specifically do you mean?"

## Contextual Inquiry Pattern

### Objective
Observe how people actually perform a task in their real environment,
capturing behavior that they can't or don't articulate in interviews.

### Session Structure

**Setup (5 min):**
1. "I'd like to watch how you normally [activity]. Please do it exactly
   as you would if I weren't here. I'll take notes and might ask a few
   questions along the way, but don't change anything for my benefit."

**Observation (30-45 min):**
2. Observe silently. Note:
   - What they do (actions, sequence, tools used)
   - What they skip or ignore
   - Where they hesitate, backtrack, or express frustration
   - Environmental factors (interruptions, multitasking, noise)
   - Differences between what they said they'd do and what they actually do

3. Ask in-the-moment questions sparingly:
   - "I noticed you [action] — can you tell me what you were thinking?"
   - "You paused there — what was going through your mind?"
   - "You skipped [element] — was that deliberate?"
   *Goal: understand the reasoning behind observed behavior*

**Debrief (15-20 min):**
4. "That was really helpful. I noticed a few things I'd like to ask about."
5. Walk through your observations and ask for their perspective:
   - "I saw you [behavior]. Is that typical? Why do you do it that way?"
   - "You didn't use [feature]. Tell me about that."
   - "The step where you [workaround] — is there a reason you do it that
     way instead of [expected way]?"

### Observation Notes Template
```
Time | Action | Quote/Thought | Emotion | Friction? | Note
-----|--------|---------------|---------|-----------|-----
0:00 | Opened app | | Neutral | | Started from home screen
0:15 | Scrolled past widget | "I usually just check the total" | | Yes — didn't engage | Contradicts interview claim
0:30 | Tapped transaction | | Slight concern | | Checking specific purchase
```

## Evaluative Interview Pattern

### Objective
Get feedback on a specific concept or prototype before committing to build.

### Key Principles
- Show, don't tell. Let them interact with the concept before explaining it
- Ask about comprehension first, preference second
- One concept at a time. If comparing, randomize the order
- Prototype fidelity should match the question: low-fi for concepts,
  high-fi for usability

### Question Sequence

**Before showing concept (5 min):**
1. "Before I show you anything, tell me about how you currently
   [relevant activity]."
   *Goal: establish baseline expectations*
2. "If you could improve one thing about that experience, what would it be?"
   *Goal: prime them to think about needs, not features*

**First impression (5 min):**
3. Show concept/prototype. Then: "What's your first reaction? What do you
   think this is?"
   *Goal: test comprehension without explanation*
4. "What do you think you can do with this?"
   *Goal: does the concept communicate its purpose?*

**Guided exploration (15-20 min):**
5. "Try to [task that the concept supports]. Think aloud as you go."
   *Goal: observe how they interact, where they get stuck*
6. "What did you expect to happen when you [action]?"
   *Goal: identify expectation mismatches*
7. "Was anything confusing or unclear?"
   *Goal: surface comprehension issues*

**Value assessment (10 min):**
8. "How would this fit into how you currently [activity]?"
   *Goal: assess real-world relevance*
9. "What would need to be true for you to actually use this regularly?"
   *Goal: identify adoption barriers*
10. "What's missing? What would make this more useful?"
    *Goal: identify gaps*

**Closing:**
11. "On a scale of 1-5, how likely would you be to use this? Why that
    number?"
    *Goal: quantifiable signal, but the reasoning matters more than the
    number*

## Universal Probing Techniques

### The 5 Whys (Adapted)
Don't literally ask "why" five times — it becomes interrogative.
Instead, use varied probes that dig deeper:
1. "Tell me more about that."
2. "What made you feel that way?"
3. "Can you give me a specific example?"
4. "What were you hoping would happen?"
5. "What would have made it better?"

### Silence
After a participant answers, wait 3-5 seconds before responding. People
often fill silence with additional, more honest detail. This is the most
underused and most powerful technique.

### Mirroring
Repeat the last 2-3 words they said, as a question.
Participant: "I stopped checking because it wasn't accurate."
You: "Wasn't accurate?"
Participant: "Yeah, it categorized my coffee as 'entertainment'..."
This keeps them talking without introducing your framing.

### Contrast Questions
"You mentioned you [do X]. Can you think of a time when you didn't?
What was different?"
Contrasts reveal the conditions that trigger or prevent behavior.
