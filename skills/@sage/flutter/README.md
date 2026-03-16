# @sage/flutter

**Layer 2 — Framework Pack**

Flutter patterns for modern development (3.x+). Widget architecture, state
management, Impeller renderer, platform-adaptive design, and the common
mistakes agents make from outdated tutorials.

## Philosophy

Flutter's "everything is a widget" model is simultaneously its greatest strength
and the main source of agent mistakes. Agents build monolithic widget trees with
thousands of lines, misuse `setState` for everything, nest widgets 15 levels
deep, and ignore the widget lifecycle. This pack establishes clean widget
architecture, proper state management selection, and Impeller-era performance
patterns.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Patterns | 7 | Widget architecture, state management, async/data, navigation, platform-adaptive, testing, performance |
| Anti-patterns | 5 | God widgets, setState everywhere, ignoring dispose, hardcoded dimensions, unnecessary packages |
| Constitution | 1 | 5 Flutter-specific principles |
| Gate | 1 | Flutter pattern compliance check |
