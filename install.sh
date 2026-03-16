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
#   1. Copies Sage framework to ~/.sage/framework/
#   2. Creates the 'sage' command at ~/.local/bin/sage
#   3. That's it.
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[32m'
YELLOW='\033[33m'
CYAN='\033[36m'
RED='\033[31m'
DIM='\033[2m'
RESET='\033[0m'

SAGE_HOME="$HOME/.sage"
SAGE_FRAMEWORK="$SAGE_HOME/framework"
SAGE_REPO="https://github.com/xoai/sage.git"
BIN_DIR="$HOME/.local/bin"

echo ""
echo -e "  ${BOLD}Sage Installer${RESET}"
echo ""

# ── Detect if running locally (from inside the framework) ──
LOCAL_SOURCE=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/bin/sage" ] && [ -d "$SCRIPT_DIR/core" ]; then
  LOCAL_SOURCE="$SCRIPT_DIR"
  echo -e "  ${GREEN}Found local Sage at:${RESET} $LOCAL_SOURCE"
fi

# ── Install framework ──
if [ -n "$LOCAL_SOURCE" ]; then
  # Local install — copy from local source
  echo "  Installing from local source..."
  mkdir -p "$SAGE_HOME"
  rm -rf "$SAGE_FRAMEWORK"
  cp -a "$LOCAL_SOURCE" "$SAGE_FRAMEWORK"
  echo -e "  ${GREEN}✓${RESET} Sage installed to ~/.sage/framework/"

elif command -v git &>/dev/null; then
  # Remote install — clone from GitHub
  if [ -d "$SAGE_FRAMEWORK/.git" ]; then
    echo "  Updating Sage..."
    if (cd "$SAGE_FRAMEWORK" && git pull --ff-only -q 2>/dev/null); then
      echo -e "  ${GREEN}✓${RESET} Sage updated"
    else
      echo -e "  ${YELLOW}Pull failed. Re-cloning...${RESET}"
      rm -rf "$SAGE_FRAMEWORK"
      git clone -q "$SAGE_REPO" "$SAGE_FRAMEWORK"
      echo -e "  ${GREEN}✓${RESET} Sage re-cloned"
    fi
  else
    echo "  Downloading Sage from GitHub..."
    mkdir -p "$SAGE_HOME"
    rm -rf "$SAGE_FRAMEWORK"
    git clone -q "$SAGE_REPO" "$SAGE_FRAMEWORK"
    echo -e "  ${GREEN}✓${RESET} Sage downloaded"
  fi

else
  echo -e "  ${RED}❌ Cannot install Sage.${RESET}"
  echo ""
  echo "  Either:"
  echo "    • Install git (https://git-scm.com/downloads) and re-run this script"
  echo "    • Download Sage manually from https://github.com/xoai/sage"
  echo "      Extract it, then run: bash install.sh"
  exit 1
fi

# ── Validate installation ──
if [ ! -f "$SAGE_FRAMEWORK/bin/sage" ]; then
  echo ""
  echo -e "  ${RED}❌ Installation failed.${RESET}"
  echo ""
  echo "  Expected to find: ~/.sage/framework/bin/sage"
  echo "  But the file doesn't exist."
  echo ""
  if [ -z "$LOCAL_SOURCE" ]; then
    echo "  This usually means the GitHub repo is empty or has"
    echo "  the wrong structure. Check:"
    echo "    https://github.com/xoai/sage"
    echo ""
    echo "  The repo root should contain bin/, core/, skills/, etc."
    echo "  Not a nested sage/ folder."
  fi
  # Clean up failed install
  rm -rf "$SAGE_FRAMEWORK"
  exit 1
fi

if [ ! -d "$SAGE_FRAMEWORK/core" ] || [ ! -d "$SAGE_FRAMEWORK/skills" ]; then
  echo ""
  echo -e "  ${RED}❌ Installation incomplete.${RESET}"
  echo "  Framework downloaded but core/ or skills/ is missing."
  echo "  Try re-running the installer."
  rm -rf "$SAGE_FRAMEWORK"
  exit 1
fi

# ── Install CLI ──
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/sage" << 'CLIEOF'
#!/usr/bin/env bash
# Sage CLI wrapper — forwards to the framework's bin/sage
SAGE_BIN="$HOME/.sage/framework/bin/sage"
if [ ! -f "$SAGE_BIN" ]; then
  echo "Error: Sage framework not found at ~/.sage/framework/"
  echo "Reinstall: curl -fsSL https://raw.githubusercontent.com/xoai/sage/main/install.sh | bash"
  exit 1
fi
exec bash "$SAGE_BIN" "$@"
CLIEOF

chmod +x "$BIN_DIR/sage"
echo -e "  ${GREEN}✓${RESET} CLI installed at ~/.local/bin/sage"

# ── Check PATH ──
PATH_OK=false
if echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR" 2>/dev/null; then
  PATH_OK=true
fi

# ── Success ──
echo ""
echo -e "  ${BOLD}╔═══════════════════════════════════════╗${RESET}"
echo -e "  ${BOLD}║        Sage Installed                ║${RESET}"
echo -e "  ${BOLD}╚═══════════════════════════════════════╝${RESET}"
echo ""
echo "  Create a project:"
echo -e "    ${CYAN}sage new my-app${RESET}"
echo ""
echo "  Or add Sage to an existing project:"
echo -e "    ${CYAN}cd your-project && sage init${RESET}"
echo ""

if [ "$PATH_OK" = false ]; then
  echo -e "  ${YELLOW}Note:${RESET} ~/.local/bin is not in your PATH."
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
