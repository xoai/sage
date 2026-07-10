#!/usr/bin/env python3
"""
check-portability.py — lint Sage's shell scripts for GNU-only constructs
that behave differently, or not at all, under BSD userland (macOS).

Sage's CI runs on Linux with GNU coreutils and a real bash:3.2 container,
which together catch *bash version* problems. Neither catches *userland*
problems: a Linux container still has GNU grep and GNU sed. macOS has
neither. This linter is the guard for that gap.

The failure mode is silence, not an error. `grep -oP` on macOS prints
"grep: invalid option -- P" to stderr, and a script that redirects stderr to
/dev/null simply sees no matches — so the check it was performing quietly
examines nothing and reports success. That is exactly how Gate 4 shipped a
fail-open hallucination check (01-analysis §2.1, root cause B).

Rules:
  SC01  grep -P / --perl-regexp   → use POSIX classes, or python3 for PCRE
  SC02  sed -i without a suffix   → use `sed -i.bak … && rm -f …bak`
  SC03  mapfile / readarray       → bash 4; use `while read` or a temp file
  SC04  declare -A (assoc arrays) → bash 4; use parallel arrays or python3
  SC05  ${var^^} / ${var,,}       → bash 4; use tr or awk
  SC06  date %N (nanoseconds)     → BSD date prints a literal "N"
  SC07  readlink -f               → BSD readlink has no -f; use a cd/pwd pair

A line may be exempted with a trailing `# portability-ok: <reason>` comment,
or by that marker on the line immediately above. A waiver must state why the
line is genuinely portable — it is not a deferral mechanism.

Pure-stdlib Python (no `grep -P` dependency, naturally) so it runs
identically on Linux, macOS, and WSL.

Usage:   python3 develop/validators/check-portability.py
Exit:    0 = clean   |   1 = GNU-only construct(s) found   |   2 = bad invocation
"""
from __future__ import annotations

import pathlib
import re
import sys

SUPPRESS = "# portability-ok"

# ── Rules ─────────────────────────────────────────────────────────────
# Each: (id, compiled pattern, what's wrong, what to do instead)
RULES = [
    (
        "SC01",
        # `grep`, then short-option clusters, until one contains P. Matches
        # -P, -oP, -qP, -coP, and the long form. Avoids matching a -P that
        # belongs to some other command by anchoring on the grep word.
        re.compile(r"\bgrep\b(?:\s+-[A-Za-z]*\b)*?\s+-[A-Za-z]*P|\bgrep\b[^\n|;&]*--perl-regexp"),
        "grep -P is GNU-only; BSD and BusyBox grep reject it",
        "use POSIX character classes ([[:digit:]]), or move the match into python3",
    ),
    (
        "SC02",
        # GNU: `sed -i 's/…'`. BSD: `sed -i '' 's/…'`. The portable spelling
        # that both accept is an attached suffix: `sed -i.bak`.
        re.compile(r"\bsed\b[^\n|;&]*\s-i(?:\s|$|'')"),
        "sed -i without an attached suffix means different things on GNU and BSD",
        "use `sed -i.bak … && rm -f ….bak`, or write to a temp file",
    ),
    (
        "SC03",
        re.compile(r"\b(?:mapfile|readarray)\b"),
        "mapfile/readarray are bash 4; macOS /bin/bash is 3.2",
        "use `while IFS= read -r line; do …; done < <(cmd)`",
    ),
    (
        "SC04",
        re.compile(r"\b(?:declare|local|typeset)\s+-[A-Za-z]*A\b"),
        "associative arrays are bash 4; macOS /bin/bash is 3.2",
        "use parallel indexed arrays, or move the logic into python3",
    ),
    (
        "SC05",
        re.compile(r"\$\{[A-Za-z_]\w*(?:\[[^\]]*\])?(?:\^\^?|,,?)\}"),
        "${var^^} / ${var,,} case modification is bash 4",
        "use `tr '[:lower:]' '[:upper:]'` or awk toupper()",
    ),
    (
        "SC06",
        re.compile(r"\bdate\b[^\n|;&]*%N"),
        "BSD date has no %N; it prints a literal 'N' rather than failing",
        "use python3 for sub-second timing, or accept whole seconds",
    ),
    (
        "SC07",
        re.compile(r"\breadlink\s+-f\b"),
        "readlink -f is GNU-only; BSD readlink has no -f",
        'use `cd "$(dirname "$x")" && pwd`',
    ),
]


def scan_file(path: pathlib.Path) -> list[tuple[int, str, str, str, str]]:
    """Return [(lineno, rule_id, line, problem, remedy)] for each violation.

    Whole-line comments are skipped: the convention docs and the gate scripts
    quote these constructs as illustrative text explaining why they are gone.
    """
    findings: list[tuple[int, str, str, str, str]] = []
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return findings

    for lineno, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        if SUPPRESS in line:
            continue
        # A waiver may sit on the line above, where a trailing comment would
        # not fit or would obscure the code.
        if lineno >= 2 and SUPPRESS in lines[lineno - 2]:
            continue
        for rule_id, pattern, problem, remedy in RULES:
            if pattern.search(line):
                findings.append((lineno, rule_id, line, problem, remedy))
    return findings


def collect_scripts(repo_root: pathlib.Path) -> list[pathlib.Path]:
    """Every shell script Sage ships or runs: bin/sage (no extension) plus
    every *.sh, excluding vendored / state / cache dirs."""
    EXCLUDE = (".git", ".sage", ".sage-memory", "node_modules", ".pytest_cache")
    out: list[pathlib.Path] = []

    sage_cli = repo_root / "bin" / "sage"
    if sage_cli.is_file():
        out.append(sage_cli)

    for p in sorted(repo_root.rglob("*.sh")):
        if any(part in EXCLUDE for part in p.relative_to(repo_root).parts):
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
    seen_rules = set()
    for path in scripts:
        findings = scan_file(path)
        if not findings:
            continue
        fail = True
        print(f"✗ {path.relative_to(repo_root)}")
        for lineno, rule_id, line, problem, _remedy in findings:
            seen_rules.add(rule_id)
            print(f"    {lineno}: [{rule_id}] {line.strip()}")
            print(f"        {problem}")

    print()
    if fail:
        print("FAIL — GNU-only construct(s) found.")
        print()
        for rule_id, _pattern, problem, remedy in RULES:
            if rule_id in seen_rules:
                print(f"  [{rule_id}] {problem}")
                print(f"         fix: {remedy}")
        print()
        print("Why: these fail silently under BSD userland (macOS), where a")
        print("     redirected stderr turns 'invalid option' into 'no matches'.")
        print("     A line that is genuinely portable may carry a trailing")
        print(f"     `{SUPPRESS}: <reason>` comment.")
        return 1

    print(f"OK — {len(scripts)} shell script(s) scanned, no GNU-only constructs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
