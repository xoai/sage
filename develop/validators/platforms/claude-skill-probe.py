#!/usr/bin/env python3
"""
claude-skill-probe.py — does REAL Claude Code register every skill `sage init`
generates? (review 2026-10-26, C2)

The deterministic checks (skill_frontmatter.py check-claude, generation-smoke.sh)
assert what we BELIEVE Claude Code accepts. This asks Claude Code itself: it
runs `sage init --platform claude-code` in a scratch project (once with default
skill names, once with `--prefix`), starts
`claude -p --output-format stream-json`, reads the session's `system/init`
event, and asserts every directory under .claude/skills/ is in its `skills`
list — and that /sage is a slash command, not shadowed by a skill.

The init event arrives before any model call, so the probe is killed as soon as
it has it: no credentials needed, no tokens spent, about a second. It runs
under a throwaway HOME so the developer's own skills and plugins cannot mask a
missing one.

Usage:  python3 develop/validators/platforms/claude-skill-probe.py
Exit:   0 = every skill registered | 1 = one did not | 0 with a LOUD skip when
        the `claude` CLI is not installed
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import List, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
INIT_TIMEOUT = 60


def init_event(project: pathlib.Path, home: pathlib.Path) -> Tuple[dict, str]:
    """The session's system/init event, and Claude's stderr (for diagnosis
    when there is no event)."""
    env = dict(os.environ, HOME=str(home))
    for k in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR"):
        env.pop(k, None)
    # stderr goes to a file, not a pipe nobody drains: a chatty CLI must not
    # block on a full pipe before it prints the event we are waiting for.
    with tempfile.TemporaryFile(mode="w+") as err:
        proc = subprocess.Popen(
            ["claude", "-p", "ok", "--output-format", "stream-json", "--verbose",
             "--max-turns", "1"],
            cwd=project, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=err, text=True)
        timer = threading.Timer(INIT_TIMEOUT, proc.kill)
        timer.start()
        event: dict = {}
        try:
            for line in proc.stdout:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("type") == "system" and ev.get("subtype") == "init":
                    event = ev
                    break
        finally:
            timer.cancel()
            proc.kill()
            proc.wait()
        err.seek(0)
        return event, err.read()[-2000:]


def probe(mode: str, extra_args: List[str]) -> List[str]:
    """`sage init` one scratch project in this mode and ask Claude Code about it."""
    with tempfile.TemporaryDirectory(prefix="sage-cc-probe-") as t:
        root = pathlib.Path(t)
        home, sage_home, proj = root / "home", root / "sage-home", root / "proj"
        for d in (home, sage_home, proj):
            d.mkdir()
        (sage_home / "framework").symlink_to(REPO_ROOT)
        subprocess.run(["git", "init", "-q", "."], cwd=proj, check=False)
        r = subprocess.run(
            ["bash", str(REPO_ROOT / "bin" / "sage"), "init", "--no-memory",
             "--platform", "claude-code", *extra_args],
            cwd=proj, env=dict(os.environ, SAGE_HOME=str(sage_home)),
            stdin=subprocess.DEVNULL, capture_output=True, text=True)
        if r.returncode != 0:
            return [f"sage init failed (exit {r.returncode})\n"
                    f"{r.stdout[-2000:]}{r.stderr[-2000:]}"]

        generated = sorted(p.name for p in (proj / ".claude" / "skills").iterdir() if p.is_dir())
        ev, stderr = init_event(proj, home)
        if not ev:
            return ["claude emitted no system/init event — cannot read its skill list"
                    + (f"\n  claude stderr (tail):\n{stderr}" if stderr.strip() else "")]
        registered = set(ev.get("skills") or [])
        commands = set(ev.get("slash_commands") or [])
        problems = [f"skill not registered by Claude Code: {s}"
                    for s in generated if s not in registered]
        if "sage" not in commands:
            problems.append("/sage is not a slash command")
        if "sage" in registered:
            problems.append("a skill named `sage` shadows the /sage command")
        if not problems:
            print(f"  ✓ {mode}: claude-code {ev.get('claude_code_version', '?')} registered "
                  f"all {len(generated)} generated skills; /sage reaches its command")
        return problems


def main() -> int:
    if not shutil.which("claude"):
        print("SKIPPED: the claude CLI is not installed — nothing to probe.", file=sys.stderr)
        return 0
    failed = 0
    # Both naming modes: `--prefix` writes every stub as `sage:<name>`.
    for mode, args in (("default", []), ("prefix", ["--prefix"])):
        problems = probe(mode, args)
        for p in problems:
            print(f"  ✗ {mode}: {p}")
        failed += len(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
