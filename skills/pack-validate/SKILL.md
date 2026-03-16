---
name: pack-validate
description: >
  Phase 5 of pack building. Runs automated checks, re-runs test prompts
  WITH the pack loaded, and measures behavior change against the Phase 3
  baseline. Determines if the pack earns its context tokens.
version: "1.0.0"
modes: [build, architect]
cost-tier: sonnet
activation: auto
tags: [pack-builder, validation, testing]
inputs: [pack-files, observation-report]
outputs: [validation-report]
---

# Pack Validate

Verify the pack works and earns its tokens.

**Core Principle:** A pack that doesn't measurably change agent behavior is
wasted context tokens. Validation proves the pack delivers value.

## Community Pack Path

### Step 1: Automated Checks

Run the pack quality checker:
```bash
bash .sage/tools/sage-check-pack.sh packs/<pack-name>
```

Fix all errors. Review all warnings. The checker validates:
- Manifest completeness (required fields, layer, dependencies)
- Token budget compliance (per-file and total)
- Required content (patterns, anti-patterns, tests.md)
- Pattern quality signals (agent-failure explanations, code examples)
- Composability (no contradictions with dependencies)

### Step 2: Re-Run Test Prompts WITH Pack

Take the same test prompts from Phase 3. Run them again, but this time
with the pack loaded in context.

For each prompt, record:
- What the agent produced this time
- Did the behavior change from the baseline?
- Did the pack's specific guidance get followed?
- Did ANY anti-pattern from the pack still occur?

### Step 3: Measure Behavior Change

Compare Phase 3 (without pack) to Step 2 (with pack):

```markdown
| Prompt | Without Pack | With Pack | Changed? | Improved? |
|--------|-------------|-----------|----------|-----------|
| 1      | [failure]   | [result]  | YES/NO   | YES/NO    |
| 2      | [failure]   | [result]  | YES/NO   | YES/NO    |
| ...    |             |           |          |           |

Behavior change rate: X/Y prompts = Z%
Target: ≥70%
```

### Step 4: Iterate If Needed

If behavior change rate is below 70%:

- **Pack guidance was ignored** → make the language stronger. "ALWAYS" and
  "NEVER" are stronger than "prefer" and "consider." Add code examples.
- **Agent acknowledged but didn't follow** → the pattern may be too abstract.
  Make it more specific with a concrete code example.
- **No change at all** → the pattern addresses something the agent already
  handles. Cut it — it's wasting tokens.
- **Agent followed guidance but result was wrong** → the pattern itself is
  inaccurate. Fix the content, not the format.

Repeat Steps 2-3 after changes until ≥70% or you've concluded the pack
can't improve on the agent's baseline (rare but honest).

### Step 5: Final Report

```markdown
# Validation Report

## Automated Checks: PASS/FAIL
## Token Usage: N / limit
## Behavior Change: X/Y = Z%

## Per-Prompt Results
[table from Step 3]

## Changes Made During Iteration
- [what was changed and why]

## Verdict: READY / NEEDS WORK / NOT VIABLE
```

## Project Overlay Path

Validation for overlays is simpler:

### Step 1: Verify Loading

Confirm the overlay loads correctly alongside its community pack:
- The overrides.md file exists and is well-formed
- The pack.yaml has `type: overlay` and `extends:` field
- The community pack it extends is installed

### Step 2: Spot Check

Give the agent 1-2 prompts that should trigger the overlay's guidance.
Verify the agent follows your project-specific conventions, not just
the community pack's generic patterns.

### Step 3: Token Check

Confirm the overlay is under 500 tokens. It should be a small delta.

## Output

Save to `.sage/pack-build/validation.md`:

```markdown
# Validation Report

Path: [community-pack / project-overlay]
Pack: <name>
Automated checks: [PASS/FAIL]
Token usage: [N / limit]
Behavior change: [X/Y = Z%]
Verdict: [READY / NEEDS WORK / NOT VIABLE]
```

## Failure Modes

- **Behavior change below 50%:** The pack isn't effective enough. Consider
  whether the framework really needs a pack or if agents handle it well enough.
- **One pattern drives all improvement:** The other patterns may be noise.
  Consider trimming to just the high-impact patterns and their supporting
  anti-patterns.
- **Pack causes regressions:** A pattern made the agent WORSE on a prompt.
  The pattern is wrong — fix or remove it immediately.
