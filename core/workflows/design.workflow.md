---
name: design
version: "1.0.0"
mode: design
produces: ["UX brief", "Feature spec", "Content/copy", "PRD"]
checkpoints: 2
scope: "Single session for focused, multi-session for comprehensive"
user-role: "Define scope, approve design deliverables"
---

# Design Workflow

Shape solutions. Reads research context, produces specs ready for build.

## Auto-Pickup

Scan `.sage/work/` for design initiatives with `status: in-progress`.
This scan is MANDATORY — check the DISK.

Scan `.sage/docs/` for upstream research artifacts:
  jtbd-*.md, ux-audit-*.md, opportunity-*.md, user-interview-*.md

If research found: "Sage: Found research context — [list].
Using as design input."

If design artifacts exist: resume from current phase.

Read `.sage/decisions.md` for context. Read `handoff` field in
the most recent artifact if present.

## Step 1: Scope the Design (Zone 1)

If research context was found:

Sage → design workflow.
Found research: [list of .sage/docs/ artifacts].

[1] Feature design — UX brief → detailed spec (2 steps)
[2] Content/copy — UX writing (1 step)
[3] Product requirements — PRD (1 step)
[4] Comprehensive — brief → spec → copy (3 steps)

Pick 1-4, type / for commands, or describe what you need.

If no research context:

Sage → design workflow. No prior research found.

[1] Feature design — UX brief → detailed spec (2 steps)
[2] Content/copy — UX writing (1 step)
[3] Product requirements — PRD (1 step)
[4] Research first — type /research to understand before designing

Pick 1-4, type / for commands, or describe what you need.

## Step 2: Execute Skill Chain

Based on scope, load and execute skills in sequence:

| Scope | Skill Chain |
|-------|-------------|
| Feature | ux-brief → ux-specify |
| Content | ux-writing |
| PRD | prd |
| Comprehensive | ux-brief → ux-specify → ux-writing |

For each skill in the chain:
1. Announce: "Sage: Starting [skill name]."
2. Load `sage/skills/[skill]/SKILL.md` and follow its process
3. If research context exists, reference it during execution
4. Save output to `.sage/work/YYYYMMDD-slug/[artifact].md`
   with standard frontmatter (title, status, phase)
5. Present per-artifact checkpoint (Zone 2):

Sage: [Artifact] saved to .sage/work/YYYYMMDD-slug/[name].md
Decision: [key design decision]. (prepended to decisions.md)

[A] Approve — continue to next step  [R] Revise

Pick A/R, or tell me what to change.

6. On approval, proceed to next skill in chain

## Step 3: Design Completion (Zone 2)

🔒 **DESIGN CHECKPOINT:**

**Self-check (observable conditions):**
- [ ] Design artifacts exist in .sage/work/
- [ ] If research context was available, findings are reflected
- [ ] Key design decisions are documented

Sage: Design complete.

Artifacts:
  .sage/work/YYYYMMDD-slug/brief.md
  .sage/work/YYYYMMDD-slug/spec.md

Decision: [key design decisions]. (prepended to decisions.md)

[A] Approve  [R] Revise  [V] → /review  [N] New session → /build

Pick A/R/V/N, or tell me what to change.

On approval: update artifact frontmatter to `status: completed`.
Write `handoff` field:
```yaml
handoff: |
  Key decisions: [design choices and rationale]
  Research context: [what research informed this design]
  Open questions: [what needs resolution during build]
  Next agent should: [guidance for implementation]
```
Prepend to decisions.md (Rule 7).

## Step 4: Next Step (Zone 3)

Next steps:
  /build   — spec → plan → implement → verify (reads your design)
  /review  — independent evaluation of the design
  /reflect — review design decisions before building

Type a command, or describe what you want to do next.

## Quality Criteria

Good design output:
- Grounded in research when available (references findings)
- Decisions have explicit rationale (not just "I chose X")
- User flows are concrete (screens, states, transitions)
- Edge cases are identified and handled
- The spec is implementable — a developer can build from it

## Rules

- Load research context if it exists in .sage/docs/
- Save all artifacts to .sage/work/ with frontmatter
- Checkpoints between each skill in the chain
- Handoff field on completion for the next agent
- If no research exists and scope is complex, suggest /research first
