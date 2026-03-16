---
name: opensource
tier: 2
version: "1.0.0"
extends: base
---

# Open Source Constitution

For open source projects that accept community contributions.
Adds principles that make the codebase approachable and contributions
reviewable.

## Additions

6. **Documentation mirrors code.** Every public API, configuration option,
   and behavioral change must have corresponding documentation updated
   in the same commit. Undocumented features don't exist to users.

7. **License compliance on all dependencies.** Every dependency must have
   a license compatible with the project's license. Copyleft dependencies
   (GPL, AGPL) require explicit approval. License checks run in CI.

8. **Contributor-friendly code.** Prefer explicitness over cleverness.
   A new contributor should understand any function in under 2 minutes
   of reading. Complex algorithms get explanatory comments with
   references to the underlying technique.

9. **Semantic versioning is a contract.** Public API changes follow strict
   semver: patch for fixes, minor for additive changes, major for breaking
   changes. Breaking changes in minor/patch versions are constitution
   violations.

10. **CI must pass before merge.** No exceptions. If CI is broken, fix CI
    first. If a test is flaky, fix the test. Never merge with red CI.
