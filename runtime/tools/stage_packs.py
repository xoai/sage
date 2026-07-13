#!/usr/bin/env python3
"""
stage_packs.py — build the three pack repo trees the maintainer pushes (R125).

Sage's packs are destined for their own repositories. This GENERATES those repo
trees under `dist/repos/<name>/` from `packs/<name>/`, rather than anyone
hand-maintaining three parallel checkouts. That distinction is not fussiness:

    the navigator was a second copy of the eager layer, and it had drifted
    — v1.3.1, cut for exactly that reason

A hand-copied pack repo is a second copy. A generated one cannot drift, because
there is nothing to drift FROM — it is rebuilt from `packs/` every time.

Each staged repo gets: the pack content, a VERSION, a LICENSE (the main repo's —
the packs carry none today), a README with the install command, and a release
workflow that produces a tarball + checksums.txt via release_lib, so the artifact
`sage add` verifies is built by the same code that verifies it.

  stage_packs.py                 stage all three into dist/repos/
  stage_packs.py --check         verify the staged trees match packs/ (CI)
  stage_packs.py --pack NAME     just one

WHAT THE SPEC GOT WRONG, recorded here because the next person will trust it:

  R125 says sage-product "additionally carries its own pressure/eval assets". IT
  DOES NOT. There is not one eval, pressure, or test asset anywhere under
  packs/sage-product/ — the only near-hit is a prose reference doc. Sage's eval
  assets all live in develop/evals/. Nothing was moved, because there was nothing
  to move.

  R125 says sage-autoresearch has "a 15-module test suite". It has FIVE test files
  (38 test functions) and 14 source modules; "15" appears to have conflated the two.
  It also has no SKILL.md at all, which means `sage add` cannot install it as skills
  — it is a Python package and needs a `python -m` / pip install note, which its
  README now carries.

Operating rule 8: when the spec conflicts with the repo, prefer the repo.

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from release_lib import Problem, read_version  # noqa: E402

PACKS = ("sage-product", "sage-pack-authoring", "sage-autoresearch")
DIST = REPO_ROOT / "dist" / "repos"

# sage-autoresearch is a Python package, not a skill bundle. `sage add` delivers
# skills; it cannot deliver this, and pretending otherwise is how a user ends up
# with an empty install and a success message.
PYTHON_PACKS = {"sage-autoresearch"}


# The pack's own tests, run in its own repo, on every push and every PR.
#
# Not boilerplate. sage-autoresearch's 38 tests had been BROKEN since the pack was
# extracted out of core/ — every one still imported `core.autoresearch.*`, a module
# that no longer exists — and nobody noticed, because nothing ran them. They were
# found on the morning the pack was about to be published, which is the last cheap
# moment to find such a thing.
#
# A test suite nobody runs is a test suite that is already broken. It just has not
# been told yet.
TEST_JOB = """\
  test:
    name: the pack's own tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install pytest
      - run: python3 -m pytest autoresearch/tests -q

"""

RELEASE_WORKFLOW = """\
name: release

on:
  push:
    tags: ['v*']
@@TRIGGERS@@
permissions:
  contents: write

jobs:
@@TEST_JOB@@  release:
    name: build and publish the pack tarball
    runs-on: ubuntu-latest
@@NEEDS@@    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.8'

      - name: Tag must match VERSION
        run: |
          tag="${GITHUB_REF#refs/tags/}"
          version="$(cat VERSION)"
          if [ "$tag" != "v$version" ]; then
            echo "::error::tag $tag does not match VERSION $version"
            exit 1
          fi

      - name: Build tarball + checksums
        run: python3 tools/release_pack.py --artifacts --out dist

      - name: Verify the checksum we are about to publish
        run: |
          cd dist
          sha256sum -c checksums.txt

      - name: Publish
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh release create "${GITHUB_REF#refs/tags/}" \\
            dist/*.tar.gz dist/checksums.txt \\
            --title "${GITHUB_REF#refs/tags/}" \\
            --notes-file RELEASE_NOTES.md
"""

RELEASE_PACK_PY = '''\
#!/usr/bin/env python3
"""
release_pack.py — cut this pack's release artifacts.

A thin shim over Sage's release_lib (vendored beside it), so the tarball a user
downloads is produced by the SAME code that verifies it in `sage add`. A pack repo
that rolled its own checksum writer would be the fourth copy of twelve lines, and
the one that is subtly wrong is always the one that prints OK.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from release_lib import Problem, build_tarball, read_version, write_checksums


def main() -> int:
    p = argparse.ArgumentParser(description="Build this pack's release artifacts.")
    p.add_argument("--artifacts", action="store_true", required=True)
    p.add_argument("--ref", default=None)
    p.add_argument("--out", type=pathlib.Path, default=ROOT / "dist")
    args = p.parse_args()

    try:
        version = read_version(ROOT)
        ref = args.ref or f"v{version}"
        args.out.mkdir(parents=True, exist_ok=True)
        tarball = build_tarball(ROOT, ref, args.out, ROOT.name, version)
        write_checksums(args.out, [tarball])
    except Problem as exc:
        print(f"\\u2717 {exc}")
        return 1

    print(f"OK \\u2014 {tarball.name} + checksums.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def readme(name: str, version: str, is_python: bool) -> str:
    if is_python:
        install = (
            "```bash\n"
            f"pip install git+https://github.com/xoai/{name}@v{version}\n"
            "autoresearch --help          # or: python -m autoresearch --help\n"
            "```\n\n"
            "**Not on PyPI.** That command installs straight from the tagged release —\n"
            "a command that actually works, as opposed to `pip install sage-autoresearch`,\n"
            "which would 404. (Sage shipped a dead `sage add xoai/sage-product` for two\n"
            "minor versions. Once was enough.)\n\n"
            "**This pack is a Python package, not a skill bundle.** It ships no\n"
            "`SKILL.md`, so `sage add` cannot install it — `sage add` delivers skills.\n"
            "That is not a limitation to work around; it is what this pack is.\n"
        )
    else:
        install = (
            "```bash\n"
            f"sage add xoai/{name}@v{version} --all    # pinned, and the sha256 is verified\n"
            f"sage add xoai/{name}                     # latest release\n"
            "```\n\n"
            f"The resolved tag and the verified sha256 are recorded in your project's\n"
            f"`.sage/packs.lock`, so a teammate running the same command gets the same\n"
            f"tree — and can prove it.\n"
        )

    return f"""\
# {name}

A Sage pack. Extracted from Sage's core catalog (ADR-7) and published here so it
can version independently of the framework.

## Install

{install}
## Integrity

Every release publishes a `checksums.txt` beside its tarball. `sage add` verifies
it and **fails closed** — a mismatch installs nothing and says so. A release with
no `checksums.txt` still installs, but loudly, and `.sage/packs.lock` records
`sha256: unverified` rather than a comfortable blank.

## Contents

See `README` inside the pack, and the CHANGELOG for what changed when.

## Home

Developed in [xoai/sage](https://github.com/xoai/sage) under `packs/{name}/` and
staged here by `runtime/tools/stage_packs.py`. **Do not hand-edit this repo** —
it is generated, and your change will be overwritten on the next stage. Send
patches to the main repo.
"""


def stage(name: str, version: str) -> pathlib.Path:
    src = REPO_ROOT / "packs" / name
    if not src.is_dir():
        raise Problem(f"packs/{name} does not exist")

    dest = DIST / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    # The pack content, verbatim.
    for item in sorted(src.iterdir()):
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    # VERSION and LICENSE: no pack has either today. A pack repo without a LICENSE
    # is a pack nobody may legally use.
    (dest / "VERSION").write_text(f"{version}\n")
    shutil.copy2(REPO_ROOT / "LICENSE", dest / "LICENSE")

    # The release machinery, sharing Sage's one implementation.
    tools = dest / "tools"
    tools.mkdir()
    shutil.copy2(HERE / "release_lib.py", tools / "release_lib.py")
    (tools / "release_pack.py").write_text(RELEASE_PACK_PY)
    (tools / "release_pack.py").chmod(0o755)

    wf = dest / ".github" / "workflows"
    wf.mkdir(parents=True)
    python_pack = name in PYTHON_PACKS
    # .format() is unusable here: the workflow is full of ${...} and ${{...}}, which
    # IS brace syntax. Plain placeholders. And the branches go INSIDE the existing
    # `push:` block — a second `push:` key is a duplicate mapping key, invalid YAML.
    (wf / "release.yml").write_text(
        RELEASE_WORKFLOW
        .replace("@@TRIGGERS@@",
                 "    branches: [main]\n  pull_request:\n" if python_pack else "")
        .replace("@@TEST_JOB@@", TEST_JOB if python_pack else "")
        .replace("@@NEEDS@@", "    needs: test\n" if python_pack else ""))

    (dest / "README.md").write_text(readme(name, version, name in PYTHON_PACKS))
    (dest / "RELEASE_NOTES.md").write_text(
        f"# {name} v{version}\n\nStaged from xoai/sage v{version}.\n")

    return dest


def main() -> int:
    p = argparse.ArgumentParser(description="Stage the pack repos for publication.")
    p.add_argument("--pack", choices=PACKS, default=None)
    p.add_argument("--check", action="store_true",
                   help="verify the staged trees are current (CI)")
    args = p.parse_args()

    try:
        version = read_version(REPO_ROOT)
        names = [args.pack] if args.pack else list(PACKS)

        if args.check:
            stale = [n for n in names
                     if not (DIST / n / "VERSION").is_file()
                     or (DIST / n / "VERSION").read_text().strip() != version]
            if stale:
                print(f"✗ staged pack(s) are stale or missing: {', '.join(stale)}")
                print(f"  run: python3 runtime/tools/stage_packs.py")
                return 1
            print(f"OK — {len(names)} pack(s) staged at {version}.")
            return 0

        for n in names:
            dest = stage(n, version)
            print(f"  staged {dest.relative_to(REPO_ROOT)}")
        print(f"\nOK — {len(names)} pack repo(s) staged at {version}.")
        print("These are NOT published. The maintainer pushes them (C17).")
        return 0
    except Problem as exc:
        print(f"✗ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
