#!/usr/bin/env bash
# The Quick reference: the routing, tiers and checkpoints system skills' "At a
# glance" sections, for the always-on layer.
#
# WHY. ADR-9 moved routing, tiers and checkpoints out of the eager layer into
# description-triggered skills — and Claude opened a Sage system skill once in
# 27 runs (review 2026-10-26, C3), so their rules mostly never reached it. Each
# of those skills now carries a short "At a glance" section, and this emits
# them, copied from the skill (one source, no drift). The full skills stay on
# demand.
#
# Used by the Claude Code generator (into CLAUDE.md, before the command-prefix
# rewrite) and by build_plugin.py (into the plugin's navigator). Platforms
# without skill discovery inline the full skills instead, which already
# contain these sections.
#
# Usage:
#   source runtime/platforms/_shared/quick-reference.sh
#   emit_quick_reference "$CORE" >> "$OUT"
# Emits nothing when no skill carries the section; exits non-zero only if
# python3 is missing.

emit_quick_reference() {
  python3 - "$1/system-skills" <<'PYEOF'
import os, re, sys
root = sys.argv[1]
parts = []
for skill, title in (("sage-routing", "Routing — when no keyword matches"),
                     ("sage-tiers", "Tiers — what does not lower one"),
                     ("sage-checkpoints", "Checkpoints — the footers")):
    try:
        text = open(os.path.join(root, skill, "SKILL.md"), encoding="utf-8").read()
    except OSError:
        continue
    text = text.replace("\r\n", "\n")
    m = re.search(r"^## At a glance\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if m:
        parts.append("### %s\n\n%s\n\n→ **%s** skill for the rest.\n"
                     % (title, m.group(1).strip(), skill))
if parts:
    print("\n## Quick reference\n")
    print("\n".join(parts), end="")
PYEOF
}
