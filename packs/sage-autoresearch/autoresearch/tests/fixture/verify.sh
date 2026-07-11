#!/bin/bash
# Deterministic verify script for testing.
# Reads src/data.txt, counts bytes, outputs METRIC.
if [ ! -f src/data.txt ]; then
  echo "METRIC size_bytes=1000"
  exit 0
fi
SIZE=$(wc -c < src/data.txt)
echo "METRIC size_bytes=$SIZE"
