---
description: Run the configured code_reviewer on the current uncommitted diff
argument-hint: [slug]
allowed-tools: Bash(.sage/scripts/run-role.sh:*), Bash(.sage/scripts/hallucination-check.sh:*), Bash(git diff --stat), Bash(git diff:*), Bash(ls -1t .sage/work/*), Read
---

# /review-code — adversarial review of the uncommitted diff

Active slug: $ARGUMENTS (default: most recent in `.sage/work/`)

Show diff scope first so the user knows what's being reviewed:

! git diff --stat

**Hallucination-check precondition.** Before paying for the codex
pass, run the deterministic phantom-import check. It walks the diff,
resolves each new `import`/`require`/`use`/`from X` against the
per-language manifest, and reports unresolved entries. Cheap
(sub-second), per-file by extension, polyglot-safe. Skip silently
on a legacy deployment that has not yet refreshed
`.sage/scripts/hallucination-check.sh` — invariant I1 (inert by
absence):

! test -x .sage/scripts/hallucination-check.sh && .sage/scripts/hallucination-check.sh "$ARGUMENTS" || true

Exit codes (when the script is present):
- `0` — clean. Proceed.
- `1` — unresolved imports present (printed to stdout). Surface them
  to the user *before* dispatching codex; they are pre-filed
  findings for the code-reviewer. The codex pass still runs (it
  catches what `grep` cannot), but the user has seen the script's
  output first.
- `2` — no diff or not a git repo. Continue to codex.

Then delegate to `codex-reviewer` sub-agent:

! .sage/scripts/run-role.sh code_reviewer diff "$ARGUMENTS"

Read the produced review file. Surface inline:

1. **Verdict line** (last line).
2. **Spec coverage matrix**: row count + count of `❌ MISSING` rows. If
   any are missing, this is itself the headline issue.
3. **All BLOCKERs**: file:line + one-line summary + one-line fix.
4. **MAJOR / MINOR counts** (don't enumerate — too noisy for the main
   context; the user reads the full file if they want detail).
5. **Tests verdict**: honest? count of new tests.
6. **Recommended next step** — a recommendation only; `/review-code`
   is a read-only review command and does not itself commit, run a
   fix, or rerun anything:
   - `APPROVE` → no blocking findings; the diff is ready to stage and
     commit (the user decides whether to commit — nothing auto-merges).
   - `FIX_BEFORE_MERGE` → route the findings to the implementer to
     fix, then re-review. Under `/build-x` that is Phase 7's `[K]`
     option; standalone, run the fix through `/build-x` or apply the
     findings directly.
   - `REWORK` → the plan or spec is wrong; return to `/review-plan` or
     `/review-spec`.

This command reviews and reports — it renders no interactive decision
menu. The interactive `[F]`/`[K]`/`[D]` choice, and the `[K]` fix
routing, belong to `/build-x` Phase 7.
