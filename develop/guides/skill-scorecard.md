# Pack Evaluation Scorecard

How Sage evaluates skill quality. Used for reviewing contributions,
auditing existing packs, and guiding authors.

> **Note:** Thresholds are provisional and will be calibrated from real
> effectiveness testing data as the ecosystem matures.

## Six Dimensions

### 1. Effectiveness (Weight: 30%)

**Question:** Does this pack change agent behavior for the better?

**How to test:** Each pack includes a `tests.md` file with 3-5 representative prompts.
Run each prompt with and without the skill loaded. Compare outputs.

**What to look for:**
- Agent produces different (better) code with the skill loaded
- Anti-patterns the skill warns against are avoided
- Patterns the skill recommends are followed

**Pass threshold:** ≥70% of test prompts show measurable improvement. (Provisional —
L1 domain packs may realistically hit 50-60%, while targeted L2 packs should hit 80%+.
Will calibrate from real data.)

**Red flags:**
- Agent output is identical with and without the skill
- Agent acknowledges the skill's guidance but doesn't follow it
- Improvement is cosmetic (variable naming) rather than structural (architecture)

---

### 2. Specificity (Weight: 20%)

**Question:** Does this pack provide judgment beyond what the LLM already knows?

**The replacement test:** For each pattern, mentally replace it with "read the official
docs for [topic]." If the agent would produce equally good output, the pattern adds
no value — it's restating documentation.

**What earns its place:**
- "ALWAYS do X because agents default to Y which causes Z" — specific correction
- "NEVER do X even though docs show it, because in practice Z happens" — experience
- "When choosing between X and Y, prefer X for [specific reason]" — opinionated judgment

**What doesn't earn its place:**
- "X works by doing Y" — that's documentation, not judgment
- "Consider A, B, or C depending on your needs" — no opinion means no value
- "Best practice is to follow the docs" — obviously

**Pass threshold:** ≥80% of patterns add judgment beyond official documentation.

---

### 3. Accuracy (Weight: 20%)

**Question:** Is the guidance correct for the current framework version?

**How to verify:**
- Cross-reference each pattern against official documentation
- Verify code examples compile/run against the targeted framework version
- Check that anti-patterns reflect actual current agent behavior, not historical issues

**Required fields in SKILL.md manifest:**
```yaml
framework-version: ">=15.0.0"  # What version(s) this pack targets
last-verified: "2026-03-01"    # When accuracy was last checked
```

**Pass threshold:** Zero incorrect or deprecated patterns.

**Staleness indicator:** When the framework releases a major version, every pack
targeting it gets flagged for review. Packs not re-verified within 6 months of a
major release are marked stale.

**Red flags:**
- References to APIs that have been removed or renamed
- Patterns that were best practice in version N but are anti-patterns in version N+1
- Anti-patterns that the framework has since fixed with better defaults

---

### 4. Maintainability (Weight: 15%)

**Question:** How easy is it to keep this pack current when the framework evolves?

**Measured by:** `sage-check-pack.sh` (partially automated)

**Structural checks:**
- Patterns are self-contained (updating one doesn't require updating others)
- Version-specific references are minimized and isolated
- No monolithic files over 150 lines

**Guidelines:**
- Use "current version" language when possible instead of hardcoded version numbers
- Separate universal principles (rarely change) from version-specific details
- Keep files small — a pattern that needs full rewrite on a major version is too coupled

**Why this matters:** Maintainability feeds directly into accuracy over time. A pack
that's hard to update becomes stale faster, and stale guidance is worse than no guidance.

**Red flags:**
- Heavy cross-referencing between patterns (updating one cascades)
- Many hardcoded API signatures (break on minor version updates)

---

### 5. Efficiency (Weight: 10%)

**Question:** Is the context token cost reasonable for the value delivered?

**Measured by:** `sage-check-pack.sh` (automated)

**Token limits per layer:**
- Layer 1 (domain foundations): ≤3500 tokens total
- Layer 2 (framework packs): ≤5000 tokens total
- Layer 3 (stack compositions): ≤1500 tokens total

**Full-stack budget:** A project loading L1 + L2 + L3 should consume ≤10,000 tokens
for pack guidance. This is well under 10% of a modern context window, leaving the
vast majority for code and conversation.

**Per-entry guidelines (not enforced by validator — soft guidance):**
- Per pattern entry: ~80-120 tokens (3-4 sentences + optional code snippet)
- Per anti-pattern entry: ~60-90 tokens (2-3 sentences)

**Red flags:**
- Pack restates information the LLM already knows reliably
- Patterns include lengthy rationale that doesn't change behavior
- Code examples are unnecessarily verbose (full files when a snippet suffices)

---

### 6. Composability (Weight: 5%)

**Question:** Does this pack work correctly alongside other packs in its layer stack?

**Measured by:** `sage-check-pack.sh` (automated)

**Checks:**
- Declared dependencies exist and are valid packs
- No contradictory guidance between this pack and its dependencies
- No redundant content (same guidance repeated across layers)
- Constitution additions don't conflict with parent layer principles
- Total token cost of full stack (this pack + all dependencies) is reasonable

**Red flags:**
- L2 pack contradicts L1 pack it depends on
- Same anti-pattern described in both L1 and L2 (redundancy)
- Pack doesn't declare dependencies but assumes L1 concepts

---

## Weight Summary

| Dimension | Weight | Focus |
|-----------|--------|-------|
| Effectiveness | 30% | Does it change behavior? |
| Specificity | 20% | Judgment or documentation? |
| Accuracy | 20% | Correct for current version? |
| Maintainability | 15% | Easy to keep current? |
| Efficiency | 10% | Reasonable token cost? |
| Composability | 5% | Plays well with others? |

**Philosophy:** Quality-heavy over efficiency-heavy. A pack 200 tokens over budget
that changes behavior 90% of the time is vastly better than a skill within budget
that only works 60%. Token costs matter, but behavior change and correctness matter more.

---

## Automated vs Manual

| Check | Automated | Manual |
|-------|:---------:|:------:|
| Token counting and limits | ✅ | |
| Manifest validation | ✅ | |
| Required sections present | ✅ | |
| Dependency chain valid | ✅ | |
| File structure / sizes | ✅ | |
| Contradiction detection | ✅ | |
| Framework version field | ✅ | |
| Effectiveness (prompt testing) | | ✅ |
| Accuracy (docs cross-reference) | | ✅ |
| Specificity (judgment vs docs) | | ✅ |
| Opinion validity (community consensus) | | ✅ |

---

## For Contributors

Before submitting a skill:

1. Run `bash .sage/tools/sage-check-pack.sh skills/@sage/<your-pack>` — fix all errors
2. Write 3-5 test prompts in `tests.md` — demonstrate behavior change
3. Self-review each pattern: "Would an agent get this wrong without this guidance?"
4. Self-review each anti-pattern: "Have I seen an agent actually do this?"
5. Verify accuracy against current official documentation
6. Check composability: load your pack with its dependencies and look for conflicts

## For Reviewers

When reviewing a skill PR:

1. Confirm `sage-check-pack.sh` passes (automated checks)
2. Run the test prompts from `tests.md` — verify behavior change claims
3. Spot-check 2-3 patterns against official docs for accuracy
4. Apply the specificity replacement test to at least 2 patterns
5. If L2 or L3, verify no contradictions with dependency packs
