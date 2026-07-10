# Deterministic Learning Lifecycle

Sage treats recall, self-learning, and reflection as general agent capabilities.
They do not select a Sage workflow, take ownership of a build or fix method, or
prevent another installed skill from owning a capability.

The lifecycle has three boundaries:

1. Hooks collect or recall bounded, structured evidence without an LLM call.
2. The canonical `sage-self-learning` skill interprets a detected candidate and
   performs its full classify, four-part author, search-before-store,
   enrich/correct/invalidate/link method.
3. The canonical `reflect` skill reviews completed-run evidence once and sends
   each novel candidate through `sage-self-learning`.

This keeps the hot path deterministic without reducing learning to keyword
matching or letting a hook invent a lesson.

## Platform lifecycle

| Moment | Claude Code | Hermes | Behavior |
|---|---|---|---|
| Before work | `UserPromptSubmit` | `pre_llm_call` | Recall scoped prevention rules as advisory context. |
| After a tool | `PostToolUse` | `post_tool_call` | Persist normalized outcomes and detect candidates. |
| Completion checkpoint | `Stop` | `pre_verify` | Request one evidence-based reflection. |
| Session cleanup | platform stop | `on_session_end`, `on_session_finalize` | Flush state only; no second reflection. |

Hermes does not run a full verification workflow after every edit. Its
reflection adapter is attached to the explicit, bounded `pre_verify`
checkpoint. Hermes treats `post_tool_call` as an observer and ignores its
return value, so that hook persists candidates without pretending they were
delivered. Undelivered candidates are claimed exactly once and injected by the
next `pre_llm_call`; a `pre_verify` reflection may claim them first.

## Deterministic candidate signals

The detector accepts structured events rather than guessing from prose:

- an explicit `user.correction` event;
- the same normalized tool failure observed twice;
- a failed verification followed by a passing verification for the same target;
- a verified behavior observation that contradicts an earlier event.

Hooks persist only trigger type, evidence references, and a stable dedupe key.
They request the canonical skill and do not prewrite What happened, Why wrong,
What's correct, or the Prevention rule.

## One store and one recall owner

Projects may use `sage-memory` or OpenViking as the learning backend. Exactly one
backend and one recall owner may be active. Environment variables override
`.sage/config.yaml`:

```yaml
learning:
  backend: openviking
  recall_owner: sage-lifecycle
  openviking:
    base_url_env: OPENVIKING_BASE_URL
    resource_uri_env: SAGE_LEARNING_RESOURCE_URI
    user_env: OPENVIKING_USER
    agent_id_env: OPENVIKING_AGENT_ID
```

The corresponding environment values identify the OpenViking server, shared
learning resource, user, and current agent. Search remains scoped by project,
platform, capability, provider, and touched path selectors stored on each
record. Generated overview nodes are not treated as learnings.

Sage's lifecycle hooks run recall only when `recall_owner` is
`sage-lifecycle` or the legacy-compatible `sage-learning`. Any other configured
owner is treated as an external recall implementation, and the Sage hooks stand
down. This prevents duplicate injections while allowing all agents to share the
same backend.

If recall is unavailable, malformed, slow, or returns no eligible rules, the
hook emits no context and work continues. Recall never routes a workflow, arms
a mutation gate, or grants authorization.

## Reflection modes

Evidence mode is the default. It derives claims from the transcript, normalized
events, artifacts, verification results, and previously recalled or created
learnings. It does not require the user to explain what went wrong when the
agent already has evidence.

Interactive mode is opt-in and may ask only for information the agent cannot
observe: external outcomes, personal preferences, or stakeholder signals. A
valid reflection may conclude that there is no novel learning to store. The
canonical skill must durably complete the request with its actual counts,
including zero, or skip it with an evidence-based reason; requested reflections
are never left pending silently.

## Validation

Run the standalone lifecycle smoke test from the repository root:

```bash
bash develop/validators/learning-lifecycle-smoke.sh .
```

It checks Claude/Hermes parity, fail-open recall, canonical candidate handoff,
exactly-once reflection, idempotent hook installation, and rejection of
ambiguous backend configuration.
