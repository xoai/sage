# Workflow Scenario Tests

End-to-end scenarios that verify each workflow produces correct outcomes.
Run these by starting a fresh session with Sage active and following
the scenario. Compare actual behavior against expected.

---

## Scenario W1: FIX Workflow — Complete Bug Fix

**Setup:** A Node.js project with a failing test:
```javascript
// test: "converts temperature correctly"
// Expected: fahrenheitToCelsius(212) === 100
// Actual: returns 93.33 (wrong formula)
```

**Trigger:** `/sage:fix "fahrenheitToCelsius returns wrong value for 212°F"`

**Expected Sequence:**

| Step | Expected Agent Behavior | Checkpoint |
|------|------------------------|------------|
| 1 | Reads error, identifies the test failure | Agent mentions the specific test |
| 2 | Reproduces: runs test, shows failure output | Shows actual command + output |
| 3 | Hypothesizes: formula error (F-32)*5/9 vs current implementation | States hypothesis |
| 4 | Confirms: reads the code, identifies wrong formula | Shows the code |
| 5 | Writes a new test or uses existing failing test | Test exists before fix |
| 6 | Fixes the formula | Minimal change only |
| 7 | Runs tests, shows all passing | Shows command + output |
| 8 | Gate 4: imports and APIs are real | Quick check |
| 9 | Gate 5: tests actually pass (already shown) | Evidence provided |
| 10 | Commits with semantic message | `fix(utils): correct fahrenheit to celsius formula` |
| 11 | Saves progress | Updates .sage/progress.md |

**Total time:** < 5 minutes

**Red flags (any = scenario FAIL):**
- Agent fixes the code without reading the error first
- Agent doesn't run the test to reproduce
- Agent changes the formula without explaining root cause
- Agent skips any gate
- Agent modifies unrelated code

---

## Scenario W2: BUILD Workflow — New Feature

**Setup:** An Express.js API project with users table but no authentication.

**Trigger:** `/sage:build "add API key authentication to all endpoints"`

**Expected Sequence:**

| Step | Expected Agent Behavior | Checkpoint |
|------|------------------------|------------|
| 1 | Scans codebase: Express, no auth, routes structure | Reports stack + patterns |
| 2 | Guided elicitation Round 1: "What should auth look like when working?" | Asks ≤ 2 questions |
| 3 | Guided elicitation Round 2: "Any endpoints that should stay public?" | Adapts to context |
| 4 | Guided elicitation Round 3: "How will we verify auth works?" | Acceptance criteria |
| 5 | Shows spec for approval | 🔒 CHECKPOINT — waits for human |
| 6 | Creates plan: ~5-8 tasks with file paths and test descriptions | Constitution check visible |
| 7 | Shows plan for approval | 🔒 CHECKPOINT — waits for human |
| 8-N | Per task: TDD implementation with quality gates | Each task: test → code → gates → commit |
| N+1 | Final review: all gates pass | Shows test output |
| N+2 | Presents result | 🔒 CHECKPOINT — merge/PR/keep/discard |

**Verify:**
- Elicitation took < 3 minutes
- Spec has intent, boundaries, acceptance criteria
- Plan has tasks ≤ 5 minutes each with file paths
- Every task followed TDD (test written before code)
- All 5 gates ran per task
- No scope creep (didn't add rate limiting, OAuth, etc. unless spec says so)
- Constitution compliance checked (if enterprise: auth audit trail included)

---

## Scenario W3: ARCHITECT Workflow — New Product Start

**Setup:** Empty directory. No codebase.

**Trigger:** `/sage:architect "build a REST API for a todo list application"`

**Expected Sequence:**

| Phase | Expected Agent Behavior | Checkpoint |
|-------|------------------------|------------|
| Discover | Socratic exploration: "Who uses this? What problem does it solve?" | Agent asks before assuming |
| | Product brief produced | 🔒 CHECKPOINT |
| Define | Guided PRD: personas, stories, requirements (with IDs), boundaries | Presented section by section |
| | PRD complete | 🔒 CHECKPOINT |
| Design | Architecture decisions with decision records (minimum 2 options per decision) | Each decision documented |
| | Architecture complete | 🔒 CHECKPOINT |
| Decompose | Epics → stories → tasks breakdown | Dependencies identified |
| | Story breakdown complete | 🔒 CHECKPOINT |
| Implement | Sprint planning → per-story → per-task with TDD + gates | Each story is a checkpoint |
| Finish | All tests pass, full quality gates | Final review |

**Verify:**
- Agent asked "why" before "how"
- No technology mentioned until the plan phase
- Architecture has at least one decision record
- Stories are user-visible increments
- Tasks are 2-5 minutes each
- TDD followed for every task
- All 5 gates + constitution check per task
- Multiple human checkpoints occurred

---

## Scenario W4: Session Continuity

**Setup:** Start a BUILD workflow, complete Phase 1-3 (spec + plan approved),
implement 2 of 5 tasks. Then close the session.

**Trigger:** Start a new session. Observe session-bridge behavior.

**Expected:**
1. Session-start hook loads constitution and progress
2. Agent reports: "Resuming feature [name]. Tasks 1-2 complete. Next: Task 3."
3. Agent continues from Task 3 without re-eliciting or re-planning
4. Previously established conventions are followed

**Red flags:**
- Agent asks "what are we working on?" (session-bridge failed)
- Agent re-runs elicitation (didn't load progress)
- Agent uses different patterns than previous session (didn't load conventions)
