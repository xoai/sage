# Anti-Pattern: Div Soup

**What agents do:** Build everything with `<div>` and `<span>`, adding `role`, `tabIndex`, and `onClick` to simulate buttons, links, and landmarks.

**Why agents do this:** `<div>` is the universal container in training data. Tutorials often style divs as buttons for CSS flexibility, and agents copy the pattern without understanding the semantic consequences.

**Why it's wrong:** Loses keyboard navigation, screen reader support, and browser built-in behavior. A `<div role="button" onClick>` needs manual keyboard handling (Enter + Space), focus management, and ARIA — a `<button>` gets all of it free. `<dialog>` gives focus trapping + Escape. `<a href>` gives middle-click to open in new tab. Do instead: semantic elements first, `<div>` only for layout containers.

---

# Anti-Pattern: Missing Alt Text

**What agents do:** Add `<img src="...">` without `alt`, or use `alt="image"`, `alt="screenshot.png"`, or `alt="photo"` — all meaningless to screen readers.

**Why agents do this:** Alt text requires understanding image content and context. Agents generate markup focused on visual output, not on what a screen reader user would need.

**Why it's wrong:** Screen readers announce filenames with no context. Do instead:
- Informative images: describe content — `alt="Bar chart showing Q3 revenue up 23%"`
- Functional images (icons in buttons): describe action — `alt="Close dialog"`
- Decorative images: empty alt — `alt=""` (screen reader skips entirely)

---

# Anti-Pattern: Layout Shift

**What agents do:** Render images, embeds, and dynamic content without reserving space. Load web fonts that reflow text. Insert banners/toasts above existing content. No `width`/`height` on images.

**Why agents do this:** In development with fast connections and cached assets, CLS is invisible. The agent doesn't experience the shift because assets load instantly in their environment.

**Why it's wrong:** CLS > 0.1 is a Core Web Vital failure and Google ranking signal. Users click the wrong element when content shifts. Do instead: `width`/`height` on all `<img>`/`<video>`. CSS `aspect-ratio` for responsive containers. `font-display: swap` + preload fonts. Reserve space for dynamic content with `min-height`. Never insert above visible content without user action.

---

# Anti-Pattern: Unprotected Forms

**What agents do:** Build forms with client-side validation only. No CSRF protection. No rate limiting. No honeypot or bot detection. Passwords accepted without minimum length requirements.

**Why agents do this:** Client validation makes the form "work" in the demo. Server-side security is invisible in the UI, so it never gets implemented.

**Why it's wrong:** Client validation is trivially bypassed with DevTools. Bots submit thousands of spam entries. CSRF exploits authenticated sessions. Do instead: CSRF token on every state-changing form. Server-side validation mirrors client-side. Rate limit submissions (especially login/registration). Honeypot field for public forms. Sanitize all input before storage and rendering.

---

# Anti-Pattern: Client-Only Critical Paths

**What agents do:** Build entire pages as client-rendered SPAs with an empty `<div id="root">`. Content, navigation, and primary actions require JavaScript to appear.

**Why agents do this:** SPAs are the default in React/Vue/Angular training data. `create-react-app` starts with a blank HTML page. Agents follow the framework default without considering progressive enhancement.

**Why it's wrong:** Search engines may not index client-only content (Google can execute JS but has limits; other crawlers can't). Slow first paint — download JS → parse → execute → fetch → render. JS failure = blank page. 53% of mobile users abandon sites taking > 3 seconds. Do instead: Server-render or statically generate initial HTML. Critical content visible in HTML source. Progressive enhancement: basic functionality without JS, JS adds interactivity.

---

# Anti-Pattern: No Security Headers

**What agents do:** Deploy web applications with zero security headers — no CSP, no HSTS, no X-Content-Type-Options. The default deployment has no defense-in-depth.

**Why agents do this:** Security headers aren't visible in the application. The app "works" without them. Headers require server/hosting configuration, not application code, so agents never add them.

**Why it's wrong:** Without CSP, any XSS vulnerability leads to full script execution — CSP is the safety net that limits the blast radius. Without HSTS, connections can be downgraded to HTTP. Without `nosniff`, browsers may execute uploaded files as scripts. OWASP lists these as baseline requirements. Do instead: Add all recommended headers in deployment config. Start with strict CSP in report-only mode, then enforce.
