---
name: autoresearch
version: "1.0.0"
mode: autoresearch
produces: ["Optimized codebase on dedicated branch", "Iteration log"]
checkpoints: 1
scope: "Multi-session, autonomous"
user-role: "Configure goal and metric, approve brief, interrupt when satisfied"
---

# Autoresearch Workflow

Autonomous iteration toward a measurable outcome. Read the full skill
at `skills/autoresearch/SKILL.md` before proceeding.

## Auto-Pickup

Scan `.sage/work/` for directories containing `autoresearch.jsonl`.
If found, this is a resume — skip to Step 3.

## Step 1: Elicit Configuration

If the user provided inline flags or a complete description, extract
the fields. Otherwise, elicit:

1. **Goal** — what are we optimizing? (one sentence)
2. **Metric** — what number, which direction, optional target
3. **Verify command** — what command produces the METRIC line
4. **Scope** — writable globs (what the agent can change) and
   frozen globs (what must not be touched)
5. **Budget** — seconds per verify run, max iterations

Search sage-memory for priors on this repo + metric domain:
- Pass domain keywords as query, filter_tags ["autoresearch"], limit 5
- If priors exist, note winning/losing patterns for IDEATE context

## Step 2: Write Brief and Approve

Save to `.sage/work/YYYYMMDD-<slug>/brief.md` using the frontmatter
format from `skills/autoresearch/SKILL.md`.

🔒 **CHECKPOINT:**

Sage: Autoresearch session configured.

  Goal: [goal]
  Metric: [name] ([direction]), target: [target or "none"]
  Verify: [command]
  Scope: writable [globs], frozen [globs]
  Budget: [seconds]s per run, [max iterations or "unlimited"]

[A] Start — begin autonomous iteration
[R] Revise — change configuration

Pick A/R, or tell me what to change.

## Step 3: Run Loop

Read `skills/autoresearch/SKILL.md` for the 8-phase loop protocol.
Read `skills/autoresearch/references/loop-protocol.md` for per-phase
detail.

**Before each IDEATE:** If sage-memory priors were found in Step 1,
use them. If stuck (5+ consecutive discard/crash), read
`skills/autoresearch/references/stuck-recovery.md`.

**Agent phases (REVIEW, IDEATE, MODIFY):**
- REVIEW: Read current files + JSONL tail (last 20 iterations)
- IDEATE: Propose ONE change, ≤1 sentence
- MODIFY: Make the change within writable scope

**Runtime phases (COMMIT, VERIFY, DECIDE, LOG, REPEAT):**
Run the Python runtime:
```bash
python -m core.autoresearch run --brief .sage/work/<slug>/brief.md --project .
```

Or handle phases inline:
- COMMIT: `git add -A && git commit -m "autoresearch #N: <desc>"`
- VERIFY: Run the verify command with budget
- DECIDE: Parse METRIC, compare to best → keep/discard/crash
- LOG: Append to JSONL, rebuild TSV, update living doc
- REPEAT: Check termination criteria

**After each iteration:** Update `autoresearch.md` living doc with
what was tried and the result.

## Step 4: Session End

When the loop exits (target hit, budget exhausted, or interrupted):

1. **Summary:**

Sage: Autoresearch complete.

  Iterations: [N total], [K kept]
  Best: [metric_name]=[value] (started at [baseline])
  Branch: autoresearch/[slug]

  Top improvements:
  - #[N]: [description] ([metric delta])
  - #[M]: [description] ([metric delta])

  [M] Merge — review and merge the branch
  [C] Continue — resume iterating
  [R] Results — show full results.tsv

2. **Store to sage-memory** (if available):
   - Winning patterns (descriptions of kept iterations)
   - Losing patterns (descriptions of discarded iterations)
   - Best achieved value and iteration count
   - Tags: ["autoresearch", metric_name, domain tags]

3. **Prepend to decisions.md:**
   ```
   ### YYYY-MM-DD — Autoresearch: [goal]
   Result: [best value] from [baseline], [N] iterations, [K] kept.
   Branch: autoresearch/[slug]. Top change: [best iteration description].
   ```

$ARGUMENTS
