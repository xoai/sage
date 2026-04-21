#!/bin/bash
set -e

# Build the project
npm run build 2>/dev/null

# Measure main bundle size in KB
SIZE=$(du -sb dist/main.js 2>/dev/null | awk '{print $1/1024}')
if [ -z "$SIZE" ]; then
  # Try alternative paths
  SIZE=$(du -sb dist/index.js 2>/dev/null | awk '{print $1/1024}')
fi

if [ -z "$SIZE" ]; then
  echo "ERROR: Could not find bundle file" >&2
  exit 1
fi

echo "METRIC bundle_kb=$SIZE"
