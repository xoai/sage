#!/usr/bin/env python3
"""
skill_frontmatter.py — read SKILL.md frontmatter correctly, and deploy Claude
Code loader stubs from it. Zero pip dependencies — Python 3.8+ stdlib only.

WHY THIS EXISTS

The Claude Code generator used to read a skill's description with
`sed -n '/^description:/...p' | head -1 | cut -c1-120`. That reads ONE line:

  - a folded description (`description: >` and the text on the lines below)
    came out empty, and the stub's `description:` was blank;
  - a quoted description longer than 120 characters lost its closing quote,
    which is invalid YAML.

Claude Code does not reject such a skill loudly. It just never registers it.
Nine of the thirty-three skills Sage shipped were silently missing on Claude Code
that way — sage-memory and the reviewer among them (review 2026-10-26, C2).

The same loop also copied every directory under skills/, including the Hermes
port of Sage's workflows (frontmatter `metadata: hermes:`). On Claude Code those
tell the model to call `delegate_task`, a tool it does not have — and the one
named `sage` shadowed the /sage command (C1).

So: one parser that understands the YAML a SKILL.md actually uses (plain, quoted,
folded and literal scalars; one level of nested mapping), one rule for which
skills a platform gets, and one writer that always emits valid YAML.

Usage (from the Claude Code generator):
    python3 skill_frontmatter.py deploy-claude <skills_dir> <out_dir> \\
        [--prefix sage:] [--skip NAME ...] [--source-rel sage/skills]
    python3 skill_frontmatter.py check-claude <out_dir>
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Claude Code's limit on a skill description. Longer ones are cut at a word
# boundary rather than mid-word, and the cut is marked.
MAX_DESCRIPTION = 1024

# Skills whose frontmatter declares one of these platforms under `metadata:` are
# that platform's port, written for its tools — never deployed to Claude Code.
FOREIGN_PLATFORMS = ("hermes",)

# Never deploy a skill with this name to Claude Code: a skill shadows a command
# of the same name, and /sage must reach the generated command.
RESERVED_NAMES = ("sage",)

_KEY = re.compile(r"^([A-Za-z_][\w-]*):(?:\s+(.*)|\s*)$")
_DQ = re.compile(r'^"((?:[^"\\]|\\.)*)"\s*(?:#.*)?$')
_SQ = re.compile(r"^'((?:[^']|'')*)'\s*(?:#.*)?$")
# A loader stub's whole body. Anything else in .claude/skills/ is not ours to remove.
_LOADER = re.compile(r"\ARead and follow the full skill at (\S+)/SKILL\.md\s*\Z")
# A plain YAML scalar may not START with these (YAML 1.2 §5.3 reserved and
# indicator characters that make PyYAML — and Claude Code — reject the file).
_BAD_PLAIN_START = tuple("@`%&*!|>{}")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _unquote(val: str) -> str:
    val = val.strip()
    m = _DQ.match(val)
    if m:
        try:
            return json.loads('"' + m.group(1) + '"')
        except ValueError:
            # YAML-only escapes (\_, \N …): keep the text, drop the backslashes.
            return re.sub(r"\\(.)", r"\1", m.group(1))
    m = _SQ.match(val)
    if m:
        return m.group(1).replace("''", "'")
    # A plain scalar ends at a comment.
    return re.sub(r"\s+#.*$", "", val)


def _block(lines: List[str], i: int, style: str, parent: int) -> Tuple[str, int]:
    """Read a block scalar starting at lines[i] whose key sits at indent `parent`;
    return (text, next index)."""
    body: List[str] = []
    indent: Optional[int] = None
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            body.append("")
            i += 1
            continue
        lead = _indent(line)
        if lead <= parent:
            break
        if indent is None:
            indent = lead
        if lead < indent:
            break
        body.append(line[indent:])
        i += 1
    while body and body[-1] == "":
        body.pop()
    if style.startswith("|"):
        return "\n".join(body), i
    # Folded: lines join with spaces; a blank line is a paragraph break.
    paras, cur = [], []
    for b in body:
        if b == "":
            if cur:
                paras.append(" ".join(cur))
                cur = []
        else:
            cur.append(b.strip())
    if cur:
        paras.append(" ".join(cur))
    return "\n".join(paras), i


def _frontmatter_lines(text: str) -> Optional[List[str]]:
    text = text.lstrip("﻿")
    m = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", text, re.S)
    return m.group(1).splitlines() if m else None


def parse_frontmatter(text: str) -> Dict[str, object]:
    """Top-level keys of a SKILL.md frontmatter.

    A scalar value comes back as a string; a nested mapping as a dict of its
    own keys (values parsed the same way). Unknown shapes (flow sequences and
    mappings, anchors) come back as their raw text — this reads skills, it is
    not a general YAML parser. lint_frontmatter() says when a file would not
    survive a real one.
    """
    lines = _frontmatter_lines(text)
    return _mapping(lines, 0)[0] if lines is not None else {}


def _mapping(lines: List[str], indent: int) -> Tuple[Dict[str, object], int]:
    out: Dict[str, object] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        lead = _indent(line)
        if lead < indent:
            break
        if lead > indent:
            i += 1                     # continuation of something we skipped
            continue
        km = _KEY.match(line[indent:])
        if not km:
            i += 1
            continue
        key, val = km.group(1), (km.group(2) or "").strip()
        i += 1
        if val[:1] in (">", "|"):
            out[key], i = _block(lines, i, val, indent)
        elif val == "":
            # Either a nested mapping or a plain scalar continued on the next lines.
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                nlead = _indent(lines[j])
                if nlead > indent and _KEY.match(lines[j][nlead:]):
                    sub, used = _mapping(lines[j:], nlead)
                    out[key] = sub
                    i = j + used
                    continue
                if nlead > indent:
                    out[key], i = _block(lines, i, ">", indent)
                    continue
            out[key] = ""
        else:
            # A plain or quoted scalar may continue on more-indented lines.
            parts = [val]
            while i < len(lines) and lines[i].strip() and _indent(lines[i]) > indent:
                parts.append(lines[i].strip())
                i += 1
            out[key] = _unquote(" ".join(parts))
    return out, i


def _flow_items(val: str) -> Optional[List[str]]:
    """The items of a one-line flow sequence, or None if it does not close."""
    inner = val[1:]
    m = re.match(r"^(.*)\]\s*(?:#.*)?$", inner)
    if not m:
        return None
    items, cur, q = [], "", ""
    for ch in m.group(1):
        if q:
            cur += ch
            if ch == q:
                q = ""
        elif ch in "\"'":
            q, cur = ch, cur + ch
        elif ch == ",":
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if q:
        return None
    if cur.strip():
        items.append(cur.strip())
    return items


def _scalar_problem(val: str) -> Optional[str]:
    if val[:1] == '"':
        return None if _DQ.match(val) else "unterminated double-quoted string"
    if val[:1] == "'":
        return None if _SQ.match(val) else "unterminated single-quoted string"
    if val.startswith(_BAD_PLAIN_START):
        return f"plain value starts with reserved {val[0]!r} — quote it"
    return None


def lint_frontmatter(text: str) -> List[str]:
    """Why a strict YAML reader (PyYAML, Claude Code) would reject this
    frontmatter — the shapes SKILL.md files have actually gotten wrong.
    Empty means none of the known failure shapes; it is not a full YAML
    validator."""
    if text.startswith("﻿"):
        return ["starts with a byte-order mark"]
    lines = _frontmatter_lines(text)
    if lines is None:
        return ["no frontmatter (--- … ---) at the top"]
    problems: List[str] = []
    block_parent: Optional[int] = None
    for n, line in enumerate(lines, 2):
        if not line.strip():
            continue
        lead = _indent(line)
        if block_parent is not None:
            if lead > block_parent:
                continue
            block_parent = None
        if "\t" in line[: len(line) - len(line.lstrip())]:
            problems.append(f"line {n}: tab in indentation")
            continue
        body = line.strip()
        if body.startswith("#"):
            continue
        if body.startswith("- "):
            body = body[2:].strip()
            km = _KEY.match(body)
            if not km:
                p = _scalar_problem(body)
                if p:
                    problems.append(f"line {n}: {p}")
                continue
        km = _KEY.match(body)
        if not km:
            continue
        val = (km.group(2) or "").strip()
        if val[:1] in (">", "|"):
            block_parent = lead
            continue
        if val[:1] == "[":
            items = _flow_items(val)
            if items is None:
                problems.append(f"line {n}: flow sequence does not close on its line")
                continue
            for it in items:
                p = _scalar_problem(it)
                if p:
                    problems.append(f"line {n}: item {it!r}: {p}")
            continue
        if val[:1] == "{":
            if not re.search(r"\}\s*(?:#.*)?$", val):
                problems.append(f"line {n}: flow mapping does not close on its line")
            continue
        p = _scalar_problem(val) if val else None
        if p:
            problems.append(f"line {n}: {km.group(1)}: {p}")
    return problems


def description_of(fm: Dict[str, object]) -> str:
    desc = fm.get("description")
    if not isinstance(desc, str):
        return ""
    desc = " ".join(desc.split())
    if len(desc) > MAX_DESCRIPTION:
        cut = desc[: MAX_DESCRIPTION - 1].rsplit(" ", 1)[0]
        desc = cut.rstrip(",;:—- ") + "…"
    return desc


def foreign_platform(fm: Dict[str, object]) -> Optional[str]:
    """The platform a skill was written for, if it is another platform's port."""
    meta = fm.get("metadata")
    for p in FOREIGN_PLATFORMS:
        if isinstance(meta, dict) and p in meta:
            return p
        # Flow-mapping form: `metadata: {hermes: {…}}`.
        if isinstance(meta, str) and re.search(r"[{,]\s*%s\s*:" % re.escape(p), meta):
            return p
    return None


def claude_loader(name: str, description: str, source_rel: str) -> str:
    # JSON string syntax is valid YAML double-quoted syntax, so the description
    # can hold any character — colons, quotes, `#` — and still parse.
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        "---\n"
        f"Read and follow the full skill at {source_rel}/SKILL.md\n"
    )


def _loader_source(skill_dir: Path) -> Optional[str]:
    """The source path a Sage loader stub points at, or None if this directory
    is not exactly one loader stub (the user's own skill, a full copy…)."""
    smd = skill_dir / "SKILL.md"
    try:
        if [p.name for p in skill_dir.iterdir()] != ["SKILL.md"]:
            return None
        text = smd.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.match(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n(.*)\Z", text, re.S)
    if not m:
        return None
    lm = _LOADER.match(m.group(1).strip())
    return lm.group(1) if lm else None


def deploy_claude(skills_dir: Path, out_dir: Path, prefix: str = "",
                  skip: Tuple[str, ...] = (), source_rel: str = "sage/skills"
                  ) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Write a loader stub per deployable skill. Returns (deployed, skipped).

    Every existing loader stub is removed first and the current set rewritten,
    so a stub an older version wrote — for a Hermes port, for `sage`, for a
    system skill, or under the other prefix setting — cannot outlive the rule
    that stopped deploying it. Only exact loader stubs are touched; a user's
    own skills and the whole-file system skills are left alone.
    """
    deployed: List[str] = []
    skipped: List[Tuple[str, str]] = []
    if out_dir.is_dir():
        for sd in out_dir.iterdir():
            if sd.is_dir() and not sd.is_symlink() and _loader_source(sd) is not None:
                shutil.rmtree(sd)
    for sd in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        smd = sd / "SKILL.md"
        if not smd.is_file():
            continue
        name = sd.name
        fm = parse_frontmatter(smd.read_text(encoding="utf-8", errors="replace"))
        port = foreign_platform(fm)
        if name in RESERVED_NAMES:
            skipped.append((name, "would shadow the /sage command"))
            continue
        if port:
            skipped.append((name, f"{port} port"))
            continue
        if name in skip:
            skipped.append((name, "delivered separately"))
            continue
        desc = description_of(fm) or f"Sage skill: {name}"
        target = out_dir / f"{prefix}{name}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(
            claude_loader(f"{prefix}{name}", desc, f"{source_rel}/{name}"),
            encoding="utf-8")
        deployed.append(name)
    return deployed, skipped


def check_claude(out_dir: Path, project_root: Optional[Path] = None) -> List[str]:
    """Every SKILL.md under out_dir (a project's .claude/skills/) registers on
    Claude Code and is one Claude Code should have: strict-YAML frontmatter,
    name equal to the directory, a non-empty description, nothing shadowing
    /sage, and — for a loader stub — a source skill that exists and is not
    another platform's port."""
    problems: List[str] = []
    if not out_dir.is_dir():
        return [f"{out_dir}: missing"]
    root = project_root or out_dir.parent.parent
    for sd in sorted(p for p in out_dir.iterdir() if p.is_dir()):
        smd = sd / "SKILL.md"
        if not smd.is_file():
            problems.append(f"{sd.name}: no SKILL.md")
            continue
        text = smd.read_text(encoding="utf-8", errors="replace")
        problems += [f"{sd.name}: {p}" for p in lint_frontmatter(text)]
        fm = parse_frontmatter(text)
        if not fm:
            continue
        if fm.get("name") != sd.name:
            problems.append(f"{sd.name}: name {fm.get('name')!r} != directory")
        if not description_of(fm):
            problems.append(f"{sd.name}: empty description")
        if sd.name.split(":")[-1] in RESERVED_NAMES:
            problems.append(f"{sd.name}: shadows the /sage command")
        sources = [fm]
        src_rel = _loader_source(sd)
        if src_rel is not None:
            src = root / src_rel / "SKILL.md"
            if not src.is_file():
                problems.append(f"{sd.name}: loader points at missing {src_rel}/SKILL.md")
            else:
                src_text = src.read_text(encoding="utf-8", errors="replace")
                sources.append(parse_frontmatter(src_text))
                text += src_text
        for s in sources:
            port = foreign_platform(s)
            if port:
                problems.append(f"{sd.name}: is the {port} port")
                break
        if "delegate_task" in text:
            problems.append(f"{sd.name}: tells Claude to call delegate_task")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("deploy-claude")
    d.add_argument("skills_dir", type=Path)
    d.add_argument("out_dir", type=Path)
    d.add_argument("--prefix", default="")
    d.add_argument("--skip", nargs="*", default=[])
    d.add_argument("--source-rel", default="sage/skills")
    c = sub.add_parser("check-claude")
    c.add_argument("out_dir", type=Path)
    a = ap.parse_args(argv)

    if a.cmd == "deploy-claude":
        deployed, skipped = deploy_claude(a.skills_dir, a.out_dir, a.prefix,
                                          tuple(a.skip), a.source_rel)
        by_reason: Dict[str, List[str]] = {}
        for name, why in skipped:
            by_reason.setdefault(why, []).append(name)
        for why, names in by_reason.items():
            print(f"  · not deployed ({why}): {', '.join(names)}")
        print(f"  ✓ {len(deployed)} skills deployed to .claude/skills/")
        return 0
    problems = check_claude(a.out_dir)
    for p in problems:
        print(f"  ✗ {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
