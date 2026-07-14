# Sage eval results

Does an agent behave better with Sage than without? Same scenario, same
prompts, same graders — the only difference is whether the project was
`sage init`-ed. The delta is the claim.

N = 3 run(s) per scenario per condition; a scenario passes on a
majority of runs. Graders are deterministic — no LLM judge.

| Scenario | sage | bare | delta |
|---|---|---|---|
| L1 *(inline)* | ✅ 3/3 | — *n/a* | *sage-only* |
| L1 *(subagents)* | ❌ 0/3 | — *n/a* | *sage-only* |

**sage 1/2 · bare 0/0** — 0 scenario(s) ran in both conditions. The rest are sage-only (routing, hooks: things Sage adds, not behaviours it improves) and are not counted against bare.

## Cost

Input counts cache creation and cache reads, not just the uncached
remainder. Sage's cost IS its eager layer, so a sage session must read more
than a bare one — counting only uncached input hid exactly that, and
reported 2 input tokens for a session that read 22,809.

| Condition | tokens in | tokens out | cost |
|---|---:|---:|---:|
| sage | 19,408,872 | 223,384 | $73.64 |

## Execution mode — inline vs. subagents

The same scenarios, the same graders, the sage condition throughout.
The only variable is whether each plan task was implemented and reviewed
by fresh subagent contexts (ADR-10) or by the inline loop. Wall time is
the mean across runs, not the sum — it is a latency, not a bill.

| Mode | passed | tokens in | tokens out | cost | mean wall |
|---|---|---:|---:|---:|---:|
| inline | 1/1 | 16,883,356 | 192,296 | $64.75 | 23.7 min |
| subagents | 0/1 | 2,525,516 | 31,088 | $8.89 | 4.2 min |

This table reports what the two modes COST and whether they PASS. It does
not report which produces better code — no grader here reads for quality,
and none should pretend to. That comparison needs a different instrument.

## Sessions — where the cost and the recovery actually happen

A multi-session scenario runs N fresh contexts against ONE workspace.
Session 2 knows only what session 1 left on disk. An interrupted session
was cut off on purpose — it is the scenario, not a failure.

| Scenario | condition | mode | session | interrupted | tokens in | cost |
|---|---|---|---|---|---:|---:|
| L1 | sage | inline | s1 | yes | 1,285,694 | $1.50 |
| L1 | sage | inline | s2 | — | 3,420,206 | $12.19 |
| L1 | sage | inline | s1 | yes | 2,625,271 | $7.69 |
| L1 | sage | inline | s2 | — | 3,902,047 | $13.66 |
| L1 | sage | inline | s1 | yes | 2,454,315 | $17.16 |
| L1 | sage | inline | s2 | — | 3,195,823 | $12.54 |
| L1 | sage | subagents | s1 | yes | 2,525,516 | $8.89 |
| L1 | sage | subagents | s2 | — | 0 | $0.00 |
| L1 | sage | subagents | s1 | yes | 0 | $0.00 |
| L1 | sage | subagents | s2 | — | 0 | $0.00 |
| L1 | sage | subagents | s1 | yes | 0 | $0.00 |
| L1 | sage | subagents | s2 | — | 0 | $0.00 |
