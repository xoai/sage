#!/bin/bash
set -e

# Run tests with coverage
npx vitest run --coverage --reporter=json 2>/dev/null || \
  npx jest --coverage --json 2>/dev/null || \
  python -m pytest --cov --cov-report=term 2>/dev/null

# Extract coverage percentage — adapt to your tool
# Vitest/Jest JSON output
if [ -f coverage/coverage-summary.json ]; then
  PCT=$(python3 -c "
import json
d = json.load(open('coverage/coverage-summary.json'))
print(d['total']['lines']['pct'])
" 2>/dev/null)
fi

# Python coverage
if [ -z "$PCT" ]; then
  PCT=$(python -m coverage report 2>/dev/null | grep TOTAL | awk '{print $NF}' | tr -d '%')
fi

if [ -z "$PCT" ]; then
  echo "ERROR: Could not extract coverage percentage" >&2
  exit 1
fi

echo "METRIC coverage_pct=$PCT"
