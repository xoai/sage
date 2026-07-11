---
name: tests-template
type: pack
variant: tests
version: "1.0.0"
description: Test prompt template for evaluating pack effectiveness.
sections: [test-prompts]
---

# Pack Tests: {pack-name}

**Framework version tested:** {version}
**Last tested:** {date}

## How to Use This File

Each test below is a prompt that should produce different (better) output when
this pack is loaded. To evaluate:

1. Run the prompt WITHOUT this pack loaded — save the output
2. Run the prompt WITH this pack loaded — save the output
3. Compare: did the pack's guidance change the behavior?

A pack should improve output on ≥70% of its test prompts.

---

## Test 1: {descriptive name}

**Prompt:**
```
{The exact prompt to give the agent}
```

**Without pack (expected bad behavior):**
{What the agent typically does wrong — the specific mistake}

**With pack (expected improvement):**
{What the agent should do instead — the specific correction}

**Which pattern/anti-pattern is tested:**
{Reference to the pattern or anti-pattern in this pack}

---

## Test 2: {descriptive name}

**Prompt:**
```
{prompt}
```

**Without pack:** {expected bad behavior}
**With pack:** {expected improvement}
**Tests:** {pattern reference}

---

## Test 3: {descriptive name}

**Prompt:**
```
{prompt}
```

**Without pack:** {expected bad behavior}
**With pack:** {expected improvement}
**Tests:** {pattern reference}

---

<!-- Add more tests as needed. Minimum 3, recommended 5. -->
<!-- Each test should target a different pattern or anti-pattern in the pack. -->
