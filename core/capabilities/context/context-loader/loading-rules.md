# Context Loader

**Version:** 1.0.0
**Status:** Stable

The context loader manages what information is in the agent's context at any given moment.
Context windows are finite and expensive. Loading everything upfront wastes tokens and
overwhelms the agent. Loading nothing means the agent makes uninformed decisions.

The principle: **load the minimum context needed for the current action**.

---

## Loading Tiers

### Tier 0: Always Loaded (every mode, every action)

| Document | Max Tokens | Rationale |
|----------|-----------|-----------|
| Merged constitution | ~2,000 | Governance must always be active |
| Active skill SKILL.md | varies | The agent needs the current skill's instructions |
| Active persona | ~500 | Behavioral overlay for current skill |
| Progress tracker | ~500 | What's been done, what's next |

**Token budget for Tier 0: ~3,000-5,000 tokens**

### Tier 1: Mode-Dependent (loaded when the mode requires it)

| Document | FIX | BUILD | ARCHITECT |
|----------|-----|-------|-----------|
| Feature spec | — | ✓ | ✓ |
| Implementation plan | — | ✓ | ✓ |
| Current task detail | ✓ (if from task list) | ✓ | ✓ |
| Architecture doc | — | — | ✓ |
| PRD | — | — | On-demand |
| Sprint status | — | — | ✓ |

### Tier 2: On-Demand (loaded when a specific skill requests it)

Skill references (e.g., `references/anti-patterns.md` inside a TDD skill),
research documents, previous session logs, and other supporting materials are
loaded ONLY when the active skill explicitly references them.

---

## Constitution Merge Rules

Three tiers merge into one effective constitution:

```
1. Start with Tier 1 (org): ~/.sage/constitution.md
2. Append Tier 2 (project): .sage/constitution.md → additions section
3. Append Tier 3 (feature): .sage/work/<YYYYMMDD>-<slug>/context.md → additions section
4. Apply waivers: mark waived principles as [WAIVED: reason]
5. Result: single merged document, always in context
```

Merge constraints:
- Lower tiers ONLY ADD principles. The loader REJECTS removals or contradictions.
- If a Tier 2 principle contradicts Tier 1, the loader flags an error and keeps Tier 1.
- Waivers are preserved in the merged output so gates can see them.

---

## Skill Context Resolution

When a skill activates, the context loader resolves its `inputs` to actual file paths:

```yaml
# Skill frontmatter
inputs: [spec, plan, constitution]
```

Resolution:
```
"spec"          → .sage/work/<active-initiative>/spec.md
"plan"          → .sage/work/<active-initiative>/plan.md
"constitution"  → (already in Tier 0, no additional load)
"codebase"      → agent scans relevant files (no pre-loading)
"error-report"  → from user's message (no file)
"architecture"  → .sage/specs/architecture.md
```

If a resolved file doesn't exist, the skill receives a `MISSING: <type>` signal
and must handle it gracefully (per skill contract: degrade, don't crash).

---

## Token Budget Management

The context loader tracks approximate token usage:

```
Total budget:     Adapter-declared (e.g., 80,000 for Tier 1, 32,000 for Tier 2)
Tier 0 reserved:  ~5,000 tokens (always loaded)
Available:         budget - 5,000
Skill allocation:  Each skill gets up to (available / 2) for its SKILL.md + references
Working space:     Remaining tokens for agent reasoning + output
```

If a skill's content exceeds its allocation:
1. Load SKILL.md (always fits — skills should be concise).
2. Load references in priority order until allocation is reached.
3. Skip remaining references with a note: "Additional references available on request."

This is why skills should be concise and reference files should be loaded on-demand.

---

## Session Persistence

The context loader reads from and writes to `.sage/progress.md` for cross-session
continuity. When a new session starts:

1. Load `.sage/progress.md` — what was the last action? what's next?
2. Load `.sage/decisions.md` — architectural decisions made so far.
3. Load `.sage/conventions.md` — discovered project conventions.
4. Restore the active mode, feature, and task position.

The agent should be able to resume work seamlessly after a session break.

---

## Pack Loading with Overlays

When packs are enabled, the context loader merges community packs with
project overlays:

```
For each enabled pack:
1. Load community pack content    skills/@sage/<n>/patterns/*.md + anti-patterns/*.md
2. Load constitution additions    skills/@sage/<n>/constitution/*.md
3. Check for project overlay      .sage/skills/@sage/<n>/overrides.md
4. If overlay exists, append it   (overlay adds/overrides community guidance)
```

Overlays are identified by `type: overlay` in their `SKILL.md manifest`.
They extend a community pack rather than replacing it.

**Resolution order for conflicting guidance:**
```
Project overlay     → highest priority (your team's rules)
Community pack      → default (shared knowledge)
Constitution        → lowest for pack-specific items, highest for principles
```

If an overlay says "never use suspense" but the community pack recommends
suspense, the overlay wins for this project. The community pack remains
unchanged for other projects.
