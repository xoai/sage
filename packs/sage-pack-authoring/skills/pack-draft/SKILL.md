---
name: pack-draft
description: >
  Phase 4 of pack building. Generates pack files from observations and
  processed sources. Handles both community pack (full structure) and
  project overlay (overrides.md only) paths.
version: "1.0.0"
modes: [build, architect]
cost-tier: sonnet
activation: auto
tags: [pack-builder, drafting, creation]
inputs: [pack-brief, processed-sources, observation-report]
outputs: [pack-files]
---

# Pack Draft

Generate the pack files from evidence.

**Core Principle:** Every pattern is grounded in an observed agent failure.
Every anti-pattern describes real agent behavior. Nothing is hypothetical.
The observation report is your evidence — the draft is your argument.

## Community Pack Path

### Step 1: Scaffold

Run the scaffolding tool:
```bash
bash .sage/tools/sage-new-pack.sh <pack-name> --layer <N>
```

This creates the directory structure with template files.

### Step 2: Write Patterns

For each confirmed need from the observation report, write a pattern.

**Format (mandatory):**
```markdown
# Pattern Name

**Why agents get this wrong:** [1-2 sentences explaining the root cause —
stale training data, wrong defaults, missing context]

**Do:** [2-3 sentences of specific instruction + code example if needed]
```

**Rules:**
- Each pattern entry should be ~80-120 tokens (3-4 sentences + optional code snippet)
- Start EVERY pattern with "Why agents get this wrong"
- Include code example only if the visual difference between right and wrong is key
- One concept per pattern — if you need a subheading, it's two patterns
- Maximum 7 patterns total

### Step 3: Write Anti-Patterns

For each confirmed failure from the observation report, write an anti-pattern.

**Format (mandatory):**
```markdown
# Anti-Pattern: Name

**What agents do:** [1-2 sentences — exact behavior observed]

**Why it's wrong:** [1-2 sentences — consequence of the mistake]

**Do instead:** [1 sentence — the correction]
```

**Rules:**
- Each anti-pattern entry should be ~60-90 tokens (2-3 sentences)
- "What agents do" must describe REAL observed behavior from Phase 3
- Maximum 5-7 anti-patterns total

### Step 4: Write Constitution Additions

Extract 3-7 non-negotiable principles from the patterns:

```markdown
1. [Framework] components MUST [do X] because [reason].
2. [Pattern Y] MUST NOT be used because [reason].
```

Use MUST/MUST NOT/SHOULD/SHOULD NOT language. These are laws, not suggestions.

### Step 5: Write Manifest

Fill in `pack.yaml` with real values: name, description, layer, dependencies,
activation conditions, framework version, last-verified date.

### Step 6: Write Tests

Transfer the test prompts from Phase 3 (pack-observe) into `tests.md`:
- Copy the prompts exactly
- Record the baseline (without pack) from observation
- Write the expected improvement (with pack) from the patterns you just wrote

### Step 7: Token Check

Count approximate tokens (words × 1.3) across all content files.
Verify total is within budget:
- L1: ≤3500 tokens
- L2: ≤5000 tokens
- L3: ≤1500 tokens

If over budget, trim the lowest-priority patterns first. Better to have
5 sharp patterns than 7 diluted ones.

## Project Overlay Path

### Step 1: Create Overlay Directory

```bash
mkdir -p .sage/packs/<pack-name>
```

### Step 2: Generate overrides.md

From the project context gathered in Phase 2, generate a single overlay file:

```markdown
# Project Overlay: <pack-name>

## Extends: <community-pack-name>

## Project-Specific Conventions

### [Convention Category]
[Specific rule for this project]

### [Convention Category]
[Specific rule]

## Constraints
- [What this project cannot use and why]
- [Required patterns]

## Project API Patterns
[Any project-specific API formats, response structures, error handling]
```

**Rules:**
- ONLY include what differs from or extends the community pack
- Don't repeat community pack guidance — it's already loaded
- Keep under 500 tokens — it's a delta, not a full pack
- Use specific, actionable language — "query keys follow [entity, action, params]"
  not "use good query key conventions"

### Step 3: Create pack.yaml (Minimal)

```yaml
---
name: "@project/<pack-name>"
type: overlay
extends: "<community-pack-name>"
version: "1.0.0"
---
```

## Output

**Community pack:** Complete pack in `packs/<name>/` with all required files.
**Project overlay:** `.sage/packs/<name>/overrides.md` + minimal `pack.yaml`.

## Failure Modes

- **Patterns are too wordy:** You're writing documentation, not corrections.
  Each pattern should be 2-4 sentences + optional code. If it's a paragraph,
  trim it.
- **Anti-patterns are hypothetical:** Go back to Phase 3 observations. If you
  didn't see the agent do it, don't list it.
- **Over token budget:** Cut the lowest-severity patterns. The top 5 failures
  cover 80% of real problems.
- **Overlay repeats community pack:** The overlay should ONLY contain what's
  different. Delete anything the community pack already covers.
