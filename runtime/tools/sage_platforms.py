#!/usr/bin/env python3
"""
sage_platforms.py — shared platform-detection helper for Sage's Python
tools.

Both `multi_agent_setup.py` and `memory_sync.py` need to answer "is
this a Claude Code project?" and "what platforms does this project
target?". Before this module each tool reimplemented that — divergently
and incorrectly (a single-line `platforms:` grep that fails on
pre-v1.1.3 configs with no `platforms:` key and on block-style YAML
lists). This module is the single source of truth so the logic cannot
drift again.

Pure stdlib — no PyYAML. `config.yaml` parsing is hand-rolled but
format-agnostic (inline list, block list, bare scalar, same-line
comments, CRLF, absent key).

Public surface:
    read_platforms(project_dir: Path) -> list[str]
    detect_claude_code(project_dir: Path) -> bool
    detect_hermes(project_dir: Path) -> bool

Spec: .sage/work/20260521-platform-detection-fix/spec.md §4.1.
"""
from __future__ import annotations

import json
from pathlib import Path


def _strip_comment(text: str) -> str:
    """Drop a same-line `# ...` comment and surrounding whitespace.

    A platform slug never contains `#`, so cutting at the first `#` is
    correct here (no need to track quoting)."""
    hash_pos = text.find("#")
    if hash_pos != -1:
        text = text[:hash_pos]
    return text.strip()


def _strip_token(tok: str) -> str:
    """Strip whitespace and one optional matching pair of surrounding
    quotes from a single list element."""
    tok = tok.strip()
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in ('"', "'"):
        tok = tok[1:-1]
    return tok.strip()


def _parse_inline(value: str) -> list[str]:
    """Parse an inline `platforms:` value into a list. Handles a flow
    list (`["a", "b"]`), a bracketless comma list (`a, b`), and a bare
    scalar (`a`). `value` must already have its comment stripped."""
    # Strip one optional surrounding [ ... ] pair.
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [t for t in (_strip_token(p) for p in value.split(",")) if t]


def read_platforms(project_dir: Path) -> list[str]:
    """Return the platform slugs listed in `.sage/config.yaml`'s
    `platforms:` key, or `[]` if the key / file is absent or the value
    is empty.

    Format-agnostic: inline flow list, bracketless comma list, bare
    scalar, block list — with optional same-line comments, and LF or
    CRLF line endings. The `platforms:` key is recognised ONLY at
    column 0; an indented `platforms:` is a nested sub-key and is
    ignored. Never raises — returns a best-effort list.
    """
    config_path = project_dir / ".sage" / "config.yaml"
    try:
        if not config_path.is_file():
            return []
        # splitlines() handles both LF and CRLF; split("\n") would not.
        lines = config_path.read_text(errors="replace").splitlines()
    except OSError:
        return []

    try:
        for i, line in enumerate(lines):
            # Column-0 anchor: must literally start with "platforms:".
            if not line.startswith("platforms:"):
                continue

            value = _strip_comment(line[len("platforms:"):])
            if value:
                return _parse_inline(value)

            # Empty value → block form. The block continues through
            # blank lines and whitespace-led lines; it ends at the
            # first line with a non-whitespace char at column 0.
            items: list[str] = []
            for cont in lines[i + 1:]:
                if cont and not cont[0].isspace():
                    break  # next top-level key
                stripped = cont.strip()
                if stripped.startswith("-"):
                    item = _strip_token(_strip_comment(stripped[1:]))
                    if item:
                        items.append(item)
                # blank or indented non-"-" (e.g. a comment) → skip
            return items

        return []  # no platforms: key
    except Exception:
        # Detection, not validation — never raise on a malformed file.
        return []


def detect_claude_code(project_dir: Path) -> bool:
    """Return True if `project_dir` is a Claude Code project.

    Precedence (any one suffices):
      1. `.claude/` directory exists — the strongest signal, and the
         multi-agent install target.
      2. `CLAUDE.md` exists and its literal first line contains "Sage"
         (a Sage-generated CLAUDE.md). Matches `bin/sage`
         select_platform()'s `head -1 ... | grep -q "Sage"`.
      3. `claude-code` appears in `read_platforms()`.
    """
    if (project_dir / ".claude").is_dir():
        return True

    claude_md = project_dir / "CLAUDE.md"
    try:
        if claude_md.is_file():
            lines = claude_md.read_text(errors="replace").splitlines()
            if lines and "Sage" in lines[0]:
                return True
    except OSError:
        pass

    return "claude-code" in read_platforms(project_dir)


def detect_hermes(project_dir: Path) -> bool:
    """Return True when project state or a generated marker targets Hermes."""

    if "hermes" in read_platforms(project_dir):
        return True

    agents = project_dir / "AGENTS.md"
    try:
        if agents.is_file() and "BEGIN SAGE HERMES GENERATED" in agents.read_text(
            encoding="utf-8", errors="replace"
        ):
            return True
    except OSError:
        pass

    catalog = project_dir / ".sage" / "runtime" / "route-catalog.json"
    try:
        if catalog.is_file():
            loaded = json.loads(catalog.read_text(encoding="utf-8-sig"))
            return isinstance(loaded, dict) and loaded.get("platform") == "hermes"
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass

    return False


# ── Self-test ─────────────────────────────────────────────────────────
# Runnable directly: `python3 runtime/tools/sage_platforms.py`.
# Exercises every read_platforms shape from spec §4.1 plus malformed
# inputs, and detect_claude_code's signals.
if __name__ == "__main__":
    import sys
    import tempfile

    failures: list[str] = []

    def _check(label: str, got, want) -> None:
        if got != want:
            failures.append(f"  ✗ {label}\n      got:  {got!r}\n      want: {want!r}")
        else:
            print(f"  ✓ {label}")

    def _project(config_text: str | None) -> Path:
        """Make a temp project; write config.yaml only if text is given."""
        d = Path(tempfile.mkdtemp())
        (d / ".sage").mkdir()
        if config_text is not None:
            (d / ".sage" / "config.yaml").write_text(config_text)
        return d

    print("read_platforms — config shapes:")

    _check("inline flow list",
           read_platforms(_project('platforms: ["claude-code", "codex"]\n')),
           ["claude-code", "codex"])
    _check("inline list, bare/unquoted",
           read_platforms(_project("platforms: [claude-code]\n")),
           ["claude-code"])
    _check("inline list, single-quoted",
           read_platforms(_project("platforms: ['claude-code']\n")),
           ["claude-code"])
    _check("bare scalar",
           read_platforms(_project("platforms: claude-code\n")),
           ["claude-code"])
    _check("block list",
           read_platforms(_project(
               "project-name: x\nplatforms:\n  - claude-code\n  - codex\n"
               "auto_review: true\n")),
           ["claude-code", "codex"])
    _check("inline list, same-line comment",
           read_platforms(_project("platforms: [claude-code]  # note\n")),
           ["claude-code"])
    _check("block item, same-line comment",
           read_platforms(_project("platforms:\n  - claude-code  # primary\n")),
           ["claude-code"])
    _check("bare scalar, comment with no space",
           read_platforms(_project("platforms: claude-code# weird\n")),
           ["claude-code"])
    _check("block list w/ internal blank + comment line",
           read_platforms(_project(
               "platforms:\n  - claude-code\n\n  # a comment\n  - codex\n"
               "auto_review: true\n")),
           ["claude-code", "codex"])
    _check("CRLF line endings",
           read_platforms(_project('platforms: ["claude-code"]\r\nx: 1\r\n')),
           ["claude-code"])
    _check("CRLF block list",
           read_platforms(_project(
               "platforms:\r\n  - claude-code\r\n  - codex\r\nx: 1\r\n")),
           ["claude-code", "codex"])
    _check("empty value, no block items",
           read_platforms(_project("platforms:\nauto_review: true\n")),
           [])
    _check("key absent",
           read_platforms(_project("project-name: x\nauto_review: true\n")),
           [])
    _check("config.yaml absent",
           read_platforms(_project(None)),
           [])
    # The round-1 BLOCKER class: a nested platforms: sub-key must NOT
    # be read as the top-level list.
    _check("nested platforms: sub-key is ignored",
           read_platforms(_project(
               "memory:\n  platforms:\n    - antigravity\n")),
           [])
    _check("nested sub-key ignored, real key still found",
           read_platforms(_project(
               "memory:\n  platforms:\n    - antigravity\n"
               'platforms: ["claude-code"]\n')),
           ["claude-code"])

    print("\nread_platforms — malformed inputs must not raise:")
    for label, text in [
        ("truncated bracket", "platforms: [claude-code\n"),
        ("stray quotes", 'platforms: "][\n'),
        ("tab-indented block", "platforms:\n\t- claude-code\n"),
        ("only a dash", "platforms:\n  -\n"),
        ("binary-ish junk", "platforms: \x00\x01\n"),
    ]:
        try:
            result = read_platforms(_project(text))
            print(f"  ✓ {label} → {result!r} (no raise)")
        except Exception as e:  # noqa: BLE001
            failures.append(f"  ✗ {label} raised {type(e).__name__}: {e}")

    print("\ndetect_claude_code — signals:")

    # Signal 1: .claude/ dir only (no config.yaml at all).
    p = _project(None)
    (p / ".claude").mkdir()
    _check("signal 1: .claude/ dir, no config.yaml", detect_claude_code(p), True)

    # Signal 2: Sage CLAUDE.md, no .claude/, no config.yaml.
    p = _project(None)
    (p / "CLAUDE.md").write_text("# My Project — powered by Sage\n\nstuff\n")
    _check("signal 2: Sage CLAUDE.md first line", detect_claude_code(p), True)

    # Signal 2 negative: CLAUDE.md whose FIRST line lacks "Sage".
    p = _project(None)
    (p / "CLAUDE.md").write_text("# My Project\n\nSage appears later\n")
    _check("signal 2: 'Sage' only on a later line → not matched",
           detect_claude_code(p), False)

    # Signal 3: block-list config names claude-code, no .claude/.
    _check("signal 3: block-list platforms only",
           detect_claude_code(_project("platforms:\n  - claude-code\n")), True)

    # Genuine negative.
    _check("negative: antigravity-only, no .claude/, no Sage CLAUDE.md",
           detect_claude_code(_project('platforms: ["antigravity"]\n')), False)

    print("\ndetect_hermes — signals:")
    _check("Hermes block-list platform",
           detect_hermes(_project("platforms:\n  - hermes\n")), True)
    _check("Hermes absent",
           detect_hermes(_project('platforms: ["claude-code"]\n')), False)

    print()
    if failures:
        print(f"FAIL — {len(failures)} self-test assertion(s):")
        for f in failures:
            print(f)
        sys.exit(1)
    print("OK — sage_platforms self-test passed.")
    sys.exit(0)
