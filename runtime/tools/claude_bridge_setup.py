#!/usr/bin/env python3
"""claude_bridge_setup.py — install, run, inspect and remove the opencode →
Claude Code bridge as a supervised user service. Invoked by
`sage setup claude-bridge` (bin/sage). Python 3.8+, stdlib only.

    claude_bridge_setup.py install  <framework> [--port N]
    claude_bridge_setup.py status   <framework> [--port N]
    claude_bridge_setup.py remove   <framework> [--purge]
    claude_bridge_setup.py restart  <framework>          (sage upgrade)
    claude_bridge_setup.py render   <framework> --os linux|macos [--port N]

Service managers: systemd user unit on Linux/WSL, launchd LaunchAgent on
macOS. The bridge CODE runs from the framework (so `sage upgrade` updates it;
`restart` makes the service pick it up); its STATE (token, log) lives in
SAGE_BRIDGE_STATE_DIR (default ~/.config/opencode/sage), which survives
installs, upgrades and removal (unless --purge).

Why the details are the way they are (brief.md, 20260927-claude-bridge-builtin):
  - PATH is captured at install time and written QUOTED (systemd) / as a
    plist dict (launchd): an unquoted PATH with a space-bearing dir made
    systemd truncate it and drop go/flutter for every Go project.
  - The service runs the installer's ABSOLUTE interpreter: macOS
    /usr/bin/python3 can be the CLT stub that pops an install dialog.
  - Install is verified by IDENTITY (/healthz code path + pid), never by "the
    port answers": a previous personal bridge may already listen there.

Exit codes: 0 ok | 1 failed | 2 bad invocation | 3 preflight failed |
            4 no supported service manager (use `sage setup claude-bridge --run`)
"""
from __future__ import annotations

import argparse
import datetime
import http.client
import json
import os
import pathlib
import plistlib
import re
import secrets
import shutil
import subprocess
import sys
import time

UNIT_NAME = "sage-claude-bridge.service"
LAUNCHD_LABEL = "dev.sage.claude-bridge"
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT = 1500          # seconds per Claude run (the wrapper's own default)
BRIDGE_REL = pathlib.Path("runtime/platforms/community/opencode/claude-bridge/claude-cli-bridge.py")
LEGACY_FILES = ("claude-cli-bridge.py", "sage-claude-implement.sh",
                "claude-implementer-shim.md", "last-request.json")
HOME = pathlib.Path.home()


def state_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get("SAGE_BRIDGE_STATE_DIR",
                                       str(HOME / ".config" / "opencode" / "sage")))


def unit_path() -> pathlib.Path:
    return HOME / ".config" / "systemd" / "user" / UNIT_NAME


def plist_path() -> pathlib.Path:
    return HOME / "Library" / "LaunchAgents" / (LAUNCHD_LABEL + ".plist")


# ── pure renders (tested on every OS) ──────────────────────────────────────

def systemd_quote(value: str) -> str:
    """Escape a value for a double-quoted systemd setting: `\\` is an escape
    and `%` a SPECIFIER inside Environment=/ExecStart= — a Windows PATH entry
    like %SystemRoot% (WSL imports the Windows PATH) would be silently
    rewritten (%S = the state dir), and `systemd-analyze verify` does not flag
    it. Quotes themselves are escaped too."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")


def render_unit(python: str, bridge: str, path_env: str, port: int, state_dir: str,
                timeout: int = DEFAULT_TIMEOUT) -> str:
    q = systemd_quote
    return "\n".join([
        "[Unit]",
        "Description=Sage claude-cli bridge (opencode -> claude -p)",
        "Documentation=https://github.com/xoai/sage/blob/main/docs/claude-bridge.md",
        "",
        "[Service]",
        'ExecStart="%s" "%s"' % (q(python), q(bridge)),
        "# PATH captured at install time and QUOTED: it may contain dirs with",
        "# spaces (WSL: /mnt/c/Program Files/...); unquoted, systemd truncates it.",
        'Environment="PATH=%s"' % q(path_env),
        'Environment="SAGE_BRIDGE_PORT=%d"' % port,
        'Environment="SAGE_CLAUDE_TIMEOUT=%d"' % timeout,
        'Environment="SAGE_BRIDGE_STATE_DIR=%s"' % q(state_dir),
        "Restart=on-failure",
        "RestartSec=3",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ])


def render_plist(python: str, bridge: str, path_env: str, port: int, state_dir: str,
                 timeout: int = DEFAULT_TIMEOUT) -> str:
    return plistlib.dumps({
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [python, bridge],
        "EnvironmentVariables": {"PATH": path_env,
                                 "SAGE_BRIDGE_PORT": str(port),
                                 "SAGE_CLAUDE_TIMEOUT": str(timeout),
                                 "SAGE_BRIDGE_STATE_DIR": state_dir},
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},       # restart on crash
        "ThrottleInterval": 5,
        "StandardOutPath": str(pathlib.Path(state_dir) / "launchd.out.log"),
        "StandardErrorPath": str(pathlib.Path(state_dir) / "launchd.err.log"),
    }).decode()


def opencode_snippet(port: int, state_dir: str) -> str:
    return """  "provider": {
    "claude-cli": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Claude CLI bridge",
      "options": {
        "baseURL": "http://127.0.0.1:%d/v1",
        "apiKey": "{file:%s/bridge.token}",
        "headerTimeout": false,
        "chunkTimeout": 600000
      },
      "models": { "sonnet": {}, "opus": {}, "haiku": {} }
    }
  },
  "agent": {
    "sage-implementer": { "mode": "subagent", "model": "claude-cli/sonnet" }
  }""" % (port, state_dir)


# ── state ──────────────────────────────────────────────────────────────────

def ensure_token(sdir: pathlib.Path) -> str:
    sdir.mkdir(parents=True, exist_ok=True)
    tok = sdir / "bridge.token"
    if not tok.exists():
        tok.write_text(secrets.token_hex(24) + "\n", encoding="utf-8")
    os.chmod(tok, 0o600)
    return tok.read_text(encoding="utf-8").strip()


def migrate_legacy(sdir: pathlib.Path) -> list:
    """A pre-built-in personal install kept its code in the state dir. Move
    those copies aside (never delete); the token and log stay put so the
    user's opencode.jsonc keeps working."""
    present = [sdir / n for n in LEGACY_FILES if (sdir / n).is_file()]
    if (sdir / "__pycache__").is_dir():           # bytecode of the legacy bridge
        present.append(sdir / "__pycache__")
    if not present:
        return []
    dest = sdir / ("legacy-" + datetime.date.today().isoformat())
    dest.mkdir(exist_ok=True)
    moved = []
    for p in present:
        target = dest / p.name
        p.rename(target)
        moved.append(str(target))
    return moved


def config_wired(config: pathlib.Path, port: int) -> bool:
    """Does the opencode config define a claude-cli provider on this port?
    A text check on purpose — the file is JSONC (comments), and we never
    rewrite it."""
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return False
    return ('"claude-cli"' in text
            and ("127.0.0.1:%d/v1" % port) in text)


def opencode_config() -> pathlib.Path:
    for name in ("opencode.jsonc", "opencode.json"):
        p = HOME / ".config" / "opencode" / name
        if p.exists():
            return p
    return HOME / ".config" / "opencode" / "opencode.jsonc"


# ── service managers ───────────────────────────────────────────────────────

def run(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def service_os() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        if shutil.which("systemctl") and run(["systemctl", "--user", "show-environment"]).returncode == 0:
            return "linux"
        return "none"
    return "none"


def installed() -> bool:
    return unit_path().exists() or plist_path().exists()


def service_pid(osname: str):
    if osname == "linux":
        out = run(["systemctl", "--user", "show", "-p", "MainPID", "--value", UNIT_NAME]).stdout.strip()
        return int(out) if out.isdigit() and out != "0" else None
    if osname == "macos":
        for domain in launchd_domains():
            out = run(["launchctl", "print", "%s/%s" % (domain, LAUNCHD_LABEL)]).stdout
            m = re.search(r"^\s*pid = (\d+)", out, re.M)
            if m:
                return int(m.group(1))
    return None


def launchd_domains() -> list:
    # gui/<uid> needs a graphical login; CI runners and ssh-only Macs may
    # only have user/<uid>. Try both, in that order, everywhere.
    return ["gui/%d" % os.getuid(), "user/%d" % os.getuid()]


def apply_linux(unit_text: str) -> None:
    up = unit_path()
    up.parent.mkdir(parents=True, exist_ok=True)
    up.write_text(unit_text, encoding="utf-8")
    run(["systemctl", "--user", "daemon-reload"], check=True)
    run(["systemctl", "--user", "enable", UNIT_NAME], check=True)
    # restart, not start: an already-running (maybe legacy) bridge must be
    # replaced by the process this unit now describes
    run(["systemctl", "--user", "restart", UNIT_NAME], check=True)


def apply_macos(plist_text: str) -> None:
    pp = plist_path()
    pp.parent.mkdir(parents=True, exist_ok=True)
    for domain in launchd_domains():                       # replace any old copy
        run(["launchctl", "bootout", "%s/%s" % (domain, LAUNCHD_LABEL)])
    pp.write_text(plist_text, encoding="utf-8")
    errors = []
    for domain in launchd_domains():
        r = run(["launchctl", "bootstrap", domain, str(pp)])
        if r.returncode == 0:
            run(["launchctl", "enable", "%s/%s" % (domain, LAUNCHD_LABEL)])
            return
        errors.append("%s: %s" % (domain, (r.stderr or r.stdout).strip()))
    r = run(["launchctl", "load", "-w", str(pp)])          # pre-bootstrap launchd
    if r.returncode != 0:
        errors.append("load -w: %s" % (r.stderr or r.stdout).strip())
        raise RuntimeError("launchctl could not load %s — %s" % (pp, "; ".join(errors)))


def healthz(port: int, token: str):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        c.request("GET", "/healthz", headers={"Authorization": "Bearer " + token})
        r = c.getresponse()
        body = r.read()
        c.close()
        return json.loads(body) if r.status == 200 else None
    except (OSError, ValueError):
        return None


def verify(port: int, token: str, bridge: pathlib.Path, osname: str, wait=20.0):
    """Identity check: THIS framework's bridge answers, as the service's pid."""
    deadline = time.time() + wait
    last = None
    while time.time() < deadline:
        h = healthz(port, token)
        if h:
            last = h
            same_code = pathlib.Path(h.get("code", "")).resolve() == bridge.resolve()
            pid = service_pid(osname)
            if same_code and (pid is None or pid == h.get("pid")):
                return True, h
        time.sleep(0.5)
    return False, last


# ── commands ───────────────────────────────────────────────────────────────

def cmd_install(framework: pathlib.Path, port: int, osname: str,
                timeout: int = DEFAULT_TIMEOUT) -> int:
    bridge = (framework / BRIDGE_REL).resolve()
    if not bridge.is_file():
        print("✗ bridge not found in the framework: %s" % bridge)
        return 3
    if not shutil.which("claude"):
        print("✗ the `claude` CLI is not on PATH — install Claude Code first:")
        print("  https://docs.anthropic.com/en/docs/claude-code")
        return 3
    if osname == "none":
        print("✗ no supported service manager (systemd user session on Linux/WSL,")
        print("  launchd on macOS). On WSL, enable systemd in /etc/wsl.conf:")
        print("    [boot]\n    systemd=true")
        print("  then `wsl --shutdown` and reopen. Or run it in the foreground:")
        print("    sage setup claude-bridge --run")
        return 4
    sdir = state_dir()
    moved = migrate_legacy(sdir)
    token = ensure_token(sdir)
    python = os.path.realpath(sys.executable)
    path_env = os.environ.get("PATH", "/usr/bin:/bin")
    args = dict(python=python, bridge=str(bridge), path_env=path_env,
                port=port, state_dir=str(sdir), timeout=timeout)
    try:
        if osname == "linux":
            apply_linux(render_unit(**args))
        else:
            apply_macos(render_plist(**args))
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print("✗ could not start the service: %s" % exc)
        return 1
    ok, h = verify(port, token, bridge, osname)
    where = unit_path() if osname == "linux" else plist_path()
    if not ok:
        print("✗ the service did not come up as THIS bridge (%s)." % bridge)
        print("  healthz answered: %s" % (json.dumps(h) if h else "nothing"))
        print("  service file: %s — log: %s/bridge.log" % (where, sdir))
        return 1
    print("✓ claude-cli bridge running — pid %s, sage %s, port %d, run limit %ds"
          % (h["pid"], h.get("version"), port, timeout))
    print("  service: %s" % where)
    print("  state:   %s (bridge.token, bridge.log)" % sdir)
    for m in moved:
        print("  moved legacy file aside: %s" % m)
    cfg = opencode_config()
    if config_wired(cfg, port):
        print("✓ %s already defines the claude-cli provider on this port." % cfg)
    else:
        print("\n  Add this to %s (merge into the top-level object):\n" % cfg)
        print(opencode_snippet(port, str(sdir)))
    print("\n  Each project must also have sage's Claude Code hooks:")
    print("    sage update --platform opencode,claude-code")
    return 0


def cmd_status(framework: pathlib.Path, port: int, osname: str) -> int:
    bridge = (framework / BRIDGE_REL).resolve()
    sdir = state_dir()
    tok = sdir / "bridge.token"
    print("  service manager: %s" % {"linux": "systemd (user)", "macos": "launchd",
                                    "none": "none available"}[osname])
    print("  service file:    %s" % (unit_path() if unit_path().exists() else
                                     plist_path() if plist_path().exists() else "not installed"))
    h = healthz(port, tok.read_text().strip()) if tok.exists() else None
    if h:
        same = pathlib.Path(h.get("code", "")).resolve() == bridge
        print("  bridge:          answering on %d — pid %s, sage %s%s"
              % (port, h["pid"], h.get("version"),
                 "" if same else "  ⚠ NOT this framework's code: %s" % h.get("code")))
    else:
        print("  bridge:          not answering on port %d" % port)
    cfg = opencode_config()
    print("  opencode config: %s" % ("wired (%s)" % cfg if config_wired(cfg, port)
                                     else "NOT wired — run install to see the snippet"))
    return 0 if h else 1


def cmd_remove(purge: bool, osname: str) -> int:
    if unit_path().exists():
        run(["systemctl", "--user", "disable", "--now", UNIT_NAME])
        unit_path().unlink()
        run(["systemctl", "--user", "daemon-reload"])
        print("✓ removed %s" % UNIT_NAME)
    if plist_path().exists():
        for domain in launchd_domains():
            run(["launchctl", "bootout", "%s/%s" % (domain, LAUNCHD_LABEL)])
        run(["launchctl", "unload", "-w", str(plist_path())])      # legacy load
        plist_path().unlink()
        print("✓ removed %s" % plist_path())
    sdir = state_dir()
    if purge:
        for n in ("bridge.token", "bridge.log", "launchd.out.log", "launchd.err.log"):
            if (sdir / n).exists():
                (sdir / n).unlink()
        print("✓ purged token and logs from %s" % sdir)
    else:
        print("  kept %s (token, log) — `--remove --purge` deletes them" % sdir)
    print("  remember to remove the claude-cli provider from your opencode config.")
    return 0


def cmd_restart(osname: str) -> int:
    """After `sage upgrade`: make an installed service run the new code."""
    if osname == "linux" and unit_path().exists():
        return run(["systemctl", "--user", "restart", UNIT_NAME]).returncode
    if osname == "macos" and plist_path().exists():
        for domain in launchd_domains():
            if run(["launchctl", "kickstart", "-k",
                    "%s/%s" % (domain, LAUNCHD_LABEL)]).returncode == 0:
                return 0
        return 1
    return 0                                   # not installed: nothing to do


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="claude_bridge_setup")
    p.add_argument("cmd", choices=["install", "status", "remove", "restart", "render"])
    p.add_argument("framework", type=pathlib.Path)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help="seconds before a Claude run is stopped (default 1500)")
    p.add_argument("--purge", action="store_true")
    p.add_argument("--os", choices=["linux", "macos"])
    a = p.parse_args(argv)
    osname = service_os()
    if a.cmd == "install":
        if a.timeout < 60:
            print("✗ --timeout must be at least 60 seconds")
            return 2
        return cmd_install(a.framework, a.port, osname, a.timeout)
    if a.cmd == "status":
        return cmd_status(a.framework, a.port, osname)
    if a.cmd == "remove":
        return cmd_remove(a.purge, osname)
    if a.cmd == "restart":
        return cmd_restart(osname)
    bridge = str((a.framework / BRIDGE_REL).resolve())
    args = dict(python=os.path.realpath(sys.executable), bridge=bridge,
                path_env=os.environ.get("PATH", ""), port=a.port, state_dir=str(state_dir()))
    print(render_unit(**args) if (a.os or "linux") == "linux" else render_plist(**args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
