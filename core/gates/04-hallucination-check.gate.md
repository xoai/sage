---
name: hallucination-check
description: Verifies all imports, APIs, methods, versions, and external references actually exist. Catches AI confabulations.
version: "1.0.0"
order: 4
cost-tier: haiku
required-context: [implementation]
category: safety
---

# Gate 4: Hallucination Check

Does everything the code references actually exist?

AI agents confabulate. They invent API methods that don't exist, import
packages with wrong names, reference configuration options that were
never real, and cite version numbers from their training data that don't
match what's installed. This gate catches those fabrications.

## Deterministic Check Script

**ALWAYS run the hallucination check script first:**

```bash
bash .sage/gates/scripts/sage-hallucination-check.sh src/ .
```

This script automatically: verifies relative imports resolve to real files,
checks imported packages exist in package.json/node_modules, runs TypeScript
compilation check (if tsconfig exists), and detects common hallucinated APIs
(useServer, useClient, Pages Router in App Router). Exit code 0 = pass.

If the script passes, proceed to the manual checks below for items
that require semantic understanding (API method names, version compatibility).

## Check Criteria

### Imports and Dependencies
- [ ] Every imported package exists and is installed (check package.json,
      requirements.txt, go.mod, etc.)
- [ ] Package names are spelled correctly (common: `lodash` vs `Lodash`)
- [ ] Import paths are correct for the project's module system

### API Usage
- [ ] Every method/function called on external libraries actually exists
      in the installed version
- [ ] Method signatures match (correct argument count, correct types)
- [ ] Return types are used correctly (not treating a Promise as a value, etc.)

### Configuration
- [ ] Environment variables referenced in code are documented or have defaults
- [ ] Configuration file paths exist or are created by the implementation
- [ ] Configuration option names are real (not invented by the agent)

### Version Compatibility
- [ ] If code uses features from a specific version, that version is actually
      installed (not a newer version the agent remembers from training)
- [ ] No deprecated APIs used without acknowledgment

### Comments vs Reality
- [ ] Comments accurately describe what the code does
- [ ] Docstrings match actual function behavior
- [ ] README/docs updates match actual implementation

## Adversarial Guidance

Agents are confident about things they've invented. A method that "sounds right"
may not exist. A package that "should have" a feature may not. Check by:
- Reading actual installed package documentation or source
- Verifying method existence in the actual codebase or node_modules
- Running import statements to see if they resolve

Don't trust the agent's memory of an API. Trust the installed code.

## Failure Response

**Non-existent import:** FAIL. Replace with real package/import. Re-run.
**Invented API method:** FAIL. Find the real method or implement the functionality. Re-run.
**Wrong version assumption:** FAIL. Update code to match installed version. Re-run.
**Comment doesn't match code:** FAIL. Fix the comment or fix the code. Re-run.
