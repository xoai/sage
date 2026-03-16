# Sage Quality Gates

Binary quality checks: PASS or FAIL. The enforcement mechanism.

## Philosophy

Gates exist because **self-assessment is unreliable.** An agent that writes code
then evaluates its own code suffers from the same bias as a human author reviewing
their own writing — they see what they intended, not what they produced.

Gates are **adversarial by design.** Each gate prompt instructs the reviewer to
actively look for problems, not passively confirm quality. The spec compliance
gate says "the implementer finished suspiciously quickly — verify independently."
A gate that always passes is useless.

Gates are **mandatory by default.** Only the project configuration can disable a
gate, and disabling is logged as a waiver. Agents cannot skip gates. Skills cannot
suppress gates. This is non-negotiable because the moment you make gates optional,
they stop running for "simple" changes — which is exactly when bugs slip through.

Gates are **graduated by mode.** FIX mode runs 2 gates (hallucination + verification).
BUILD and ARCHITECT mode run all 5. This matches the adaptive weight principle —
less overhead for smaller work, full rigor for larger work. But even the minimum
(2 gates) catches the most dangerous failures: fabricated APIs and unverified claims.

## Default Gates

| Order | Name | Category | Core Question |
|-------|------|----------|---------------|
| 01 | spec-compliance | compliance | Does it match what was requested? |
| 02 | constitution-compliance | compliance | Does it respect governance principles? |
| 03 | code-quality | quality | Is it clean, secure, and maintainable? |
| 04 | hallucination-check | safety | Is everything the code references real? |
| 05 | verification | verification | Does it actually work when executed? |
| 06 | visual-verification | visual | Does it LOOK right in the browser? |

## Gate Activation by Mode and Deliverable Type

Gates activate based on both the workflow mode AND the task's deliverable type:

| Gate | FIX | BUILD (code) | BUILD (doc) | ARCHITECT (code) | ARCHITECT (doc) |
|------|:---:|:---:|:---:|:---:|:---:|
| 01 Spec compliance | — | ✅ | ✅ | ✅ | ✅ |
| 02 Constitution | — | ✅ | ✅ | ✅ | ✅ |
| 03 Code quality | — | ✅ | — | ✅ | — |
| 04 Hallucination | ✅ | ✅ | — | ✅ | — |
| 05 Verification | ✅ | ✅ | — | ✅ | — |
| 06 Visual | — | ✅* | — | ✅* | — |

\* Gate 06 only for tasks producing visible UI changes.

For **document tasks** (marked with `[DOC]` in the plan): only gates 01 and 02
run. These check "does the document match what the spec asked for?" and "does
it respect project principles?" — both meaningful for documents. Gates 03-06
check code-specific concerns (quality, phantom imports, test passes, visual
rendering) and are meaningless for documents.

For **mixed deliverables**: each task runs the gates appropriate to its type.
Code tasks get all gates. Document tasks get gates 01-02. The plan's `[DOC]`
marker determines which set applies per task.

## Deterministic Gate Scripts

Following Anthropic's principle: "Code is deterministic; language interpretation
isn't." Four gates now have companion bash scripts that handle the verifiable,
mechanical parts of each check:

| Gate | Script | What It Checks Deterministically |
|------|--------|--------------------------------|
| 01 spec-compliance | `scripts/sage-spec-check.sh` | Files listed in task exist, test files present |
| 04 hallucination | `scripts/sage-hallucination-check.sh` | Imports resolve, packages in package.json, TypeScript compiles, no phantom APIs |
| 05 verification | `scripts/sage-verify.sh` | Test runner detected and all tests pass, build compiles, no TODO markers |
| 06 visual | `scripts/sage-visual-gate.sh` | Screenshots captured at 3 breakpoints, no blank pages, no mobile horizontal overflow, no console errors |

Scripts return exit code 0 (pass) or 1 (fail). Gate files instruct: "ALWAYS run
the script first. Language-based checking is supplementary."

The scripts handle WHAT exists and passes. Claude handles WHETHER the code is
semantically correct. This split gives deterministic evidence for the mechanical
checks and reserves Claude's judgment for the things that actually require judgment.

## Why Gates Don't Enforce Pack Rules

Pack rules like "prefer server components" or "don't use useEffect for data
fetching" are judgment calls, not verifiable facts. A bash script can't determine
whether a component SHOULD be a server component — that requires understanding
the component's purpose, its data needs, and the framework's rendering model.

This is a deliberate architectural boundary:

- **Gates verify** — tests pass, imports resolve, no overflow (deterministic)
- **Packs persuade** — use this approach, avoid that pattern (judgment)
- **MCP informs** — here's the current API syntax (knowledge)

Attempting to turn pack rules into gate checks (a "pack linter") would address
only ~15% of rules (the syntactic ones like "no `getServerSideProps` in app/
directory"). The remaining 85% require AST analysis (35%) or semantic judgment
(50%) that scripts can't provide. The maintenance cost of a partial linter
outweighs its value — and creates a false sense of enforcement for rules that
aren't actually checked.

Instead, pack rules reach the agent through the context-aware loading system:
principles always in CLAUDE.md, details loaded via "Read first" in task plans.
The quality-review gate catches violations through AI judgment, not scripts.

## Adding Gates

Extension packs add domain-specific gates (order 50+). Projects add custom gates
in `.sage/gates/`. See `develop/contracts/gate.contract.md`.
