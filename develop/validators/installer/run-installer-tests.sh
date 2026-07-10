#!/usr/bin/env bash
# run-installer-tests.sh — tests for install.sh's integrity checks (ADR-3).
#
# Serves a fake release over file:// and drives the real install.sh against it
# via its environment seams (SAGE_VERSION, SAGE_HOME, SAGE_BIN_DIR,
# SAGE_RELEASE_BASE_URL). Nothing touches the developer's ~/.sage.
#
# Usage: bash develop/validators/installer/run-installer-tests.sh
# Exit:  0 = all pass | 1 = a case failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
INSTALLER="$REPO_ROOT/install.sh"

N_PASS=0
N_FAIL=0

ok()   { N_PASS=$((N_PASS + 1)); printf '  [PASS]  %s\n' "$1"; }
bad()  { N_FAIL=$((N_FAIL + 1)); printf '  [FAIL]  %s\n' "$1"; shift
         while [ $# -gt 0 ]; do printf '            %s\n' "$1"; shift; done; }

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  else python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
  fi
}

# ── Build a fake release tree: $1 = root, $2 = "complete" | "no-bin" ──
make_release() {
  local root="$1" shape="${2:-complete}"
  local stage="$root/stage" rel="$root/releases/v9.9.9"
  rm -rf "$root"; mkdir -p "$stage/sage-9.9.9" "$rel"

  mkdir -p "$stage/sage-9.9.9/core" "$stage/sage-9.9.9/skills"
  printf '9.9.9\n' > "$stage/sage-9.9.9/VERSION"
  printf 'placeholder\n' > "$stage/sage-9.9.9/core/keep"
  printf 'placeholder\n' > "$stage/sage-9.9.9/skills/keep"
  if [ "$shape" = "complete" ]; then
    mkdir -p "$stage/sage-9.9.9/bin"
    printf '#!/usr/bin/env bash\necho fixture-sage\n' > "$stage/sage-9.9.9/bin/sage"
  fi

  tar -czf "$rel/sage-9.9.9.tar.gz" -C "$stage" sage-9.9.9
  printf '%s  %s\n' "$(sha256_of "$rel/sage-9.9.9.tar.gz")" "sage-9.9.9.tar.gz" \
    > "$rel/checksums.txt"
}

# Run install.sh from a copy outside any framework tree, so its local-source
# detection does not short-circuit the download path under test.
run_installer() {
  local root="$1"
  local copy="$root/install.sh"
  cp "$INSTALLER" "$copy"
  ( cd "$root" \
    && SAGE_VERSION=v9.9.9 \
       SAGE_HOME="$root/home/.sage" \
       SAGE_BIN_DIR="$root/home/bin" \
       SAGE_RELEASE_BASE_URL="file://$root/releases" \
       bash "$copy" ) > "$root/out.txt" 2>&1
  echo $?
}

echo "═══ Sage installer integrity tests ═══"
echo ""

if ! command -v curl >/dev/null 2>&1; then
  echo "  SKIP — curl is required"
  exit 0
fi

# ── G-installer-1: a good release installs ──
T=$(mktemp -d); make_release "$T"
RC=$(run_installer "$T")
if [ "$RC" -eq 0 ] && [ -f "$T/home/.sage/framework/bin/sage" ] \
   && [ -x "$T/home/bin/sage" ]; then
  ok "G-installer-1  verified release installs"
else
  bad "G-installer-1  verified release installs" "exit=$RC" "$(tail -5 "$T/out.txt")"
fi
if grep -q "Checksum verified" "$T/out.txt" && grep -q "9.9.9" "$T/out.txt"; then
  ok "G-installer-1b announces the verified version"
else
  bad "G-installer-1b announces the verified version" "$(tail -5 "$T/out.txt")"
fi
rm -rf "$T"

# ── G-installer-2: a corrupted tarball aborts before installing ──
T=$(mktemp -d); make_release "$T"
# Flip one byte of the tarball, leaving checksums.txt describing the original.
python3 - "$T/releases/v9.9.9/sage-9.9.9.tar.gz" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
data = bytearray(p.read_bytes())
data[len(data) // 2] ^= 0x01
p.write_bytes(bytes(data))
PY
RC=$(run_installer "$T")
if [ "$RC" -ne 0 ]; then
  ok "G-installer-2  corrupted tarball aborts (exit $RC)"
else
  bad "G-installer-2  corrupted tarball aborts" "installer exited 0"
fi
if grep -q "CHECKSUM MISMATCH" "$T/out.txt"; then
  ok "G-installer-2b names the mismatch loudly"
else
  bad "G-installer-2b names the mismatch loudly" "$(tail -5 "$T/out.txt")"
fi
if [ ! -d "$T/home/.sage/framework" ]; then
  ok "G-installer-2c nothing was installed"
else
  bad "G-installer-2c nothing was installed" "framework dir exists"
fi
rm -rf "$T"

# ── G-installer-3: a corrupted checksums.txt aborts ──
T=$(mktemp -d); make_release "$T"
printf '%s  %s\n' "$(printf 'deadbeef%.0s' 1 2 3 4 5 6 7 8)" "sage-9.9.9.tar.gz" \
  > "$T/releases/v9.9.9/checksums.txt"
RC=$(run_installer "$T")
if [ "$RC" -ne 0 ] && [ ! -d "$T/home/.sage/framework" ]; then
  ok "G-installer-3  wrong digest in checksums.txt aborts pre-install"
else
  bad "G-installer-3  wrong digest in checksums.txt aborts pre-install" "exit=$RC"
fi
rm -rf "$T"

# ── G-installer-4: a missing checksums.txt aborts (never install unverified) ──
T=$(mktemp -d); make_release "$T"
rm -f "$T/releases/v9.9.9/checksums.txt"
RC=$(run_installer "$T")
if [ "$RC" -ne 0 ] && grep -q "unverified" "$T/out.txt" \
   && [ ! -d "$T/home/.sage/framework" ]; then
  ok "G-installer-4  missing checksums.txt aborts"
else
  bad "G-installer-4  missing checksums.txt aborts" "exit=$RC" "$(tail -5 "$T/out.txt")"
fi
rm -rf "$T"

# ── G-installer-5: a structurally broken tarball aborts after verification ──
T=$(mktemp -d); make_release "$T" no-bin
RC=$(run_installer "$T")
if [ "$RC" -ne 0 ] && [ ! -d "$T/home/.sage/framework" ]; then
  ok "G-installer-5  tarball without bin/sage aborts"
else
  bad "G-installer-5  tarball without bin/sage aborts" "exit=$RC"
fi
rm -rf "$T"

# ── G-installer-6: a failed install leaves an existing framework intact ──
T=$(mktemp -d); make_release "$T"
mkdir -p "$T/home/.sage/framework/bin"
printf 'PRIOR INSTALL\n' > "$T/home/.sage/framework/bin/sage"
python3 - "$T/releases/v9.9.9/sage-9.9.9.tar.gz" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
data = bytearray(p.read_bytes())
data[len(data) // 2] ^= 0x01
p.write_bytes(bytes(data))
PY
RC=$(run_installer "$T")
if [ "$RC" -ne 0 ] && grep -q "PRIOR INSTALL" "$T/home/.sage/framework/bin/sage"; then
  ok "G-installer-6  existing framework survives a failed install"
else
  bad "G-installer-6  existing framework survives a failed install" "exit=$RC"
fi
rm -rf "$T"

echo ""
echo "═══ Summary ═══"
printf '  pass %d · fail %d\n' "$N_PASS" "$N_FAIL"
[ "$N_FAIL" -eq 0 ] || exit 1
exit 0
