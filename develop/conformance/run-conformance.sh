#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Sage conformance suite — does the platform do what its contract claims?
#
# ADR-11. A declared capability that nothing checks is the pre-1.2.0 mistake
# with better formatting. This is the checking.
#
# THREE LEVELS, strongest first. Every declared capability must be provable by
# one of them, or it fails — and the fix is a check, an attestation, or an honest
# `false`. Never a sentence in a README asserting it works.
#
#   Level 1  GENERATED-OUTPUT CHECKS.  Free, CI-safe, run on every PR.
#            `sage init` the platform into a scratch project and look at what
#            came out. If a contract says `command-delivery: true`, there had
#            better be commands in the generated tree.
#
#   Level 2  LIVE HEADLESS PROBES.  Costs money, gated on the release workflow.
#            The only way to prove `pre-tool-veto` is to make a hook veto
#            something in a real session and watch the edit not happen.
#
#   Level 3  ATTESTATION VALIDATION.  Free. For capabilities no free check can
#            reach: the evidence file exists, parses, and is not expired (C15).
#
# Exit: 0 pass · 1 fail · 2 unverifiable (the Sage three-state contract).
#
# Usage:
#   run-conformance.sh <platform> [--level 1,3] [--report]
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLATFORM="${1:-}"
LEVELS="1,3"
REPORT=""
shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --level) LEVELS="$2"; shift 2 ;;
    --level=*) LEVELS="${1#--level=}"; shift ;;
    --report) REPORT="true"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$PLATFORM" ]; then
  echo "usage: run-conformance.sh <platform> [--level 1,2,3] [--report]" >&2
  exit 2
fi

N_PASS=0; N_FAIL=0; N_SKIP=0
RESULTS=""

green() { printf '\033[32m%s\033[0m' "$1"; }
red()   { printf '\033[31m%s\033[0m' "$1"; }
yellow(){ printf '\033[33m%s\033[0m' "$1"; }

ok()   { N_PASS=$((N_PASS+1)); printf '  %s %-26s %s\n' "$(green ✓)" "$1" "$2"; RESULTS="$RESULTS
| \`$1\` | ✅ pass | $2 |"; }
bad()  { N_FAIL=$((N_FAIL+1)); printf '  %s %-26s %s\n' "$(red ✗)" "$1" "$2"; RESULTS="$RESULTS
| \`$1\` | ❌ FAIL | $2 |"; }
skip() { N_SKIP=$((N_SKIP+1)); printf '  %s %-26s %s\n' "$(yellow ○)" "$1" "$2"; RESULTS="$RESULTS
| \`$1\` | ○ skipped | $2 |"; }

echo ""
echo "── Conformance: $PLATFORM ──"

# ── The contract itself must parse before anything else means anything ──
CONTRACT_JSON="$(python3 "$REPO_ROOT/runtime/tools/contract.py" --json 2>/dev/null)" || {
  echo "  ⚠️  UNVERIFIABLE — contracts do not parse. Fix contract.py --check first."
  exit 2
}

read_cap() {  # read_cap <capability> → true | false | attested | missing
  python3 - "$PLATFORM" "$1" <<'PY'
import json, subprocess, sys, pathlib
root = pathlib.Path(__file__).resolve()
out = subprocess.run(["python3", "runtime/tools/contract.py", "--json"],
                     capture_output=True, text=True, cwd=sys.argv[0] and ".")
try:
    data = json.loads(out.stdout)
except Exception:
    print("missing"); raise SystemExit(0)
for c in data:
    if c.get("name") == sys.argv[1]:
        print(str((c.get("capabilities") or {}).get(sys.argv[2], "missing")).lower())
        raise SystemExit(0)
print("missing")
PY
}

CAPS="$(python3 - "$PLATFORM" <<'PY'
import json, subprocess, sys
out = subprocess.run(["python3", "runtime/tools/contract.py", "--json"],
                     capture_output=True, text=True)
data = json.loads(out.stdout)
for c in data:
    if c.get("name") == sys.argv[1]:
        for k, v in (c.get("capabilities") or {}).items():
            print("%s=%s" % (k, str(v).lower()))
        raise SystemExit(0)
raise SystemExit(3)
PY
)" || { echo "  ⚠️  UNVERIFIABLE — no contract named '$PLATFORM'."; exit 2; }

cap() { printf '%s\n' "$CAPS" | grep "^$1=" | cut -d= -f2; }

# Artifact layout — read from the CONTRACT, not assumed.
#
# The first version of this checker hardcoded claude-code's tree (CLAUDE.md,
# .claude/commands/) and duly reported gemini-cli as FAILING context-injection
# while it was writing GEMINI.md exactly as designed. The checker was wrong, not
# the platform. R112 exists to stop exactly that: per-platform conditionals that
# duplicate what the contract already says.
ART="$(python3 - "$PLATFORM" <<'ARTEOF'
import json, subprocess, sys
out = subprocess.run(["python3", "runtime/tools/contract.py", "--json"],
                     capture_output=True, text=True)
for c in json.loads(out.stdout):
    if c.get("name") == sys.argv[1]:
        a = c.get("artifacts") or {}
        print("instructions=%s" % a.get("instructions", "CLAUDE.md"))
        print("commands-dir=%s" % a.get("commands-dir", ""))
        print("skills-dir=%s" % a.get("skills-dir", ""))
        print("hooks-config=%s" % a.get("hooks-config", ".claude/settings.json"))
        raise SystemExit(0)
ARTEOF
)"
art() { printf '%s\n' "$ART" | grep "^$1=" | cut -d= -f2; }

INSTR_FILE="$(art instructions)"
CMDS_DIR="$(art commands-dir)"
SKILLS_DIR="$(art skills-dir)"
HOOKS_FILE="$(art hooks-config)"


# ═══════════════════════════════════════════════════════════════════════════
# LEVEL 1 — generated-output checks
#
# Generate a real project for this platform and look at what came out. This is
# the level that catches the failure Sage actually had: `--platform generic`
# claimed to work and silently produced a claude-code install.
# ═══════════════════════════════════════════════════════════════════════════
if printf '%s' "$LEVELS" | grep -q 1; then
  echo ""
  echo "  Level 1 — generated output"

  WORK="$(mktemp -d "${TMPDIR:-/tmp}/sage-conf-XXXXXX")"
  trap 'rm -rf "$WORK"' EXIT

  mkdir -p "$WORK/home"
  # Vendor the framework the way context_budget.py does — measure what a user gets.
  ( cd "$REPO_ROOT" && tar --exclude=.git --exclude=node_modules --exclude=__pycache__ \
      --exclude=dist --exclude=.sage -cf - . ) | ( mkdir -p "$WORK/home/framework" && tar -xf - -C "$WORK/home/framework" )

  mkdir -p "$WORK/proj"
  ( cd "$WORK/proj" && git init -q \
      && SAGE_HOME="$WORK/home" bash "$WORK/home/framework/bin/sage" init \
           --preset base --platform "$PLATFORM" ) >"$WORK/init.log" 2>&1
  INIT_RC=$?

  if [ $INIT_RC -ne 0 ]; then
    bad "generation" "sage init --platform $PLATFORM failed (see log)"
  else
    ok "generation" "sage init --platform $PLATFORM succeeded"

    # context-injection — an instructions file the platform will actually read.
    if [ "$(cap context-injection)" = "true" ]; then
      if [ -f "$WORK/proj/$INSTR_FILE" ]; then
        LINES=$(wc -l < "$WORK/proj/$INSTR_FILE" | tr -d ' ')
        ok "context-injection" "$INSTR_FILE generated ($LINES lines)"
      else
        bad "context-injection" "declared true, but $INSTR_FILE was not generated"
      fi
    fi

    # command-delivery — commands the platform can offer explicitly.
    case "$(cap command-delivery)" in
      true)
        N_CMD=0
        if [ -n "$CMDS_DIR" ] && [ -d "$WORK/proj/$CMDS_DIR" ]; then
          N_CMD="$(find "$WORK/proj/$CMDS_DIR" -type f | wc -l | tr -d ' ')"
        fi
        if [ "$N_CMD" -gt 0 ]; then
          ok "command-delivery" "$N_CMD command(s) in $CMDS_DIR"
        else
          bad "command-delivery" "declared true, but $CMDS_DIR is empty or absent"
        fi ;;
      false)
        # A `false` must ALSO be true. A platform claiming no commands must not be
        # quietly shipping them: a contract that lies in the SAFE direction is
        # still lying, and the user still cannot trust its next line.
        if [ -n "$CMDS_DIR" ] && [ -d "$WORK/proj/$CMDS_DIR" ]; then
          bad "command-delivery" "declared false, but $CMDS_DIR was generated anyway"
        else
          ok "command-delivery" "declared false, and none generated"
        fi ;;
    esac

    # native-skill-discovery — ADR-9's delivery fork, checked on BOTH branches.
    case "$(cap native-skill-discovery)" in
      true|attested)
        N_SK=0
        if [ -n "$SKILLS_DIR" ] && [ -d "$WORK/proj/$SKILLS_DIR" ]; then
          N_SK="$(find "$WORK/proj/$SKILLS_DIR" -name 'SKILL.md' | wc -l | tr -d ' ')"
        fi
        if [ "$N_SK" -gt 0 ]; then
          ok "native-skill-discovery" "$N_SK skills emitted for on-demand discovery"
        else
          bad "native-skill-discovery" "declared, but no skills were emitted to $SKILLS_DIR"
        fi ;;
      false)
        # No discovery means the generator MUST inline the content instead. If it
        # does NEITHER, the content does not exist for that platform's users at all
        # — while their instructions file still points at it ("→ sage-gates skill")
        # as though it were reachable. That is worse than never having moved it.
        #
        # This check found a real regression on all four community platforms
        # (P4-T4): ADR-9 took 220 lines out of the eager body and only claude-code
        # and generic ever got them back.
        INSTR="$WORK/proj/$INSTR_FILE"
        if [ -f "$INSTR" ] && grep -q "^# Reference" "$INSTR"; then
          ok "native-skill-discovery" "declared false, and the skills are INLINED instead"
        else
          bad "native-skill-discovery" "declared false, and nothing is inlined — the content is UNREACHABLE for this platform's users"
        fi ;;
    esac

    # pre-tool-veto / post-tool-events / session-events — the hooks.
    HOOKS_JSON="$WORK/proj/$HOOKS_FILE"
    for pair in "pre-tool-veto:PreToolUse" "post-tool-events:PostToolUse" "session-events:SessionStart"; do
      CAPNAME="${pair%%:*}"; EVENT="${pair##*:}"
      case "$(cap "$CAPNAME")" in
        true|attested)
          if { [ -f "$HOOKS_JSON" ] && grep -q "$EVENT" "$HOOKS_JSON"; } || \
             { [ -f "$WORK/proj/.claude/settings.local.json" ] && grep -q "$EVENT" "$WORK/proj/.claude/settings.local.json"; }; then
            ok "$CAPNAME" "$EVENT hook registered in the generated project"
          else
            bad "$CAPNAME" "declared, but no $EVENT hook was registered"
          fi ;;
        false)
          if [ -f "$HOOKS_JSON" ] && grep -q "$EVENT" "$HOOKS_JSON"; then
            bad "$CAPNAME" "declared false, but a $EVENT hook was registered anyway"
          else
            ok "$CAPNAME" "declared false, and no $EVENT hook registered"
          fi ;;
      esac
    done

    # subagent-dispatch — not observable from generated output. Level 2 or an
    # attestation. Saying so is the honest move; passing it silently is not.
    case "$(cap subagent-dispatch)" in
      true)
        skip "subagent-dispatch" "not provable from generated output — needs a level-2 probe" ;;
      attested)
        : ;;  # level 3 handles it
      false)
        ok "subagent-dispatch" "declared false (subagent mode will refuse loudly, R97)" ;;
    esac
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# LEVEL 2 — live headless probes (costs money; release workflow only)
# ═══════════════════════════════════════════════════════════════════════════
if printf '%s' "$LEVELS" | grep -q 2; then
  echo ""
  echo "  Level 2 — live probes"
  if [ "$PLATFORM" != "claude-code" ]; then
    skip "live-probes" "no headless driver for $PLATFORM"
  elif ! command -v claude >/dev/null 2>&1; then
    skip "live-probes" "the claude CLI is not installed"
  else
    bash "$(dirname "${BASH_SOURCE[0]}")/probes/claude-code-veto.sh" && \
      ok "pre-tool-veto" "a live hook blocked a live edit" || \
      bad "pre-tool-veto" "the hook did NOT block (see probe output)"
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# LEVEL 3 — attestation validation (free)
#
# An `attested` capability is a LOAN against a claim, not a gift. The evidence
# must exist, and the loan must not have matured (C15).
# ═══════════════════════════════════════════════════════════════════════════
if printf '%s' "$LEVELS" | grep -q 3; then
  echo ""
  echo "  Level 3 — attestations"
  ATT_OUT="$(python3 "$REPO_ROOT/develop/conformance/check_attestations.py" "$PLATFORM" 2>&1)"
  ATT_RC=$?
  if [ $ATT_RC -eq 0 ]; then
    printf '%s\n' "$ATT_OUT" | while IFS= read -r line; do [ -n "$line" ] && echo "  $(green ✓) $line"; done
    N_PASS=$((N_PASS + 1))
  elif [ $ATT_RC -eq 3 ]; then
    echo "  ○ no attestations declared"
  else
    printf '%s\n' "$ATT_OUT" | while IFS= read -r line; do [ -n "$line" ] && echo "  $(red ✗) $line"; done
    N_FAIL=$((N_FAIL + 1))
  fi
fi

echo ""
printf '  pass %d · fail %d · skip %d\n' "$N_PASS" "$N_FAIL" "$N_SKIP"

if [ -n "$REPORT" ]; then
  OUT="$REPO_ROOT/develop/conformance/reports/${PLATFORM}-$(date +%Y-%m-%d).md"
  mkdir -p "$(dirname "$OUT")"
  {
    echo "# Conformance report — $PLATFORM"
    echo ""
    echo "**Date:** $(date +%Y-%m-%d) · **Levels:** $LEVELS"
    echo "**Result:** $N_PASS passed, $N_FAIL failed, $N_SKIP skipped"
    echo ""
    echo "| Capability | Result | Detail |"
    echo "|---|---|---|"
    printf '%s\n' "$RESULTS"
  } > "$OUT"
  echo "  report → ${OUT#$REPO_ROOT/}"
fi

[ "$N_FAIL" -gt 0 ] && exit 1
exit 0
