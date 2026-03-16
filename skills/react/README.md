# react

**Layer 2 — Framework Pack**

React-specific patterns and anti-patterns for React 18/19. Hooks discipline,
component architecture, state management, and the mistakes agents make from
stale training data.

## Philosophy

React is the framework where LLM training data is most polluted. Fifteen years
of blog posts, Stack Overflow answers, and tutorials mix class components with
hooks, lifecycle methods with effects, Redux boilerplate with context, and
pre-React-19 patterns with post-React-19 patterns. An agent trained on all
of this produces code that "works" but uses outdated idioms.

This pack corrects the most common stale-training-data mistakes and establishes
the modern React mental model as the baseline for all React code in the project.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Patterns | 7 | Component composition, hooks discipline, state management, data fetching, error boundaries, forms, testing |
| Anti-patterns | 6 | useEffect abuse, derived state in useState, prop drilling, index keys, class components, inline object props |
| Constitution | 1 | 5 React-specific principles |

## Key Corrections

- **useEffect is not a lifecycle method.** It synchronizes with external systems.
  If you're using it to derive state, transform data, or respond to props — stop.
- **Not everything needs to be in state.** Values computed from existing state/props
  should be calculated during render, not stored in separate useState calls.
- **React.memo / useMemo / useCallback are optimization tools, not defaults.**
  Profile first, then memoize the bottleneck. Premature memoization adds complexity
  and can mask architectural problems.

## Overridden by nextjs

When `nextjs` is also installed, it overrides the data-fetching and
routing patterns from this pack, since Next.js handles those differently
(server components, App Router).
