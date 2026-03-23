---
name: design-check
description: >
  Quick design quality scan of changed frontend files. Checks for
  hardcoded colors (when design system exists), missing interactive
  states, and AI slop indicators. Code-only — does not use Lightpanda.
  Advisory only — never blocks. Invisible when no frontend files in diff.
version: "1.0.0"
modes: [build]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [verification, design, quality, frontend]
inputs: [diff]
outputs: [pass-warnings]
requires: []
-->

# Design Check (Light Mode)

Quick scan within quality-gates. Catches common design quality issues
in changed frontend files. Code-only — does not require a browser.

## Availability Check

**FIRST:** Check if the diff contains frontend files:
.html, .css, .scss, .less, .jsx, .tsx, .vue, .svelte, .astro

If NO frontend files in diff:
- Return immediately
- No output, no warning, INVISIBLE

## Design System Detection

Scan in order (stop at first match):
1. Design system skill in `sage/skills/` or `.claude/skills/`
2. `DESIGN.md` or `design-system.md` in project root or `.sage/docs/`
3. CSS custom properties pattern (`--color-*`, `--spacing-*`, `--font-*`)

If found → enable token compliance checks.
If not found → skip token checks, still run general quality checks.

Detection is automatic and INVISIBLE — do not announce whether a
design system was found. Just use it (or don't) silently.

## What It Checks (15 seconds max)

### 1. Hardcoded colors (when design system detected)

Scan changed files for raw hex colors (#fff, #333, rgb(), hsl())
that should be design system token references.

Finding: note — "N hardcoded colors in [file] (consider using tokens)"

### 2. Missing interactive states

Search changed component files for:
- `:hover` styles on interactive elements (buttons, links, cards)
- `:focus` or `:focus-visible` on focusable elements
- `disabled` attribute handling with visual distinction
- Loading/empty/error state handling in components

Finding: note — "[file] has no :focus style on [element]"

### 3. AI slop indicators

In new or heavily modified components, check for:
- Purple-to-blue gradient hero sections
- 3-column icon grids with uniform card styling
- Uniform large border-radius on every element
- Centered text on every section
- Decorative background shapes with no function
- Excessive shadow/elevation on flat content

Each indicator: warning (awareness, not judgment)

## Report

**If findings exist:**

```
✓ Design check: PASS ({N} notes)
  - Note: {finding 1}
  - Note: {finding 2}
  - Warning: {AI slop indicator}
```

**If clean:**

```
✓ Design check: PASS
```

**If no frontend files:**

No output. Invisible.

## Enforcement

- Advisory ONLY — never blocks the build
- Findings are notes and warnings, never issues
- Do NOT fabricate findings — if you didn't read the file, don't claim
- Do NOT invent a design system — if none detected, skip token checks
- Do NOT auto-fix design decisions — report only
- AI slop indicators are WARNINGS, not issues. Count, don't grade.
