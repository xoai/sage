---
name: code-quality
description: Reviews code for readability, error handling, security, performance, and convention adherence.
version: "1.0.0"
order: 3
cost-tier: sonnet
required-context: [implementation, codebase-context, constitution]
category: quality
---

# Gate 3: Code Quality

Is the code well-crafted? Clean, secure, maintainable, and performant?

## Check Criteria

### Readability
- [ ] Names are descriptive and follow project naming conventions
- [ ] Logic flow is clear without requiring comments to understand
- [ ] Functions/methods are reasonably sized (< 40 lines as guideline)
- [ ] No unnecessary complexity — could this be simpler?

### Error Handling
- [ ] No empty catch blocks or swallowed errors
- [ ] Error messages are actionable (help diagnose the problem)
- [ ] External call failures are handled (network, DB, file system)
- [ ] Failure paths have test coverage

### Security (Critical — always causes FAIL)
- [ ] Inputs are validated and sanitized
- [ ] No hardcoded secrets, tokens, or credentials
- [ ] No SQL/NoSQL injection vectors (queries are parameterized)
- [ ] No user data in logs at debug level or higher
- [ ] Authentication/authorization checked where needed
- [ ] Dependencies are from trusted sources with pinned versions

### Performance (flag only obvious issues)
- [ ] No N+1 query patterns
- [ ] No unbounded data loading into memory
- [ ] No blocking operations in async contexts
- [ ] No unnecessary work in hot paths (loops, request handlers)

### Conventions
- [ ] Follows patterns established in the codebase
- [ ] Consistent with project file structure and organization
- [ ] Matches existing code style (formatting, imports, exports)

## Adversarial Guidance

Don't rubber-stamp. Read the code line by line. Look specifically for:
- Security issues hiding in "standard" code patterns
- Error paths that are never tested
- Complexity that could be removed, not just refactored

## Blocked Rationalizations

- "The code is straightforward, a line-by-line review isn't needed" —
  security issues hide in straightforward code. Read every line.
- "This error can't happen in practice" — if you can't prove it
  can't happen, handle it. Production finds ways.
- "The security concern is theoretical" — theoretical security issues
  become real exploits. If it's in the checklist, check it.
- "I already reviewed this in a previous gate" — each gate checks
  different things. Code quality is not spec compliance.
- "The existing codebase does it this way too" — existing patterns
  may be technical debt. Don't propagate known issues.

## Failure Response

**Security issue:** FAIL (always critical). Fix immediately. Re-run.
**Error handling gap:** FAIL if in a failure-likely path. Fix. Re-run.
**Readability/convention issue:** FAIL if severe enough to cause maintenance problems.
Otherwise note as suggestion and PASS.
**Performance concern:** FAIL only with evidence of actual impact. Speculative
performance concerns are suggestions, not failures.
