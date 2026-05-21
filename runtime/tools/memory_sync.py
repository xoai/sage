#!/usr/bin/env python3
"""
memory_sync.py — sage-memory integration helper.

Invoked by `sage upgrade`, `sage update`, `sage init` via bin/sage.
Pure Python 3.11+ stdlib only (no pip deps).

Responsibilities:
  detect         — print structured status about installed sage-memory
  upgrade        — prompt-and-upgrade if a newer version is on PyPI
  sync           — overlay wheel-canonical skills via `sage-memory install-skills`
  migrate-legacy — backup pre-v1.1.7 legacy skill dirs once (gated)

Spec contract: see .sage/work/20260519-sage-memory-integration/spec.md.
The helper is best-effort — sage's primary commands never fail because
of sage-memory side effects.

Exit codes (stable, see spec §4.3):
  0   success (including no-op when sage-memory absent)
  1   unexpected error
  2   bad invocation
  5   Python <3.11
  7   sage-memory CLI subprocess errored (forwarded)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Sibling helper in runtime/tools/ — resolvable because this script is
# invoked as `python3 .../runtime/tools/memory_sync.py`, so its own
# directory is sys.path[0].
from sage_platforms import read_platforms


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


# ── Constants ─────────────────────────────────────────────────────────
PYPI_URL = "https://pypi.org/pypi/sage-memory/json"
PYPI_TIMEOUT = 5  # seconds

# Sage platform name → sage-memory install-skills agent name
PLATFORM_TO_AGENT = {
    "claude-code": "claude-code",
    "codex":       "codex",
    "opencode":    "opencode",
    "gemini-cli":  "gemini",
    "cursor":      "cursor",
    # antigravity → no adapter; handled separately in sync
}

LEGACY_NAMES = ("memory", "ontology", "self-learning")


# ── Detection ─────────────────────────────────────────────────────────
def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a subprocess; return (returncode, stdout, stderr). Never raises."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 127, "", ""


def _detect_via_uv() -> str | None:
    """Return version if sage-memory is installed via uv, else None."""
    if not shutil.which("uv"):
        return None
    rc, out, _ = _run(["uv", "tool", "list"])
    if rc != 0:
        return None
    for line in out.splitlines():
        # `uv tool list` format: "sage-memory v0.9.0" or "sage-memory 0.9.0"
        m = re.match(r"^sage-memory\s+v?(\S+)", line.strip())
        if m:
            return m.group(1)
    return None


def _detect_via_pipx() -> str | None:
    """Return version if installed via pipx, else None."""
    if not shutil.which("pipx"):
        return None
    rc, out, _ = _run(["pipx", "list", "--short"])
    if rc != 0:
        return None
    for line in out.splitlines():
        m = re.match(r"^sage-memory\s+(\S+)", line.strip())
        if m:
            return m.group(1)
    return None


def _detect_via_pip() -> str | None:
    """Return version if `pip show sage-memory` succeeds, else None."""
    rc, out, _ = _run([sys.executable, "-m", "pip", "show", "sage-memory"])
    if rc != 0:
        return None
    for line in out.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return None


def _detect_unmanaged() -> str | None:
    """Last resort: sage-memory binary on PATH but not tracked by any manager."""
    if not shutil.which("sage-memory"):
        return None
    rc, out, _ = _run(["sage-memory", "--version"])
    if rc != 0:
        return None
    # Output shape varies — try to extract a version-like substring
    m = re.search(r"(\d+\.\d+\.\d+(?:[.-]\S+)?)", out)
    return m.group(1) if m else "unknown"


def _has_install_skills(method: str) -> bool:
    """Check whether the installed sage-memory has install-skills subcommand
    (added in v0.8.0). Probe by running --help and looking for the verb."""
    if method == "absent":
        return False
    rc, out, _ = _run(["sage-memory", "install-skills", "--help"])
    return rc == 0


def _pypi_latest() -> str:
    """Probe PyPI for the latest sage-memory version. Returns 'unknown' on
    any failure (offline, timeout, decode error). Hard 5s timeout."""
    try:
        with urllib.request.urlopen(PYPI_URL, timeout=PYPI_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("info", {}).get("version", "unknown") or "unknown"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
            UnicodeDecodeError, KeyError, OSError):
        return "unknown"


def detect_status() -> dict[str, str]:
    """Returns {status, method, version, latest_pypi, install_skills_cli}.

    Detection order: uv → pipx → pip → unmanaged. First hit wins.
    """
    version = _detect_via_uv()
    method = "uv" if version else None

    if not version:
        version = _detect_via_pipx()
        method = "pipx" if version else method

    if not version:
        version = _detect_via_pip()
        method = "pip" if version else method

    if not version:
        version = _detect_unmanaged()
        method = "unmanaged" if version else method

    if not version:
        return {
            "status": "absent",
            "method": "absent",
            "version": "none",
            "latest_pypi": "n/a",
            "install_skills_cli": "n/a",
        }

    return {
        "status": "installed",
        "method": method or "unknown",
        "version": version,
        "latest_pypi": _pypi_latest(),
        "install_skills_cli": "yes" if _has_install_skills(method or "") else "no",
    }


def cmd_detect(framework_dir: Path) -> int:
    info_dict = detect_status()
    for k in ("status", "method", "version", "latest_pypi", "install_skills_cli"):
        print(f"{k}: {info_dict[k]}")
    return 0


# ── Version comparison ────────────────────────────────────────────────
def _version_tuple(v: str) -> tuple[int, ...]:
    """Loose semver tuple for comparison. '0.9.0' → (0, 9, 0).
    Pre/post markers are dropped — we only care if X > Y at the numeric core.
    Returns (0,) for unparseable input so it never wins comparisons."""
    m = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", v)
    if not m:
        return (0,)
    return tuple(int(g or 0) for g in m.groups())


def _is_newer(latest: str, current: str) -> bool:
    if latest == "unknown" or current in ("none", "unknown"):
        return False
    return _version_tuple(latest) > _version_tuple(current)


# ── Upgrade ───────────────────────────────────────────────────────────
def cmd_upgrade(framework_dir: Path, yes: bool = False) -> int:
    s = detect_status()

    if s["status"] == "absent":
        print()
        info("sage-memory not installed (optional MCP server for persistent memory)")
        print(f"    {C.D}Setup: sage setup memory{C.R}")
        return 0

    version, latest, method = s["version"], s["latest_pypi"], s["method"]

    if latest == "unknown":
        print()
        info(f"sage-memory: {version} (PyPI version check unavailable; skipping upgrade prompt)")
        return 0

    if not _is_newer(latest, version):
        print()
        ok(f"sage-memory: {version} (up to date)")
        return 0

    print()
    info(f"sage-memory: {version} → {latest} available")

    if method != "uv":
        hint = {
            "pipx":      "pipx upgrade sage-memory",
            "pip":       f"{sys.executable} -m pip install --upgrade sage-memory",
            "unmanaged": "consult your install source",
        }.get(method, "consult your install source")
        print(f"    Installed via {method} — not managed by `sage upgrade`.")
        print(f"    To upgrade: {C.CYAN}{hint}{C.R}")
        return 0

    if yes:
        answer = "y"
    else:
        try:
            answer = input(f"    Upgrade? [Y/n]: ").strip().lower() or "y"
        except EOFError:
            answer = "y"

    if answer.startswith("n"):
        info("Skipped.")
        return 0

    rc, out, errout = _run(["uv", "tool", "upgrade", "sage-memory"], timeout=120)
    if out:
        for line in out.splitlines():
            print(f"    {line}")
    if rc != 0:
        if errout:
            err(errout.strip())
        warn("uv tool upgrade exited non-zero — sage upgrade continues")
        return 0
    ok(f"sage-memory upgraded to {latest}")
    return 0


# ── Sync ──────────────────────────────────────────────────────────────
def _has_prefix_mode(project_dir: Path) -> bool:
    config_path = project_dir / ".sage" / "config.yaml"
    if not config_path.exists():
        return False
    for line in config_path.read_text().splitlines():
        if line.strip().startswith("command_prefix:"):
            value = line.split(":", 1)[1].strip()
            return value.lower() == "true"
    return False


def cmd_sync(framework_dir: Path, project_dir: Path, yes: bool = False) -> int:
    s = detect_status()
    if s["status"] == "absent":
        return 0
    if s["install_skills_cli"] != "yes":
        print()
        info(f"sage-memory: {s['version']} — skill sync requires sage-memory >= 0.8.0 (current install lacks install-skills CLI); vendored fallback remains active")
        return 0

    if _has_prefix_mode(project_dir):
        print()
        info("prefix mode detected — skipping sage-memory skill sync (vendored fallback remains active)")
        return 0

    platforms = read_platforms(project_dir)
    if not platforms:
        return 0

    supported = []
    skipped_antigravity = False
    for p in platforms:
        if p in PLATFORM_TO_AGENT:
            supported.append((p, PLATFORM_TO_AGENT[p]))
        elif p == "antigravity":
            skipped_antigravity = True

    if not supported and not skipped_antigravity:
        return 0

    print()
    info("Refreshing sage-memory skills (wheel canonical)")

    if skipped_antigravity:
        print(f"    {C.D}antigravity: no adapter; vendored fallback active{C.R}")

    for platform, agent in supported:
        # Run sage-memory install-skills <agent> --project --yes inside project_dir
        rc, out, errout = _run(
            ["sage-memory", "install-skills", agent, "--project", "--yes"],
            timeout=60,
        )
        if rc != 0:
            warn(f".claude/skills/sage-*/ ({platform}): install-skills exit {rc}")
            if errout:
                for line in errout.strip().splitlines():
                    print(f"    {line}", file=sys.stderr)
            # Don't abort — continue to next platform
            continue
        ok(f"sage-memory skills refreshed for {platform}")

    return 0


# ── Config block helpers (merge-not-replace YAML editing) ─────────────
def _config_path(project_dir: Path) -> Path:
    return project_dir / ".sage" / "config.yaml"


def _read_memory_block(config_path: Path) -> dict[str, str]:
    """Return the memory: block's children as a flat dict (one level deep).
    Returns {} if config missing or block absent."""
    if not config_path.exists():
        return {}
    block: dict[str, str] = {}
    in_block = False
    for raw in config_path.read_text().splitlines():
        if raw.startswith("memory:"):
            in_block = True
            continue
        if in_block:
            if raw.startswith(" ") or raw.startswith("\t"):
                line = raw.strip()
                if ":" in line:
                    k, v = line.split(":", 1)
                    block[k.strip()] = v.strip().strip('"').strip("'")
            elif raw.strip() == "":
                # blank line still inside the block
                continue
            else:
                in_block = False
    return block


def update_memory_block(config_path: Path, key: str, value: Any) -> None:
    """Insert-or-replace a single key inside the memory: block. Preserves
    any other keys at the same indent level. Per spec §4.9.

    Edge cases:
    - Config file missing: create with a fresh memory: block.
    - Block missing: append a new memory: block.
    - Block present with other keys: merge (replace the named key only).
    - Malformed YAML: raise — never silently overwrite.
    """
    # Format value
    if isinstance(value, bool):
        formatted = "true" if value else "false"
    elif isinstance(value, str):
        formatted = f'"{value}"'
    else:
        formatted = str(value)

    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"memory:\n  {key}: {formatted}\n")
        return

    # Read existing memory block; preserve everything else
    existing = _read_memory_block(config_path)
    existing[key] = formatted.strip('"') if isinstance(value, str) else (
        "true" if value is True else ("false" if value is False else str(value))
    )

    # Re-emit: remove old block, append fresh block at the end
    lines = config_path.read_text().splitlines()
    out: list[str] = []
    in_block = False
    block_found = False
    for raw in lines:
        if raw.startswith("memory:"):
            in_block = True
            block_found = True
            continue
        if in_block:
            if raw.startswith(" ") or raw.startswith("\t") or raw.strip() == "":
                continue
            in_block = False
        out.append(raw)

    # Strip trailing blanks
    while out and out[-1] == "":
        out.pop()

    out.append("")
    out.append("memory:")
    for k, v in existing.items():
        # Re-quote strings that aren't 'true'/'false' or numeric
        if v in ("true", "false") or v.replace(".", "").replace("-", "").isdigit():
            out.append(f"  {k}: {v}")
        else:
            out.append(f'  {k}: "{v}"')

    config_path.write_text("\n".join(out) + "\n")


# ── Migrate legacy ────────────────────────────────────────────────────
def cmd_migrate_legacy(project_dir: Path) -> int:
    config_path = _config_path(project_dir)
    memory_block = _read_memory_block(config_path)
    if memory_block.get("legacy_migrated") == "true":
        return 0  # Already migrated; silent.

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = project_dir / ".sage" / f".legacy-skills-{stamp}"
    moved: list[str] = []

    for legacy in LEGACY_NAMES:
        path = project_dir / ".claude" / "skills" / legacy
        if path.is_dir() and (path / "SKILL.md").exists():
            # Lazy-create backup dir on first move only — avoids leaving
            # empty timestamp dirs on no-op runs (spec §4.6, R2-3/R2-7).
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(backup_dir / legacy))
            moved.append(legacy)

    if moved:
        print()
        info("Migration: backing up pre-v1.1.7 skill directories")
        ok(f"backed up legacy skill dirs to {backup_dir.relative_to(project_dir)}/ ({len(moved)} dirs)")

    # Always set the marker (even on no-op) so the scan never runs again.
    update_memory_block(config_path, "legacy_migrated", True)
    return 0


# ── Entry point ───────────────────────────────────────────────────────
def main() -> int:
    if sys.version_info < (3, 11):
        err(f"Python 3.11+ required (have {sys.version_info.major}.{sys.version_info.minor})")
        return 5

    p = argparse.ArgumentParser(prog="memory_sync")
    p.add_argument("subcommand",
                   choices=("detect", "upgrade", "sync", "migrate-legacy"))
    p.add_argument("framework_dir", nargs="?", default=".")
    p.add_argument("project_dir", nargs="?", default=".")
    p.add_argument("--yes", action="store_true",
                   help="bypass confirmation prompts (CI)")
    args = p.parse_args()

    framework_dir = Path(args.framework_dir).resolve()
    project_dir = Path(args.project_dir).resolve()

    if args.subcommand == "detect":
        return cmd_detect(framework_dir)
    if args.subcommand == "upgrade":
        return cmd_upgrade(framework_dir, yes=args.yes)
    if args.subcommand == "sync":
        return cmd_sync(framework_dir, project_dir, yes=args.yes)
    if args.subcommand == "migrate-legacy":
        # framework_dir not used by migrate-legacy; project_dir is the
        # second positional. bin/sage calls: `migrate-legacy <project_dir>`
        # so we accept either calling convention:
        #   memory_sync.py migrate-legacy <project_dir>
        #   memory_sync.py migrate-legacy <framework_dir> <project_dir>
        if args.project_dir == "." and args.framework_dir != ".":
            return cmd_migrate_legacy(framework_dir)
        return cmd_migrate_legacy(project_dir)

    return 2


if __name__ == "__main__":
    sys.exit(main())
