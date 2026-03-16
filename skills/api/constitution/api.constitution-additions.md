# API — Constitution Additions

## Principles

1. Every API endpoint MUST validate all input (path params, query params, request body) at the boundary using a schema library before any business logic executes. Invalid requests MUST be rejected with 400 and a descriptive error envelope.
2. Every error response MUST use the project's standard error envelope format containing code, message, and details. No endpoint may return a non-standard error shape.
3. Every collection endpoint MUST paginate using cursor-based pagination with opaque page tokens. Returning unbounded result sets is forbidden. Default page size MUST be ≤100.
4. Database queries that fetch related data MUST use joins, eager loading, or batch queries. N+1 query loops (query-per-item in a map/loop) are forbidden.
5. Authentication middleware MUST be applied globally by default. Public endpoints MUST be explicitly opted out. Authorization checks MUST verify not just authentication but specific permissions for the requested action.
6. All write operations MUST be idempotent or support idempotency keys. Non-idempotent creates that can produce duplicates on retry are forbidden.
7. API responses MUST use explicit response shapes (DTOs/serializers). Returning raw database/ORM objects directly is forbidden. Sensitive fields (password hashes, internal IDs, system timestamps) MUST NOT appear in API responses.
8. HTTP status codes MUST accurately reflect the result. 200 for success, 201 for creation, 400 for bad input, 401 for unauthenticated, 403 for unauthorized, 404 for not found, 429 for rate limited, 500 for unhandled errors. Returning 200 with an error body is forbidden.
9. All APIs MUST use structured JSON logging with request IDs for correlation. Console.log is forbidden in production code.
10. All APIs MUST include unauthenticated `/health` and `/ready` endpoints for operational monitoring. Health checks MUST NOT conflate liveness with readiness.
11. All APIs MUST be deployed with a URL version prefix (`/v1/`). Adding response fields is safe. Removing or renaming fields MUST trigger a new version with deprecation timeline for the old version.
