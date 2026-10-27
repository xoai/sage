#!/usr/bin/env python3
"""
claude_settings.py — merge Sage's hook entries into a Claude Code settings file
without ever losing what the user put there. Python 3.8+ stdlib only.

WHY THIS EXISTS

`.claude/settings.local.json` is where Claude Code saves the user's "don't ask
again" permission answers. `sage update` used to overwrite it wholesale, so those
answers vanished and the prompts came back after every update; `settings.json`
was merged, but a file that failed to parse was silently treated as empty and
rewritten (review 2026-10-26, C4). One policy for both files now:

  - missing, empty or whitespace-only → start from {}  (nothing to lose)
  - not valid JSON, or not an object  → REFUSE: exit 3, file untouched
  - our old entries (any command naming one of our scripts) are replaced, never
    duplicated; every other key and hook entry is kept as it was
  - written atomically, keeping the file's mode, and through a symlink rather
    than over it

Usage:
    python3 claude_settings.py session  <settings.local.json>
    python3 claude_settings.py enforce  <settings.json>
    python3 claude_settings.py enforce-unshipped <settings.json>  # plugin on:
                                 # ours minus what the plugin ships
    python3 claude_settings.py strip-session|strip-shipped <file>  # remove ours
    python3 claude_settings.py plugin   <project>   # exit 0 + level if the plugin is on
    python3 claude_settings.py plugin-project <project>  # exit 0 if the project's
                                 # committed settings.json enables it
Exit: 0 merged · 3 refused (unreadable or not a JSON object) · 2 bad invocation
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from typing import Dict, List, Tuple

HOOK_CMD = 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/%s"'

SESSION: List[Tuple[str, str, str]] = [
    ("SessionStart", "startup|resume|clear|compact", "sage-session-init.sh"),
]

# (settings event, matcher, script) — the enforcement hooks, committed with the
# repo in settings.json because enforcement is project policy.
ENFORCE: List[Tuple[str, str, str]] = [
    ("PreToolUse", "Edit|Write|MultiEdit", "sage-spec-gate.sh"),
    ("PreToolUse", "Edit|Write|MultiEdit", "sage-tdd-gate.sh"),
    ("PreToolUse", "Edit|Write|MultiEdit", "sage-bookkeeping-gate.sh"),
    ("PreToolUse", "Edit|Write|MultiEdit", "sage-secrets-gate.sh"),
    ("PreToolUse", "Edit|Write|MultiEdit", "sage-branch-gate.sh"),   # X4
    ("PreToolUse", "Bash", "sage-verify-gate.sh"),
    ("PreToolUse", "Bash", "sage-bash-write-gate.sh"),   # a shell write is an edit (X1)
    ("PostToolUse", "Bash|Edit|Write|MultiEdit", "sage-verify-tracker.sh"),
    ("PreToolUse", "Bash|Edit|Write|MultiEdit", "sage-config-gate.sh"),
    ("PreToolUse", "Edit|Write|MultiEdit", "sage-scope-gate.sh"),
    ("PostToolUse", "Write|Edit", "sage-degradation-log.sh"),
    ("PostToolUse", "Write|Edit", "sage-manifest-sync.sh"),
    ("PostToolUse", "Bash|Edit|Write|MultiEdit", "sage-scope-journal.sh"),
]


class Refused(Exception):
    pass


def load(path: str) -> Dict:
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise Refused(f"cannot read: {exc}")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise Refused(f"not valid JSON ({exc})")
    if not isinstance(data, dict):
        raise Refused("not a JSON object")
    return data


def merge(data: Dict, wanted: List[Tuple[str, str, str]]) -> Dict:
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise Refused('"hooks" is not an object')
    for event, matcher, script in wanted:
        entries = hooks.get(event, [])
        if not isinstance(entries, list):
            raise Refused(f'"hooks.{event}" is not a list')

        def is_ours(entry, _script=script):
            if not isinstance(entry, dict):
                return False
            return any(isinstance(h, dict) and _script in (h.get("command") or "")
                       for h in entry.get("hooks") or [])

        entries = [e for e in entries if not is_ours(e)]
        entries.append({
            "matcher": matcher,
            "hooks": [{"type": "command", "command": HOOK_CMD % script}],
        })
        hooks[event] = entries
    return data


def write(path: str, data: Dict) -> None:
    # Through a symlink, not over it; with the file's own mode, not mkstemp's 0600.
    real = os.path.realpath(path)
    try:
        mode = stat.S_IMODE(os.stat(real).st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    d = os.path.dirname(real) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sage-settings.", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.chmod(tmp, mode)
        os.replace(tmp, real)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# The hook scripts the Sage plugin registers itself (runtime/plugin-overlay/
# hooks/hooks.json — build_plugin.py --check holds the two lists equal). With
# the plugin on, `sage init` registers only what the plugin does NOT ship (the
# scope gate and journal), so nothing fires twice and nothing goes missing.
PLUGIN_SHIPS = frozenset({
    "sage-session-init.sh", "sage-spec-gate.sh", "sage-tdd-gate.sh",
    "sage-bookkeeping-gate.sh", "sage-secrets-gate.sh", "sage-branch-gate.sh",
    "sage-verify-gate.sh", "sage-bash-write-gate.sh", "sage-config-gate.sh",
    "sage-degradation-log.sh", "sage-manifest-sync.sh", "sage-verify-tracker.sh",
})


def plugin_state(project: str) -> Tuple[bool, str]:
    """(enabled, level) for the Sage plugin in this project, by Claude Code's
    precedence: the project's local settings, then its committed settings,
    then the user's. The first file that names the plugin decides; one that
    cannot be read stops the search (unknown → treated as off: never strip on
    a guess). level is "local" | "project" | "user" | "" (not named).
    (review 2026-10-26, C5)"""
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude")
    for level, path in (("local", os.path.join(project, ".claude", "settings.local.json")),
                        ("project", os.path.join(project, ".claude", "settings.json")),
                        ("user", os.path.join(home, "settings.json"))):
        try:
            data = load(path)
        except Refused:
            return False, ""
        plugins = data.get("enabledPlugins")
        if not isinstance(plugins, dict):
            continue
        named = [v for k, v in plugins.items() if str(k).split("@")[0] == "sage"]
        if named:
            return named[0] is True, level
    return False, ""


def project_enables_plugin(project: str) -> bool:
    """Whether the committed .claude/settings.json enables the plugin — the
    team's choice, which alone decides what Sage writes to that shared file.
    One person's local or user setting must never reshape it for everyone."""
    try:
        data = load(os.path.join(project, ".claude", "settings.json"))
    except Refused:
        return False
    plugins = data.get("enabledPlugins")
    if not isinstance(plugins, dict):
        return False
    named = [v for k, v in plugins.items() if str(k).split("@")[0] == "sage"]
    return bool(named) and named[0] is True


def strip(data: Dict, wanted: List[Tuple[str, str, str]]) -> Dict:
    """Remove Sage's own hook entries (the plugin registers them instead)."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return data
    scripts = {w[2] for w in wanted}
    for event in list(hooks):
        entries = hooks[event]
        if not isinstance(entries, list):
            raise Refused('"hooks.%s" is not a list' % event)
        kept = [e for e in entries if not (isinstance(e, dict) and any(
            isinstance(h, dict) and any(sc in (h.get("command") or "") for sc in scripts)
            for h in e.get("hooks") or []))]
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks:
        del data["hooks"]
    return data


def main(argv: List[str]) -> int:
    if len(argv) == 2 and argv[0] == "plugin":
        enabled, level = plugin_state(argv[1])
        print(level if enabled else "")
        return 0 if enabled else 1
    if len(argv) == 2 and argv[0] == "plugin-project":
        return 0 if project_enables_plugin(argv[1]) else 1
    if len(argv) != 2 or argv[0] not in ("session", "enforce", "enforce-unshipped",
                                         "strip-session", "strip-shipped"):
        print(__doc__.split("Usage:")[1].split("Exit:")[0].rstrip(), file=sys.stderr)
        return 2
    kind, path = argv
    shipped = [w for w in SESSION + ENFORCE if w[2] in PLUGIN_SHIPS]
    unshipped = [w for w in ENFORCE if w[2] not in PLUGIN_SHIPS]
    try:
        data = load(path)
        if kind.startswith("strip-"):
            if not data:
                return 0
            data = strip(data, SESSION if kind == "strip-session" else shipped)
        elif kind == "enforce-unshipped":
            data = merge(strip(data, shipped) if data else data, unshipped)
        else:
            data = merge(data, SESSION if kind == "session" else ENFORCE)
    except Refused as exc:
        print(f"    {path}: {exc} — left untouched.", file=sys.stderr)
        return 3
    write(path, data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
