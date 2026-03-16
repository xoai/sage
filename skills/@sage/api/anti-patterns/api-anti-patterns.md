# Anti-Pattern: Inconsistent Error Shapes

**What agents do:** Return `{ error: "not found" }` from one endpoint, `{ message: "Not found" }` from another, raw string from a third, and just a status code with empty body from a fourth.

**Why agents do this:** Each endpoint is written independently. Without a shared error middleware, each handler crafts its own error response.

**Why it's wrong:** Clients can't reliably parse errors — every endpoint needs different handling. Do instead: ONE error envelope defined once in shared middleware, used everywhere.

---

# Anti-Pattern: Trust the Client Input

**What agents do:** Pass `req.body` directly to database: `db.create(req.body)`. Accept query params without type checking: `db.findMany({ skip: req.query.page })`.

**Why agents do this:** The happy path works in testing. The agent focuses on making the feature work, not on what happens with malicious or malformed input.

**Why it's wrong:** Missing fields cause null reference errors deep in the stack. Wrong types cause cryptic crashes. Extra fields enable mass-assignment attacks. No validation means no error messages — users get 500 instead of "email is required." Do instead: Schema validation (Zod, Joi, Pydantic) at the boundary. Reject before processing.

---

# Anti-Pattern: Return All Records

**What agents do:** `GET /products` queries the database with no limit and returns every record. No pagination params, no cursor, no total count.

**Why agents do this:** Works perfectly with 10 seed records in development. The agent doesn't think about production data volumes.

**Why it's wrong:** 100K products → multi-second response, memory exhaustion, possible timeout. Do instead: Cursor-based pagination on every collection endpoint. Default 20 items, max 100.

---

# Anti-Pattern: N+1 Query Loops

**What agents do:** Fetch a list, then query per item in a loop. The universal agent pattern for "get related data."

**Why agents do this:** It's the obvious imperative approach — "for each user, get their posts." Agents write code that reads naturally without considering query count.

**Why it's wrong:** 100 users = 101 database round-trips. Linear query growth kills performance under load and exhausts connection pools. Do instead: Batch-IN query (`userId IN (...)`) or ORM eager loading (`include`, `prefetch_related`).

---

# Anti-Pattern: Bolt-On Authentication

**What agents do:** Build all endpoints unprotected, then add auth middleware to individual routes later. Some routes get it, others don't. JWT verification logic duplicated across handlers.

**Why agents do this:** Auth feels like a feature to add, not infrastructure to start with. The agent builds the "core" functionality first and treats auth as a later concern.

**Why it's wrong:** Inconsistent security coverage — one missed route is a vulnerability. Duplicated verification logic means inconsistent token handling. Do instead: Auth middleware globally by default. Explicitly opt OUT for public routes.

---

# Anti-Pattern: Non-Idempotent Creates

**What agents do:** Use POST for all resource creation with no deduplication. Client retries a timed-out request → duplicate record.

**Why agents do this:** POST for create is the CRUD default taught everywhere. Agents follow the pattern without considering network unreliability.

**Why it's wrong:** Network failures are normal (Kleppmann). A mobile client in a tunnel retries a payment POST — two charges created. Do instead: PUT with client-generated ID (naturally idempotent), or POST with Idempotency-Key header (server stores key → response mapping).

---

# Anti-Pattern: Leaking Database Internals

**What agents do:** `res.json(user)` returning the raw ORM object — `_id`, `__v`, `password_hash`, `createdAt`, `updatedAt`, internal flags, every column.

**Why agents do this:** It's the shortest code path. The ORM returns an object, `res.json()` serializes it. Why write extra mapping code?

**Why it's wrong:** Exposes sensitive fields (password hashes, internal IDs). Couples clients to database schema — any migration breaks the API. Ousterhout: information leakage between layers. Do instead: Explicit response DTOs mapping only the fields clients need.

---

# Anti-Pattern: 200 OK with Error Body

**What agents do:** Return HTTP 200 for everything, including errors. The error is in the response body: `{ "success": false, "error": "User not found" }`.

**Why agents do this:** Simpler client code in the agent's mental model — always check `response.success` instead of status codes.

**Why it's wrong:** Breaks HTTP semantics. Caches store error responses as valid. Monitoring tools report 100% success rate while the API is failing. Middleware (retry, circuit breaker) can't distinguish success from failure. Do instead: Proper status codes (400 for bad input, 404 for not found, 500 for server error). Reserve 200 for actual success.

---

# Anti-Pattern: No Versioning Plan

**What agents do:** Build the API with no version prefix and no strategy for breaking changes. When a field needs renaming, existing clients break immediately.

**Why agents do this:** Versioning feels like premature complexity for a v1 API. "We'll add it when we need it."

**Why it's wrong:** Once clients depend on a response shape, changing it is breaking. Adding versioning retroactively requires all clients to update their base URL simultaneously. Do instead: Start with `/v1/` prefix. Adding fields is safe. Removing/renaming requires a new version with parallel operation and deprecation timeline.
