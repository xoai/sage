# Pack Tests: @sage/api

**Framework version tested:** Universal (Express, Fastify, Django, etc.)
**Last tested:** 2026-03-13

---

## Test 1: Basic CRUD API

**Prompt:**
```
Create a REST API for a blog with posts and comments endpoints.
```

**Without pack:** Returns all posts unbounded, inconsistent error formats, N+1 query for comments, no input validation, `res.json(post)` leaking all DB fields.

**With pack:** Cursor-based pagination on GET /posts, consistent error envelope via middleware, batch query for comments, Zod/Joi schema validation on POST body, explicit response DTO excluding internal fields.

**Tests:** Patterns "Cursor Pagination" + "Error Envelope" + "Batch Queries" + "Input Validation" + "Separate Representation"

---

## Test 2: Adding authentication

**Prompt:**
```
Add user authentication to this API with JWT tokens.
```

**Without pack:** Auth middleware applied per-route inconsistently. Some routes missed. Token verification duplicated in handlers.

**With pack:** Global auth middleware first, all routes protected by default, public routes (/health, /auth/login) explicitly opted out. Centralized token verification.

**Tests:** Pattern "Auth-First Middleware" + Anti-pattern "Bolt-On Authentication"

---

## Test 3: User registration endpoint

**Prompt:**
```
Create a POST endpoint for user registration with email, password, and name.
```

**Without pack:** Passes req.body directly to DB. No validation. Returns raw user object including password_hash. No idempotency. Returns 200 for everything.

**With pack:** Schema validation first (Zod). Returns explicit DTO (no sensitive fields). Accepts Idempotency-Key header. Returns 201 Created. Errors return 400 with envelope.

**Tests:** Patterns "Input Validation" + "Separate Representation" + "Idempotent Writes" + "HTTP Status Codes"

---

## Test 4: Performance issue on product list

**Prompt:**
```
The product list endpoint is slow — products have categories and reviews.
```

**Without pack:** Suggests Redis cache. Doesn't identify N+1. Doesn't add pagination.

**With pack:** Identifies N+1 (products→categories loop, products→reviews loop), rewrites with batch/join, adds cursor pagination if missing.

**Tests:** Pattern "Batch Queries" + Anti-pattern "N+1 Query Loops" + Pattern "Cursor Pagination"

---

## Test 5: Make API production-ready

**Prompt:**
```
Review this API and make it production-ready.
```

**Without pack:** Adds helmet/cors. Maybe a generic error handler. Misses pagination, validation, rate limiting, structured logging, health endpoints, versioning.

**With pack:** Adds rate limiting middleware, structured logging with request IDs, /health and /ready endpoints, validates all inputs, ensures cursor pagination on collections, adds /v1/ prefix, verifies error envelope consistency.

**Tests:** Patterns "Rate Limiting" + "Structured Logging" + "Health Endpoints" + "API Versioning" + "Input Validation"
