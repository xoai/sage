---
name: ux-audit
description: >
  Reverse-engineers the current design system from screenshots or a live URL.
  Extracts colors, typography, spacing, component patterns, and layout structure.
  Use when redesigning an existing page, auditing a current design, or when the
  user says "audit this design", "what's the current design system", "analyze
  this page", or provides a URL and says "redesign".
version: "1.0.0"
modes: [build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [ux, design, audit, reverse-engineering, visual]
inputs: [screenshots-or-url]
outputs: [current-design-system]
playbook: ux-design
requires: []
-->

# UX Audit

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
