# Consistent Error Envelope

**Why agents get this wrong:** Agents return different error shapes per endpoint — `{ error: "msg" }` here, `{ message: "msg" }` there, raw strings elsewhere. Ousterhout's "define errors out of existence": handle errors centrally so individual endpoints can't produce inconsistent formats.

**Do:** ONE error structure for the entire API, defined once in shared middleware:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Email address is invalid",
    "details": [
      { "field": "email", "reason": "Must be a valid email format" }
    ]
  }
}
```

Map exceptions to HTTP status codes centrally. Individual endpoints throw typed errors — the middleware formats them. Never craft error responses in route handlers.

---

# Validate All Input at the Boundary

**Why agents get this wrong:** Agents pass `req.body` directly to business logic or database queries. Invalid data causes cryptic errors deep in the stack, or worse, enables injection attacks.

**Do:** Validate EVERY request at the API boundary before any logic executes:
```ts
// WRONG — trusting client input
app.post('/users', async (req, res) => {
  await db.user.create({ data: req.body }); // No validation!
});

// RIGHT — schema validation first
const CreateUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(100),
  password: z.string().min(8),
});
app.post('/users', async (req, res) => {
  const data = CreateUserSchema.parse(req.body); // Throws 400 on invalid
  await db.user.create({ data });
});
```

Path params, query params, AND request bodies — all validated. Use Zod, Joi, Pydantic, or Marshmallow. The boundary is the security perimeter.

---

# Cursor-Based Pagination

**Why agents get this wrong:** Agents return all records unbounded, or use offset pagination (`?page=2&limit=20`) which breaks when records are inserted or deleted between page requests — users see duplicates or miss items. Geewax: use opaque page tokens.

**Do:** Every collection endpoint paginates with cursor tokens:
```ts
// Request
GET /products?maxPageSize=20&pageToken=eyJpZCI6MTAwfQ

// Response
{
  "data": [...],
  "nextPageToken": "eyJpZCI6MTIwfQ",  // Opaque — client doesn't parse this
  "hasMore": true
}
```

Default page size: 20. Maximum page size: 100 (prevent clients from requesting 10,000). Cursor tokens encode the position opaquely — clients pass them back verbatim. Cursor pagination is stable under concurrent writes. Offset is not.

---

# Batch Queries, Not N+1 Loops

**Why agents get this wrong:** Agents fetch a list, then loop making one query per item. This is the default agent pattern for "get related data."

```ts
// WRONG — N+1: 100 users = 101 queries
const users = await db.user.findMany();
const result = await Promise.all(
  users.map(async u => ({
    ...u,
    posts: await db.post.findMany({ where: { userId: u.id } })
  }))
);

// RIGHT — batch: 100 users = 2 queries
const users = await db.user.findMany();
const posts = await db.post.findMany({
  where: { userId: { in: users.map(u => u.id) } }
});
```

Kleppmann: this is the single most common performance killer in data-intensive applications. If you see `.map()` with a query inside, it's N+1. Use joins, eager loading (`include`/`prefetch_related`/`joinedload`), or batch-IN queries.

---

# Auth-First Middleware

**Why agents get this wrong:** Agents build all endpoints unprotected, then bolt auth on as a feature late in development. Some routes get middleware, others don't. Token verification duplicated in individual handlers.

**Do:** Auth middleware FIRST, globally. All routes protected by default:
```ts
// Apply globally
app.use(authMiddleware);

// Explicitly opt OUT for public routes
app.get('/health', skipAuth, healthHandler);
app.post('/auth/login', skipAuth, loginHandler);
app.get('/docs', skipAuth, docsHandler);
```

Use role-based middleware for authorization (`requireRole('admin')`). Auth is infrastructure, not a feature. Never duplicate token verification in individual handlers.

---

# RESTful URL Conventions

**Why agents get this wrong:** Agents mix styles in the same API: `/getUsers`, `/user/list`, `/api/v1/users`, `/products/create`. Amundsen: HTTP methods carry the verb — URLs are nouns.

**Do:**
```
GET    /users              → list users
POST   /users              → create user
GET    /users/:id          → get single user
PUT    /users/:id          → replace user
PATCH  /users/:id          → partial update
DELETE /users/:id          → delete user
GET    /users/:id/orders   → list user's orders
```

Plural nouns. HTTP methods for actions. Nested for relationships. No verbs in URLs. Version prefix if needed: `/v1/users`.

---

# Rate Limiting and Abuse Protection

**Why agents get this wrong:** Agents never add rate limiting. The API accepts unlimited requests from any source, with no body size limits or timeout handling.

**Do:** Rate limiting middleware from day one — even 100 req/min prevents abuse. Set request body size limits (1MB default, configurable for file uploads). Set response timeouts. Return `429 Too Many Requests` with `Retry-After` header. Per-user and per-IP limits. Stricter limits on auth endpoints (login, registration, password reset) to prevent credential stuffing.

---

# Idempotent Writes

**Why agents get this wrong:** Agents use POST for all creates and assume networks are reliable. Client retries a timed-out POST → duplicate record. Geewax: request deduplication. Amundsen: "How can you know whether it is safe to re-send if the client never gets a response?" Kleppmann: network failures are normal, not exceptional.

**Do:** Design every write to be safely retryable:
```ts
// Option 1: PUT with client-generated ID (idempotent by definition)
PUT /orders/ord_a1b2c3 { ... }  // Same ID twice = same result

// Option 2: POST with Idempotency-Key header
POST /orders
Idempotency-Key: unique-client-key-123
{ ... }
// Server: if key seen before, return the stored response
```

PUT and PATCH are naturally idempotent. DELETE is naturally idempotent. Only POST needs special handling — use idempotency keys. Store the key → response mapping for 24 hours.

---

# Separate Representation from Storage

**Why agents get this wrong:** Agents return raw database objects as API responses: `res.json(user)` where `user` contains `_id`, `__v`, `password_hash`, `created_at`, internal timestamps, and every column. Ousterhout: "different layer, different abstraction" — the API is a different layer from the database. "Information leakage" — exposing storage decisions through the API creates coupling.

**Do:** Define explicit response DTOs. Map DB models to API shapes:
```ts
// WRONG — leaking database internals
app.get('/users/:id', async (req, res) => {
  const user = await db.user.findUnique({ where: { id: req.params.id } });
  res.json(user); // Exposes password_hash, __v, internal fields
});

// RIGHT — explicit API representation
app.get('/users/:id', async (req, res) => {
  const user = await db.user.findUnique({ where: { id: req.params.id } });
  res.json({
    id: user.id,
    name: user.name,
    email: user.email,
    avatarUrl: user.avatarUrl,
    joinedAt: user.createdAt,
  });
});
```

This hides schema changes from clients, prevents leaking sensitive fields, and lets the API evolve independently from the database.

---

# API Versioning Strategy

**Why agents get this wrong:** Agents build v1 with no versioning plan. When breaking changes are needed, there's no path forward without breaking clients. Gough/Bryant: API lifecycle (planned → active → deprecated → retired). Geewax: versioning and compatibility.

**Do:** URL prefix versioning (`/v1/users`) — simplest and most common. Establish the compatibility contract from day one:
- **Safe (never breaking):** Adding new fields to responses, adding new endpoints, adding optional request parameters
- **Breaking (requires new version):** Removing or renaming response fields, changing field types, removing endpoints, making optional params required

When a break is needed: create `/v2/` endpoints, run both in parallel, deprecate v1 with a sunset date and `Deprecation` header. Never modify an existing endpoint's response shape without a version bump.

---

# Proper HTTP Status Codes

**Why agents get this wrong:** Agents return 200 for everything (including errors), use 500 for validation failures, or use 404 when they mean 400. The status code is the first thing clients check — getting it wrong breaks error handling.

**Do:**
```
200 OK              → successful GET, PUT, PATCH, DELETE
201 Created         → successful POST that created a resource
204 No Content      → successful DELETE with no response body
400 Bad Request     → invalid input (validation failure)
401 Unauthorized    → not authenticated (no token, expired token)
403 Forbidden       → authenticated but not authorized for this action
404 Not Found       → resource doesn't exist
409 Conflict        → state conflict (duplicate email, version mismatch)
422 Unprocessable   → valid syntax but semantically wrong
429 Too Many Reqs   → rate limited
500 Internal Error  → unhandled server error (never intentional)
```

401 means "who are you?" — 403 means "I know who you are, and you can't do this." Never return 200 with an error body. Never return 500 for client input errors.

---

# Structured Logging

**Why agents get this wrong:** Agents either add no logging (can't debug production) or scatter `console.log` everywhere with no structure, no request IDs, no correlation.

**Do:** Structured JSON logging from the start. Every log entry gets: timestamp, level, request ID, user ID (if authenticated), and context:
```ts
// WRONG
console.log('User created', userId);
console.log(error);

// RIGHT
logger.info('user.created', { userId, email, requestId: req.id });
logger.error('payment.failed', { orderId, error: err.message, requestId: req.id });
```

Use a logging library (Pino, Winston, structlog). Include request ID in every entry — trace a single request across all log lines. Log levels: ERROR (failures), WARN (degraded), INFO (business events), DEBUG (development only).

---

# Health and Readiness Endpoints

**Why agents get this wrong:** Agents never add health check endpoints. Load balancers, container orchestrators (K8s), and monitoring systems need a way to verify the service is alive and ready.

**Do:** Two endpoints, no authentication:
```ts
// Liveness — is the process running?
GET /health → 200 { "status": "ok" }

// Readiness — can the service handle requests?
GET /ready → 200 { "status": "ok", "db": "connected", "cache": "connected" }
         → 503 { "status": "degraded", "db": "connected", "cache": "timeout" }
```

Liveness checks should be trivial (return 200). Readiness checks verify all dependencies (database, cache, external services). K8s uses liveness to decide restart, readiness to decide routing — conflating them causes cascading failures.
