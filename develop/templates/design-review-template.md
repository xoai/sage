---
name: design-review-report
type: report
version: "1.0.0"
description: >
  Design review report. Produced by /design-review workflow. Contains
  general quality findings (6 categories), design system compliance
  (when applicable), AI slop count, and findings classified as /fix
  (mechanical) or manual (design decision). Read by /fix for
  mechanical findings only.
---

# Template

```markdown
---
title: "Design Review: {description}"
status: complete
reviewed: YYYY-MM-DD HH:MM
browser: lightpanda | code-only
design_system: {name} | none
scope: {cycle-id | standalone}
---

# Design Review: {description}

## Summary

**Reviewed:** {N} files, {M} components
**Design system:** {name — compliance checked | none — general audit only}
**Browser:** {Lightpanda — rendered verification | code-only}
**Findings:** {issue count} issues, {warning count} warnings, {note count} notes
**AI slop indicators:** {count} / 10 patterns detected

## General quality

### Typography — {issues/warnings/clean}

{Findings with file locations and specific values}

### Spacing and layout — {issues/warnings/clean}

{Findings}

### Visual hierarchy — {issues/warnings/clean}

{Findings}

### Interactive states — {issues/warnings/clean}

{Findings}

### Color and contrast — {issues/warnings/clean}

{Findings}

### AI slop detection — {count}/10

{Which patterns found, where. Warnings only.}

## Design system compliance

{Section only present when design system detected}

### Token compliance — {issues/warnings/clean}

{Hardcoded values → correct token name, location}

### Component compliance — {issues/warnings/clean}

{Wrong component, incorrect dimensions, misused variants}

### Layout compliance — {issues/warnings/clean}

{Incorrect anatomy, wrong padding/spacing values}

## Findings detail

### {FINDING-1}: {title}

- **Category:** {typography | spacing | hierarchy | states | color | slop | compliance}
- **Severity:** issue | warning | note
- **Location:** {file:line — component name}
- **What's wrong:** {specific description}
- **What right looks like:** {specific correction}
- **Recommended action:** /fix (mechanical) | manual (design decision)
- **Verified:** code-only | browser-verified

## Recommendations

**Route to /fix (mechanical):**
{List of findings /fix can handle — wrong tokens, missing states, hardcoded values}

**Design decisions needed (manual):**
{Findings requiring human judgment — hierarchy, layout, component rethinking}

**Consider for future:**
{Opportunities, not issues}
```
