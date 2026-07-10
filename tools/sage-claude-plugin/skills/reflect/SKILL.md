---
name: reflect
description: >
  Reviews completed-run evidence, sends novel candidates through the canonical
  self-learning skill, and durably completes or skips the reflection request.
user-invocable: true
---

<!-- sage-metadata
activation: explicit-or-terminal
tags: [reflection, learning, evidence, lifecycle]
inputs: [run-state, events, artifacts, verification, learning-candidates]
outputs: [reflection-summary, learning-records, lifecycle-acknowledgment]
composition:
  contract: composition/v1
  id: reflect
  atomic: true
  provides:
    - capability: learning.reflect
      role: owner
      combine: exclusive
      terminal: reflection-acknowledged
-->

# Reflect

Reflection and `sage-self-learning` are one lifecycle. Reflection discovers and
consolidates evidence; the self-learning skill owns search-before-store,
semantic authoring, correction links, and persistence.

## When to Use

- an explicit `/reflect` command;
- a terminal reflection request from a completed Sage run;
- a long work cycle with evidence worth consolidating.

## Modes

- **Evidence mode (default):** use run events, transcript evidence, artifacts,
  verification results, recalled rules, and pending candidates.
- **Interactive mode (`--interactive`):** ask only for unobservable external
  outcomes, preferences, or stakeholder signals. Do not ask the user to explain
  failures the run already records.

## Process

1. Load the requested run and confirm the reflection request is still pending.
2. Review decisions, failures, corrections, recoveries, verification, and
   candidate evidence. Separate observed facts from interpretation.
3. Group items by root cause and prevention rule. A valid outcome may contain
   zero novel candidates.
4. Send every novel candidate through `sage-self-learning`. Never issue a raw
   backend store from this skill.
5. Summarize reinforced practices, prevented recurrences, improved methods, and
   useful seeds for the next cycle.
6. Acknowledge the request exactly once:

   ```text
   <sage-runtime-cli> reflection complete --run-dir <run-dir> --stored <count> --novel-candidates <count>
   ```

   If evidence cannot support a valid reflection:

   ```text
   <sage-runtime-cli> reflection skip --run-dir <run-dir> --reason <evidence-based-reason>
   ```

Use the installed runtime CLI path supplied by the platform hook. Counts must be
actual integers; zero is valid. A requested reflection may not be left pending
silently.

## Rules

- Evidence mode is the default.
- No mandatory questionnaire when context already answers it.
- No direct backend writes; use `sage-self-learning`.
- Do not manufacture novelty to justify a store.
- Do not reflect twice over the same acknowledged request.
- Reflection failure does not retroactively invalidate completed task evidence.

## Failure Modes

- **Missing run directory:** skip with the missing-evidence reason.
- **Backend unavailable:** keep candidate outcomes in evidence, complete with
  the actual stored count, and report the storage limitation.
- **Duplicate learning:** reinforce/update through self-learning; do not count it
  as a novel stored record.
- **Only personal or machine-specific detail:** generalize safely or skip.
