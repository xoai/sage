---
name: enterprise
tier: 2
version: "1.0.0"
extends: base
---

# Enterprise Constitution

For production systems with compliance requirements, multiple teams,
and low tolerance for incidents. Adds governance and security
principles on top of the base.

## Additions

6. **All endpoints require authentication.** No public API endpoints
   without an explicit, documented security review and waiver. Internal
   endpoints between services require service-to-service authentication.

7. **Audit trail for mutations.** Every create, update, and delete
   operation must produce an audit log entry with: who, what, when,
   and the previous value. Audit logs are append-only and immutable.

8. **Input validation at every boundary.** Every function that accepts
   external input (API handlers, message consumers, file parsers) must
   validate input structure and content before processing. Validation
   failures return descriptive errors without exposing internals.

9. **No direct database access from handlers.** Business logic lives
   in a service layer. Request handlers call services, services call
   repositories. This enforces separation of concerns and enables
   testing without infrastructure.

10. **Every deployment is reproducible.** Builds are deterministic.
    Environments are defined in code (IaC). Configuration differences
    between environments are limited to environment variables.
    "Works on my machine" is not acceptable.

11. **Breaking changes require migration plans.** API changes, schema
    changes, and interface changes that affect consumers must include
    a migration path. Backward compatibility is preserved for at least
    one release cycle unless a waiver is granted.

12. **Incidents produce postmortems.** Every production incident results
    in a blameless postmortem document within 48 hours. Postmortems
    must include root cause, timeline, impact, and preventive actions.
    Preventive actions become tasks in the next sprint.
