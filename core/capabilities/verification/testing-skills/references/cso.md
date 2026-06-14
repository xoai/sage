# CSO — the Concise-Self-describing-Operation description standard

A skill's `description:` is loaded into the agent's system prompt at startup
(~100 tokens, always present). The body is loaded **only when the agent decides
to open the skill**. That asymmetry is the whole problem.

## The empirical finding (why this matters)

When a description *summarizes the workflow* — "runs 5 checks: spec alignment,
test coverage, error handling, boundaries, integration" — the agent reads that
summary and treats it as sufficient. It believes it already knows what the skill
does, so it **acts from the summary instead of opening the body**. The careful
enforcement, the rationalization counters, the exact procedure — all of it sits
in the unread body. The description became a shortcut *around* the skill.

This is the plausible mechanism behind the `auto-review` skip: the agent had a
one-line summary that felt like enough, and rationalized past the actual review.

**A description states WHEN to reach for the skill. It never states WHAT the
skill does step by step.** Triggering conditions pull the agent *into* the body.
A workflow summary lets the agent stay *out* of it.

## The rule

A CSO-clean description contains **triggering conditions only**:
- the situations, signals, and user phrasings that should activate the skill;
- written in third person;
- with NO enumeration of internal steps/checks, NO process-sequencing language,
  NO "what it does" recital.

## Violation signals (what the validator flags)

1. **Step/check enumeration** — "5 checks", "three steps", "seven principles",
   "four dimensions". A count of internal operations is a workflow summary.
2. **Process sequencing** — "then", "after that", "first… then…", "followed by".
   These narrate the procedure.
3. **A ≥3-item imperative list of what it does** — "Checks X, verifies Y,
   validates Z, confirms W." Three or more "what it does" verbs in a list is a
   summary the agent will follow instead of the body.

## Worked example — `auto-qa`

**Before (CSO violation — enumerates the five checks):**

> Automatic sub-agent code verification after quality gates pass. Independent
> context window. Checks spec-implementation alignment, test coverage, error
> handling, boundary conditions, and integration consistency. 60 seconds,
> code-only, advisory.

The sentence "Checks spec-implementation alignment, test coverage, error
handling, boundary conditions, and integration consistency" is a five-item
recital of the body's procedure. An agent reading it thinks *"I know what auto-QA
checks — alignment, coverage, errors, boundaries, integration — I can eyeball
those myself"* and skips the independent sub-agent. The summary replaced the
skill.

**After (CSO-clean — triggering conditions only):**

> Use after implementation passes the quality gates, when a change needs an
> independent pass over the code before it ships, or when the user asks to
> "QA this", "check the implementation", or "verify it matches the spec".
> Applies to Standard and Comprehensive scopes; skip for Lightweight tasks.

No check is named. The agent cannot act from the description — to learn *what*
auto-QA does, it must open the body, which is exactly where the enforcement and
the rationalization table live.

## The test

Read only the description. If you could *perform* the skill's job from it, it
leaks the workflow — tighten it to conditions. If it only tells you *when you'd
want the skill*, it is CSO-clean.
