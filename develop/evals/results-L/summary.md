# Sage eval results

Does an agent behave better with Sage than without? Same scenario, same
prompts, same graders — the only difference is whether the project was
`sage init`-ed. The delta is the claim.

N = 1 run(s) per scenario per condition; a scenario passes on a
majority of runs. Graders are deterministic — no LLM judge.

| Scenario | sage | bare | delta |
|---|---|---|---|
| L1 | ❌ 0/1 | ❌ 0/1 | same |
| L2 | ✅ 1/1 | ✅ 1/1 | same |

**sage 1/2 · bare 1/2** — 2 scenario(s) ran in both conditions. The rest are sage-only (routing, hooks: things Sage adds, not behaviours it improves) and are not counted against bare.

## Cost

Input counts cache creation and cache reads, not just the uncached
remainder. Sage's cost IS its eager layer, so a sage session must read more
than a bare one — counting only uncached input hid exactly that, and
reported 2 input tokens for a session that read 22,809.

| Condition | tokens in | tokens out | cost |
|---|---:|---:|---:|
| sage | 4,913,784 | 67,898 | $6.34 |
| bare | 1,914,280 | 24,119 | $2.42 |

## Sessions — where the cost and the recovery actually happen

A multi-session scenario runs N fresh contexts against ONE workspace.
Session 2 knows only what session 1 left on disk. An interrupted session
was cut off on purpose — it is the scenario, not a failure.

| Scenario | condition | mode | session | interrupted | tokens in | cost |
|---|---|---|---|---|---:|---:|
| L1 | bare | n/a | s1 | yes | 583,737 | $0.72 |
| L1 | bare | n/a | s2 | — | 883,631 | $1.01 |
| L1 | sage | n/a | s1 | yes | 1,069,086 | $1.40 |
| L1 | sage | n/a | s2 | — | 2,353,170 | $2.63 |
| L2 | bare | n/a | s1 | — | 91,169 | $0.22 |
| L2 | bare | n/a | s2 | — | 118,154 | $0.19 |
| L2 | bare | n/a | s3 | — | 237,589 | $0.28 |
| L2 | sage | n/a | s1 | — | 252,340 | $0.53 |
| L2 | sage | n/a | s2 | — | 117,300 | $0.29 |
| L2 | sage | n/a | s3 | — | 1,121,888 | $1.49 |
