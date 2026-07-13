# packs/ — the packs live in their own repos now

They used to live here. As of **v1.3.2** each pack has its own repository, its own
version, and its own release — which is what ADR-7 extracted them for: a pack should
not need a Sage release to ship a fix.

**There is no pack content in this directory any more. This file is the whole of it.**

## The three packs

| Pack | What it is | Install |
|---|---|---|
| [**xoai/sage-product**](https://github.com/xoai/sage-product) | The PM & UX suite — 11 skills, plus the `/research` and `/design` workflows | `sage add xoai/sage-product@v1.3.2 --all` |
| [**xoai/sage-pack-authoring**](https://github.com/xoai/sage-pack-authoring) | Toolkit for writing packs — discover, draft, observe, process sources, validate | `sage add xoai/sage-pack-authoring --all` |
| [**xoai/sage-autoresearch**](https://github.com/xoai/sage-autoresearch) | Autonomous research loop. A **Python package**, not skills | `pip install git+https://github.com/xoai/sage-autoresearch@v1.3.2` |

Pin the tag if you want a reproducible install. `sage add` verifies the release's
sha256 against its published `checksums.txt` and **fails closed** on a mismatch, then
records source, version and digest in your project's `.sage/packs.lock` — so a
teammate running the same command gets the same tree, and can prove it.

`sage-autoresearch` ships no `SKILL.md`, so `sage add` cannot install it. `sage add`
delivers skills; that pack is a Python package. Not a limitation to work around — it
is what the pack is.

## Migration — where the skills went

| Skill | Now in |
|---|---|
| `jtbd`, `opportunity-map`, `prd`, `problem-solving` | `sage add xoai/sage-product` |
| `ux-brief`, `ux-design`, `ux-discovery`, `ux-plan-tasks` | `sage add xoai/sage-product` |
| `ux-review`, `ux-specify`, `ux-writing` | `sage add xoai/sage-product` |
| `pack-discover`, `pack-draft`, `pack-observe`, `pack-source-process`, `pack-validate` | `sage add xoai/sage-pack-authoring` |
| `autoresearch` | `pip install git+https://github.com/xoai/sage-autoresearch@v1.3.2` |

`sage update` detects a project that installed a pack from a local `packs/` checkout
and prints the command to reinstall it from the published repo.

## `sage add ./packs/<name>` no longer works

There is nothing here to install. Use the repo:

```bash
sage add xoai/sage-product@v1.3.2 --all
```

Sage printed that exact command as migration guidance for two minor versions *before
the repository existed* — a dead link, shipped. It resolves now, and
`release.py --dist-status` checks that it still does rather than assuming it.
