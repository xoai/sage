# Sage Constitution

Governance as code. The highest authority.

## Philosophy

The constitution is the only document loaded in **every mode, every session, every
action.** It's not a reference you consult when convenient — it's a constraint that
shapes every decision.

Constitutions contain **enforceable principles, not aspirational goals.** "We value
security" is aspirational — a gate can't check it. "All API endpoints must require
authentication" is enforceable — Gate 02 can verify it against code. If a gate can't
check a principle, the principle doesn't belong in the constitution.

The three-tier model (**org → project → feature**) solves a real organizational
problem: engineering teams need standards that apply to ALL projects without manually
copying rules everywhere. An org constitution mandates "no public endpoints without
auth" once, and every project inherits it. Lower tiers ADD constraints but cannot
REMOVE inherited ones. Waivers are the only exemption, and they require explicit
documentation with reason, scope, approver, and expiration.

Constitutions should be **concise.** Ten sharp principles beat fifty vague ones.
Aim for under 2,000 tokens merged. Move implementation details out — "use JWT with
RS256" belongs in architecture.md, not in the constitution.

## Available Constitutions

| Name | Extends | For |
|------|---------|-----|
| [base](base.constitution.md) | — | 5 universal principles (TDD, no silent failures, no secrets in code, explicit deps, reversible changes) |
| [startup](presets/startup.constitution.md) | base | Ship small, one way to do things, logs over dashboards, monolith first |
| [enterprise](presets/enterprise.constitution.md) | base | Auth everywhere, audit trails, input validation, reproducible deploys, postmortems |
| [opensource](presets/opensource.constitution.md) | base | Docs mirror code, license compliance, contributor-friendly, strict semver |

## Usage

```yaml
# .sage/constitution.md
---
name: my-project
tier: 2
extends: startup
---
## Additions
6. All APIs use REST with JSON. No GraphQL.
7. PostgreSQL is the only approved database.
```

See `develop/contracts/constitution.contract.md` for the full specification.
