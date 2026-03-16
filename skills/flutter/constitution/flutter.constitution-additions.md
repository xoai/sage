# Flutter Extension — Constitution Additions

## Flutter Principles

1. Widgets MUST be small and focused. A widget file exceeding 200 lines MUST be decomposed. Extract sub-widgets as separate classes, not methods returning widgets (methods returning widgets don't get independent rebuild boundaries).
2. State management MUST use a structured solution (Riverpod, BLoC, or Zustand) for any state shared beyond a single widget. setState() is ONLY acceptable for local UI state within a single StatefulWidget. No exceptions for "simple" features.
3. All TextEditingControllers, AnimationControllers, StreamSubscriptions, ScrollControllers, and FocusNodes MUST be disposed in the dispose() method. Memory leaks from undisposed controllers are the #1 source of Flutter production bugs.
4. All long lists MUST use lazy builder constructors (ListView.builder, GridView.builder, SliverList with delegate). Never use Column + .map() or ListView with children: [] for dynamic data exceeding 20 items.
5. All layouts MUST use responsive patterns — LayoutBuilder, MediaQuery.sizeOf, Expanded/Flexible. No hardcoded width/height values for layout containers. Test on both smallest phone (320dp wide) and tablet (768dp+ wide) in both orientations.
