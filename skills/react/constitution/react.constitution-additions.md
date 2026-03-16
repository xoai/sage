# React Extension — Constitution Additions

## React Principles

1. Components MUST be functional components with hooks. No class components in new code.
2. Component rendering MUST be a pure function of props and state. No side effects during render except via hooks.
3. All list renderings MUST use stable, unique keys — never array index unless the list is static, never-reordered, and never-filtered.
4. State that can be computed from other state or props MUST be computed during render, not stored in separate useState.
5. useEffect MUST only be used to synchronize with external systems (DOM APIs, network, timers, third-party libraries). Not for derived state, not for prop-change responses, not for data transformation.
