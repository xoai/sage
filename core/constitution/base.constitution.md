---
name: base
tier: 2
version: "1.0.0"
---

# Sage Base Constitution

Universal engineering principles. Every Sage project inherits these.
Projects extend by adding principles — they cannot remove these.

## Principles

1. **Tests before code.** Every behavior has a test written before the
   implementation. Code without tests is unverified code.

   The observable condition, because "write tests first" is rationalizable and
   measurably gets rationalized: **a commit that changes behavior must contain, or
   follow, a commit containing a test that fails without it.** "It's only one
   number", "it's just config", "it's boilerplate" and "the tests already cover it"
   are not exemptions — they are the four excuses this principle exists to refuse.
   Nothing in Sage mechanically blocks a test-less commit; this rule is yours to
   keep.

2. **No silent failures.** Errors must be handled, logged, or propagated.
   Empty catch blocks, swallowed exceptions, and ignored return values
   are violations. If something can fail, the failure path must be explicit.

3. **Secrets never in code.** No hardcoded passwords, tokens, API keys,
   or credentials in source files. Use environment variables, secret
   managers, or configuration files excluded from version control.

4. **Dependencies are explicit.** Every external dependency must be declared
   in the project's dependency manifest with a pinned or range-locked version.
   No vendored code without documentation. No implicit global dependencies.

5. **Changes are reversible.** Database migrations must be reversible.
   Feature flags should allow rollback. Deployments should support rollback.
   Irreversible changes require explicit approval and a recovery plan.
