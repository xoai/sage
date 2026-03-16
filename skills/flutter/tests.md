# Pack Tests: flutter

**Framework version tested:** Flutter 3.x+
**Last tested:** 2025-03-13

---

## Test 1: Data display screen

**Prompt:**
```
Create a screen that fetches and displays a list of products from an API.
```

**Without pack:** Agent builds one StatefulWidget with setState for loading/error/data, fetch call in initState, all UI inline.
**With pack:** Agent separates into a provider (Riverpod FutureProvider) and a ConsumerWidget with `.when(loading:, error:, data:)` handling all states.
**Tests:** Pattern "State Management Selection" + Anti-pattern "setState for Everything"

---

## Test 2: Form with text inputs

**Prompt:**
```
Build a registration form with name, email, and password fields.
```

**Without pack:** Agent creates TextEditingControllers without disposing them.
**With pack:** Agent creates controllers in initState, disposes all in dispose() with super.dispose() called last.
**Tests:** Anti-pattern "Not Disposing Controllers"

---

## Test 3: Complex screen layout

**Prompt:**
```
Create a dashboard screen with a header, stats cards, a chart, and a recent activity list.
```

**Without pack:** Agent builds a single 400+ line widget with all sections inline.
**With pack:** Agent extracts HeaderSection, StatsCards, ChartWidget, RecentActivity as separate widget classes composed in the dashboard.
**Tests:** Pattern "Widget Architecture" + Anti-pattern "God Widgets"

---

## Test 4: Responsive product grid

**Prompt:**
```
Build a product catalog grid that works on phones and tablets.
```

**Without pack:** Agent hardcodes `GridView` with `crossAxisCount: 2` and fixed pixel dimensions.
**With pack:** Agent uses `LayoutBuilder` or `MediaQuery.sizeOf` for adaptive column count, relative sizing, SafeArea for insets.
**Tests:** Anti-pattern "Hardcoded Dimensions"
