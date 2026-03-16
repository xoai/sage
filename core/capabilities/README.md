# Sage Core Capabilities

Composable capabilities. The atoms of the framework.

## Philosophy

Capabilities encode **discipline, not knowledge.** An LLM already knows how to
write code or draft a document. It doesn't naturally know to write the test
first, verify its work, stay in scope, or distrust its own assumptions.
Capabilities enforce the processes that produce reliable output — whether that
output is source code, a PRD, a security audit, or a content strategy.

Capabilities are **laws, not suggestions.** We learned from Superpowers that
optional skills get ignored. When a capability is marked `mandatory`, the agent
cannot bypass it — only an explicit human override can, and overrides are logged.

Capabilities use **progressive disclosure.** Following Anthropic's three-level
model: YAML frontmatter (~100 tokens, always loaded) tells Claude WHEN to use
the capability. The SKILL.md body (loaded when triggered) tells Claude HOW.
References and scripts load only as needed.

Capabilities have **trigger-rich descriptions.** A capability that Claude never
loads is one that doesn't exist. Descriptions MUST include both what the
capability does AND trigger phrases matching what users actually say.

Capabilities enforce **degrees of freedom.** Rules sections separate MUST
(violation = bugs or lost work), SHOULD (violation = suboptimal but working),
and MAY (context-dependent choice).

## Deliverable Awareness

Most capabilities work for both code and document deliverables without
modification. The process they encode (understand, define, plan, verify) is
universal. Three capabilities adapt based on the spec's `Deliverable` field:

| Capability | Code Deliverable | Document Deliverable |
|-----------|-----------------|---------------------|
| `specify` | Intent, boundaries, acceptance criteria, affected files | Same, plus infers `deliverable: document` from context |
| `plan` | TDD tasks with Read first / Files / Test / Verify | [DOC] tasks with Read first / Output / Criteria |
| `tdd` | Mandatory — test first | Skipped — replaced by criteria-first drafting |

All other capabilities (elicitation, review, debugging, context management)
work identically regardless of deliverable type. The quality-review skill
reviews code quality for code tasks and content quality for document tasks —
same adversarial review process, different criteria.

## Authoring Conventions

From Anthropic's Skills Guide and our experience building 18 capabilities:

- **Description:** Third person. Include "Use when..." with 3-5 trigger phrases.
  Under 1024 characters. No XML tags.
- **Frontmatter:** Only name, description, version, modes in YAML. Everything
  else in `<!-- sage-metadata -->`.
- **Body:** Under 500 lines. If longer, split into referenced files.
- **References:** One level deep from SKILL.md. Never chain A → B → C.
- **Rules:** Three tiers: MUST, SHOULD, MAY. Match rigidity to fragility.
- **Scripts:** Use deterministic scripts for critical validation. Language is
  supplementary; code is authoritative.
- **Naming:** kebab-case. No "claude" or "anthropic" in names (reserved).
- **Files are named SKILL.md** for Anthropic ecosystem compatibility, but we
  call them "core capabilities" in user-facing docs to distinguish from
  user-extensible packs and playbooks.

## Orchestration — The Entry Layer

These capabilities make the framework accessible. They're the connective
tissue between the user and the workflow engine.

| Capability | Modes | Purpose |
|------------|-------|---------|
| `onboard` | all | First-run setup: detect stack, select packs, generate .sage/ and CLAUDE.md |
| `sage-help` | all | Always-available: reads state, gives ONE specific next action |
| `build-loop` | build, architect | Execution engine: drives task-by-task production with quality gates |
| `deep-elicit` | architect | Socratic exploration: 3 rounds, 9 questions, produces product brief |

## Elicitation — Understand before acting

| Capability | Modes | Philosophy |
|------------|-------|-----------|
| `codebase-scan` | build, architect | Look before you leap. 5 min scanning prevents 5 hours rework. |
| `quick-elicit` | build | Guide humans to think clearly in 2 min, not 20. Ask only what can't be inferred. |
| `deep-elicit` | architect | Socratic exploration of the problem space. 10 min prevents weeks of rework. |

## Planning — Define what and how

| Capability | Modes | Philosophy |
|------------|-------|-----------|
| `specify` | build, architect | Specs say WHAT and WHY. Includes deliverable type: code, document, or mixed. |
| `plan` | build, architect | Tasks clear enough for someone with no context to follow. Adapts template to deliverable type. |

## Execution — Produce with discipline

| Capability | Modes | Activation | Philosophy |
|------------|-------|------------|-----------|
| `tdd` | all | **mandatory** (code tasks) | If you didn't watch the test fail, you don't know if it tests the right thing. |
| `implement` | all | auto | Production is translation, not design. Thinking was done in spec and plan. |
| `build-loop` | build, architect | auto | Execute the plan task by task with quality gates between each. |

## Review — Adversarial verification

| Capability | Modes | Activation | Philosophy |
|------------|-------|------------|-----------|
| `spec-review` | all | **mandatory** | Don't trust the producer. Read the output, not the report. |
| `quality-review` | build, architect | **mandatory** | Spec compliance verifies the right thing. Quality review verifies it's built well. |
| `visual-review` | build, architect | auto (UI tasks) | Does it LOOK right? Screenshots at 3 breakpoints. |

## Debugging — Root causes, not symptoms

| Capability | Modes | Philosophy |
|------------|-------|-----------|
| `systematic-debug` | all | No fix without root cause. Random fixes waste hours and create new bugs. |
| `verify-completion` | all | Run it. Show the output. Claims are not evidence. |

## Context — Maintain continuity

| Capability | Modes | Activation | Philosophy |
|------------|-------|------------|-----------|
| `session-bridge` | all | auto | Next session knows everything without the human repeating anything. |
| `scope-guard` | all | **mandatory** | Every line not in the plan is unreviewed, untested, and unapproved. |
| `tool-use` | all | auto | Cheapest effective tool: local scripts → MCP proxy → subagent. |

## Replacing Capabilities

Read `develop/contracts/skill.contract.md`. Create your capability with
`replaces: <n>`. Place in `.sage/skills/` (project) or `community/skills/`
(contribution). Your version takes priority.
