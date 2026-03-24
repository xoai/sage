# Examples

Complete end-to-end scenarios showing the self-learning lifecycle:
detect → capture → recall → prevent.

## Scenario 1: The Stripe Webhook Gotcha

### Session A — Discovery and Capture

The user asks: "Add a Stripe webhook handler for payment_intent.succeeded."

**Agent writes the handler:**
```javascript
app.post('/api/webhooks/stripe', express.json(), async (req, res) => {
  const sig = req.headers['stripe-signature'];
  const event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
  // ... handle event
});
```

**Error occurs:**
```
StripeSignatureVerificationError: No signatures found matching the expected signature for payload.
```

**Agent debugs:** The error suggests the signing secret is wrong. But the
secret is correct. After investigation, discovers that `express.json()`
middleware parses the body before Stripe can verify the raw signature.

**Detection trigger:** Gotcha — non-obvious behavior, misleading error
message, required investigation.

**Search before store:**
```
sage_memory_search: query="stripe webhook signature", filter_tags=["self-learning"]
→ No results
```

**Capture:**
```
sage_memory_store:
  title: "[LRN:gotcha] Stripe webhook requires raw body before JSON parsing"
  content: >
    What happened: Webhook signature verification failed with 400
    "No signatures found matching the expected signature."
    Why: Express body parser (express.json()) replaced the raw request
    body with parsed JSON before the Stripe SDK could verify the
    signature. Error message misleadingly suggests wrong signing secret.
    What's correct: Use express.raw({type: 'application/json'}) for
    the webhook route, placed before any JSON body parser.
    Prevention: Before implementing any webhook handler that verifies
    signatures (Stripe, GitHub, Twilio), check whether the verification
    SDK requires the raw request body. If yes, ensure body parsing
    middleware is skipped or deferred for that route.
  tags: ["self-learning", "gotcha", "stripe", "webhooks", "express"]
  scope: "project"
```

**Agent fixes the code** and the webhook works.

### Session B — Recall and Prevention

Two weeks later. The user asks: "Add a GitHub webhook handler for
push events."

**Agent recalls at task start:**
```
sage_memory_search: query="webhook handler", filter_tags=["self-learning"]
→ Found: [LRN:gotcha] Stripe webhook requires raw body before JSON parsing
```

**Agent reports the prevention rule:** "Before implementing this webhook
handler, I should verify whether GitHub's webhook verification requires
the raw request body. Checking... yes, GitHub's `@octokit/webhooks`
library also requires the raw body for signature verification."

**Agent writes correct code from the start:**
```javascript
app.post('/api/webhooks/github', express.raw({type: 'application/json'}), async (req, res) => {
  const signature = req.headers['x-hub-signature-256'];
  // verify with raw body...
});
```

**No error. No debugging. Learning prevented the repeat.**

---

## Scenario 2: The Package Manager Correction

### Session A — User Correction and Capture

The user asks: "Install the new analytics package."

**Agent runs:** `npm install analytics-sdk`

**User corrects:** "We use pnpm, not npm. The lock file is pnpm-lock.yaml."

**Detection trigger:** Correction — user explicitly corrected the agent.

**Search before store:**
```
sage_memory_search: query="pnpm npm package manager", filter_tags=["self-learning"]
→ No results
```

**Capture:**
```
sage_memory_store:
  title: "[LRN:correction] This project uses pnpm workspaces not npm"
  content: >
    What happened: Ran `npm install analytics-sdk`.
    Why wrong: Project uses pnpm workspaces. Lock file is
    pnpm-lock.yaml, not package-lock.json.
    What's correct: Use `pnpm add analytics-sdk` for this project.
    Prevention: Before running any package install command, check for
    pnpm-lock.yaml, yarn.lock, or bun.lockb in the project root.
    Only use npm if package-lock.json is present or no lock file exists.
  tags: ["self-learning", "correction", "pnpm", "package-manager"]
  scope: "project"
```

### Session B — Recall

New session, same project. User asks: "Add the stripe package."

**Agent recalls at task start:**
```
sage_memory_search: query="install package", filter_tags=["self-learning"]
→ Found: [LRN:correction] This project uses pnpm workspaces not npm
```

**Agent runs:** `pnpm add stripe` — correct from the start.

### Session C — Promotion to Global

The agent encounters the same pattern in a different project. Before
running `npm install`, it searches global learnings:

```
sage_memory_search: query="package manager detection", filter_tags=["self-learning"]
→ Found: [LRN:correction] This project uses pnpm workspaces not npm
```

The agent realizes this prevention rule (check for lock files before
assuming npm) applies to ANY project, not just the original one.

**Promote to global:**
```
sage_memory_store:
  title: "[LRN:correction] Check lock file before assuming package manager"
  content: >
    What happened: Used npm in a pnpm project.
    Why wrong: Different projects use different package managers, and
    the agent defaults to npm without checking.
    What's correct: Detect the package manager from the lock file.
    Prevention: Before running any package install command, check the
    project root for: pnpm-lock.yaml (→ pnpm), yarn.lock (→ yarn),
    bun.lockb (→ bun), package-lock.json (→ npm). If multiple exist,
    prefer the one matching the "packageManager" field in package.json.
  tags: ["self-learning", "correction", "package-manager", "pnpm", "yarn", "npm"]
  scope: "global"
```

Now every project benefits from this learning.

---

## Scenario 3: The API Drift Discovery

### Session A — Discovery

The user asks: "Add function calling to the OpenAI chat completion."

**Agent writes:**
```python
response = client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    functions=[{"name": "get_weather", "parameters": {...}}]
)
```

**Warning appears:**
```
DeprecationWarning: `functions` is deprecated. Use `tools` instead.
```

**Detection trigger:** API drift — library behavior differs from
training data.

**Capture:**
```
sage_memory_store:
  title: "[LRN:api-drift] OpenAI SDK v1.x: use tools param not functions"
  content: >
    What happened: Used `functions` parameter in chat.completions.create().
    Why wrong: `functions` is v0.x syntax. In v1.x+, the parameter is
    `tools` with type "function". Raises DeprecationWarning now, will
    break in v2.x.
    What's correct: Wrap each function def in
    {"type": "function", "function": {...}} and pass as `tools`.
    Prevention: Before using any LLM SDK for function/tool calling,
    check the installed SDK version and verify the current parameter
    name. Don't trust training data for rapidly evolving APIs —
    verify against `pip show <package>` or the SDK changelog.
  tags: ["self-learning", "api-drift", "openai", "tools", "functions"]
  scope: "global"
```

### Session B — Prevention in Another Project

Different project. User asks: "Integrate OpenAI with tool use."

**Agent recalls:**
```
sage_memory_search: query="openai function tool calling", filter_tags=["self-learning"]
→ Found: [LRN:api-drift] OpenAI SDK v1.x: use tools param not functions
```

**Agent checks the installed version first:** `pip show openai` → 1.52.0.

**Agent writes correct v1.x syntax from the start:**
```python
response = client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=[{"type": "function", "function": {"name": "get_weather", "parameters": {...}}}]
)
```

---

## Scenario 4: Review and Consolidation

After several weeks, the project has accumulated 25 learnings. The user
says: "sage review."

**Step 1 — Inventory:**
```
Learning Inventory (project: billing-service)
Total: 25 learnings (20 project, 5 global)

By type:  gotcha: 10  │  correction: 6  │  convention: 4
          error-fix: 3  │  api-drift: 2

By domain:  stripe (7)  │  database (5)  │  auth (4)
            docker (3)  │  testing (3)  │  other (3)
```

**Step 2 — Cluster:** "Stripe has 7 learnings — consolidation candidate."

**Step 3 — Stale check:** "2 learnings reference src/api/v1/ which was
migrated to src/api/v2/ three weeks ago."

**Step 4 — Consolidate:** The 7 Stripe learnings are merged into 2:
one for webhook integration (body parsing + signatures + idempotency)
and one for payment flow (retry logic + error codes + currency handling).
The 2 stale v1 API learnings are updated with v2 paths.

**Step 5 — Promote:** The Docker error-fix and OpenAI api-drift are
promoted to global scope.

**Step 6 — Report:**
```
Review Complete
  Reviewed: 25  →  Current: 19
  Stale updated: 2
  Consolidated: 7 Stripe → 2, 3 Auth → 1
  Promoted to global: 2
  Database health: clean
```

---

## Scenario 5: Ontology-Linked Learning

The ontology skill is active. A project has tasks tracked as entities.

**Task entity exists:**
```
[Task:task_a1b2] Fix payment timeout in checkout flow
```

**Agent works on the task and discovers a gotcha.** The N+1 query in
ReportBuilder causes the timeout.

**Capture with ontology link:**
```
sage_memory_store:
  title: "[LRN:gotcha] ReportBuilder N+1 query causes payment timeout"
  content: >
    What happened: /api/reports endpoint timed out at ~30s for users
    with >100 transactions.
    Why: ReportBuilder.aggregate() calls Transaction.load_details()
    per row instead of batch loading.
    What's correct: Use prefetch_related('details', 'categories')
    on the queryset in ReportQuerySet.for_user().
    Prevention: Before adding any new queryset in ReportBuilder,
    check if it loads related objects. If yes, use prefetch_related()
    or select_related() to batch-load. Test with >100 records to
    catch N+1 patterns early.
  tags: ["self-learning", "gotcha", "database", "performance",
         "n-plus-one", "edge:task_a1b2"]
  scope: "project"
```

The `edge:task_a1b2` tag links this learning to the ontology task. Now:

**Any future work on task_a1b2 automatically surfaces this learning:**
```
sage_memory_search: filter_tags=["self-learning", "edge:task_a1b2"]
→ Found: [LRN:gotcha] ReportBuilder N+1 query causes payment timeout
```

**During review, the ontology connection provides context:** "This
learning is linked to task 'Fix payment timeout' which is now status:done.
Is the learning still relevant, or was it resolved with the task?"
