# sage-autoresearch

The autoresearch optimization-loop runtime, extracted from Sage core (ADR-8,
§19 R60) into its own package — like sage-memory, it has a distinct risk profile
(a sandboxed git-driven iteration harness) and its own release cadence.

The `/autoresearch` workflow and the `autoresearch` skill stay in Sage core.
When invoked, they probe for this package (`python3 -c 'import autoresearch'`)
and, if it is absent, degrade LOUDLY — announcing manual mode and logging to
decisions.md — with the install command:

```bash
sage add xoai/sage-autoresearch
```

`autoresearch/` is the importable package (`python3 -m autoresearch run …`) and
carries its own 15-module test suite. Staged here for review; destined for
github.com/xoai/sage-autoresearch (and PyPI).
