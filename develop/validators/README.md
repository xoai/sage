# Sage Tests

The framework tests itself with the same discipline it enforces.

## Philosophy

Traditional tests verify that things work when followed correctly. Sage tests
also verify that things **can't be bypassed** when agents try to cut corners.

This is Superpowers' core testing insight: **if you didn't watch an agent fail
without the skill, you don't know if the skill prevents the right failures.**
A TDD skill that looks comprehensive on paper might have a gap that lets the
agent rationalize skipping tests "just this once." You only find that gap by
putting the agent under pressure.

We test at two levels:

**Structural tests** (automated, no AI needed) verify that every module meets
its contract. Does every SKILL.md have the required frontmatter? Do workflows
reference real skill names? Do personas bind to skills that exist? These run
in seconds and catch structural regressions.

**Behavioral tests** (require AI agent) verify that agents actually follow the
skills, respect the gates, and can't rationalize their way out of mandatory
processes. These are the expensive tests — they require real agent execution —
and they're the most important ones.

## Test Categories

| Category | Method | Tests | What It Catches |
|----------|--------|-------|-----------------|
| `contracts/` | Bash scripts, automated | 9 validators | Structural contract violations |
| `pressure/` | Agent scenarios, manual | 33 adversarial prompts | Rationalization gaps in skills |
| `core/workflows/` | Agent scenarios, manual | 4 end-to-end | Workflow sequencing and gate execution |
| `integration/` | Agent scenarios, manual | 8 cross-module | Module interaction failures |
| `core/capabilities/` | Agent scenarios, manual | 14 targeted | Individual skill behavior correctness |

## Running Tests

```bash
# Contract validation — runs in seconds, no AI needed
bash develop/validators/contracts/validate-all.sh

# Individual validators
bash develop/validators/contracts/validate-skills.sh
bash develop/validators/contracts/validate-gates.sh
bash develop/validators/contracts/validate-workflows.sh
```

Pressure tests and scenario tests are run manually by presenting the scenario
to an AI agent with Sage active and comparing actual behavior against documented
expected behavior.

## The Pressure Test Cycle

When a pressure test reveals a gap:

1. **Document** the exact rationalization the agent used
2. **Close** the gap in the relevant skill (add the rationalization to the counter-table)
3. **Re-test** the same scenario to verify the fix
4. **Repeat** until no new rationalizations surface

This is RED-GREEN-REFACTOR for skills: observe failure (RED), fix the skill (GREEN),
close loopholes (REFACTOR).
