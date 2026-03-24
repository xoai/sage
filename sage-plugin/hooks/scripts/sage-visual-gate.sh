#!/usr/bin/env bash
# sage-visual-gate.sh — Deterministic visual checks for Gate 6
# Captures screenshots, then runs automated checks that don't require AI judgment.
# AI-based visual review (layout, hierarchy, aesthetics) is done by the visual-review skill.
#
# Usage: bash sage/core/gates/scripts/sage-visual-gate.sh <url> [feature-dir]
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
SAGE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PASS=true
WARNINGS=0

log()  { echo "$1"; }
warn() { log "⚠️  $1"; WARNINGS=$((WARNINGS + 1)); }
fail() { log "❌ $1"; PASS=false; }

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

mkdir -p "$FEATURE_DIR"

# ── Step 1: Capture screenshots ──
log "── Step 1: Capturing screenshots ──"

SCREENSHOT_TOOL="$SAGE_ROOT/runtime/tools/sage-screenshot.sh"
if [ ! -f "$SCREENSHOT_TOOL" ]; then
  # Try relative to gate script location
  SCREENSHOT_TOOL="$(cd "$SCRIPT_DIR/../../../runtime/tools" 2>/dev/null && pwd)/sage-screenshot.sh"
fi

if [ ! -f "$SCREENSHOT_TOOL" ]; then
  fail "Screenshot tool not found at $SCREENSHOT_TOOL"
  log ""
  log "═══ Gate 6 Result ═══"
  log "❌ FAIL — Screenshot tool missing"
  exit 1
fi

bash "$SCREENSHOT_TOOL" "$URL" \
  --output "$FEATURE_DIR" \
  --label gate6 \
  --full-page \
  --wait 3000 2>&1

if [ $? -ne 0 ]; then
  fail "Screenshot capture failed"
fi

echo ""

# ── Step 2: Verify screenshots exist and aren't blank ──
log "── Step 2: Screenshot integrity ──"

EXPECTED_FILES=("gate6-mobile-375x812.png" "gate6-tablet-768x1024.png" "gate6-desktop-1440x900.png")
BLANK_THRESHOLD=5000  # bytes — a truly blank page is < 5KB

for expected in "${EXPECTED_FILES[@]}"; do
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

# Generate a small Playwright script that checks if page is wider than viewport
OVERFLOW_SCRIPT=$(mktemp /tmp/sage-overflow-XXXX.cjs)
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

OVERFLOW_OUTPUT=$(node "$OVERFLOW_SCRIPT" "$URL" 2>&1 | grep "^RESULT:" | sed 's/RESULT://')
rm -f "$OVERFLOW_SCRIPT"

if [ -n "$OVERFLOW_OUTPUT" ]; then
  HAS_OVERFLOW=$(echo "$OVERFLOW_OUTPUT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.overflow)" 2>/dev/null)
  SCROLL_W=$(echo "$OVERFLOW_OUTPUT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.scrollWidth)" 2>/dev/null)
  CONSOLE_ERRORS=$(echo "$OVERFLOW_OUTPUT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.consoleErrors)" 2>/dev/null)

  if [ "$HAS_OVERFLOW" = "true" ]; then
    fail "Mobile horizontal overflow detected (scrollWidth: ${SCROLL_W}px > viewport: 375px)"
  else
    log "  ✅ No horizontal overflow (scrollWidth: ${SCROLL_W}px)"
  fi

  if [ "${CONSOLE_ERRORS:-0}" -gt 0 ]; then
    warn "Console errors during page load: $CONSOLE_ERRORS"
    SAMPLES=$(echo "$OVERFLOW_OUTPUT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); d.consoleErrorSamples.forEach(e=>console.log('    '+e))" 2>/dev/null)
    [ -n "$SAMPLES" ] && echo "$SAMPLES"
  else
    log "  ✅ No console errors"
  fi
else
  warn "Could not run overflow check (page may not be accessible)"
fi

echo ""

# ── Step 4: Manifest summary ──
log "── Step 4: Evidence summary ──"

MANIFEST="$FEATURE_DIR/gate6-manifest.json"
if [ -f "$MANIFEST" ]; then
  SCREENSHOT_COUNT=$(node -e "const m=JSON.parse(require('fs').readFileSync('$MANIFEST','utf8')); console.log(m.screenshots.length)" 2>/dev/null || echo "?")
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
