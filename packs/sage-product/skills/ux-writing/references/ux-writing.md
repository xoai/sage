# UX Writing Methodology

## Purpose

Provides the structured methodology for UX writing — voice and tone design,
microcopy patterns, content-first design, and measuring effectiveness. Read
this before producing any UX writing deliverable. It covers what UX writing
is (and isn't), the process, and the common failure modes that LLMs produce
without methodological grounding.

## What UX Writing Is

UX writing is the process of creating the words in user interfaces: titles,
buttons, labels, instructions, descriptions, notifications, warnings, error
messages, empty states, confirmations, and controls. It also covers the setup
information, onboarding flows, and contextual guidance that helps users take
their next step with confidence.

Microcopy is a subset: the brief text that guides users through specific
interactions — button labels, form hints, error messages, tooltips. The
definition from Kinneret Yifrah: "The words or phrases in the user interface
that are directly related to the actions a user takes — the motivation before
the action, instructions that accompany the action, and feedback after the
user has taken the action."

**UX writing is NOT marketing copy.** Marketing copy persuades people to
consider a product. UX writing helps people USE the product. They serve
different goals, appear at different points in the journey, and follow
different rules. When UX copy tries to sell instead of guide, it creates
friction.

## Voice and Tone

### Voice: The Product's Personality

Voice is consistent — it's WHO the product is. It doesn't change between
screens or features. Podmajersky's framework: create a voice chart with
3-5 personality attributes, each defined on a spectrum.

Example voice attributes:
- Confident, not arrogant
- Friendly, not unprofessional
- Clear, not dumbed-down
- Encouraging, not pushy
- Calm, not cold

The voice chart becomes a decision-making tool: when writing any piece of
copy, check it against the voice attributes. "Does this sound confident
without being arrogant? Friendly without being unprofessional?"

### Tone: Voice Adapted to Context

Tone shifts based on the user's emotional state and the moment in the
journey. The same product voice sounds different when:

| Moment | Tone Shift | Example |
|--------|-----------|---------|
| Onboarding (excitement) | Warm, encouraging | "Let's get you set up — it takes about 2 minutes" |
| Error (frustration) | Calm, helpful, specific | "That password doesn't match. Try again or reset it" |
| Success (satisfaction) | Celebratory but brief | "Done! Your profile is ready" |
| Waiting (impatience) | Transparent, reassuring | "Uploading your photo — almost there" |
| Deletion (anxiety) | Serious, clear about consequences | "This will permanently delete your account and all data" |

Yifrah's principle: the MORE stressful the moment for the user, the MORE
careful and empathetic the tone should be. Error messages deserve more
attention than success messages because the user is already frustrated.

### Voice and Tone Guide as a Deliverable

A voice and tone guide includes:
1. **Brand personality attributes** (3-5, on spectrums)
2. **Voice principles** (3-5 rules the product always follows)
3. **Tone spectrum** with examples per emotional moment
4. **Word list** — preferred terms vs avoided terms
5. **Do/don't examples** for each microcopy pattern

This is a living document stored in `.sage/docs/` — it informs all
future UX writing and development work.

## Microcopy Patterns

### The 11 Core Patterns (from Podmajersky)

Each pattern has a specific purpose in the interface. Knowing the pattern
tells you what the copy needs to accomplish:

**1. Titles** — Orient the user. "Where am I?" Answer it in 2-5 words.
Titles should be scannable and specific. "Settings" is better than "Your
Account Settings Page."

**2. Buttons and CTAs** — Tell the user what happens next. Use verb + object
format: "Save draft," "Send message," "Start free trial." Never "Submit"
or "Click here" — these tell the user what to do mechanically, not what
happens as a result.

**3. Descriptions** — Explain what something is or does. Keep under 2
sentences. Front-load the value: what does the user gain?

**4. Empty states** — The first impression of a feature with no data.
Three elements: what this area is for, why it's empty, what to do next.
"No messages yet. When someone contacts you, their messages appear here.
Start a conversation →"

**5. Labels** — Name things clearly. Use the user's language, not the
system's. "Email" not "Electronic mail address." "Password" not "Credential."
One entity = one term, everywhere. If it's called "project" on one screen,
don't call it "workspace" on another.

**6. Controls** — Toggles, checkboxes, radio buttons. The label should
describe the STATE, not the action: "Show notifications" (toggle on = show,
off = hide). Not "Toggle notifications on/off."

**7. Text input fields** — Placeholder text and helper text. Placeholders
show format ("jane@example.com"). Helper text explains requirements
("Must be at least 8 characters"). Never use placeholder as the only label
— it disappears when the user starts typing.

**8. Transitional text** — Loading states, progress indicators, waiting
screens. Tell the user what's happening and how long it might take.
"Saving your changes..." is better than a spinner with no text. For longer
waits, use progress messaging: "Uploading photo (2 of 5)..."

**9. Confirmation messages** — Reassure after an action. Confirm what
happened and what comes next. "Your order is placed. You'll receive a
confirmation email within 5 minutes." Not just "Success!" — that tells the
user nothing about what succeeded or what to expect.

**10. Notifications** — Time-sensitive, contextual. Must earn attention.
Three parts: what happened, why it matters, what to do. "Your trial ends
in 3 days. Upgrade to keep your data →"

**11. Error messages** — The most critical microcopy. Three rules:
- Say what happened (in human terms, not error codes)
- Say why (if the user can understand the cause)
- Say how to fix it (the next action)

"Your password must be at least 8 characters" is better than "Invalid
password." "We couldn't reach the server — check your internet connection
and try again" is better than "Error 500."

### The Editing Process (Podmajersky's Four Phases)

After writing any piece of copy, edit in four passes:

1. **Purposeful:** Does this copy help the user accomplish their goal? If
   not, cut it. Every word must earn its place.
2. **Concise:** Can this be shorter without losing meaning? Remove filler
   words, hedging, and redundancy. "In order to" → "To." "Please note
   that" → (delete).
3. **Conversational:** Does this sound like a person talking? Read it aloud.
   If you'd never say it in conversation, rewrite it.
4. **Clear:** Will the user understand this on first read? Test with someone
   unfamiliar with the product. If they hesitate, rewrite.

## Content-First Design

Podmajersky's insight: write the conversation BEFORE designing the screen.
The interface is a dialogue between the product and the user:

- Titles, body text, and tooltips are the product's "phrases"
- Buttons, input fields, and controls are the user's "phrases"

Process:
1. Role-play the conversation: product asks → user responds → product
   confirms or helps
2. Write out the full conversation in plain text
3. Map each conversational turn to a UI element
4. Design the screen around the content, not the other way around

This prevents the common anti-pattern: designing a beautiful layout, then
cramming words into whatever space is left. Content-first means the words
inform the design, not accommodate it.

## Measuring UX Writing Effectiveness

### Direct Measurement

- **Task completion rate:** Can users finish the task with this copy?
- **Error rate on forms:** How many users make mistakes? Reduce with
  better helper text and error messages.
- **Time to completion:** How long does the flow take? Clearer copy
  reduces hesitation.
- **Support ticket volume:** Are users confused by something the UI
  should explain? Each ticket is a failed microcopy opportunity.

### Content Heuristics (Podmajersky's Framework)

Evaluate existing copy against these criteria:

| Heuristic | Question |
|-----------|----------|
| Purposeful | Does this text help the user achieve their goal? |
| Concise | Could this be shorter without losing meaning? |
| Conversational | Does this sound human? |
| Clear | Will a first-time user understand this immediately? |
| Useful | Does this provide information the user needs right now? |
| Consistent | Does this use the same terms as the rest of the product? |
| On-brand | Does this sound like the product's voice? |
| Accessible | Can a screen reader make sense of this? |

### Content Research (from Jorgensen)

Test copy with users using:
- **5-second tests:** Show a screen for 5 seconds. Ask what they remember.
  If they can't recall the main message, it's not clear enough.
- **Cloze tests:** Remove key words from copy. Can users fill in the blanks?
  If they guess differently from what you wrote, your terms don't match
  their mental model.
- **A/B testing:** Test two versions of the same copy. Measure completion
  rates, not preferences — what users say they prefer often differs from
  what performs better.

## LLM Failure Modes

### 1. Corporate Voice Default

**What happens:** The LLM produces copy that sounds like a press release:
"We are pleased to present our innovative solution for..." Users don't talk
like this. Products shouldn't either.

**Fix:** The voice chart acts as a constraint. "Does this sound [voice
attribute]?" If the copy sounds like it came from a corporate communications
department, rewrite it. The product speaks TO the user, not AT them.

### 2. Over-Friendly / Quirky Everywhere

**What happens:** The LLM makes every interaction playful: "Oopsie! Looks
like something went wrong 🙈." This is tone-deaf when the user just lost
their data or can't complete a payment.

**Fix:** The tone spectrum (from voice and tone guide) specifies where
playfulness is appropriate and where it's not. Error states, destructive
actions, and payment flows should be serious and clear. Save personality
for low-stakes moments: onboarding, empty states, success confirmations.

### 3. Verbose Microcopy

**What happens:** The LLM writes paragraphs where 5 words would do.
"In order to proceed with your account creation process, please click on
the button labeled 'Continue' below." → "Continue" (the button itself).

**Fix:** Apply the conciseness edit: can this be shorter? Most microcopy
should be under 20 words. Button labels should be 1-4 words. Error messages
should be 1-2 sentences max.

### 4. Generic Instead of Specific

**What happens:** "Something went wrong" instead of "Your file is too large
(max 5MB). Try a smaller image." The generic message doesn't help the user
fix the problem.

**Fix:** Every error message must answer three questions: what happened,
why, and how to fix it. If the LLM can't determine the specific cause,
it should produce a template with placeholders: "Your [item] couldn't be
[action] because [reason]. Try [fix]."

### 5. Inconsistent Terminology

**What happens:** The same thing is called "workspace" on one screen,
"project" on another, and "dashboard" on a third. Users lose confidence
when the product can't decide what things are called.

**Fix:** The voice and tone guide includes a word list — the canonical
name for every concept in the product. One entity = one term, everywhere.

### 6. Ignoring the Emotional Context

**What happens:** The LLM produces the same neutral tone for a welcome
screen and a data deletion confirmation. "Your account will be deleted"
sounds the same as "Your profile is ready."

**Fix:** The tone spectrum maps emotional contexts to tone adjustments.
The LLM should be instructed to identify the user's likely emotional state
at each point and adjust accordingly.

### 7. Marketing Language in the UI

**What happens:** "Unlock the power of AI-driven insights!" on a dashboard
title. The user already bought the product — they don't need to be sold on
it. They need to use it.

**Fix:** Marketing copy belongs on the landing page and in ads. UX copy
belongs inside the product. The rule: if the user is already logged in,
stop selling and start helping.

## Sources

- Microcopy: The Complete Guide — Kinneret Yifrah
- Strategic Writing for UX — Torrey Podmajersky
- The Business of UX Writing — Yael Ben-David
- Strategic Content Design — Erica Jorgensen
- NN/g: UX Copy Sizes (Long, Short, and Micro)
- Smashing Magazine: How to Improve Your Microcopy
