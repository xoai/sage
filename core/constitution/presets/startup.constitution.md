---
name: startup
tier: 2
version: "1.0.0"
extends: base
---

# Startup Constitution

For early-stage projects that need to move fast without accumulating
crippling technical debt. Adds velocity-focused principles on top of
the base safety net.

## Additions

6. **Ship smallest viable increment.** Build the minimum that validates
   the hypothesis. Features that aren't validated by users are waste.
   No "V2 features" in V1. No abstractions before the third use case.

7. **One way to do things.** Pick one pattern for each concern (one ORM,
   one state management approach, one API style) and use it everywhere.
   Consistency beats theoretical best-fit. Revisit when evidence shows
   the pattern doesn't scale.

8. **Logs over dashboards.** Structured logging from day one. Dashboards
   come when you know what metrics matter. Don't build observability
   infrastructure before you have users.

9. **Monolith first.** Start with a single deployable unit. Extract services
   only when you have evidence that a boundary exists (different scaling
   needs, different team ownership, different deployment cadence).
