---
name: codebase-scan
description: >
  Scans relevant codebase areas to understand existing patterns, conventions,
  dependencies, and architecture before making changes. Use at the start of
  any feature or fix, when entering an unfamiliar codebase area, or when the
  user says "scan the project", "what patterns are used", or "analyze the
  codebase".
version: "1.0.0"
modes: [build, architect]
---

<!-- sage-metadata
cost-tier: haiku
activation: auto
tags: [analysis, context, conventions, reconnaissance]
inputs: [codebase]
outputs: [codebase-context]
-->

# Codebase Scan

Understand the codebase BEFORE you plan or build anything. Agents that skip
reconnaissance duplicate existing code, break established patterns, and
introduce inconsistencies.

**Core Principle:** Look before you leap. Five minutes of scanning prevents
five hours of rework.

## When to Use

At the START of any BUILD or ARCHITECT workflow, before elicitation or planning.
Also when resuming a session in an unfamiliar part of the codebase.

## Process

### Step 1: Project Structure (30 seconds)

Examine the top-level directory structure. Identify:
- **Language/framework:** What stack is this? (package.json, requirements.txt, go.mod, etc.)
- **Project layout:** Monorepo? Standard framework layout? Custom structure?
- **Entry points:** Where does execution start? Where do tests live?

### Step 2: Relevant Area (60 seconds)

Based on the task, identify the specific area of the codebase that will be affected.
Examine:
- **Existing code in the area:** What files exist? What do they do?
- **Patterns used:** How are similar things implemented in this project?
- **Naming conventions:** How are files, functions, classes, variables named?
- **Test patterns:** What testing framework? How are tests structured?
- **Import conventions:** How are dependencies organized?

### Step 3: Dependencies and Boundaries (30 seconds)

Identify:
- **What depends on the area being changed?** Breaking changes affect these.
- **What does the area depend on?** These are the interfaces you must respect.
- **Configuration:** Environment variables, config files, feature flags relevant to the change.

### Output: Codebase Context

Produce a concise summary (NOT a full report — just what's relevant to the task):

```
CODEBASE CONTEXT:
Stack: [language, framework, version]
Area: [files/directories relevant to the task]
Patterns: [established conventions this task must follow]
Dependencies: [what will be affected by changes]
Test setup: [framework, how tests are structured here]
Concerns: [anything that could complicate the task]
```

This output feeds into elicitation (so you don't ask about things you already know)
and planning (so the plan follows existing patterns).

## Rules

**MUST (violation = missed context or wasted time):**
- MUST NOT spend more than 2 minutes on scanning. This is reconnaissance, not a full audit.
- MUST NOT skip this in BUILD/ARCHITECT mode. Even for "simple" changes, understanding
  context prevents breaking things.
- MUST note existing patterns. The plan MUST follow them unless the spec explicitly
  documents a reason to deviate.

**SHOULD (violation = incomplete picture):**
- SHOULD read the `.sage/conventions.md` if it exists — it captures previously
  discovered patterns.
- SHOULD focus on the relevant area + nearby examples, not every file in the project.

**MAY (context-dependent):**
- MAY skip for FIX mode if the bug location is already known and isolated.

## Failure Modes

- **Empty project (greenfield):** Report that. No conventions to follow — the first
  implementation sets the pattern. Note this so elicitation and planning account for it.
- **Massive monorepo:** Focus ONLY on the relevant area. Don't try to understand the
  whole thing. Use directory structure and imports to scope your scan.
- **No tests exist:** Flag this as a risk. The plan should include setting up the test
  infrastructure as a prerequisite task.
