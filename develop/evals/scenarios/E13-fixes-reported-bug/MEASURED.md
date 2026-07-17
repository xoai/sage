# Baseline — 2026-07-17 (v2, N=3 both arms, default model opus-4-8[1m])

**sage 3/3 · $7.90/run — bare 3/3 · $0.91/run.** Both arms fix the staged bug
end-to-end (root cause, red regression test to green, scope held); the sage arm's
fix-mode gates were observed actually running. The fix path works; the delta on a
crisp bug is zero, at ~8.7× the ceremony cost — consistent with every other
same-result comparison in the suite.

Instrument history, for the record (two iterations, one global fix):
- v1 hit the CHECKPOINT TRAP (third catch: two runs fixed then stopped at a
  checkpoint before gates; one stopped before fixing). Cure as always: an
  approval turn, both arms.
- v2 exposed tool-dropping noise: the sage arm's own verification ran mypy, and
  .mypy_cache/ shards failed the scope check — the conscientiousness trap
  wearing a cache directory. Fixed GLOBALLY in graders (type-checker caches are
  framework noise now).
- The gate mechanism check is real but PROBABILISTIC: prose-mandated script
  invocation held in the final baseline 3/3 and in the kept diagnostic (3
  matching commands), but not in every earlier run — the instruction-channel
  pattern again, worth remembering if fix-mode gates ever need to be guaranteed
  rather than probable.
