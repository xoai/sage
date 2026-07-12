#!/usr/bin/env bash
# Inline the system skills into an instructions file, for platforms that cannot
# fetch them on demand.
#
# WHY THIS EXISTS, AND WHY IT EXISTS AS A SHARED FUNCTION
#
# ADR-9 moved ~220 lines out of the eager layer and into seven description-
# triggered skills. On claude-code that content is fetched when a description
# matches. On every platform WITHOUT `native-skill-discovery`, there is nothing
# to fetch it — so it must be inlined, or it does not exist for those users at
# all.
#
# The generic generator did this. The four community generators did not, because
# they source instructions-body.sh directly and nobody thought about them. The
# result: their users silently lost the routing chain, the memory guide, the gates
# explainer, the checkpoint protocol, tiers, the constitution's full text and the
# decision-log protocol. Their instructions file still POINTED at those skills —
# "→ sage-gates skill" — while the skills were unreachable.
#
# The conformance suite (P4-T4) caught it: "declared false, and nothing is
# inlined — the content is unreachable on this platform". That is the entire
# argument for having built the suite, demonstrated on a bug the suite's own
# author had shipped two phases earlier.
#
# So the inlining lives here, once, and every generator without discovery calls
# it. A second copy would drift, and the drift would be silent in exactly this
# way again.
#
# Usage:
#   source runtime/platforms/_shared/system-skills.sh
#   emit_system_skills_inline "$CORE" >> "$OUT"

emit_system_skills_inline() {
  local core="$1"
  local dir="$core/system-skills"
  [ -d "$dir" ] || return 0

  echo ""
  echo "---"
  echo ""
  echo "# Reference"
  echo ""
  echo "On platforms with native skill discovery, everything below is fetched on"
  echo "demand when it is relevant. This platform has no discovery mechanism, so it"
  echo "is inlined. Read the section that matches what you are doing."

  local sd
  for sd in "$dir"/*/; do
    [ -d "$sd" ] || continue
    [ -f "$sd/SKILL.md" ] || continue
    echo ""
    # Strip the YAML frontmatter: it is trigger metadata for a mechanism this
    # platform does not have, and it would read as noise.
    sed '1{/^---$/!q;};1,/^---$/d' "$sd/SKILL.md"
  done
}
