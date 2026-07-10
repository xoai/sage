# Sage Process Constitution

These principles govern an explicitly selected Sage workflow or a persisted
active Sage run. They do not force Sage onto ordinary host-agent work.

## Rule 0: Explicit Authority

- Installed slash commands are authoritative.
- Plain prose and keyword matches are never authoritative transitions.
- Advisory route context may be accepted, combined, or ignored.
- An active run suppresses inferred rerouting until explicit switch or cancel.
- A stale or unavailable target is rejected rather than guessed.

**Compliance:** every run transition has an explicit command and durable event.

## Rule 1: Replayable State

An explicit start records the workflow, strict-mode choice, route-catalog hash,
and resolved composition before entering a capability. State and event receipts
must be idempotent and safe under concurrent hooks.

**Compliance:** the run can be reconstructed from `.sage/runtime` events.

## Rule 2: Declared Composition

Every required capability has one declared owner. Compatible augmenters,
validators, and observers may assist only when selected by explicit request,
user/project policy, or workflow defaults. Compatibility makes a skill eligible;
it does not auto-activate every installed skill. Ambiguous exclusive owners
require a user choice.

The user may combine Sage with external methods and domain skills. A keyword in
task prose never replaces the selected owner.

**Compliance:** capability entry names its resolved owner and selected helpers.

## Rule 3: Scoped Gates

Strict enforcement exists only for a healthy active run explicitly started with
`--strict`. Outside that state, hooks fail open. Inside it, gates may enforce only
declared shell, lane, ownership, artifact, and lifecycle invariants. Prose is not
an authorization channel.

Workflow approval checkpoints apply only when the selected workflow declares
them. Ordinary free input does not inherit Sage artifact or approval gates.

**Compliance:** every denial cites an active strict run and a declared invariant.

## Rule 4: Skills Before Assumptions

Load the resolved owner skill before producing its output. Preserve atomic spans
through their declared terminal. Helpers may not silently take over the owner's
method or terminal.

**Compliance:** entered and exited capability events match the composition plan.

## Rule 5: Verify Before Claiming Done

Obtain fresh evidence in proportion to risk and compare it with the declared
acceptance criteria. Store actual evidence in run state or workflow artifacts.
Do not claim completion while declared tasks remain unfinished.

**Compliance:** a completion event references current verification evidence.

## Rule 6: Canonical Self-Learning

Hooks detect structured correction, repeated-failure, fail-to-pass, behavioral
contradiction, and better-method evidence. Hooks never author learnings from
keywords. The `sage-self-learning` skill interprets candidates, searches before
store, enriches or updates equivalents, and supersedes incorrect rules through
the one configured backend.

Exactly one recall owner injects bounded prevention rules. Backend or recall
failure is advisory and fails open.

**Compliance:** every stored learning was authored by the canonical skill and
has a stable dedupe key, evidence references, rationale, and prevention rule.

## Rule 7: Evidence-Based Reflection

Self-learning capture and reflection form one lifecycle. At a terminal checkpoint,
the canonical reflection skill reviews run evidence and pending candidates. It
does not require the user to restate observable failures. Interactive questions
are reserved for unobservable external outcomes or preferences.

Every reflection request ends with a durable completion containing actual counts
(including zero) or a durable skip with an evidence-based reason.

**Compliance:** requested reflections are never left pending silently.

## Rule 8: Durable Decisions

Record only decisions declared durable by the active workflow. Initiative-local
decisions belong with that initiative; cross-project decisions belong in the
global project log. Do not create Sage artifacts merely because routing advice was
shown.

**Compliance:** artifacts and decision logs match the active run and approved
scope.
