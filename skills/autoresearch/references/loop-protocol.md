# Loop Protocol — Per-Phase Detail

## Phase 1: REVIEW

**Actor:** Agent
**Inputs:** Current file state, git log on branch, last 20 JSONL entries
**Outputs:** Understanding of current state and trajectory

Read the working tree to understand what the code currently looks like.
Read the JSONL tail to understand recent attempts — what worked, what
didn't, what crashed. If this is iteration 0, note that no history
exists yet.

**Do NOT skip this phase.** Even if you "remember" the state from the
previous iteration, context may have been compacted. Always re-read.

## Phase 2: IDEATE

**Actor:** Agent
**Inputs:** Review output, memory priors (if available), stuck flag
**Outputs:** One change description (≤1 sentence)

Propose exactly ONE change. Not two. Not "try A and also B." One.

Good: "Lazy-load the admin routes module"
Bad: "Try lazy-loading and also switch to dynamic imports"

If the stuck flag is set (last 5 iterations all discard/crash):
1. Re-read ALL in-scope files (not just recently changed)
2. Review the full JSONL for patterns (what clusters of ideas failed)
3. Try combining the two best near-misses
4. Try the opposite of the recent direction
5. Try a radical structural change

If memory priors exist, use them:
- Winning patterns → try variations of these first
- Losing patterns → avoid unless your approach is fundamentally different

## Phase 3: MODIFY

**Actor:** Agent
**Inputs:** The change description from IDEATE
**Outputs:** Modified files within writable scope

Make the change. Stay within the writable globs from the brief.
Do NOT touch frozen files. The scope gate will revert violations
automatically, wasting an iteration.

**One change only.** If you're editing 5 files across 3 modules,
that's probably more than one change. Scope it down.

## Phase 4: COMMIT

**Actor:** Runtime (deterministic)
**Inputs:** Modified files, description from IDEATE
**Outputs:** New commit on `autoresearch/<slug>` branch

```bash
git add -A
git commit -m "autoresearch #N: <description>"
```

The runtime handles this. The agent does not run git commands during
autoresearch — the runtime owns the branch.

## Phase 5: VERIFY

**Actor:** Runtime (deterministic)
**Inputs:** Verify command from brief, per_run_seconds budget
**Outputs:** stdout, stderr, exit code, duration

The runtime runs the verify command with a wall-clock budget.
If the command exceeds the budget: SIGTERM → 5s grace → SIGKILL.

The agent does NOT run the verify command. The runtime does.

## Phase 6: DECIDE

**Actor:** Runtime (deterministic)
**Inputs:** Verify output, current best metric value
**Outputs:** keep / discard / crash

Decision is fully deterministic:
- crash: exit ≠ 0, no METRIC line, nan/inf, timeout
- keep: metric improved in declared direction
- discard: metric equal or worse (ties discard by default)

On crash or discard: `git reset --hard HEAD~1` to revert.
On keep: branch advances, new best is recorded.

## Phase 7: LOG

**Actor:** Runtime + Agent
**Inputs:** Decision, metrics, iteration metadata
**Outputs:** JSONL row, TSV rebuild, living doc update

Runtime appends to JSONL and rebuilds TSV.
Agent updates `autoresearch.md` with what was tried and what happened.

The living doc should capture:
- What was tried (the idea)
- What happened (metrics, keep/discard/crash)
- Any insights ("lazy-loading works for admin but not checkout")

## Phase 8: REPEAT

**Actor:** Runtime (deterministic)
**Inputs:** Termination criteria from brief
**Outputs:** Continue or exit

Three termination modes:
- `target`: metric crossed the target threshold → exit
- `iterations`: iteration count reached max_iterations → exit
- `interrupt`: user sends Ctrl+C or stop signal → exit

If none triggered → goto Phase 1.
