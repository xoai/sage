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
| `CLAUDE.md` | 398 | 4,433 | 430 | ✅ |

## Per-command layer

Paid only when the command runs — but paid in full: the generator inlines
each workflow rather than pointing at it.

| Command | Lines | ~Tokens | Budget | |
|---|---:|---:|---:|---|
| `/build` | 535 | 5,888 | 580 | ✅ |
| `/fix` | 465 | 4,684 | 505 | ✅ |
| `/architect` | 409 | 4,521 | 445 | ✅ |
| `/learn` | 203 | 1,958 | 220 | ✅ |
| `/reflect` | 186 | 1,569 | 205 | ✅ |
| `/autoresearch` | 174 | 1,728 | 190 | ✅ |
| `/continue` | 137 | 1,205 | 150 | ✅ |
| `/review` | 126 | 1,131 | 140 | ✅ |
| `/sage` | 54 | 428 | 70 | ✅ |

## Totals

- Eager: **398 lines** (~4,433 tokens) on every turn.
- Heaviest command: **/build at 535 lines** (~5,888 tokens), on top of the eager layer.
