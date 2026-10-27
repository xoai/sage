# Context budget

What Sage costs a model, measured against a real `sage init --preset base`
project rather than against the source templates — the model reads the
generated output, and the two are not the same file.

Tokens are estimated at chars/4. That is a heuristic, useful for
comparing releases to each other, not for quoting as an exact figure.

## Eager layer

Loaded on every turn of every session. This is the one that matters.

| File | Lines | ~Tokens | Budget | |
|---|---:|---:|---:|---|
| `CLAUDE.md` | 232 | 2,756 | 235 | ✅ |

## Per-command layer

Paid only when the command runs — but paid in full: the generator inlines
each workflow rather than pointing at it.

| Command | Lines | ~Tokens | Budget | |
|---|---:|---:|---:|---|
| `/build` | 599 | 6,899 | 600 | ✅ |
| `/fix` | 485 | 5,011 | 505 | ✅ |
| `/architect` | 419 | 4,661 | 445 | ✅ |
| `/learn` | 203 | 1,958 | 220 | ✅ |
| `/reflect` | 186 | 1,569 | 205 | ✅ |
| `/autoresearch` | 174 | 1,728 | 190 | ✅ |
| `/continue` | 149 | 1,410 | 150 | ✅ |
| `/review` | 126 | 1,131 | 140 | ✅ |
| `/sage` | 54 | 428 | 70 | ✅ |

## On-demand layer (system skills)

Content ADR-9 moved out of the eager layer. Fetched only when the
platform's description-triggered discovery matches — so the TOTAL below is
not a per-turn cost, and a session that never asks about tiers never pays
for `sage-tiers`.

It is measured anyway, because the diet is only real if someone counts both
halves. Relocating cost from a file paid every turn to a file paid on demand
is a genuine win; relocating it into a file nobody measures is an accounting
trick that reads exactly the same in a release note.

| Skill | Lines | ~Tokens | Budget | |
|---|---:|---:|---:|---|
| `sage-gates` | 139 | 1,549 | 160 | ✅ |
| `sage-routing` | 99 | 912 | 105 | ✅ |
| `sage-checkpoints` | 95 | 891 | 96 | ✅ |
| `sage-using-memory` | 77 | 794 | 90 | ✅ |
| `sage-constitution` | 75 | 957 | 87 | ✅ |
| `sage-decisions` | 69 | 699 | 80 | ✅ |
| `sage-tiers` | 64 | 725 | 70 | ✅ |

## Generic platform

Platforms with no skill discovery (Cursor, Copilot, Windsurf, …) cannot
fetch on demand, so the same content is INLINED into their instructions
file. Their eager layer is therefore larger — necessarily, not accidentally.

This row exists so that number is visible instead of hiding inside
claude-code's. Delivery is capability-gated (ADR-11); the cost of a platform
that cannot fetch on demand is that it carries everything.

| File | Lines | ~Tokens | Budget | |
|---|---:|---:|---:|---|
| `CLAUDE.md` | 788 | 8,425 | 810 | ✅ |

## Totals

- Eager: **232 lines** (~2,756 tokens) on every turn.
- On-demand: **618 lines** (~6,527 tokens) across 7 system skills — paid per skill, per use, never all at once.
- Generic platform eager: **788 lines** — everything inlined, because nothing there can fetch.
- Heaviest command: **/build at 599 lines** (~6,899 tokens), on top of the eager layer.

