---
name: flag-parser
description: >
  Parses workflow flags (--quality-locked, --autonomous) from $ARGUMENTS
  at the start of /build and /architect commands. Sets workflow runtime
  state, persists to manifest, and returns the cleaned goal string.
version: "1.0.0"
type: process
---

# Flag Parser

Workflow flags are passed inline in slash command arguments. Both
`/build` and `/architect` accept the same two flags, parsed identically.
This capability defines the parsing contract.

## Supported Flags

| Flag | Effect | Default |
|------|--------|---------|
| `--quality-locked` | Loop review/revise until findings are clean or cap (10) hit | off |
| `--autonomous` | Agent makes elicitation decisions from memory/codebase/principles | off |

Flags are independent. Either, both, or neither can be set.

## Parsing Rules

1. **Flags must appear before the goal description.** Flags at the end
   are not parsed — they're treated as part of the goal text.
2. **Flag order doesn't matter.** `--autonomous --quality-locked` and
   `--quality-locked --autonomous` are equivalent.
3. **Unknown flags are an error.** If $ARGUMENTS starts with `--` and
   the flag name isn't recognized, surface a clear error:
   ```
   Sage: Unknown flag `--foo`. Supported: --quality-locked, --autonomous
   ```
4. **No values, just booleans.** Neither flag takes an argument.
   `--quality-locked=true` is not supported (use bare `--quality-locked`).
5. **Goal is everything after the flags.** Whitespace between flags
   and the goal is trimmed.

## Parsing Algorithm

```
INPUT: $ARGUMENTS (string)
OUTPUT: quality_locked_mode (bool), autonomous_mode (bool), goal (string)

quality_locked_mode = false
autonomous_mode = false
remaining = $ARGUMENTS.trim()

WHILE remaining starts with "--":
  first_word = remaining.split(whitespace)[0]
  IF first_word == "--quality-locked":
    quality_locked_mode = true
  ELIF first_word == "--autonomous":
    autonomous_mode = true
  ELSE:
    ERROR: "Unknown flag `{first_word}`."
  remaining = remaining[len(first_word):].lstrip()

goal = remaining
```

## Examples

```
$ARGUMENTS = "Ship dark mode"
→ quality_locked_mode = false
→ autonomous_mode = false
→ goal = "Ship dark mode"

$ARGUMENTS = "--quality-locked Ship dark mode"
→ quality_locked_mode = true
→ autonomous_mode = false
→ goal = "Ship dark mode"

$ARGUMENTS = "--autonomous --quality-locked Ship dark mode"
→ quality_locked_mode = true
→ autonomous_mode = true
→ goal = "Ship dark mode"

$ARGUMENTS = "--quality-locked"
→ quality_locked_mode = true
→ autonomous_mode = false
→ goal = "" (workflow may scan .sage/work/ for active initiative)

$ARGUMENTS = "Ship --quality-locked dark mode"
→ quality_locked_mode = false (flag not at start)
→ autonomous_mode = false
→ goal = "Ship --quality-locked dark mode"

$ARGUMENTS = "--foo bar"
→ ERROR: "Unknown flag `--foo`. Supported: --quality-locked, --autonomous"
```

## Announcement

After parsing, the workflow announces active modes (if any) before
starting work:

```
Sage → build workflow.
Modes: --quality-locked, --autonomous
Goal: Ship dark mode for the dashboard
```

If neither flag is set, omit the Modes line entirely.

## Manifest Persistence

After parsing, before starting Step 1, the workflow writes flag state
to manifest.md frontmatter:

```yaml
flags:
  quality_locked: true
  autonomous: true
```

On `/continue`, the workflow reads these fields and restores both
modes for the duration of the session.

## Failure Modes

- **Empty $ARGUMENTS + no active initiative:** workflow falls back to
  asking for the goal interactively, with no flags active.
- **Flag followed by no goal:** valid — workflow scans `.sage/work/`
  for an in-progress initiative matching the flag state.
- **Conflicting flag values on `/continue`:** the user's new invocation
  overrides the manifest's stored flags. Note this to the user.

## Quality Criteria

- Parser is deterministic — same input always produces same output
- Error messages name the unknown flag and list supported flags
- Goal preserves user-supplied whitespace and casing
- Flag state is announced and persisted before any artifact work begins
