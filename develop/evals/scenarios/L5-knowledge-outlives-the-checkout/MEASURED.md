# First measurement — 2026-07-17 (N=3 both arms, kept)

**With the structurally-broken freeze check removed (see rationale v2): sage 3/3,
bare 3/3 — the rule survived the fresh checkout in BOTH arms.** Sage $5.97/run,
bare $0.73/run (~8×).

**The finding that ends the L-series arc:** even in the constructed regime where
git cannot carry the rule and the repo channel is frozen shut, the "bare" agent
is not memoryless — it used **Claude Code's own per-project auto-memory**
(`~/.claude/projects/<cwd>/memory/`), wrote the rule there in s1, read it back in
the fresh checkout in s2, and honored it 3/3. (One run also escalated to the
user-global CLAUDE.md — resourceful, and also real-environment pollution: the
harness must isolate HOME before more memory-flavoured scenarios run.)

Sage's mechanism was again flawless (store 3/3, search 3/3, memory_home survived
the checkout). So across L2 → L4 → L5 the pattern is now complete:

    L2: the session log carried it        → bare tied
    L4: the committed code carried it     → bare tied
    L5: the platform's memory carried it  → bare tied, at 1/8th the cost

sage-memory works. It has not yet found a regime where the alternatives fail.
The remaining candidate is CROSS-PROJECT knowledge (platform auto-memory is
per-cwd; sage-memory's global/hub scope crosses projects) — untested, and the
last untested regime on the map.
