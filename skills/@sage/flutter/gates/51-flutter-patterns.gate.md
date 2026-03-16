---
name: 51-flutter-patterns
order: 51
category: compliance
version: "1.0.0"
modes: [build, architect]
---

# Gate 51: Flutter Pattern Compliance

## Check Criteria

**Widget Architecture (FAIL if violated):**
- No widget file exceeds 200 lines without decomposition
- No helper methods returning widgets where a separate widget class is appropriate
- const constructors used on all eligible widgets

**State Management (FAIL if violated):**
- setState() only used for local UI state within a single widget
- Shared state uses a structured solution (Riverpod, BLoC, or equivalent)
- No API calls or business logic inside widget build methods
- No Future creation inside build() (causes infinite rebuild loops)

**Resource Lifecycle (FAIL if any missing):**
- All controllers disposed in dispose()
- All stream subscriptions cancelled in dispose()
- super.initState() called first, super.dispose() called last

**List Performance (FAIL if violated):**
- No Column + .map() or ListView(children: []) for dynamic data > 20 items
- Lazy builder constructors (ListView.builder, GridView.builder) used for all dynamic lists

**Layout (FAIL if hardcoded):**
- No hardcoded pixel dimensions for screen-level layout containers
- SafeArea used for edge content
- Responsive patterns (LayoutBuilder, MediaQuery.sizeOf) for adaptive layouts

## Failure Response

Identify the violation, explain the correct Flutter pattern, provide the fix.
