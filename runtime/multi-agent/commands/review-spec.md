---
description: Run the configured spec_reviewer on spec.md for the given slug
argument-hint: [slug]
allowed-tools: Bash(.sage/scripts/run-role.sh:*), Bash(ls -1t .sage/work/*), Read, Glob
---

# /review-spec — adversarial review of spec.md

Active slug: $ARGUMENTS

If no slug was given, find the most recent work directory:

! ls -1t .sage/work/ 2>/dev/null | head -1

Delegate the review to the `codex-reviewer` sub-agent so its tool output
stays out of the main context. The sub-agent will run:

! .sage/scripts/run-role.sh spec_reviewer doc "$ARGUMENTS" spec.md

The script prints the path to a new review file under
`.sage/work/<slug>/reviews/`. Read that file and return inline:

1. **Verdict line** (last line of the review file).
2. **Top findings**: all BLOCKERs and up to 3 MAJORs, each as a single
   bullet with `path:line` and a one-sentence summary.
3. **Recommended next step**:
   - `APPROVE` → suggest `/review-plan` or `/implement` depending on
     whether `plan.md` exists yet.
   - `REVISE` → list the spec sections that need edits and offer to
     revise them.
   - `REJECT` → stop and ask the user what to do.

Do not read the full review into context. The file is the audit trail;
the user can open it if they want detail.
