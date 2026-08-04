#!/usr/bin/env python3
"""agent_binding.py — which opencode agents did the USER bind a model to? (A6)

THE RULE (T4-rev2, extended per-role): on opencode, the agent is the model
routing, and model spend requires explicit designation. A role resolves to a
named agent ONLY when the user's opencode config defines that agent WITH a
`model` binding. An entry without a model is treated as unbound — dispatching
a named-but-modelless agent LOOKS routed while silently spending on the
primary ([V-E], proven live 2026-08-04: a modelless config agent dispatched
fine and inherited the session model). Unbound roles keep today's behavior:
dispatch as usual, inherit the session model, and say so in the record.

This is the deterministic half of the subagent role split
(sage-implementer / sage-task-reviewer / sage-branch-reviewer): the workflow
asks THIS tool which roles are bound, then dispatches accordingly — the
decision is read from config by code, never vibed from memory by the model.

TWIN NOTE: scope_judge.py carries the same reader specialized to
`sage-scope-judge` (its T4-rev2 resolver, shipped and pinned by its own 48
tests before this tool existed). The semantics must stay identical — brace-
matched flat read, project-then-global merge, allowlist sanitization,
modelless = unbound. test_agent_binding.py pins the two in PARITY on shared
fixtures; if you change the semantics here, that test tells you where else.

Usage:
    agent_binding.py <agent-name> [<agent-name> ...] [--root PATH]

Prints one line per BOUND agent: `<name>\t<model>`. Unbound names print
nothing. Exit 0 always — this is an informational read, and a broken config
must degrade to "nothing is bound", never to a blocked workflow.

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys


def _agent_model_in(text: str, name: str) -> str:
    """The named agent's model binding inside ONE opencode config file, or
    "". Brace-matched flat read — no JSON dependency; the nesting is real
    (agent blocks carry permission objects) but string-content braces are
    not a case an agent block has. The character allowlist matters wherever
    the model string later meets a shell."""
    m = re.search(r'"%s"\s*:\s*\{' % re.escape(name), text)
    if not m:
        return ""
    depth, start = 0, m.end() - 1
    for j in range(start, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                mm = re.search(r'"model"\s*:\s*"([^"]+)"', text[start:j + 1])
                if not mm:
                    return ""
                model = mm.group(1)
                return model if re.match(r"^[A-Za-z0-9._/:@-]+$", model) \
                    else ""
    return ""


def agent_model(name: str, root: pathlib.Path, environ=None) -> str:
    """The model the user bound to `name`, or "". Project config first,
    then the global one, mirroring opencode's per-key merge."""
    environ = os.environ if environ is None else environ
    cfg_home = pathlib.Path(environ.get("XDG_CONFIG_HOME")
                            or (pathlib.Path.home() / ".config"))
    for path in (root / "opencode.json", root / "opencode.jsonc",
                 cfg_home / "opencode" / "opencode.json",
                 cfg_home / "opencode" / "opencode.jsonc"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        model = _agent_model_in(text, name)
        if model:
            return model
    return ""


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = pathlib.Path.cwd()
    names = []
    i = 0
    while i < len(argv):
        if argv[i] == "--root" and i + 1 < len(argv):
            root = pathlib.Path(argv[i + 1])
            i += 2
            continue
        names.append(argv[i])
        i += 1
    if not names:
        print("usage: agent_binding.py <agent-name> [...] [--root PATH]",
              file=sys.stderr)
        return 0                       # informational tool: never blocks
    for name in names:
        try:
            model = agent_model(name, root)
        except Exception:
            model = ""                 # fail open, per header
        if model:
            print("%s\t%s" % (name, model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
