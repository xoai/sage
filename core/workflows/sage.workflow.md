---
name: sage
version: "1.0.0"
mode: sage
---

# Sage Workflow

Sage's intelligent entry point. Start here for any substantial work.

## Process

Read and follow the **sage-navigator** skill.

The navigator will:
1. Check project state (`.sage/progress.md` and existing artifacts)
2. Understand what you're asking for
3. Assess scope and detect gaps
4. Recommend the best path — and wait for your approval

## Quick Reference

If you already know what you want, use a specific workflow:
- **build** — feature development (spec → plan → implement)
- **fix** — debug and patch
- **architect** — system design from scratch
- **status** — check current project state

## Rules

- Always read project state before recommending anything.
- Follow the navigator's process — don't shortcut it.
- If the navigator isn't available, fall back to asking the user
  what they'd like to do and use the best matching workflow.
