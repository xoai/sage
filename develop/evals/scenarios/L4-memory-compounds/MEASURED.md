# First measurement campaign — 2026-07-16/17 (v1–v3)

**The compounding MECHANISM is proven; the behavioral edge over rereading is not.**

Mechanism (sage arm, every graded run, 12/12 checks across v2+v3): stored in s1,
stored again in s3, retrieved in s4 — through the exact stack `sage init` writes
(.mcp.json → uvx → .sage-memory/). Accumulation and joint retrieval work.

Behavior at this horizon (4 sessions, one workspace): **bare ties or better.**
v3: bare 3/3 — honored all three never-restated conventions by rereading its own
logs, $2.17/run. Sage: 2 of 3 runs produced fully compliant trees (both
functions, raise ConfigError, no sleep in code, 3.8 typing) but were VOIDED by a
driver bug (below); the third spent its budget on ceremony (two approval
checkpoints + sub-agent review + close-out bookkeeping) and never implemented —
the L1 disease on the fresh-cycle path. Sage ~$9–14/run vs bare ~$2.

Instrument lessons (three iterations, matching L1/L2 history):
- v1–v2: the checkpoint trap (headless [A], the E5 lesson — fixed with a second
  turn) and the conscientiousness trap (code_only unset; a docstring citing
  time.sleep failed the arm that avoided it) and a file-level-unpassable check.
- v3 DRIVER BUG (open): `error_max_budget_usd` on a --resume continuation turn
  is classified "platform errored and nothing ran ... unknown error" and VOIDS
  the run — after $6+ of real, committed work. That contradicts the load-bearing
  void-vs-truncated rule (tokens read → truncated+graded). test_driver does not
  pin this shape. Fix before the next multi-turn scenario.

What remains untested: the regime where memory can beat rereading — a workspace
WITHOUT the log (fresh clone, teammate, cross-project). That is the strong-case
experiment for any "compounds" claim.
