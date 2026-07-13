# Installing Sage

Four ways in. They differ in one thing that matters more than convenience: **what,
if anything, proves you got what you think you got.** That is stated for each,
plainly, including where the answer is "nothing".

| Path | What it installs | Integrity |
|---|---|---|
| [Script](#1-the-install-script) | The framework + `sage` CLI | **sha256 verified**, fails closed |
| [Plugin](#2-the-claude-code-plugin) | Sage inside Claude Code | GitHub's transport; no checksum |
| [Vendored](#3-vendored-into-a-repo) | A pinned copy in your repo | **Your git history is the proof** |
| [Packs](#4-packs) | Optional skill bundles | **sha256 verified** when the release publishes one; loud warning when not |

---

## 1. The install script

```bash
curl -fsSL https://raw.githubusercontent.com/xoai/sage/main/install.sh | bash
```

**Integrity: verified, and it refuses rather than degrades.** The script downloads
the release tarball *and* its `checksums.txt`, and checks one against the other
using whichever of `sha256sum`, `shasum`, or `python3` your machine has. If none of
the three exists it does not shrug and continue — it stops:

> No SHA-256 tool found (sha256sum, shasum, or python3). Refusing to install an
> unverified download.

If the digest does not match, nothing is installed and your existing Sage is left
exactly as it was.

Piping a URL into `bash` requires trusting the transport and the source. If you
would rather not, download `install.sh`, read it, then run it — it is 247 lines and
the verification is the block at the top.

## 2. The Claude Code plugin

```
/plugin marketplace add xoai/sage-marketplace
/plugin install sage@sage-marketplace
```

> **Not yet live.** The marketplace repo is staged but unpublished (Phase 6, C17 —
> publishing is a public, hard-to-retract act and it needs a maintainer's hand, not
> an agent's). Until it is, install via the script or vendor the plugin directly
> from the `plugin-dist` branch, where the built tree lives under
> `tools/sage-claude-plugin/` — note the path; the branch root is empty by design.

**Integrity: GitHub's transport, and nothing else.** There is no checksum on this
path. The plugin is a build output, force-pushed to `plugin-dist` on every release
by CI, and you are trusting GitHub and the workflow that produced it. That is the
same trust every plugin marketplace asks for. It is worth knowing you are extending
it.

## 3. Vendored into a repo

```bash
sage init --vendor        # copies the framework into sage/ and commits it
```

**Integrity: your own git history.** Nothing is fetched at use time, so nothing can
change under you. The framework is a tree of files your repo tracks, and `git diff`
is the audit. This is the strongest guarantee available, and it is the only one that
survives the upstream repository being deleted, rewritten, or compromised after you
installed.

The cost is that upgrades are yours to run (`sage update`), and a vendored copy that
nobody updates is a vendored copy that quietly rots.

## 4. Packs

Packs are optional skill bundles that version independently of the framework.

```bash
sage add xoai/sage-product@v1.3.1 --all   # pinned to a tag
sage add xoai/sage-product --all          # whatever is latest today
sage add ./packs/sage-product --all       # from a local checkout
```

> **Not yet live.** The three pack repos are staged but unpublished (C17). Until
> they are pushed, use the local-checkout form. `sage update` has been recommending
> `sage add xoai/sage-product` since v1.2 — that command does not resolve yet, and
> making it true is what Phase 6 is for.

**Integrity: verified when the release publishes a `checksums.txt`, and loud when it
does not.**

- **checksums.txt present** → the tarball is verified against it and `sage add`
  **fails closed** on a mismatch. Nothing is installed; your existing skills are
  untouched.
- **checksums.txt absent** → the pack still installs, but you are warned in as many
  words that you fetched a tarball nobody attested, and `.sage/packs.lock` records
  `sha256: unverified`. Not a blank — a blank reads as *not applicable*, and this is
  not that.

### `.sage/packs.lock`

Every pack install records what it actually got:

```json
{
  "version": 1,
  "packs": {
    "sage-product": {
      "source": "xoai/sage-product",
      "version": "v1.3.1",
      "sha256": "9f2c…",
      "skills": ["jtbd", "prd", "ux-review"],
      "installed": "2026-07-12"
    }
  }
}
```

Commit it. `sage/skills/skills.json` already records *a* source, but for a local
install it records an **absolute path on your machine** — which is not portable and
is not a version. It cannot answer *"is your sage-product the same as mine"*. This
can.

### The pack that is not skills

`sage-autoresearch` is a **Python package**, not a skill bundle. It ships no
`SKILL.md`, so `sage add` cannot deliver it — `sage add` delivers skills:

```bash
pip install sage-autoresearch      # or: uv pip install sage-autoresearch
python -m autoresearch --help
```

Today, `sage add ./packs/sage-autoresearch` prints *"No SKILL.md files found"* and
exits successfully, having installed nothing. It now says what to do instead.

---

## Which one should you use?

- **Trying Sage out** → the script. It is verified and it is one line.
- **Working inside Claude Code** → the plugin, once it is live.
- **A team repo, or anything you will still be running in a year** → vendor it. The
  supply chain you do not depend on is the one that cannot break.
- **You want the PM/UX or pack-authoring skills** → a pack, on top of any of the above.
