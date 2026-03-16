---
name: visual-verification
description: Captures screenshots and verifies UI implementation matches visual requirements. Evidence-based — uses real rendered output, not code inspection.
version: "1.0.0"
order: 6
cost-tier: sonnet
required-context: [implementation, spec, screenshots]
category: verification
---

# Gate 6: Visual Verification

Does it LOOK right? Not in code — in the browser.

Code can be structurally correct and render wrong. A missing Tailwind class,
a broken image path, a z-index conflict, a responsive breakpoint that collapses
unexpectedly — none of these show up in code review or test suites. They show
up in screenshots.

## When This Gate Runs

- BUILD mode: after Gate 5 (functional verification), only for tasks that produce
  visible UI changes. Skip for API-only, database, or config tasks.
- ARCHITECT mode: after Gate 5, for all UI-producing tasks.
- FIX mode: skip unless the fix is visual (CSS bug, layout fix, responsive issue).

Detection: if the task's **Files** list includes `.tsx`, `.jsx`, `.vue`, `.svelte`,
`.html`, `.css`, or `.scss` files in `app/`, `pages/`, `components/`, or `src/`,
this gate runs. Otherwise it's skipped automatically.

## Deterministic Screenshot Script

**ALWAYS run the screenshot capture script first:**

```bash
bash .sage/tools/sage-screenshot.sh http://localhost:3000/<route> \
  --output .sage/work/<YYYYMMDD-slug>/screenshots \
  --label <feature-name> \
  --full-page \
  --after
```

This captures screenshots at 375px (mobile), 768px (tablet), and 1440px (desktop).
The script is deterministic — it produces PNG files and a manifest.json.

If "before" screenshots were captured at the start of a redesign task, comparison
is automatic.

## Check Criteria

### Mobile (375px) — Check FIRST
- [ ] Page renders completely (no blank sections, no loading spinners stuck)
- [ ] No horizontal overflow (no sideways scrolling)
- [ ] Text is readable (minimum 16px body, adequate contrast)
- [ ] Touch targets are at least 44x44pt (buttons, links, form inputs)
- [ ] Primary CTA is visible without scrolling (if spec requires above-fold CTA)
- [ ] Images load and maintain aspect ratio (no squish, no stretch, no broken icons)

### Tablet (768px)
- [ ] Layout adapts (not just stretched mobile or squished desktop)
- [ ] Grid layouts use available space (2-column where appropriate)
- [ ] Navigation is accessible (not hidden behind a desktop menu that doesn't fit)

### Desktop (1440px)
- [ ] Content is centered with appropriate max-width (no ultra-wide stretched text)
- [ ] Line length is readable (45-75 characters for body text)
- [ ] Visual hierarchy is clear (headings > subheadings > body)
- [ ] Whitespace between sections is consistent

### Responsive Consistency
- [ ] Same content appears at all breakpoints (nothing missing on mobile)
- [ ] Color scheme is consistent across breakpoints
- [ ] Interactive elements are identifiable at all sizes

### Before/After (if both exist)
- [ ] Improvements match what the spec requested
- [ ] No visual regressions in unchanged areas
- [ ] Nothing changed that wasn't in the spec (scope creep)

## Pass / Fail

**PASS:** All breakpoints render correctly, no critical visual issues.
Minor issues (spacing slightly off, color shade difference) noted but don't block.

**PASS WITH NOTES:** One or more minor issues found. Log them in the visual
review report. Merge is OK but issues should be addressed in a follow-up task.

**FAIL:** Any of these:
- Blank or broken rendering at any breakpoint
- Horizontal overflow on mobile
- Missing content that should be visible
- Critical accessibility failure (unreadable text, invisible focus states)
- Spec-required layout not implemented (e.g., "CTA above fold" but CTA is below)

Record the result in the plan's Gate Log table alongside Gates 1-5.

## Adversarial Guidance

Assume the implementer:
- Tested only at their monitor's resolution, not at all breakpoints
- Used placeholder content that is shorter/simpler than real content
- Didn't test with images that fail to load or text that overflows
- Verified the "golden path" layout but not edge cases (empty states,
  long usernames, RTL text, many items)
- Said "it looks right" based on the desktop view without checking mobile

Screenshots don't lie. Trust what you see, not what was described.

## Failure Response

- **Dev server not running:** BLOCKED. Start it: `npm run dev` (Next.js), `flutter run -d chrome`
  (Flutter web), `npx expo start --web` (Expo). Wait for ready, then retry.
- **Page requires auth:** BLOCKED. Ask the human for test credentials or a bypass route.
  Capture the login page screenshot as evidence.
- **Screenshot shows loading spinner:** RETRY with `--wait 5000` or `--wait 8000`.
  If still loading, FAIL — the page has a performance issue. Flag it.
- **Cannot start dev server (missing deps):** BLOCKED. Run `npm install` first.
  If that fails, this is a Gate 5 issue, not Gate 6.
- **Blank page at any breakpoint:** FAIL. The page is not rendering. Check for
  JavaScript errors in the console output from the gate script.
- **Mobile horizontal overflow:** FAIL. A CSS element exceeds viewport width.
  Check for fixed-width elements, missing responsive styles, or uncontained images.
