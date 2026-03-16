# Bundle Skill Contract

**Version:** 1.0.0
**Status:** Stable

A playbook is a discipline-specific process that weaves into the development
workflow at defined integration points. Playbooks contain their own skills,
sub-workflows, references, and quality gates — organized around a discipline
(UX design, product strategy, game design) rather than a technology.

Playbooks are structurally between workflows and skills in complexity. A skill
is atomic (one job, 2-5 minutes). A workflow orchestrates the full development
lifecycle. A playbook is a structured, sequenced process within a specific
discipline that integrates at defined phases of the workflow.

---

## The Litmus Test

**"If I switch my entire tech stack tomorrow, does this pack still apply?"**

If **yes** → playbook. It's a discipline-specific process.
If **no** → domain extension. It's technology-specific knowledge.

UX design, product strategy, and game design processes apply regardless of
whether you build in React, Flutter, or a CLI. They are playbooks.

---

## Playbook vs Other Module Types

| Dimension | Playbook | Domain Extension | Skill |
|-----------|----------|-----------------|-------|
| **Complexity** | Multi-step process with sequence | Bundle of patterns and gates | Single atomic capability |
| **Contains skills?** | Yes — discipline-specific | Yes — tech-specific | No — IS a skill |
| **Has sequence?** | Yes — ordered phases | No — loaded on detection | No — standalone |
| **Produces artifacts?** | Yes — journey maps, personas, hypotheses | No — provides patterns | No — executes a task |
| **Tech-agnostic?** | Yes | No | Depends |
| **Activation** | Mode-based (light BUILD, full ARCHITECT) | Codebase detection | Workflow references |
| **Integration** | Weaves into workflow phases | Adds new workflow steps | Is a workflow step |

### Phase Gravity

Playbooks pull toward the LEFT side of the workflow — discovery, specification,
planning. They shape WHAT gets built. Domain extensions pull toward the RIGHT —
implementation, review, verification. They shape HOW it's built.

```
DISCOVER → SPECIFY → PLAN → IMPLEMENT → REVIEW → VERIFY
 ◄──── playbook gravity ────────►
                        ◄──── extension gravity ────────────►
```

---

## Required Directory Structure

```
skills/@sage/<playbook-name>/
├── playbook.yaml                # REQUIRED — Manifest with integration points
├── README.md                    # REQUIRED — Purpose, discipline, what it produces
│
├── core/capabilities/                      # REQUIRED — Discipline-specific skills (min 1)
│   └── <skill-name>/
│       └── SKILL.md             # Must satisfy skill.contract.md
│
├── core/workflows/                   # OPTIONAL — Sub-workflows for ARCHITECT mode
│   └── <name>.workflow.md
│
├── references/                  # OPTIONAL — Supporting knowledge for skills
│   └── *.md
│
├── core/constitution/                # OPTIONAL — Discipline principles
│   └── *.constitution-additions.md
│
├── core/gates/                       # OPTIONAL — Discipline-specific quality checks
│   └── <NN>-<name>.gate.md     # Order 50+ (core gates are 01-49)
│
└── persona-enrichments/         # OPTIONAL — Additional principles for personas
    └── <persona-name>.enrichment.md
```

---

## Required Manifest (playbook.yaml)

```yaml
---
# REQUIRED FIELDS
name: <string>                    # Scoped name: "@sage/play-ux-design"
description: <string>             # What discipline this covers
version: <semver>
type: playbook                    # MUST be "playbook"

# REQUIRED: Integration points — where this playbook weaves into the workflow
integrates-at:
  <workflow-phase>:               # One of: elicitation, specification, planning, review
    skill: <skill-name>           # The playbook skill that runs at this phase
    mode-depth:
      build: light | full | none  # How much work in BUILD mode
      architect: light | full     # How much work in ARCHITECT mode
    runs: alongside | after       # Relative to the core skill at this phase
    produces: [<artifact-names>]  # What artifacts this integration point creates

# OPTIONAL
provides:
  skills: [<skill-names>]
  workflows: [<workflow-names>]
  references: [<filenames>]
  constitution-additions: [<filenames>]
  gates: [<gate-names>]
  persona-enrichments: [<persona-names>]

requires:
  sage-core: <semver-range>
---
```

### Integration Points

The four workflow phases where playbooks can integrate:

| Phase | Core Skill | Playbook Runs | Produces |
|-------|-----------|---------------|----------|
| `elicitation` | quick-elicit | alongside or after | User research artifacts |
| `specification` | specify | after | Enriched spec with discipline perspective |
| `planning` | plan | after | Additional tasks in the plan |
| `review` | quality-review | alongside | Discipline-specific quality assessment |

### Mode Depth

Playbooks respect the adaptive weight model:

**none:** This integration point doesn't activate in this mode.

**light:** The playbook skill runs a compressed version — adds a few
considerations or questions within the existing time budget. Adds ~30 seconds
to the phase, not 30 minutes.

**full:** The playbook skill runs its complete process. May take significant
time (15-60 minutes). Justified in ARCHITECT mode where planning investment
matches implementation cost.

### Runs: alongside vs after

**alongside:** The playbook skill's considerations are merged into the core
skill's execution. The core skill and playbook skill produce a single combined
output. Used when the bundle adds perspective to an existing activity
(e.g., UX questions woven into elicitation).

**after:** The playbook skill runs as a separate step after the core skill
completes. Produces its own artifacts. Used when the bundle has a distinct
process that takes the core skill's output as input (e.g., journey mapping
runs after specification, taking the spec as input).

---

## Behavioral Contract

Playbooks MUST:

1. **Have at least one integration point.** A playbook without integration points
   is just a bag of files. Integration points are what make it a process that
   weaves into the workflow.
2. **Have at least one skill.** The integration points reference skills. Skills
   do the actual work. References are supporting material, not the main event.
3. **Respect mode depth.** Light mode adds considerations, not process. Full mode
   runs the complete discipline process. A playbook that makes BUILD mode feel
   like ARCHITECT mode has violated the adaptive weight contract.
4. **Be tech-stack agnostic.** No references to specific frameworks, languages,
   or tools. If the bundle content mentions React, it belongs in a domain
   extension, not a bundle skill.
5. **Declare what it produces.** Each integration point should declare the
   artifacts it creates. The workflow executor and downstream skills need to
   know what new documents exist.

Playbooks MUST NOT:

1. **Replace core skills.** Playbook skills integrate alongside or after core
   skills. They never replace `specify`, `plan`, `tdd`, or any core skill.
2. **Add workflow steps outside their integration points.** A playbook can't
   insert an arbitrary step between "plan" and "implement." It integrates at
   defined phases.
3. **Conflict with other playbooks.** Multiple playbooks can be active
   simultaneously. When two playbooks integrate at the same phase, they run
   in sequence (config.yaml order). Each one enriches the output of the
   previous one.

---

## How Multiple Playbooks Compose

When multiple playbooks are installed and active:

```yaml
# .sage/config.yaml
playbooks:
  enabled: [ux-design, product]
```

At each integration point, playbook skills run in listed order:

```
elicitation phase:
  1. quick-elicit (core)
  2. ux-discovery (from ux-design playbook, alongside)
  3. product-discovery (from product playbook, alongside)

specification phase:
  1. specify (core)
  2. ux-specify (from ux-design playbook, after)
  3. product-hypothesis (from product playbook, after)
```

Each playbook's output enriches the artifacts for the next. The UX playbook
adds journey maps and personas to the spec. The product playbook then reads
those enriched specs and adds hypotheses and risk assessments. No conflicts
because each adds without modifying what came before.

---

## User Experience

```bash
# Install playbooks
sage playbooks add @sage/play-ux-design
sage playbooks add @sage/play-product

# They integrate automatically based on mode
/sage:build "add user profile page"
# → UX discovery runs light alongside elicitation
# → UX specify runs light after specification

/sage:architect "new onboarding flow"
# → Full UX discovery process: research, personas, journey mapping
# → Full product hypothesis and risk assessment
# → UX tasks added to the plan (usability testing, etc.)
# → UX heuristic review added to quality gates
```

In `.sage/config.yaml`:
```yaml
playbooks:
  enabled: [ux-design, product]
```
