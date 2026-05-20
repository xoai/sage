#!/usr/bin/env python3
"""
check-bash-arrays.py — lint Sage's shell scripts for bash 3.2-unsafe
empty-array expansions.

Under `set -u`, bash < 4.4 (macOS /bin/bash is 3.2.57) aborts when an
empty array is expanded — it treats the empty expansion as an unbound
variable. This applies to:

  - quoted standalone:   "${arr[@]}"
  - embedded in a string: "  prefix ${arr[*]} suffix"
  - unquoted whole-word:  ${arr[@]}
  - the [*] star form:    "${arr[*]}"

The empty-safe form  ${arr[@]+"${arr[@]}"}  expands to nothing when the
array is empty and behaves identically when non-empty. See CONTRIBUTING.md
"Shell script conventions".

This is a pure-stdlib Python script (no `grep -P` dependency) so it runs
identically on Linux, macOS (BSD userland), and WSL — unlike a
PCRE-grep-based linter, which silently no-ops where `grep -P` is absent.

Usage:   python3 develop/validators/check-bash-arrays.py
Exit:    0 = clean   |   1 = unsafe expansion(s) found   |   2 = bad invocation
"""
from __future__ import annotations

import pathlib
import re
import sys


# ── The unsafe pattern ────────────────────────────────────────────────
# Matches a VALUE expansion of an array element-list:  ${NAME[@]}  or
# ${NAME[*]}  — i.e. the closing `}` comes immediately after the `[@]`
# / `[*]` subscript.
#
# Two negative lookbehinds:
#   (?<!\+")  excludes the *inner* half of the safe form
#             ${NAME[@]+"${NAME[@]}"} — there the inner "${NAME[@]}" is
#             always immediately preceded by `+"`. (The *outer*
#             ${NAME[@]+...} is not matched at all — it has `]+`, not
#             `]}`.)
#   (?<!\\)   excludes an escaped  \${...}  — display text inside an
#             echo, e.g.  echo "... \${a[@]} ..."  — not a real
#             expansion.
#
# Correctly NOT matched (already safe):
#   ${#arr[@]}             — length; `#` breaks the name char class
#   "${arr[@]:-default}"   — `:-default` sits between `]` and `}`
#   ${arr[@]+"${arr[@]}"}  — outer has `]+`; inner excluded by lookbehind
#
# Matched regardless of surrounding quotes, so embedded expansions
# ("text ${arr[*]} text") and unquoted whole-word expansions are both
# caught.
UNSAFE = re.compile(r'(?<!\+")(?<!\\)\$\{([A-Za-z_]\w*)\[([@*])\]\}')

# A line carrying this marker is intentionally exempt — used for the
# deliberate quirk-reproduction payload in bash32-smoke.sh, where an
# unsafe expansion is the thing under test.
SUPPRESS = "# bash-array-ok"


def scan_file(path: pathlib.Path) -> list[tuple[int, str]]:
    """Return [(lineno, line)] for every unsafe expansion. Whole-line
    comments are skipped (the convention docs quote the unsafe pattern
    as illustrative text)."""
    findings: list[tuple[int, str]] = []
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return findings
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        if SUPPRESS in line:
            continue
        if UNSAFE.search(line):
            findings.append((lineno, line))
    return findings


def collect_scripts(repo_root: pathlib.Path) -> list[pathlib.Path]:
    """Every shell script Sage ships or runs: bin/sage (no extension)
    plus every *.sh, excluding vendored / state / cache dirs."""
    EXCLUDE = (".git", ".sage", ".sage-memory", "node_modules", ".pytest_cache")
    out: list[pathlib.Path] = []

    sage_cli = repo_root / "bin" / "sage"
    if sage_cli.is_file():
        out.append(sage_cli)

    for p in sorted(repo_root.rglob("*.sh")):
        rel_parts = p.relative_to(repo_root).parts
        if any(part in EXCLUDE for part in rel_parts):
            continue
        out.append(p)
    return out


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    scripts = collect_scripts(repo_root)
    if not scripts:
        print("ERROR: no shell scripts found to scan", file=sys.stderr)
        return 2

    fail = False
    for path in scripts:
        findings = scan_file(path)
        if findings:
            fail = True
            rel = path.relative_to(repo_root)
            print(f"✗ {rel}")
            for lineno, line in findings:
                print(f"    {lineno}: {line.strip()}")

    print()
    if fail:
        print("FAIL — unsafe empty-array expansion(s) found.")
        print()
        print('Fix: replace  "${arr[@]}"  with  ${arr[@]+"${arr[@]}"}')
        print('     (and the [*] form likewise:  ${arr[*]+"${arr[*]}"})')
        print("Why: macOS /bin/bash is 3.2 and aborts on empty-array")
        print("     expansion under 'set -u'. See CONTRIBUTING.md")
        print("     'Shell script conventions'.")
        return 1

    print(f"OK — {len(scripts)} shell script(s) scanned, "
          "no unsafe empty-array expansions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
