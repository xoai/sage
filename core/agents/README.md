# Sage Agent Personas

Lightweight behavioral overlays. Style, not substance.

## Philosophy

Personas shape **HOW**, not **WHAT.** Skills define the process (write test first,
read the error, check the spec). Personas define the approach (be pragmatic, be
skeptical, ask before assuming). A persona that contradicts a skill is broken.

Personas are **lightweight by design** — under 500 tokens each. This is deliberate.
BMAD uses heavy persona files (thousands of tokens per agent) loaded in separate
sessions. Sage uses thin overlays injected alongside the active skill. This keeps
context budgets manageable while still providing behavioral differentiation.

**One agent, many personas.** The agent shifts persona based on which skill is active.
When implementing, the developer persona applies (YAGNI, show code). When reviewing,
the reviewer persona applies (read code not reports, assume the author rushed). When
debugging, the debugger persona applies (evidence before action, one variable at a time).
This models how a real senior engineer shifts mindset between building and reviewing.

Personas resist **anti-patterns** by naming them explicitly. The developer persona lists
"let me also add..." as an anti-pattern. The reviewer lists "it's probably fine..." as one.
Naming the behavior makes the agent recognize it when it occurs — the same technique
Superpowers uses for TDD rationalizations.

## Available Personas

| Persona | Modes | Applied To | Core Trait |
|---------|-------|-----------|------------|
| [developer](developer.persona.md) | all | implement, tdd | Pragmatic — YAGNI, ask before assuming |
| [reviewer](reviewer.persona.md) | all | spec-review, quality-review | Skeptical — reads code, distrusts reports |
| [architect](architect.persona.md) | architect | specify, plan | Systems thinker — explicit trade-offs, minimum 2 options |
| [analyst](analyst.persona.md) | architect | quick-elicit, specify | Socratic — asks WHY, uncovers real problems |
| [debugger](debugger.persona.md) | all | systematic-debug, verify-completion | Evidence-driven — refuses to guess |

## Replacing Personas

Teams often customize personas to match their culture. Create `<n>.persona.md` with
`replaces: developer` in frontmatter. Place in `.sage/agents/` (project) or
`community/core/agents/` (contribution).
