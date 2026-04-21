# Stuck Recovery

## Detection

The runtime flags "stuck" when the last N iterations (default: 5) are
all `discard` or `crash`. This means the agent is grinding on variations
of the same bad idea.

## Recovery Playbook

When stuck is flagged, execute these steps IN ORDER before the next
IDEATE:

### 1. Re-read all in-scope files

Don't rely on your memory of the code. Context may have drifted.
Read every file in the writable scope to refresh your understanding.

### 2. Review the full JSONL

Not just the tail — read ALL iterations. Look for patterns:
- Which clusters of ideas have been tried?
- Were there any near-misses (small regressions)?
- Is there a direction that was abandoned too early?

### 3. Combine near-misses

If iterations 12 and 17 each got close but from different angles,
try combining them. Apply both changes in one iteration.

### 4. Invert the recent direction

If the last 5 attempts were all about removing code, try adding
something (a cache, an index, a precomputation). If they were all
about restructuring, try a surgical targeted change instead.

### 5. Radical structural change

If none of the above work, try something fundamentally different:
- Different algorithm entirely
- Different architectural approach
- Move computation to a different layer
- Change the data structure, not the code that processes it

## Anti-Patterns

- **Tweaking the same thing**: changing `bufferSize: 1024` to `1025` to
  `1023` to `1026` — this is not iteration, this is noise
- **Ignoring crash logs**: if iterations are crashing, the crash log
  tells you why. Read `runs/NNNN-*.log`
- **More of the same**: if tree-shaking didn't help in 3 attempts, a
  4th tree-shaking attempt won't either. Change strategy.
