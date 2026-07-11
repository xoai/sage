---
name: pack-observe
description: >
  Phase 3 of pack building. Runs test prompts WITHOUT the pack loaded to
  establish a baseline of agent failures. Records what the agent gets wrong
  as evidence for patterns and anti-patterns. Community pack path only —
  overlays skip this phase.
version: "1.0.0"
modes: [build, architect]
cost-tier: sonnet
activation: auto
tags: [pack-builder, testing, observation]
inputs: [pack-brief, processed-sources]
outputs: [observation-report]
---

# Pack Observe

Run test prompts and record what agents get wrong.

**Core Principle:** Packs are evidence-based. Every pattern and anti-pattern
should be traceable to an observed agent failure. This phase creates that
evidence. Skip this for project overlays (overlays are based on team rules,
not agent observations).

## Process

### Step 1: Design Test Prompts

Using the agent failures identified in Phase 1 (pack-discover) and the
processed sources from Phase 2 (pack-source-process), design 3-5 test prompts.

Each prompt should:
- Be a realistic task a developer would ask an agent to do
- Be specific enough to trigger the expected failure
- Target a different pattern/anti-pattern from the pack
- Be self-contained (no dependencies on prior prompts)

```markdown
## Test Prompt 1: [descriptive name]
Target: [which failure this should expose]
Prompt: "[exact text to give the agent]"
Expected failure: [what the agent will probably get wrong]
```

### Step 2: Run Baseline Prompts

This is the critical step. Run each test prompt and record the ACTUAL output.
The agent should work on these prompts in a clean context — no pack loaded,
no special instructions about the framework.

For each prompt, record:
- What the agent produced (summary, not full code)
- What specifically it got wrong
- What it got right (important — don't create patterns for things that work)
- Severity of the failure (crashes, wrong behavior, suboptimal but works, cosmetic)

### Step 3: Analyze Results

Compare actual failures against expected failures:

- **Expected failure occurred** → strong candidate for anti-pattern
- **Unexpected failure occurred** → bonus insight, add to candidate list
- **Expected failure did NOT occur** → agent handles this correctly, DROP
  this pattern candidate (it would waste tokens on something not needed)

The last case is critical. If the agent already handles something well,
a pattern for it is noise. Cut it aggressively.

### Step 4: Document Observations

Record findings in a structured format that directly feeds Phase 4 (drafting).

## Output

Save to `.sage/pack-build/observations.md`:

```markdown
# Observation Report

## Test Results

### Prompt 1: [name]
Failure observed: YES/NO
What happened: [description]
Severity: [critical/major/minor/none]
Pattern candidate: [yes/no — drop if no failure]

### Prompt 2: [name]
...

## Confirmed Failures (will become anti-patterns)
1. [failure] — observed in prompt [N]
2. ...

## Confirmed Needs (will become patterns)
1. [what the agent needs to be told] — addresses failure [N]
2. ...

## Dropped Candidates (agent handles correctly)
- [candidate] — reason dropped
```

## Rules

- Do NOT fabricate observations. If you didn't see the failure, don't claim it.
- Record what the agent ACTUALLY does, not what you expect it to do.
- Be honest about what the agent gets right — unnecessary patterns waste tokens.
- Minimum 3 test prompts. If you can't design 3, the pack idea is too narrow.

## Failure Modes

- **Agent passes all tests:** Rare but possible — the LLM's training data is
  already sufficient for this framework. No pack needed. Report this honestly.
- **Failures are inconsistent:** Agent gets it right sometimes, wrong sometimes.
  Still worth a pattern — the pack makes it consistently right.
- **User is in a hurry and wants to skip observation:** Push back gently.
  "Observation takes 10 minutes and prevents building a pack that wastes
  tokens on things agents already handle. It's the most important step."
