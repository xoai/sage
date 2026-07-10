#!/usr/bin/env python3
"""
release.py — keep every version artifact derived from the root VERSION file.

VERSION is the single source of truth (ADR-2). Everything else is a copy:

  .claude-plugin/plugin.json                            "version"
  .claude-plugin/marketplace.json                      "version"
  tools/sage-claude-plugin/.claude-plugin/plugin.json  "version"
  tools/sage-claude-plugin/.claude-plugin/marketplace.json  "version"
  CHANGELOG.md                                   top `## [X.Y.Z]` entry
  .sage/config.yaml in user projects             stamped by `sage init`

Before this existed the four disagreed — 1.1.11 / 1.1.8 / 1.0.9 / 1.0.0 — and
nobody could tell which Sage they were running.

Usage:
  release.py --check              verify every artifact agrees (writes nothing)
  release.py --sync              propagate VERSION into the derived files
  release.py --bump patch|minor|major
                                 raise VERSION, then --sync
  release.py --artifacts         build the release tarball + checksums.txt
  release.py --repo-root PATH    operate on a tree other than this checkout

Exit: 0 = agree / written   |   1 = drift or refusal   |   2 = bad invocation

`--bump` refuses to write unless CHANGELOG.md's top entry already names the new
version. Write the entry first; the changelog is the release note, not an
afterthought.

`--artifacts` produces dist/sage-X.Y.Z.tar.gz from a git ref (default: the tag
`vX.Y.Z`) and a checksums.txt that `sha256sum -c` and `shasum -a 256 -c` both
understand. install.sh verifies against it before unpacking anything (ADR-3).

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import subprocess
import sys

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PLUGIN_VERSION = re.compile(r'("version"\s*:\s*)"(\d+\.\d+\.\d+)"')
CHANGELOG_ENTRY = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.M)

# A hard-coded `sage-version: "1.2.3"` anywhere but the changelog is drift
# waiting to happen: docs and templates must show a placeholder instead.
HARDCODED = re.compile(r'sage-version:\s*["\']?(\d+\.\d+\.\d+)')

PLUGIN_MANIFESTS = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "tools/sage-claude-plugin/.claude-plugin/plugin.json",
    "tools/sage-claude-plugin/.claude-plugin/marketplace.json",
)

SCAN_SUFFIXES = (".md", ".sh", ".yaml", ".yml")
SCAN_EXCLUDE_DIRS = (".git", ".sage", ".sage-memory", "node_modules", ".pytest_cache")
# The tooling tests build fixture trees that deliberately contain literals.
SCAN_EXCLUDE_PATHS = ("CHANGELOG.md", "develop/validators/tools")


class Problem(Exception):
    pass


def read_version(root: pathlib.Path) -> str:
    path = root / "VERSION"
    if not path.is_file():
        raise Problem("VERSION file not found at repo root")
    version = path.read_text().strip()
    if not SEMVER.match(version):
        raise Problem(f"VERSION is not semver: {version!r}")
    return version


def changelog_top(root: pathlib.Path) -> str:
    path = root / "CHANGELOG.md"
    if not path.is_file():
        raise Problem("CHANGELOG.md not found")
    m = CHANGELOG_ENTRY.search(path.read_text())
    if not m:
        raise Problem("CHANGELOG.md has no `## [X.Y.Z]` entry")
    return m.group(1)


def plugin_version(root: pathlib.Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        raise Problem(f"{rel} not found")
    m = PLUGIN_VERSION.search(path.read_text())
    if not m:
        raise Problem(f'{rel} has no "version" field')
    return m.group(2)


def hardcoded_literals(root: pathlib.Path) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        rel = path.relative_to(root)
        if any(part in SCAN_EXCLUDE_DIRS for part in rel.parts):
            continue
        if any(str(rel).startswith(p) for p in SCAN_EXCLUDE_PATHS):
            continue
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if HARDCODED.search(line):
                hits.append((str(rel), lineno, line.strip()))
    return hits


def check(root: pathlib.Path) -> int:
    version = read_version(root)
    problems: list[str] = []

    for rel in PLUGIN_MANIFESTS:
        try:
            found = plugin_version(root, rel)
        except Problem as exc:
            problems.append(str(exc))
            continue
        if found != version:
            problems.append(f"{rel}: version {found} != VERSION {version}")

    try:
        top = changelog_top(root)
        if top != version:
            problems.append(
                f"CHANGELOG.md: top entry [{top}] != VERSION {version}"
            )
    except Problem as exc:
        problems.append(str(exc))

    for rel, lineno, line in hardcoded_literals(root):
        problems.append(f"{rel}:{lineno}: hard-coded version — {line}")

    if problems:
        print(f"✗ version drift (VERSION = {version})")
        for p in problems:
            print(f"    {p}")
        print()
        print("FAIL — derived artifacts disagree with VERSION.")
        print("  Fix: python3 runtime/tools/release.py --sync")
        print("  Docs and templates must show a placeholder, not a literal.")
        return 1

    print(f"OK — every version artifact agrees on {version}.")
    return 0


def sync(root: pathlib.Path) -> int:
    version = read_version(root)
    changed = []
    for rel in PLUGIN_MANIFESTS:
        path = root / rel
        if not path.is_file():
            raise Problem(f"{rel} not found")
        text = path.read_text()
        new_text, n = PLUGIN_VERSION.subn(rf'\g<1>"{version}"', text, count=1)
        if n == 0:
            raise Problem(f'{rel} has no "version" field')
        if new_text != text:
            path.write_text(new_text)
            changed.append(rel)

    if changed:
        for rel in changed:
            print(f"  updated {rel} → {version}")
    else:
        print("  plugin manifests already in sync")

    literals = hardcoded_literals(root)
    if literals:
        print()
        print("✗ hard-coded version literals remain (sync cannot fix these):")
        for rel, lineno, line in literals:
            print(f"    {rel}:{lineno}: {line}")
        print("  Replace them with a placeholder.")
        return 1

    print(f"OK — synced to {version}.")
    return 0


def bump(root: pathlib.Path, level: str) -> int:
    major, minor, patch = (int(x) for x in read_version(root).split("."))
    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    new_version = f"{major}.{minor}.{patch}"

    # Fail before writing anything: the changelog entry is the release note,
    # and a bump without one produces a release nobody can read.
    top = changelog_top(root)
    if top != new_version:
        print(f"✗ CHANGELOG.md's top entry is [{top}], not [{new_version}].")
        print()
        print(f"FAIL — add a `## [{new_version}]` entry first, then re-run.")
        return 1

    (root / "VERSION").write_text(new_version + "\n")
    print(f"  updated VERSION → {new_version}")
    return sync(root)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifacts(root: pathlib.Path, ref: str, outdir: pathlib.Path) -> int:
    version = read_version(root)
    if ref is None:
        ref = f"v{version}"

    # A tag that names a different version than VERSION would ship a tarball
    # whose contents contradict its filename.
    m = SEMVER.match(ref[1:]) if ref.startswith("v") else None
    if m and ref[1:] != version:
        raise Problem(f"ref {ref} does not match VERSION {version}")

    outdir.mkdir(parents=True, exist_ok=True)
    tarball = outdir / f"sage-{version}.tar.gz"

    # git archive honors .gitattributes export-ignore and never includes .git,
    # so the tarball is exactly the tracked tree at that ref.
    proc = subprocess.run(
        ["git", "-C", str(root), "archive", "--format=tar.gz",
         f"--prefix=sage-{version}/", "-o", str(tarball), ref],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise Problem(f"git archive {ref} failed: {proc.stderr.strip()}")

    digest = sha256_file(tarball)
    # Two spaces: the format both `sha256sum -c` and `shasum -a 256 -c` read.
    (outdir / "checksums.txt").write_text(f"{digest}  {tarball.name}\n")

    print(f"  built {tarball.relative_to(root) if root in tarball.parents else tarball}")
    print(f"  sha256 {digest}")
    print(f"OK — artifacts for {version} from {ref}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Keep version artifacts derived from the root VERSION file."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="verify every artifact agrees (writes nothing)")
    group.add_argument("--sync", action="store_true",
                       help="propagate VERSION into the derived files")
    group.add_argument("--bump", choices=("patch", "minor", "major"),
                       help="raise VERSION, then sync")
    group.add_argument("--artifacts", action="store_true",
                       help="build the release tarball and checksums.txt")
    parser.add_argument("--ref", default=None,
                        help="git ref to archive (default: the tag vX.Y.Z)")
    parser.add_argument("--out", type=pathlib.Path, default=None,
                        help="artifact output directory (default: <repo>/dist)")
    parser.add_argument("--repo-root", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[2],
                        help="operate on a tree other than this checkout")
    args = parser.parse_args()

    root = args.repo_root.resolve()
    try:
        if args.check:
            return check(root)
        if args.sync:
            return sync(root)
        if args.artifacts:
            return artifacts(root, args.ref, args.out or root / "dist")
        return bump(root, args.bump)
    except Problem as exc:
        print(f"✗ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
