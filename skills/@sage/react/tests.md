# Pack Tests: @sage/react

**Framework version tested:** React 18+
**Last tested:** 2025-03-13

---

## Test 1: Data display component

**Prompt:**
```
Create a component that fetches and displays a list of users from /api/users.
```

**Without pack:** Agent writes useEffect + fetch + useState with manual loading/error states.
**With pack:** Agent uses TanStack Query or SWR, with automatic caching and error handling.
**Tests:** Pattern "Data Fetching" + Anti-pattern "useEffect for Everything"

---

## Test 2: Computed display value

**Prompt:**
```
Create a shopping cart component that shows items and a total price.
```

**Without pack:** Agent stores `total` in useState and syncs it with useEffect when items change.
**With pack:** Agent derives `total` directly: `const total = items.reduce(...)` — no state, no effect.
**Tests:** Pattern "State Management" + Anti-pattern "Duplicated Derived State"

---

## Test 3: Large feature component

**Prompt:**
```
Build a user profile page with avatar upload, bio editing, notification preferences, and account deletion.
```

**Without pack:** Agent builds one 300+ line component with all features inline.
**With pack:** Agent splits into smaller components (AvatarUpload, BioEditor, NotificationPrefs, DangerZone) composed in a parent.
**Tests:** Pattern "Composition Over Monoliths"

---

## Test 4: Dynamic list rendering

**Prompt:**
```
Render a sortable list of tasks that users can reorder.
```

**Without pack:** Agent uses `tasks.map((task, index) => <Task key={index} />)`.
**With pack:** Agent uses `task.id` as key: `tasks.map(task => <Task key={task.id} />)`.
**Tests:** Anti-pattern "Array Index as Key"
