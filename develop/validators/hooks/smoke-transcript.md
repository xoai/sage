# Spec-gate hook — lifecycle smoke transcript

Phase-gate 2 evidence (30-§6): the block → spec → unblock flow, plus the
completion guard. Agent-driven rather than captured from a live Claude Code
session — the hook is exercised exactly as Claude Code invokes it (tool-call
JSON on stdin, `CLAUDE_PROJECT_DIR` in the environment), so the observed exit
codes and stderr are the ones a real session would see.

Reproduce:

```bash
bash develop/validators/hooks/run-hook-tests.sh   # the automated form of this
```

Fixture: a project with `hard_enforcement: true` and one cycle,
`.sage/work/auth-feature/manifest.md`, whose `gate_state` is advanced by hand to
stand in for the workflow's checkpoints.

---

### Step 1 — cycle is `pre-spec`; the agent tries to edit `src/auth.ts`

Input: `{"tool_name":"Edit","tool_input":{"file_path":"src/auth.ts", ...}}`

```
Sage spec-gate: cycle "auth-feature" is pre-spec. Rule 3: spec.md must exist and
be approved before implementation. Write .sage/work/auth-feature/spec.md and get
[A] approval, or set tier: tier1 in the manifest if this is genuinely
trivial, or set hard_enforcement: false in .sage/config.yaml to disable.
(Blocked edit: src/auth.ts)
```

**exit 2 — BLOCKED.** The reason is fed back to the model.

### Step 2 — the agent writes the spec (never blocked, even while pre-spec)

Input: `Write .sage/work/auth-feature/spec.md`

**exit 0 — ALLOWED.** Writing under `.sage/` is always permitted.

### Step 3 — spec approved `[A]`; `gate_state` → `spec-approved`; retry the edit

Input: `Edit src/auth.ts` (same as Step 1)

**exit 0 — UNBLOCKED.** The spec exists and was approved, so implementation
proceeds.

### Step 4 — the agent tries to mark the cycle complete while still `building`

Input: `Write .sage/work/auth-feature/manifest.md` with `gate_state: complete`

```
Sage spec-gate: cannot mark cycle "auth-feature" complete — gate_state is
"building", not gates-passed. Rule 5: run the quality gates and verify
before claiming done. Run the gates, set gate_state: gates-passed,
then complete.
```

**exit 2 — BLOCKED** by the completion guard (R25).

### Step 5 — quality gates pass (`gate_state` → `gates-passed`); complete again

Input: same completion write

**exit 0 — ALLOWED.** Completion is permitted once the gates have passed.

---

Rule 3 (spec-before-code) and Rule 5 (verify-before-done) are both mechanical on
Claude Code — not prose the model can rationalize past.
