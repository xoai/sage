---
name: "api"
description: "Corrects the 13 most common API design mistakes agents make — grounded in Geewax, Amundsen, Ousterhout, Kleppmann, and Gough/Bryant"
version: "2.0.0"
type: knowledge
layer: domain
requires:
  sage: ">=1.0.0"
activates-when:
  detected: [express, fastify, koa, hono, django, flask, rails, spring, gin, echo, actix-web, axum]
tags: [express,fastify,koa,hono,django]
---

# api

**Layer 1 — Domain Foundation (v2.0)**

Corrects the 13 most common API design mistakes agents make, grounded in
5 authoritative sources:

- **Geewax** (API Design Patterns) — cursor pagination, error structure, idempotency, request deduplication
- **Amundsen** (RESTful Web API Cookbook) — PUT for idempotent creates, HTTP method semantics
- **Ousterhout** (Philosophy of Software Design) — information hiding, define errors out of existence, different layer/different abstraction
- **Kleppmann** (Designing Data-Intensive Applications) — network failures are normal, batch processing, data integrity
- **Gough/Bryant** (Mastering API Architecture) — schema validation, API lifecycle, backward compatibility, deprecation

## What's Included

| Type | Count | Coverage |
|------|-------|----------|
| Patterns | 13 | Error envelope, input validation, cursor pagination, batch queries, auth-first, URL conventions, rate limiting, idempotent writes, separate representation, versioning, HTTP status codes, structured logging, health endpoints |
| Anti-patterns | 9 | Inconsistent errors, trusting input, returning all records, N+1 loops, bolt-on auth, non-idempotent creates, leaking DB internals, 200-with-error-body, no versioning plan |
| Constitution | 11 | principles |

Every pattern includes code examples showing wrong vs right approaches.
Every anti-pattern includes root cause explaining WHY agents default to the wrong behavior.
