# Contributing to Sage

## Ways to Contribute

### Build a Skill

Skills provide technology-specific judgment — when to use framework features,
what patterns to follow, what to avoid. If you're an expert in a framework
Sage doesn't cover yet, a skill is the highest-value contribution.

**Start here:** Read `develop/guides/skill-authoring-guide.md` for the full
process, then `develop/contracts/skill.contract.md` for the formal contract.

**What makes a good skill:**
- Encodes judgment, not documentation (MCP provides docs; skills provide opinions)
- Includes anti-patterns with explanations (why the obvious approach is wrong)
- Uses MUST/SHOULD/MAY degrees of freedom (not everything is a hard rule)
- Defines quality criteria — what good output looks like for this domain
- Includes self-review instructions so the agent checks its own work
- Stays under token budget (200-400 lines for patterns, 100-200 for anti-patterns)

**Needed skills:** Vue/Nuxt, SvelteKit, Django, Go, Laravel, Rails, .NET,
Spring Boot, Tailwind CSS, Prisma, Drizzle.

### Build a Bundle

Bundles provide discipline-specific processes — structured methodologies
that produce expert-quality deliverables. If you're a practitioner in a
discipline Sage doesn't cover yet, a bundle contribution makes the
framework useful for a new audience.

**Start here:** Read `develop/guides/bundle-authoring-guide.md` for the
full process including reference curation, skill anatomy for document
deliverables, phases, skill chains, mode behaviors, and quality standards.

**What makes a good bundle:**
- Has a structured process with concrete deliverables (not general advice)
- References encode methodology that LLMs get wrong without guidance
- Skills define mode behaviors for FIX, BUILD, and ARCHITECT
- Every skill produces an artifact with a defined output path and format
- Tested: "before" (without bundle) vs "after" (with bundle) shows
  meaningful improvement

**Needed bundles:** Content strategy, technical writing, security
assessment, data analysis, game design.

### Improve Existing Modules

- **Fix validation warnings:** Run `bash develop/validators/contracts/validate-all.sh .`
  and address any warnings. Currently 1 remaining (false positive).
- **Add Failure Modes sections:** Some skills are missing this recommended
  section. Check the contract and add practical failure modes.
- **Improve reference files:** If you're a domain expert and a reference file
  is missing important methodology or anti-patterns, propose improvements.
- **Add examples:** Worked examples (like `skills/product-management/examples/jtbd-sample.md`)
  help users understand what good output looks like.

### Report Issues

If Sage produces wrong output, misapplies a methodology, or has a design
flaw, report it. The most valuable reports include:
- What you asked Sage to do
- What it produced
- What a domain expert would have produced instead
- Which reference or skill is responsible for the gap

## Development Setup

```bash
# Clone
git clone <repo-url>
cd sage

# Validate everything passes
bash develop/validators/contracts/validate-all.sh .
# Expected: 311+ passed, 0 failed

# Check structure
find . -name 'SKILL.md' | wc -l   # Skills
find . -name '*.gate.md' | wc -l  # Gates
find skills -maxdepth 1 -type d | wc -l  # Packs
```

## Shell script conventions

Sage's CLI (`bin/sage`), the multi-agent dispatcher
(`runtime/multi-agent/scripts/run-role.sh`), and the platform
generators are bash scripts that run on contributors' and users'
machines — including **macOS, whose default `/bin/bash` is 3.2.57**
(frozen at the last GPLv2 release; it cannot be upgraded in place).

### Empty-safe array expansion (required)

All Sage shell scripts run under `set -euo pipefail`. Under `set -u`,
**bash < 4.4 aborts when an empty array is expanded** via
`"${arr[@]}"` — it treats the empty expansion as an unbound variable.
Bash 4.4+ fixed this, but macOS users on the system bash hit it.

**Rule:** any array that *can be empty* at the point of expansion MUST
use the empty-safe form:

```bash
# WRONG — crashes on macOS bash 3.2 when `args` is empty:
some_command "${args[@]}"

# RIGHT — expands to nothing when empty, identical when non-empty:
some_command ${args[@]+"${args[@]}"}
```

This applies to command arguments, `for` loops, and array assignments
(`new=(${old[@]+"${old[@]}"})`). It's harmless on non-empty arrays and
on modern bash, so when in doubt, use the safe form.

`${#arr[@]}` (the length) and `${arr+set}` (the is-set test) are NOT
affected — only value expansion (`${arr[@]}` / `${arr[*]}`) is.

### Verifying

```bash
# Syntax check
bash -n bin/sage runtime/multi-agent/scripts/run-role.sh

# Static lint for unsafe expansions (must report none).
# Pure-Python, stdlib only — portable across Linux / macOS / WSL.
# Catches quoted, embedded ("text ${arr[*]} text"), and unquoted forms.
python3 develop/validators/check-bash-arrays.py

# Behavioral smoke test under a *real* bash 3.2 (requires Docker).
# Proves the quirk reproduces, the empty-safe idiom works, and every
# script parses under 3.2.
docker run --rm -v "$PWD":/sage -w /sage bash:3.2 \
  bash develop/validators/bash32-smoke.sh
```

CI runs both — a static-lint job on modern bash and a behavioral job
inside the `bash:3.2` container. See `.github/workflows/shell-compat.yml`.

## Code of Conduct

- **Be honest about quality.** If a reference file is wrong, say so. If a
  skill produces generic output, demonstrate the gap. Evidence over opinions.
- **Build what evidence demands.** Don't add modules for hypothetical needs.
  Build when real usage reveals the gap.
- **Respect contracts.** Modules satisfy contracts. If you think a contract
  is wrong, propose a contract change — don't build a module that violates it.

## Contribution Process

1. **Read the relevant contract** for the module type you're contributing.
2. **Read an existing module** of the same type as reference. Start with a
   well-built example:
   - Pack: `skills/nextjs/` or `skills/react/`
   - Playbook: `skills/product-management/` (non-code) or `skills/ux-design/` (enriching)
   - Skill: `core/capabilities/planning/specify/SKILL.md`
3. **Build the module** following the contract and authoring guide.
4. **Run validation:** `bash develop/validators/contracts/validate-all.sh .`
5. **Test:** Compare output with and without your module. Document the
   difference.
6. **Submit** with a description of what it adds and evidence it improves
   output quality.

## Architecture Overview

For contributors who want to understand the full system:

1. Root `README.md` — design principles, project structure
2. `docs/philosophy/design-philosophy.md` — why every architectural decision
   was made (24 sections, 955 lines)
3. `docs/philosophy/project-state-convention.md` — journal, two-folder
   structure, artifact lifecycle
4. `develop/contracts/README.md` — how all contracts relate

## Questions?

Open an issue or read `docs/README.md` for the complete documentation map
with recommended reading orders for different contributor types.
