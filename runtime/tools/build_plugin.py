#!/usr/bin/env python3
"""
build_plugin.py — generate the Claude Code plugin from single sources.

The plugin under tools/sage-claude-plugin/ has been a hand-synced second copy of
every skill, gate script, and template (ADR-5). Drift is structural — the Gate 4
bug shipped twice because of it. This generator reproduces the plugin from its
real sources so there is one copy of each file, not two.

Composition (three layers, applied in order — later layers win):

  1. Framework skills — copy skills/<name>/ → plugin skills/<name>/ for every
     skill dir that the plugin ships. These are byte-identical today.
  2. File map — a handful of files the plugin pulls from core/ and runtime/
     (gate scripts, the spec-gate hook, templates, references) copied to their
     plugin locations.
  3. Overlay — runtime/plugin-overlay/ holds the plugin-ONLY files (manifests,
     sage-navigator, the workflow→skill wrappers, agents, plugin README) laid
     over the tree, overriding where present. The two .claude-plugin JSONs carry
     a {{VERSION}} placeholder filled from the root VERSION file.

Usage:
  build_plugin.py                 build into dist/sage-claude-plugin/
  build_plugin.py --out DIR       build into DIR
  build_plugin.py --check         build to a temp dir and diff against the
                                  committed mirror; exit nonzero on any drift

Exit: 0 = built / no drift | 1 = drift (with file list) | 2 = bad invocation

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import filecmp
import pathlib
import shutil
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MIRROR = REPO_ROOT / "tools" / "sage-claude-plugin"
OVERLAY = REPO_ROOT / "runtime" / "plugin-overlay"
SKILLS = REPO_ROOT / "skills"

VERSION_PLACEHOLDER = "{{VERSION}}"

# Skill dirs the plugin does NOT ship (present in skills/ but not in the plugin).
SKILLS_NOT_IN_PLUGIN = {"autoresearch"}

# Per framework skill, the plugin ships only the runtime-facing content — the
# authoring extras (README.md, tests.md, patterns/, constitution/, gates/,
# anti-patterns/, examples/, templates/, integration/) stay in the repo.
SKILL_INCLUDE_FILES = {"SKILL.md"}
SKILL_INCLUDE_DIRS = {"references", "scripts"}

# Files the plugin pulls from core/ and runtime/ (plugin path → repo source).
FILE_MAP = {
    "hooks/scripts/sage-hallucination-check.sh": "core/gates/scripts/sage-hallucination-check.sh",
    "hooks/scripts/sage-spec-check.sh": "core/gates/scripts/sage-spec-check.sh",
    "hooks/scripts/sage-verify.sh": "core/gates/scripts/sage-verify.sh",
    "hooks/scripts/sage-visual-gate.sh": "core/gates/scripts/sage-visual-gate.sh",
    "hooks/scripts/sage-spec-gate.sh": "runtime/platforms/claude-code/hooks/sage-spec-gate.sh",
    "references/decision-template.md": "core/templates/architecture/decision-template.md",
    "references/full-spec-template.md": "core/templates/spec/full.spec-template.md",
    "references/plan-template.md": "core/templates/plan/standard.plan-template.md",
    "references/spec-template.md": "core/templates/spec/minimal.spec-template.md",
    "references/lightpanda-setup.md": "core/references/lightpanda-setup.md",
    "references/skill-authoring-guide.md": "develop/guides/skill-authoring-guide.md",
}


class BuildError(Exception):
    pass


def read_version() -> str:
    vf = REPO_ROOT / "VERSION"
    if not vf.is_file():
        raise BuildError("VERSION file not found at repo root")
    return vf.read_text().strip()


def copy_file(src: pathlib.Path, dst: pathlib.Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build(out: pathlib.Path) -> None:
    version = read_version()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # ── 1. Framework skills ──
    plugin_skill_names = {p.name for p in (MIRROR / "skills").iterdir() if p.is_dir()}
    for skill in sorted(SKILLS.iterdir()):
        if not skill.is_dir():
            continue
        if skill.name in SKILLS_NOT_IN_PLUGIN:
            continue
        if skill.name not in plugin_skill_names:
            continue
        for f in skill.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(skill)
            top = rel.parts[0]
            if not (str(rel) in SKILL_INCLUDE_FILES or top in SKILL_INCLUDE_DIRS):
                continue
            copy_file(f, out / "skills" / skill.name / rel)

    # ── 2. File map ──
    for plugin_rel, src_rel in FILE_MAP.items():
        src = REPO_ROOT / src_rel
        if not src.is_file():
            raise BuildError(f"file-map source missing: {src_rel}")
        copy_file(src, out / plugin_rel)

    # ── 3. Overlay (overrides) ──
    if not OVERLAY.is_dir():
        raise BuildError(f"overlay dir missing: {OVERLAY.relative_to(REPO_ROOT)}")
    for f in sorted(OVERLAY.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(OVERLAY)
        dst = out / rel
        text = f.read_text(encoding="utf-8", errors="replace")
        if VERSION_PLACEHOLDER in text:
            text = text.replace(VERSION_PLACEHOLDER, version)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")


def _diff(a: pathlib.Path, b: pathlib.Path, rel: str, out: list):
    """Recursively compare two trees; append drift descriptions to `out`."""
    cmp = filecmp.dircmp(a, b)
    for name in sorted(cmp.left_only):
        out.append(f"  only in generated: {rel}{name}")
    for name in sorted(cmp.right_only):
        out.append(f"  only in mirror:    {rel}{name}")
    # filecmp uses shallow stat compare by default; force content compare.
    for name in sorted(cmp.common_files):
        if not filecmp.cmp(a / name, b / name, shallow=False):
            out.append(f"  differs:           {rel}{name}")
    for name in sorted(cmp.common_dirs):
        _diff(a / name, b / name, f"{rel}{name}/", out)


def check() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sage-plugin-build-"))
    try:
        build(tmp)
        drift = []
        _diff(tmp, MIRROR, "", drift)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if drift:
        print("✗ plugin drift — the generator does not reproduce the committed mirror:")
        for line in drift:
            print(line)
        print()
        print("FAIL — correct the source side (skills/, core/, runtime/plugin-overlay/)")
        print("  until the generator reproduces tools/sage-claude-plugin/ exactly.")
        return 1
    print("OK — generator reproduces tools/sage-claude-plugin/ exactly.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Claude Code plugin.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="build to a temp dir and diff against the committed mirror")
    parser.add_argument("--out", type=pathlib.Path, default=None,
                        help="output directory (default: dist/sage-claude-plugin)")
    args = parser.parse_args()

    try:
        if args.check:
            return check()
        out = args.out or (REPO_ROOT / "dist" / "sage-claude-plugin")
        build(out)
        print(f"OK — built plugin into {out}")
        return 0
    except BuildError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
