# packs/ — staged installable packs

Content extracted from Sage's core catalog (ADR-7) and staged here for review.
Each pack is destined for its own repository; until then it installs from a
local checkout:

```bash
sage add ./packs/<pack-name>
```

- **sage-product** — the PM & UX suite (jtbd, prd, ux-*, /research, /design).

Removed skills map to a pack via the migration table in CHANGELOG. A pack is
just a directory of skill folders (each with a `SKILL.md`); `sage add` installs
them into a project's `sage/skills/`.
