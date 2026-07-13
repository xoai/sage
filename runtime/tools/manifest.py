#!/usr/bin/env python3
"""manifest.py — keep the cycle manifest's `gate_state` true, mechanically.

WHY THIS EXISTS, AND WHY IT IS A SCRIPT AND NOT A PARAGRAPH

L1 measured resume fidelity end-to-end — the first scenario in Sage's history to
cross a context boundary — and found this. Three runs of the IDENTICAL cycle, all
three completing all three tasks and committing them:

    run 1    gate_state: gates-passed
    run 2    gate_state: plan-approved     <-- "plan approved, no tasks started"
    run 3    gate_state: complete

Run 2 is the bug. Every task was implemented, tested and committed, and the
manifest still said the work had not begun. **A session resuming from that manifest
would read "no tasks started" and do it all again.** The artifact whose entire
purpose is to carry work across a context boundary had drifted from the tree it
describes — which is the one thing it must never do.

There was no enum in force and no state machine. `cycle-protocol.md` said, in
prose, "Advance it at every checkpoint", and prose is read by the same model that
is deciding whether to bother. Three runs produced three vocabularies.

This is the third time this exact bug has been found in this codebase:

    R29  the degradation record   promised in prose  ->  logged 1 of 3 runs
    ADR-10 the task ledger        promised in prose  ->  written 2 of 3 runs
    R120 the manifest gate_state  promised in prose  ->  correct 1 of 3 runs

The first two are hooks and scripts now. So is this.

    "If a rule matters, make it code. If you can't, don't claim it."

WHAT THIS DELIBERATELY WILL NOT DO

It will not advance a cycle to `gates-passed` or `complete`. Those are APPROVAL
states — granted by a human, or by the quality-locked loop after the gates actually
run. A script that advanced a cycle to `gates-passed` because the files looked
finished would be forging the signature the gate exists to collect, and that is a
worse bug than the one it fixes. Evidence may report that work HAS BEGUN. It may
never report that work has been APPROVED.

So the ceiling on derivation is `building`, and the fix is precisely scoped to the
failure that was measured: a manifest that still claims to be pre-implementation
while the implementation is sitting in the tree.

Usage:
    manifest.py advance <manifest.md> --wrote <path>   # a source file was written
    manifest.py sync    <manifest.md>                  # repair from git evidence
    manifest.py check   [<manifest.md> ...]            # exit 1 on an incoherent manifest

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

# The vocabulary, in order. The spec-gate hook already rejects anything outside it
# (KNOWN_STATES); this is the same list, and it is the only one.
GATE_STATES = (
    "pre-spec",
    "spec-approved",
    "plan-approved",
    "building",
    "gates-passed",
    "complete",
)
RANK = {s: i for i, s in enumerate(GATE_STATES)}

# Evidence may raise a manifest this far and no further. See the module docstring.
DERIVABLE_CEILING = "building"

# States from which observing a source write means "building has begun". NOT
# pre-spec: a pre-spec cycle that is somehow being edited is a Rule 3 violation, and
# silently advancing it would erase the violation rather than report it.
ADVANCEABLE_FROM = ("spec-approved", "plan-approved")

FRONTMATTER_RE = re.compile(r"\A﻿?---\r?\n(.*?)\r?\n---\s*?\r?\n", re.S)
GATE_RE = re.compile(
    r"^(?P<indent>\s*)gate_state\s*:\s*\"?(?P<val>[A-Za-z0-9_-]+)\"?\s*(?P<tail>#.*)?$",
    re.M,
)

# Paths that are Sage's own machinery, not the user's source. Writing one of these is
# bookkeeping, not implementation, and must not flip a cycle to `building`.
NOT_SOURCE = (".sage/", "sage/", ".claude/", ".agent/", "docs/", "node_modules/")
NOT_SOURCE_SUFFIX = (".md", ".txt", ".lock", ".log")


class Problem(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
def split_frontmatter(text: str):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text


def read_gate_state(text: str):
    """(state, ok). ok=False when the frontmatter has no gate_state, or it is not a
    legal value — which is itself a finding, not something to paper over."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        return None, False
    m = GATE_RE.search(fm)
    if not m:
        return None, False
    val = m.group("val").lower()
    return val, val in RANK


def write_gate_state(text: str, new_state: str) -> str:
    """Replace gate_state INSIDE the frontmatter only.

    A `gate_state: building` written in the body prose — and cycle manifests do
    quote their own state in the body — must not be rewritten. The hook would then
    be editing the agent's narration instead of the machine field.
    """
    fm, _ = split_frontmatter(text)
    if fm is None:
        raise Problem("manifest has no frontmatter")
    if not GATE_RE.search(fm):
        raise Problem("manifest frontmatter has no gate_state")

    new_fm = GATE_RE.sub(
        lambda m: f"{m.group('indent')}gate_state: {new_state}"
                  + (f" {m.group('tail')}" if m.group("tail") else ""),
        fm, count=1)
    return text.replace(fm, new_fm, 1)


def is_source(rel: str) -> bool:
    """Is this path the user's implementation, as opposed to Sage's bookkeeping?

    NOTE the prefix stripping. `"./x".lstrip("./")` removes any leading '.' OR '/'
    character — so `.claude/settings.json` becomes `claude/settings.json` and slips
    straight past a `.claude/` exclusion. A unit test caught that here; in
    production it would have advanced a cycle to `building` because the agent
    touched a settings file.
    """
    rel = rel.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    rel = rel.lstrip("/")
    if not rel:
        return False
    if any(rel == p.rstrip("/") or rel.startswith(p) for p in NOT_SOURCE):
        return False
    if rel.endswith(NOT_SOURCE_SUFFIX):
        return False
    return True


def cycle_is_active(text: str) -> bool:
    fm, _ = split_frontmatter(text)
    if fm is None:
        return False
    m = re.search(r"^\s*status\s*:\s*\"?([A-Za-z-]+)", fm, re.M)
    return not (m and m.group(1).lower() in ("complete", "completed", "abandoned"))


# ─────────────────────────────────────────────────────────────────────────────
def advance(manifest_path: pathlib.Path, wrote: str) -> tuple:
    """A source file was written. If this cycle still claims to be pre-implementation,
    say what is true: building.

    Returns (old, new) — new is None when nothing changed.
    """
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    if not cycle_is_active(text):
        return None, None
    if not is_source(wrote):
        return None, None

    state, ok = read_gate_state(text)
    if not ok:
        return state, None                    # illegal/absent — `check` reports it
    if state not in ADVANCEABLE_FROM:
        return state, None                    # already building+, or pre-spec (a violation)

    manifest_path.write_text(write_gate_state(text, DERIVABLE_CEILING),
                             encoding="utf-8")
    return state, DERIVABLE_CEILING


# ─────────────────────────────────────────────────────────────────────────────
def _git(root: pathlib.Path, *args) -> str:
    try:
        p = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout if p.returncode == 0 else ""


def implementation_has_begun(root: pathlib.Path, manifest: pathlib.Path) -> bool:
    """Has any source file changed since this cycle's manifest appeared?

    Committed changes AND uncommitted ones — an agent that writes a file and never
    commits it has still written it, and a check that only read the git log would
    call that a clean tree.

    Fail-soft: no git, no answer, no claim. Returns False rather than guessing.
    """
    rel = manifest.resolve()
    try:
        rel = rel.relative_to(root.resolve()).as_posix()
    except ValueError:
        return False

    born = [s for s in _git(root, "log", "--diff-filter=A", "--format=%H",
                            "--", rel).splitlines() if s.strip()]
    if not born:
        return False
    base = born[-1].strip()           # the commit that ADDED it (oldest)

    changed = set()
    for line in _git(root, "diff", "--name-only", base).splitlines():
        if line.strip():
            changed.add(line.strip())
    for line in _git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        if line.strip():
            changed.add(line.strip())

    return any(is_source(c) for c in changed)


def sync(manifest_path: pathlib.Path, root: pathlib.Path) -> tuple:
    """Repair a manifest from git evidence. Same ceiling: never past `building`."""
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    if not cycle_is_active(text):
        return None, None
    state, ok = read_gate_state(text)
    if not ok or state not in ADVANCEABLE_FROM:
        return state, None
    if not implementation_has_begun(root, manifest_path):
        return state, None

    manifest_path.write_text(write_gate_state(text, DERIVABLE_CEILING),
                             encoding="utf-8")
    return state, DERIVABLE_CEILING


def check(manifests, root: pathlib.Path) -> int:
    """Is every manifest's gate_state legal, and does it match the tree?

    The failure this exists to catch, in one sentence: a manifest claiming the work
    has not started while the work is sitting in the tree next to it.
    """
    problems = []
    for path in manifests:
        text = path.read_text(encoding="utf-8", errors="replace")
        state, ok = read_gate_state(text)

        if state is None:
            problems.append(f"{path}: no gate_state in frontmatter")
            continue
        if not ok:
            problems.append(
                f"{path}: gate_state {state!r} is not one of "
                f"{', '.join(GATE_STATES)}")
            continue
        if not cycle_is_active(text):
            continue

        if (RANK[state] < RANK["building"]
                and implementation_has_begun(root, path)):
            problems.append(
                f"{path}: gate_state is {state!r}, but source files have changed "
                f"since this cycle began.\n"
                f"      The manifest says the work has not started. The tree says "
                f"it has.\n"
                f"      A session resuming from this manifest would redo the work.\n"
                f"      Fix: python3 sage/runtime/tools/manifest.py sync {path}")

    if problems:
        print("✗ incoherent cycle manifest(s):\n")
        for p in problems:
            print(f"  {p}\n")
        return 1

    print(f"OK — {len(manifests)} manifest(s); every gate_state is legal and "
          f"consistent with the tree.")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
def find_manifests(root: pathlib.Path) -> list:
    work = root / ".sage" / "work"
    if not work.is_dir():
        return []
    return sorted(work.glob("*/manifest.md"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("advance", help="a source file was written — record that")
    a.add_argument("manifest", type=pathlib.Path)
    a.add_argument("--wrote", required=True, help="the path that was written")

    s = sub.add_parser("sync", help="repair gate_state from git evidence")
    s.add_argument("manifest", type=pathlib.Path)
    s.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())

    c = sub.add_parser("check", help="exit 1 if a manifest contradicts the tree")
    c.add_argument("manifest", type=pathlib.Path, nargs="*")
    c.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())

    args = p.parse_args(argv)

    try:
        if args.cmd == "advance":
            old, new = advance(args.manifest, args.wrote)
            if new:
                print(f"gate_state: {old} → {new}")
            return 0

        if args.cmd == "sync":
            old, new = sync(args.manifest, args.repo_root.resolve())
            print(f"gate_state: {old} → {new}" if new
                  else f"gate_state: {old} (unchanged — nothing to repair)")
            return 0

        manifests = args.manifest or find_manifests(args.repo_root.resolve())
        if not manifests:
            print("OK — no cycle manifests.")
            return 0
        return check(manifests, args.repo_root.resolve())

    except (Problem, OSError) as exc:
        print(f"✗ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
