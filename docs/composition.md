# Neutral Skill Composition

Sage composition decides which installed provider owns each method capability.
It is separate from routing: a route may select a workflow, but prompt words
never decide method ownership. The compiler validates provider metadata and
overlays before a run; the resolver applies explicit choices and policy in a
fixed order; run state locks atomic providers until their declared terminal.

This permits four first-class modes:

- Sage supplies the workflow and all methods.
- Sage supplies a workflow while an external skill owns one or more methods.
- An external workflow runs without Sage instructions or gates.
- Direct agent work runs without a workflow while learning or other compatible
  services are selected independently.

## Canonical coverage model

Sage uses three deterministic surfaces instead of routing every installed item
the same way:

1. **Workflow routes** — every canonical `core/workflows/*.workflow.md` has one
   validated explicit slash target and one workflow-default composition plan.
2. **Method providers** — canonical process, optional-mode, verification,
   learning, research, and design skills declare capabilities and roles. They
   enter a run only through explicit selection, user/project policy, workflow
   defaults, or an exact supported mode flag.
3. **Direct skills** — domain/reference skills that claim no workflow method
   remain valid platform skill commands and appear in `direct_skills`. They can
   be invoked directly without making Sage own the surrounding task.

`--strict`, `--quality-locked`, and `--autonomous` are parsed only as leading
exact flags. Strict mode controls runtime invariants. The two optional method
flags add their declared providers to build/fix/architect composition; negative
flags override project defaults. Words later in the goal never activate a mode.

Unmodified external skills remain direct until a user or project overlay
declares their capabilities. This is deliberate: Sage cannot infer that an
arbitrary third-party skill is an owner or helper without inventing semantics.

## Provider metadata

A skill owned in this repository can declare nested metadata in one bounded HTML
comment. The block is parsed with `yaml.safe_load`; duplicate blocks, unsafe
tags, malformed YAML, invalid roles, and invalid capability names fail
compilation with a source line.

```yaml
<!-- sage-metadata
composition:
  contract: composition/v1
  atomic: true
  provides:
    - capability: requirements.elicit
      role: owner
      combine: exclusive
      inputs: [request, codebase-context]
      outputs: [problem-frame, acceptance-criteria]
    - capability: solution.specify
      role: owner
      combine: exclusive
      inputs: [problem-frame, acceptance-criteria]
      outputs: [specification]
      terminal: design-approved
-->
```

Capabilities are stable dotted identifiers such as `requirements.elicit` or
`change.implement`. Roles are:

- `owner` — controls the method for the capability;
- `augmenter` — contributes compatible inputs or analysis;
- `validator` — checks the owner's output;
- `observer` — records evidence without controlling the method.

`combine: exclusive` is valid only for an owner. Compatible helpers never take
ownership. An `atomic: true` provider declares an ordered span and at least one
terminal signal. The runtime will not interleave another owner inside that span.

## Unmodified third-party skills

Do not patch a third-party package just to add Sage metadata. Describe it in a
user overlay at `~/.sage/composition.yaml` or a project overlay at
`<project>/.sage/composition.yaml`:

```yaml
contract: composition-overlay/v1

bindings:
  superpowers:brainstorming:
    atomic: true
    provides:
      - capability: requirements.elicit
        role: owner
        combine: exclusive
        outputs: [problem-frame]
      - capability: solution.specify
        role: owner
        combine: exclusive
        inputs: [problem-frame]
        outputs: [specification]
        terminal: design-approved

policy:
  requirements.elicit:
    owner: superpowers:brainstorming
  solution.specify:
    owner: superpowers:brainstorming
  output.review:
    validators: [sage:quality-review]
```

Project overlay keys replace only matching user keys. Unrelated user bindings
and helper lists remain. Every referenced ID must exist in the platform's
installed skill set, and every selected role must match a declared capability.
For a namespaced overlay ID such as `superpowers:brainstorming`, the compiler
also accepts an installed `brainstorming` leaf directory; the explicit overlay
provides the namespace and semantics that the filesystem alone cannot infer.
Compilation failure leaves the previous `.sage/composition.json` untouched.

The compiled catalog also lists installed `direct_skills`. These are valid
platform skill commands but do not claim a workflow capability. This keeps
domain/reference skills routable without pretending they should own or
automatically join every Sage workflow.

## Resolution order

For each required capability, ownership is resolved exactly once in this order:

1. explicit provider selection in the run request;
2. project policy;
3. user policy;
4. the explicitly selected workflow's defaults;
5. a unique installed owner when no policy selected one.

Helpers use the same explicit/project/user/workflow precedence. A compatible
declaration makes an augmenter, validator, or observer eligible; it does not
auto-activate every compatible installed skill.

An explicit request looks like:

```json
{
  "explicit": {
    "requirements.elicit": {"owner": "superpowers:brainstorming"},
    "solution.specify": {"owner": "superpowers:brainstorming"}
  },
  "selected_workflow": "sage:build",
  "required_capabilities": [
    "requirements.elicit",
    "solution.specify",
    "change.implement",
    "evidence.verify"
  ]
}
```

Resolve it with:

```bash
python sage/runtime/tools/sage_runtime_cli.py composition resolve \
  --catalog .sage/composition.json < composition-request.json
```

The result is `resolved-composition/v1`. It is recorded in `run.started`; the
state reducer selects the owner on `capability.entered` and records
`active_provider`, `atomic_span`, and `provider_terminal`. Replay produces the
same lock. `provider.terminal`, explicit `provider.switched`, `/cancel`, or run
completion unlocks it.

## Conflicts and choices

If two exclusive owners remain after precedence is applied, the resolver emits
`choice-required/v1` and exits 4. It lists only validated candidates and their
provenance; it never picks by keyword score or installation order. A platform
integration may persist that result at
`.sage/runtime/choice-required.json`. The pre-turn hook asks once per stable
choice hash before entering the capability. After the user chooses, resolve
again with an explicit owner and start the run from that result.

A missing provider, incompatible augmenter, malformed overlay, or partial
selection of an atomic provider is invalid configuration and exits 2.

## Sage-off behavior

When `selected_workflow` is absent or names an external workflow:

- Sage workflow instructions and strict gates do not activate.
- Direct agent behavior or the external workflow owns the task.
- Explicitly selected Sage capabilities may still participate in their declared
  roles without turning Sage into the root workflow.
- Learning can remain selected independently because it is a general lifecycle,
  not a prerequisite for a Sage workflow.

The neutral composition context states only the capability, selected owner,
terminal, and compatible helpers. It does not restate or modify the provider's
method.

## Regeneration

Claude Code and Hermes generators compile the catalog after validating installed
route IDs:

```bash
bash sage/runtime/platforms/claude-code/setup/generate-claude-code.sh .
bash sage/runtime/platforms/hermes/setup/generate-hermes.sh .
```

Both consume the same built-in defaults and layered overlays. Re-run the
generator after installing, removing, or changing a provider or overlay. The
catalog and each provider carry stable hashes so a run can prove which resolved
composition it locked.
