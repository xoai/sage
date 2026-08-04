#!/usr/bin/env bash
# run-opencode-adapter-tests.sh — the opencode adapter's deterministic suite.
#
# Stages a vendored-project-shaped scratch (adapter + real gate scripts + the
# real judge runtime + the claude-code journal hook for the parity check) and
# runs setup/adapter-test.mjs in it. No opencode binary, no model backend —
# this is the same "test the wire against the real scripts" pattern the
# 2026-07-17 Tier-A port established, extended to the scope judge.
#
# Exit: 0 green · 1 failures · 0 with a LOUD skip when node is unavailable
# (the adapter is javascript; a box without node cannot run opencode either,
# so there is no adapter behavior to verify on it).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if ! command -v node >/dev/null 2>&1; then
  echo "SKIPPED: node not found — the opencode adapter suite needs node." >&2
  exit 0
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "SKIPPED: python3 not found — the judge runtime needs python3." >&2
  exit 0
fi

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/sage-oc-adapter.XXXXXX")" || exit 1
trap 'rm -rf "$SCRATCH"' EXIT

mkdir -p "$SCRATCH/.opencode/plugin" "$SCRATCH/.opencode/sage-hooks" \
         "$SCRATCH/.sage/work" "$SCRATCH/sage/runtime/tools"

OC_SETUP="$REPO_ROOT/runtime/platforms/community/opencode/setup"
CC_HOOKS="$REPO_ROOT/runtime/platforms/claude-code/hooks"

cp "$OC_SETUP/sage-plugin.js" "$SCRATCH/.opencode/plugin/sage.js"
cp "$OC_SETUP/adapter-test.mjs" "$SCRATCH/adapter-test.mjs"

# The gate scripts the adapter drives — same set generate-opencode.sh installs.
for g in sage-spec-gate.sh sage-tdd-gate.sh sage-bookkeeping-gate.sh \
         sage-secrets-gate.sh sage-config-gate.sh sage-scope-gate.sh \
         sage-verify-gate.sh sage-verify-tracker.sh sage-degradation-log.sh \
         sage-manifest-sync.sh; do
  if [ -f "$CC_HOOKS/$g" ]; then
    cp "$CC_HOOKS/$g" "$SCRATCH/.opencode/sage-hooks/$g"
    chmod +x "$SCRATCH/.opencode/sage-hooks/$g"
  fi
done
for c in sage-verify.sh sage-spec-check.sh sage-hallucination-check.sh; do
  if [ -f "$REPO_ROOT/core/gates/scripts/$c" ]; then
    cp "$REPO_ROOT/core/gates/scripts/$c" "$SCRATCH/.opencode/sage-hooks/$c"
    chmod +x "$SCRATCH/.opencode/sage-hooks/$c"
  fi
done

# The judge runtime, at the vendored path the adapter resolves first — and
# the claude-code journal hook, for the journal schema parity check.
cp "$REPO_ROOT/runtime/tools/scope_judge.py" \
   "$SCRATCH/sage/runtime/tools/scope_judge.py"
cp "$CC_HOOKS/sage-scope-journal.sh" "$SCRATCH/claude-scope-journal.sh"
chmod +x "$SCRATCH/claude-scope-journal.sh"

cd "$SCRATCH" || exit 1
node adapter-test.mjs
rc=$?
exit "$rc"
