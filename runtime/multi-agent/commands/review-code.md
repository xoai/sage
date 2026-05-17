---
description: Run the configured code_reviewer on the current uncommitted diff
argument-hint: [slug]
allowed-tools: Bash(.sage/scripts/run-role.sh:*), Bash(git diff --stat), Bash(git diff:*), Bash(ls -1t .sage/work/*), Read
---

# /review-code — adversarial review of the uncommitted diff

Active slug: $ARGUMENTS (default: most recent in `.sage/work/`)

Show diff scope first so the user knows what's being reviewed:

! git diff --stat

Delegate to `codex-reviewer` sub-agent:

! .sage/scripts/run-role.sh code_reviewer diff "$ARGUMENTS"

Read the produced review file. Surface inline:

1. **Verdict line** (last line).
2. **Spec coverage matrix**: row count + count of `❌ MISSING` rows. If
   any are missing, this is itself the headline issue.
3. **All BLOCKERs**: file:line + one-line summary + one-line fix.
4. **MAJOR / MINOR counts** (don't enumerate — too noisy for the main
   context; the user reads the full file if they want detail).
5. **Tests verdict**: honest? count of new tests.
6. **Decision prompt** based on verdict:
   - `APPROVE` → "No blocking findings. Stage and commit?
     `[Y]` Commit with message referencing spec.md
     `[N]` I'll commit manually
     `[R]` Show full review first"
   - `FIX_BEFORE_MERGE` → "Fix options:
     `[K]` Send fix list to `/implement` again
     `[F]` Patch the small things myself (only for trivial fixes)
     `[D]` Show full review and decide"
   - `REWORK` → "The plan or spec is wrong. Return to `/review-plan` or
     `/review-spec`?"

Wait for the user's response before any commit or further action.
