# Harness Conventions

## The METRIC Contract

The verify command must print one or more lines matching this format
to stdout:

```
METRIC <name>=<number>
```

- `name`: alphanumeric + underscores (e.g., `bundle_kb`, `coverage_pct`)
- `number`: integer, float, or scientific notation (e.g., `42`, `3.14`, `1.5e2`)
- Negative numbers allowed (e.g., `-3.5`)
- `nan` and `inf` are NOT valid — treated as crash

If the same name appears multiple times, the **last value wins**.

## Exit Code Semantics

- `0` — verify succeeded, METRIC line(s) present → normal decision flow
- Non-zero — verify failed → classified as `crash`, iteration reverted

## Timeout Behavior

- Budget is `per_run_seconds` from the brief (default: 120s)
- On timeout: SIGTERM sent to the process group
- 5-second grace period for cleanup
- If still running: SIGKILL
- Classified as `crash` with note "timed out"

## Stderr

Captured in `runs/NNNN-*.log` but NOT parsed. Use stderr for
diagnostic output (build warnings, debug info). Only stdout METRIC
lines are parsed.

## Examples

**Simple:**
```bash
echo "METRIC size_bytes=$(wc -c < dist/main.js)"
```

**With build step:**
```bash
npm run build 2>&1 >/dev/null
SIZE=$(stat -f%z dist/main.js 2>/dev/null || stat -c%s dist/main.js)
echo "METRIC bundle_bytes=$SIZE"
```

**Multiple metrics (v1 uses primary only):**
```bash
echo "METRIC bundle_kb=$SIZE"
echo "METRIC build_time_s=$TIME"
```

## Writing a verify script

For complex commands, save as `autoresearch.sh` in the work directory:

```bash
#!/bin/bash
set -e
# Build
npm run build 2>/dev/null

# Measure
SIZE=$(du -sb dist/ | awk '{print $1}')
echo "METRIC bundle_bytes=$SIZE"
```

Then set `verify: "bash .sage/work/<slug>/autoresearch.sh"` in the brief.
