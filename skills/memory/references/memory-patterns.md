# Memory Patterns

Examples of good vs bad memory entries and integration patterns.

## Good Memory Examples

### Architecture Decision
```
Title: "Event sourcing rejected for billing — saga pattern chosen instead"
Content: "The team evaluated event sourcing vs saga pattern for multi-service
payment processing (Jan 2026). Event sourcing was rejected because: (1) the
audit trail requirement was met by saga compensation logs, (2) event sourcing
added replay complexity the team couldn't maintain, (3) existing PostgreSQL
infrastructure didn't support event store patterns well.
PaymentOrchestrator coordinates StripeGateway, LedgerService, and
NotificationService. Failures trigger compensating transactions defined in
saga_rollback_handlers.py."
Tags: ["billing", "architecture", "saga", "payments"]
```

Why this works: specific decision with rationale, names actual components,
explains what was rejected and why. Future queries for "billing architecture"
or "payment processing pattern" will find this.

### Convention
```
Title: "API handlers follow validate-process-respond pattern with Zod schemas"
Content: "Every API route handler in src/api/ follows the same structure:
(1) parse request with Zod schema from src/api/schemas/,
(2) call service layer function from src/services/,
(3) return standardized response envelope { data, error, meta }.
Validation errors return 422 with Zod error details. Service errors
return 500 with generic message (details logged, not exposed).
Exception: webhook handlers in src/api/webhooks/ skip Zod validation
because they validate via provider signatures (Stripe, GitHub)."
Tags: ["api", "conventions", "validation", "zod"]
```

Why this works: describes the pattern AND the exception. Uses actual paths
and technology names. A future task touching API routes will immediately
know the expected structure.

### Debugging Insight
```
Title: "504 timeouts on /api/reports caused by N+1 queries in ReportBuilder"
Content: "Reports endpoint was timing out at ~30s for users with >100
transactions. Root cause: ReportBuilder.aggregate() called
Transaction.load_details() per-row instead of batch loading. Fixed by
adding prefetch_related('details', 'categories') to the queryset in
ReportQuerySet.for_user(). Performance went from ~30s to ~200ms for
the worst case. Related: the ORM doesn't log slow queries by default —
added SLOW_QUERY_THRESHOLD=500ms to settings for future detection."
Tags: ["performance", "reports", "database", "debugging"]
```

Why this works: captures the symptom, root cause, fix, and a preventive
measure. Future performance issues in the reports module will benefit
from knowing this history.

### Domain Knowledge
```
Title: "Three distinct user segments with different JTBD from Q1 interviews"
Content: "User research (12 interviews, Jan 2026) identified three segments:
(1) Power users (~15%): batch-process invoices weekly, job is 'process all
pending invoices in under 30 minutes without errors.' Pain: manual
reconciliation after batch failures. (2) Casual users (~60%): check balance
and recent transactions 2-3x/week, job is 'confirm my finances are normal
without thinking.' Pain: notification overload obscuring important alerts.
(3) Admin users (~25%): configure rules and permissions, rarely transact
directly, job is 'set guardrails so my team can operate independently.'
Pain: no audit trail for permission changes."
Tags: ["user-research", "segments", "jtbd", "interviews"]
```

Why this works: specific data (12 interviews, percentages), actual jobs
in JTBD format, actionable pains. Any future product decision can reference
this grounding.

## Bad Memory Examples

### Too Vague
```
Title: "How the app works"
Content: "The app uses React and Node.js with a PostgreSQL database."
```
Why this fails: states obvious facts readable from package.json. No insight.
No domain vocabulary for search to match on.

### Too Granular
```
Title: "Fixed typo in header component"
Content: "Changed 'Welcom' to 'Welcome' in src/components/Header.tsx line 14."
```
Why this fails: trivial change that doesn't inform any future decision.
Git history already tracks this.

### No Rationale
```
Title: "Using JWT for auth"
Content: "The project uses JWT tokens for authentication."
```
Why this fails: states the WHAT without the WHY. Compare: "Chose JWT over
sessions because the microservices architecture requires stateless auth —
each service validates tokens independently without sharing session state.
Refresh tokens stored in httpOnly cookies, access tokens in memory only."

### Temporary State
```
Title: "Currently working on billing feature"
Content: "Started implementing the billing module today. Need to finish
the payment form and connect to Stripe."
```
Why this fails: this is task progress, not knowledge. It belongs in
`.sage/progress.md`, not in memory. It becomes stale the moment the task
completes.

## When NOT to Store

Ask: "If I deleted this memory, would it change how I approach a future task?"

- **No** → don't store it
- **Yes** → store it

Concrete test cases where the answer is NO:
- File exports and function signatures (re-readable)
- Package versions (check package.json)
- Current task status (use .sage/progress.md)
- Things the user explicitly told you this session (they know)
- Generic best practices not specific to this project
