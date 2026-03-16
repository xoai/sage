# Knowledge Skill Contract

**Version:** 1.0.0
**Status:** Stable

An extension is a domain-specific pack that adds skills, gates, constitution principles,
and templates to Sage. Extensions are the mechanism for specialization — the core
framework handles universal software engineering; extensions handle domain knowledge.

---

## Required Directory Structure

```
skills/@sage/<extension-name>/
├── SKILL.md manifest            # REQUIRED — Manifest declaring what the extension provides
├── README.md                 # REQUIRED — What this extension does, who it's for
│
├── core/capabilities/                   # OPTIONAL — Domain-specific skills
│   └── <skill-name>/
│       ├── SKILL.md          # Must satisfy skill.contract.md
│       └── ...
│
├── core/gates/                    # OPTIONAL — Domain-specific quality gates
│   └── <NN>-<gate-name>.gate.md  # Must satisfy gate.contract.md
│
├── core/constitution/             # OPTIONAL — Constitution additions
│   └── <n>.constitution-additions.md
│
├── develop/templates/                # OPTIONAL — Domain-specific document templates
│   └── <n>-template.md
│
└── core/agents/                   # OPTIONAL — Domain-specific personas
    └── <n>.persona.md        # Must satisfy agent.contract.md
```

---

## Required Manifest (SKILL.md manifest)

```yaml
---
name: <string>                 # Scoped name, e.g., "@sage/web" or "community-gamedev"
description: <string>          # What agent mistakes this pack corrects
version: <semver>
license: <string>              # e.g., "MIT", "Apache-2.0"
layer: <1|2|3>                 # 1=domain, 2=framework, 3=stack composition

# What this pack provides (all optional, at least one must be non-empty)
provides:
  skills: [<skill-names>]
  gates: [<gate-names>]
  constitution-additions: [<filenames>]
  templates: [<filenames>]
  agents: [<persona-names>]

# Dependencies
requires:
  sage-core: <semver-range>   # Minimum Sage core version
  packs: [<names>]             # Other packs this depends on (L2 requires L1, L3 requires L2)

# Activation
activates-in: [<modes>]        # Which modes this pack's guidance applies to

activates-when:
  detected: [<packages>]       # Package names in package.json, pubspec.yaml, etc.

# Accuracy tracking
framework-version: <semver-range>  # What framework version this targets
last-verified: <date>              # When accuracy was last checked (YYYY-MM-DD)
---
```

### Required Files

In addition to `SKILL.md manifest`, every pack MUST include:

- `README.md` — What the skill does and what's included
- `tests.md` — 3+ test prompts demonstrating behavior change (see Pack Scorecard)
- At least one of: `patterns/`, `anti-patterns/`, or `constitution/` with content

---

## Behavioral Contract

Extensions MUST:

1. **Satisfy sub-contracts**. Every skill in the extension must satisfy `skill.contract.md`.
   Every gate must satisfy `gate.contract.md`. Every persona must satisfy `agent.contract.md`.
   Extensions are bundles of standard modules, not special cases.
2. **Be self-contained**. Installing an extension should not break existing functionality.
   Extension skills, gates, and personas ADD capabilities — they don't modify core modules.
3. **Declare everything in the manifest**. If an extension provides a skill, it MUST be
   listed in `SKILL.md manifest`. Hidden modules are not allowed.
4. Use **gate order 50+** for extension gates. Orders 01-49 are reserved for core gates.

Extensions MUST NOT:

1. **Replace core modules** without declaring `replaces` in the relevant module's frontmatter.
   Silent shadowing of core modules is a bug, not a feature.
2. **Require themselves**. Extensions are always optional. Core workflows must function
   without any extensions installed.
3. **Conflict with other extensions**. If two extensions provide skills with the same name,
   the conflict must be documented and the resolution must be explicit in project config.

---

## Constitution Additions

Extensions can add domain-specific principles to the constitution. These additions:

- Are injected at Tier 2 (project level) when the extension is enabled.
- Follow the same inheritance rules — they ADD, never remove.
- Are only active when the extension is enabled in `.sage/config.yaml`.

```markdown
# web.constitution-additions.md

## Web Extension Principles

1. All user-facing pages MUST be accessible (WCAG 2.1 AA minimum).
2. No inline styles. All styling through CSS classes or CSS-in-JS.
3. Images MUST have alt text. No exceptions.
4. Client-side JavaScript MUST have a no-JS fallback for critical paths.
```

---

## Installation and Activation

Packs are installed by placing them in `skills/@sage/` (bundled) or
`.sage/skills/@sage/` (project-local). They are activated in `.sage/config.yaml`:

```yaml
packs:
  enabled: [web, backend, security]
```

Enabling a knowledge skill:
1. Registers its skills in the skill registry
2. Registers its gates in the gate configuration
3. Merges its constitution additions into the effective constitution
4. Makes its templates available to skills
5. Makes its personas available for skill binding

---

## Project Overlays

A project overlay customizes a community pack with project-specific conventions,
constraints, and patterns. Overlays sit alongside community packs and add
context without modifying the shared pack.

### Overlay Structure

```
.sage/skills/@sage/<pack-name>/
├── SKILL.md manifest          # type: overlay, extends: @sage/<community-pack>
└── overrides.md       # Project-specific additions (≤500 tokens)
```

### Overlay Manifest

```yaml
---
name: "@project/<pack-name>"
type: overlay
extends: "@sage/<community-pack-name>"
version: "1.0.0"
---
```

### Loading Order

When both a community pack and a project overlay exist for the same framework:

```
1. Community pack loaded first     (skills/@sage/<name>/ — shared patterns)
2. Project overlay loaded second   (.sage/skills/@sage/<name>/ — project rules)
```

The overlay ADDS to the community pack — it does not replace it.
If the overlay contradicts the community pack, the overlay wins for this
project (project-specific rules override community defaults).

### What Belongs in an Overlay

- Team naming conventions (query key format, file naming, etc.)
- Forbidden patterns ("we can't use suspense because of legacy error boundaries")
- Required patterns ("all API calls go through our apiClient wrapper")
- Project-specific API formats (response envelopes, error structures)
- Architecture constraints ("no direct database access from components")

### What Does NOT Belong in an Overlay

- Anything the community pack already covers (don't duplicate)
- General best practices (those go in the community pack)
- Temporary workarounds (put those in .sage/decisions.md instead)

