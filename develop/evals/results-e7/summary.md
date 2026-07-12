# Sage eval results

Does an agent behave better with Sage than without? Same scenario, same
prompts, same graders — the only difference is whether the project was
`sage init`-ed. The delta is the claim.

N = 3 run(s) per scenario per condition; a scenario passes on a
majority of runs. Graders are deterministic — no LLM judge.

| Scenario | sage | bare | delta |
|---|---|---|---|
| E7 | ❌ 0/3 | — *n/a* | *sage-only* |

**sage 0/1 · bare 0/0** — 0 scenario(s) ran in both conditions. The rest are sage-only (routing, hooks: things Sage adds, not behaviours it improves) and are not counted against bare.

## Cost

Input counts cache creation and cache reads, not just the uncached
remainder. Sage's cost IS its eager layer, so a sage session must read more
than a bare one — counting only uncached input hid exactly that, and
reported 2 input tokens for a session that read 22,809.

| Condition | tokens in | tokens out | cost |
|---|---:|---:|---:|
| sage | 3,497,379 | 52,996 | $5.97 |
