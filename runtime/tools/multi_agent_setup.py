#!/usr/bin/env python3
"""
multi_agent_setup.py — Install/refresh/remove the Sage multi-agent capability.

Invoked by `sage setup multi-agent` (via bin/sage). Zero pip deps —
Python 3.11+ stdlib only (tomllib comes in 3.11).

Usage:
    multi_agent_setup.py install <framework_dir> <project_dir> [--yes] [--force]
    multi_agent_setup.py remove  <framework_dir> <project_dir> [--yes]
    multi_agent_setup.py refresh <framework_dir> <project_dir> [--yes] [--force]
    multi_agent_setup.py status  <framework_dir> <project_dir>

Exit codes:
    0  success
    1  generic error
    2  bad invocation
    3  preflight failed (hard)
    5  Python <3.11 (no tomllib)
    6  project not Sage-initialized
    7  user cancelled
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Sibling helper in runtime/tools/ — resolvable because this script is
# invoked as `python3 .../runtime/tools/multi_agent_setup.py`, so its
# own directory is sys.path[0].
from sage_platforms import detect_claude_code

# Schema version of .sage/config.yaml :: multi_agent block we write.
MULTI_AGENT_CONFIG_VERSION = "1.0.0"

# ── ANSI ──────────────────────────────────────────────────────────────
class C:
    R = "\033[0m"
    B = "\033[1m"
    D = "\033[2m"
    G = "\033[32m"
    Y = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    @classmethod
    def disable(cls) -> None:
        for k in ("R", "B", "D", "G", "Y", "RED", "CYAN"):
            setattr(cls, k, "")

if not sys.stdout.isatty():
    C.disable()


def info(msg: str) -> None: print(f"  {C.CYAN}↻{C.R} {msg}")
def ok(msg: str) -> None: print(f"  {C.G}✓{C.R} {msg}")
def warn(msg: str) -> None: print(f"  {C.Y}⚠{C.R} {msg}")
def err(msg: str) -> None: print(f"  {C.RED}✗{C.R} {msg}", file=sys.stderr)
def step(msg: str) -> None: print(f"    {C.D}{msg}{C.R}")


# ── Manifest ──────────────────────────────────────────────────────────
def load_manifest(framework_dir: Path) -> dict[str, Any]:
    manifest_path = framework_dir / "runtime" / "multi-agent" / "manifest.json"
    if not manifest_path.exists():
        err(f"missing manifest: {manifest_path}")
        sys.exit(1)
    return json.loads(manifest_path.read_text())


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Sage version (for the agents.toml header stamp) ──────────────────
def detect_sage_version(framework_dir: Path) -> str:
    plugin = framework_dir / ".claude-plugin" / "plugin.json"
    if plugin.exists():
        try:
            return json.loads(plugin.read_text()).get("version", "unknown")
        except Exception:
            pass
    return "unknown"


# ── Pre-flight ────────────────────────────────────────────────────────
def preflight(project_dir: Path, *, for_install: bool) -> tuple[bool, list[str]]:
    """Returns (proceed, warnings). Hard failures sys.exit; warnings are printed."""
    hard_fail = False
    warnings: list[str] = []

    print(f"\n  {C.B}Pre-flight checks{C.R}")

    # Sage-initialized?
    sage_dir = project_dir / ".sage"
    if not sage_dir.is_dir():
        err(".sage/ missing — run `sage init` first")
        hard_fail = True
    else:
        ok(".sage/ exists")

    # Python 3.11+
    if sys.version_info < (3, 11):
        err(f"Python 3.11+ required (have {sys.version_info.major}.{sys.version_info.minor})")
        hard_fail = True
    else:
        ok(f"Python {sys.version_info.major}.{sys.version_info.minor} (≥3.11)")

    # claude-code project? Detect from project state (.claude/ dir,
    # Sage CLAUDE.md, or config.yaml platforms) via the shared helper —
    # not a brittle single-line config.yaml grep.
    if detect_claude_code(project_dir):
        ok("Claude Code project detected")
    else:
        err("not a Claude Code project — multi-agent is Claude Code "
            "only in v1")
        err("(no .claude/ directory, no Sage-generated CLAUDE.md, and "
            ".sage/config.yaml does not list claude-code)")
        hard_fail = True

    # CLIs on PATH (soft)
    if for_install:
        if shutil.which("codex"):
            ok("codex CLI on PATH")
        else:
            warn("codex CLI not on PATH (install before first /build-x)")
            warnings.append("codex")
        if shutil.which("kimi"):
            ok("kimi CLI on PATH")
        else:
            warn("kimi CLI not on PATH (install before first /build-x)")
            warnings.append("kimi")

    if hard_fail:
        sys.exit(3)
    return True, warnings


# ── Config block I/O (minimal YAML — top-level keys + 1-level nesting) ─
def read_multi_agent_config(config_path: Path) -> dict[str, str] | None:
    """Returns {'enabled': 'true', 'installed_version': '1.0.0'} or None if absent."""
    if not config_path.exists():
        return None
    in_block = False
    block: dict[str, str] = {}
    for raw in config_path.read_text().splitlines():
        if raw.startswith("multi_agent:"):
            in_block = True
            continue
        if in_block:
            if raw.startswith(" ") or raw.startswith("\t"):
                line = raw.strip()
                if ":" in line:
                    k, v = line.split(":", 1)
                    block[k.strip()] = v.strip().strip('"').strip("'")
            else:
                in_block = False
    return block if block else None


def write_multi_agent_config(config_path: Path, version: str) -> None:
    """Insert or update the multi_agent: block in .sage/config.yaml.

    Minimal YAML editing — the block uses 2-space indented children.
    Idempotent: replaces an existing block, doesn't duplicate.
    """
    lines = config_path.read_text().splitlines() if config_path.exists() else []
    out: list[str] = []
    skipping = False
    found = False
    new_block = [
        "multi_agent:",
        "  enabled: true",
        f'  installed_version: "{version}"',
    ]
    for raw in lines:
        if raw.startswith("multi_agent:"):
            skipping = True
            found = True
            out.extend(new_block)
            continue
        if skipping:
            if raw.startswith(" ") or raw.startswith("\t") or raw == "":
                continue
            skipping = False
        out.append(raw)
    if not found:
        if out and out[-1] != "":
            out.append("")
        out.extend(new_block)
    config_path.write_text("\n".join(out) + "\n")


def remove_multi_agent_config(config_path: Path) -> None:
    if not config_path.exists():
        return
    lines = config_path.read_text().splitlines()
    out: list[str] = []
    skipping = False
    for raw in lines:
        if raw.startswith("multi_agent:"):
            skipping = True
            continue
        if skipping:
            if raw.startswith(" ") or raw.startswith("\t"):
                continue
            skipping = False
        out.append(raw)
    # Strip trailing blank lines
    while out and out[-1] == "":
        out.pop()
    config_path.write_text("\n".join(out) + "\n")


# ── Settings.json merge ───────────────────────────────────────────────
def merge_settings_json(settings_path: Path, snippet_path: Path) -> set[str]:
    """Union snippet's permissions.allow into settings.json. Returns the added patterns."""
    snippet = json.loads(snippet_path.read_text())
    snippet_allow = set(snippet.get("permissions", {}).get("allow", []))

    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            warn(f"settings.json malformed — replacing with minimal config")
            current = {}
    else:
        current = {}

    if "$schema" not in current:
        current["$schema"] = snippet.get("$schema", "")
    perms = current.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    existing = set(allow)
    added = snippet_allow - existing
    for pat in sorted(added):
        allow.append(pat)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(current, indent=2) + "\n")
    return added


def prune_settings_json(settings_path: Path, snippet_path: Path) -> set[str]:
    """Remove snippet's permissions.allow entries from settings.json. Returns the removed."""
    if not settings_path.exists():
        return set()
    try:
        current = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return set()
    snippet = json.loads(snippet_path.read_text())
    snippet_allow = set(snippet.get("permissions", {}).get("allow", []))
    allow = current.get("permissions", {}).get("allow", [])
    keep = [p for p in allow if p not in snippet_allow]
    removed = set(allow) - set(keep)
    if removed:
        current["permissions"]["allow"] = keep
        settings_path.write_text(json.dumps(current, indent=2) + "\n")
    return removed


# ── File copy with placeholder rendering ──────────────────────────────
def render_placeholders(text: str, *, sage_version: str) -> str:
    return (text
            .replace("{{SAGE_VERSION}}", sage_version)
            .replace("{{DATE}}", datetime.date.today().isoformat()))


def copy_template(src: Path, dst: Path, *, render: bool, sage_version: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if render:
        dst.write_text(render_placeholders(src.read_text(), sage_version=sage_version))
    else:
        shutil.copy2(src, dst)


# ── File ownership lists from manifest ────────────────────────────────
def framework_owned_pairs(manifest: dict[str, Any], framework_root: Path, project: Path) -> list[tuple[Path, Path]]:
    out = []
    base = framework_root / "runtime" / "multi-agent"
    for deployed_rel, meta in manifest["framework_owned"].items():
        src = base / meta["source"]
        dst = project / deployed_rel
        out.append((src, dst))
    return out


def user_owned_pairs(manifest: dict[str, Any], framework_root: Path, project: Path) -> list[tuple[Path, Path]]:
    out = []
    base = framework_root / "runtime" / "multi-agent"
    for deployed_rel, meta in manifest["user_owned"].items():
        src = base / meta["source"]
        dst = project / deployed_rel
        out.append((src, dst))
    return out


# ── Prompts ───────────────────────────────────────────────────────────
def confirm(prompt: str, *, default: str = "A", yes: bool = False) -> str:
    if yes:
        return default
    try:
        ans = input(f"\n  {prompt}: ").strip()
    except EOFError:
        return default
    return ans or default


# ── CLAUDE.md augmentation ────────────────────────────────────────────
CLAUDE_MARKER_START = "<!-- sage-multi-agent-section-start -->"
CLAUDE_MARKER_END = "<!-- sage-multi-agent-section-end -->"

CLAUDE_SECTION_BODY = """\
## Multi-Agent build cycle (optional)

This project has the Sage multi-agent capability installed. In addition
to the standard in-session `/build`, you can run a cross-model
augmented cycle:

- `/build-x <task>` — full cycle: brief → spec → external spec review →
  plan → external plan review → external implement → external code
  review → reflect. Slower but the external reviewer (Codex CLI) and
  external implementer (Kimi CLI by default) catch self-bias failures
  the in-session loop misses.
- `/review-spec <slug>`, `/review-plan <slug>` — adversarial review of
  the named artefact via the configured `spec_reviewer` agent.
- `/implement <slug>` — hand off implementation to the configured
  `implementer` agent (writes uncommitted diff + `implementer-notes.md`).
- `/review-code <slug>` — adversarial review of the uncommitted diff.

Tool bindings live in `.sage/agents.toml`. Edit that file to swap which
CLI handles each role (e.g., point `code_reviewer` at Kimi instead of
Codex). Role prompts live in `.sage/prompts/` and are yours to tune.

Prefer `/build` for fast in-session work where you want one model's
output. Prefer `/build-x` when the work is non-trivial, security-
adjacent, or the kind of refactor where independent review changes
your mind. See `.sage/docs/multi-agent.md` for the protocol contract.
"""


def claude_md_section() -> str:
    return f"\n{CLAUDE_MARKER_START}\n{CLAUDE_SECTION_BODY}\n{CLAUDE_MARKER_END}\n"


def append_claude_section(claude_md: Path) -> bool:
    """Returns True if the section was added (False if already present or file missing)."""
    if not claude_md.exists():
        return False
    body = claude_md.read_text()
    if CLAUDE_MARKER_START in body:
        return False
    if not body.endswith("\n"):
        body += "\n"
    claude_md.write_text(body + claude_md_section())
    return True


def remove_claude_section(claude_md: Path) -> bool:
    if not claude_md.exists():
        return False
    body = claude_md.read_text()
    if CLAUDE_MARKER_START not in body or CLAUDE_MARKER_END not in body:
        return False
    start = body.find(CLAUDE_MARKER_START)
    end = body.find(CLAUDE_MARKER_END) + len(CLAUDE_MARKER_END)
    # Walk back over the newline before the start marker, walk forward over the one after end
    if start > 0 and body[start - 1] == "\n":
        start -= 1
    if end < len(body) and body[end] == "\n":
        end += 1
    new_body = body[:start] + body[end:]
    claude_md.write_text(new_body)
    return True


# ── Commands ──────────────────────────────────────────────────────────
def cmd_install(framework_dir: Path, project_dir: Path, *, yes: bool, force: bool) -> int:
    manifest = load_manifest(framework_dir)
    sage_version = detect_sage_version(framework_dir)

    preflight(project_dir, for_install=True)

    config_path = project_dir / ".sage" / "config.yaml"
    existing = read_multi_agent_config(config_path)
    is_reinstall = existing is not None and existing.get("enabled") == "true"

    print(f"\n  {C.B}This will install{C.R} (sage v{sage_version}):\n")
    fw_pairs = framework_owned_pairs(manifest, framework_dir, project_dir)
    user_pairs = user_owned_pairs(manifest, framework_dir, project_dir)
    for _, dst in user_pairs:
        info(f"{dst.relative_to(project_dir)}  {C.D}(yours — edit freely){C.R}")
    for _, dst in fw_pairs:
        info(f"{dst.relative_to(project_dir)}  {C.D}(framework — refreshed by sage update){C.R}")
    info(".claude/settings.json  (merged, not overwritten)")
    info(f".sage/config.yaml  (multi_agent block, version {sage_version})")
    info("CLAUDE.md  (multi-agent section appended)")

    if is_reinstall:
        print(f"\n  {C.Y}multi-agent is already installed (v{existing.get('installed_version', '?')}).{C.R}")
        print(f"  {C.D}Per-file prompt mode: each existing file will ask Keep | Replace | Skip.{C.R}")

    ans = confirm("[A] Proceed  |  [C] Cancel", default="A", yes=yes).upper()
    if ans.startswith("C"):
        warn("Cancelled.")
        return 7
    if ans not in ("A", ""):
        warn(f"Unrecognised input ({ans!r}) — treating as cancel.")
        return 7

    print()
    # User-owned: skip if already exists (unless --force). User edits win.
    for src, dst in user_pairs:
        render = (src.name == "agents.toml.template")
        if dst.exists() and not force:
            ok(f"{dst.relative_to(project_dir)}  (preserved)")
            continue
        copy_template(src, dst, render=render, sage_version=sage_version)
        ok(f"{dst.relative_to(project_dir)}  (installed)")

    # Framework-owned: always refresh.
    for src, dst in fw_pairs:
        copy_template(src, dst, render=False, sage_version=sage_version)
        if dst.suffix == ".sh":
            os.chmod(dst, 0o755)
        ok(f"{dst.relative_to(project_dir)}  (installed/refreshed)")

    # settings.json merge
    snippet_path = framework_dir / "runtime" / "multi-agent" / "settings.snippet.json"
    settings_path = project_dir / ".claude" / "settings.json"
    added = merge_settings_json(settings_path, snippet_path)
    if added:
        ok(f".claude/settings.json  (added {len(added)} bash patterns)")
    else:
        ok(".claude/settings.json  (already up to date)")

    # config.yaml
    write_multi_agent_config(config_path, version=sage_version)
    ok(f".sage/config.yaml  (multi_agent.enabled=true, version={sage_version})")

    # CLAUDE.md
    claude_md = project_dir / "CLAUDE.md"
    if append_claude_section(claude_md):
        ok("CLAUDE.md  (multi-agent section appended)")
    else:
        if claude_md.exists():
            ok("CLAUDE.md  (multi-agent section already present)")
        else:
            warn("CLAUDE.md  (not found — run `sage update` to regenerate)")

    print(f"\n  {C.B}Done.{C.R}  Try: {C.CYAN}/build-x <task>{C.R}  inside Claude Code.")
    print(f"  {C.D}Edit .sage/agents.toml to change tool bindings.{C.R}\n")
    return 0


def cmd_remove(framework_dir: Path, project_dir: Path, *, yes: bool) -> int:
    manifest = load_manifest(framework_dir)
    config_path = project_dir / ".sage" / "config.yaml"
    existing = read_multi_agent_config(config_path)

    if not existing or existing.get("enabled") != "true":
        warn("multi-agent is not installed in this project — nothing to remove.")
        return 0

    fw_pairs = framework_owned_pairs(manifest, framework_dir, project_dir)
    user_pairs = user_owned_pairs(manifest, framework_dir, project_dir)

    print(f"\n  {C.B}This will remove{C.R}:\n")
    for _, dst in user_pairs:
        info(f"{dst.relative_to(project_dir)}  {C.D}(user — backed up before removal){C.R}")
    for _, dst in fw_pairs:
        info(f"{dst.relative_to(project_dir)}  {C.D}(framework — deleted){C.R}")
    info(".claude/settings.json  (prune multi-agent patterns; keep yours)")
    info(".sage/config.yaml  (multi_agent block removed)")
    info("CLAUDE.md  (multi-agent section removed)")
    print(f"  {C.D}.sage/work/  is never touched.{C.R}")

    ans = confirm("[A] Remove  |  [C] Cancel", default="A", yes=yes).upper()
    if ans.startswith("C"):
        warn("Cancelled.")
        return 7

    # Backup user-owned content before deleting
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = project_dir / ".sage" / f".removed-multi-agent-{stamp}"
    print()
    any_backup = False
    for _, dst in user_pairs:
        if dst.exists():
            rel = dst.relative_to(project_dir)
            target = backup_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(target))
            any_backup = True
            ok(f"{rel}  → {target.relative_to(project_dir)}")
    if any_backup:
        info(f"backup at {backup_dir.relative_to(project_dir)}/")

    # Framework-owned deletes
    for _, dst in fw_pairs:
        if dst.exists():
            dst.unlink()
            ok(f"{dst.relative_to(project_dir)}  (deleted)")

    # Empty .sage/prompts/, .sage/scripts/, .sage/docs/ if no other content
    for sub in ("prompts", "scripts", "docs"):
        d = project_dir / ".sage" / sub
        if d.is_dir():
            remaining = [p for p in d.iterdir() if p.name != ".gitkeep"]
            if not remaining:
                d.rmdir()
                ok(f".sage/{sub}/  (empty — removed)")
    # Same for .claude/{commands,agents}/ — only remove if multi-agent was the sole occupant.
    # We leave these alone since the platform generator likely owns them.

    # Settings prune
    snippet_path = framework_dir / "runtime" / "multi-agent" / "settings.snippet.json"
    settings_path = project_dir / ".claude" / "settings.json"
    removed = prune_settings_json(settings_path, snippet_path)
    if removed:
        ok(f".claude/settings.json  (pruned {len(removed)} bash patterns)")

    # Config remove
    remove_multi_agent_config(config_path)
    ok(".sage/config.yaml  (multi_agent block removed)")

    # CLAUDE.md
    claude_md = project_dir / "CLAUDE.md"
    if remove_claude_section(claude_md):
        ok("CLAUDE.md  (multi-agent section removed)")

    print(f"\n  {C.B}Removed.{C.R}  /build still works as the in-session cycle.\n")
    return 0


def cmd_refresh(framework_dir: Path, project_dir: Path, *, yes: bool, force: bool) -> int:
    """Refresh framework-owned files from the template. Called by `sage update`.

    User-owned files (agents.toml, prompts/) are never touched.
    For each framework-owned file:
      - if deployed hash == prior-version's expected hash → safe overwrite
      - if deployed hash != prior-version's hash → drift; prompt unless --force
    """
    manifest = load_manifest(framework_dir)
    sage_version = detect_sage_version(framework_dir)
    config_path = project_dir / ".sage" / "config.yaml"
    existing = read_multi_agent_config(config_path)
    if not existing or existing.get("enabled") != "true":
        # Not installed in this project — nothing to do.
        return 0

    print(f"\n  {C.B}Refreshing multi-agent files{C.R}  (template → project)\n")
    fw_pairs = framework_owned_pairs(manifest, framework_dir, project_dir)
    deployed_to_meta = {k: v for k, v in manifest["framework_owned"].items()}

    for src, dst in fw_pairs:
        deployed_rel = str(dst.relative_to(project_dir))
        expected_hash = deployed_to_meta[deployed_rel]["sha256"]

        # If the file isn't deployed at all, just install it.
        if not dst.exists():
            copy_template(src, dst, render=False, sage_version=sage_version)
            if dst.suffix == ".sh":
                os.chmod(dst, 0o755)
            ok(f"{deployed_rel}  (installed)")
            continue

        current_hash = sha256_of(dst)
        template_hash = sha256_of(src)

        if current_hash == template_hash:
            ok(f"{deployed_rel}  (up to date)")
            continue

        if current_hash == expected_hash:
            # Deployed matches what we last shipped; safe to overwrite.
            copy_template(src, dst, render=False, sage_version=sage_version)
            if dst.suffix == ".sh":
                os.chmod(dst, 0o755)
            ok(f"{deployed_rel}  (refreshed)")
            continue

        # Drift: deployed differs from both template AND last-shipped.
        if force:
            backup = dst.with_suffix(dst.suffix + f".replaced-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}")
            shutil.copy2(dst, backup)
            copy_template(src, dst, render=False, sage_version=sage_version)
            if dst.suffix == ".sh":
                os.chmod(dst, 0o755)
            warn(f"{deployed_rel}  (forced replace; backup at {backup.name})")
            continue

        if yes:
            # Non-interactive without --force → preserve local edits.
            ok(f"{deployed_rel}  (kept — local edits, --force to overwrite)")
            continue

        print(f"  {C.Y}↺{C.R} {deployed_rel}  (locally modified)")
        ans = ""
        try:
            ans = input(f"    [K]eep yours  |  [R]eplace with template  |  [D]iff first  > ").strip().upper()
        except EOFError:
            ans = "K"
        if ans.startswith("D"):
            try:
                subprocess.run(["diff", "-u", str(dst), str(src)], check=False)
            except FileNotFoundError:
                warn("diff not on PATH; skipping")
            try:
                ans = input(f"    [K]eep yours  |  [R]eplace with template  > ").strip().upper()
            except EOFError:
                ans = "K"
        if ans.startswith("R"):
            backup = dst.with_suffix(dst.suffix + f".replaced-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}")
            shutil.copy2(dst, backup)
            copy_template(src, dst, render=False, sage_version=sage_version)
            if dst.suffix == ".sh":
                os.chmod(dst, 0o755)
            ok(f"{deployed_rel}  (replaced; backup at {backup.name})")
        else:
            ok(f"{deployed_rel}  (kept)")

    # Bump installed_version
    write_multi_agent_config(config_path, version=sage_version)

    # Refresh CLAUDE.md section if missing (e.g., generator regenerated CLAUDE.md and lost it).
    claude_md = project_dir / "CLAUDE.md"
    if append_claude_section(claude_md):
        ok("CLAUDE.md  (multi-agent section re-appended)")

    print(f"\n  {C.G}Multi-agent refresh complete.{C.R}\n")
    return 0


def cmd_status(framework_dir: Path, project_dir: Path) -> int:
    config_path = project_dir / ".sage" / "config.yaml"
    existing = read_multi_agent_config(config_path)
    if not existing:
        print("multi-agent: not installed")
        return 0
    print(f"multi-agent: enabled={existing.get('enabled')} version={existing.get('installed_version', '?')}")
    return 0


# ── Entry point ───────────────────────────────────────────────────────
def main() -> int:
    p = argparse.ArgumentParser(prog="multi_agent_setup")
    p.add_argument("subcommand", choices=("install", "remove", "refresh", "status"))
    p.add_argument("framework_dir")
    p.add_argument("project_dir")
    p.add_argument("--yes", action="store_true", help="bypass confirmation prompts")
    p.add_argument("--force", action="store_true", help="overwrite locally-modified framework files")
    args = p.parse_args()

    framework_dir = Path(args.framework_dir).resolve()
    project_dir = Path(args.project_dir).resolve()

    if args.subcommand == "install":
        return cmd_install(framework_dir, project_dir, yes=args.yes, force=args.force)
    if args.subcommand == "remove":
        return cmd_remove(framework_dir, project_dir, yes=args.yes)
    if args.subcommand == "refresh":
        return cmd_refresh(framework_dir, project_dir, yes=args.yes, force=args.force)
    if args.subcommand == "status":
        return cmd_status(framework_dir, project_dir)
    return 2


if __name__ == "__main__":
    sys.exit(main())
