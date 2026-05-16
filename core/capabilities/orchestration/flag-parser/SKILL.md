---
name: flag-parser
description: >
  Parses workflow flags (--quality-locked, --autonomous) from $ARGUMENTS
  at the start of /build and /architect commands. Uses deterministic
  runtimes (Python primary, Bash fallback) with prose-rule fallback
  if neither runtime is available. Returns a strict JSON contract that
  the agent trusts unconditionally.
version: "1.1.0"
type: process
---

# Flag Parser

Workflow flags are passed inline in slash command arguments. Both
`/build` and `/architect` accept the same flags, parsed identically.

**Parsing must be deterministic.** Prose-only parsing by the agent is
unreliable — the runtime layers below produce the same JSON output and
the agent trusts that JSON unconditionally.

## Supported Flags

| Flag | Effect | Default |
|------|--------|---------|
| `--quality-locked` | Loop review/revise until findings are clean or cap (10) hit | off (overridable by config) |
| `--no-quality-locked` | Force off, overriding a config default | — |
| `--autonomous` | Agent makes elicitation decisions from memory/codebase/principles | off (overridable by config) |
| `--no-autonomous` | Force off, overriding a config default | — |

## Precedence (highest wins)

For each mode (quality_locked, autonomous):

| Priority | Source | Effect | Source label |
|----------|--------|--------|--------------|
| 1 (highest) | `--no-<flag>` | Force off | `"flag"` |
| 2 | `--<flag>` | Force on | `"flag"` |
| 3 | `<flag>: true` in `.sage/config.yaml` | Default on | `"config"` |
| 4 (lowest) | nothing | Off (current behavior) | `null` |

**Flag vs config when they agree:** the source label is `"flag"`
(explicit intent always labels, even when the value matches config).
Functional outcome is the same (mode on).

**Conflict:** passing `--<flag>` AND `--no-<flag>` in the same invocation
is a user error. The parser returns an error JSON and exits non-zero.

## Config File Defaults

Read from `.sage/config.yaml`. Strict-match contract: only lines
matching exactly `<key>: true` (with one space after the colon,
lowercase `true`, no trailing characters) are honored. The strict form
ensures Python and Bash agree byte-for-byte. Rejected variants
(treated as no default):

- `quality_locked: True` (titlecase)
- `quality_locked: "true"` (quoted)
- `quality_locked: yes` (YAML alias)
- `quality_locked:true` (no space)
- `quality_locked:  true` (extra space)
- `quality_locked: true  # comment` (trailing content)
- Any nested/indented key (only top-level keys are read)

`quality_locked: false` is equivalent to no default — value is off.
Use the `--quality-locked` flag to override.

## JSON Contract

All three parsing layers emit the same JSON shape to stdout:

```json
{
  "quality_locked": true | false,
  "autonomous": true | false,
  "goal": "<remainder after flags, trimmed>",
  "error": null | "<error message>",
  "quality_locked_source": "flag" | "config" | null,
  "autonomous_source": "flag" | "config" | null
}
```

Source value is `"flag"` whenever a flag (positive `--X` or negative
`--no-X`) influenced the result. `"config"` only when no flag was
passed AND config provides the default-on. `null` when the value is
the implicit default-off.

Exit code semantics:
- `0` — clean parse (`error: null`)
- `1` — unknown flag, conflicting flags, or malformed input
  (`error` is populated; JSON still printed)

## Parsing Order (Try Each Layer)

The agent tries each layer in order. As soon as one returns valid JSON,
use it and skip the rest.

### Layer 1 — Python (primary, preferred)

```bash
python -m core.flag_parser parse "$ARGUMENTS" --config-path .sage/config.yaml
```

The `--config-path` is optional — when provided, the parser reads
`quality_locked: true` / `autonomous: true` lines as defaults. When
omitted (or the file is missing/malformed), no defaults apply.

Outputs JSON to stdout. Exit 0 on clean parse, 1 on unknown flag or
conflict.

### Layer 2 — Bash fallback (when Python unavailable)

```bash
bash sage/core/flag_parser/parse.sh "$ARGUMENTS" --config-path .sage/config.yaml
```

Same JSON shape, same exit codes. Uses only POSIX bash features —
works on macOS bash 3.2+ and any Linux bash.

### Layer 3 — Prose-rule fallback (last resort)

Use ONLY when both Python and Bash are unavailable (rare — locked-down
container, embedded environments). The agent reads the parsing rules
below and produces JSON manually.

**Announce when falling back:**

```
Sage: Deterministic parsers unavailable (Python and Bash both failed).
Using prose-rule fallback for flag parsing.
```

This is the only case where prose parsing is acceptable.

## Parsing Rules (used by all three layers)

1. **Flags must appear before the goal description.** Flags at the end
   are not parsed — they're treated as part of the goal.
2. **Flag order doesn't matter.** `--autonomous --quality-locked` and
   `--quality-locked --autonomous` are equivalent.
3. **Unknown flags are an error.** If $ARGUMENTS starts with `--` and
   the flag name isn't recognized, return JSON with `error` populated.
4. **No values, just booleans.** Neither flag takes an argument.
   `--quality-locked=true` is not supported.
5. **Goal is everything after the flags.** Surrounding whitespace
   trimmed; internal whitespace preserved.

## Examples

```
INPUT:  "Ship dark mode"
OUTPUT: {"quality_locked": false, "autonomous": false, "goal": "Ship dark mode", "error": null}

INPUT:  "--quality-locked Ship dark mode"
OUTPUT: {"quality_locked": true, "autonomous": false, "goal": "Ship dark mode", "error": null}

INPUT:  "--autonomous --quality-locked Ship dark mode"
OUTPUT: {"quality_locked": true, "autonomous": true, "goal": "Ship dark mode", "error": null}

INPUT:  "--quality-locked"
OUTPUT: {"quality_locked": true, "autonomous": false, "goal": "", "error": null}

INPUT:  "Ship --quality-locked dark mode"   # flag not at start
OUTPUT: {"quality_locked": false, "autonomous": false, "goal": "Ship --quality-locked dark mode", "error": null}

INPUT:  "--foo bar"
OUTPUT: {"quality_locked": false, "autonomous": false, "goal": "", "error": "Unknown flag '--foo'. Supported flags: --quality-locked, --autonomous."}
EXIT:   1
```

## After Parsing

### On clean parse (error: null)

1. Use `quality_locked` and `autonomous` booleans for the rest of the
   workflow.
2. Use `goal` as the user's task description (may be empty — workflow
   will auto-pickup from `.sage/work/`).
3. Announce active modes (if any) before starting work:

```
Sage → build workflow.
Modes: --quality-locked, --autonomous
Goal: Ship dark mode for the dashboard
```

If both flags are false, omit the Modes line entirely.

### On error (error populated)

Surface the error verbatim to the user and stop the workflow:

```
Sage: {error message}
```

Do NOT guess what the user meant. Wait for them to retry with the
correct flag name.

## Manifest Persistence

After successful parsing, before starting Step 1, the workflow writes
flag state to manifest.md frontmatter:

```yaml
flags:
  quality_locked: true
  autonomous: true
```

On `/continue`, the workflow reads these fields and restores both
modes for the duration of the session.

## Failure Modes

| Situation | Behavior |
|---|---|
| Python missing | Fall through to Bash layer automatically |
| Bash failed (e.g., parse.sh missing) | Fall through to prose-rule layer |
| Unknown flag | Surface error message, stop workflow |
| Empty $ARGUMENTS | Both modes off, empty goal — workflow may scan `.sage/work/` for active initiative |
| `/continue` overrides | New invocation's flags override manifest; note to user |

## Quality Criteria

- Parser is deterministic — same input always produces same output
- All three layers produce IDENTICAL JSON for the same input (verified by parity tests)
- Error messages name the unknown flag and list supported flags
- Goal preserves user-supplied whitespace and casing
- Flag state is announced and persisted before any artifact work begins
- Prose-fallback announcement is mandatory so the user knows reliability is degraded
