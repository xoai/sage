#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
PYTHON_BIN="${PYTHON_BIN:-python3}"
CLAUDE_PROJECT=$(mktemp -d)
HERMES_PROJECT=$(mktemp -d)
HERMES_PROFILE="$HERMES_PROJECT/profile"
trap 'rm -rf "$CLAUDE_PROJECT" "$HERMES_PROJECT"' EXIT

ln -s "$ROOT" "$CLAUDE_PROJECT/sage"
ln -s "$ROOT" "$HERMES_PROJECT/sage"
mkdir -p "$HERMES_PROFILE"

PYTHON_BIN="$PYTHON_BIN" bash \
  "$ROOT/runtime/platforms/claude-code/setup/generate-claude-code.sh" \
  "$CLAUDE_PROJECT" >/dev/null
PYTHON_BIN="$PYTHON_BIN" bash \
  "$ROOT/runtime/platforms/hermes/setup/generate-hermes.sh" \
  "$HERMES_PROJECT" "$HERMES_PROFILE" >/dev/null

test -f "$CLAUDE_PROJECT/.sage/composition.json"
test -f "$HERMES_PROJECT/.sage/composition.json"

"$PYTHON_BIN" - \
  "$CLAUDE_PROJECT/.sage/composition.json" \
  "$HERMES_PROJECT/.sage/composition.json" <<'PY'
import json
import sys
from pathlib import Path

claude = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
hermes = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

def normalized(catalog):
    return {
        "providers": {
            key: {
                field: value
                for field, value in provider.items()
                if field != "sources"
            }
            for key, provider in catalog["providers"].items()
        },
        "policy": catalog["policy"],
        "workflow_defaults": catalog["workflow_defaults"],
    }

assert normalized(claude) == normalized(hermes)
assert "implement" in claude["providers"]
assert "sage:build" in claude["workflow_defaults"]
print("composition platform generation: PASS")
PY
