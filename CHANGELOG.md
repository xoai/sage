# Changelog

All notable changes to Sage will be documented in this file.

## [1.0.0] — Initial Release

### Core
- **Sage Navigator** — intelligent process orchestration across the
  UNDERSTAND → ENVISION → DELIVER spectrum. Proactive gap detection,
  scope-adaptive process, workflow chaining.
- **Process Constitution** — five non-negotiable rules (State First,
  Skills Before Assumptions, Never Plan Alone, Checkpoints Are Sacred,
  Save State). Platform-adaptive enforcement.
- **18 core capabilities** — elicitation, planning, execution, review,
  debugging, orchestration, and context management.
- **Quality gates** — deterministic verification at each stage.

### Skills
- **33 official skills** in `@sage/` namespace:
  - Knowledge: react, nextjs, web, api, mobile, baas, flutter, react-native
  - Composite: stack-nextjs-supabase, stack-nextjs-fullstack, and more
  - PM Process: jtbd, opportunity-map, user-interview, prd
  - UX Process: ux-audit, ux-research, ux-evaluate, ux-brief, ux-discovery,
    ux-specify, ux-plan-tasks, ux-heuristic-review, ux-writing
  - Builder: pack-discover, pack-draft, pack-observe, pack-source-process, pack-validate
  - Bundles: product-management, ux-design, skill-builder
- **Progressive enhancement** — community skills work at Layer 0 with
  zero Sage metadata. Add frontmatter for smarter integration.

### Platforms
- **Claude Code** — CLAUDE.md with inlined constitution and navigator.
- **Antigravity** — GEMINI.md + `.agent/rules/` + `.agent/skills/` +
  `.agent/workflows/` with `/sage`, `/build`, `/fix`, `/architect`, `/status`.
- **Platform-agnostic state** — `.sage/` shared across platforms.

### Installation
- **`sage` CLI** — global install via `curl | bash`. Commands:
  `sage new`, `sage init`, `sage update`, `sage upgrade`. Auto-detects platform and stack.

### Project State Convention
- `docs/` — project-level knowledge (flat, skill-prefixed)
- `work/` — per-initiative (`YYYYMMDD-slug/` folders)
- Core files: `brief.md` (WHAT), `spec.md` (HOW), `plan.md` (ORDER)
- Decision records: `decision-*.md` prefix
