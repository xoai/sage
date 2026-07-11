---
name: ux-review
description: >
  Assess an existing UI three ways: reverse-engineer its design system from
  screenshots or a live URL (audit), benchmark it against category leaders
  (evaluate), and check it against usability heuristics (Nielsen, Norman, Krug).
  Merges the former ux-audit, ux-evaluate, and ux-heuristic-review skills.
version: "1.0.0"
type: process
tags: [ux, review, audit, evaluate, heuristics, assessment]
---

# UX Review

Three assessment modes. Pick by intent, or run in sequence (audit → evaluate →
heuristic review) for a full picture.

---

## Mode: Audit — reverse-engineer the current design system

Extract the implicit design system from an existing page. Before you can
improve a design, you need to understand what currently exists — not from
the code, but from what the user sees.

**Core Principle:** Every shipped product has a design system, even if it
was never documented. Colors were chosen. Typography was set. Spacing
patterns emerged. Component shapes repeated. This skill makes the implicit
explicit so the redesign can make intentional choices about what to keep,
what to change, and what to unify.

## When to Use

- Before a redesign task (runs BEFORE ux-discovery)
- When the user provides a URL and says "redesign this"
- When auditing an existing interface for consistency issues
- When onboarding to an unfamiliar codebase's design patterns

Do NOT use for:
- Greenfield projects (nothing to audit — skip to ux-discovery)
- API-only features (no visual output)

## Process

### Step 1: Capture Current State

If screenshots don't already exist, capture them:

```bash
bash sage/runtime/tools/sage-screenshot.sh <url-or-localhost> \
  --output .sage/work/<feature>/screenshots \
  --label current \
  --full-page \
  --before
```

If the user provided a URL, also fetch the page content for structural analysis:
- Page title, meta description
- Heading hierarchy (h1 → h2 → h3)
- Navigation structure
- Section count and ordering
- CTA placement and wording

### Step 2: Extract Color Palette

From the screenshots, identify:

```markdown
## Colors
Primary:    [color] — used for: [CTAs, links, active states]
Secondary:  [color] — used for: [headings, accents]
Background: [color(s)] — used for: [page bg, section bgs, card bgs]
Text:       [color(s)] — used for: [body, headings, muted/secondary]
Accent:     [color(s)] — used for: [badges, highlights, alerts]
Semantic:   success [color], error [color], warning [color]
```

Note inconsistencies: "Two different blues used for CTAs — #2563eb on hero,
#3b82f6 on cards. Likely unintentional."

### Step 3: Extract Typography

```markdown
## Typography
Heading 1:  [size estimate] / [weight] / [color]
Heading 2:  [size estimate] / [weight] / [color]
Heading 3:  [size estimate] / [weight] / [color]
Body:       [size estimate] / [weight] / [color] / [line-height estimate]
Caption:    [size estimate] / [weight] / [color]
Font family: [serif/sans-serif/identified family if recognizable]
```

Note: sizes are estimates from screenshots. Exact values come from code
inspection if needed. The point is to identify the visual hierarchy, not
the pixel values.

### Step 4: Extract Spacing and Layout

```markdown
## Layout
Max content width: [estimate]
Grid system:       [columns at desktop, tablet, mobile]
Section spacing:   [gap between major sections]
Card spacing:      [gap between cards/items]
Internal padding:  [padding inside cards/sections]

## Responsive
Mobile:  [what stacks, what hides, what changes]
Tablet:  [how grid adapts]
Desktop: [full layout description]
```

### Step 5: Extract Component Patterns

Identify repeating UI components:

```markdown
## Components
Buttons:     [styles: primary, secondary, ghost — shapes, sizes]
Cards:       [structure: image + title + desc + CTA? shadow? border-radius?]
Navigation:  [type: sticky header? hamburger on mobile? mega menu?]
Hero:        [pattern: text-left/image-right? full-width image? video?]
Social proof: [testimonials? logos? numbers? score displays?]
Forms:       [input style, label position, error display]
Icons:       [style: outlined? filled? library if recognizable?]
```

### Step 6: Extract Information Architecture

```markdown
## Page Sections (in order)
1. [Section name] — [purpose] — [above/below fold on mobile]
2. [Section name] — [purpose]
3. ...

## CTA Strategy
Primary CTA:   [text] — [placement] — [visual weight]
Secondary CTA: [text] — [placement]
CTA count:     [total on page]

## Navigation
Header:  [logo + nav items + CTA]
Footer:  [columns, links, contact info]
```

### Step 7: Produce Design System Document

Combine all extractions into `.sage/work/<feature>/current-design-system.md`:

```markdown
# Current Design System: [page/product name]

**Audited from:** [URL or screenshots]
**Date:** [timestamp]
**Breakpoints reviewed:** mobile, tablet, desktop

## Colors
[from Step 2]

## Typography
[from Step 3]

## Spacing and Layout
[from Step 4]

## Components
[from Step 5]

## Information Architecture
[from Step 6]

## Consistency Issues Found
- [inconsistency 1]
- [inconsistency 2]

## Strengths
- [what works well visually]

## Weaknesses
- [what could be improved]
```

Show the document to the user:
"Here's the current design system I extracted. Anything I missed or got wrong?"

## Rules

**MUST (violation = inaccurate audit):**
- MUST work from screenshots, not from memory or assumptions. If no screenshots
  exist, capture them first.
- MUST note inconsistencies explicitly. "Two shades of blue" is a finding, not
  something to gloss over.
- MUST separate facts (what IS there) from judgment (what SHOULD change).
  The audit is descriptive. The evaluation skill handles prescriptive.

**SHOULD (violation = incomplete audit):**
- SHOULD check all three breakpoints (mobile, tablet, desktop).
- SHOULD identify the visual hierarchy — what draws the eye first, second, third.
- SHOULD note accessibility observations (contrast issues, small text, missing
  alt text visible as broken images).

**MAY (context-dependent):**
- MAY inspect source code for exact color values, font stacks, and spacing
  tokens if the codebase is accessible.
- MAY skip component extraction for simple pages with few repeating elements.

## Failure Modes

- **Page requires login:** Audit the login page and public-facing portions.
  Note what's behind auth. Ask the user for screenshots of authenticated views.
- **Screenshots are low quality:** Re-capture with higher DPI or longer wait time.
- **Page is heavily animated:** Capture multiple states. Note animations in the
  audit — "Hero cycles through 3 images on a 5s interval."
- **Design system is very inconsistent:** That's a valid finding. Document the
  inconsistencies — they're input to the evaluation skill.

## Quality Criteria

**Communication style:** Evaluator language. Be specific and evidence-based.
Every finding needs observable evidence and user impact. Thoroughness
is more valuable than diplomacy.

Good UX audit output:
- Covers all heuristic categories — not just visual issues
- Findings cite specific elements, not vague impressions
- Severity is assigned to every finding (critical, major, minor)
- At least mobile and desktop breakpoints are checked
- Accessibility observations are included (contrast, text size, keyboard)
- Visual hierarchy is identified — what draws the eye first, second, third
- Screenshots or specific element references support each finding

## Self-Review

Before presenting your output, check each quality criterion above.
For each, confirm it's met or note what's missing. Present your
findings AND your self-assessment:

"Self-review: [X/Y criteria met]. [Note any gaps and why they exist.]"


---

## Mode: Evaluate — benchmark against category leaders


<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [ux, evaluation, gap-analysis, design-system, redesign]
inputs: [current-design-system, category-benchmarks]
outputs: [design-evaluation]
playbook: ux-design
requires: [ux-audit, ux-research]
-->

# UX Evaluate

Compare what you have against what the category expects. Not to copy
competitors — to make intentional decisions about what to keep, evolve,
and improve.

**Core Principle:** A redesign without evaluation is a reskin. Changing
colors and fonts without understanding what works and what doesn't produces
a different-looking version of the same problems. Evaluation grounds the
redesign in evidence: what's working (keep it), what's convention (match it),
what's below standard (fix it).

## When to Use

After both ux-audit (know what you have) and ux-research (know what the
category does). Before ux-brief (translating evaluation into design decisions).

## Process

### Step 1: Load Inputs

Read both artifacts:
- `.sage/work/<feature>/current-design-system.md` (from ux-audit)
- `.sage/work/<feature>/category-benchmarks.md` (from ux-research)

If either is missing, the evaluation can't proceed. Run the missing skill first.

### Step 2: Evaluate Each Design Dimension

For each dimension (colors, typography, layout, components, information
architecture), compare current state against category benchmarks and produce
a classification:

#### Color Evaluation

```markdown
## Colors
| Element | Current | Category Convention | Classification | Rationale |
|---------|---------|-------------------|----------------|-----------|
| Primary brand color | Orange #f97316 | Varies (each brand unique) | MUST KEEP | Brand identity — recognized by users |
| CTA color | Orange (same as brand) | Contrasting color from brand | SHOULD IMPROVE | CTA doesn't stand out from brand elements |
| Background | White #fff | White or light gray | SHOULD KEEP | Matches convention, no issue |
| Text color | #333 | #111-#333 range | SHOULD KEEP | Within convention range |
```

#### Typography Evaluation

```markdown
## Typography
| Element | Current | Category Convention | Classification | Rationale |
|---------|---------|-------------------|----------------|-----------|
| Hero heading size | ~28px mobile | 32-40px mobile | SHOULD IMPROVE | Below category standard, feels less impactful |
| Body text | 16px | 16-18px | SHOULD KEEP | Matches convention |
| Heading hierarchy | h1 → h3 (skips h2) | Sequential h1 → h2 → h3 | MUST IMPROVE | Accessibility violation, not just preference |
```

#### Layout Evaluation

```markdown
## Layout
| Element | Current | Category Convention | Classification | Rationale |
|---------|---------|-------------------|----------------|-----------|
| Hero pattern | Image grid + tagline | Clear value prop + single CTA | SHOULD IMPROVE | Category leaders lead with outcome, not feature showcase |
| CTA placement | Below fold on mobile | Above fold | SHOULD IMPROVE | Users must scroll to take action |
| Section count | 7 sections | 4-6 sections | MAY CHANGE | Slightly long but not critical |
```

#### Component Evaluation

```markdown
## Components
| Element | Current | Category Convention | Classification | Rationale |
|---------|---------|-------------------|----------------|-----------|
| Course cards | Image + title + description | Image + title + key metric + CTA | SHOULD IMPROVE | Missing differentiating metric (e.g., "95% AI accuracy") |
| Testimonials | Text carousel | Photo + name + score + quote | SHOULD IMPROVE | Photo + score increases credibility |
| Bee mascot | Present throughout | N/A (unique to Prep) | MUST KEEP | Brand differentiator, recognized by users |
```

#### Information Architecture Evaluation

```markdown
## Information Architecture
| Element | Current | Category Convention | Classification | Rationale |
|---------|---------|-------------------|----------------|-----------|
| First screen content | Brand tagline + animated images | Value prop + CTA + social proof | SHOULD IMPROVE | Category leaders answer "what is this?" and "why should I care?" above fold |
| Social proof position | Bottom half of page | Top half, near hero | SHOULD IMPROVE | 100K+ students is a powerful signal — it's buried |
| Navigation | Full nav with dropdowns | Simplified nav + prominent CTA | MAY CHANGE | Current works, but heavy for a landing page |
```

### Step 3: Classification Framework

Use these four categories consistently:

**MUST KEEP** — Brand identity elements. Changing these confuses existing users.
- Logo, brand colors, mascot/character, brand voice/tone
- Unique differentiators that aren't replicated by competitors
- Test: "Would existing users not recognize this as the same product?"

**SHOULD KEEP** — Patterns that work and match conventions.
- Elements that are both functionally correct AND match category expectations
- Test: "Is there evidence this is broken or underperforming?" If no → keep

**MAY CHANGE** — Style elements where updating would freshen without breaking.
- Background colors, section styling, animation approaches
- Layout tweaks that don't change information architecture
- Test: "Would changing this confuse anyone or break anything?" If no → candidate

**SHOULD IMPROVE** — Elements that fall below category standards or have
measurable problems.
- Missing conventions that users expect (CTA above fold, social proof near hero)
- Accessibility violations (contrast, heading hierarchy, touch targets)
- Performance issues visible in screenshots (layout shift, broken images)
- Test: "Is this measurably worse than category convention?" If yes → improve

### Step 4: Prioritize Improvements

Rank SHOULD IMPROVE items by impact:

```markdown
## Priority Improvements
1. [Highest impact]: [description] — [why: conversion / accessibility / performance]
2. [High impact]: [description] — [why]
3. [Medium impact]: [description] — [why]
...
```

Impact factors:
- Above-fold changes affect all visitors
- Accessibility fixes have legal/compliance implications
- Mobile fixes affect majority of traffic (in Vietnam, ~70%+ mobile)
- Social proof placement directly affects conversion

### Step 5: Produce Evaluation Document

Save to `.sage/work/<feature>/design-evaluation.md`:

```markdown
# Design Evaluation: [page/product]

**Based on:** current-design-system.md + category-benchmarks.md
**Date:** [timestamp]

## Summary
[2-3 sentences: overall assessment, how current design compares to category]

## Classification Table
| Dimension | MUST KEEP | SHOULD KEEP | MAY CHANGE | SHOULD IMPROVE |
|-----------|-----------|-------------|------------|----------------|
| Colors | [count] | [count] | [count] | [count] |
| Typography | [count] | [count] | [count] | [count] |
| Layout | [count] | [count] | [count] | [count] |
| Components | [count] | [count] | [count] | [count] |
| IA | [count] | [count] | [count] | [count] |

## Detailed Evaluation
[from Step 2 — all dimension tables]

## Priority Improvements
[from Step 4 — ranked list]
```

Show to user: "Here's the evaluation. Before I create the design brief,
I want to confirm: do you agree with the classifications? Anything I
marked as MUST KEEP that you actually want to change, or vice versa?"

🔒 **CHECKPOINT:** This is where the user's input matters most. The
classifications are proposals — the user decides.

## Rules

**MUST (violation = uninformed redesign):**
- MUST have both ux-audit and ux-research outputs before evaluating.
  Evaluation without evidence is opinion.
- MUST present classifications to the user for confirmation before
  proceeding to ux-brief. The user decides what to keep.
- MUST classify accessibility violations as SHOULD IMPROVE regardless
  of category convention. Accessibility is a standard, not a preference.

**SHOULD (violation = incomplete evaluation):**
- SHOULD evaluate all five dimensions (colors, typography, layout,
  components, information architecture).
- SHOULD reference specific category benchmark evidence for each
  SHOULD IMPROVE classification. "Competitors do X" is evidence.

**MAY (context-dependent):**
- MAY merge dimensions if the page is simple (e.g., a single-section
  landing page doesn't need separate layout and IA evaluation).
- MAY add dimensions not listed (animation, micro-interactions,
  illustration style) if they're relevant to the redesign.

## Failure Modes

- **User disagrees with MUST KEEP classification:** Respect their decision.
  They know their brand better. Reclassify and note the reason.
- **No clear category convention exists:** Mark as MAY CHANGE with note
  "No strong convention — this is a differentiation opportunity."
- **Current design is significantly better than competitors in an area:**
  Mark as MUST KEEP with note "Ahead of category — preserve this advantage."
- **User wants to change everything:** Caution them: "Changing everything
  at once risks losing what works. Suggest phasing: SHOULD IMPROVE items
  first, MAY CHANGE items in a second pass." Respect their final decision.

## Quality Criteria

**Communication style:** Analytical language. Justify classifications
with evidence — benchmarks, conventions, principles. Evaluations should
hold up if challenged by a stakeholder.

Good UX evaluation output:
- Every dimension is classified (MUST KEEP / SHOULD IMPROVE / MAY CHANGE)
- Classifications are justified with evidence — benchmark data, conventions, principles
- MUST KEEP items cite specific brand or usability reasons
- SHOULD IMPROVE items cite category benchmarks or established conventions
- Competitor analysis is specific — names, observations, patterns
- The evaluation would hold up if challenged by a stakeholder

## Self-Review

Before presenting your output, check each quality criterion above.
For each, confirm it's met or note what's missing. Present your
findings AND your self-assessment:

"Self-review: [X/Y criteria met]. [Note any gaps and why they exist.]"


---

## Mode: Heuristic Review — check against usability heuristics


# UX Heuristic Review

Evaluates the implementation against usability heuristics. Runs ALONGSIDE the
core `quality-review` skill at the review phase. When installed, this review
is mandatory — it cannot be skipped by the agent.

## Mode: BUILD (light) — Critical Four

Evaluate the implementation against the four heuristics most likely to catch
user-facing failures. Takes ~2 minutes per task.

### H1: Feedback — Visibility of System Status

- Does every button/action produce visible response?
- Are there loading indicators for async operations?
- Does the user know if their action succeeded or failed?
- Is there any action that results in silence?
→ Silence after user action = FAIL

### H3: Control — User Control and Freedom

- Can the user undo or cancel actions?
- Can they dismiss modals and dialogs?
- Does the back button work correctly?
- Are destructive actions protected by confirmation?
→ No undo on destructive action = FAIL

### H5: Prevention — Error Prevention

- Are inputs constrained where possible (dropdowns, datepickers, type validation)?
- Does inline validation catch errors before submission?
- Are dangerous options visually distinct from safe ones?
→ Free text where a constrained input would prevent errors = FAIL

### H9: Recovery — Help Users Recognize and Recover from Errors

- Are error messages in user language (not developer jargon)?
- Does each error message say what went wrong AND what to do next?
- Is form data preserved on validation failure?
- No HTTP status codes, field names, or stack traces in user-facing messages?
→ Technical error message shown to user = FAIL

## Mode: ARCHITECT (full) — All Ten Heuristics

Evaluate against all 10 Nielsen heuristics plus Norman's design principles.
Takes ~10 minutes per major feature.

### Additional Heuristics (beyond the Critical Four)

**H2: Real-World Match** — Does the interface use the user's language? Are
icons and metaphors recognizable? Is information organized the way users think?

**H4: Consistency** — Are the same actions called the same thing everywhere?
Do similar elements behave the same way? Does it follow platform conventions?

**H6: Recognition over Recall** — Are all available actions visible? Do forms
show expected formats? Can users see previous selections when making new ones?

**H7: Flexibility** — Are there keyboard shortcuts for frequent actions? Can
expert users bypass introductory steps? Does it remember preferences?

**H8: Minimalism** — Is there unnecessary text? Are visual elements serving a
purpose? Is the visual hierarchy clear?

**H10: Help** — Is contextual help available for complex features? Are tooltips
concise and useful?

### Norman's Principles Check

In addition to Nielsen's heuristics, check:
- **Affordances:** Do interactive elements look interactive?
- **Signifiers:** Is it clear what's clickable, draggable, editable?
- **Mapping:** Do control positions correspond to what they affect?
- **Conceptual Model:** Does the interface communicate how the system works?

## Severity Classification

Each finding gets a severity:

| Severity | Definition | Action |
|----------|-----------|--------|
| **Catastrophic** | User loses data or can't complete primary task | MUST fix before merge |
| **Major** | User significantly confused or frustrated | SHOULD fix before merge |
| **Minor** | User notices oddity but works around it | Fix in next iteration |
| **Cosmetic** | Violates principle but minimal user impact | Note for polish |

## Produce: heuristic-assessment artifact

```
## UX Heuristic Review: [feature name]
Date: [date]
Mode: [BUILD light / ARCHITECT full]

### Findings

1. [H9 - MAJOR] Error message on login form says "401 Unauthorized"
   → Should say: "Wrong email or password. Check your details and try again."
   → Fix: Update error handler in login-form.tsx

2. [H1 - CATASTROPHIC] No loading state on payment submission
   → User clicks "Pay" and sees no response for 3-5 seconds
   → Fix: Add loading spinner to submit button, disable during processing

### Summary
- Catastrophic: 1 (must fix)
- Major: 1 (should fix)
- GATE RESULT: FAIL (catastrophic finding blocks merge)
```

## References

- `heuristic-evaluation.md` — Full heuristic descriptions and checkpoints
- `usability-principles.md` — Krug's laws and Norman's principles
- `error-and-recovery-design.md` — Error taxonomy for H5/H9 evaluation
