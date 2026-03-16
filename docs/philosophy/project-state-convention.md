# Project State Convention

How Sage organizes generated files in a user's project.

## Directory Structure

```
.sage/
├── progress.md              # Session state — what's done, what's next
├── journal.md               # Living artifact index + append-only change log
├── conventions.md           # Code patterns (auto-discovered by codebase-scan)
├── constitution.md          # Project principles (user-defined)
│
├── docs/                    # Project-level knowledge (flat)
│   ├── jtbd-product-analysis.md
│   ├── opportunity-map-q2.md
│   ├── ux-writing-voice-and-tone.md
│   ├── decision-auth-provider.md
│   └── ...
│
└── work/                    # Per-initiative
    ├── 20260215-user-auth/
    │   ├── brief.md         # WHAT and WHY
    │   ├── spec.md          # HOW to build
    │   └── plan.md          # ORDER — milestones, tasks, checkboxes
    │
    └── 20260315-personal-baseline/
        ├── brief.md
        ├── spec.md
        ├── plan.md
        └── research/        # Initiative-specific discovery (optional)
            ├── jtbd-analysis.md
            └── usability-test-results.md
```

## Naming Conventions

### Work Folders

Format: `YYYYMMDD-slug`

- `YYYYMMDD` — the date the initiative started
- `slug` — lowercase, hyphens, brief descriptive name

Examples: `20260215-user-auth`, `20260315-personal-baseline`,
`20260801-baseline-v2` (revisiting — new date, clear iteration)

### Core Files in Work Folders

| File | Purpose | Who Reads It |
|------|---------|-------------|
| `brief.md` | WHAT to build and WHY. Job stories, acceptance scenarios, constraints. | Stakeholders, PMs, designers, engineers |
| `spec.md` | HOW to build it. Components, data model, APIs, resolved decisions. | Engineers, AI agents |
| `plan.md` | In what ORDER. Milestones, tasks with checkboxes, progress. | AI agents (execute), humans (review) |
| `research/` | Initiative-specific discovery. Optional subfolder. | PMs, designers |

### Project-Level Docs

Format: `skill-prefix-description.md` (flat, no subfolders)

| Prefix | Examples |
|--------|---------|
| `jtbd-` | `jtbd-product-analysis.md` |
| `opportunity-map-` | `opportunity-map-q2-priorities.md` |
| `ux-writing-` | `ux-writing-voice-and-tone.md` |
| `ux-audit-` | `ux-audit-current-homepage.md` |
| `decision-` | `decision-auth-provider.md` |

### Decision Records

Use `decision-` prefix. Format captures: context, options, decision, consequences.

## Cross-Cutting vs Initiative-Specific

If it applies to the whole product → `docs/`.
If it was created for one initiative → `work/YYYYMMDD-slug/research/`.
