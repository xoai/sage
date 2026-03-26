---
name: coding-principles
description: >
  Seven universal coding principles applied during implementation.
  Language-agnostic quality standards that shape every line of code
  as it's written. Loaded by build-loop before each task. Not a
  review checklist — a mindset active during implementation.
version: "1.0.0"
modes: [build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [execution, quality, principles, coding, implementation]
inputs: [plan-task, codebase-context]
outputs: [implementation]
requires: []
-->

# Coding Principles

Seven universal principles for writing production-quality code.
Apply these to every line, in every language. They are not a
post-hoc checklist — they shape decisions AS you write.

Stack skills (react, flutter, nextjs, etc.) add language-specific
idioms on top. These principles are the foundation.

## Principle 1: Clarity Over Cleverness

Write code a stranger can read without asking you what it does.

**Do:**
- Name things for what they DO: `fetchActiveUsers()`, `isExpired`,
  `MAX_RETRY_ATTEMPTS`
- Functions do one thing. If you need "and" to describe it, split it.
- Comments explain WHY, not WHAT. The code says what; the comment
  says why it's surprising or non-obvious.
- Prefer explicit over implicit. `if (user.role === "admin")` not
  `if (checkAccess(user, 2))`.

**Don't:**
- Magic numbers: `if (retries > 3)` → `if (retries > MAX_RETRIES)`
- Clever one-liners that save a line but cost a minute to read.
- Names like `data`, `temp`, `flag2`, `processStuff`, `handleIt`.
- Nested ternaries. Ever.

## Principle 2: Fail Loudly, Recover Gracefully

Every external call can fail. Handle it explicitly. Never swallow
errors. Give the caller something useful when things go wrong.

**Do:**
- Every `fetch`, `query`, `read`, `parse` has error handling.
- Error messages include: what happened, what was expected, what to
  do about it.
- Async operations have loading, success, AND error states. No async
  without all three.
- Distinguish recoverable (retry, fallback) from fatal (log, alert,
  stop).

**Don't:**
- Empty catch blocks. Ever. If you truly ignore an error, comment
  WHY.
- `console.log(err)` as the only error handling.
- "Failed to load" with no context. WHO failed to load WHAT and WHY.
- Retrying fatal errors. Crashing on recoverable ones.

## Principle 3: Guard the Boundaries

Validate at every entry point. Don't trust input from users, APIs,
files, or even your own internal modules.

**Do:**
- Public function parameters: validate type, range, presence.
- API responses: check shape before accessing nested fields.
  `response?.data?.user?.id` not `response.data.user.id`.
- User input: validate before processing. Reject early, clearly.
- Configuration: fail at startup if config is invalid, not at 3am
  when the missing value is first accessed.
- Database results: handle empty results, null fields, unexpected types.

**Don't:**
- Trust that an API response has the shape you expect.
- Access nested properties without null checks.
- Process user input without validation.
- Assume config values exist without checking.

## Principle 4: Smallest Scope, Shortest Lifetime

Variables close to where they're used. Functions close to what
calls them. Reduce the blast radius of every change.

**Do:**
- Declare variables at first use, not at the top.
- Prefer local over global. Prefer parameters over shared state.
- Prefer pure functions (same input → same output) where practical.
- Keep functions short. If you're scrolling, it's too long. Extract.
- Modules have one reason to change.

**Don't:**
- Declare all variables at the top of the function.
- Use global state when a parameter would work.
- Write 200-line functions. Extract logical sections.
- Put unrelated functionality in the same module because
  "it's convenient."

## Principle 5: Make the Right Thing Easy, the Wrong Thing Hard

Design APIs and interfaces so correct usage is obvious and misuse
requires effort.

**Do:**
- Required parameters come first. Optional parameters have defaults.
- Return types that force the caller to handle success and failure.
- Use the type system: enum not string, branded types for IDs,
  non-nullable when null is invalid.
- Impossible states should be unrepresentable.

**Don't:**
- Return `null` to mean both "failed" and "empty."
- Accept `any` or untyped dictionaries for structured data.
- Design functions where the caller must remember to check a flag.
- Allow invalid state combinations that crash at runtime.

## Principle 6: Consistency Beats Perfection

Match the existing codebase. Consistency across the project matters
more than your personal preference.

**Do:**
- Read existing code before writing new code. Match patterns.
- Follow the project's error handling pattern.
- Use the project's existing utilities before writing new ones.
- If the project has no patterns, establish one and follow it.
- Match naming: if the project uses `camelCase`, use `camelCase`.

**Don't:**
- Introduce a new style in your files because "it's better."
- Write a utility function when one already exists in the project.
- Mix patterns: callbacks in one file, promises in another,
  async/await in a third.

## Principle 7: Test What Matters, Not What's Easy

Write tests that catch bugs, not tests that inflate coverage numbers.

**Do:**
- Test the contract: "given X input, expect Y output."
- Test boundaries: min, max, zero, empty, one, many.
- Test error paths: invalid input, timeout, permission denied.
- One assertion per test when practical.
- Test names describe the scenario: `test_expired_token_returns_401`.

**Don't:**
- Test implementation details: "function calls helper A then B."
- Test only the happy path.
- Name tests `test_1`, `test_auth_3`, `test_new`.
- Write tests that pass regardless of the implementation being correct.
- Mock everything — some integration is worth testing.

## How This Loads

Build-loop loads this capability at Step 3, before each task:

```
Sage: Loading coding principles for implementation.
Following: clarity, error handling, boundary guards, minimal scope,
safe APIs, consistency, behavior testing.
```

These principles are active for every line written during the task.
They are NOT a post-hoc checklist — they shape the code as it's
written.

## Relationship to Other Capabilities

- **Stack skills** (react, flutter, nextjs) add language-specific
  idioms. Principles provide the universal foundation.
- **TDD capability** drives the test-first workflow. Principle 7
  guides WHAT to test within that workflow.
- **quality-review** (Gate 3) reviews AFTER implementation.
  Principles guide DURING implementation. Both are needed.
- **auto-QA** verifies code against spec. Principles ensure the
  code is well-crafted regardless of spec compliance.

## Rules

- Principles apply to ALL languages. No language-specific rules here.
- Principles guide, they don't block. Pragmatic exceptions are fine
  when explicitly justified.
- When principles conflict with project conventions, conventions win
  (Principle 6).
- When principles conflict with each other, clarity wins (Principle 1).
