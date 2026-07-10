#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage Installer
#
# Remote install (from GitHub):
#   curl -fsSL https://raw.githubusercontent.com/xoai/sage/main/install.sh | bash
#
# Local install (from cloned/extracted repo):
#   bash install.sh
#
# What it does:
#   1. Resolves the latest release tag (or $SAGE_VERSION)
#   2. Downloads the release tarball and checksums.txt
#   3. Verifies the SHA-256 — aborts on mismatch, before touching anything
#   4. Unpacks it to ~/.sage/framework/
#   5. Creates the 'sage' command at ~/.local/bin/sage
#
# It used to `git clone` main, unverified. A compromised or mid-push main
# landed straight in ~/.sage/framework and, from there, into every project on
# its next `sage update` (ADR-3).
#
# Environment overrides (also the seams the installer tests drive):
#   SAGE_VERSION           pin a tag, e.g. v1.1.11
#   SAGE_HOME              install root (default ~/.sage)
#   SAGE_BIN_DIR           CLI location (default ~/.local/bin)
#   SAGE_RELEASE_BASE_URL  where tarballs live
#   SAGE_API_URL           where the latest tag is resolved from
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[32m'
YELLOW='\033[33m'
CYAN='\033[36m'
RED='\033[31m'
DIM='\033[2m'
RESET='\033[0m'

SAGE_HOME="${SAGE_HOME:-$HOME/.sage}"
SAGE_FRAMEWORK="$SAGE_HOME/framework"
BIN_DIR="${SAGE_BIN_DIR:-$HOME/.local/bin}"
SAGE_REPO="xoai/sage"
SAGE_API_URL="${SAGE_API_URL:-https://api.github.com/repos/$SAGE_REPO/releases/latest}"
SAGE_RELEASE_BASE_URL="${SAGE_RELEASE_BASE_URL:-https://github.com/$SAGE_REPO/releases/download}"

TMPDIR_SAGE=""
cleanup() { [ -n "$TMPDIR_SAGE" ] && rm -rf "$TMPDIR_SAGE"; }
trap cleanup EXIT

have() { command -v "$1" >/dev/null 2>&1; }

die() {
  echo ""
  echo -e "  ${RED}❌ $1${RESET}"
  shift
  while [ $# -gt 0 ]; do echo "  $1"; shift; done
  echo ""
  exit 1
}

echo ""
echo -e "  ${BOLD}Sage Installer${RESET}"
echo ""

# ── Detect a local source (running from inside an extracted repo) ──
LOCAL_SOURCE=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/bin/sage" ] && [ -d "$SCRIPT_DIR/core" ]; then
  LOCAL_SOURCE="$SCRIPT_DIR"
fi

# ── Verify a downloaded tarball against checksums.txt ──
# Prefer the platform's own tool; fall back to python3. Never skip.
verify_checksum() {
  local dir="$1"
  if have sha256sum; then
    ( cd "$dir" && sha256sum -c checksums.txt >/dev/null 2>&1 )
  elif have shasum; then
    ( cd "$dir" && shasum -a 256 -c checksums.txt >/dev/null 2>&1 )
  elif have python3; then
    python3 - "$dir" <<'PY'
import hashlib, pathlib, sys
d = pathlib.Path(sys.argv[1])
ok = True
for line in (d / "checksums.txt").read_text().splitlines():
    if not line.strip():
        continue
    expected, name = line.split()[0], line.split()[-1]
    actual = hashlib.sha256((d / name).read_bytes()).hexdigest()
    ok = ok and actual == expected
sys.exit(0 if ok else 1)
PY
  else
    die "No SHA-256 tool found (sha256sum, shasum, or python3)." \
        "Refusing to install an unverified download."
  fi
}

resolve_latest_tag() {
  local json
  json="$(curl -fsSL "$SAGE_API_URL" 2>/dev/null)" || return 1
  if have python3; then
    printf '%s' "$json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])' 2>/dev/null
  else
    printf '%s' "$json" \
      | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
  fi
}

# ── Install framework ──
if [ -n "$LOCAL_SOURCE" ]; then
  echo -e "  ${GREEN}Found local Sage at:${RESET} $LOCAL_SOURCE"
  echo -e "  ${DIM}Local source — no checksum to verify against.${RESET}"
  mkdir -p "$SAGE_HOME"
  rm -rf "$SAGE_FRAMEWORK"
  cp -a "$LOCAL_SOURCE" "$SAGE_FRAMEWORK"
  echo -e "  ${GREEN}✓${RESET} Sage installed to $SAGE_FRAMEWORK"

else
  have curl || die "curl is required to download Sage." \
                   "Install curl, or download the release manually from" \
                   "  https://github.com/$SAGE_REPO/releases" \
                   "extract it, and run: bash install.sh"
  have tar || die "tar is required to unpack Sage."

  TAG="${SAGE_VERSION:-}"
  if [ -z "$TAG" ]; then
    echo "  Resolving the latest release..."
    TAG="$(resolve_latest_tag || true)"
    [ -n "$TAG" ] || die "Could not resolve the latest release tag." \
      "Check your network, or pin one explicitly:" \
      "  SAGE_VERSION=v1.1.11 bash install.sh"
  fi
  VER="${TAG#v}"

  TMPDIR_SAGE="$(mktemp -d "${TMPDIR:-/tmp}/sage-install-XXXXXX")"
  TARBALL="sage-$VER.tar.gz"
  BASE="$SAGE_RELEASE_BASE_URL/$TAG"

  echo "  Downloading Sage $TAG..."
  curl -fsSL -o "$TMPDIR_SAGE/$TARBALL" "$BASE/$TARBALL" \
    || die "Download failed: $BASE/$TARBALL" \
           "Does that release exist? https://github.com/$SAGE_REPO/releases"
  curl -fsSL -o "$TMPDIR_SAGE/checksums.txt" "$BASE/checksums.txt" \
    || die "Could not download checksums.txt for $TAG." \
           "Refusing to install an unverified download."

  echo "  Verifying SHA-256..."
  if ! verify_checksum "$TMPDIR_SAGE"; then
    die "CHECKSUM MISMATCH for $TARBALL." \
        "The download does not match the checksum published for $TAG." \
        "This means the file was corrupted in transit — or tampered with." \
        "" \
        "Nothing has been installed. Your existing Sage is untouched." \
        "Report this at https://github.com/$SAGE_REPO/issues"
  fi
  echo -e "  ${GREEN}✓${RESET} Checksum verified"

  tar -xzf "$TMPDIR_SAGE/$TARBALL" -C "$TMPDIR_SAGE" \
    || die "Could not unpack $TARBALL."

  UNPACKED="$TMPDIR_SAGE/sage-$VER"
  if [ ! -f "$UNPACKED/bin/sage" ] || [ ! -d "$UNPACKED/core" ] || [ ! -d "$UNPACKED/skills" ]; then
    die "The release tarball is missing bin/sage, core/ or skills/." \
        "Nothing has been installed."
  fi

  # Swap only after everything above succeeded, so a failed install never
  # leaves a half-written framework behind.
  mkdir -p "$SAGE_HOME"
  if [ -d "$SAGE_FRAMEWORK" ]; then
    rm -rf "$SAGE_FRAMEWORK.previous"
    mv "$SAGE_FRAMEWORK" "$SAGE_FRAMEWORK.previous"
  fi
  mv "$UNPACKED" "$SAGE_FRAMEWORK"
  rm -rf "$SAGE_FRAMEWORK.previous"
  echo -e "  ${GREEN}✓${RESET} Sage $TAG installed to $SAGE_FRAMEWORK"
fi

# ── Validate installation ──
if [ ! -f "$SAGE_FRAMEWORK/bin/sage" ]; then
  rm -rf "$SAGE_FRAMEWORK"
  die "Installation failed — $SAGE_FRAMEWORK/bin/sage does not exist."
fi
if [ ! -d "$SAGE_FRAMEWORK/core" ] || [ ! -d "$SAGE_FRAMEWORK/skills" ]; then
  rm -rf "$SAGE_FRAMEWORK"
  die "Installation incomplete — core/ or skills/ is missing."
fi

# ── Install CLI ──
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/sage" << CLIEOF
#!/usr/bin/env bash
# Sage CLI wrapper — forwards to the framework's bin/sage
SAGE_BIN="$SAGE_FRAMEWORK/bin/sage"
if [ ! -f "\$SAGE_BIN" ]; then
  echo "Error: Sage framework not found at $SAGE_FRAMEWORK"
  echo "Reinstall: curl -fsSL https://raw.githubusercontent.com/$SAGE_REPO/main/install.sh | bash"
  exit 1
fi
exec bash "\$SAGE_BIN" "\$@"
CLIEOF
chmod +x "$BIN_DIR/sage"
echo -e "  ${GREEN}✓${RESET} CLI installed at $BIN_DIR/sage"

# ── Check PATH ──
PATH_OK=false
if echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR" 2>/dev/null; then
  PATH_OK=true
fi

# ── Success ──
INSTALLED_VERSION="unknown"
[ -f "$SAGE_FRAMEWORK/VERSION" ] && INSTALLED_VERSION="$(tr -d ' \t\n\r' < "$SAGE_FRAMEWORK/VERSION")"

echo ""
echo -e "  ${BOLD}╔═══════════════════════════════════════╗${RESET}"
echo -e "  ${BOLD}║        Sage Installed                ║${RESET}"
echo -e "  ${BOLD}╚═══════════════════════════════════════╝${RESET}"
echo ""
echo -e "  Version: ${CYAN}${INSTALLED_VERSION}${RESET}"
echo ""
echo "  Create a project:"
echo -e "    ${CYAN}sage new my-app${RESET}"
echo ""
echo "  Or add Sage to an existing project:"
echo -e "    ${CYAN}cd your-project && sage init${RESET}"
echo ""

if [ "$PATH_OK" = false ]; then
  echo -e "  ${YELLOW}Note:${RESET} $BIN_DIR is not in your PATH."
  echo "  Add it by running:"
  echo ""
  if [ -f "$HOME/.zshrc" ]; then
    echo "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
  elif [ -f "$HOME/.bashrc" ]; then
    echo "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
  else
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
  fi
  echo ""
fi
