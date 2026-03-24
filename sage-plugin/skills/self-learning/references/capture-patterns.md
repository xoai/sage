# Capture Patterns

When to capture, what to capture, and how to write prevention rules.

## The Prevention Rule

Every learning must include a prevention rule — a forward-looking
instruction that tells the agent what to check *before* the same mistake
happens again. This is the most important part of any learning.

**The test:** If recalled before a future task, does this learning change
behavior? A good prevention rule does. An incident report doesn't.

```
Incident report (weak):   "Webhook verification failed because body was parsed."
Prevention rule (strong):  "Before implementing any webhook handler that verifies
                            signatures, check if the SDK requires the raw request
                            body. If yes, skip body parsing for that route."
```

The prevention rule is the *first thing reported during recall*. Write
it as an instruction, not as history.

## Detection Triggers

### Corrections (→ type: correction)

The user tells you something was wrong. Phrases to watch for:

- "No, that's not right..."
- "Actually, it should be..."
- "You're wrong about..."
- "That's outdated..."
- "We don't do it that way here..."

**What to capture:** What you assumed, what's correct, why the difference
matters, and what to check next time.

**Example:**
```
Title:   [LRN:correction] This project uses pnpm workspaces not npm
Content:
  What happened: Attempted to run `npm install`.
  Why wrong: Project uses pnpm workspaces. Lock file is pnpm-lock.yaml.
  What's correct: Use `pnpm install` for all dependency operations.
  Prevention: Before running any package install command, check for
  pnpm-lock.yaml, yarn.lock, or bun.lockb. Only use npm if
  package-lock.json is present or no lock file exists.
Tags:    ["self-learning", "correction", "pnpm", "package-manager"]
```

### Gotchas (→ type: gotcha)

Something non-obvious discovered through debugging or investigation.

Signals:
- A fix that required reading source code, not just docs
- Behavior that contradicts reasonable assumptions
- Environment-specific issues (OS, version, config)
- Timing-sensitive or order-dependent behavior
- Silent failures (no error, just wrong results)

**Example:**
```
Title:   [LRN:gotcha] Express body parser must be skipped for Stripe webhooks
Content:
  What happened: Webhook signature verification failed with 400 "No
  signatures found matching the expected signature."
  Why wrong: Express body parser replaced raw body with parsed JSON
  before Stripe SDK could verify. The error message misleadingly
  suggests wrong signing secret, not wrong body format.
  What's correct: Use express.raw({type: 'application/json'})
  middleware specifically for the webhook route.
  Prevention: Before implementing any webhook handler that verifies
  signatures (Stripe, GitHub, Twilio), check whether the SDK requires
  the raw request body. If yes, ensure body parsing middleware is
  skipped or deferred for that route.
Tags:    ["self-learning", "gotcha", "stripe", "webhooks", "express"]
```

### Conventions (→ type: convention)

An undocumented project or team pattern discovered through code reading
or user feedback.

Signals:
- Multiple files follow the same pattern but it's not documented
- The user refers to "how we do it" without formal documentation
- A code review reveals an expected pattern the agent didn't follow

**Example:**
```
Title:   [LRN:convention] All API handlers return {data, error, meta} envelope
Content:
  What happened: Created a new endpoint returning bare JSON.
  Why wrong: Project convention requires {data, error, meta} envelope
  on all responses. 40+ handlers follow this pattern. Exception:
  webhook handlers in src/api/webhooks/ return raw status codes.
  What's correct: Wrap all API responses in the envelope structure.
  Validation errors use error field with 422 status.
  Prevention: Before creating any new API handler in src/api/, check
  an existing handler for the response envelope pattern. Mirror the
  structure exactly, including the meta field with requestId and
  timestamp.
Tags:    ["self-learning", "convention", "api", "response-format"]
```

### API Drift (→ type: api-drift)

An API or library behaves differently than training data suggests.

Signals:
- A function/method/parameter that no longer exists
- Default behavior that changed between versions
- A deprecated pattern that the agent used
- New required parameters or authentication methods

**Example:**
```
Title:   [LRN:api-drift] OpenAI SDK v1.x: use tools param not functions
Content:
  What happened: Used `functions` parameter in chat.completions.create().
  Why wrong: `functions` is the v0.x syntax. In v1.x+ the parameter is
  `tools` with type "function". Old param raises deprecation warning.
  What's correct: Wrap each function definition in
  {"type": "function", "function": {...}} and pass as `tools`.
  Prevention: Before using any LLM SDK for function/tool calling,
  verify the current parameter name and format. Check the installed
  SDK version (`pip show openai`) and match the syntax to that version.
Tags:    ["self-learning", "api-drift", "openai", "tools", "functions"]
Scope:   global
```

### Error Fixes (→ type: error-fix)

A recurring error with a known solution.

Signals:
- The same error message appeared before
- The error message is misleading about the actual cause
- Platform-specific errors (M1 Mac, Windows paths, Docker)

**Example:**
```
Title:   [LRN:error-fix] Docker "no match for platform" on Apple Silicon
Content:
  What happened: Docker build failed with "no match for platform
  linux/arm64" on M1 Mac.
  Why wrong: Base image doesn't have ARM64 variant. Docker defaults
  to the host platform on Apple Silicon.
  What's correct: Add --platform linux/amd64 to docker build, or
  FROM --platform=linux/amd64 in Dockerfile.
  Prevention: Before writing a Dockerfile or docker build command,
  check if the target base image has ARM64 support. If running on
  Apple Silicon and the image is AMD64-only, add explicit
  --platform linux/amd64. Note: ~20% perf hit from Rosetta emulation.
Tags:    ["self-learning", "error-fix", "docker", "arm64", "apple-silicon"]
Scope:   global
```

## Writing Good Prevention Rules

A prevention rule should be:

**Actionable.** It tells the agent what to *do*, not what *happened*.
```
Bad:  "This caused an error last time."
Good: "Before deploying, run `pnpm tsc --noEmit` to catch type errors."
```

**Scoped.** It says *when* it applies, not just *what* to do.
```
Bad:  "Always check the body parser."
Good: "Before implementing webhook handlers that verify signatures,
       check if the SDK requires the raw request body."
```

**Specific.** It names concrete things — commands, files, config values.
```
Bad:  "Check the package manager first."
Good: "Check for pnpm-lock.yaml, yarn.lock, or bun.lockb before
       running install commands."
```

**Self-contained.** It makes sense without reading the full learning.
During recall, the prevention rule is often the only part reported.

## When NOT to Capture

Apply the deletion test: "If I deleted this learning, would it change
how I approach a future task?"

**Don't store:** typo fixes, trivial errors with obvious causes, anything
re-readable from source code, temporary task state, things the user just
told you this session, generic best practices ("always validate input"),
single-occurrence trivial errors.

## Capture Budget

**Target: 2-5 learnings per significant task completion.** If more than
5, consolidate related learnings into a single comprehensive entry.

## Enriching Existing Learnings

When search-before-store finds a similar learning:

1. `sage_memory_search` with key terms + `filter_tags: ["self-learning"]`
2. If found: read its content, add new context, `sage_memory_update`
3. If not found: create new entry
4. If 3+ similar found: recurring pattern — consider scope promotion
