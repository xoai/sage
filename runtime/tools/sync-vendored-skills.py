#!/usr/bin/env python3
"""
sync-vendored-skills.py — refresh sage's vendored fallback skills from
the sage-memory wheel.

Run this when sage-memory ships a new release. The vendored fallback at
`skills/sage-{memory,ontology,self-learning}/` and the plugin mirror
at `tools/sage-claude-plugin/skills/sage-{memory,ontology,self-learning}/`
serves users without the sage-memory MCP package installed — and needs
manual refresh whenever the canonical wheel content changes.

Usage:
    runtime/tools/sync-vendored-skills.py [--from PATH]

Default source: sibling repo at ../sage-memory/. Override with --from
or the SAGE_MEMORY_SRC environment variable.

What it does:
    1. Copies SKILL.md + references/ + scripts/ from the wheel to both
       canonical (skills/) and plugin-mirror locations.
    2. Re-injects sage's fallback comment header after each SKILL.md's
       frontmatter.
    3. Patches upstream prose stragglers where the wheel still has
       "the memory skill" / "the ontology skill" / "self-learning skill"
       without the sage- prefix (sage-memory <= 0.10.0).
    4. Verifies frontmatter, fallback headers, and absence of stale
       prose. Returns non-zero if any check fails.

Exit codes:
    0  success
    1  verification failure or file I/O error
    2  bad invocation
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


# Comment block re-injected at the top of every vendored SKILL.md.
# Distinct from any wheel content; idempotent (skipped if already present).
FALLBACK_HEADER = """\
<!--
  Fallback copy — sage's vendored prose for users without the
  sage-memory MCP package installed.

  Canonical version: ships with sage-memory >= 0.8.0 and is deployed
  automatically by `sage update` (which runs `sage-memory
  install-skills` when the package is present). Edits here only
  affect users who don't have sage-memory installed.

  To override locally for everyone: create a project-level skill
  under .claude/skills/ with a different name.
-->"""


SKILLS = ("sage-memory", "sage-ontology", "sage-self-learning")


# Prose-rename fixes for upstream stragglers. sage-memory 0.10.0 still
# has these in `sage-self-learning/references/{team-sharing,ontology-
# integration,review-workflow}.md`. Until upstream cleans up, the
# script re-applies them every sync to keep the vendored fallback
# internally consistent with sage's naming convention.
#
# Each entry is (regex_pattern, replacement). Patterns use a negative
# lookbehind `(?<!sage-)` so already-prefixed forms aren't re-prefixed
# — makes the substitutions IDEMPOTENT (running the script twice in a
# row on the same state is a no-op).
PROSE_SUBSTITUTIONS: list[tuple[str, str]] = [
    (r"(?<!sage-)\bthe memory skill\b",        "the sage-memory skill"),
    (r"(?<!sage-)\bthe ontology skill\b",      "the sage-ontology skill"),
    (r"(?<!sage-)\bthe self-learning skill\b", "the sage-self-learning skill"),
    (r"(?<!sage-)\bmemory skill's\b",          "sage-memory skill's"),
    (r"(?<!sage-)\bontology skill's\b",        "sage-ontology skill's"),
    (r"(?<!sage-)\bself-learning skill's\b",   "sage-self-learning skill's"),
    (r"(?<!sage-)\bvia self-learning\b",       "via sage-self-learning"),
]


def info(msg: str) -> None:
    print(f"  {msg}")


def err(msg: str) -> None:
    print(f"  ERROR: {msg}", file=sys.stderr)


def detect_sage_memory_version(src: Path) -> str:
    """Read version from sage-memory's pyproject.toml."""
    pyproject = src / "pyproject.toml"
    if not pyproject.exists():
        return "unknown"
    for line in pyproject.read_text().splitlines():
        m = re.match(r'^version\s*=\s*"([^"]+)"', line.strip())
        if m:
            return m.group(1)
    return "unknown"


def inject_fallback_header(skill_md: Path) -> None:
    """Insert the fallback comment block right after the YAML frontmatter
    close ('---' line). Idempotent — no-op if the header is already present."""
    content = skill_md.read_text()
    if "Fallback copy" in content:
        return

    lines = content.split("\n")
    fm_close_idx = -1
    fm_seen = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            fm_seen += 1
            if fm_seen == 2:
                fm_close_idx = i
                break

    if fm_close_idx < 0:
        raise RuntimeError(f"no YAML frontmatter close found in {skill_md}")

    # Insert: blank line + header block + (whatever followed the frontmatter)
    out = (
        lines[: fm_close_idx + 1]
        + [""]
        + [FALLBACK_HEADER]
        + lines[fm_close_idx + 1:]
    )
    skill_md.write_text("\n".join(out))


def sync_skill(wheel_root: Path, skill: str, dst_root: Path) -> None:
    """Copy SKILL.md + references/ + scripts/ from wheel into
    dst_root/skill/. Replaces any existing content under those subdirs."""
    src = wheel_root / skill
    dst = dst_root / skill

    if not src.exists():
        raise RuntimeError(f"wheel source not found: {src}")

    dst.mkdir(parents=True, exist_ok=True)

    # SKILL.md — straight copy, header injected separately
    shutil.copy2(src / "SKILL.md", dst / "SKILL.md")

    # references/ — replace entirely (matches wheel structure)
    src_refs = src / "references"
    if src_refs.exists():
        dst_refs = dst / "references"
        if dst_refs.exists():
            shutil.rmtree(dst_refs)
        shutil.copytree(src_refs, dst_refs)

    # scripts/ — ontology has graph_check.py; others may add later
    src_scripts = src / "scripts"
    if src_scripts.exists():
        dst_scripts = dst / "scripts"
        if dst_scripts.exists():
            shutil.rmtree(dst_scripts)
        shutil.copytree(src_scripts, dst_scripts)

    inject_fallback_header(dst / "SKILL.md")


def apply_prose_fixes(dst_root: Path, skill: str) -> int:
    """Apply PROSE_SUBSTITUTIONS (negative-lookbehind regex) to every text
    file under dst_root/skill/. Idempotent — a second run on the same
    state is a no-op. Returns count of files modified."""
    skill_dir = dst_root / skill
    if not skill_dir.exists():
        return 0

    modified = 0
    for f in skill_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in (".md", ".py", ".sh", ".json", ".txt"):
            continue
        try:
            original = f.read_text()
        except (UnicodeDecodeError, PermissionError):
            continue
        patched = original
        for pattern, replacement in PROSE_SUBSTITUTIONS:
            patched = re.sub(pattern, replacement, patched)
        if patched != original:
            f.write_text(patched)
            modified += 1
    return modified


# ── Verification ──────────────────────────────────────────────────────
def grep_stale_prose(sage_root: Path) -> list[str]:
    """Run a strict regex with negative lookbehind. Returns lines that
    still contain unprefixed skill-name prose (i.e., not preceded by
    'sage-')."""
    pattern = (
        r"(?<!sage-)the memory skill\b|"
        r"(?<!sage-)the ontology skill\b|"
        r"(?<!sage-)the self-learning skill\b|"
        r"(?<!sage-)via self-learning\b|"
        r"(?<!sage-)memory skill's\b|"
        r"(?<!sage-)ontology skill's\b|"
        r"(?<!sage-)self-learning skill's\b"
    )
    paths = [
        sage_root / "skills" / "sage-memory",
        sage_root / "skills" / "sage-ontology",
        sage_root / "skills" / "sage-self-learning",
        sage_root / "tools" / "sage-claude-plugin" / "skills" / "sage-memory",
        sage_root / "tools" / "sage-claude-plugin" / "skills" / "sage-ontology",
        sage_root / "tools" / "sage-claude-plugin" / "skills" / "sage-self-learning",
    ]
    cmd = ["grep", "-rPn", pattern] + [str(p) for p in paths if p.exists()]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def verify_frontmatter(sage_root: Path) -> list[str]:
    """Check every vendored SKILL.md's `name:` field matches its
    directory name. Returns mismatches as 'path: name=X dir=Y' strings."""
    paths = []
    for s in SKILLS:
        paths.append(sage_root / "skills" / s / "SKILL.md")
        paths.append(sage_root / "tools" / "sage-claude-plugin" / "skills" / s / "SKILL.md")

    mismatches = []
    for f in paths:
        if not f.exists():
            mismatches.append(f"missing: {f}")
            continue
        head = "\n".join(f.read_text().splitlines()[:5])
        m = re.search(r"^name:\s*(\S+)", head, re.MULTILINE)
        if not m:
            mismatches.append(f"no name field: {f}")
            continue
        expected = f.parent.name
        if m.group(1) != expected:
            mismatches.append(f"{f}: name={m.group(1)} dir={expected}")
    return mismatches


def verify_fallback_headers(sage_root: Path) -> list[str]:
    """Return list of SKILL.md paths missing the fallback comment header."""
    paths = []
    for s in SKILLS:
        paths.append(sage_root / "skills" / s / "SKILL.md")
        paths.append(sage_root / "tools" / "sage-claude-plugin" / "skills" / s / "SKILL.md")
    missing = []
    for f in paths:
        if not f.exists() or "Fallback copy" not in f.read_text():
            missing.append(str(f))
    return missing


# ── Entry point ───────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Refresh sage's vendored fallback skills from sage-memory wheel.")
    ap.add_argument(
        "--from", dest="src",
        default=os.environ.get("SAGE_MEMORY_SRC", "../sage-memory"),
        help="path to sage-memory repo (default: ../sage-memory or $SAGE_MEMORY_SRC)")
    args = ap.parse_args()

    sage_memory_src = Path(args.src).resolve()
    sage_root = Path(__file__).resolve().parents[2]

    wheel_root = sage_memory_src / "src" / "sage_memory" / "skills"
    if not wheel_root.exists():
        err(f"sage-memory skills not found: {wheel_root}")
        err("Pass --from <path> or set SAGE_MEMORY_SRC")
        return 1

    version = detect_sage_memory_version(sage_memory_src)
    print()
    print(f"  Syncing vendored skills from sage-memory {version}")
    print(f"  Source: {sage_memory_src}")
    print(f"  Target: {sage_root}/skills/  +  tools/sage-claude-plugin/skills/")
    print()

    canonical_dst = sage_root / "skills"
    mirror_dst = sage_root / "tools" / "sage-claude-plugin" / "skills"

    print("  Canonical vendored fallback:")
    for skill in SKILLS:
        sync_skill(wheel_root, skill, canonical_dst)
        info(f"  {skill}  (SKILL.md + references/ + scripts/ if any, fallback header injected)")
    print()

    print("  Plugin mirror:")
    for skill in SKILLS:
        sync_skill(wheel_root, skill, mirror_dst)
        info(f"  {skill}")
    print()

    print("  Applying upstream prose-rename fixes (sage-memory <= 0.10.0 stragglers):")
    total_patched = 0
    for skill in SKILLS:
        total_patched += apply_prose_fixes(canonical_dst, skill)
        total_patched += apply_prose_fixes(mirror_dst, skill)
    info(f"  patched {total_patched} file(s)")
    print()

    print("  Verification:")

    stale = grep_stale_prose(sage_root)
    if stale:
        err("stale skill-name prose still present after sync:")
        for ln in stale:
            print(f"    {ln}", file=sys.stderr)
        return 1
    info("  ✓ No stale skill-name prose")

    mismatches = verify_frontmatter(sage_root)
    if mismatches:
        err("frontmatter name field doesn't match directory:")
        for m in mismatches:
            print(f"    {m}", file=sys.stderr)
        return 1
    info("  ✓ All frontmatter names match directory names")

    missing_headers = verify_fallback_headers(sage_root)
    if missing_headers:
        err("fallback comment header missing:")
        for m in missing_headers:
            print(f"    {m}", file=sys.stderr)
        return 1
    info("  ✓ All fallback comment headers present")

    print()
    print(f"  Done. Synced from sage-memory {version}.")
    print()
    print("  Next steps:")
    print(f"    1. Review the diff:  git diff skills/sage-* tools/sage-claude-plugin/skills/sage-*")
    print(f"    2. CHANGELOG.md:     add 'vendored fallback refreshed from sage-memory {version}' under [Unreleased]")
    print(f"    3. Commit:           git add -A skills/sage-* tools/sage-claude-plugin/skills/sage-* CHANGELOG.md")
    print(f"                         git commit -m 'sync vendored fallback from sage-memory {version}'")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
