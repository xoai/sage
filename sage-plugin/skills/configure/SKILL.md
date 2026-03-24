---
name: configure
description: >
  Configure Sage preset and project settings. Switch between base,
  startup, enterprise, or opensource constitution presets. Use when
  the user says "configure sage", "change preset", or "sage settings".
disable-model-invocation: true
---

# Configure Sage

Set up project-level Sage configuration.

## Step 1: Read Current Config

Read `.sage/config.yaml` if it exists. If not, note: "No project
config found. Using base preset (default)."

## Step 2: Present Options (Zone 1)

Sage: Current preset: {current or "base (default)"}

[1] Base — TDD, no silent failures, simple first, document decisions
[2] Startup — velocity-focused, lighter process, ship fast
[3] Enterprise — compliance, audit trails, security-first
[4] Open Source — contributor-friendly, RFC process, public decisions

Pick 1-4, or describe what you need.

## Step 3: Apply Preset

Write the choice to `.sage/config.yaml`:

```yaml
preset: {chosen-preset}
```

If `.sage/` doesn't exist, create it with:
- config.yaml (with preset)
- decisions.md (empty template)

## Step 4: Confirm

Sage: Preset updated to {preset}. Start a new session or reload
the plugin to apply the new rules.

The {preset} preset adds these principles on top of base:
{list key additions from the chosen preset}

Type a command, or describe what you want to do next.

## Preset Summaries

**Base** (default): TDD first, no silent failures, simplest solution
first, document decisions, work in the open. Applied to all projects.

**Startup**: Bias toward shipping. Reduce ceremony for small changes.
Speed > perfection for v1. But: never skip tests, never skip root
cause analysis. Fast doesn't mean reckless.

**Enterprise**: Every change auditable. Security review on auth/data
changes. Compliance evidence in artifacts. Approval chains documented.
Change management discipline.

**Open Source**: Changes proposed as RFCs. Public decision log.
Contributor-friendly: explain WHY in every decision. Breaking changes
get migration guides. Backward compatibility by default.
