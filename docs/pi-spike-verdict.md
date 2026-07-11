# Pi spike — verdict: **UNRESOLVED**

| Field | Value |
|---|---|
| **Question** | Can a Pi extension **deny** a built-in tool call, or only observe it? |
| **Verdict** | **UNRESOLVED — not GO, not NO-GO.** The spike was not run. |
| **Date** | 2026-07-12 |
| **Tier assignment** | **None.** Pi has no row in the capability contract. |
| **Program-3 stub** | **Not written.** A stub requires a GO, and there is no GO. |

---

## Why there is no verdict

Phase 1 was out of scope for this execution run. The spike needs a Pi checkout
and a Pi runtime to build a real extension against, and neither was available.
No Pi source was read; no extension was built; no session was run.

So this document records an **absence**, and that is the entire reason it exists.

## Why the row is empty instead of estimated

ADR-12 rests on a specific unproven assumption: that Pi's extension API can
**veto** a tool call, not merely intercept it. The observed surface
(`pi/packages/coding-agent/src/core/extensions/types.ts`, ~1,666 lines, 30+
events) was reported to include tool-lifecycle events. Whether an extension can
*deny* one has never been demonstrated.

That distinction is the whole decision. Under ADR-11:

- **If Pi can veto:** Tier B (veto + context injection). Sage's gates hold there,
  and a port is worth costing.
- **If Pi can only observe:** Tier C. Sage's rules would be prose on Pi, and the
  v1.2.1 eval measured what prose alone is worth: a behavioural delta of zero.

Those are not adjacent outcomes. They are the difference between a platform worth
porting to and a platform where Sage would be a documentation generator.

**It would have been easy to write a plausible row.** The API surface "suggests"
interception; interception "usually" implies the ability to reject; Pi is a
serious project and would "probably" support it. Every step of that is reasonable
and the conclusion would still be a guess with a table cell around it.

R108 says it plainly: *if the spike was NO-GO or unresolved, the row says so
explicitly rather than guessing.* And this program has spent its entire length
deleting exactly this kind of claim from Sage's own documentation — the
`tier: 1` somebody typed by hand, the `supported-os: [windows]` nobody tested,
the "~200 lines" that was 398, the enforcement table that described mechanisms
nothing checked. Adding a fresh unverified capability claim to the very contract
built to prevent them would be an unusually direct way to miss the point.

So: no `runtime/platforms/community/pi/platform.yaml`. No tier. No stub plan.
An empty row is a true statement; a guessed one is not.

## What running it actually requires

The spike is well-specified (10-spec-phase1-pi-spike.md) and small. It needs:

1. A Pi checkout, and a Pi runtime that can load an extension.
2. **Q1 — the veto question.** The minimum extension that intercepts an
   edit/write/bash tool call and attempts to DENY it, with a reason surfaced back
   to the model. This is the whole spike. If the answer is no, the rest is moot.
3. **Q2 — context injection.** Can the extension put Sage's eager core in front
   of the model at session start?
4. **Q3 — post-tool observation.** Can it audit completed calls (the
   degradation-log pattern)?
5. A headless session transcript proving Q1 **either way** — a NO-GO with evidence
   is a perfectly good outcome and closes the question permanently.

Time-boxed at two days (ADR-12), and the deliverable is a verdict, not code. **No
port code in program 2 regardless of the answer.**

## What to do with this document

If the spike runs, this file is replaced by the real verdict, and P4-T6 fills the
contract row from the evidence — `pre-tool-veto: attested` with the transcript
attached, or `false`, whichever the session actually shows.

Until then it stands as the record that the question was asked, was not answered,
and was **not quietly answered anyway**.
