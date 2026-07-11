---
type: autoresearch
goal: "Reduce data file size below 500 bytes"
metric:
  name: size_bytes
  direction: lower
  target: 500
scope:
  writable: ["src/**"]
  frozen: ["verify.sh"]
verify: "bash verify.sh"
budget:
  per_run_seconds: 10
  max_iterations: 10
  termination: target
---

# Test fixture brief

Reduce the size of src/data.txt below 500 bytes while keeping it valid.
