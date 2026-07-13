#!/usr/bin/env python3
"""
release_lib.py — the release mechanics shared by Sage and the packs it ships.

Sage's main repo cuts a tarball and a checksums.txt. So will each of the three pack
repos (sage-product, sage-pack-authoring, sage-autoresearch). That is four copies of
the same twelve lines — and this project has already paid for what happens next:

    the navigator was a second copy of the eager layer, and it had drifted
    — v1.3.1, cut for exactly that reason

So the mechanics live here once, and release.py, the pack release workflows, and
`sage add`'s verification all call them. One implementation, many callers.

Two halves, and they must agree byte-for-byte or the integrity story is theatre:

  PRODUCER — write_checksums() emits the two-space format that BOTH `sha256sum -c`
             and `shasum -a 256 -c` parse. (One space is a different format; the
             BSD tools read it as a filename beginning with a space.)
  CONSUMER — verify_checksums() reads that format back and fails closed. It is the
             Python arm of the same chain install.sh:77-102 walks, and it exists
             because `sage add` is Python and shelling out to sha256sum would
             reintroduce the portability problem install.sh already solved.

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
CHANGELOG_ENTRY = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)


class Problem(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Version + changelog
# ─────────────────────────────────────────────────────────────────────────────
def read_version(root: pathlib.Path) -> str:
    path = root / "VERSION"
    if not path.is_file():
        raise Problem(f"VERSION file not found at {root}")
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


def notes(root: pathlib.Path, version: str) -> str:
    """The CHANGELOG section for one version — the text of the release notes.

    Includes the `## [X.Y.Z]` heading, because that is what the published GitHub
    release bodies have always contained; changing it here would silently restyle
    every future release. This lived as a Python heredoc inside release.yml's
    publish step, where it was both untestable and — because the heredoc body sat
    at column 0 — enough to make the whole workflow file invalid YAML.
    """
    version = version.lstrip("v")
    path = root / "CHANGELOG.md"
    if not path.is_file():
        raise Problem("CHANGELOG.md not found")
    # This version's heading, up to the next one (or end of file).
    m = re.search(
        r"^##\s*\[%s\].*?(?=^##\s*\[|\Z)" % re.escape(version),
        path.read_text(), re.M | re.S,
    )
    if not m:
        raise Problem(f"CHANGELOG.md has no `## [{version}]` entry")
    return m.group(0).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Checksums — the producer and the consumer, in one place, agreeing by construction
# ─────────────────────────────────────────────────────────────────────────────
def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(outdir: pathlib.Path, files) -> pathlib.Path:
    """Emit checksums.txt in the one format both GNU and BSD tools read.

    TWO SPACES between digest and name. `sha256sum -c` and `shasum -a 256 -c` both
    parse that; with one space, the BSD tool reads the name as starting with a
    space and reports every file missing — which looks exactly like a tampered
    download, and would be blamed on the network for a week.
    """
    lines = [f"{sha256_file(f)}  {f.name}" for f in files]
    dest = outdir / "checksums.txt"
    dest.write_text("\n".join(lines) + "\n")
    return dest


def parse_checksums(text: str) -> dict:
    """{filename: digest} from a checksums.txt. Tolerant of 1-or-more spaces on
    read (be liberal in what you accept), strict on write (be conservative in what
    you send)."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        digest, name = parts[0], parts[-1]
        out[name.lstrip("*")] = digest.lower()
    return out


def verify_checksums(directory: pathlib.Path, required=None) -> list:
    """Verify every file named in directory/checksums.txt. Returns the verified names.

    FAILS CLOSED. A missing file, a mismatched digest, or an unreadable
    checksums.txt raises. The one thing this must never do is return quietly when
    it has verified nothing — an integrity check that no-ops on an empty manifest
    is worse than no check at all, because it prints a tick.
    """
    manifest = directory / "checksums.txt"
    if not manifest.is_file():
        raise Problem(f"no checksums.txt in {directory}")

    expected = parse_checksums(manifest.read_text())
    if not expected:
        raise Problem(f"{manifest} lists no files — refusing to call that verified")

    if required:
        missing = [n for n in required if n not in expected]
        if missing:
            raise Problem(
                f"checksums.txt does not cover {', '.join(missing)} — "
                f"the download is not fully attested")

    verified = []
    for name, want in sorted(expected.items()):
        target = directory / name
        if not target.is_file():
            raise Problem(f"checksums.txt names {name}, which is not here")
        got = sha256_file(target)
        if got != want:
            raise Problem(
                f"CHECKSUM MISMATCH for {name}\n"
                f"  expected {want}\n"
                f"  actual   {got}\n"
                f"Refusing to install an unverified download.")
        verified.append(name)
    return verified


# ─────────────────────────────────────────────────────────────────────────────
# Tarballs
# ─────────────────────────────────────────────────────────────────────────────
def build_tarball(root: pathlib.Path, ref: str, outdir: pathlib.Path,
                  name: str, version: str) -> pathlib.Path:
    """`git archive` the tracked tree at `ref` into outdir/<name>-<version>.tar.gz.

    git archive honors .gitattributes export-ignore and never includes .git, so the
    tarball is exactly the tracked tree at that ref — not the working directory,
    which may contain anything at all.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    tarball = outdir / f"{name}-{version}.tar.gz"
    proc = subprocess.run(
        ["git", "-C", str(root), "archive", "--format=tar.gz",
         f"--prefix={name}-{version}/", "-o", str(tarball), ref],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise Problem(f"git archive {ref} failed: {proc.stderr.strip()}")
    return tarball
