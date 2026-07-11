---
name: problem-solving
description: >
  Systematic techniques for breaking through when stuck. Activate when:
  the agent has tried 3+ approaches without resolution, complexity is
  spiraling with growing special cases, a test keeps failing after
  multiple fix attempts, or the solution feels forced with no
  alternatives considered.
version: "1.0.0"
---

# Problem-Solving

Structured techniques for different types of stuck-ness. Each targets
a specific pattern. Don't try harder — try differently.

## When to Activate

Observable triggers — the agent or navigator detects:

- **Complexity spiral:** 3+ approaches tried, special cases growing,
  "just one more condition" repeating
- **Assumption trap:** Solution feels forced, "only way to do it,"
  no alternatives considered
- **Scale mismatch:** Works in dev, breaks in production. Passes with
  test data, fails with real data
- **Undiagnosed failure:** Test keeps failing after multiple fix
  attempts without clear root cause

If you notice any of these patterns in your own work, STOP and
apply the matching technique below.

## Technique Dispatch

| Stuck Pattern | Technique | Reference |
|---------------|-----------|-----------|
| Growing special cases, 3+ implementations | **Simplification** | `references/simplification.md` |
| "Only one way," forced solution | **Inversion** | `references/inversion.md` |
| Works small, breaks at scale | **Scale Testing** | `references/scale-testing.md` |
| Can't isolate the cause | **Minimal Reproduction** | `references/minimal-reproduction.md` |

## Quick Reference

### Simplification

The problem has too many moving parts. Find one insight that
eliminates multiple components.

Ask: "If [X] were true, what could I remove?"

**Red flag:** "Just need to add one more case..." (repeating)

### Inversion

You're trapped by an assumption you haven't questioned. Flip it.

Ask: "What if the opposite of my core assumption were true?"

**Red flag:** "There's only one way to do this"

### Scale Testing

The solution works at one scale but breaks at another. Test at
extremes to expose fundamental design issues.

Ask: "What happens at 1000x? What happens at 1/1000th?"

**Red flag:** "Should scale fine" (without evidence)

### Minimal Reproduction

You can't isolate the cause because there's too much context.
Strip the problem to the smallest case that still exhibits the issue.

Ask: "What's the simplest possible reproduction?"

**Red flag:** "It only happens in the full system" (usually means
the reproduction isn't minimal enough)

## Application Process

1. **Recognize the pattern.** Match your stuck-ness to the dispatch
   table above. If unsure, start with Minimal Reproduction — it
   works for most problems.
2. **Load the reference.** Read the detailed technique from `references/`.
3. **Apply systematically.** Follow the technique's steps. Don't
   skip ahead — each step builds on the previous.
4. **Document the insight.** When you break through, store the
   finding via Post-Flight memory (tagged `learning`). This prevents
   future agents from hitting the same wall.

## Combining Techniques

Some problems need multiple techniques in sequence:

- **Minimal Reproduction + Simplification:** Reduce to smallest case,
  then find the unifying insight that eliminates complexity
- **Inversion + Scale Testing:** Flip assumptions, then test the
  inverted approach at extremes
- **Scale Testing + Simplification:** Extremes reveal which
  components actually matter, then simplify around those

## Quality Criteria

**Communication style:** Diagnostic precision. Show the reasoning
chain — what was tried, what failed, what the technique revealed,
and why the new approach is better.

Good problem-solving output:
- The stuck pattern is identified explicitly, not just "I tried a
  different approach"
- The technique applied is named and the steps are visible
- The breakthrough insight is articulated clearly — what changed
  in understanding, not just what changed in code
- The finding is stored in memory to prevent recurrence
- If the technique didn't work, that's documented too — with
  reasoning about why and which technique to try next

## Self-Review

Before claiming a breakthrough, check:
- Did I actually change my approach, or just try the same thing
  with minor variations?
- Can I explain WHY the new approach works, not just THAT it works?
- Would this insight help a future agent facing a similar problem?
