---
name: sage
version: "1.0.0"
mode: sage
produces: ["Routes to the right workflow based on intent and scope"]
checkpoints: 0
scope: "Entry point — scope depends on selected workflow"
user-role: "Describe what you want to do"
---

# Sage Workflow

Sage's intelligent entry point. Start here for any substantial work.

## Process

Read and follow the **sage-navigator** skill.

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
