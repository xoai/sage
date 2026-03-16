# Composition Over Monoliths

**Why agents get this wrong:** Agents generate one massive component per feature — 300+ lines with UI, state, data fetching, and formatting mixed together. This is untestable and unreusable.

**Do:** Split into container (data) and presentation (UI) components. Each component does one thing. Prefer composition over configuration:

```tsx
// WRONG — configuration nightmare
<Card showHeader showFooter showImage variant="featured" size="large" />

// RIGHT — composable
<Card>
  <Card.Image src={img} />
  <Card.Body>{content}</Card.Body>
  <Card.Footer>{actions}</Card.Footer>
</Card>
```

If a component exceeds ~150 lines, extract sub-components. If it has more than 5-6 props, use composition or context.

**Children and slots:** Use `children` as the primary composition mechanism. For multiple slots, use named props:
```tsx
<PageLayout
  sidebar={<Sidebar />}
  header={<Header />}
>
  {/* main content as children */}
</PageLayout>
```

**Custom hooks for logic reuse:** Extract shared stateful logic into custom hooks, not HOCs or render props. `useDebounce`, `useLocalStorage`, `useMediaQuery` — reusable behavior. Name them starting with `use` — this is a rule, not a convention.

**Co-location:** Keep related files together — component, styles, tests, types in the same directory. Shared utilities in `lib/` or `utils/`. Avoid a flat `components/` folder with 50+ files — use feature-based grouping.

---

# Hooks Discipline

**Why agents get this wrong:** Agents use `useEffect` as a catch-all for any logic that "needs to happen." Most useEffect calls should be something else entirely.

**useEffect is ONLY for synchronizing with external systems:**
- Subscriptions (ResizeObserver, WebSocket, event listeners)
- Third-party library integration
- Timers/intervals

**NOT useEffect — do this instead:**
- Computing derived values → calculate during render or `useMemo`
- Responding to prop changes → adjust in the render function
- Resetting state when props change → use a `key` to remount
- Sending analytics on events → call in the event handler
- Transforming data for display → compute inline

Always include cleanup. Always complete the dependency array — if adding a dependency causes unwanted re-runs, restructure the code, don't suppress the linter. In React 19.2+, use `useEffectEvent` to separate event logic from synchronization logic.

**useState discipline:**
- Initialize with the simplest possible value. Lazy initialization (`useState(() => expensive())`) only when initial value is expensive.
- Don't mirror props in state. If a value comes from props, use it directly.
- Group related state with `useReducer` when you have 4+ related `useState` calls that update together.

**useRef — not a state substitute:**
- For DOM references: measurements, focus, scroll position
- For mutable values that don't trigger re-render: previous values, timer IDs, interval references
- Never use `useRef` as a state substitute — changes to `ref.current` don't cause re-render, so the UI won't update

---

# State Management

**Why agents get this wrong:** Agents put everything in `useState` — including values derivable from other state, server data, and URL params. This creates synchronization bugs and unnecessary complexity.

**State location decision tree:**
1. Can it be computed from other state/props? → Don't store it. Derive it.
2. Used by one component only? → Local `useState`
3. Shared by parent + few children? → Lift state to common parent
4. Shared across a subtree? → React Context (split by concern: `ThemeContext`, `AuthContext` — never a single `AppContext`)
5. Global + complex + needs middleware? → Zustand, Jotai, or Redux Toolkit
6. Data from an API? → TanStack Query or SWR — NOT component state

**Critical distinction:** Server state (cached, stale, needs revalidation) and client state (ephemeral UI: modal open, selected tab) are different things. Manage them separately. Mixing them (useEffect + useState for API data) is the #1 data management bug source.

**Context pitfalls:** Context triggers re-render of ALL consumers when the value changes. Wrap provider values in `useMemo` to prevent unnecessary re-renders. Place providers as low as possible in the tree — not everything needs to be at the root.

**Form state:** Simple forms (< 5 fields): controlled components with `useState`. Complex forms: React Hook Form or similar. Never build your own form library — validation, dirty tracking, and error management are deceptively complex.

---

# Error Boundaries

**Why agents get this wrong:** Agents never add error boundaries. One thrown error in any component crashes the entire app with a white screen.

**Placement strategy:**
1. **Route level** — each page gets its own boundary. Settings crash shouldn't blank the dashboard.
2. **Feature level** — independent features (chat widget, notifications) fail independently.
3. **Data-dependent sections** — components rendering API data show fallback on malformed response.

Never a single boundary at the root — one bad component takes down everything.

**Fallback UI must provide recovery:** "Something went wrong" + "Try again" button + navigation so users aren't trapped. Log errors to monitoring. Show last good state when possible.

**Error boundaries do NOT catch:** event handler errors (use try/catch), async errors (promises, setTimeout), or SSR errors. Handle those with try/catch + error state.

---

# Forms

**Why agents get this wrong:** Agents build forms with scattered useState per field, manual validation logic, and no submission handling discipline.

**Do:** Use a form library (React Hook Form, Formik) or Server Actions. Validate with a schema (Zod, Yup) — never hand-roll validation for more than 3 fields. Show errors inline next to the field. Disable submit during submission. Handle optimistic updates for better UX.

For simple forms (< 5 fields): controlled components with useState is fine.
For complex forms: React Hook Form. Never build your own form library.

---

# Testing

**Why agents get this wrong:** Agents test implementation details — checking that useState was called, asserting on internal component state, or testing className values.

**Do:** Test behavior from the user's perspective: render → interact → assert visible output. Use Testing Library. Query by role, label, and text — never by test ID unless no semantic alternative exists.

```tsx
// WRONG — testing implementation
expect(component.state.isOpen).toBe(true);

// RIGHT — testing behavior
await user.click(screen.getByRole('button', { name: 'Open menu' }));
expect(screen.getByRole('navigation')).toBeVisible();
```

---

# Data Fetching

**Why agents get this wrong:** Agents default to `useEffect` + `fetch` + `useState` for loading/error/data. This pattern produces race conditions, stale closures, no caching, no deduplication, no retry.

**Do:** Use TanStack Query or SWR for all server data. These handle loading, error, caching, deduplication, background refresh, and retry automatically.

```tsx
// WRONG — manual everything
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);
useEffect(() => { fetch('/api/users').then(r => r.json()).then(setData); }, []);

// RIGHT — library handles complexity
const { data, isLoading, error } = useQuery({
  queryKey: ['users'],
  queryFn: () => fetch('/api/users').then(r => r.json()),
});
```

For mutations: use `useMutation` with cache invalidation. For instant-feeling updates: optimistic updates with rollback on failure.

---

# Performance (useMemo / useCallback)

**Why agents get this wrong:** Agents either wrap everything in `useMemo`/`useCallback` (premature optimization, adds complexity) or never use them (causes expensive re-renders in hot paths). Both extremes are wrong.

**Use memoization ONLY when:**
- You measured a performance problem (React DevTools Profiler shows >1ms)
- The memoized value is passed to a `React.memo`-wrapped child
- The computation is genuinely expensive
- The value is a dependency of another hook

```tsx
// WRONG — premature, adds complexity for no benefit
const name = useMemo(() => `${first} ${last}`, [first, last]);

// RIGHT — expensive computation passed to memoized child
const sortedItems = useMemo(() =>
  items.sort((a, b) => complexSort(a, b)), [items]
);
return <MemoizedList items={sortedItems} />;
```

Don't memoize everything — it adds memory overhead and makes code harder to read. Memoize at measured bottlenecks.

---

# Accessibility in React

**Why agents get this wrong:** Agents build interactive components without keyboard support, focus management, or screen reader announcements. SPAs are especially bad — route changes are silent, focus goes nowhere.

**Do:**
- **Focus management:** After navigation, focus the main content heading. After modal open, focus first interactive element. After modal close, return focus to the trigger.
- **Announcements:** Use `aria-live="polite"` regions for async updates (toast, search results count). Use `role="alert"` for errors.
- **Custom components:** If building a custom dropdown/combobox/tabs, implement the ARIA pattern completely — `role`, `aria-selected`, `aria-expanded`, keyboard arrows, Home/End. Or use a library (Radix, React Aria, Headless UI) that handles it.
- **Skip links:** First focusable element should be "Skip to main content" link.

---

# TypeScript Patterns

**Why agents get this wrong:** Agents write loose types — `any` for props, `object` for state, string literals where unions belong. This defeats TypeScript's purpose and lets bugs through.

**Do:**
- Props: explicit interface per component. Never `React.FC` (adds implicit children). Use discriminated unions for variant props:
```tsx
// WRONG — loose, anything goes
type Props = { variant: string; onClick?: any };

// RIGHT — precise, TypeScript catches misuse
type Props =
  | { variant: 'link'; href: string }
  | { variant: 'button'; onClick: () => void };
```
- Event handlers: Use React's event types (`React.MouseEvent<HTMLButtonElement>`), not generic `any`.
- State: type the initial value explicitly when `null` is a valid state: `useState<User | null>(null)`.
- API responses: define response types matching the API contract. Never `as any`.
