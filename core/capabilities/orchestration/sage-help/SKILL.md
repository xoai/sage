---
name: sage-help
description: >
  Provides specific, actionable guidance on what to do next based on current
  project state. Reads progress files and context to give one clear next step.
  Use when the user says "help", "what do I do", "sage help", "what's next",
  "I'm stuck", or "status".
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: haiku
activation: manual
tags: [help, guidance, navigation, orchestration]
inputs: [progress, sage-config]
outputs: [guidance]
-->

# Sage Help

Tell the user exactly what to do next. Not documentation. Not a feature list.
Specific, actionable guidance based on WHERE THEY ARE right now.

**Core Principle:** A beginner should never feel lost. One command, one clear answer.

## When to Use

- User says "help", "sage help", "what do I do", "what's next", "I'm stuck"
- User appears confused about the process
- Start of a new session with no clear task

## Process

### Step 1: Read Current State

Check these files in order:
1. `.sage/work/` frontmatter — what's the current phase?
2. `.sage/config.yaml` — is Sage configured?
3. Active feature directory — is there work in progress?

### Step 2: Respond Based on State

#### State: No `.sage/` directory exists
```
👋 This project isn't set up with Sage yet.

  Say "set up sage" and I'll configure it (~2 minutes).
  I'll detect your tech stack and set up quality guidance.

  Or just tell me what you want to build — I'll set up as we go.
```

#### State: `.sage/` exists, no active feature
```
✅ Sage is configured. Ready to work.

  What would you like to do?
  • Describe a feature to build → I'll guide you through spec → plan → build
  • Describe a bug to fix → I'll debug systematically and verify the fix
  • Say "new project" → I'll help you start from scratch with architecture guidance

  Your stack: [from config.yaml]
  Active packs: [from config.yaml]
```

#### State: Feature in progress, spec phase
```
📋 Working on: [feature name]
   Phase: Specification

   Your spec is at: .sage/work/[YYYYMMDD-slug]/spec.md
   [status: draft / awaiting approval / approved]

   Next: [Review and approve the spec / Answer the remaining questions / Plan implementation]
```

#### State: Feature in progress, plan phase
```
📝 Working on: [feature name]
   Phase: Planning

   Plan: .sage/work/[YYYYMMDD-slug]/plan.md
   [status: draft / awaiting approval / approved]

   Next: [Review and approve the plan / Start implementation]
```

#### State: Feature in progress, implementation phase
```
🔨 Working on: [feature name]
   Phase: Implementation

   Progress: [X] of [Y] tasks complete
   Next task: Task [N]: [name]
   Blocked: [any blocked tasks]

   Next: [Implement Task N / Review completed work / Fix failing gate]
```

#### State: Feature in progress, review phase
```
✅ Working on: [feature name]
   Phase: Review

   All [N] tasks complete. Running final quality review.

   Next: [Address review feedback / Merge / Create PR]
```

#### State: User asks a specific question
If the user asks "sage help [specific question]", answer the question directly
using knowledge of Sage's workflow, skills, and packs. Examples:

- "sage help how do I skip elicitation" → "Provide a detailed spec directly and I'll accept it. Or say 'just do it' to skip to implementation."
- "sage help what packs are loaded" → Read config.yaml and list active packs with brief descriptions.
- "sage help how do I add a new pack" → Explain the pack installation process.
- "sage help what's the constitution" → Show the active constitution principles.

## Rules

**MUST (violation = useless help):**
- MUST NOT dump documentation. Give the ONE thing to do right now.
- MUST NOT list all features. Answer the specific question or state.
- MUST scan .sage/work/ frontmatter before responding — context-aware guidance is the whole point.
- MUST be concrete: file paths, task numbers, specific actions. Not "continue working on the feature."

**SHOULD (violation = suboptimal experience):**
- SHOULD keep responses to 3-8 lines. The user wants direction, not a manual.
- SHOULD ask if state is ambiguous: "I see [X]. Are you continuing that, or starting something new?"

## Failure Modes

- **No .sage/work/ artifacts or plan.md exists:** The project hasn't started or state
  was lost. Guide the user to onboard or to start a new initiative. Don't
  guess at state that doesn't exist.
- **Multiple features in progress:** If plan.md shows unchecked tasks across
  multiple features, ask: "I see work in progress on [X] and [Y]. Which one
  are you working on right now?"
- **User asks about a capability Sage doesn't have:** Be honest. "Sage
  doesn't have a skill for [X] yet. You could [workaround] or consider
  adding a playbook skill for this."
- **User is lost in a long project:** Read the journal if it exists. Give a
  3-line summary: "Here's where the project is: [last journal entry summary].
  The current task is [plan.md current task]. Want to continue or do something
  different?"
