---
name: sage
description: "Routes to the right workflow based on intent and scope"
version: 1.0.0
author: Sage
metadata:
  hermes:
    tags: [Sage, Workflow, sage]
---

## When to Use
Load this skill when the user runs `/sage` or asks to sage something (the Sage sage workflow).

## Arguments
Hermes does NOT interpolate an in-body argument token. The user's arguments/flags arrive as a SEPARATE instruction line appended to this skill invocation. Wherever the steps below refer to "the user's arguments", use the text of that appended instruction line.

## Independent review (delegate_task)
When a step calls for an independent review, invoke `delegate_task` against the `sage-reviewer` skill. Hermes delegate_task has NO toolset-restriction parameter — read-only is prompt-enforced, and you MUST verify afterward that the reviewer made no edits (e.g. `git status` unchanged) before accepting its verdict.


# Sage Workflow

Sage's intelligent entry point. Start here for any substantial work.

## Process

Read and follow the **sage-navigator** skill at `sage/core/capabilities/orchestration/sage-navigator/SKILL.md`.

The navigator will:
1. Check project state (`.sage/work/` artifacts and `.sage/decisions.md`)
2. Understand what you're asking for
3. Assess scope and detect gaps
4. Recommend the best path — and wait for your approval

## Quick Reference

If you already know what you want, use a specific workflow:
- **/build** — feature development (brief → spec → plan → implement)
- **/fix** — debug and patch (diagnose → test → fix → verify)
- **/architect** — system design (ADRs → spec → milestone plan → phased build)
- **/review** — independent artifact evaluation
- **/learn** — codebase knowledge capture
- **/status** — check current project state

## Rules

- Always read project state before recommending anything.
- Follow the navigator's process — don't shortcut it.
- If the navigator isn't available, fall back to asking the user
  what they'd like to do and use the best matching workflow.
