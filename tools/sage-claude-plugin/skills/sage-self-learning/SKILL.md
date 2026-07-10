---
name: sage-self-learning
description: >
  Turns correction, failure, recovery, contradiction, and better-method
  evidence into deduplicated prevention rules. Uses the one configured learning
  backend, searches before storing, and pairs capture with evidence reflection.
version: "2.0.0"
type: process
---

<!-- sage-metadata
activation: candidate-or-explicit
tags: [learning, correction, reflection, openviking, memory]
inputs: [learning-candidate, evidence, recalled-rules, learning-config]
outputs: [learning-record, correction-link, reflection-input]
composition:
  contract: composition/v1
  id: sage-self-learning
  atomic: false
  provides:
    - capability: learning.capture
      role: owner
      combine: compatible
-->

# Self-Learning

Self-learning changes future behavior. It is not an activity log and it is not
permission to turn a keyword match into a rule. The skill is paired with
`reflect`: capture handles evidence during work; reflection consolidates the
cycle and closes the learning request.

## When to Use

Use this skill when a deterministic hook supplies a candidate or when there is
clear evidence of one of these conditions:

- the user corrected an approach or claimed behavior;
- the same normalized operation failed repeatedly;
- a failed verification later passed for the same target;
- verified behavior contradicted an earlier assumption;
- a demonstrably better recurring method was found.

Do not trigger from sentiment, generic negative words, or task keywords alone.

## Backend Authority

Exactly one configured backend stores learnings and exactly one configured
recall owner injects them. Read `.sage/config.yaml` and its named environment
variables; do not probe several stores and do not copy a learning into a second
memory system.

Supported backends:

- `openviking` — shared Markdown learning resources under the configured
  `resource_uri`;
- `sage-memory` — legacy-compatible structured memory tools;
- a project adapter implementing the same search/store/update/supersede/link
  contract.

If the configured backend is unavailable, preserve the candidate as pending and
fail open. Do not silently fall back to local prose, a native agent memory file,
or another database.

## Process

### 1. Load evidence

Read the candidate's evidence references and the relevant normalized events.
Separate observed facts from interpretation. A valid record must be able to
name the failure/correction, its root cause, the corrected behavior, and a
forward-looking check.

### 2. Search before store

Search the configured backend using the proposed root cause and prevention rule.
Limit results and scope them by project, platform, active capability, selected
providers, subsystem, and touched paths when available.

- Same root cause and same prevention rule: enrich/update the existing record.
- Earlier rule is now wrong: create a correction, supersede the old record, and
  link the audit trail.
- Similar symptom but different cause or prevention: create a separate record.
- No future behavior change: do not store.

This step occurs before any Persist operation. Never reach directly for a raw
memory call just because the thought "remember this" occurred.

### 3. Author the record

Use a specific `[LRN:<type>]` title and these four semantic sections:

1. **What happened** — bounded evidence, not a transcript dump.
2. **Why it was wrong** — the causal explanation.
3. **What's correct** — the verified behavior or method.
4. **Prevention** — what to check before the next similar action.

Include a stable dedupe key plus selectors that make recall precise:

- `status`: `active`, `superseded`, or `invalidated`;
- `scope`: `project` or `global`;
- project and platform;
- capabilities and providers;
- relevant paths or subsystem;
- evidence references;
- `corrects` or `superseded_by` when applicable.

### 4. Persist through the configured adapter

#### OpenViking

Search only beneath the configured `viking://resources/...` learning URI. Write
one Markdown resource beneath that same URI using the host's OpenViking
write/store operation (the HTTP equivalent is `POST /api/v1/content/write` with
`mode: replace`). Use a deterministic filename derived from the title slug and
dedupe key. Never embed a user name, machine path, credential, or agent identity
in source-controlled configuration.

The resource shape is:

```markdown
---
schema: sage-learning/v1
status: active
scope: project
project: <project selector>
platforms: [<platform>]
capabilities: [<capability>]
providers: [<provider>]
paths: [<relative path>]
tags: [self-learning, <type>]
dedupe_key: <sha256>
evidence_refs: [<event id>]
corrects: null
superseded_by: null
---
# [LRN:<type>] <specific title>

What happened: ...
Why it was wrong: ...
What's correct: ...
Prevention: ...
```

Update an equivalent record in place. For a correction, write the new record,
mark the old record `superseded`, set its `superseded_by`, and set the new
record's `corrects` field. Generated `.abstract.md` and `.overview.md` nodes are
never learning records.

#### Sage Memory

Use the structured `sage_memory_search`, `sage_memory_store`,
`sage_memory_update`, and `sage_memory_link` operations supplied by that
backend. Preserve the same record fields and search-before-store decision. The
skill owns these calls; hooks and workflows must not hand-author raw entries.

### 5. Hand off to reflection

Keep stored/updated record IDs and candidate outcomes in run evidence. At the
workflow terminal, `reflect` reviews the complete cycle, consolidates patterns,
and records actual stored and novel-candidate counts. Capture is not a substitute
for reflection, and reflection must not invent records without this skill.

## Rules

- Evidence detection and semantic authoring are separate stages.
- Search before every new store.
- Prefer one enriched rule over near-duplicates.
- Prevention must be actionable before the next attempt.
- Store only claims supported by evidence.
- Use relative selectors; never persist personal or machine-specific details.
- Do not block task execution merely because storage is unavailable.
- A configured external recall owner means Sage recall hooks stand down.

## Failure Modes

- **Raw memory logging:** stop and run this process from search-before-store.
- **Duplicate result:** enrich the existing record and reuse its ID.
- **Wrong old rule:** supersede and link; never delete the audit trail silently.
- **Ambiguous backend:** store nothing until configuration selects exactly one.
- **OpenViking result outside the resource prefix:** ignore it.
- **Only generated overview nodes returned:** treat as no eligible learning.
- **Insufficient evidence:** keep the candidate pending or skip with a reason.

## Quality Check

Before returning, verify that the selected backend is the configured one, the
search preceded Persist, the record has all four semantic sections, selectors
contain no personal data, correction links are consistent, and the record ID is
available to the terminal reflection.
