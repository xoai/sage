# Configuring Sage — the `.sage/config.yaml` reference

`sage init` writes `.sage/config.yaml` into your project. It is the single
switchboard for everything Sage enforces, reviews, and automates. This guide
documents every key the codebase actually reads — what it does, who reads
it, its default, and whether an agent under enforcement is allowed to touch
it.

Two principles shape everything below:

- **The knob ships, the number decides (ADR-14).** A feature whose value is
  unmeasured ships **off**, and the measurement decides the default — in
  either direction. The review-loop v2 keys earned their default that way;
  the scope-guard keys were measured on 2026-08-02 and **stayed off**,
  because the drift they prevent did not occur in six bare runs across two
  model tiers.
- **An agent cannot soften its own floor.** While `hard_enforcement: true`,
  the config-gate hook blocks the agent from editing this file in any way
  that reduces enforcement. Humans change enforcement in their own editor —
  which never goes through a tool call, so the gate never sees it.

## How the file is read

Sage's hooks parse this file with deliberately simple line-based readers,
not a YAML library. That buys three properties you should know about:

- **The FIRST occurrence of a key wins.** Duplicate keys are not a merge —
  and the config-gate refuses to *create* a file that states the same
  enforcement key twice with different values (a "reader-divergence bomb").
- **Keep the canonical form.** Flag defaults (`quality_locked`,
  `autonomous`, `subagents`) are honored only as exactly `key: true` —
  lowercase, one space, nothing trailing. `True`, `"true"`, `yes`, and
  trailing comments read as *no default* there. Other keys tolerate
  quotes and trailing `# comments`, but the canonical form always works.
- **Comments are free.** Lines starting `#` are never read as keys.

---

## Identity and platforms

Written by `sage init`; rarely edited by hand.

| Key | Default | What it does |
|---|---|---|
| `sage-version` | the installed version | Which framework version initialized this project. `sage update` maintains it; version-drift tooling reads it. |
| `project-name` | detected | Display name used in generated docs. |
| `detected-stack` | detected | The stack `sage init` sniffed (informational). |
| `platforms` | detected | Which platform runtimes are generated (`["claude-code"]`, `["opencode"]`, …). Drives what `sage update` regenerates and what `sage worktree` seeds. |
| `command_prefix` | `/sage` | The slash-command prefix on platforms that support one. |

## The quality chain

| Key | Default | What it does |
|---|---|---|
| `auto_review` | `true` | At spec/plan approval, a fresh-context sub-agent reviews the artifact before work proceeds (when the platform can dispatch sub-agents). `false` skips the independent review — the skip is announced, never silent. |
| `auto_qa` | `true` | Independent QA sub-agent at completion. A cycle cannot complete *silently* without it: the manifest's `qa:` field must record `passed` or a declared skip (R29 — the spec-gate enforces this). |
| `independent_gate3` | `true` | Gate 3 (code quality) runs in a fresh sub-agent instead of self-review. `false` means the agent reviews its own code, and Sage says so. |

## Enforcement — the master switch and the gates

These are the keys the config-gate protects. The table lists each gate's
default *reading* when the key is absent — which is what makes upgrades
safe: a project that has never heard of a key is never surprise-blocked.

| Key | New projects | Absent means | What it gates |
|---|---|---|---|
| `hard_enforcement` | `true` | off | The master switch. Nothing below fires without it. Projects upgraded by `sage update` get it added as `false` with a notice — enforcement never surprises an established workflow. |
| `tdd_enforcement` | `true` | off | The TDD gate: a source edit is blocked until a test is dirty/untracked or the last commit was test-only. Escape hatches: `tier: tier1` on the cycle manifest, or this key. |
| `secrets_gate` | on | on | Credentials in source are blocked (provider-shaped patterns; `.env` and test fixtures allowed; live-marked keys blocked everywhere but `.env`). `false` is the explicit opt-out. |
| `verify_gate` | on | on | A code-bearing commit demands this-session test evidence. `false` opts out. |
| `bookkeeping_gate` | on | on | Hand-edits of an active cycle's `manifest.md`/`decisions.md` are redirected to the one-command `manifest.py close-out` writer. `false` opts out. |

**What the config-gate blocks the agent from writing** (humans out-of-band
only): flipping `hard_enforcement` off; adding `secrets_gate`/`verify_gate:
false`; removing `tdd_enforcement: true`; softening the review floor
(`review_loop.mode` v2→v1, `witness_capping` off) while v2 is active;
lowering `scope_gate`'s rank or flipping `implicit_test_scope` while the
scope gate is armed; turning `scope_judge` off or touching any `judge_*`
knob while it is on; and creating contradictory duplicates of any of these.
Obvious Bash evasions (redirects/`sed -i` writing the switch off) are
blocked too.

## Scope Guard (measured, and off by default)

Scope Guard turns the approved plan's declared file lists into a machine
floor. **Both knobs are off, and the 2026-08-02 measurement says leave them
there** — not because the mechanism is unproven-but-promising, but because
the failure it prevents did not occur: L3 at N=3 on two model tiers scored
bare 3/3 and gated 3/3, with zero false blocks. Turn `scope_gate` on if you
want the floor anyway (it is harmless and fast); do not expect it to catch
something, and do not claim it does. Full numbers and the reasoning:
[SCOPE-GUARD-CAMPAIGN.md](../develop/evals/SCOPE-GUARD-CAMPAIGN.md).

At plan approval the workflow runs:

```bash
python3 sage/runtime/tools/manifest.py scope derive .sage/work/<cycle>/manifest.md
```

which parses each plan task's `Files:` (and `Output:` for [DOC] tasks) into
a `scope:` block in the manifest frontmatter. That block — never the plan
directly — is what the gate enforces.

| Key | Default | Values |
|---|---|---|
| `scope_gate` | `off` (absent) | `off` \| `standard+` \| `all` |
| `implicit_test_scope` | `true` (absent) | `false` requires tests to be declared in the plan |
| `scope_judge` | `false` (absent) | `true` arms the advisory background judge — measured 1 false positive in 4 clean runs; detection unmeasured |

### `scope_gate` semantics

With `standard+`, an Edit/Write outside the derived scope of the active
cycle(s) exits 2 with both legal exits named:

1. `manifest.py scope add-collateral <path> --task TN --reason "…"` — one
   extra path, recorded; the tool writes the decisions.md line itself and
   refuses globs with no literal prefix (a scope-wide grant is not
   collateral).
2. Ask the user, amend the plan's `Files:` lines, then
   `scope derive --refresh` — the old→new delta, naming the added globs, is
   recorded in decisions.md.

Scope changes go through the artifact, never silently through the diff.

What is *never* blocked: paths under `.sage/` and `sage/`, paths outside
the project, Tier-1 work (no manifest), `tier: tier1` cycles under
`standard+` (`all` gates them too), cycles owned by another checkout
(parallel sessions / harvested worktrees), and — with
`implicit_test_scope: true` — witness/TDD tests: anything under a dedicated
test root (`tests/`, `test/`, `__tests__/`, `spec/`), or a test file whose
subject maps to an in-scope source.

With several active cycles the **union** of their scopes governs — an edit
is allowed if any cycle sanctions it. Each cycle's scope is
integrity-checked before it counts: the sibling `plan.md` must exist and
declare at least one `Files:`/`Output:` line, and its declaration hash must
match the manifest's `derived_from`. On a mismatch (the plan changed after
derive) the cycle stays armed with the intersection of its recorded globs
and what the plan still declares, and every allowed edit carries a warning
naming the `--refresh` command. A cycle whose gate is on but whose scope
was never derived warns loudly on every edit rather than silently
disarming.

Stated residuals, in the same register as the other gates: bash-mediated
writes bypass Edit/Write matchers entirely (partially covered by the scope
journal when the judge is on, and by review-time diff checks), and a
deliberately forged plan+manifest pair that *openly declares* a wide scope
defeats the union — two artifact writes a review cannot miss. These gates
are floors under rationalization drift, not sandboxes.

### `scope_judge` and its knobs

The judge is an advisory background check for drift a path gate cannot see
— off-task work *inside* in-scope files. It journals tool calls
(`scope-journal.jsonl` in the cycle dir, Bash included), runs a cheap-model
pass over a bounded window when enough events accumulate, and on a `drift`
verdict injects **one** correction into the next hook return. It never
blocks. It runs on claude-code and opencode — one runtime, two delivery
wires: claude-code returns the correction as PostToolUse
`additionalContext`; the opencode adapter appends it to the next tool
result (capability attested with a live planted-drift transcript,
`docs/attestations/opencode-context-injection-midstream-2026-08-04.md`,
expires 1.4). Capability is not efficacy: E-JUDGE-1 was measured on
claude-code only — where it failed its precision criterion, which is why
the knob ships `false` — and has never run on opencode. The floor is
available there; its necessity is unproven everywhere.

| Key | Default | Meaning |
|---|---|---|
| `judge_window` | `10` | Events per pass — only the last N non-subagent journal entries since the previous verdict are ever read. |
| `judge_every` | `8` | A pass becomes eligible every N journal events. Event-driven — never a timer. |
| `judge_cooldown` | `15` | At most one injected correction per N journal events; repeats also require a *new* reason. |
| `judge_timeout` | `60` | Seconds before a judge model call is killed. A killed pass records `insufficient-evidence`, never `drift`. |
| `judge_cmd` | `auto` | The judge's model command, packet on stdin. On claude-code, `auto` → `claude -p --model haiku`. On opencode, `auto` resolves in this order and stops: **1.** an explicit `judge_cmd` in this file — escape hatch, mostly for testing; **2.** a user-defined agent named `sage-scope-judge` in opencode config (project or global) **that carries a `model` binding** — an agent entry without a model is treated as undefined, because the judge must never resolve to "inherit the session model"; **3.** soft-fail — the pass records `insufficient-evidence` (never `drift`) and a one-time journal note says exactly how to designate. No model is inferred; the judge stays idle until designated. Protected while the judge is armed. |

On opencode, designating the judge's model is one config block — this is
the template, authored by you, never generated (a generated agent would be
Sage picking a paid model on your behalf, or worse, a modelless entry that
inherits the primary):

```jsonc
// opencode.json
"agent": {
  "sage-scope-judge": {
    "model": "<provider>/<cheap-model>",
    "permission": { "edit": "deny", "bash": "deny" }
  }
}
```

The `permission` block is load-bearing, not decoration: headless agent
invocations DO get tools ([V-D], 2026-08-04), and the deny pair is what
keeps the judge's session read-only. The cross-platform asymmetry is
design, not gap: claude-code's `auto` resolves to the platform's canonical
cheap tier because one exists; opencode has no canonical cheap model,
which is why explicit agent designation is the correct resolution there.

Safety invariants, all deterministic-tested: the judge's own model calls
can never re-trigger judging (`SAGE_JUDGE` guard); one pass per cycle at a
time; machine-wide cap of 2; subagent events are journaled but never
judged or corrected — a packet-scoped implementer receiving cycle-scope
corrections is being derailed, not helped. Every injection writes its own
decisions.md audit line, and per-cycle cost totals print at close-out.

## The review loop (v2 — the measured default)

`review_loop` puts the review-revise verdict in code: findings land in a
machine-owned ledger and every CONTINUE/STOP is computed, not vibed. v2 is
the default since its flip criteria were measured and held; existing
projects were pinned to `mode: v1` by `sage update` and opt in by deleting
the pin.

```yaml
review_loop:
  mode: v2                  # v2 (default) | v1 restores the classic loop
  major_budget: 0           # open majors tolerated at stop (v1: always block)
  iteration_cap: 5          # v1 value: 10
  escalate_after_stalls: 2  # non-improving rounds before ESCALATE
  witness_capping: true     # false restores severity-as-reported
  scope_check: true         # false restores v1 (no diff-scope check on fixes)
  review_model: inherit     # inherit | cheap (savings unclaimed until measured)
```

An *absent* block reads as v2; `mode` and `witness_capping` are part of the
enforcement floor while v2 is active.

## Execution-flag defaults

The `/build`-family flags can be defaulted from config. **Canonical form
only** — exactly `key: true`, or the default is silently ignored (this
strictness is what keeps the Bash and Python readers byte-for-byte
identical):

| Key | Flag | What it turns on |
|---|---|---|
| `quality_locked` | `--quality-locked` | The review-revise loop runs at every checkpoint until clean. |
| `autonomous` | `--autonomous` | Checkpoints auto-resolve (decisions are still logged). |
| `subagents` | `--subagents` | Per-task fresh implementer + independent reviewer (platform permitting; refusal is announced, R97). |

Command-line flags always win: `--no-x` > `--x` > config default > off.

## Resume close-out economy

These tune what a *resumed* session re-pays. Defaults are the lean settings
the resume-cost campaign measured; each key's other value restores the
pre-campaign behavior. Full rationale: `cycle-protocol.md § Resume
close-out economy`.

| Key | Default | Meaning |
|---|---|---|
| `gate_review` | `combined` | One adversarial review over the whole cycle diff at close-out. `per-gate` restores a dispatch per gate; `off` skips it. |
| `batch_bookkeeping` | `true` | Bookkeeping is the ONE `manifest.py close-out` command, not incremental hand-edits (the bookkeeping-gate enforces this mechanically). |
| `trust_inherited_red` | `true` | A test recorded as already-failing is not re-run just to re-witness it — write the code, confirm green. |
| `resume_memory` | `skip` | Skip the memory search/store on resume (measured null at this horizon). `keep` restores both. |
| `resume_test_cadence` | `lean` | Targeted test per step; the full suite once at close-out. `full` re-runs the suite per task. |

## Parallel sessions and worktrees

| Key | Default | Meaning |
|---|---|---|
| `isolation` | `branch` | `worktree` gives each initiative its own worktree for parallel sessions ([guide](parallel-sessions.md)). |
| `worktree_copy` | `[.sage/config.yaml, .sage/constitution.md, .sage/gates, .sage/agents.toml, .sage/prompts, .sage/scripts, .mcp.json]` | Gitignored paths `sage worktree` seeds INTO a new worktree. |
| `worktree_harvest` | `[.sage/work/*]` | Gitignored paths `sage worktree remove` harvests BACK (trailing `/*` = each child independently). Without this, `.sage/` state dies with the worktree. |

Cycles carry an `owner:` field so `/continue` — and the scope gate — ignore
cycles that belong to another checkout.

## Multi-agent (optional block)

`sage multi-agent install` adds — and `remove` deletes — a block of its own:

```yaml
multi_agent:
  enabled: true
  installed_version: "<the framework version at install time>"
```

You never write this by hand; the installer owns it. The full cross-model
build cycle it enables is documented in [multi-agent.md](multi-agent.md).

## A complete annotated example

```yaml
sage-version: "<stamped by sage init from the framework's VERSION file>"
project-name: "acme-api"
detected-stack: [python]
platforms: ["claude-code"]
command_prefix: /sage

# Quality chain
auto_review: true
auto_qa: true
independent_gate3: true

# Enforcement (protected by the config-gate while the master is on)
hard_enforcement: true
tdd_enforcement: true
# secrets_gate / verify_gate / bookkeeping_gate default ON — only write
# them to opt out.

# Scope Guard — ships OFF until measured (ADR-14)
scope_gate: off              # off | standard+ | all
implicit_test_scope: true
scope_judge: false
# judge_window: 10           # the judge's knobs; protected while armed
# judge_every: 8
# judge_cooldown: 15
# judge_timeout: 60
# judge_cmd: auto

# Review loop v2 (the measured default)
review_loop:
  mode: v2
  major_budget: 0
  iteration_cap: 5
  escalate_after_stalls: 2
  witness_capping: true
  scope_check: true
  review_model: inherit

# Execution-flag defaults (canonical form only)
# quality_locked: true
# autonomous: true
# subagents: true

# Resume close-out economy (lean defaults, measured)
# gate_review: combined
# resume_memory: skip
# resume_test_cadence: lean

# Parallel sessions
isolation: branch
worktree_copy: [.sage/config.yaml, .sage/constitution.md, .sage/gates, .sage/agents.toml, .sage/prompts, .sage/scripts, .mcp.json]
worktree_harvest: [.sage/work/*]
```

## Troubleshooting

- **"sage-config-gate: this would turn OFF enforcement…"** — you (or the
  agent) tried to soften a protected key through a tool call. If the change
  is genuinely wanted, edit `.sage/config.yaml` in your own editor.
- **"scope_gate is on but cycle X has no derived scope"** — the cycle
  reached plan-approval without `scope derive` running. Run the command the
  warning prints; the gate stays open (loudly) until then.
- **"cycle X's plan changed after `scope derive`"** — the plan's
  `Files:`/`Output:` lines were edited without a refresh. Still-declared
  globs stay enforced; run `scope derive --refresh` to re-derive and record
  the delta.
- **A flag default is being ignored** — check the canonical form: exactly
  `subagents: true`, lowercase, one space, no trailing comment.
