# Releasing sage

Maintainer-facing checklist. End users don't read this.

## Cutting a release

The root `VERSION` file is the single source of truth. The plugin and
marketplace manifests, the CHANGELOG's top entry, and the `sage-version`
stamped into every project's `.sage/config.yaml` are all derived from it, and
CI fails on drift.

```bash
# 1. Rename the ## [Unreleased] heading to ## [X.Y.Z] — <title>.
#    `--bump` refuses to write until that entry exists: a release without a
#    changelog entry is a release nobody can read.

# 2. Raise the version and propagate it into all four manifests.
python3 runtime/tools/release.py --bump patch    # or minor / major

# 3. Full CI green.
bash develop/validators/gates/run-gate-tests.sh
bash develop/validators/installer/run-installer-tests.sh
python3 develop/validators/tools/test_release.py
python3 develop/validators/check-bash-arrays.py
python3 develop/validators/check-portability.py
docker run --rm -v "$PWD":/sage -w /sage bash:3.2 bash develop/validators/bash32-smoke.sh

# 4. Commit, then tag. The tag must match VERSION or the workflow rejects it.
git tag -a "v$(cat VERSION)" -m "Sage v$(cat VERSION)"
git push origin main --tags
```

The tag push runs `.github/workflows/release.yml`, which re-runs the gate tests
and validators (a tag can point at a commit CI never saw), builds
`sage-X.Y.Z.tar.gz` plus `checksums.txt`, verifies the checksum it is about to
publish, and attaches both to a GitHub release with that version's changelog
section as the notes.

`install.sh` and `sage upgrade` both refuse to install a tarball whose SHA-256
does not match the published `checksums.txt`. Nothing else authenticates the
download — if the release assets are wrong, every user gets the wrong Sage.

Smoke the result on a clean machine or container:

```bash
curl -fsSL https://raw.githubusercontent.com/xoai/sage/main/install.sh | bash
sage version && sage new smoke-test
```

## When `sage-memory` ships a new release

`sage-memory` is a sibling Python package (`/mnt/e/Codes/sage-memory/`,
[github.com/xoai/sage-memory](https://github.com/xoai/sage-memory)) that
provides the MCP server and three canonical skills (`sage-memory`,
`sage-ontology`, `sage-self-learning`).

Sage **vendors a fallback copy** of those three skills under
[skills/sage-*/](skills/) and [tools/sage-claude-plugin/skills/sage-*/](tools/sage-claude-plugin/skills/)
so users **without** the MCP installed still get the prose. The
vendored fallback is *not* auto-synced at runtime — it's committed to
the sage repo and needs maintainer refresh when sage-memory updates.

End users with sage-memory installed are unaffected (their `sage update`
calls `sage-memory install-skills` which deploys the wheel-canonical
copy on top of the vendored fallback).

### One-command refresh

```bash
# Default: looks for sibling repo at ../sage-memory
runtime/tools/sync-vendored-skills.py

# Or specify an explicit path / env var:
runtime/tools/sync-vendored-skills.py --from /path/to/sage-memory
SAGE_MEMORY_SRC=/path/to/sage-memory runtime/tools/sync-vendored-skills.py
```

The script does:

1. Copies `SKILL.md` + `references/` + `scripts/` from sage-memory's
   wheel into `skills/sage-{memory,ontology,self-learning}/`.
2. Same copy into `tools/sage-claude-plugin/skills/sage-*/`.
3. Re-injects sage's fallback comment header at the top of each
   SKILL.md (lost when wheel content overwrites it).
4. Patches upstream prose stragglers — sage-memory ≤ 0.10.0 still has
   `the memory skill` / `the ontology skill` / `the self-learning skill`
   references in a few `sage-self-learning/references/*.md` files
   without the `sage-` prefix. Until upstream cleans up, the script
   re-applies those renames every sync.
5. Verifies:
   - No stale unprefixed skill-name prose
   - Every SKILL.md `name:` frontmatter matches its directory name
   - Every vendored SKILL.md has the fallback comment header

Exits non-zero if any verification fails. The script is **idempotent**
— running it twice in a row on an already-synced state is a no-op.

### After running the script

```bash
# 1. Review what changed
git diff skills/sage-* tools/sage-claude-plugin/skills/sage-*

# 2. Add a line to CHANGELOG.md under the upcoming release section:
#    "vendored fallback refreshed from sage-memory X.Y.Z"
$EDITOR CHANGELOG.md

# 3. Commit and push
git add -A skills/sage-* tools/sage-claude-plugin/skills/sage-* CHANGELOG.md
git commit -m "sync vendored fallback from sage-memory X.Y.Z"
git push origin main
```

If the refresh is part of a sage release, tag after the commit:

```bash
git tag v1.1.X
git push origin v1.1.X
```

## When to refresh

- **Always** after a sage-memory minor or patch release (`0.X.0` →
  `0.X.1` or `0.X.0` → `0.Y.0`).
- **Strongly recommended** before tagging a sage release.
- **Optional** for sage-memory patch-only updates that don't touch
  skill prose — but running the script is cheap and confirms nothing
  drifted, so default to running it.

## When NOT to refresh

- The script is for the **vendored fallback** only. End-user projects
  using the MCP get the canonical wheel content automatically via
  `sage update` → `sage-memory install-skills`. There's nothing to do
  for those users.
- Don't manually edit the vendored fallback in `skills/sage-*/`. Edits
  there get clobbered on next sync. If you need to change behavior for
  users without the MCP, the right place is sage-memory's upstream
  repo (PR to `src/sage_memory/skills/`).

## Architecture context

The full spec/plan for this integration lives at
[.sage/work/20260519-sage-memory-integration/](.sage/work/20260519-sage-memory-integration/).
See particularly `spec.md` §4.7 (loader-then-overlay flow) and §4.6
(migration semantics) for the design reasoning.

The end-user-facing pieces are:
- [bin/sage](bin/sage) → `sage_upgrade`, `sage_update`, `sage_init`
  call [runtime/tools/memory_sync.py](runtime/tools/memory_sync.py)
- [runtime/tools/memory_sync.py](runtime/tools/memory_sync.py) →
  `detect`, `upgrade`, `sync`, `migrate-legacy`

The maintainer-facing pieces are:
- [runtime/tools/sync-vendored-skills.py](runtime/tools/sync-vendored-skills.py)
  (this script — refreshes vendored from wheel)
- [RELEASING.md](RELEASING.md) (this file — the checklist)
