# Sage eval results

Does an agent behave better with Sage than without? Same scenario, same
prompts, same graders — the only difference is whether the project was
`sage init`-ed. The delta is the claim.

N = 3 run(s) per scenario per condition; a scenario passes on a
majority of runs. Graders are deterministic — no LLM judge.

| Scenario | sage | bare | delta |
|---|---|---|---|
| L1 | ✅ 2/3 | — *n/a* | *sage-only* |

**sage 1/1 · bare 0/0** — 0 scenario(s) ran in both conditions. The rest are sage-only (routing, hooks: things Sage adds, not behaviours it improves) and are not counted against bare.

## Cost

Input counts cache creation and cache reads, not just the uncached
remainder. Sage's cost IS its eager layer, so a sage session must read more
than a bare one — counting only uncached input hid exactly that, and
reported 2 input tokens for a session that read 22,809.

| Condition | tokens in | tokens out | cost |
|---|---:|---:|---:|
| sage | 11,404,022 | 124,516 | $33.07 |

## Sessions — where the cost and the recovery actually happen

A multi-session scenario runs N fresh contexts against ONE workspace.
Session 2 knows only what session 1 left on disk. An interrupted session
was cut off on purpose — it is the scenario, not a failure.

| Scenario | condition | mode | session | interrupted | tokens in | cost |
|---|---|---|---|---|---:|---:|
| L1 | sage | n/a | s1 | yes | 2,487,307 | $5.97 |
| L1 | sage | n/a | s2 | — | 2,953,852 | $10.40 |
| L1 | sage | n/a | s1 | yes | 3,234,911 | $7.15 |
| L1 | sage | n/a | s2 | — | 2,727,952 | $9.56 |
| L1 | sage | n/a | s1 | yes | 0 | $0.00 |
| L1 | sage | n/a | s2 | — | 0 | $0.00 |
