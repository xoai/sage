#!/usr/bin/env python3
"""
build_plugin.py — generate the Claude Code plugin from single sources.

The plugin used to live at tools/sage-claude-plugin/ as a hand-synced second
copy of every skill, gate script, and template (ADR-5). Drift was structural —
the Gate 4 bug shipped twice because of it. That mirror is gone (P3-T2b). This
generator is now the only way the plugin comes into existence: `main` holds one
copy of each file, and the release workflow builds the tree and publishes it to
the `plugin-dist` branch, which the marketplace `source` pins via `ref`.

Composition (three layers, applied in order — later layers win):

  1. Framework skills — copy skills/<name>/ → plugin skills/<name>/ for every
     skill in PLUGIN_SKILLS that has a skills/ source.
  2. File map — the files the plugin pulls from core/ and runtime/ (gate
     scripts, the spec-gate hook, templates, references).
  3. Overlay — runtime/plugin-overlay/ holds the plugin-ONLY files (manifests,
     sage-navigator, the workflow→skill wrappers, agents, plugin README) laid
     over the tree, overriding where present. The two .claude-plugin JSONs carry
     a {{VERSION}} placeholder filled from the root VERSION file.

Because no built tree is committed any more, PLUGIN_SKILLS below is the
reviewable statement of what the plugin ships — adding a skill to skills/
without listing it here (or in SKILLS_NOT_IN_PLUGIN) is a build error, so the
decision cannot be made by accident.

Usage:
  build_plugin.py                 build into dist/sage-claude-plugin/
  build_plugin.py --out DIR       build into DIR
  build_plugin.py --check         build and verify the artifact is well-formed,
                                  reproducible, and faithful to its sources

Exit: 0 = built / check passed | 1 = build error or failed check | 2 = bad invocation

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
OVERLAY = REPO_ROOT / "runtime" / "plugin-overlay"
SKILLS = REPO_ROOT / "skills"
SYSTEM_SKILLS = REPO_ROOT / "core" / "system-skills"
INSTRUCTIONS_BODY = REPO_ROOT / "runtime" / "platforms" / "_shared" / "instructions-body.sh"
CONSTITUTION_SH = REPO_ROOT / "runtime" / "platforms" / "_shared" / "constitution.sh"

VERSION_PLACEHOLDER = "{{VERSION}}"

# The branch the release workflow publishes the built tree to. The marketplace
# entry must pin this as its `ref` — without it, `source` resolves to the default
# branch, which no longer carries a plugin tree, and the plugin is uninstallable.
DIST_REF = "plugin-dist"

# Every skill the plugin ships. Sources: skills/<name>/ (framework skills) and/or
# runtime/plugin-overlay/skills/<name>/ (plugin-only skills and overrides).
PLUGIN_SKILLS = frozenset({
    # workflow→skill wrappers + the router (overlay-only)
    "architect", "build", "configure", "continue", "fix", "learn", "reflect",
    "review", "sage", "sage-navigator",
    # framework skills (skills/)
    "api", "baas", "flutter", "mobile", "nextjs", "react", "react-native",
    "sage-memory", "sage-ontology", "sage-self-learning", "web",
})

# Skill dirs that exist in skills/ but are deliberately NOT shipped in the plugin.
SKILLS_NOT_IN_PLUGIN = frozenset({"autoresearch"})

# System skills (core/system-skills/) — Sage-about-Sage content that ADR-9 moved
# OUT of the eager layer. They ship in the plugin because the plugin install has
# no vendored sage/ tree to point a loader stub at: if they are not here, the
# content the eager layer no longer carries does not exist at all for plugin
# users. Discovered from disk rather than enumerated, because the whole point of
# the diet is that this list grows as the eager layer shrinks — and a hand-kept
# copy of a directory listing is a drift bug waiting for a quiet release.
SYSTEM_SKILL_NAMES = frozenset(
    p.name for p in sorted(SYSTEM_SKILLS.iterdir()) if (p / "SKILL.md").is_file()
) if SYSTEM_SKILLS.is_dir() else frozenset()

# Per framework skill, the plugin ships only the runtime-facing content — the
# authoring extras (README.md, tests.md, patterns/, constitution/, gates/,
# anti-patterns/, examples/, templates/, integration/) stay in the repo.
SKILL_INCLUDE_FILES = {"SKILL.md"}
SKILL_INCLUDE_DIRS = {"references", "scripts"}

# Files the plugin pulls from core/ and runtime/ (plugin path → repo source).
FILE_MAP = {
    # The CLI the plugin's README tells users to run. The overlay used to carry its
    # own copy, which nothing regenerated: it froze at v1.1.7 (1007 lines against
    # bin/sage's 2056) and hardcoded `sage-version: "1.0.0"` into every project it
    # initialized. A second copy of a file that has a canonical source is exactly
    # what ADR-5 exists to forbid — so it is generated, and audit() now holds it
    # byte-identical to bin/sage forever.
    "scripts/sage": "bin/sage",
    "hooks/scripts/sage-hallucination-check.sh": "core/gates/scripts/sage-hallucination-check.sh",
    "hooks/scripts/sage-spec-check.sh": "core/gates/scripts/sage-spec-check.sh",
    "hooks/scripts/sage-verify.sh": "core/gates/scripts/sage-verify.sh",
    "hooks/scripts/sage-visual-gate.sh": "core/gates/scripts/sage-visual-gate.sh",
    "hooks/scripts/sage-spec-gate.sh": "runtime/platforms/claude-code/hooks/sage-spec-gate.sh",
    "hooks/scripts/sage-degradation-log.sh": "runtime/platforms/claude-code/hooks/sage-degradation-log.sh",
    "hooks/scripts/sage-tdd-gate.sh": "runtime/platforms/claude-code/hooks/sage-tdd-gate.sh",
    "references/decision-template.md": "core/templates/architecture/decision-template.md",
    "references/full-spec-template.md": "core/templates/spec/full.spec-template.md",
    "references/plan-template.md": "core/templates/plan/standard.plan-template.md",
    "references/spec-template.md": "core/templates/spec/minimal.spec-template.md",
    "references/lightpanda-setup.md": "core/references/lightpanda-setup.md",
    "references/skill-authoring-guide.md": "develop/guides/skill-authoring-guide.md",
}

# ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/foo.sh → hooks/scripts/foo.sh
HOOK_COMMAND = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/(\S+)")


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


NAVIGATOR_FRONTMATTER = """---
name: sage-navigator
description: >
  Sage's process layer — routing, the constitution, the checkpoint contract, and
  the skill-check rule. A plugin cannot install a CLAUDE.md, so this carries what
  a vendored install puts in the eager layer. Generated from the same source; do
  not hand-edit.
user-invocable: false
---

<!-- GENERATED by runtime/tools/build_plugin.py from
     runtime/platforms/_shared/instructions-body.sh. Do not edit: build_plugin.py
     --check rebuilds it and a hand edit will be silently overwritten. The
     hand-maintained version of this file drifted for two releases and shipped a
     routing table that was a release out of date. -->

"""


def build_navigator() -> str:
    """The eager body, rendered as the plugin's process skill.

    Same source as every platform's instructions file — because a second copy is
    a copy that drifts, and this one did.
    """
    script = (
        'set -eu\n'
        'source "%s"\n'
        'source "%s"\n'
        'emit_instructions_body\n' % (INSTRUCTIONS_BODY, CONSTITUTION_SH)
    )
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    if proc.returncode != 0:
        raise BuildError("could not emit the instructions body for the navigator:\n"
                         + proc.stderr[-800:])

    body = proc.stdout

    # The constitution placeholder is substituted by each platform's generator. The
    # plugin has no project to read a preset from, so it gets the base five — with
    # each principle naming the mechanism that enforces it, exactly as the eager
    # layer does.
    const = subprocess.run(
        ["bash", "-c",
         'source "%s"; build_constitution_section "%s" "/nonexistent"'
         % (CONSTITUTION_SH, REPO_ROOT / "core")],
        capture_output=True, text=True)
    if const.returncode != 0:
        raise BuildError("constitution merge failed:\n" + const.stderr[-400:])

    body = body.replace("__CONSTITUTION_PLACEHOLDER__", const.stdout.rstrip("\n"))

    if "__CONSTITUTION_PLACEHOLDER__" in body:
        raise BuildError("the navigator still carries an unsubstituted placeholder")

    return NAVIGATOR_FRONTMATTER + body


def copy_file_text(text: str, dst: pathlib.Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


def build(out: pathlib.Path) -> None:
    version = read_version()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # ── 1. Framework skills ──
    # A skill in skills/ that is neither shipped nor explicitly excluded is an
    # unmade decision — fail rather than silently pick one.
    on_disk = {p.name for p in SKILLS.iterdir() if p.is_dir()}
    undeclared = on_disk - PLUGIN_SKILLS - SKILLS_NOT_IN_PLUGIN
    if undeclared:
        raise BuildError(
            "skills/ holds dirs the plugin manifest does not mention: "
            + ", ".join(sorted(undeclared))
            + " — add each to PLUGIN_SKILLS or SKILLS_NOT_IN_PLUGIN in build_plugin.py"
        )

    for name in sorted(PLUGIN_SKILLS & on_disk):
        skill = SKILLS / name
        for f in skill.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(skill)
            top = rel.parts[0]
            if not (str(rel) in SKILL_INCLUDE_FILES or top in SKILL_INCLUDE_DIRS):
                continue
            copy_file(f, out / "skills" / name / rel)

    # ── 1a. sage-navigator — GENERATED from the eager body ──
    #
    # A plugin cannot write a CLAUDE.md into a user's project, so the navigator is
    # the plugin's process layer. It used to be a 441-line file maintained BY HAND
    # alongside the real eager body — and it had drifted for two releases: it still
    # routed to /analyze, /qa, /design-review and /status, every one of them folded
    # into another command back in v1.2.0. Plugin users were being handed a routing
    # table a release out of date, and nothing noticed, because nothing compared the
    # two copies.
    #
    # It is generated from the same source as CLAUDE.md now. There is one eager
    # layer. If it is wrong it is wrong in one place, and every consumer is wrong
    # together — which is the only kind of wrong you can actually fix.
    #
    # This is the drift ADR-5 exists to forbid, and it survived because the
    # navigator lived in the overlay rather than in FILE_MAP. It is neither now.
    copy_file_text(build_navigator(), out / "skills" / "sage-navigator" / "SKILL.md")

    # ── 1b. System skills (ADR-9 delivery class 2) ──
    for name in sorted(SYSTEM_SKILL_NAMES):
        copy_file(SYSTEM_SKILLS / name / "SKILL.md",
                  out / "skills" / name / "SKILL.md")

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

    # Every declared skill must have materialized from one layer or the other.
    for name in sorted(PLUGIN_SKILLS | SYSTEM_SKILL_NAMES):
        if not (out / "skills" / name / "SKILL.md").is_file():
            raise BuildError(
                f"PLUGIN_SKILLS names {name!r} but no layer produced "
                f"skills/{name}/SKILL.md"
            )


def build_inputs() -> list:
    """Every repo file the build reads. The artifact is exactly a function of these."""
    inputs = [REPO_ROOT / "VERSION"]
    inputs += [REPO_ROOT / src for src in FILE_MAP.values()]
    inputs += [f for f in OVERLAY.rglob("*") if f.is_file()]
    for name in sorted(PLUGIN_SKILLS):
        skill = SKILLS / name
        if not skill.is_dir():
            continue
        for f in skill.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(skill)
            if str(rel) in SKILL_INCLUDE_FILES or rel.parts[0] in SKILL_INCLUDE_DIRS:
                inputs.append(f)
    return inputs


def untracked_inputs() -> list:
    """Build inputs that git does not track — files that exist for you and nobody else.

    .gitignore's unanchored `sage/` rule silently swallowed the plugin's /sage
    router for the whole Phase-3 program: it sat on every developer's disk, was
    absent from every clean checkout, and would have shipped a plugin with no
    entry point once the committed mirror stopped covering for it. An input the
    release runner cannot see is not an input — it is a local accident.

    Returns [] when this is not a git checkout (a release tarball, say), where
    the question does not apply.
    """
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "-z"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    tracked = {
        REPO_ROOT / p.decode()
        for p in proc.stdout.split(b"\0") if p
    }
    return [f for f in build_inputs() if f not in tracked]


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


def audit(tree: pathlib.Path) -> list:
    """Verify a built tree is well-formed and faithful to its sources.

    No committed mirror exists to diff against any more, so these are the
    properties that used to be enforced by eyeballing the mirror's diff:
    the manifests are stamped and pin the dist branch, the gate scripts are
    byte-identical to the ones the repo tests, and every hook the plugin
    registers actually ships.
    """
    version = read_version()
    problems: list = []

    # 1. No placeholder survives into the artifact.
    for f in sorted(tree.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if VERSION_PLACEHOLDER in text:
            problems.append(f"unsubstituted {VERSION_PLACEHOLDER} in {f.relative_to(tree)}")

    # 2. plugin.json is the version authority and agrees with VERSION.
    plugin_json = tree / ".claude-plugin" / "plugin.json"
    if not plugin_json.is_file():
        problems.append("missing .claude-plugin/plugin.json")
    else:
        try:
            found = json.loads(plugin_json.read_text()).get("version")
        except json.JSONDecodeError as exc:
            problems.append(f".claude-plugin/plugin.json is not valid JSON: {exc}")
            found = None
        if found is not None and found != version:
            problems.append(
                f".claude-plugin/plugin.json version {found} != VERSION {version}"
            )

    # 3. The marketplace entry pins the dist branch and defers the version to
    #    plugin.json. Without `ref` the source resolves to the default branch,
    #    which carries no plugin tree — the plugin would be uninstallable.
    market = tree / ".claude-plugin" / "marketplace.json"
    if not market.is_file():
        problems.append("missing .claude-plugin/marketplace.json")
    else:
        try:
            entries = json.loads(market.read_text()).get("plugins", [])
        except json.JSONDecodeError as exc:
            problems.append(f".claude-plugin/marketplace.json is not valid JSON: {exc}")
            entries = []
        for entry in entries:
            name = entry.get("name", "?")
            source = entry.get("source", {})
            if source.get("source") == "git-subdir" and source.get("ref") != DIST_REF:
                problems.append(
                    f"marketplace entry {name!r}: source.ref is {source.get('ref')!r}, "
                    f"expected {DIST_REF!r} — the default branch carries no plugin tree"
                )
            if "version" in entry:
                problems.append(
                    f"marketplace entry {name!r} pins a version — remove it; "
                    f"plugin.json is the single authority"
                )

    # 4. Gate scripts and templates are byte-identical to the sources the repo
    #    tests. A mis-wired FILE_MAP would ship a stale gate.
    for plugin_rel, src_rel in FILE_MAP.items():
        src, dst = REPO_ROOT / src_rel, tree / plugin_rel
        if not dst.is_file():
            problems.append(f"file-map target missing from artifact: {plugin_rel}")
        elif not filecmp.cmp(src, dst, shallow=False):
            problems.append(f"{plugin_rel} differs from its source {src_rel}")

    # 5. Every hook the plugin registers resolves to a file that ships.
    hooks_json = tree / "hooks" / "hooks.json"
    if not hooks_json.is_file():
        problems.append("missing hooks/hooks.json")
    else:
        try:
            hooks = json.loads(hooks_json.read_text())
        except json.JSONDecodeError as exc:
            problems.append(f"hooks/hooks.json is not valid JSON: {exc}")
            hooks = {}
        for matchers in hooks.get("hooks", {}).values():
            for matcher in matchers:
                for hook in matcher.get("hooks", []):
                    for rel in HOOK_COMMAND.findall(hook.get("command", "")):
                        if not (tree / rel).is_file():
                            problems.append(f"hooks.json registers {rel}, which does not ship")

    # 6. Every input the build reads is tracked by git. Otherwise this build and
    #    the one the release runner does are builds of two different trees.
    for f in untracked_inputs():
        problems.append(
            f"build input is not tracked by git: {f.relative_to(REPO_ROOT)} "
            f"— it exists here and in no clean checkout (check .gitignore)"
        )

    return problems


def check() -> int:
    a = pathlib.Path(tempfile.mkdtemp(prefix="sage-plugin-a-"))
    b = pathlib.Path(tempfile.mkdtemp(prefix="sage-plugin-b-"))
    try:
        build(a)
        build(b)
        problems = audit(a)
        # A build that is not reproducible cannot be reviewed by its inputs.
        drift: list = []
        _diff(a, b, "", drift)
        if drift:
            problems.append("build is not reproducible — two runs differ:")
            problems.extend(drift)
        skills = sorted(p.name for p in (a / "skills").iterdir() if p.is_dir())
    finally:
        shutil.rmtree(a, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)

    if problems:
        print("✗ the generated plugin does not satisfy its contract:")
        for line in problems:
            print(f"  {line}")
        print()
        print("FAIL — correct the source side (skills/, core/, runtime/plugin-overlay/).")
        return 1

    print(f"OK — plugin builds clean: {len(skills)} skills, "
          f"{len(FILE_MAP)} mapped files, version {read_version()}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Claude Code plugin.")
    parser.add_argument("--check", action="store_true",
                        help="build and verify the artifact against its contract")
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
