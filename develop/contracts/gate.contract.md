# Gate Contract

**Version:** 1.0.0
**Status:** Stable

A gate is a quality check that runs after skill execution. Gates are binary: PASS or FAIL.
They are the enforcement mechanism — skills do the work, gates verify the work.

Gates are mandatory by default. They cannot be skipped by agents or skills.
Only the project configuration can disable a gate, and disabling is logged as a waiver.

---

## Required File Structure

```
core/gates/
├── <NN>-<gate-name>.gate.md    # REQUIRED — Gate definition
└── _config/
    └── gate-modes.yaml          # REQUIRED — Gate activation per mode
```

Gate files are prefixed with a two-digit number (01-99) that defines execution order.
Gates ALWAYS execute in numerical order.

---

## Required Frontmatter

```yaml
---
# REQUIRED FIELDS
name: <string>               # Unique gate identifier, kebab-case
description: <string>        # What this gate checks
version: <semver>
order: <integer>             # Execution order (01-99). Lower runs first.
                             # Default gates use: 01, 02, 03, 04, 05
                             # Extension gates should use 50+ to run after defaults.

# OPTIONAL FIELDS
replaces: <string>           # Name of the default gate this replaces
cost-tier: <string>          # Recommended model: haiku, sonnet, opus. Default: sonnet
required-context: [<string>, ...]  # Documents the gate needs to perform its check
                                   # e.g., ["spec", "constitution", "implementation"]
category: <string>           # One of: compliance, quality, safety, verification
---
```

---

## Gate Body Structure

```markdown
---
(frontmatter)
---

# <Gate Name>

<1-2 sentence summary of what this gate checks.>

## Check Criteria

<Explicit list of what the gate verifies. Each criterion is a yes/no question.
The gate PASSES only if ALL criteria pass.>

## Failure Response

<What happens when the gate fails.
MUST include: what the agent should do to fix the failure.
MUST include: when to escalate to human vs retry.>

## Adversarial Guidance

<Instructions for the gate to be skeptical.
e.g., "Do not trust the implementer's self-report. Verify independently."
This is what makes gates meaningful — they must actively look for problems.>
```

---

## Gate Modes Configuration

`core/gates/_config/gate-modes.yaml` defines which gates are active in each mode:

```yaml
fix:
  mandatory: [<gate-names>]      # MUST run, cannot be skipped
  optional: [<gate-names>]       # Available but not required
  skipped: [<gate-names>]        # Not run in this mode

build:
  mandatory: [<gate-names>]
  optional: [<gate-names>]
  skipped: [<gate-names>]

architect:
  mandatory: [<gate-names>]
  optional: [<gate-names>]
  skipped: [<gate-names>]
```

Rules:
- A gate in `mandatory` MUST pass before the workflow continues.
- A gate in `optional` runs if enabled in `.sage/config.yaml` but doesn't block on failure.
- A gate in `skipped` does not run at all.
- The project config can move gates between `mandatory`, `optional`, and `skipped`,
  but moving a gate FROM `mandatory` to `skipped` is logged as a waiver.

---

## Output Contract

Every gate MUST produce a result with this structure:

```
GATE: <gate-name>
RESULT: PASS | FAIL
FINDINGS:
  - <finding 1>
  - <finding 2>
ACTION: none | fix-and-retry | escalate-to-human
```

- **PASS**: All check criteria met. Workflow continues to next gate.
- **FAIL + fix-and-retry**: Agent attempts to fix the issues, then the gate re-runs.
  Maximum retries are defined by `execution.max-retries` in project config (default: 3).
- **FAIL + escalate-to-human**: Gate failure cannot be auto-fixed. Workflow pauses.

---

## Behavioral Contract

Every gate MUST:

1. Be **adversarial**. Gates exist to catch problems. A gate that always passes is useless.
   Gates SHOULD actively look for violations, not passively confirm compliance.
2. Be **independent**. A gate MUST NOT depend on another gate's output.
   Gates run in order but each makes its own judgment.
3. Be **deterministic** where possible. The same code reviewed twice should get the same result.
   Non-determinism (e.g., from LLM variance) should be acknowledged in the gate's README.
4. Produce a **structured result** (PASS/FAIL with findings and action).
5. **Never auto-approve**. If a gate cannot determine compliance, the result is FAIL
   with `escalate-to-human`, not a silent PASS.
6. **Respect retry limits**. After `max-retries` failures, always escalate to human.

Every gate MUST NOT:

1. **Modify code**. Gates verify — they don't fix. Fixes happen in the retry cycle
   through the relevant skill (e.g., `implement` for code fixes).
2. **Skip other gates**. Gates don't control flow — the workflow's sub-workflow does.
3. **Be disabled by agents or skills**. Only the project config can disable a gate.

---

## Default Gates (Included with Sage)

| Order | Name | Category | What It Checks |
|-------|------|----------|----------------|
| 01 | spec-compliance | compliance | Implementation matches task specification |
| 02 | constitution-compliance | compliance | No governance principles violated |
| 03 | code-quality | quality | Clean, readable, maintainable, secure code |
| 04 | hallucination-check | safety | All imports, APIs, versions are real |
| 05 | verification | verification | Tests pass, feature works when executed |

## Extension Gates (Examples)

| Order | Name | Category | Source |
|-------|------|----------|--------|
| 51 | owasp-security | safety | @sage/security extension |
| 52 | accessibility | quality | @sage/web extension |
| 53 | performance-budget | quality | @sage/web extension |
| 54 | license-compliance | compliance | @sage/opensource extension |

---

## Adding Custom Gates

1. Create `<NN>-<name>.gate.md` in `core/gates/optional/` (for bundled optional gates)
   or `.sage/gates/` (for project-specific gates).
2. Add the gate name to the appropriate mode list in `gate-modes.yaml`
   or in `.sage/config.yaml` under `gates.additional`.
3. Extension packs add gates through their `SKILL.md manifest` manifest.
