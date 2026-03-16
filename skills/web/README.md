# web

**Layer 1 — Domain Foundation (v2.0)**

Universal web development principles that apply to every web project regardless
of framework. React, Vue, Svelte, vanilla JS — these principles hold.

## Philosophy

This pack encodes the foundational web platform knowledge that agents frequently
get right in isolation but miss in practice. An agent knows what ARIA labels are.
It still produces a form with no error announcements for screen readers. An agent
knows about Core Web Vitals. It still renders a 2MB hero image without dimensions.

The gap isn't knowledge — it's consistent application.

## What's Included

| Type | Count | Coverage |
|------|-------|----------|
| Patterns | 7 | Accessibility (WCAG 2.2), performance (Core Web Vitals), security headers (OWASP), SEO, responsive design, error UX, loading states |
| Anti-patterns | 6 | Div soup, missing alt text, layout shift, unprotected forms, client-only critical paths, no security headers |
| Constitution | 7 | principles |

Grounded in: W3C WCAG 2.2 (October 2023), Google Core Web Vitals (2025),
OWASP Secure Headers Project, OWASP CSP Cheat Sheet, MDN Web Docs,
Web Almanac 2025, European Accessibility Act (June 2025).

## What This Pack Does NOT Cover

- Framework-specific patterns (see `react`, `nextjs`, etc.)
- CSS methodology opinions (BEM vs utility-first vs CSS-in-JS)
- Build tool configuration (Webpack, Vite, Turbopack)
- Backend/API patterns (see `api` or `baas`)
