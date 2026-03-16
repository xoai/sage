# Widget Architecture

**Why agents get this wrong:** Agents build 500+ line god widgets with UI, state, API calls, and formatting in one file. Flutter's performance depends on small widget trees with independent rebuild boundaries.

**Do:** Extract each logical section as a separate widget class (not a helper method returning Widget — methods don't create rebuild boundaries). Each widget file under 200 lines.

**Use `const` constructors aggressively.** `const` widgets are canonicalized — Flutter creates a single shared instance and skips the entire rebuild subtree. Mark every stateless widget `const`. This isn't just a style preference — it's a performance mechanism that eliminates unnecessary work:

```dart
// WRONG — helper method, no rebuild boundary
Widget _buildHeader() => Container(...);

// RIGHT — separate widget, independent rebuild, const-eligible
class ProfileHeader extends StatelessWidget {
  const ProfileHeader({super.key, required this.user});
  // ...
}
```

---

# State Management Selection

**Why agents get this wrong:** Agents use `setState()` for everything — shared state, server data, complex domain logic. This forces entire widget rebuilds on any change.

**Decision framework:**
- State used by one widget only → `setState`
- Shared across widgets → Riverpod provider or InheritedWidget
- Complex domain logic with events → BLoC
- Server/async data → Riverpod `FutureProvider`/`StreamProvider`

Never use `setState` for data shared between screens — it can't cross widget boundaries.

---

# Async and Data Fetching

**Why agents get this wrong:** Agents create Futures inside `build()`, causing infinite rebuild loops. Or they put all async logic directly in widgets without a repository layer.

```dart
// WRONG — creates new Future every build, infinite loop
Widget build(context) {
  return FutureBuilder(future: fetchProducts(), ...); // fetchProducts() called every build!
}

// RIGHT — Future created once in initState or provider
late final Future<List<Product>> _productsFuture;
void initState() { _productsFuture = fetchProducts(); }
Widget build(context) {
  return FutureBuilder(future: _productsFuture, ...);
}
```

Handle ALL three states: loading, error, AND data. Use a repository pattern to separate data access from UI.

---

# Navigation with GoRouter

**Why agents get this wrong:** Agents use imperative `Navigator.push` chains that become unmanageable and break deep linking.

**Do:** Use GoRouter for declarative routing. Define routes in one place. Use `redirect` for auth guards at the router level, not per-screen. Support deep links from the start — it's painful to add later. Use `StatefulShellRoute` for tab-based navigation with preserved state.

---

# Platform-Adaptive Design

**Why agents get this wrong:** Agents apply Material Design everywhere, even on iOS where it feels foreign.

**Do:** Use `Platform.isIOS`/`Platform.isAndroid` for platform-specific behavior. Use adaptive widgets (`Switch.adaptive`, `Slider.adaptive`, `showAdaptiveDialog`). Match platform navigation: bottom tabs on iOS, drawer or top tabs on Android. Share business logic, adapt presentation.

---

# Testing

**Why agents get this wrong:** Agents skip Flutter testing entirely or only write unit tests for utilities, ignoring widget tests.

**Three layers:** Unit tests for business logic. Widget tests for component behavior (`testWidgets`, `find.byType`, `tester.tap`, `tester.pumpAndSettle`). Integration tests for critical user flows. Widget tests are the highest-value layer — they catch UI regressions without a real device and run in seconds.

---

# Performance

**Why agents get this wrong:** Agents write expensive `build()` methods with inline computations and no rebuild boundaries.

**Do:** Keep `build()` simple — no computation, no conditionals that create different tree shapes. Use `RepaintBoundary` to isolate frequently-updating widgets (animations, timers). Use `const` widgets wherever possible to skip rebuild. Use `ListView.builder` (lazy) instead of `ListView(children: [...])` (eager) for any list. Profile with Flutter DevTools — look for unnecessary rebuilds, not just frame drops.

---

# Keys and Widget Identity

**Why agents get this wrong:** Agents don't use `Key` parameters, causing Flutter to reuse widget state incorrectly when lists are reordered or items are conditionally shown/hidden.

**Do:** Use `ValueKey(item.id)` on list items, `UniqueKey()` when you want forced rebuild. Most critical in `ListView.builder` with reorderable or filterable data. Without keys, text fields keep old values when items swap positions — same bug as React index keys.

---

# Error Handling in Providers

**Why agents get this wrong:** Agents use `FutureProvider` and `StreamProvider` but only handle the `.data` case. Loading and error states silently render nothing or crash.

**Do:** Always use `.when()` with ALL three states:
```dart
ref.watch(productsProvider).when(
  loading: () => const Center(child: CircularProgressIndicator()),
  error: (error, stack) => ErrorWidget(error, onRetry: () => ref.refresh(productsProvider)),
  data: (products) => ProductList(products: products),
);
```
Never use `.value!` — it crashes on loading/error. The `.when()` pattern makes states explicit and exhaustive.
