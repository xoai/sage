---
name: "@sage/skill-builder"
description: "Build, validate, and publish Sage skills — discover patterns from source material, draft skill files, validate quality."
version: "1.0.0"
type: bundle
includes:
  - "@sage/pack-discover"
  - "@sage/pack-draft"
  - "@sage/pack-observe"
  - "@sage/pack-source-process"
  - "@sage/pack-validate"
requires:
  sage: ">=1.0.0"
tags: [skill-building, authoring, validation]
---

# Skill Builder

Installs 5 skills for creating new Sage skills:

- **pack-discover** — Find patterns and anti-patterns in source material
- **pack-draft** — Draft skill files with proper structure
- **pack-observe** — Learn from existing codebases
- **pack-source-process** — Process source books and documentation
- **pack-validate** — Validate skill quality against contracts

Note: These skills will be renamed from pack-* to skill-* in a future version.
