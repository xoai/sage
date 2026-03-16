# Pack Tests: web

**Framework version tested:** Universal (any web framework)
**Last tested:** 2026-03-13

---

## Test 1: Landing Page

**Prompt:**
```
Create a landing page with a hero image, features section, and contact form.
```

**Without pack:** `<div onClick>` for CTA buttons. Hero image with no alt, no dimensions, no priority loading. No security headers. No responsive design.

**With pack:** Semantic `<button>` for CTA. Hero image with `alt`, `width`/`height`, `loading="eager"`, `fetchpriority="high"`, WebP format. Security headers configured. Mobile-first responsive layout.

**Tests:** Patterns "Accessibility" + "Performance" + "Security Headers" + "Responsive"

---

## Test 2: Form with Validation

**Prompt:**
```
Build a registration form with email, password, and name fields.
```

**Without pack:** No `<label>` elements. Placeholder as only label. Client validation only. No CSRF. Error shown as alert(). No aria attributes.

**With pack:** Visible `<label htmlFor>` on every input. `aria-describedby` linking errors. `aria-required="true"`. Inline validation on blur. CSRF token. Server-side validation mirrors client. Focus first errored field on submit failure.

**Tests:** Patterns "Accessibility" + "Error UX" + Anti-pattern "Unprotected Forms"

---

## Test 3: Image Gallery

**Prompt:**
```
Create an image gallery that loads 50+ images.
```

**Without pack:** All images `loading="eager"`. No dimensions. No responsive srcset. Layout shifts as images load. No lazy loading.

**With pack:** First visible images eager + priority, rest `loading="lazy"`. All images have `width`/`height`. Responsive `srcset`. WebP/AVIF with fallback. CLS < 0.1.

**Tests:** Patterns "Performance" + Anti-pattern "Layout Shift"

---

## Test 4: SPA with Dynamic Content

**Prompt:**
```
Build a dashboard that fetches and displays data from an API.
```

**Without pack:** Empty `<div id="root">`, client-only rendering, no SSR. Loading is full-page spinner. Errors show "Something went wrong" with no recovery. Route changes silent to screen readers.

**With pack:** SSR/SSG for initial shell. Skeleton screens during data loading. Error messages with recovery actions. Route changes announced via `aria-live`. Optimistic UI for fast interactions.

**Tests:** Patterns "Loading States" + "Error UX" + "Accessibility" + Anti-pattern "Client-Only Critical Paths"

---

## Test 5: Production Readiness

**Prompt:**
```
Review this web app and make it production-ready.
```

**Without pack:** Adds minification. Maybe HTTPS. Misses security headers, a11y audit, CWV optimization, proper error handling.

**With pack:** Security headers audit (CSP, HSTS, nosniff, Referrer-Policy, Permissions-Policy). Accessibility audit (axe-core). CWV check (LCP, INP, CLS). Image optimization. Font loading strategy. Error boundaries with recovery. Structured data for SEO.

**Tests:** All patterns — comprehensive production review
