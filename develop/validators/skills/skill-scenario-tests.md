# Skill Scenario Tests

Targeted tests for individual skills. Each scenario tests ONE skill's behavior
in isolation. Use these to verify skills work correctly before running full
workflow tests.

---

## Quick Elicit Scenarios

### QE1: Adapts to inferred context

**Setup:** Express.js project with existing user routes.
**Prompt:** `/sage:build "add password reset functionality"`
**Verify:** Agent scans codebase FIRST, then asks about behavior ("What happens when
a user requests a reset?") but does NOT ask about tech stack, test framework, or
file structure (all inferred). Total questions ≤ 7.

### QE2: Handles impatient user

**Prompt:** `/sage:build "add a logout button"` — then respond to every question
with brief one-word answers.
**Verify:** Agent works with what it gets. Does not push for more detail. Produces
a spec from minimal input + inferred context. Does not interrogate.

### QE3: Detects complexity beyond BUILD

**Prompt:** `/sage:build "redesign the entire auth system to support SSO, OAuth2,
SAML, and magic links across all our microservices"`
**Verify:** Agent recommends ARCHITECT mode. "This spans multiple services and auth
protocols — ARCHITECT mode would give us proper planning. Switch?"

---

## Systematic Debug Scenarios

### SD1: Follows phases in order

**Setup:** A test that fails with `TypeError: Cannot read property 'id' of undefined`
**Prompt:** `/sage:debug "user.id is undefined in the order handler"`
**Verify:** Agent reads error (Phase 1) → forms hypotheses about where user object
becomes undefined (Phase 2) → traces through code to find the specific line (Phase 3)
→ writes test + fix (Phase 4). Does NOT jump to a fix.

### SD2: Resists guess-and-fix

**Prompt:** "The API is returning 500 errors sometimes. I think it's a database
connection issue — can you add a retry wrapper?"
**Verify:** Agent does NOT add a retry wrapper based on the guess. Instead: "Let me
investigate the root cause first. When do the 500 errors occur? Let me check the
logs and reproduce." Follows Phase 1-3 before proposing any fix.

### SD3: Escalates after 3 failed fixes

**Setup:** A tricky bug that can't be fixed with simple patches.
**Simulate:** Agent proposes fix → fix doesn't work. Repeat 3 times.
**Verify:** After 3rd failed fix, agent invokes Phase 4.5: "Three fixes have failed.
This suggests the root cause is architectural, not a simple code bug. Let me
re-examine the design. Should we discuss refactoring this module?"

---

## Codebase Scan Scenarios

### CS1: Identifies patterns from existing code

**Setup:** React project with Redux, styled-components, Jest, components in
`src/features/<name>/` directories.
**Verify:** Scan output correctly identifies: React, Redux, styled-components,
Jest, feature-based directory structure. Report is concise (not a full audit).

### CS2: Handles empty project

**Setup:** Empty directory with only package.json.
**Verify:** Reports "greenfield project, no established conventions." Notes that
the first implementation will set patterns.

### CS3: Stays under 2 minutes

**Setup:** Large monorepo (100+ files).
**Verify:** Scan completes quickly by focusing on the relevant area, not reading
every file. Reports relevant patterns from nearby code, not a comprehensive analysis.

---

## Specify Scenarios

### SP1: WHAT/HOW separation

**Prompt:** In BUILD mode, user says "I want a search feature using Elasticsearch."
**Verify:** Spec captures "search feature" as requirement. Elasticsearch is NOT in
the spec — it goes in the plan. Agent may note: "I'll capture the search requirement
in the spec. We'll discuss Elasticsearch as a technology choice during planning."

### SP2: Constitution conflict detection

**Setup:** Constitution says "PostgreSQL is the only approved database."
**Prompt:** User's requirements imply needing a document store for flexible schemas.
**Verify:** Agent flags the tension: "Your requirements suggest a document-oriented
data model, but the constitution mandates PostgreSQL. Options: use PostgreSQL's
JSONB columns, request a constitution waiver, or redesign requirements. Which?"

---

## Session Bridge Scenarios

### SB1: Saves progress after each task

**Test:** Complete 3 tasks in BUILD mode. Check `.sage/decisions.md` after each.
**Verify:** After task 1: progress shows task 1 complete, next is task 2.
After task 2: progress shows tasks 1-2 complete. After task 3: updated again.
Each save includes the "Next action" field.

### SB2: Recovers from stale progress

**Setup:** artifact frontmatter says "Task 3 in progress" but git log shows task 3
was committed, and task 4 was partially started.
**Verify:** Agent detects the discrepancy, trusts git over artifact frontmatter, updates
frontmatter to match actual state, and resumes from the correct position.
