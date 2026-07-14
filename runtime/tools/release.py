#!/usr/bin/env python3
"""
release.py — keep every version artifact derived from the root VERSION file.

VERSION is the single source of truth (ADR-2). Everything else is a copy:

  .claude-plugin/plugin.json                     "version"
  CHANGELOG.md                                   top `## [X.Y.Z]` entry
  .sage/config.yaml in user projects             stamped by `sage init`

Before this existed the four disagreed — 1.1.11 / 1.1.8 / 1.0.9 / 1.0.0 — and
nobody could tell which Sage they were running.

The plugin's own manifests are no longer copies to keep in step: the mirror
under tools/sage-claude-plugin/ is gone (P3-T2b) and build_plugin.py stamps the
generated tree from VERSION at build time. The marketplace *entry* must not pin
a version at all — when both are set Claude Code silently prefers plugin.json,
so a second number there is drift with no reader. `--check` enforces that.

Usage:
  release.py --check              verify every artifact agrees (writes nothing)
  release.py --sync              propagate VERSION into the derived files
  release.py --bump patch|minor|major
                                 raise VERSION, then --sync
  release.py --artifacts         build the release tarball + checksums.txt
  release.py --notes vX.Y.Z      print that version's CHANGELOG section
  release.py --with-evals        run the eval suite and write its summary
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
import json
import pathlib
import re
import subprocess
import sys

# The tarball/checksum/changelog mechanics are shared with the three pack repos
# (ADR-15). They live in release_lib so there is ONE implementation of them rather
# than four copies drifting apart — which is not a hypothetical here: v1.3.1 was cut
# because the navigator was a second copy of the eager layer and had drifted.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from release_lib import (                                            # noqa: E402
    Problem, build_tarball, changelog_top, notes, sha256_file, write_checksums,
)

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PLUGIN_VERSION = re.compile(r'("version"\s*:\s*)"(\d+\.\d+\.\d+)"')
CHANGELOG_ENTRY = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.M)

# A hard-coded `sage-version: "1.2.3"` anywhere but the changelog is drift
# waiting to happen: docs and templates must show a placeholder instead.
HARDCODED = re.compile(r'sage-version:\s*["\']?(\d+\.\d+\.\d+)')

PLUGIN_MANIFESTS = (
    ".claude-plugin/plugin.json",
)

# The marketplace entry defers its version to plugin.json (see the module
# docstring). These carry no version and must not grow one back.
MARKETPLACES = (
    ".claude-plugin/marketplace.json",
    "runtime/plugin-overlay/.claude-plugin/marketplace.json",
)

SCAN_SUFFIXES = (".md", ".sh", ".yaml", ".yml")
# …and extensionless scripts. The CLI is `bin/sage`, with no suffix, so it was not
# scanned — and it sat there hardcoding `sage-version: "1.0.0"` into every project
# it initialized while VERSION said 1.2.0. The one guard built to catch exactly
# that literal could not see the one file that actually stamps it.
SCAN_EXCLUDE_DIRS = (".git", ".sage", ".sage-memory", "node_modules", ".pytest_cache")
# Test harnesses build fixture trees (fake .sage/config.yaml, plugin.json,
# CHANGELOG) that deliberately contain version literals — exclude them.
SCAN_EXCLUDE_PATHS = (
    "CHANGELOG.md",
    "develop/validators/tools",
    "develop/validators/hooks",
)


def read_version(root: pathlib.Path) -> str:
    """The root VERSION, validated.

    Not release_lib's: this one's error message names the repo root, because in the
    main repo a missing VERSION is a broken checkout, while in a pack repo it is a
    pack that has not been staged yet. Same check, different thing gone wrong.
    """
    path = root / "VERSION"
    if not path.is_file():
        raise Problem("VERSION file not found at repo root")
    version = path.read_text().strip()
    if not SEMVER.match(version):
        raise Problem(f"VERSION is not semver: {version!r}")
    return version


def plugin_version(root: pathlib.Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        raise Problem(f"{rel} not found")
    m = PLUGIN_VERSION.search(path.read_text())
    if not m:
        raise Problem(f'{rel} has no "version" field')
    return m.group(2)


def marketplace_version_pins(root: pathlib.Path, rel: str) -> list[str]:
    """Names of marketplace entries that pin a version they should not."""
    path = root / rel
    if not path.is_file():
        return []
    try:
        entries = json.loads(path.read_text()).get("plugins", [])
    except json.JSONDecodeError as exc:
        raise Problem(f"{rel} is not valid JSON: {exc}")
    return [e.get("name", "?") for e in entries if "version" in e]


def is_script(path: pathlib.Path) -> bool:
    """An extensionless file that opens with a shebang — bin/sage and its kin."""
    if path.suffix:
        return False
    try:
        with path.open("rb") as fh:
            return fh.read(2) == b"#!"
    except OSError:
        return False


def hardcoded_literals(root: pathlib.Path) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in SCAN_SUFFIXES and not is_script(path):
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

    for rel in MARKETPLACES:
        try:
            for name in marketplace_version_pins(root, rel):
                problems.append(
                    f'{rel}: entry "{name}" pins a version — remove it; '
                    f"plugin.json is the single authority"
                )
        except Problem as exc:
            problems.append(str(exc))

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

    pins = [(rel, name) for rel in MARKETPLACES
            for name in marketplace_version_pins(root, rel)]
    if pins:
        print()
        print("✗ marketplace entries pin a version (sync cannot fix these):")
        for rel, name in pins:
            print(f'    {rel}: entry "{name}"')
        print("  Remove the field — plugin.json is the single authority.")
        return 1

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


def with_evals(root: pathlib.Path, runs: int) -> int:
    """Run the eval suite and leave its summary where the release notes can reach it.

    Not part of --check, and deliberately not in per-PR CI: a full run makes real
    model calls and costs real money, so it is a thing a maintainer decides to do
    at release time, with the number in hand, rather than a thing that happens to
    them on every typo fix (13-§30 R74).
    """
    runner = root / "develop" / "evals" / "run_evals.py"
    if not runner.is_file():
        raise Problem("develop/evals/run_evals.py not found")

    print(f"  running the eval suite (N={runs}) — this makes real model calls…")
    proc = subprocess.run(
        [sys.executable, str(runner), "--runs", str(runs), "--report"],
        cwd=str(root),
    )
    summary = root / "develop" / "evals" / "results" / "summary.md"
    if summary.is_file():
        print(f"\n  summary → {summary.relative_to(root)}")
        print("  Paste it into the release notes; the sage-vs-bare delta is the claim.")
    if proc.returncode != 0:
        print("\n✗ the eval run reported failures — read the summary before releasing.")
        return 1
    return 0


PACK_REPOS = ("sage-product", "sage-pack-authoring", "sage-autoresearch")

PACK_OWNER = "xoai"


MARKETPLACE_REPO = "sage-marketplace"


def canonical_plugin_source(root: pathlib.Path) -> dict:
    """The plugin `source` block this repo publishes — the thing that must not drift."""
    path = root / ".claude-plugin" / "marketplace.json"
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return (d.get("plugins") or [{}])[0].get("source") or {}
    except (ValueError, OSError, IndexError):
        return {}


def marketplace_repo_state() -> tuple:
    """('published'|'no-repo'|'unknown', source_block).

    Reads the manifest out of the published marketplace repo. Fail-soft: an
    unreachable network returns 'unknown' and no claim, because a check that guesses
    reads exactly like a check that knows.
    """
    import base64
    import urllib.error
    import urllib.request

    url = (f"https://api.github.com/repos/{PACK_OWNER}/{MARKETPLACE_REPO}"
           f"/contents/.claude-plugin/marketplace.json")
    req = urllib.request.Request(url, headers={"User-Agent": "sage-release"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        raw = base64.b64decode(payload.get("content", "")).decode("utf-8")
        d = json.loads(raw)
        return "published", (d.get("plugins") or [{}])[0].get("source") or {}
    except urllib.error.HTTPError as exc:
        return ("no-repo" if exc.code == 404 else "unknown"), {}
    except (urllib.error.URLError, OSError, ValueError, IndexError):
        return "unknown", {}


def pack_release_state(name: str) -> tuple:
    """('published'|'missing-release'|'no-repo'|'unknown', latest_tag).

    Asks whether the pack has a LATEST RELEASE — not whether it carries Sage's
    version. Packs version independently (ADR-7); tying them to Sage's number is the
    lockstep the extraction exists to break.

    Fail-soft: an unreachable network yields 'unknown' and no claim. A release check
    that guesses is worse than one that says it does not know, because a guess reads
    exactly like an answer.
    """
    import urllib.error
    import urllib.request

    url = f"https://api.github.com/repos/{PACK_OWNER}/{name}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "sage-release"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return "published", data.get("tag_name") or "?"
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            return "unknown", None
    except (urllib.error.URLError, OSError, ValueError):
        return "unknown", None

    # 404 on /releases/latest is ambiguous: no repo, or a repo with no releases.
    repo = f"https://api.github.com/repos/{PACK_OWNER}/{name}"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(repo, headers={"User-Agent": "sage-release"}),
                timeout=10):
            return "missing-release", None
    except urllib.error.HTTPError as exc:
        return ("no-repo" if exc.code == 404 else "unknown"), None
    except (urllib.error.URLError, OSError):
        return "unknown", None


def dist_status(root: pathlib.Path) -> int:
    """What is distributable, what is staged, and what is still a promise (R132).

    Drift is a WARNING here and an ERROR at release time. The distinction matters
    because for most of this program's life the honest answer to "where do the packs
    live" has been "nowhere" — and a check that hard-failed on that would have been
    disabled within a week, which is how checks die.

    What it will not do is stay quiet. `sage update` has been telling users to run
    `sage add xoai/sage-product` since v1.2 — a command for a repository that does
    not exist. Nothing in CI noticed, because nothing was looking. This looks.
    """
    version = read_version(root)
    print(f"Distribution status for {version}\n")

    problems, warnings = [], []

    # ── The plugin ──────────────────────────────────────────────────────────
    for rel in PLUGIN_MANIFESTS:
        try:
            pv = plugin_version(root, rel)
            mark = "✓" if pv == version else "✗"
            print(f"  {mark} plugin  {rel} → {pv}")
            if pv != version:
                problems.append(f"{rel} pins {pv}, not {version}")
        except Problem as exc:
            problems.append(str(exc))

    # ── The marketplace ─────────────────────────────────────────────────────
    # The entry defers its version to plugin.json on purpose. A version here is a
    # second place to forget to bump.
    for rel in MARKETPLACES:
        pins = marketplace_version_pins(root, rel)
        if pins:
            problems.append(f"{rel} pins a version for: {', '.join(pins)} "
                            f"— the marketplace must defer to plugin.json")
            print(f"  ✗ market  {rel} → pins a version it should not")
        elif (root / rel).is_file():
            print(f"  ✓ market  {rel} → defers to plugin.json")

    # The published marketplace repo carries a COPY of the plugin source block. A copy
    # of a thing with a canonical source is exactly what shipped the navigator a
    # release out of date, so the two are checked against each other rather than
    # trusted to stay in step.
    #
    # The `name` field is deliberately NOT compared: it is the marketplace's ID, and it
    # must be `sage-marketplace` there and `sage` here. Copying it verbatim is what made
    # `/plugin install sage@sage-marketplace` fail with "not found in marketplace" —
    # the documented command was a dead link until it was actually run.
    state, remote_source = marketplace_repo_state()
    local_source = canonical_plugin_source(root)
    if state == "no-repo":
        warnings.append(
            "xoai/sage-marketplace does not exist — "
            "`/plugin marketplace add xoai/sage-marketplace` is a dead link (P6-T4)")
    elif state == "unknown":
        warnings.append("could not reach xoai/sage-marketplace — pin unverified")
    elif remote_source != local_source:
        problems.append(
            f"xoai/sage-marketplace's plugin source has drifted from this repo's:\n"
            f"      here:   {json.dumps(local_source, sort_keys=True)}\n"
            f"      there:  {json.dumps(remote_source, sort_keys=True)}")
        print("  ✗ market  xoai/sage-marketplace → source block DRIFTED")
    else:
        print("  ✓ market  xoai/sage-marketplace → published, source block agrees")

    # ── The packs ───────────────────────────────────────────────────────────
    # There is no "staged" state any more. The packs left this repo in v1.3.2 and
    # their own repositories are canonical; packs/ is a pointer README. What is left
    # to check is the only thing that was ever load-bearing: are they actually THERE.

    # ── Staged is not published, and this must ASK rather than assume ───────
    #
    # This block used to print "staged ≠ published" unconditionally. The moment the
    # repos went live it became a lie — the tool asserting a fact it had not checked,
    # which is the exact defect this release spent its whole budget chasing. It looks
    # now. Fail-soft: no network, no claim.
    # PACKS VERSION INDEPENDENTLY OF SAGE. That is what ADR-7 extracted them for — a
    # pack should not need a Sage release to ship a fix — so demanding the pack carry
    # a tag matching Sage's VERSION is the lockstep assumption the extraction exists to
    # break. It also manufactures a dead link: cutting Sage v1.3.3 would have this
    # check demand a pack tag v1.3.3 that nobody has any reason to have cut, and
    # `sage update` would have told users to install it.
    #
    # What matters is that the pack HAS a release, so `sage add xoai/<pack>` resolves.
    # Which release is the pack's business, and `.sage/packs.lock` records the one the
    # user actually got.
    for name in PACK_REPOS:
        state, latest = pack_release_state(name)
        if state == "published":
            print(f"  ✓ remote  {name} → {latest} published (versions independently)")
        elif state == "missing-release":
            warnings.append(
                f"xoai/{name} exists but has published NO release — "
                f"`sage add xoai/{name}` cannot resolve")
        elif state == "no-repo":
            warnings.append(
                f"xoai/{name} does not exist. `sage update` has been printing "
                f"`sage add xoai/{name}` since v1.2 (bin/sage, the R54 block) — "
                f"that is a dead link until the repo is published (C17).")
        else:
            warnings.append(f"{name}: could not reach GitHub — publication unverified")

    print()
    for w in warnings:
        print(f"  ⚠ {w}")
    for p in problems:
        print(f"  ✗ {p}")

    print()
    if problems:
        print(f"✗ {len(problems)} drift problem(s). Fix before releasing.")
        return 1
    print(f"OK — no drift. {len(warnings)} thing(s) staged but not published (C17).")
    return 0


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
    tarball = build_tarball(root, ref, outdir, "sage", version)
    write_checksums(outdir, [tarball])
    digest = sha256_file(tarball)

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
    group.add_argument("--notes", metavar="VERSION",
                       help="print that version's CHANGELOG section (release notes)")
    group.add_argument("--with-evals", action="store_true",
                       help="run the eval suite and write results/summary.md "
                            "(makes real model calls; costs money)")
    group.add_argument("--dist-status", action="store_true",
                       help="report the distribution surface: staged pack repos, "
                            "marketplace pin, and what is not yet published")
    parser.add_argument("--eval-runs", type=int, default=3,
                        help="runs per scenario per condition for --with-evals (default 3)")
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
        if args.dist_status:
            return dist_status(root)
        if args.sync:
            return sync(root)
        if args.artifacts:
            return artifacts(root, args.ref, args.out or root / "dist")
        if args.notes:
            print(notes(root, args.notes))
            return 0
        if args.with_evals:
            return with_evals(root, args.eval_runs)
        return bump(root, args.bump)
    except Problem as exc:
        print(f"✗ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
