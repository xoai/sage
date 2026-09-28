#!/usr/bin/env bash
# sage-visual-gate.sh — Deterministic visual checks for Gate 6
# Captures screenshots, then runs automated checks that don't require AI judgment.
# AI-based visual review (layout, hierarchy, aesthetics) is done by the visual-review skill.
#
# Usage: bash sage/core/gates/scripts/sage-visual-gate.sh <url> [feature-dir]
#
# Exit contract (ADR-1):
#   0 = screenshots captured, automated checks clean
#   1 = a real visual defect (blank page, missing capture, mobile overflow)
#   2 = unverifiable — no browser toolchain, or the page could not be loaded
#
# Exit 2 matters here: "the layout is fine" and "no browser is installed" are
# different claims. A missing toolchain used to be reported as a visual defect.
#
# What this script checks deterministically:
#   1. Screenshots captured at all breakpoints (files exist, non-zero)
#   2. No horizontal overflow on mobile (page width matches viewport)
#   3. Page is not blank (screenshot file size above threshold)
#   4. No console errors during page load
#
# What the visual-review SKILL checks (requires AI judgment):
#   - Layout matches spec
#   - Visual hierarchy is correct
#   - Responsive behavior is appropriate
#   - Typography and spacing are consistent

set -uo pipefail

URL="${1:-}"
FEATURE_DIR="${2:-.sage/screenshots}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS=true
WARNINGS=0

log()  { echo "$1"; }
warn() { log "⚠️  $1"; WARNINGS=$((WARNINGS + 1)); }
fail() { log "❌ $1"; PASS=false; }

unverifiable() {
  log ""
  log "═══ Gate 6 Result ═══"
  log "⚠️ UNVERIFIABLE — $1"
  exit 2
}

if [ -z "$URL" ]; then
  echo "Usage: sage-visual-gate.sh <url> [screenshot-output-dir]"
  echo "  url: page to screenshot (http://localhost:3000 or file:///path)"
  echo "  screenshot-output-dir: where to save (default: .sage/screenshots)"
  exit 1
fi

log "═══ Sage Gate 6: Visual Verification ═══"
log "  URL: $URL"
log "  Output: $FEATURE_DIR"
log ""

# ── Step 0: Preflight ──
#
# Missing tooling is unverifiable, never a visual defect. The old resolution
# rooted SAGE_ROOT at core/ (SCRIPT_DIR/../..), so the primary path was always
# wrong and only the fallback ever matched.
SCREENSHOT_TOOL="${SAGE_SCREENSHOT_TOOL:-}"
if [ -z "$SCREENSHOT_TOOL" ]; then
  for candidate in \
    "$SCRIPT_DIR/../../../runtime/tools/sage-screenshot.sh" \
    "$SCRIPT_DIR/../../runtime/tools/sage-screenshot.sh" \
    "$SCRIPT_DIR/../../../../runtime/tools/sage-screenshot.sh"; do
    if [ -f "$candidate" ]; then
      SCREENSHOT_TOOL="$candidate"
      break
    fi
  done
fi

if [ -z "$SCREENSHOT_TOOL" ] || [ ! -f "$SCREENSHOT_TOOL" ]; then
  unverifiable "screenshot tool not found (set SAGE_SCREENSHOT_TOOL to override)"
fi
if ! command -v node >/dev/null 2>&1; then
  unverifiable "node is not installed — a browser is required to capture screenshots"
fi
if ! command -v python3 >/dev/null 2>&1; then
  unverifiable "python3 is required to read the capture results"
fi

mkdir -p "$FEATURE_DIR"

# ── Step 1: Capture screenshots ──
log "── Step 1: Capturing screenshots ──"

CAPTURE_OUTPUT=$(bash "$SCREENSHOT_TOOL" "$URL" \
  --output "$FEATURE_DIR" \
  --label gate6 \
  --full-page \
  --wait 3000 2>&1)
CAPTURE_RC=$?

if [ "$CAPTURE_RC" -ne 0 ]; then
  printf '%s\n' "$CAPTURE_OUTPUT" | tail -10
  # Distinguish "no browser" from "the page is broken" where we can; both
  # leave us without evidence, so neither may masquerade as a visual verdict.
  if printf '%s' "$CAPTURE_OUTPUT" | grep -Fq "Cannot find module 'playwright'"; then
    unverifiable "playwright is not installed (npm install playwright)"
  fi
  unverifiable "screenshot capture failed — no evidence to check (exit $CAPTURE_RC)"
fi
printf '%s\n' "$CAPTURE_OUTPUT" | tail -5

echo ""

# ── Step 2: Verify screenshots exist and aren't blank ──
log "── Step 2: Screenshot integrity ──"

EXPECTED_FILES=("gate6-mobile-375x812.png" "gate6-tablet-768x1024.png" "gate6-desktop-1440x900.png")
BLANK_THRESHOLD=5000  # bytes — a truly blank page is < 5KB

for expected in ${EXPECTED_FILES[@]+"${EXPECTED_FILES[@]}"}; do
  filepath="$FEATURE_DIR/$expected"
  if [ ! -f "$filepath" ]; then
    fail "Missing: $expected"
    continue
  fi

  size=$(stat -c%s "$filepath" 2>/dev/null || stat -f%z "$filepath" 2>/dev/null || echo "0")
  if [ "$size" -lt "$BLANK_THRESHOLD" ]; then
    fail "Likely blank page: $expected ($size bytes — below ${BLANK_THRESHOLD}B threshold)"
  else
    log "  ✅ $expected (${size} bytes)"
  fi
done

echo ""

# ── Step 3: Check for horizontal overflow on mobile ──
log "── Step 3: Mobile overflow check ──"

OVERFLOW_SCRIPT=$(mktemp "${TMPDIR:-/tmp}/sage-overflow-XXXXXX.cjs") || \
  unverifiable "could not create a temporary file"
trap 'rm -f "$OVERFLOW_SCRIPT"' EXIT

cat > "$OVERFLOW_SCRIPT" << 'OFJS'
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

function findChromium() {
  const searchPaths = ['/opt/pw-browsers', process.env.HOME + '/.cache/ms-playwright'];
  for (const base of searchPaths) {
    if (!fs.existsSync(base)) continue;
    const dirs = fs.readdirSync(base).filter(d => d.startsWith('chromium-')).sort().reverse();
    for (const dir of dirs) {
      const chrome = path.join(base, dir, 'chrome-linux', 'chrome');
      if (fs.existsSync(chrome)) return chrome;
    }
  }
  return null;
}

(async () => {
  const url = process.argv[2];
  if (!url) { console.log('NO_URL'); process.exit(1); }

  const execPath = findChromium();
  const launchOpts = { headless: true };
  if (execPath) launchOpts.executablePath = execPath;

  const browser = await chromium.launch(launchOpts);
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  // Collect console errors
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
  } catch {
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 10000 });
    } catch (e) {
      console.log('LOAD_FAILED:' + e.message);
      await browser.close();
      process.exit(1);
    }
  }

  await page.waitForTimeout(2000);

  // Check horizontal overflow
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const viewportWidth = 375;
  const hasOverflow = scrollWidth > viewportWidth + 2; // 2px tolerance

  // Output results as JSON
  const result = {
    overflow: hasOverflow,
    scrollWidth: scrollWidth,
    viewportWidth: viewportWidth,
    consoleErrors: errors.length,
    consoleErrorSamples: errors.slice(0, 3),
  };
  console.log('RESULT:' + JSON.stringify(result));

  await browser.close();
})();
OFJS

PROBE_OUTPUT=$(node "$OVERFLOW_SCRIPT" "$URL" 2>&1)

if printf '%s' "$PROBE_OUTPUT" | grep -Fq "LOAD_FAILED:"; then
  unverifiable "the page could not be loaded: $(printf '%s' "$PROBE_OUTPUT" | sed -n 's/^LOAD_FAILED://p' | head -1)"
fi

RESULT_JSON=$(printf '%s\n' "$PROBE_OUTPUT" | sed -n 's/^RESULT://p' | head -1)

if [ -n "$RESULT_JSON" ]; then
  # One python3 parse instead of four `node -e` subprocesses.
  PARSED=$(printf '%s' "$RESULT_JSON" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(str(d["overflow"]).lower())
print(d["scrollWidth"])
print(d["consoleErrors"])
for s in d.get("consoleErrorSamples", []):
    print("    " + s)
')
  HAS_OVERFLOW=$(printf '%s\n' "$PARSED" | sed -n '1p')
  SCROLL_W=$(printf '%s\n' "$PARSED" | sed -n '2p')
  CONSOLE_ERRORS=$(printf '%s\n' "$PARSED" | sed -n '3p')

  if [ "$HAS_OVERFLOW" = "true" ]; then
    fail "Mobile horizontal overflow detected (scrollWidth: ${SCROLL_W}px > viewport: 375px)"
  else
    log "  ✅ No horizontal overflow (scrollWidth: ${SCROLL_W}px)"
  fi

  if [ "${CONSOLE_ERRORS:-0}" -gt 0 ]; then
    warn "Console errors during page load: $CONSOLE_ERRORS"
    printf '%s\n' "$PARSED" | sed -n '4,$p'
  else
    log "  ✅ No console errors"
  fi
else
  printf '%s\n' "$PROBE_OUTPUT" | tail -5
  unverifiable "the overflow probe produced no result — cannot verify layout"
fi

echo ""

# ── Step 4: Manifest summary ──
log "── Step 4: Evidence summary ──"

MANIFEST="$FEATURE_DIR/gate6-manifest.json"
if [ -f "$MANIFEST" ]; then
  SCREENSHOT_COUNT=$(python3 -c '
import json, sys
try:
    print(len(json.load(open(sys.argv[1]))["screenshots"]))
except Exception:
    print("?")
' "$MANIFEST")
  log "  Screenshots captured: $SCREENSHOT_COUNT"
  log "  Manifest: $MANIFEST"
else
  warn "No manifest file found"
fi

echo ""

# ── Result ──
log "═══ Gate 6 Result ═══"
if [ "$PASS" = true ] && [ "$WARNINGS" -eq 0 ]; then
  log "✅ PASS — Screenshots captured, no automated issues detected"
  log ""
  log "  Next: Run the visual-review skill for AI-based layout/design evaluation"
  log "  Screenshots at: $FEATURE_DIR/"
  exit 0
elif [ "$PASS" = true ]; then
  log "⚠️  PASS WITH WARNINGS — $WARNINGS warning(s), review recommended"
  log ""
  log "  Next: Run the visual-review skill to evaluate screenshots"
  exit 0
else
  log "❌ FAIL — Critical visual issues detected"
  log ""
  log "  Fix the issues above, then re-run this gate"
  exit 1
fi
