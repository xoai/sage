# Contracts

Contracts define how Sage modules plug together. They are the PERMANENT part
of the framework — everything else is replaceable.

## Contract Index

| Contract | Governs | Key Principle |
|----------|---------|---------------|
| [skill.contract.md](skill.contract.md) | Skills — composable capabilities | Self-contained, declares inputs/outputs, laws not suggestions |
| [workflow.contract.md](workflow.contract.md) | Workflows — orchestrated sequences | References skills by NAME, defines order and conditions |
| [gate.contract.md](gate.contract.md) | Gates — quality checks | Binary PASS/FAIL, adversarial by design, mandatory by default |
| [constitution.contract.md](constitution.contract.md) | Constitutions — governance principles | Three-tier inheritance, additions only, waivers are explicit |
| [agent.contract.md](agent.contract.md) | Personas — behavioral overlays | Lightweight (<500 tokens), shapes style not substance |
| [extension.contract.md](extension.contract.md) | Extensions — domain packs | Tech-specific bundles, additive not modifying |
| [bundle-skill.contract.md](bundle-skill.contract.md) | Playbooks — discipline processes | Weaves into workflow phases, has own skills, tech-agnostic |
| [adapter.contract.md](adapter.contract.md) | Adapters — platform integration | Declares capabilities, Tier 1/2 model, graceful degradation |
| [template.contract.md](template.contract.md) | Templates — document shapes | Placeholder syntax, variant system, section-level loading |

## Two Pack Types: Extensions vs Playbooks

Sage distinguishes between technology knowledge and discipline processes:

**Domain packs** (`react`, `web`) ADD new capabilities —
patterns, gates, and constitution rules specific to a technology. They activate
from codebase detection and pull toward the RIGHT side of the workflow
(implementation, review, verification).

**Playbooks** (`play-ux-design`, `play-product-management`) are structured
discipline-specific processes with their own skills. They WEAVE INTO existing
workflow phases at defined integration points. They activate by mode depth
(light for BUILD, full for ARCHITECT) and pull toward the LEFT side of the
workflow (discovery, specification, planning). Each playbook declares its own
discipline-specific phases (e.g., Discovery → Planning → Delivery for PM,
Research → Design → Evaluate for UX).

The litmus test: **"If I switch my entire tech stack, does this pack still apply?"**
Yes → playbook. No → domain extension.

## How Contracts Relate

```
Constitution ─────────────────────────────────────────────────────────────┐
  (always active, governs everything)                                     │
                                                                          │
Workflow ◄─── Playbook (weaves discipline skills into workflow phases)     │
  │ references by name                                                    │
  ├── Skill ◄── Persona (behavioral overlay)                              │
  │     │                                                                 │
  │     ├── uses Template (document shape)                                │
  │     ├── loads references/ on demand                                   │
  │     └── declares inputs/outputs                                       │
  │                                                                       │
  ├── Gate (runs after skill, verifies quality) ◄─── checks against ──────┘
  │     └── PASS/FAIL → continue or fix-and-retry
  │
  └── Adapter (translates workflow execution to platform capabilities)

Extension (domain)                  Playbook (discipline)
  └── ADDS: patterns + gates +        └── WEAVES IN: own skills + gates +
      constitution rules                   constitution + persona enrichments
      (tech-specific, right side)          (tech-agnostic, left side)
```

## The Stability Promise

Contracts use strict semver:

- **Patch** (1.0.x): Clarifications, typos, additional examples. No module breakage.
- **Minor** (1.x.0): New optional fields. Existing modules still work unchanged.
- **Major** (x.0.0): Breaking changes. Requires migration. Announced via RFC.

We will not break your modules without a major version bump.

## Reading Guide for Contributors

- **Building a skill?** Read `skill.contract.md` thoroughly. Read the others at summary level.
- **Building a workflow?** Read `workflow.contract.md` + `skill.contract.md` (to understand what you're orchestrating).
- **Building a gate?** Read `gate.contract.md` + `constitution.contract.md` (gates enforce constitutions).
- **Building an extension?** Read `extension.contract.md` + all contracts it bundles.
- **Building a playbook?** Read `bundle-skill.contract.md` + `skill.contract.md` (playbooks contain skills) + `workflow.contract.md` (playbooks integrate into workflows).
- **Building a platform?** Read `adapter.contract.md` + `workflow.contract.md` (to understand what you're translating).
