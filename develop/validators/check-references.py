#!/usr/bin/env python3
"""
check-references.py — verify that framework paths named in the prose exist.

Phase 3 relocates and removes a lot of content (templates move, the plugin
mirror goes, skills extract to packs, workflows fold). Every one of those moves
can leave a workflow or skill pointing at a path that no longer exists — a
dangling reference the model then can't follow. This validator is the guard:
run it before AND after each move, and CI runs it on every PR.

Scope: markdown under core/, skills/, and runtime/ (the prose the model reads).
It extracts backtick-quoted tokens that look like framework paths and checks
each resolves to a real file or directory.

A framework path is `[sage/](core|skills|runtime|develop|bin)/...`. The optional
`sage/` prefix is the vendored layout a user project sees; it maps to the repo
root. Runtime project state (`.sage/…`), template placeholders (`{…}`, `<…>`,
`*`, `YYYYMMDD`, `$VAR`), and example paths (`src/`, `app/`) are skipped — they
are not framework files and are not expected to exist in the repo.

A line may be exempted with a trailing `# ref-ok` comment (rare; for a
deliberately illustrative path).

Pure-stdlib. Usage:  python3 develop/validators/check-references.py
Exit: 0 = every reference resolves | 1 = dangling reference(s) | 2 = bad invocation
"""
from __future__ import annotations

import pathlib
import re
import sys

SUPPRESS = "# ref-ok"

# A backtick-quoted token beginning (optionally) with the vendored `sage/`
# prefix, then one of the framework top-level dirs.
REF = re.compile(
    r"`(?P<path>(?:sage/)?(?:core|skills|runtime|develop|bin)/[A-Za-z0-9._/-]+)`"
)

# Tokens that look like paths but are placeholders or non-framework examples.
PLACEHOLDER = re.compile(r"[{}<>*$\[\]]|YYYYMMDD|N/M|\.\.\.")


def looks_dynamic(path: str) -> bool:
    return bool(PLACEHOLDER.search(path))


def normalize(path: str) -> str:
    # The vendored prefix `sage/` maps to the repo root.
    if path.startswith("sage/"):
        path = path[len("sage/"):]
    return path.rstrip("/")


def scan_file(path: pathlib.Path, repo_root: pathlib.Path):
    """Yield (lineno, raw_ref, resolved_rel) for each dangling reference."""
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return
    for lineno, line in enumerate(lines, 1):
        if SUPPRESS in line:
            continue
        for m in REF.finditer(line):
            raw = m.group("path")
            if looks_dynamic(raw):
                continue
            rel = normalize(raw)
            target = repo_root / rel
            if not (target.is_file() or target.is_dir()):
                yield (lineno, raw, rel)


def collect_markdown(repo_root: pathlib.Path):
    EXCLUDE = (".git", ".sage", ".sage-memory", "node_modules", ".pytest_cache",
               "dist")
    out = []
    for base in ("core", "skills", "runtime"):
        root = repo_root / base
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.md")):
            if any(part in EXCLUDE for part in p.relative_to(repo_root).parts):
                continue
            out.append(p)
    return out


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    files = collect_markdown(repo_root)
    if not files:
        print("ERROR: no markdown found to scan", file=sys.stderr)
        return 2

    fail = False
    checked = 0
    for f in files:
        findings = list(scan_file(f, repo_root))
        checked += 1
        if not findings:
            continue
        fail = True
        print(f"✗ {f.relative_to(repo_root)}")
        for lineno, raw, rel in findings:
            print(f"    {lineno}: `{raw}` → {rel} (not found)")

    print()
    if fail:
        print("FAIL — dangling framework reference(s).")
        print("  A referenced path does not exist. If a file moved, update the")
        print("  reference; if the path is illustrative, add a trailing `# ref-ok`.")
        return 1

    print(f"OK — {checked} markdown file(s) scanned, every framework reference resolves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
