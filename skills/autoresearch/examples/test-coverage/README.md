# Example: Test Coverage Improvement

## Setup

1. Have a project with a test runner that reports coverage (Jest, Vitest, pytest)
2. Copy `brief.md` and `autoresearch.sh` to `.sage/work/YYYYMMDD-coverage/`
3. Adapt `autoresearch.sh` to your test runner's coverage output format

## Run

```
/autoresearch
```

## What the agent will try

Typical winning patterns for coverage improvement:
- Add tests for uncovered functions (start with highest-impact)
- Add edge case tests (null inputs, empty arrays, error paths)
- Add branch coverage for conditionals
- Test error handling paths
- Test boundary conditions

## Notes

- Coverage percentage is a proxy — the agent optimizes the number, not test quality
- Frozen config files prevent the agent from lowering coverage thresholds
- Set a reasonable budget (180s) since test suites can be slow
