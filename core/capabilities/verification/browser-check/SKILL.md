---
name: browser-check
description: >
  Quick browser smoke test via Lightpanda MCP. Checks if the primary
  affected route renders, has no JS errors, and contains expected elements.
  Advisory only — never blocks. Invisible when Lightpanda is not available
  or no frontend files in diff.
version: "1.0.0"
modes: [build, fix]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [verification, browser, qa, smoke-test]
inputs: [url, diff]
outputs: [pass-fail]
requires: []
-->

# Browser Check (Light Mode)

Quick smoke test within quality-gates. Catches catastrophic failures:
page doesn't load, JS errors, blank screen, missing key elements.

## Availability Check

**FIRST:** Check if Lightpanda MCP tools are in the agent's tool list.

If Lightpanda MCP is NOT available:
- Return immediately
- No output, no warning, INVISIBLE
- Do NOT suggest installing Lightpanda
- Do NOT mention this gate was skipped

If the change does NOT touch frontend/user-facing code:
- Return immediately, invisible

If no running URL is known:
- Ask once: "What URL should I check? (e.g., localhost:3000)"
- If user declines or URL is unreachable, skip invisibly

## When All Conditions Met

Time budget: 30 seconds max. One page load, three tool calls.

### Step 1: Navigate

Use `goto` to load the primary affected route.
If Lightpanda doesn't respond within 10 seconds, skip with timeout note.

### Step 2: Check for Catastrophic Failures

1. `evaluate`: check for JS console errors (uncaught exceptions)
2. `markdown`: verify page has non-empty content (not blank/error)
3. `semantic_tree`: verify expected key elements exist (based on spec)

### Step 3: Report

**If catastrophic failure detected:**

```
⚠ Browser check: FAIL
Route: /[path]
Issue: [what's wrong — JS error, blank page, missing elements]
Console: [relevant error output]

Recommend: Run /qa for full assessment, or /fix for this issue.
```

**If pass:**

```
✓ Browser check: PASS
Route: /[path] — renders, no JS errors, key elements present.
```

## Enforcement

- Advisory ONLY — never blocks the build
- A failure produces a warning and recommendation, NOT a gate failure
- Do NOT fabricate browser findings (if you didn't load the page, don't
  claim you did)
- Do NOT test routes that weren't affected by the current change
