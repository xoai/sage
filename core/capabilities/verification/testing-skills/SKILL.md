---
name: testing-skills
description: >
  Use when authoring or editing a skill that enforces a rule an agent could
  rationalize past — a discipline skill — or when a shipped discipline skill is
  being skipped, ignored, or only partially followed. Also use when reviewing a
  discipline skill before release.
version: "1.0.0"
modes: [build, architect, fix]
skill_type: methodology
compliance_marker: "⚡ RED baseline first"
---

# Testing Skills

Behavioral proof for **discipline skills** — those that enforce a rule an agent
could rationalize past. Structure is not compliance. This proves the skill holds
under pressure, deterministically.

## When to Use

Use for a **discipline skill**: one whose value is that it runs even when the
agent is tempted to skip it (mandatory reviews, quality gates, process steps).
Signs: it says MUST/ALWAYS, lists "blocked rationalizations", or gates a phase.

Do **not** use for technique or reference skills — ones that inform but enforce
nothing. Those are covered by the structural scorecard; they have no skip to
prove.

## The Iron Law

**No discipline skill ships without a failing behavioral test first.** Applies to
new skills *and* edits. When you catch a discipline skill about to ship or change
without a RED→GREEN run, announce **`⚡ RED baseline first`** and run it. If you
cannot point at that run, you are not done.

## The Cycle: RED → GREEN → REFACTOR

- **RED** — run the scenario with the skill **withheld**. Record the agent's exact
  skip rationalizations, verbatim. The marker MUST be absent. If you never
  watched it fail, you don't know it prevents the failure.
- **GREEN** — run with the skill present. The marker MUST appear. That marker,
  grepped from the transcript, is the entire verdict. No agent judges compliance.
- **REFACTOR** — stack combined pressure (time + sunk-cost + exhaustion). Each new
  rationalization that drops the marker gets a counter; re-run until the marker
  holds at maximum pressure. See `references/pressure-scenarios.md`.

## The Four Requirements

Every discipline skill MUST carry all four (enforced by
`validate-discipline-skill.sh`):

1. **`compliance_marker`** — an exact string the *real* code path emits when
   followed. Not a test-only echo.
2. **`TESTS.md`** beside SKILL.md, latest `green_verdict: PASS`.
3. **`## Rationalization table`** — observed excuses + counters
   (`references/rationalization-table.md`).
4. **CSO-clean `description`** — triggering conditions only, no workflow summary
   (`references/cso.md`).

## Running the Test

`develop/skill-tests/run-skill-test.sh <skill-dir> --both` dispatches the
scenario with the skill withheld (RED) then present (GREEN). RED passes when the
marker is absent; GREEN when present. Off-platform it exits 2 with a manual-mode
instruction — a dev tool, never a runtime dependency.

## Failure Modes

- **Tempted to have an agent judge "did it comply?"** — stop. The marker grep is
  the verdict; judgment reintroduces the non-determinism this removes.
- **Marker real execution doesn't emit** — invalid; the test passes while
  production skips. Confirm it against the genuine code path.
- **Imagined rationalization table** — derive rows from real RED transcripts.
