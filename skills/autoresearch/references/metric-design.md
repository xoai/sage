# Metric Design

A good autoresearch metric is:

1. **Mechanical** — computed by a script, not by human judgment
2. **Deterministic** — same code → same number (no randomness)
3. **Fast** — runs in seconds, not minutes
4. **Single number** — one dimension of "better"
5. **Independent** — doesn't depend on execution order or external state

## Good Metrics

| Domain | Metric | Verify command |
|--------|--------|---------------|
| Bundle size | `bundle_kb` | `build && du -sb dist/ \| awk '{print "METRIC bundle_kb="$1/1024}'` |
| Test coverage | `coverage_pct` | `coverage run && coverage report \| grep TOTAL \| awk '{print "METRIC coverage_pct="$4}'` |
| Query time | `query_ms` | `psql -c "EXPLAIN ANALYZE ..." \| grep "Execution Time" \| ...` |
| Readability | `flesch_grade` | `textstat score.py < doc.md` |
| Binary size | `binary_kb` | `go build && ls -l binary \| awk '{print "METRIC binary_kb="$5/1024}'` |
| Compile time | `compile_s` | `time make 2>&1 \| grep real \| ...` |

## Bad Metrics (Anti-Patterns)

- **Subjective**: "looks better" — no number, no automation
- **Noisy**: test suite with random seeds — same code, different results
- **Slow**: full CI pipeline taking 20 minutes — iteration is too expensive
- **Composite without weights**: "improve both size AND speed" — which direction?
- **External dependency**: API latency that varies with server load

## Multi-Metric Workaround (v1)

v1 supports one metric. To optimize multiple dimensions, compose them
in the verify script:

```bash
SIZE=$(du -sb dist/ | awk '{print $1/1024}')
TIME=$(measure_build_time)
# Weighted composite — lower is better
SCORE=$(echo "$SIZE * 0.7 + $TIME * 0.3" | bc)
echo "METRIC composite=$SCORE"
```

The agent sees one number. Composing is the user's responsibility.
