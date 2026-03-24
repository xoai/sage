---
name: ux-writing
description: >
  Produces UX writing deliverables: voice and tone guides, microcopy for
  specific features, and content audits of existing product copy. Use when
  the user needs to define a product's voice, write interface copy for a
  feature, audit existing microcopy quality, or establish UX writing
  guidelines. Also triggers when the user says "write the button labels,"
  "what should the error message say," "create a voice and tone guide,"
  "audit the product copy," "write microcopy for this flow," or "the copy
  doesn't sound right." Do NOT use for marketing copy, blog posts, landing
  page content, or email campaigns — those are marketing writing, not UX
  writing.
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [ux-design, writing, microcopy, voice-tone, content, copy]
inputs: [feature-context, brand-context]
outputs: [voice-tone-guide, microcopy-set, content-audit]
requires: []
-->

# UX Writing

Create the words that help users accomplish their goals inside the product.
UX writing is about clarity, not cleverness — every word earns its place by
reducing friction, building confidence, or guiding the next action.

**Deliverable type:** document (voice and tone guide, microcopy set) or
mixed (microcopy embedded in implementation tasks alongside code)

## Mode Behaviors

**FIX (update):** Revise specific microcopy — rewrite an error message,
fix inconsistent terminology, adjust tone for a specific screen. Don't
redesign the voice. Minutes.

**BUILD (standard):** Produce microcopy for a specific feature or flow.
Write all interface text (titles, buttons, labels, errors, empty states,
confirmations) following the voice and tone guide. If no guide exists,
establish key voice principles before writing. 15-30 minutes.

**ARCHITECT (full):** Complete voice and tone guide for the product, plus
microcopy for the target feature. Includes brand personality analysis,
voice chart with spectrum attributes, tone mapping across emotional
contexts, word list, do/don't examples for all 11 microcopy patterns, and
content heuristic evaluation of existing copy. 45-60 minutes.

## When to Use

- A new product needs its voice defined before any interface copy is written
- A feature is being built and needs all its interface text written
- Existing product copy is inconsistent, unclear, or off-brand
- The development team needs guidelines for writing copy themselves
- A PRD or spec describes user-facing behavior but doesn't specify the words
- Someone says "the copy feels wrong" or "what should this button say?"

## Prerequisites

The skill works with whatever context is available:

- **Product context** — what the product does, who it serves, what it values.
  If a JTBD analysis exists, it provides the language of the user's world.
- **Brand guidelines** — if visual brand guidelines exist, the voice should
  complement them. If not, the voice guide establishes verbal identity
  alongside (or ahead of) visual identity.
- **Existing copy** — if the product already has interface text, reviewing it
  reveals the current (often implicit) voice and its inconsistencies.
- **Voice and tone guide** — if one exists (in `.sage/docs/` or
  elsewhere), load it. All microcopy should follow it. If none exists,
  creating one is the first step.

## Process

### Step 0: Understand the Context

Confirm with the user in ONE message:

1. **What's the deliverable?** Voice and tone guide? Microcopy for a specific
   feature/flow? Content audit of existing copy? All three?
2. **Does a voice and tone guide exist?** If yes, load it. If no, we need
   to establish voice principles first (even in BUILD mode, this takes 5
   minutes and prevents inconsistency).
3. **Who are the users?** The user's language should shape the product's
   language. If a JTBD analysis exists, the job performer definition and
   emotional jobs provide the foundation.
4. **What's the emotional context?** Where in the journey does this copy
   appear? Onboarding (excited, uncertain)? Error recovery (frustrated)?
   Daily use (efficient, habitual)? The emotional context determines tone.

### Step 1: Establish Voice (ARCHITECT) or Confirm Voice (BUILD)

**Read first:** `references/ux-writing.md` (Voice and Tone section)

**ARCHITECT mode — full voice and tone guide:**

1. **Brand personality analysis.** What 3-5 personality attributes describe
   how this product should feel? Define each on a spectrum:
   "Confident, not arrogant." "Friendly, not unprofessional."

2. **Voice principles.** 3-5 rules the product always follows. These are
   the non-negotiable guidelines that every piece of copy must satisfy.
   Example: "We explain, we don't lecture." "We celebrate with the user,
   we never gloat."

3. **Tone spectrum.** Map emotional moments to tone adjustments: onboarding,
   errors, success, waiting, destructive actions, empty states. For each,
   show a do/don't example.

4. **Word list.** Canonical terms for every key concept in the product.
   One entity = one term, everywhere. Include both the preferred term and
   the terms to avoid (with reasons).

5. **Do/don't examples.** For each of the 11 microcopy patterns (titles,
   buttons, descriptions, empty states, labels, controls, text inputs,
   transitional text, confirmations, notifications, errors), show one
   good and one bad example in the product's voice.

Save the voice and tone guide to `.sage/docs/ux-writing-voice-and-tone.md`.
This becomes a cross-cutting reference for all future work.

**BUILD mode — confirm or establish minimal voice:**

If a voice and tone guide exists, load it and confirm it applies.
If not, establish three things in 5 minutes:
- 3 voice attributes (on spectrums)
- 3 key terms (the most important concepts in the product)
- 1 guiding principle ("We sound like [X], not like [Y]")

This minimal voice direction is enough to write consistent microcopy for
one feature. It can be expanded to a full guide later.

### Step 2: Identify All Copy Touchpoints

For the target feature or flow, list every place where text appears:

- Page/screen titles
- Section headings
- Button labels and CTAs
- Form field labels, placeholders, and helper text
- Error messages (one per error condition)
- Success/confirmation messages
- Empty states (no data yet)
- Loading/transitional text
- Tooltips and contextual help
- Notifications (if applicable)

Map each touchpoint to the user's emotional state at that moment.
A form field is neutral. An error after submitting the form is frustrated.
A success message is relieved/satisfied. This mapping determines the tone
for each piece of copy.

### Step 3: Write the Microcopy

**Read first:** `references/ux-writing.md` (Microcopy Patterns section)

For each touchpoint identified in Step 2:

1. **Write content-first.** Imagine the conversation between the product
   and the user. Write the product's "line" in plain language first, then
   refine it into UI text.

2. **Apply the voice.** Check against voice attributes: does this sound
   like the product? Adjust until it does.

3. **Apply the tone.** Check the emotional context: is this the right
   warmth/seriousness for this moment?

4. **Edit in four passes** (Podmajersky's process):
   - Purposeful: does this help the user?
   - Concise: can this be shorter?
   - Conversational: does this sound human?
   - Clear: will a first-time user understand this?

5. **Check accessibility.** Will a screen reader make sense of this?
   Are button labels descriptive enough without visual context? Is the
   reading level appropriate for the audience?

### Step 4: Quality Check

Before presenting, validate:

- [ ] Every piece of copy serves the user's goal, not the business's goal
- [ ] Button labels use verb + object format (not "Submit" or "Click here")
- [ ] Error messages answer three questions: what happened, why, how to fix
- [ ] Empty states explain what the area is for, why it's empty, what to do
- [ ] One entity = one term, everywhere (no "project"/"workspace" confusion)
- [ ] Tone matches the emotional context (serious for errors, warm for success)
- [ ] No marketing language inside the product ("Unlock the power of...")
- [ ] No placeholder text left unwritten ("Lorem ipsum," "[TODO]")
- [ ] Copy is concise — most microcopy under 20 words, buttons 1-4 words
- [ ] Copy passes the "read aloud" test — sounds like a person, not a robot
- [ ] Voice attributes are consistent across all touchpoints
- [ ] Accessibility: labels are descriptive, no reliance on color alone

## Output

**Voice and tone guide (ARCHITECT):**
Save to `.sage/docs/ux-writing-voice-and-tone.md`
This is a project-level reference used by all future work — developers
writing microcopy during implementation, designers creating mockups, PMs
writing PRD copy. Append to `.sage/decisions.md`.

**Microcopy set (BUILD or ARCHITECT):**
Save to `.sage/work/<YYYYMMDD>-<slug>/microcopy.md`
Organized by screen/flow, with all touchpoints covered.

**Content audit (ARCHITECT):**
Save to `.sage/docs/content-audit.md`
Evaluates existing copy against the content heuristics, identifies
inconsistencies and improvement priorities.

Present to user: "Here's the [deliverable]. The voice is [summary of voice
attributes]. Key decisions: [notable copy choices and reasoning]. Anything
that needs adjustment?"

## Rules

**MUST:**
- MUST read `references/ux-writing.md` before writing any copy
- MUST establish or confirm voice principles before writing microcopy —
  copy without voice direction produces inconsistency
- MUST write error messages that answer what/why/how-to-fix — never just
  "Error" or "Something went wrong"
- MUST use the user's language, not the system's — "Email" not "SMTP
  recipient address," "Save" not "Persist to database"
- MUST check the emotional context for every piece of copy — the same
  voice sounds different when a user is frustrated vs excited
- MUST use verb + object for buttons — "Send message" not "Submit"

**SHOULD:**
- SHOULD produce do/don't examples for each pattern to help developers
  write consistent copy in future implementation
- SHOULD include a word list of canonical terms
- SHOULD flag where existing copy contradicts the voice (content audit)
- SHOULD consider localization implications — copy that works in one
  language may not translate well (idioms, humor, cultural references)
- SHOULD write for scanning, not reading — front-load the key information

**MAY:**
- MAY produce a lightweight microcopy set in BUILD mode without a full
  voice and tone guide (minimal voice direction is sufficient)
- MAY recommend A/B tests for copy where effectiveness is uncertain
- MAY suggest illustration, animation, or visual treatment that complements
  the microcopy (empty states, onboarding, success moments)
- MAY produce copy in multiple languages if the product serves multilingual
  users (but note: translation is not the same as localization — culturally
  adapted copy is better than literal translation)

## Failure Modes

- **No voice direction exists and user wants to skip it:** Don't skip.
  Spend 5 minutes on minimal voice (3 attributes, 1 principle). Without
  voice direction, copy for buttons will sound different from copy for
  error messages, and the product will feel schizophrenic.

- **User wants marketing language in the UI:** Push back gently. "Inside
  the product, users need help, not persuasion. Marketing copy belongs on
  the landing page. Once someone is logged in, we stop selling and start
  guiding."

- **Copy is written without seeing the design:** UX writing works best
  with the design — copy length, placement, and hierarchy depend on the
  layout. If no design exists, write content-first (the conversation)
  and note that refinement may be needed when the design takes shape.

- **User wants "fun" copy everywhere:** The tone spectrum exists for this.
  Show where playfulness works (empty states, onboarding, success) and
  where it doesn't (errors, payments, destructive actions). "We're
  friendly overall, but we're serious when the user's data or money is
  at stake."

- **Too many stakeholders want input on copy:** This is the business
  problem Ben-David identifies. Copy-by-committee produces bland,
  safe, generic text. The voice and tone guide is the decision-making
  framework — it answers "which version is right?" by checking against
  the voice attributes, not by voting.
