# Web — Constitution Additions

These principles are enforced by Gate 02 (constitution compliance) on every implementation.

## Principles

1. All interactive elements MUST be keyboard-accessible using semantic HTML elements (`<button>`, `<a>`, `<dialog>`, `<select>`). No mouse-only interactions. Using `<div>` with `onClick` where a semantic element exists is forbidden.
2. All images MUST have meaningful `alt` text (or empty `alt=""` for decorative images). No exceptions. All forms MUST have visible labels, validation feedback, and error messages announced to screen readers via `aria-describedby`.
3. All touch/click targets MUST meet WCAG 2.2 minimum of 24×24px, with 44×44px recommended. Focus indicators MUST NOT be fully obscured by sticky headers or other author-created content.
4. All pages MUST set security headers: Content-Security-Policy (strict, nonce-based preferred), Strict-Transport-Security, X-Content-Type-Options: nosniff, Referrer-Policy, and Permissions-Policy at minimum. Deploying without security headers is forbidden.
5. Core Web Vitals MUST be monitored: LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1. All images and media MUST have explicit `width`/`height` attributes. Layout shift above 0.1 after content becomes visible is forbidden.
6. No user-visible content may depend entirely on client-side JavaScript for first render. Critical paths MUST work with progressive enhancement — server-render or statically generate initial HTML for SEO and performance.
7. Every error state MUST provide a recovery path (retry, navigate away, or contact support). Dead-end error screens with no user action available are forbidden. Error messages MUST NOT expose stack traces, internal paths, or database details.
