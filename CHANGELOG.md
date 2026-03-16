# Changelog

All notable changes to Sage will be documented in this file.

## [1.0.1] — Skill Management Improvements

### Improved Search Experience
- **Beautiful display** — skill name left-aligned and bold, registry
  right-aligned with dot leaders, description below in dim. Clean
  vertical rhythm for quick scanning.
- **Interactive install from search** — after `sage find`, type a
  number to install directly. Multi-select loop for installing several
  skills in one session. Press Enter to finish.
- **No auto-refresh** — search uses local index instantly. Bundled seed
  catalog (2,100+ skills) ships with framework for offline use. Explicit
  `--refresh` flag when user wants fresh data from upstream.

### Git-Free Skill Downloads
- **GitHub API download** — `sage add` downloads only the skill folder
  via GitHub API. No git clone of entire repositories. Works on any
  machine with Python 3.8+ and internet.
- **Git as optional fallback** — if API download fails and git is
  available, falls back to cloning. Git is no longer a hard dependency
  for skill management.

### Instant Platform Deployment
- **`sage add` deploys immediately** — skills deploy to `.agent/skills/`
  (Antigravity) right after download. No separate `sage update` needed.
- **`sage remove` undeploys immediately** — removes from both
  `sage/skills/` and `.agent/skills/` in one command.

### Smart Update with Preview
- **`sage skills update`** — shows preview of repositories, skill counts,
  and asks for confirmation before downloading.
- **Selective update** — target by registry (`sage skills update antfu/skills`)
  or individual skill (`sage skills update vue`).
- **Built-in protection** — built-in skills excluded from update (update
  those with `sage upgrade`). `sage remove` warns before removing built-in
  skills.

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
- **33 official skills:**
  - Knowledge: react, nextjs, web, api, mobile, baas, flutter, react-native
  - Composite: stack-nextjs-supabase, stack-nextjs-fullstack, and more
  - PM Process: jtbd, opportunity-map, user-interview, prd
  - UX Process: ux-audit, ux-research, ux-evaluate, ux-brief, ux-discovery,
    ux-specify, ux-plan-tasks, ux-heuristic-review, ux-writing
  - Builder: pack-discover, pack-draft, pack-observe, pack-source-process,
    pack-validate
  - Bundles: product-management, ux-design, skill-builder
- **Progressive enhancement** — community skills work at Layer 0 with
  zero Sage metadata. Add frontmatter for smarter integration.

### Platforms
- **Claude Code** — CLAUDE.md + `.claude/commands/` with slash commands
  generated from core workflows.
- **Antigravity** — GEMINI.md + `.agent/rules/` + `.agent/skills/` +
  `.agent/workflows/` with `/sage`, `/build`, `/fix`, `/architect`, `/status`.
- **Platform-agnostic state** — `.sage/` shared across platforms.

### Installation
- **`sage` CLI** — global install via `curl | bash`. Commands:
  `sage new`, `sage init`, `sage update`, `sage upgrade`. Auto-detects
  platform and stack.

### Project State Convention
- `docs/` — project-level knowledge (flat, skill-prefixed)
- `work/` — per-initiative (`YYYYMMDD-slug/` folders)
- Core files: `brief.md` (WHAT), `spec.md` (HOW), `plan.md` (ORDER)
- Decision records: `decision-*.md` prefix
