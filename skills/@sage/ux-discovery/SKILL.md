---
name: ux-discovery
description: "User research and context gathering — understands who users are, what they do, and why"
version: "1.0.0"
modes: [build, architect]
category: elicitation
activation: auto
cost-tier: sonnet
playbook: ux-design
inputs: [codebase-scan-output]
outputs: [user-context-notes, persona-profiles, journey-maps]
---

# UX Discovery

Gathers user context to ground specifications in real user behavior rather than
developer assumptions. Runs alongside `quick-elicit` at the elicitation phase.

## Mode: BUILD (light)

Add these UX-focused questions to the elicitation, woven into the normal
`quick-elicit` flow. Don't extend the time — make the existing questions sharper.

**Ask about the user's context (pick 2-3 most relevant):**

1. "Who specifically uses this, and what's their state of mind when they arrive?"
   (Rushed? Anxious? Browsing? In the middle of another task?)
2. "What are they doing immediately before this feature? How do they get here?"
   (From a notification? Search? Navigation? Deep link?)
3. "What do they currently do to solve this problem?" (The existing workflow,
   including workarounds. Past behavior > hypothetical behavior.)
4. "What goes wrong? What's the most common failure or frustration?"

**Capture in the user-context-notes artifact:**
- Who: one sentence describing the primary user and their context
- Before: how they arrive at this feature
- After: where they go when done
- Pain: the current frustration this feature addresses

## Mode: ARCHITECT (full)

Run the complete UX discovery process. This is a structured investigation
that produces artifacts feeding directly into specification.

### Phase 1: Stakeholder Context (5 min)

Review what's known about the users from:
- Existing documentation, previous specs, analytics data
- The codebase-scan output (what patterns exist? what user flows already exist?)
- Stakeholder input ("who is this for and why now?")

### Phase 2: User Research Framing (10-15 min)

Apply The Mom Test principles to structure the inquiry:
- Frame questions about past behavior, not opinions
- Ask "When did you last...?" not "Would you ever...?"
- Look for concrete facts: what they did, what tools they used, what frustrated them
- If talking to real users isn't possible, use the best proxy: support tickets,
  analytics data, competitor reviews, forum posts

Produce: research findings summary

### Phase 3: Persona Development (10 min)

From the research, develop 2-3 behavioral personas:

```
[Name] — [Role]
"[Quote capturing their attitude]"

GOAL: What they're trying to accomplish
CONTEXT: When, where, on what device
PAIN: What frustrates them about current solutions
BEHAVIOR: How they approach problems
FREQUENCY: How often they do this
```

Designate one as the PRIMARY persona (design for this person first).
Optionally designate a NEGATIVE persona (explicitly NOT designing for).

Produce: persona-profiles artifact

### Phase 4: Journey Mapping (10-15 min)

Map the primary persona's full journey:

1. **Trigger:** What causes them to start this journey?
2. **Arrival:** How do they get to the feature? What do they expect?
3. **Core flow:** Step by step, what do they do?
4. **Decision points:** Where do they choose between options?
5. **Failure points:** Where can things go wrong? What happens?
6. **Completion:** What tells them they're done? Where do they go next?
7. **Emotional arc:** When are they confident? Confused? Frustrated? Relieved?

Produce: journey-map artifact

### Phase 5: Pain Point Inventory (5 min)

From the journey map, extract the top pain points ranked by severity:
- **Blockers:** User can't complete their goal
- **Friction:** User can complete but with unnecessary effort or confusion
- **Annoyance:** User notices something wrong but works around it

These feed directly into the specification as requirements and acceptance criteria.

## References

Load from `references/` as needed:
- `user-behavior-model.md` — How users actually behave (Krug, Norman)
- `user-research-conversations.md` — Mom Test rules for useful conversations
- `persona-development.md` — Persona construction framework
- `journey-mapping.md` — Journey mapping components and process
