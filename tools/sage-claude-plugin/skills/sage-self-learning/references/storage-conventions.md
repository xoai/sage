# Storage Conventions

How to structure learnings for reliable storage and retrieval. These
conventions ensure learnings are searchable, distinguishable from
regular memories, and useful when recalled.

## sage-memory Storage (Primary)

### Title Convention

Titles follow the format: `[LRN:<type>] <specific description>`

- The `[LRN:<type>]` prefix makes learnings identifiable in sage_memory_list
  and distinguishes them from codebase knowledge.
- The description is 5-15 words, specific and searchable.
- Use the project's actual vocabulary — class names, library names,
  endpoint paths, error messages.

**Good titles:**
```
[LRN:gotcha] Stripe webhook requires raw body before JSON parsing
[LRN:correction] Project uses pnpm workspaces not npm
[LRN:api-drift] OpenAI v1.x uses tools param not functions
[LRN:error-fix] Docker platform mismatch on Apple Silicon M1
[LRN:convention] All API handlers return {data, error, meta} envelope
```

**Bad titles:**
```
[LRN:gotcha] API issue                    ← too vague, won't retrieve
[LRN:error-fix] Fixed a bug               ← no searchable terms
[LRN:correction] Wrong assumption          ← what assumption?
```

### Tag Convention

Tags use a positional convention:

1. **First tag:** Always `self-learning` (skill namespace, enables
   filtering)
2. **Second tag:** Always the learning type (`gotcha`, `correction`,
   `convention`, `api-drift`, `error-fix`)
3. **Remaining tags:** Domain keywords — library names, concepts, areas

```
tags: ["self-learning", "gotcha", "stripe", "webhooks", "express"]
tags: ["self-learning", "correction", "pnpm", "package-manager"]
tags: ["self-learning", "api-drift", "openai", "tools", "sdk"]
tags: ["self-learning", "error-fix", "docker", "arm64"]
tags: ["self-learning", "convention", "api", "response-format"]
```

Total: 3-6 tags per learning. The `self-learning` namespace tag is
mandatory. Domain tags should match vocabulary the agent would use in
future searches.

### Content Structure

Content follows a four-part pattern with a mandatory prevention rule.

```
What happened:    <symptom or situation>
Why it was wrong: <root cause or misconception>
What's correct:   <the right approach>
Prevention:       <what to check BEFORE this happens again>
```

The prevention rule is the most important part. It transforms the
learning from an incident log into a behavioral instruction that
changes future behavior. During recall, the prevention rule is often
the only part reported to the user.

**Full example:**
```
sage_memory_store:
  title: "[LRN:gotcha] Express body parser must be skipped for Stripe webhooks"
  content: >
    What happened: Webhook signature verification failed with 400
    "No signatures found matching the expected signature."
    Why: Express body parser replaced raw body with parsed JSON before
    the Stripe SDK could verify the signature. Error message is
    misleading — suggests wrong secret, not wrong body format.
    What's correct: Use express.raw({type: 'application/json'})
    middleware for the webhook route, before the global body parser.
    Prevention: Before implementing any webhook handler that verifies
    signatures (Stripe, GitHub, Twilio), check whether the SDK requires
    the raw request body. If yes, ensure body parsing middleware is
    skipped or deferred for that route.
  tags: ["self-learning", "gotcha", "stripe", "webhooks", "express"]
  scope: "project"
```

### Scope Selection

**Project scope** (default): The learning is specific to this codebase.
- Project-specific conventions
- Gotchas about this project's architecture
- File/module-specific behavior

**Global scope**: The learning applies across any project.
- API drift (library X changed behavior in version Y)
- Platform-specific issues (Docker on M1, Windows path handling)
- Tool gotchas (git rebase edge cases, npm vs pnpm detection)
- Error fixes for common tools/frameworks

**Rule of thumb:** If you'd want to know this in a *different* project
that uses the same library/tool, it should be global.

### Search Patterns

**Recall at task start:**
```
sage_memory_search:
  query: "<task-relevant keywords>"
  filter_tags: ["self-learning"]
  limit: 5
```

**Find all learnings of a type:**
```
sage_memory_search:
  query: "<domain keywords>"
  filter_tags: ["self-learning", "gotcha"]
  limit: 10
```

**Search before store (dedup check):**
```
sage_memory_search:
  query: "<key terms from the new learning>"
  filter_tags: ["self-learning"]
  limit: 5
```

**List all learnings (browsing):**
```
sage_memory_list:
  tags: ["self-learning"]
```

Note: `sage_memory_search` uses `filter_tags` for hard WHERE filtering
(sage-memory v0.3+). This excludes non-learning entries entirely.
`sage_memory_list` uses `tags` which already hard-filters. The older `tags`
parameter on `sage_memory_search` is a soft boost — do not use it for
namespace isolation.

## File-Based Storage (Fallback)

When sage-memory MCP tools are not available, store learnings in
the same `.sage-memory/` directory the MCP server would use — one
markdown file per learning, prefixed `lrn-`. This is the same
fallback layout described in SKILL.md and shared with the memory
and ontology skills (one directory, three skill facets, separated
by the `type:` frontmatter field).

### Directory Structure

```
<project-root>/.sage-memory/
  ├── lrn-stripe-webhook-raw-body.md       ← project-scope learning
  ├── lrn-pnpm-workspace.md
  └── ...
~/.sage-memory/
  ├── lrn-postgres-jsonb-index.md          ← global-scope learning
  └── ...
```

One file per learning. Filename slug = short summary, kebab-case,
prefixed `lrn-`. Project vs global is determined by which
`.sage-memory/` directory the file lives in (project's vs `~`).

### File Format

```markdown
---
tags: [self-learning, gotcha, stripe, webhooks]
type: learning
scope: project
created: 2026-03-20
---

[LRN:gotcha] Stripe webhook requires raw body before JSON parsing

What happened: Webhook signature verification failed with 400
"No signatures found matching the expected signature."

Why: Express body parser replaced raw body with parsed JSON before
the Stripe SDK could verify the signature.

What's correct: Use express.raw({type: 'application/json'})
middleware for the webhook route, before the global body parser.

Prevention: Before implementing any webhook handler that verifies
signatures (Stripe, GitHub, Twilio), check whether the SDK requires
the raw request body. If yes, ensure body parsing middleware is
skipped or deferred for that route.
```

The `type: learning` value is what distinguishes a self-learning
entry from a memory (`type: knowledge`) or an ontology entry
(`type: ontology`) when MCP isn't available. The fallback `tags`
array must include `self-learning` so a future migration to MCP
preserves namespace isolation via `filter_tags`.

### Fallback Search

Without sage-memory, search by listing `lrn-*.md` files and
scanning their filenames. Slug names (`lrn-stripe-webhook-raw-body`)
are intentionally descriptive so agents can pick relevant entries
without reading every file's body.

For broad scans (10+ files), read the YAML frontmatter only and
filter by `tags`. Read full body content only for matching files.

### Migration to sage-memory

When sage-memory becomes available, the skill can migrate file-based
learnings by reading each `.sage-memory/lrn-*.md` file and calling
`sage_memory_store` with the parsed title (`[LRN:type] description`
line), body content, frontmatter `tags`, and `scope`. sage-memory's
SHA-256 dedup prevents duplicates if migration runs multiple times.
