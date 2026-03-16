---
name: visual-review
description: >
  Evaluates UI implementation by analyzing screenshots at multiple breakpoints
  against the spec, design conventions, and web standards. Checks layout,
  hierarchy, responsiveness, spacing, and accessibility. Use after implementing
  UI components, after a redesign, when the user says "how does it look",
  "check the design", "visual review", or "review the UI".
version: "1.0.0"
modes: [build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [review, visual, design, accessibility, responsive]
inputs: [implementation, screenshots, spec]
outputs: [visual-review-report]
requires: [verify-completion]
-->

# Visual Review

Evaluate the visual implementation using real screenshots — not code inspection,
not assumptions. Screenshots are evidence. Code can look correct and render wrong.

**Core Principle:** Visual quality is verified visually. Reading JSX tells you
what the DOM structure is. Screenshots tell you what the USER sees. This skill
bridges the gap between "the code is correct" and "the page looks right."

## When to Use

After implementing UI components in BUILD or ARCHITECT mode. Specifically:
- After completing a page, section, or component that has visual output
- During redesign tasks where before/after comparison matters
- When the spec includes visual requirements (layout, hierarchy, responsive)
- When the user asks for visual feedback

Do NOT use for:
- API-only features (no UI)
- Database migrations
- Backend logic with no visual output

## Process

### Step 1: Capture Screenshots

Run the screenshot tool at the standard breakpoints:

```bash
bash .sage/tools/sage-screenshot.sh http://localhost:3000 \
  --output .sage/work/<feature>/screenshots \
  --label <feature-name> \
  --full-page \
  --after
```

If "before" screenshots exist from before the implementation, the tool will
have captured them with `--before`. Both sets enable comparison.

If the dev server isn't running, start it first:
```bash
npm run dev &
sleep 5  # wait for server
# capture screenshots
kill %1  # stop server
```

### Step 2: Review Each Breakpoint

For each screenshot (mobile 375px, tablet 768px, desktop 1440px), evaluate:

#### Layout and Structure
- Does the visual hierarchy match the spec? (most important content largest/first)
- Are sections in the correct order?
- Is there a clear visual flow from top to bottom?
- Is there adequate whitespace between sections?

#### Responsive Behavior
- Does mobile stack correctly? (no horizontal overflow, no tiny text)
- Does tablet use the available space well? (not just stretched mobile)
- Does desktop fill the width appropriately? (no ultra-wide stretched content)
- Are touch targets at least 44x44pt on mobile?

#### Typography and Readability
- Is there a clear heading hierarchy? (one h1, sequential heading levels)
- Is body text readable at the viewport width? (not too wide, not too narrow)
- Is line length reasonable? (45-75 characters per line for body text)
- Is font size appropriate per breakpoint? (min 16px body on mobile)

#### Visual Consistency
- Are colors consistent with the design system / conventions?
- Is spacing consistent? (same gaps between similar elements)
- Are interactive elements visually distinguishable? (buttons look like buttons)
- Do images load and display correctly? (no broken images, correct aspect ratios)

#### Accessibility (Visual)
- Is text readable against its background? (contrast ratio)
- Are focus states visible? (for keyboard navigation)
- Is there color-only information? (should have text/icon alternatives)
- Are images decorative or informative? (informative ones need alt text)

### Step 3: Compare Before/After (If Available)

If both "before" and "after" screenshots exist:

- What improved? (be specific: "Hero CTA is now above the fold on mobile")
- What regressed? (be specific: "Card spacing is tighter than before on tablet")
- What's unchanged that should have changed per spec?
- What changed that wasn't in the spec? (scope creep flag)

### Step 4: Produce Report

Output a structured visual review to `.sage/work/<feature>/visual-review.md`:

```markdown
# Visual Review: [feature name]

**Date:** [timestamp]
**Breakpoints reviewed:** 375px, 768px, 1440px

## Summary
[1-2 sentence overall assessment]

## Mobile (375px)
**Status:** PASS / ISSUES FOUND
[Specific findings with reference to what's visible in screenshot]

## Tablet (768px)
**Status:** PASS / ISSUES FOUND
[Specific findings]

## Desktop (1440px)
**Status:** PASS / ISSUES FOUND
[Specific findings]

## Before/After Comparison
[If available — specific improvements and regressions]

## Issues Found
1. [Issue]: [description] — [severity: critical/major/minor]
2. ...

## Recommendation
PASS — ready to merge
PASS WITH NOTES — merge but address [minor issues] in follow-up
FAIL — [critical issues] must be fixed before merge
```

Show the report to the user. If issues are found, present the screenshot
alongside the issue description so the user can see what you're referring to.

## Rules

**MUST (violation = missed visual bugs):**
- MUST capture screenshots at all three breakpoints before reviewing.
  Do not review from code or memory — only from actual rendered output.
- MUST check mobile FIRST. Mobile issues are missed most often because
  developers test on desktop.
- MUST reference specific visual evidence. "The layout looks off" is not
  acceptable. "The hero section has 8px left padding instead of the 24px
  used in other sections, visible at 375px" is acceptable.

**SHOULD (violation = incomplete review):**
- SHOULD compare against the spec's acceptance criteria, not just general
  "does it look good" judgment.
- SHOULD check loading states and empty states if the spec mentions them.
- SHOULD verify images use correct aspect ratios (no squished/stretched).

**MAY (context-dependent):**
- MAY skip tablet breakpoint if the spec only mentions mobile and desktop.
- MAY capture additional breakpoints if the spec has specific requirements
  (e.g., 1920px for admin dashboards, 320px for older devices).
- MAY use browser DevTools for detailed inspection if screenshots reveal
  issues that need pixel-level diagnosis.

## Failure Modes

- **Dev server not running:** Report it. "I need the dev server running to
  capture screenshots. Run `npm run dev` and tell me when it's ready."
- **Screenshots show blank page:** The page may require authentication or
  have a loading state. Try waiting longer (--wait 5000) or check if
  auth is needed.
- **Before screenshots don't exist:** Skip comparison. Note in report:
  "No before state available — reviewing current implementation only."
- **Visual issue is subjective:** Present the evidence (screenshot) and
  your assessment, but frame it as a recommendation: "The spacing between
  cards appears inconsistent. I'd suggest 24px uniform gap. Your call."
