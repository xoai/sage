# Sage Core

The engine. Everything here is the framework team's responsibility.
Users don't touch core/. Contributors rarely touch core/.

## Philosophy

Core answers two questions: **how does the agent work?** (capabilities, workflows,
gates) and **how do modules plug together?** (contracts define the sockets,
implementations define the plugs).

**Why "capabilities" instead of "skills":** In the broader ecosystem, a "skill" is
the thing users build and share. In Sage, users build **packs** (knowledge) and
**playbooks** (processes). The 18 capabilities here are the framework's internal
engine — onboard, build-loop, implement, tdd, quality-review. They're not
user-extensible in the same way packs are. The files are still named SKILL.md for
Anthropic ecosystem compatibility, but we call them "core capabilities" in all
user-facing documentation to avoid confusion.

**Why contracts live in develop/, not core/:** Contracts define what contributors
need to know to build packs, playbooks, and other modules. That's contributor
tooling, not engine internals. The contracts moved to `develop/contracts/` in the
ring restructure to match this mental model — contributors work in develop/,
the engine lives in core/.

## Ring Architecture

```
sage/
├── core/          ← YOU ARE HERE (the engine)
├── skills/         ← extensible knowledge (community contributes)
├── skills/     ← extensible processes (community contributes)
├── runtime/       ← execution plumbing (tools, MCP, platforms)
├── develop/       ← contributor toolkit (contracts, guides, validators)
└── docs/          ← philosophy (why decisions were made)
```

Core is the innermost ring. It changes rarely and deliberately. Everything
outside core/ is designed to be extended, replaced, or contributed to
by the community.

## Contents

```
core/
├── capabilities/       # 18 core capabilities across 7 categories
│   ├── orchestration/  #   onboard, sage-help, build-loop
│   ├── elicitation/    #   codebase-scan, quick-elicit, deep-elicit
│   ├── planning/       #   specify, plan
│   ├── execution/      #   implement, tdd
│   ├── review/         #   spec-review, quality-review, visual-review
│   ├── debugging/      #   systematic-debug, verify-completion
│   └── context/        #   session-bridge, scope-guard, tool-use
├── workflows/          # 3 mode definitions (fix, build, architect)
├── gates/              # 6 quality gates + 4 deterministic scripts
├── constitution/       # Base principles + presets (startup/enterprise/opensource)
├── agents/             # 5 persona overlays
└── context-loader/     # CLAUDE.md template + assembly logic + loading strategy
```

## Stability Promise

Strict semver. Patch = clarifications. Minor = new optional fields. Major = breaking
changes (rare, requires RFC and migration guide).
