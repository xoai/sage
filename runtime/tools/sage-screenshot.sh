#!/usr/bin/env bash
# ╔═══════════════════════════════════════════════════════════╗
# ║  sage-screenshot.sh — Capture screenshots at breakpoints ║
# ║                                                           ║
# ║  Deterministic visual evidence capture. Takes a URL,      ║
# ║  screenshots at mobile/tablet/desktop, saves to .sage/.  ║
# ║                                                           ║
# ║  Usage:                                                   ║
# ║    bash sage-screenshot.sh <url> [options]               ║
# ║                                                           ║
# ║  Options:                                                 ║
# ║    --output <dir>     Output directory (default: cwd)     ║
# ║    --label <name>     Filename prefix (default: screenshot)║
# ║    --full-page        Capture full scrollable page        ║
# ║    --breakpoints <s>  Comma-separated widths              ║
# ║                       (default: 375,768,1440)             ║
# ║    --wait <ms>        Wait after load (default: 2000)     ║
# ║    --before           Save as "before" snapshots          ║
# ║    --after            Save as "after" snapshots           ║
# ╚═══════════════════════════════════════════════════════════╝
set -euo pipefail

URL=""
OUTPUT_DIR="."
LABEL="screenshot"
FULL_PAGE="false"
BREAKPOINTS="375,768,1440"
WAIT_MS="2000"
PHASE=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --output)     OUTPUT_DIR="$2"; shift 2 ;;
    --label)      LABEL="$2"; shift 2 ;;
    --full-page)  FULL_PAGE="true"; shift ;;
    --breakpoints) BREAKPOINTS="$2"; shift 2 ;;
    --wait)       WAIT_MS="$2"; shift 2 ;;
    --before)     PHASE="before"; shift ;;
    --after)      PHASE="after"; shift ;;
    --help|-h)
      echo "Usage: bash sage-screenshot.sh <url> [--output dir] [--label name]"
      echo "       [--full-page] [--breakpoints 375,768,1440] [--wait 2000]"
      echo "       [--before|--after]"
      exit 0 ;;
    *)
      if [ -z "$URL" ]; then URL="$1"; else echo "Unknown arg: $1"; exit 1; fi
      shift ;;
  esac
done

if [ -z "$URL" ]; then
  echo "❌ No URL provided"
  echo "Usage: bash sage-screenshot.sh <url> [options]"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "═══ Sage Screenshot Capture ═══"
echo "  URL: $URL"
echo "  Breakpoints: $BREAKPOINTS"
echo "  Full page: $FULL_PAGE"
echo "  Output: $OUTPUT_DIR"
[ -n "$PHASE" ] && echo "  Phase: $PHASE"
echo ""

# Generate the Playwright script
SCRIPT=$(mktemp /tmp/sage-screenshot-XXXX.cjs)

cat > "$SCRIPT" << 'PLAYWRIGHT'
const { chromium } = require('playwright');

// Detect chromium executable — handle version mismatches
function findChromium() {
  const fs = require('fs');
  const path = require('path');
  const searchPaths = [
    '/opt/pw-browsers',
    process.env.HOME + '/.cache/ms-playwright',
  ];
  for (const base of searchPaths) {
    if (!fs.existsSync(base)) continue;
    const dirs = fs.readdirSync(base).filter(d => d.startsWith('chromium-')).sort().reverse();
    for (const dir of dirs) {
      const chrome = path.join(base, dir, 'chrome-linux', 'chrome');
      if (fs.existsSync(chrome)) return chrome;
    }
  }
  return null; // fallback to playwright default
}

PLAYWRIGHT

cat >> "$SCRIPT" << PLAYWRIGHT
const url = '${URL}';
const outputDir = '${OUTPUT_DIR}';
const label = '${LABEL}';
const fullPage = ${FULL_PAGE};
const breakpoints = '${BREAKPOINTS}'.split(',').map(Number);
const waitMs = ${WAIT_MS};
const phase = '${PHASE}';

const viewports = {
  375:  { width: 375,  height: 812,  name: 'mobile' },
  390:  { width: 390,  height: 844,  name: 'mobile' },
  414:  { width: 414,  height: 896,  name: 'mobile-lg' },
  768:  { width: 768,  height: 1024, name: 'tablet' },
  1024: { width: 1024, height: 768,  name: 'tablet-lg' },
  1280: { width: 1280, height: 800,  name: 'laptop' },
  1440: { width: 1440, height: 900,  name: 'desktop' },
  1920: { width: 1920, height: 1080, name: 'desktop-xl' },
};

(async () => {
  const execPath = findChromium();
  const launchOpts = { headless: true };
  if (execPath) launchOpts.executablePath = execPath;
  const browser = await chromium.launch(launchOpts);
  const results = [];

  for (const bp of breakpoints) {
    const vp = viewports[bp] || { width: bp, height: Math.round(bp * 0.75), name: 'w' + bp };
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: bp <= 414 ? 2 : 1,
    });
    const page = await context.newPage();

    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    } catch {
      // Fall back to domcontentloaded if networkidle times out
      try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
      } catch (e) {
        console.error('Failed to load ' + url + ' at ' + bp + 'px: ' + e.message);
        await context.close();
        continue;
      }
    }

    // Wait for animations/lazy images
    await page.waitForTimeout(waitMs);

    // Build filename
    const suffix = phase ? '-' + phase : '';
    const filename = label + '-' + vp.name + '-' + vp.width + 'x' + vp.height + suffix + '.png';
    const filepath = outputDir + '/' + filename;

    await page.screenshot({
      path: filepath,
      fullPage: fullPage,
    });

    results.push({ breakpoint: bp, name: vp.name, file: filename, width: vp.width, height: vp.height });
    console.log('  ✅ ' + filename + ' (' + vp.width + 'x' + vp.height + (fullPage ? ' full-page' : '') + ')');

    await context.close();
  }

  await browser.close();

  // Write manifest
  const manifest = {
    url: url,
    timestamp: new Date().toISOString(),
    phase: phase || 'capture',
    fullPage: fullPage,
    screenshots: results,
  };
  const manifestPath = outputDir + '/' + label + '-manifest.json';
  const fs = require('fs');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log('  ✅ ' + label + '-manifest.json');
})();
PLAYWRIGHT

# Run it
node "$SCRIPT" 2>&1
EXIT_CODE=$?

rm -f "$SCRIPT"

echo ""
if [ $EXIT_CODE -eq 0 ]; then
  COUNT=$(ls "$OUTPUT_DIR"/${LABEL}-*.png 2>/dev/null | wc -l)
  echo "═══ Done: $COUNT screenshots captured ═══"
else
  echo "❌ Screenshot capture failed (exit: $EXIT_CODE)"
fi

exit $EXIT_CODE
