---
name: sage-decisions
description: Recording decisions in the right log. Use when a decision needs to be written down, when the user asks why something was decided, when writing an ADR or a decision entry, or when unsure whether something belongs in the initiative's log or the global one.
version: "1.0.0"
type: system
---

# Decision logs

**The file system is the source of truth for state** — what exists in
`.sage/work/` and its frontmatter. **Decision logs are the source of truth for
reasoning.** A diff shows what changed; only the log shows why, and why is the
thing that is gone in three months.

## Which log

| Decision | Goes to |
|---|---|
| Anything scoped to one initiative | `.sage/work/<initiative>/decisions.md` |
| Cross-initiative: constitution choices, conventions, project-wide calls | `.sage/decisions.md` (global) |

**Default to the initiative log.** The global file is for decisions that
outlive the work that produced them.

## Why the split exists

Two parallel initiative branches, both prepending to one global file, is a
guaranteed merge conflict — on every checkpoint, forever. The per-initiative
split is what makes parallel sessions safe, and it is the entire reason for the
rule.

Writers switch immediately, including for initiatives already in flight.
Readers check the initiative log first and fall back to the global one, so the
switch is safe mid-cycle and needs no migration.

## How to write an entry

**Prepend** — insert directly after the `# Decisions` header, before existing
entries. Newest first. A log you have to scroll to the bottom of to find the
current state is a log nobody reads.

Each entry records:

- **What** was decided
- **Why** — the reasoning, not the restatement
- **What alternatives were considered**, and why they lost

The third one is what makes a decision log worth keeping. "We chose Postgres"
is a fact you could have got from the lockfile. "We chose Postgres over DynamoDB
because the access patterns are relational and we would have spent the savings
on a join layer" is a decision, and it is the thing that stops someone
relitigating it next quarter with the same arguments and less context.

## When

At **every checkpoint that involved a decision**. The compliance signal is
observable: after a checkpoint with a decision in it, the initiative's
`decisions.md` has a new entry at the top.

Not "at the end". At the end you will remember the conclusion and not the
alternatives, and the alternatives are the part with the value.

## Archive rotation

When the **global** `decisions.md` passes ~200 lines, at the next workflow
close: keep the 20 most recent entries, move the rest to
`decisions-{YYYY-MM-DD}.md`. Archives are read-only reference.

Initiative logs live and die with their work directory. No rotation.
