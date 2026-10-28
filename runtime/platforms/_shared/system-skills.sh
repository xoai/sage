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

# List the system skills instead of inlining them, for an instructions file with
# a size cap the inlined text does not fit under.
#
# Codex reads at most 32 KiB of AGENTS.md (project_doc_max_bytes) and drops the
# rest without a word. Inlined, the seven skills are ~25 KB of a ~33.5 KB file,
# and they come last: a default install lost the tail of Sage's instructions, and
# left no room at all for the project's own AGENTS.md text.
#
# Nothing is lost by listing them. `sage init` copies the framework into the
# project, so every SKILL.md is a file the agent can read. Each entry carries the
# skill's own description — the same trigger text native discovery matches on —
# so this is discovery done by hand: the model sees what each skill is for, and
# reads it when that matches. The descriptions come from the files, so there is
# no second copy to drift.
#
# Usage:
#   emit_system_skills_index "$CORE" "sage/core" >> "$OUT"
#   (second argument: the core directory as a path relative to the
#    instructions file — what the model will be told to read)
emit_system_skills_index() {
  local core="$1" rel="$2"
  local dir="$core/system-skills"
  [ -d "$dir" ] || return 0

  echo ""
  echo "---"
  echo ""
  echo "# Reference"
  echo ""
  echo "On platforms with native skill discovery, the skills below are fetched on"
  echo "demand. This platform has none, and this file has a size cap they do not fit"
  echo "under, so they are listed instead of inlined. Each one is a file in this"
  echo "project (paths are relative to this file). When a description matches what"
  echo "you are doing — or a rule above says \"→ <name> skill\" — read that file and"
  echo "follow it before you go on."

  local sd name desc
  for sd in "$dir"/*/; do
    [ -d "$sd" ] || continue
    [ -f "$sd/SKILL.md" ] || continue
    name="$(basename "$sd")"
    # The frontmatter description: one line, or a folded block (`>` / `|`).
    desc="$(awk '
      NR == 1 { if ($0 != "---") exit; next }
      /^---$/ { exit }
      fold && /^[ \t]/ { sub(/^[ \t]+/, ""); d = d (d == "" ? "" : " ") $0; next }
      fold { exit }
      /^description:/ {
        v = $0; sub(/^description:[ \t]*/, "", v)
        if (v ~ /^[>|][-+]?$/) { fold = 1; next }
        d = v; exit
      }
      END { print d }
    ' "$sd/SKILL.md")"
    echo ""
    echo "- **$name** — \`$rel/system-skills/$name/SKILL.md\`"
    [ -n "$desc" ] && echo "  $desc"
  done
  return 0
}
