# Sage eval results

Does an agent behave better with Sage than without? Same scenario, same
prompts, same graders — the only difference is whether the project was
`sage init`-ed. The delta is the claim.

N = 3 run(s) per scenario per condition; a scenario passes on a
majority of runs. Graders are deterministic — no LLM judge.

| Scenario | sage | bare | delta |
|---|---|---|---|
| L1 | ❌ 0/3 | ✅ 3/3 | **−Sage** |
| L2 | ✅ 3/3 | ✅ 3/3 | same |

**sage 1/2 · bare 2/2** — 2 scenario(s) ran in both conditions. The rest are sage-only (routing, hooks: things Sage adds, not behaviours it improves) and are not counted against bare.

## Cost

Input counts cache creation and cache reads, not just the uncached
remainder. Sage's cost IS its eager layer, so a sage session must read more
than a bare one — counting only uncached input hid exactly that, and
reported 2 input tokens for a session that read 22,809.

| Condition | tokens in | tokens out | cost |
|---|---:|---:|---:|
| sage | 9,556,090 | 123,827 | $12.96 |
| bare | 5,053,069 | 73,851 | $7.00 |

## Sessions — where the cost and the recovery actually happen

A multi-session scenario runs N fresh contexts against ONE workspace.
Session 2 knows only what session 1 left on disk. An interrupted session
was cut off on purpose — it is the scenario, not a failure.

| Scenario | condition | mode | session | interrupted | tokens in | cost |
|---|---|---|---|---|---:|---:|
| L1 | bare | n/a | s1 | yes | 551,630 | $0.68 |
| L1 | bare | n/a | s2 | — | 631,496 | $0.83 |
| L1 | bare | n/a | s1 | yes | 488,695 | $0.60 |
| L1 | bare | n/a | s2 | — | 898,267 | $1.16 |
| L1 | bare | n/a | s1 | yes | 462,624 | $0.62 |
| L1 | bare | n/a | s2 | — | 623,372 | $0.95 |
| L1 | sage | n/a | s1 | yes | 1,208,535 | $1.34 |
| L1 | sage | n/a | s2 | — | 1,281,795 | $1.47 |
| L1 | sage | n/a | s1 | yes | 1,653,753 | $1.77 |
| L1 | sage | n/a | s2 | — | 623,662 | $0.86 |
| L1 | sage | n/a | s1 | yes | 1,218,647 | $1.47 |
| L1 | sage | n/a | s2 | — | 710,596 | $1.19 |
| L2 | bare | n/a | s1 | — | 66,876 | $0.18 |
| L2 | bare | n/a | s2 | — | 116,833 | $0.19 |
| L2 | bare | n/a | s3 | — | 264,306 | $0.37 |
| L2 | bare | n/a | s1 | — | 143,459 | $0.27 |
| L2 | bare | n/a | s2 | — | 93,651 | $0.17 |
| L2 | bare | n/a | s3 | — | 214,142 | $0.27 |
| L2 | bare | n/a | s1 | — | 112,899 | $0.20 |
| L2 | bare | n/a | s2 | — | 117,018 | $0.18 |
| L2 | bare | n/a | s3 | — | 267,801 | $0.34 |
| L2 | sage | n/a | s1 | — | 322,763 | $0.61 |
| L2 | sage | n/a | s2 | — | 155,101 | $0.33 |
| L2 | sage | n/a | s3 | — | 665,878 | $0.93 |
| L2 | sage | n/a | s1 | — | 341,547 | $0.68 |
| L2 | sage | n/a | s2 | — | 154,772 | $0.32 |
| L2 | sage | n/a | s3 | — | 449,879 | $0.62 |
| L2 | sage | n/a | s1 | — | 237,988 | $0.52 |
| L2 | sage | n/a | s2 | — | 118,874 | $0.28 |
| L2 | sage | n/a | s3 | — | 412,300 | $0.56 |
