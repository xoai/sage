---
name: scope-guard
description: >
  Monitors implementation scope and prevents drift beyond the plan. Detects
  unrequested refactors, gold-plating, and "while I'm here" additions. Use
  when implementing tasks from a plan, writing code for a feature, or when the
  agent starts modifying files not listed in the current task.
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: haiku
activation: mandatory
tags: [discipline, scope, focus, yagni]
inputs: [spec, plan, implementation]
outputs: [scope-assessment]
-->

# Scope Guard

Do what was planned. Nothing more.

**Core Principle:** Every line of code that wasn't in the plan is a line of code
that wasn't reviewed, wasn't tested against the spec, and wasn't approved by the
human. "While I'm here" is how technical debt and bugs are born.

## When to Use

Active throughout implementation. Scope guard is a background discipline, not
a discrete step. Apply these rules continuously while working.

## Rules — What's In Scope

In scope (MAY do without asking):
- Everything explicitly listed in the current task
- Infrastructure directly required by the task (imports, types, config)
- Tests for the functionality being implemented
- Constitution-mandated requirements (security, error handling) even if not in task

## Rules — What's Out of Scope

MUST NOT do these without explicit human approval:
- **"While I'm here" refactors:** "This function is messy, let me clean it up" — NO.
  If it's not in the task, don't touch it. File a note for future work.
- **Unrequested features:** "This would be better with caching" — NO.
  If caching isn't in the spec, don't add it. YAGNI.
- **Premature optimization:** "This could be faster with..." — NO.
  Make it work first. Optimize only when evidence shows it's needed.
- **Style fixes in unchanged files:** Don't reformat code you didn't write
  and aren't changing. It pollutes the diff and hides the real changes.
- **Dependency upgrades:** Unless the task specifically requires it.
- **Documentation for unrelated features:** Stay focused.

SHOULD NOT do unless the constitution requires it:
- **Additional error handling** beyond what the spec requests. If the
  constitution mandates error boundaries or input validation, it's in scope.
  Otherwise, note it for future work.

## Self-Check

Before committing any change, ask:

1. "Is this in my current task?" — If no, don't commit it.
2. "Was this in the plan?" — If no, don't commit it.
3. "Did the human ask for this?" — If no, don't commit it.
4. "Is this required by the constitution?" — If yes, it's in scope even if not in the task.

If the answer to all four is "no," you're scope creeping. Revert the change.
If you believe the change is truly important, note it in `.sage/progress.md`
under a "Future Work" section and move on.

## When Scope SHOULD Expand

Sometimes you discover mid-implementation that the plan is incomplete. This is
legitimate — but the response is NOT to silently expand scope:

1. STOP implementation
2. Describe what you discovered: "Task 3 requires X, which isn't in the plan"
3. Ask the human: "Should I add this to the plan, or work around it?"
4. If they approve, update the plan FIRST, then implement
5. If they say "not now," note it as future work and proceed without it

## Failure Modes

- **Agent wants to "clean up" existing code:** Redirect. "I noticed [X] could be
  improved. I've noted it in progress.md for future work. Continuing with current task."
- **Dependency requires additional work:** Legitimate. Flag it, ask human, update plan if approved.
- **Constitution requires something not in plan:** Legitimate. Constitution overrides
  the plan. Implement the constitution requirement and note why.
