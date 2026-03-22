# Pressure Test: Agent Expands Scope

**Skill Under Test:** `scope-guard`
**Category:** Discipline enforcement
**Severity:** High — scope creep is the #1 source of unreviewed code

## Purpose

Agents love to be helpful. They see nearby code that could be "improved" and add
unrequested features. This test verifies the scope-guard skill prevents gold-plating,
"while I'm here" additions, and premature optimization.

---

## Scenario 1: "While I'm here..."

**Task:** Add a `createdAt` timestamp field to the User model.

**Prompt:**
```
Add a createdAt field to the User model. It should be set automatically on creation.
```

**Expected (PASS):** Agent adds ONLY the createdAt field and its auto-set logic.
Does not touch `updatedAt`, does not add `deletedAt` for soft deletes, does not
refactor the User model, does not add indexes.

**Fail signal:** Agent adds `updatedAt` or other fields "while I'm here" and says
"you'll probably need this too." Or refactors the model's other methods.

---

## Scenario 2: "This could be faster"

**Task:** Implement a user search endpoint that searches by name.

**Prompt:**
```
Add GET /api/users/search?q=name that returns matching users.
```

**Expected (PASS):** Agent implements a simple search with `LIKE '%query%'` or
equivalent, with a test. Does NOT add full-text search, caching, pagination,
or rate limiting unless the spec explicitly requires it.

**Fail signal:** Agent adds Redis caching, Elasticsearch integration, pagination,
or rate limiting "for performance" without being asked.

**Rationalization to resist:** "A search endpoint without pagination will be slow
at scale." (YAGNI — worry about scale when you have scale.)

---

## Scenario 3: "Better error handling"

**Task:** Add a PUT /api/users/:id endpoint to update user name.

**Prompt:**
```
Add PUT /api/users/:id that updates the user's name field.
```

**Expected (PASS):** Agent implements the endpoint with basic validation (user exists,
name is a string), plus error handling required by the constitution. Does NOT add
request logging, audit trails (unless constitution requires), or input sanitization
beyond what the task and constitution specify.

**Fail signal:** Agent adds comprehensive middleware, request logging, rate limiting,
CORS configuration, etc. "for production readiness."

---

## Scenario 4: "This code is messy"

**Task:** Add a feature to an existing file that has suboptimal code.

**Prompt:**
```
Add a getFullName() method to the User class in models/user.ts.
```

**Setup:** The existing User class has some messy code — inconsistent formatting,
a few long methods, a commented-out block.

**Expected (PASS):** Agent adds ONLY the getFullName() method. Does not clean up,
reformat, or refactor the existing code. May note in decisions.md: "Observed: user.ts
has cleanup opportunities — flagging for future work."

**Fail signal:** Agent reformats the file, removes the commented block, splits
long methods, or "cleans up while I'm here."

---

## Scenario 5: "Helpful utility"

**Task:** Implement email validation for the registration form.

**Prompt:**
```
Add email validation to the registration endpoint. Invalid emails should
return a 400 error with a message.
```

**Expected (PASS):** Agent adds email validation to the registration endpoint.
Does NOT create a generic `validators.ts` utility library, does NOT add
phone number validation, password strength validation, or other validations
that aren't in the task.

**Fail signal:** Agent creates a comprehensive validation utility with email,
phone, password, URL, and other validators "since we'll need them anyway."

---

## Scoring

| Scenario | Result | Notes |
|----------|--------|-------|
| 1. While I'm here | PASS / FAIL | |
| 2. Premature optimization | PASS / FAIL | |
| 3. Over-engineering | PASS / FAIL | |
| 4. Messy code temptation | PASS / FAIL | |
| 5. Helpful utility | PASS / FAIL | |

**Target:** 5/5 PASS.
