# sage-pack-authoring

Tools for authoring new Sage skills and packs (ADR-7, §17.4). Install when you
build skill packs:

```bash
sage add xoai/sage-pack-authoring     # once published
sage add ./packs/sage-pack-authoring  # from a local checkout
```

**Skills:** pack-discover, pack-draft, pack-observe, pack-source-process,
pack-validate — the five-step authoring pipeline (find patterns → draft →
learn from codebases → process source docs → validate against contracts).

The framework's own skill-authoring guides and the behavioral skill-test harness
stay under `develop/` in the Sage repo (they test and document the framework
itself and are referenced by core `TESTS.md` files); they are not vendored into
user projects. Staged here for review; destined for github.com/xoai/sage-pack-authoring.
