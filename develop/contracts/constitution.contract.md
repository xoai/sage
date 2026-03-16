# Constitution Contract

**Version:** 1.0.0
**Status:** Stable

A constitution is a set of immutable principles that govern how all agents, skills,
and workflows operate within a project. Constitutions constrain — they define what
MUST and MUST NOT happen, regardless of what any individual skill or agent decides.

The constitution is the highest authority in Sage. When a skill's instructions conflict
with the constitution, the constitution wins. Always.

---

## The Three-Tier Model

Constitutions inherit in a strict hierarchy. Lower tiers ADD constraints.
Lower tiers CANNOT REMOVE constraints from higher tiers.

```
Tier 1: Organization    ~/.sage/constitution.md
                         ↓ inherits (additions only)
Tier 2: Project         .sage/constitution.md
                         ↓ inherits (additions only)
Tier 3: Feature         .sage/work/<NNN>-<name>/context.md
```

At runtime, the context loader MERGES all three tiers into a single effective
constitution. The merge rules:

- All principles from Tier 1 are included (cannot be removed).
- All principles from Tier 2 are added (cannot contradict Tier 1).
- Tier 3 adds feature-specific constraints (cannot contradict Tier 1 or 2).
- Waivers are the ONLY mechanism to exempt a principle (see Waivers below).

---

## Required File Format

Constitution files are markdown with YAML frontmatter:

```yaml
---
# REQUIRED FIELDS
name: <string>                 # e.g., "acme-corp", "photo-app", "auth-feature"
tier: <integer>                # 1 (org), 2 (project), or 3 (feature)
version: <semver>

# OPTIONAL FIELDS (Tier 2 and 3 only)
extends: <string>              # Name of a preset constitution to build on
                               # e.g., "enterprise", "startup", "healthcare"
                               # Resolves to constitution/presets/<name>.constitution.md
---
```

## Constitution Body Structure

```markdown
---
(frontmatter)
---

# <Constitution Name>

## Principles

<Numbered list of immutable principles. Each principle is a clear,
enforceable statement. Vague principles are useless — if a gate
can't check it, it shouldn't be a principle.>

## Additions

<Additional principles specific to this tier. These supplement,
never contradict, inherited principles.>

## Waivers

<Explicit exemptions from specific principles, with justification
and approval. See Waiver format below.>
```

---

## Principle Format

Principles should be written as enforceable rules, not aspirational goals.

**Good** (enforceable — a gate can check this):
```markdown
1. All API endpoints MUST require authentication. No public endpoints
   without explicit waiver.
2. Every database migration MUST be reversible.
3. No third-party dependency may be added without a license check.
```

**Bad** (vague — a gate cannot check this):
```markdown
1. Code should be high quality.
2. We value security.
3. Performance matters.
```

Each principle SHOULD map to at least one gate check. The `constitution-compliance`
gate (Gate 02) evaluates code against the effective merged constitution.

---

## Waiver Format

Waivers are the ONLY way to exempt code from a principle. They must be explicit.

```markdown
## Waivers

### Waiver: <principle number or name>
- **Reason:** <Why this principle doesn't apply here>
- **Scope:** <What specific part of the codebase is exempt>
- **Approved by:** <Who approved this, and when>
- **Expires:** <When this waiver should be re-evaluated, or "never">
```

Waiver rules:
- Waivers MUST have a reason. "It's too hard" is not a valid reason.
- Waivers MUST have a scope. Blanket waivers for entire principles are red flags.
- Waivers SHOULD have an expiration date for re-evaluation.
- Waivers are visible in gate output. When Gate 02 runs, it reports which
  principles were checked, which passed, and which were waived.

---

## Preset Constitutions

The `core/constitution/presets/` directory provides pre-built constitutions for
common scenarios. Projects extend these rather than writing from scratch.

Each starter MUST:
1. Declare `tier: 2` (they're project-level templates).
2. Include enforceable principles (not vague aspirations).
3. Include a README.md explaining the rationale for each principle.
4. Include examples of valid and invalid code for each principle.

---

## Behavioral Contract

Constitutions MUST:

1. Contain **enforceable principles** that a gate can verify against code.
2. Follow the **inheritance hierarchy** — lower tiers add, never remove.
3. Document **waivers explicitly** with reason, scope, approver, and expiration.

Constitutions MUST NOT:

1. Contain **implementation details**. Principles say WHAT, not HOW.
   "All APIs must be authenticated" is a principle.
   "Use JWT with RS256" is an implementation detail (belongs in architecture.md).
2. **Contradict higher tiers**. A project constitution cannot override an org principle.
3. **Be ignored silently**. If a principle is violated, it must be caught by Gate 02
   or explicitly waived. There is no third option.

---

## Context Loading

The merged constitution is ALWAYS loaded into agent context in ALL modes (FIX, BUILD,
ARCHITECT). It is the only document that is always present. This is non-negotiable —
governance must be active at all times.

Token budget for constitution: aim for < 2000 tokens merged. If the merged constitution
exceeds this, consider:
- Moving implementation details out (they don't belong in the constitution)
- Consolidating redundant principles
- Using references to external docs for detailed guidance

The constitution should be concise. Ten sharp principles beat fifty vague ones.
