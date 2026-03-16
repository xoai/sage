# Integration Tests

Verifies that Sage modules work together correctly — skills chain properly,
context flows between phases, and the override/replacement system functions.

---

## Test I1: Constitution Inheritance Chain

**Setup:**
1. Create org constitution (`~/.sage/constitution.md`) with principle: "All APIs use REST."
2. Create project constitution (`.sage/constitution.md`) extending enterprise with
   addition: "PostgreSQL is the only database."
3. Create feature context (`.sage/work/001-search/context.md`) with
   addition: "Search must support fuzzy matching."

**Test:** Start a BUILD workflow for the search feature.

**Verify:**
- Agent references ALL three tiers of principles
- Gate 2 checks against the merged constitution (REST + PostgreSQL + fuzzy)
- Agent cannot propose GraphQL (violates org tier)
- Agent cannot propose MongoDB (violates project tier)
- Agent implements fuzzy matching (required by feature tier)

**Fail condition:** Agent ignores any tier, or lower tier overrides higher tier.

---

## Test I2: Skill Override Resolution

**Setup:**
1. Default TDD skill exists in `core/capabilities/execution/tdd/`
2. Create a project override in `.sage/skills/tdd/SKILL.md` that adds a custom rule:
   "All test file names must end with `.spec.ts` (not `.test.ts`)"
3. Set `replaces: tdd` in the override's frontmatter

**Test:** Start a BUILD workflow and implement a task.

**Verify:**
- The override TDD skill is loaded (not the default)
- Test files are created with `.spec.ts` extension
- All other TDD behaviors (red-green-refactor, deletion rule) still apply

**Fail condition:** Default TDD skill loads instead of override, or override
breaks core TDD behaviors.

---

## Test I3: Gate Pipeline Stops on Failure

**Setup:** Intentionally introduce a spec compliance violation — implement a task
but omit one of the requirements.

**Test:** Run the quality gates.

**Verify:**
- Gate 1 (spec compliance) catches the missing requirement → FAIL
- Gates 2-5 do NOT run (pipeline stops at first failure)
- Agent attempts to fix the missing requirement
- After fix, gates restart from Gate 1
- All 5 gates eventually pass

**Fail condition:** Later gates run despite Gate 1 failing, or agent bypasses
the failed gate.

---

## Test I4: Mode Escalation Mid-Workflow

**Setup:** Start FIX mode for what seems like a simple bug.

**Test prompt:** `/sage:fix "The user profile page is blank"`

**During investigation:** Agent discovers the profile page component was never
implemented — it's a placeholder div.

**Verify:**
- Agent detects the scope exceeds FIX mode
- Agent recommends BUILD mode: "This isn't a bug — the feature doesn't exist.
  Switch to BUILD mode?"
- If user agrees, workflow transitions to BUILD
- BUILD mode starts from Phase 1 (scan + elicit), not from where FIX left off
- Progress.md tracks the mode change

**Fail condition:** Agent stays in FIX mode and patches a stub implementation,
or switches mode silently without human approval.

---

## Test I5: Codebase Scan → Elicitation Adaptation

**Setup:** An existing React project with:
- TypeScript
- Jest tests using `describe/it` pattern
- Components in `src/components/` with PascalCase naming
- API calls through a `src/api/` layer

**Test:** `/sage:build "add user profile page"`

**Verify:**
- Codebase scan identifies: TypeScript, React, Jest, component patterns
- Quick elicitation does NOT ask "what framework?" or "what test library?"
  (already known from scan)
- Elicitation focuses on behavior questions only
- The plan references correct paths (`src/components/UserProfile.tsx`)
- Task tests use `describe/it` pattern matching existing convention
- Components follow PascalCase naming

**Fail condition:** Elicitation asks about tech stack (should be inferred),
or plan uses wrong paths/conventions (scan results not applied).

---

## Test I6: Persona Switching Across Phases

**Setup:** ARCHITECT mode workflow.

**Test:** `/sage:architect "build a notification service"`

**Verify across phases:**
- Phase 1 (Discover): Analyst persona active — asks Socratic questions,
  doesn't mention technology
- Phase 3 (Design): Architect persona active — discusses boundaries,
  trade-offs, decision records
- Phase 4 (Implement): Developer persona active — pragmatic, YAGNI,
  shows code not descriptions
- Gate checks: Reviewer persona active — skeptical, reads code not reports

**Fail condition:** Developer persona leaks into discovery phase (suggesting
solutions too early), or analyst persona persists during implementation
(asking too many questions instead of building).

---

## Test I7: Extension Adds Constitution + Gate

**Setup:**
1. Enable a hypothetical `security` extension that adds:
   - Constitution addition: "All inputs must be sanitized against XSS"
   - Gate 51: OWASP security scan
2. Configure in `.sage/config.yaml`: `extensions: [security]`

**Test:** BUILD workflow for a feature that accepts user input.

**Verify:**
- The XSS sanitization principle appears in the merged constitution
- Gate 2 checks for XSS sanitization compliance
- Gate 51 runs after the 5 default gates
- If input handling doesn't sanitize, Gate 2 OR Gate 51 catches it

**Fail condition:** Extension principles not merged, extension gate not run,
or extension conflicts with core behavior.

---

## Test I8: Session Bridge Across Crash

**Setup:** Start a BUILD workflow. Complete 3 of 6 tasks. Simulate a session
crash (close the terminal mid-task, or let context compact).

**Test:** Start a new session.

**Verify:**
- `.sage/progress.md` shows tasks 1-3 complete, task 4 in progress or not started
- Agent resumes from task 3 or 4 (depending on when crash happened)
- Git history shows commits for tasks 1-3
- Agent does NOT re-implement completed tasks
- If task 4 was partially done, agent detects via git status and either
  continues or rolls back the partial work

**Fail condition:** Agent starts over from scratch, re-implements completed
tasks, or leaves inconsistent state from partial task 4.
