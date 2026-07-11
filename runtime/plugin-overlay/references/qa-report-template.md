---
name: qa-report
type: report
version: "1.0.0"
description: >
  QA testing report. Produced by /qa workflow. Contains route results,
  flow results, bugs with severity and fix classification, and
  recommendations. Read by /fix to skip re-diagnosis.
---

# Template

```markdown
---
title: "QA Report: {description}"
status: complete
tested: YYYY-MM-DD HH:MM
url: {application URL}
browser: lightpanda | code-only
scope: {cycle-id | standalone}
---

# QA Report: {description}

## Summary

**Tested:** {N} routes, {M} flows
**Results:** {pass count} pass, {fail count} fail, {warning count} warning
**Verdict:** PASS | FAIL | PASS WITH WARNINGS
**Browser:** Lightpanda MCP | Code-only (no browser)

## Route results

### {route path} — {PASS | FAIL | WARNING}

{What was tested, what was found}

- Page renders: {yes | no — error details}
- JS errors: {none | list}
- Key elements: {all present | missing: list}

## Flow results

### {flow name} — {PASS | FAIL | WARNING}

**Steps:**
1. {action} → {expected} → {actual} ✓
2. {action} → {expected} → {actual} ✗ — {what went wrong}

**Failure point:** Step N — {description}

## Bugs found

### BUG-1: {title}

- **Severity:** critical | major | minor
- **Route:** {where it occurs}
- **Steps to reproduce:** {numbered steps}
- **Expected:** {what should happen}
- **Actual:** {what actually happens}
- **Suggested fix classification:** Surgical | Moderate | Systemic
- **Evidence:** {console output, semantic tree snippet, or description}

## Recommendations

{Which bugs to fix first. Whether to run /fix. Whether any bug
suggests a deeper issue needing /architect.}
```
