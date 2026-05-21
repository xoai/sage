---
description: Run the configured implementer on the slug's spec + plan
argument-hint: [slug]
allowed-tools: Bash(.sage/scripts/run-role.sh:*), Bash(git status:*), Bash(git diff --stat), Bash(ls -1t .sage/work/*), Read
---

# /implement — hand off to the configured implementer

Active slug: $ARGUMENTS (default: most recent in `.sage/work/`)

**Precondition:** the working tree must be clean. The implementer's output
is identified as the entire uncommitted diff at the end of this run, so
any pre-existing dirty state would contaminate the review.

! git status --porcelain

If non-empty, stop and ask the user to commit or stash before continuing.

Determine how the configured `implementer` role runs:

! .sage/scripts/run-role.sh probe-kind implementer

If this prints **`host`**, stop here. `/implement` cannot run a host
implementer — its `allowed-tools` grant no write access, and the
`kimi-implementer` sub-agent (`Bash`, `Read` only) cannot author code
either. Tell the user: the `implementer` role is a host agent; run the
implementation through `/build-x` (its Phase 6 runs a host implementer
in-session), or implement directly. Then exit without changes.

If it prints **`cli`**, continue. Delegate the implementation pass to the
`kimi-implementer` sub-agent. It isolates the implementer's stdout (which
is large) from the main context and returns only a short summary.

The sub-agent runs:

! .sage/scripts/run-role.sh implementer doc "$ARGUMENTS" plan.md

After it returns, show the diff scope:

! git diff --stat

Then read `.sage/work/$ARGUMENTS/implementer-notes.md` and summarize:

1. **Plan adherence**: steps complete / blocked / skipped (counts only).
2. **Files touched**: top 5 by lines changed.
3. **Tests added**: count.
4. **Spec ambiguities the implementer flagged** (the `Questions for the
   planner` section of the notes file) — these are the most important
   thing the user needs to see, because they indicate spec defects that
   require revision before the next iteration.
5. **Recommended next step**: usually `/review-code <slug>`.

Do not read source files into context. The reviewer needs the diff fresh.
