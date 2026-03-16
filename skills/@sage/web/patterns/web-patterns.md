# Semantic HTML and Accessibility

**Why agents get this wrong:** Agents build everything with `<div>` and `onClick`. WCAG 2.2 (W3C, current standard; EAA legally enforceable in EU since June 2025) requires semantic elements — they provide keyboard handling, screen reader support, and focus management that `<div>` can never replicate without reimplementing the browser.

```html
<!-- WRONG — must reimplement keyboard, focus, ARIA from scratch -->
<div class="btn" onClick={handleClick} role="button" tabIndex={0}>Save</div>

<!-- RIGHT — keyboard, focus, screen reader all built-in -->
<button onClick={handleClick}>Save</button>
```

**Semantic elements:** `<button>` for actions, `<a href>` for navigation, `<nav>/<main>/<aside>/<header>/<footer>` for landmarks, `<dialog>` for modals (gets focus trapping + Escape for free), `<details>/<summary>` for disclosure widgets.

**Forms:** Every `<input>` needs a visible `<label htmlFor>`. Error messages use `aria-describedby` linked to the input. Required fields use `aria-required="true"`. Form-level errors announced via `aria-live="polite"` region. Never use placeholder as the only label.

**Dynamic content:** Toasts use `role="status"` + `aria-live="polite"`. Errors use `role="alert"`. Loading containers get `aria-busy="true"`. SPA route changes must announce the new page title to screen readers.

**Color and contrast:** Text 4.5:1 minimum (3:1 for large text 18px+). Never convey information by color alone — add icons, patterns, or text. Red/green status without an icon is invisible to colorblind users. Test with forced-colors mode.

**WCAG 2.2 additions:** Minimum 24×24px touch/click targets (SC 2.5.8). Focus must not be fully obscured by sticky headers/footers (SC 2.4.11). No cognitive function test for authentication — support paste, autofill, passkeys (SC 3.3.7).

**Testing:** Run axe-core or Lighthouse accessibility audit. Fix all critical and serious violations before feature is complete.

---

# Performance (Core Web Vitals)

**Why agents get this wrong:** Agents load everything eagerly and ignore layout stability. Google's Core Web Vitals are ranking signals — only 48% of mobile pages pass all three thresholds (Web Almanac 2025). A 1-second LCP improvement can increase conversions 8-14%.

**Targets (Google, measured at 75th percentile of real users):** LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1.

**Images (the #1 cause of slow LCP and CLS):**
```html
<!-- WRONG — no dimensions, no lazy, no priority, no modern format -->
<img src="hero.jpg" />

<!-- RIGHT — LCP image: eager + priority + dimensions + modern format -->
<img src="hero.webp" alt="..." width="1200" height="630"
     loading="eager" fetchpriority="high" />

<!-- RIGHT — below-fold image: lazy + dimensions -->
<img src="card.webp" alt="..." width="400" height="300" loading="lazy" />
```
Always set `width`/`height` (browser reserves space, prevents CLS). Use WebP/AVIF with fallback. Responsive `srcset` for viewport sizes. Never serve 4000px in a 400px container.

**JavaScript:** Defer non-critical scripts (`<script defer>` or dynamic import). Code-split by route — never ship a monolithic bundle. Avoid blocking main thread > 50ms (kills INP). Prefer CSS animations over JS (GPU-composited).

**Fonts:** `font-display: swap` to prevent invisible text. Preload critical fonts: `<link rel="preload" as="font" crossorigin>`. Subset to characters used. Max 2 font families.

**Third-party scripts:** Load analytics asynchronously, never in the critical path. Use `rel="preconnect"` for known third-party origins. Audit third-party impact quarterly — scripts accumulate silently and degrade performance without anyone noticing.

---

# Security Headers

**Why agents get this wrong:** Agents never add security headers unless explicitly asked. OWASP recommends these as baseline defense-in-depth — CSP alone prevents the majority of XSS exploits even when application code has vulnerabilities.

**Required headers (OWASP Secure Headers Project):**
- **Content-Security-Policy:** Start strict. OWASP current best practice is "Strict CSP" with nonces, not allowlists: `script-src 'nonce-{random}' 'strict-dynamic'`. Never `'unsafe-eval'` in production. Fallback: `default-src 'self'; script-src 'self'`
- **Strict-Transport-Security:** `max-age=31536000; includeSubDomains` — forces HTTPS for one year. Only set after confirming HTTPS works on all subdomains
- **X-Content-Type-Options:** `nosniff` — prevents MIME-sniffing attacks
- **Referrer-Policy:** `strict-origin-when-cross-origin` — protects internal URL structures from leaking
- **Permissions-Policy:** Disable unused browser APIs: `camera=(), microphone=(), geolocation=(), payment=()`
- **X-Frame-Options** is obsoleted by CSP `frame-ancestors` — use `frame-ancestors 'self'` instead

**Cookies:** `Secure` on all cookies. `HttpOnly` on session/auth cookies. `SameSite=Lax` minimum, `Strict` for sensitive actions (banking, account changes).

**CORS:** Never `Access-Control-Allow-Origin: *` on authenticated endpoints. Whitelist specific origins — don't reflect the Origin header blindly.

---

# SEO and Discoverability

**Why agents get this wrong:** Agents generate pages without metadata, with no heading hierarchy, and with content invisible to crawlers behind client-only JavaScript.

**Every page gets:** unique `<title>` (50-60 chars, primary keyword near start), `<meta name="description">` (150-160 chars, compelling and unique), `<link rel="canonical">` to prevent duplicates, Open Graph tags (`og:title`, `og:description`, `og:image`) for social sharing.

**Semantic structure:** One `<h1>` per page — the primary topic. Heading hierarchy h1→h2→h3 (no skipping levels). `<article>` for self-contained content, `<nav>` for navigation, `<aside>` for supplementary. Internal links use descriptive anchor text — never "click here."

**Technical:** Server-render or statically generate critical content — client-only JS is invisible to most crawlers. Every page reachable within 3 clicks from homepage. XML sitemap generated, submitted, and updated on changes. Structured data (JSON-LD) for articles, products, FAQs, breadcrumbs. `robots.txt` allows public content, blocks admin/API routes. Mobile-first: responsive design is required — Google uses mobile-first indexing.

---

# Responsive Design

**Why agents get this wrong:** Agents hardcode pixel widths matching one screen size. Real users have 320px phones and 2560px monitors. Mobile is the majority of web traffic.

**Mobile-first:** Base styles for mobile, `min-width` media queries add complexity for larger screens:
```css
/* Base: mobile */                → single column, stacked
/* @media (min-width: 768px) */   → tablet adjustments
/* @media (min-width: 1024px) */  → desktop layout
```

**Layout:** CSS Grid for page-level (header/sidebar/main/footer), Flexbox for component-level (navbars, cards). Never fixed pixel widths on containers — `max-width` + auto margins. Set `box-sizing: border-box` globally.

**Touch targets:** Minimum 24×24px (WCAG 2.2 SC 2.5.8), recommended 44×44px (Apple HIG). Adequate spacing between adjacent targets. Dropdowns must be touch-friendly — not hover-dependent.

**Content decisions per breakpoint:** Responsive is not just CSS. Decide what to show/hide (CSS, not JS for visibility). Most important content first in source order. Progressive disclosure on mobile. Hamburger menu on mobile, full nav on desktop.

**Testing:** 375px (iPhone SE), 390px (iPhone 14), 412px (Android), 768px (iPad), 1024px+. Both orientations on tablets. 200% browser zoom (WCAG requirement).

---

# Error UX

**Why agents get this wrong:** Agents show raw error objects or generic "Something went wrong" with no recovery path. Users are left stuck with no way forward.

**Every error answers three questions:**
1. **What happened?** — clear, non-technical description
2. **Why?** — brief context if cause isn't obvious
3. **What now?** — specific recovery action

```
Bad:  "Error 422: Unprocessable Entity"
Good: "Your email address doesn't look right. Check for typos and try again."
```

**Forms:** Validate inline on blur, not just on submit. Show errors next to the field, not just at the top. Don't clear the form on error — preserve what the user entered. Focus the first errored field on submit failure. Connect errors to inputs with `aria-describedby` for screen readers.

**Network:** Distinguish "no connection" from "server error" — different recovery actions. Retry button for transient failures (timeouts, 5xx). Show last successful state during temporary failures, not a blank page. Queue offline actions and sync on reconnect where feasible.

**404:** Custom page with navigation — never raw server error. Suggest related content or search. Link to homepage.

**Catastrophic:** Global error boundaries with recovery UI. Always provide "reload" or "go home" — never a dead end. Log errors server-side, never expose stack traces to users.

---

# Loading States

**Why agents get this wrong:** Agents either show nothing during loading (blank screen) or a single full-page spinner for everything. Users think the app is broken.

**By duration:**
- **Instant (<100ms):** Optimistic UI — show expected result immediately, rollback on failure
- **Fast (100ms-1s):** Inline spinner (inside the button, not blocking the page) or progress bar
- **Slow (1-10s):** Skeleton screens matching the layout shape. Better than spinners — they communicate what's coming and prevent CLS
- **Very slow (10s+):** Progress with steps. "Analyzing 3 of 7 datasets." Visible milestones

**Never:** Full-page spinners blocking all interaction. Loaders that don't match final layout (causes CLS). Flickering (add 300ms minimum display time to prevent flash). Infinite loading without timeout — always show an escape after a reasonable period.
