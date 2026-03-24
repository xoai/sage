---
name: design-review
description: >-
  Design review report with findings, severity, and fix/manual classification
disable-model-invocation: true
---

- Announce: "Sage → design-review workflow." before starting work

# Design Review Workflow

Design quality audit + design system compliance. Finds visual quality
issues, missing states, token violations, and AI slop patterns.

Report only — /design-review does NOT modify code. Mechanical findings
route to /fix. Design decisions require human judgment.

## Step 1: Context Detection

**Design system detection.** Scan in order (stop at first match):
1. Design system skill in `sage/skills/` or `.claude/skills/`
2. `DESIGN.md` or `design-system.md` in project root or `.sage/docs/`
3. CSS custom properties (`--color-*`, `--spacing-*`, `--font-*`)

If found:
```
Sage: Found design system context: [{source}].
      Will audit general quality + design system compliance.
```

If not found:
```
Sage: No design system detected. Auditing general design quality only.
      (To enable compliance checking, add a DESIGN.md or design system skill.)
```

**Lightpanda detection.** Check for MCP tool availability.
If available, note it. If not, proceed code-only. No nag.

## Step 2: Scope Analysis (Zone 1)

**If invoked after /build** (cycle context exists):
Read spec and plan. Identify changed frontend files/components.
Scope audit to those components + immediate parents.

**If invoked standalone:**

```
Sage → design-review workflow. What should I review?

[1] Recent changes — audit the current diff
[2] Specific page/component — point me at what to review
[3] Full app — audit all frontend code (broader, slower)

Pick 1-3, type / for commands, or describe what you need.
```

Show scoped file list, confirm before proceeding.

## Step 3: Code Audit

For each component/file in scope:

**Layer 1 — General quality (always runs).** 6 categories:

**1. Typography:** heading hierarchy, font count (>2 = warning),
type scale consistency, line height (1.4-1.7), measure (45-75 chars).

**2. Spacing and layout:** spacing consistency (grid vs arbitrary),
spacing scale system, container consistency, alignment.

**3. Visual hierarchy:** primary action clarity, information hierarchy,
contrast, whitespace.

**4. Interactive states:** hover/focus, disabled, loading, empty, error.

**5. Color and contrast:** color count (>8 non-gray = warning),
semantic color consistency, WCAG AA contrast ratios, dark mode coverage.

**6. AI slop detection:** purple-to-blue gradients, 3-column icon grids,
uniform border-radius, all-centered text, decorative blobs, generic
CTAs, identical repeated cards, excessive shadows, Inter with no
personality. Each indicator is a WARNING, not an issue.

**Layer 2 — Design system compliance (when system detected).**

**Token compliance:** hardcoded values vs token references.
**Component compliance:** correct component usage, sizes, variants.
**Layout compliance:** screen anatomy, padding, spacing values.
**Anti-mixing:** patterns from different design systems mixed.

For each finding, record:
- Category (which of the 6 + compliance categories)
- Severity (issue / warning / note)
- Location (file, line, component)
- What's wrong and what right looks like
- Action: **/fix** (mechanical) or **manual** (design judgment)

## Step 4: Browser Audit (if Lightpanda available)

If Lightpanda MCP is available AND URL provided:

1. `goto` each affected route
2. `semantic_tree` — verify rendered structure matches intent
3. `evaluate` with `getComputedStyle` — verify fonts, colors, sizes
4. `interactiveElements` — verify all interactive elements reachable
5. Check viewport behavior if design system specifies target width

Browser findings flagged as "browser-verified" (higher confidence).

If Lightpanda not available: skip entirely, no message. Code audit
findings are still valuable.

## Step 5: Design Review Report (Zone 2)

Save to `.sage/work/[cycle-id]/design-review.md` (if cycle) or
`.sage/docs/design-review-[topic].md` (if standalone).

Use template from `develop/templates/design-review-template.md`.

🔒 **DESIGN REVIEW CHECKPOINT:**

```
Sage: Design review complete.

Reviewed: {N} files, {M} components
Design system: {name | none}
Findings: {issues} issues, {warnings} warnings, {notes} notes
AI slop indicators: {count}/10

Route to /fix (mechanical): {count} findings
Design decisions needed (manual): {count} findings

Report: .sage/[path]/design-review.md

[A] Approve report  [R] Revise — recheck something
[F] → /fix to address mechanical issues  [N] New session

Pick A/R/F/N, or tell me what to change.
```

**Next steps (Zone 3):**

```
Next steps:
  /fix            — diagnose → scope → fix (reads design-review findings)
  /qa             — browser-based functional testing
  /reflect        — review the cycle, extract learnings

Type a command, or describe what you want to do next.
```

## Quality Criteria

Good design review output:
- Every finding has a specific location (file:line, component name)
- "What right looks like" references the design system when available
- Mechanical vs judgment classification is honest
- AI slop indicators counted, not graded
- Browser-verified findings distinguished from code-only findings
- Findings that are just code style preferences are NOT design issues

## Enforcement Contracts

**No fabricated browser findings.** If Lightpanda wasn't used, do NOT
claim browser-verified findings. Code-only analysis is honest.

**Design system detection honesty.** Do NOT invent design system
standards. If no DESIGN.md, no skill, no tokens → Layer 2 doesn't run.

**Mechanical vs judgment separation.** A missing :focus style is
mechanical (/fix). "The page layout buries the primary action" is
judgment (manual). Do NOT auto-fix design decisions.

**Light mode invisible when N/A.** In quality gates (Gate 7), if no
frontend files in diff → no output, no warning.

## Rules

- /design-review reports, it does NOT modify code
- Mechanical findings → suggest /fix. Design decisions → suggest manual.
- AI slop indicators are WARNINGS. Count, not grade.
- Browser audit is additive — code audit runs with or without browser
- Design system compliance only runs when system is detected
- Update manifest.md if cycle context exists
