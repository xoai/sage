---
name: autoresearch
description: >
  Autonomous iteration toward a measurable outcome. Use when the user
  wants to optimize a numeric metric through repeated modify-verify
  cycles — reduce bundle size, increase test coverage, improve query
  time, lower readability score. Not for exploratory research, subjective
  judgment, or tasks without a verification command.
version: "1.0.0"
type: process
activates-when: >
  User asks to optimize, reduce, increase, minimize, maximize, or
  improve a measurable quantity. Also: "iterate until", "keep trying",
  "get X below/above Y". Must have a verifiable metric, not just a
  subjective goal.
---

# Autoresearch

Autonomous iteration toward a measurable outcome. The agent modifies
code, commits, runs a verify command, keeps improvements, reverts
regressions — repeating until a target is hit, a budget is exhausted,
or the user interrupts.

**Core principles** (from Karpathy's autoresearch pattern):
1. One change per iteration
2. Commit before verify
3. Metrics must be mechanical (deterministic, fast, parseable)
4. Keep improvements, revert regressions — no exceptions
5. The branch is sacred — never touch main
6. State survives crashes — resume from last known good
7. Memory spans sessions — what worked/failed carries forward

## When to Use

- Task has a **measurable numeric metric** (size, time, count, score, coverage)
- A **verify command** exists that outputs the metric deterministically
- "Better" means the number going **consistently in one direction**
- The agent can make changes **autonomously** within a defined scope

## When NOT to Use

- Subjective goals ("make the UI prettier")
- No verify command available
- Metric requires manual evaluation
- Task needs human judgment per iteration
- Exploratory research without a target

## Elicitation Checklist

Before the loop can start, capture these (skip if already provided):

| Field | Required | Example |
|-------|----------|---------|
| **Goal** | Yes | "Reduce bundle below 200KB" |
| **Metric name** | Yes | `bundle_kb` |
| **Direction** | Yes | `lower` or `higher` |
| **Target** | Optional | `200` |
| **Verify command** | Yes | `pnpm build && measure.sh` |
| **Writable scope** | Recommended | `src/**/*.ts` |
| **Frozen scope** | Recommended | `package.json, *.lock` |
| **Per-run budget** | Yes (default 120s) | `120` seconds |
| **Max iterations** | Optional | `100` |
| **Termination** | Auto | `target` if target given, else `interrupt` |

Present as a brief for user approval:

```
Sage: Autoresearch session configured.

  Goal: [goal statement]
  Metric: [name] ([direction]), target: [target or "none — runs until interrupted"]
  Verify: [command]
  Scope: writable [globs], frozen [globs]
  Budget: [seconds]s per run, [max iterations or "unlimited"]

[A] Start — begin autonomous iteration
[R] Revise — change configuration
```

## The 8-Phase Loop

Each iteration follows 8 phases. Read `references/loop-protocol.md`
for per-phase detail.

| # | Phase | Actor | What happens |
|---|-------|-------|-------------|
| 1 | REVIEW | agent | Read current state, recent history (last 20 iterations from JSONL) |
| 2 | IDEATE | agent | Propose ONE change, ≤1 sentence. If stuck, load `references/stuck-recovery.md` |
| 3 | MODIFY | agent | Make the change. Stay within writable scope. |
| 4 | COMMIT | runtime | `git add -A && git commit` on `autoresearch/<slug>` branch |
| 5 | VERIFY | runtime | Run verify command with wall-clock budget |
| 6 | DECIDE | runtime | Parse METRIC, compare to best → keep / discard / crash |
| 7 | LOG | runtime+agent | Append JSONL, rebuild TSV, agent updates living doc |
| 8 | REPEAT | runtime | Check termination → loop or exit |

**Decision rules (Phase 6):**
- Exit code ≠ 0 → `crash`, reset to HEAD
- No METRIC line → `crash`, reset
- nan/inf → `crash`, reset
- Metric improved → `keep`, advance branch
- Metric equal or worse → `discard`, reset

## Runtime Integration

The Python runtime at `core/autoresearch/` handles deterministic phases
(COMMIT, VERIFY, DECIDE, LOG, REPEAT). The agent handles creative
phases (REVIEW, IDEATE, MODIFY).

**Running the runtime:**
```bash
python -m core.autoresearch run --brief .sage/work/<slug>/brief.md --project .
```

**Harness contract:** The verify command must print `METRIC name=number`
to stdout. See `references/harness-conventions.md`.

## Session State

All state lives in `.sage/work/<YYYYMMDD-slug>/`:

| File | Role |
|------|------|
| `brief.md` | Configuration (goal, metric, scope, budget) |
| `autoresearch.md` | Living doc — ideas tried, wins, dead ends |
| `autoresearch.jsonl` | Structured log (one line per iteration) |
| `results.tsv` | Human-readable view (derived from JSONL) |
| `runs/NNNN-*.log` | Per-iteration stdout+stderr |
| `.autoresearch-state.json` | Crash recovery state (not committed) |

## Session Resume

On resume (new session, context reset, platform switch):
1. Read `autoresearch.md` for high-level context
2. Read last 20 lines of `autoresearch.jsonl` for recent history
3. Verify last JSONL commit matches `git log` on the branch
4. Continue from next iteration number

See `references/session-continuity.md` for full protocol.

## Memory Integration

**Session end:** Store a structured summary in sage-memory:
- Winning patterns (what worked)
- Losing patterns (what didn't)
- Best achieved value
- Iteration count

**Session start:** Search sage-memory for priors on this repo + metric.
Inject into IDEATE as "known-good starting points" and "known dead ends."

## Quality Gates

| Gate | When | Check |
|------|------|-------|
| scope | After MODIFY | Changed files ⊆ writable, frozen untouched |
| pre-verify | After COMMIT | `git status` is clean |
| metric-parseable | After VERIFY | At least one METRIC line in stdout |
| budget | During VERIFY | Wall-clock ≤ per_run_seconds |

Gates are enforced by the runtime, not by prose. The agent cannot
bypass them.

## References

- `references/loop-protocol.md` — per-phase inputs, outputs, failure modes
- `references/metric-design.md` — what makes a good metric
- `references/harness-conventions.md` — METRIC line contract
- `references/stuck-recovery.md` — escape local minima
- `references/crash-handling.md` — retry vs skip decision tree
- `references/session-continuity.md` — resume protocol
