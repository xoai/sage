# Anti-Pattern: Auth Check Per Screen

**What agents do:** `if (!user) redirect('/login')` at the top of every screen, duplicated across 20+ files.

**Why agents do this:** It's the obvious "safe" approach — each screen protects itself. Agents don't realize Expo Router's layout hierarchy can handle this centrally.

**Why it's wrong:** Duplication is fragile — one missed screen exposes unauthenticated access. It also causes a flash of the protected screen before redirect (component renders one frame, then navigates away). Do instead: Single auth guard in root `_layout.tsx`. Individual screens never check auth.

---

# Anti-Pattern: Store Hydration Race Condition

**What agents do:** Render the app immediately without waiting for Zustand stores to hydrate from MMKV.

**Why agents do this:** In web React, state initializes synchronously from defaults. Agents apply the same assumption to mobile persistent stores, which load asynchronously.

**Why it's wrong:** Flash of wrong state (light theme → dark theme). Navigation bugs — auth store default is "logged out," app redirects to login, then store hydrates with "logged in" and redirects back. Do instead: Show splash until `store.persist.hasHydrated()` returns true for all persisted stores.

---

# Anti-Pattern: Server Data in Zustand

**What agents do:** Fetch API data in an effect, store in Zustand, manually manage loading/error/stale/refresh.

**Why agents do this:** Zustand looks like a universal state container. Agents treat all state the same — UI toggles and API data go in the same store.

**Why it's wrong:** You're reimplementing caching, retry, background refresh, deduplication, and optimistic updates that TanStack Query provides. Do instead: TanStack Query for ALL server data. Zustand ONLY for client UI state (filters, sort order, theme).
