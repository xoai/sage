# Anti-Pattern: God Widgets

**What agents do:** Build 500+ line widget files with UI, state, API calls, formatting, and navigation all in one class.

**Why agents do this:** Flutter tutorials often show complete features in one widget for simplicity. Agents copy this pattern for production code, not realizing the tutorial was optimizing for readability, not performance.

**Why it's wrong:** Any `setState` rebuilds the entire tree — a text input keystroke triggers a rebuild of images, lists, and complex layouts. Do instead: Extract each section as its own widget class for independent rebuild boundaries. Methods returning Widget don't create boundaries — only separate widget classes do.

---

# Anti-Pattern: setState for Everything

**What agents do:** Use `setState()` as the only state mechanism — API data, error state, loading flags, shared preferences all managed via setState in a single StatefulWidget.

**Why agents do this:** `setState` is the first state mechanism taught in every Flutter tutorial. It works for simple examples, so agents apply it everywhere.

**Why it's wrong:** Can't share state between screens. Every state change rebuilds everything. Testing requires the full widget. Do instead: Riverpod/BLoC for anything beyond trivial local UI state. `setState` only for local toggle/animation state.

---

# Anti-Pattern: Not Disposing Controllers

**What agents do:** Create TextEditingController, AnimationController, ScrollController, StreamSubscription without calling `.dispose()` in the `dispose()` method.

```dart
// WRONG — memory leak
class _MyState extends State<MyWidget> {
  final controller = TextEditingController(); // never disposed!
}

// RIGHT
void dispose() {
  controller.dispose();
  super.dispose(); // super.dispose() LAST
}
```

**Why it's wrong:** Memory leaks. After 20 navigations, 20 leaked controllers ticking in background. The #1 production Flutter crash source. Always dispose. `super.initState()` first, `super.dispose()` last.

---

# Anti-Pattern: Hardcoded Dimensions

**What agents do:** Use `Container(width: 375, height: 812)` — pixel values from one specific phone model.

**Why it's wrong:** Breaks on every other device. Do instead: `MediaQuery.sizeOf(context)`, `SafeArea`, `Expanded`, `Flexible`, `LayoutBuilder` for responsive layouts. Never hardcode screen-level dimensions.

---

# Anti-Pattern: Package for Every Feature

**What agents do:** Install a pub.dev package for every minor feature — toast display, email validation, date formatting, padding helpers.

**Why it's wrong:** Bloats bundle size, creates maintenance debt, risks version conflicts and abandoned packages. Do instead: Check if Flutter/Dart core provides it first (`intl` for dates, `RegExp` for validation). Write simple utilities yourself if under 50 lines.
