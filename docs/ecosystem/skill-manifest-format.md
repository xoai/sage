# Skill Manifest Format

The skill manifest is YAML frontmatter at the top of `SKILL.md`. **All fields
are optional.** A bare SKILL.md with just instructions and no frontmatter is a
valid skill (Layer 0).

## Complete Reference

```yaml
---
# ── Identity (optional) ──
name: "react"
version: "2.1.0"
description: "React component patterns, state management, and performance"

# ── Integration (optional) ──
type: knowledge              # knowledge | process | composite | bundle
layer: framework             # domain | framework | stack

# ── Relationships (optional) ──
extends: "react"      # "I'm a stricter version" (at most one)
replaces: "react"     # "I'm a complete alternative" (at most one)
complements:                 # "I work alongside these"
  - "web"

# ── Dependencies (optional) ──
requires:
  sage: ">=1.0.0"
  skills:
    - "react@^2.0.0"

# ── Bundle members (type: bundle only) ──
includes:
  - "jtbd"
  - "prd"

# ── Ecosystem (optional) ──
author: "sage-team"
license: "MIT"
tags: ["react", "frontend"]
sources: ["React documentation"]

# ── Detection (optional) ──
activates-when:
  detected: [react, react-dom]

# ── Sage integration (optional, advanced) ──
integrates-at:
  specification:
    runs: alongside
    mode-depth: { build: light, architect: full }
provides: [react-component-patterns]
constitution-additions: "constitution.md"
gates: ["quality-gate.md"]
---
```

## Defaults When Fields Are Missing

| Field | Default |
|-------|---------|
| name | Folder name |
| version | "0.0.0" (unversioned) |
| type | knowledge |
| layer | None (no auto-detection) |
| extends | Nothing (standalone) |
| replaces | Nothing (doesn't deactivate anything) |
| complements | Nothing (coexists with everything) |
| requires | No requirements |

## Compatibility Layers

| Layer | What's Needed | What Sage Does |
|-------|--------------|----------------|
| 0 | Just SKILL.md with instructions | Loads into context. User configures manually. |
| 1 | SKILL.md + type/version frontmatter | Smart integration based on type. |
| 2 | Full manifest with relationships | Full ecosystem: extends/replaces/complements. |
