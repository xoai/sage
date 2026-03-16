# Anti-Pattern: useEffect for Everything

**What agents do:** Use `useEffect` to compute derived values, handle form submission, transform data, and synchronize state that could be calculated directly.

**Why agents do this:** Training data contains millions of examples of useEffect for everything — it was the "default tool" for any side-effect-like logic in pre-hooks-maturity React (2019-2022).

**Why it's wrong:** Creates unnecessary render cycles, race conditions, and stale closures. A derived value (`const total = items.reduce(...)`) is simpler, faster, and bug-free compared to `useEffect` + `setState` to "sync" the same value.

**Do instead:** Before writing useEffect, ask: "Can this be a derived value, an event handler, or fetched server-side?" Only useEffect for external system synchronization.

---

# Anti-Pattern: Duplicated Derived State

**What agents do:** Store a computed value in useState and sync it with useEffect when its source changes:

```tsx
// WRONG — two sources of truth
const [items, setItems] = useState([]);
const [total, setTotal] = useState(0);
useEffect(() => { setTotal(items.reduce((s, i) => s + i.price, 0)); }, [items]);

// RIGHT — derived directly
const total = items.reduce((s, i) => s + i.price, 0);
```

**Why it's wrong:** Two sources of truth that can desync. Extra render cycle on every change. If expensive, use `useMemo`. Never store what you can derive.

---

# Anti-Pattern: Prop Drilling

**What agents do:** Pass props through 4-5 intermediate components that don't use them, just to reach a deeply nested child.

**Why it's wrong:** Every intermediate component re-renders when the prop changes. Refactoring any component in the chain breaks the others. Do instead: Use composition (children prop), context (for truly global state), or restructure the component tree to flatten it.

---

# Anti-Pattern: Array Index as Key

**What agents do:** `items.map((item, index) => <Item key={index} />)` for lists that can be reordered, filtered, or modified.

**Why agents do this:** The `.map((item, index) =>` pattern puts `index` right there as a convenient key. Tutorials use it for simple examples, and agents copy the pattern without considering whether the list is static or dynamic.

**Why it's wrong:** React uses keys to track identity across renders. Index keys cause incorrect reuse when items are inserted, removed, or reordered — inputs keep stale values, animations break, state bleeds between items. Do instead: Use a stable unique ID from the data (`key={item.id}`).

---

# Anti-Pattern: Inline Object/Array Props

**What agents do:** Pass `style={{margin: 10}}` or `options={[1,2,3]}` directly in JSX, creating a new reference every render.

**Why it's wrong:** Breaks `React.memo` and causes unnecessary re-renders of child components. Matters most in lists and frequently-updating parents. Do instead: Hoist constants outside the component or wrap in `useMemo`.

---

# Anti-Pattern: Single Root Error Boundary

**What agents do:** Place one `<ErrorBoundary>` at the app root and nowhere else. Or no error boundary at all.

**Why it's wrong:** One error in any component crashes the entire app. A settings page error shouldn't blank the dashboard. Do instead: Error boundaries at route level, feature level, and around data-dependent sections. Multiple boundaries isolate failures.

---

## Old Patterns (Deprecated Reference)

<details>
<summary>Class Components and lifecycle methods — superseded by Hooks (React 16.8+, Feb 2019)</summary>

Class components still work but SHOULD NOT be generated for new code.
Error boundaries are the sole exception — they still require class syntax.

| Class pattern (deprecated) | Hooks replacement |
|---------------------------|------------------|
| `class Foo extends Component` | `function Foo()` or `const Foo = () =>` |
| `this.state` / `this.setState` | `useState` |
| `componentDidMount` | `useEffect(() => { ... }, [])` |
| `componentDidUpdate(prevProps)` | `useEffect(() => { ... }, [dep])` |
| `componentWillUnmount` | `useEffect` cleanup return |
| `shouldComponentUpdate` | `React.memo` |
| `getDerivedStateFromProps` | Derive in render or `useMemo` |
| Higher-Order Components (HOCs) | Custom hooks |
| Render props | Custom hooks |
| `createRef` | `useRef` |
| `this.context` with `contextType` | `useContext` |
</details>

<details>
<summary>Legacy Context API — replaced by createContext (React 16.3+, Mar 2018)</summary>

The old `childContextTypes` / `getChildContext` API was removed in React 19.
If agents generate this pattern, correct to `createContext` + `useContext`.
</details>

<details>
<summary>createReactClass and mixins — removed</summary>

`React.createClass` was removed in React 16. Mixins have no equivalent in
modern React — the pattern is replaced by custom hooks for shared logic
and composition for shared rendering.
</details>
