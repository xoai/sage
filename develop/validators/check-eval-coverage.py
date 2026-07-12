#!/usr/bin/env python3
"""Eval coverage validator — ADR-14's contract, made mechanical.

Two jobs, and they are different jobs:

  --check (default)   The registry is complete and truthful. Every behavioral
                      surface on disk has a row in coverage.yaml; every row
                      points at a file that exists; every scenario it names is
                      real. A new skill or workflow with no row fails here.

  --diff <base>       The change contract. A commit that alters a mapped
                      surface must also touch one of the scenarios covering it,
                      or update that surface's mapping, or declare itself
                      behavior-neutral with `#eval-neutral` in the commit body.

The second is the one with teeth, and the one that would have caught the
mistake this whole program exists to correct: content edited, claims unchanged,
nothing re-measured.

Exit codes follow the Sage gate convention: 0 pass, 1 fail, 2 unverifiable.
Stdlib only — this runs in CI on python 3.8 with nothing installed.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COVERAGE = REPO_ROOT / "develop" / "evals" / "coverage.yaml"
SCENARIOS = REPO_ROOT / "develop" / "evals" / "scenarios"

# The eager layer lives inside a heredoc in a shell script, so its "surfaces"
# are markdown headings, not files. This is where they live.
EAGER_BODY = REPO_ROOT / "runtime" / "platforms" / "_shared" / "instructions-body.sh"
HEREDOC_OPEN = "INSTRUCTIONS_EOF"

NEUTRAL_TAG = "#eval-neutral"

# Where surfaces are discovered from. Each entry: (kind, glob, root-relative).
# Adding a file that matches one of these globs and forgetting coverage.yaml is
# the failure this table exists to produce.
DISCOVERY = [
    ("workflow",     "core/workflows/*.workflow.md"),
    ("sub-workflow", "core/workflows/sub-workflows/*.workflow.md"),
    ("capability",   "core/capabilities/*/*/SKILL.md"),
    ("skill",        "skills/*/SKILL.md"),
    ("system-skill", "core/system-skills/*/SKILL.md"),
    # The plugin overlay is what PLUGIN users actually receive, and until now the
    # coverage contract could not see any of it — 11 skills, ~2,500 lines, in the
    # blind spot. That is exactly how sage-navigator drifted for two releases while
    # shipping a routing table a release out of date: nothing was watching the
    # thing users were being given.
    ("overlay-skill", "runtime/plugin-overlay/skills/*/SKILL.md"),
    ("hook",         "runtime/platforms/claude-code/hooks/*.sh"),
    ("gate",         "core/gates/scripts/*.sh"),
]


class CoverageError(Exception):
    pass


# ── A deliberately small YAML reader ─────────────────────────────────────────
#
# The repo's other validators either hand-roll this (context_budget.py) or
# treat PyYAML as optional and exit 2 without it (check-workflows.py). Exit 2
# is wrong for a blocking gate — a check that shrugs when a dependency is
# missing is a check that can be disabled by uninstalling something. So: no
# dependency, and a grammar narrow enough that a hand parser is honest.
#
# Supported, and nothing else:
#   key: value            scalar (optionally "quoted")
#   key: [a, b]           inline list
#   key: >                folded block; continuation lines are more-indented
#   two-space nesting for surface ids, four-space for their fields

def parse_coverage(text):
    """coverage.yaml → {"version": int, "surfaces": {id: {field: value}}}."""
    doc = {"version": None, "surfaces": {}}
    lines = text.splitlines()
    i = 0
    section = None
    surface = None

    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()

        if indent == 0:
            if line.startswith("version:"):
                doc["version"] = int(line.split(":", 1)[1].strip())
                section = None
            elif line == "surfaces:":
                section = "surfaces"
            else:
                raise CoverageError("unexpected top-level line: %r" % line)
            surface = None
            continue

        if section != "surfaces":
            raise CoverageError("indented line outside surfaces: %r" % line)

        if indent == 2:
            if not line.endswith(":"):
                raise CoverageError("surface id must end with ':' — got %r" % line)
            surface = line[:-1].strip()
            if surface in doc["surfaces"]:
                raise CoverageError("duplicate surface id: %s" % surface)
            doc["surfaces"][surface] = {}
            continue

        if indent == 4:
            if surface is None:
                raise CoverageError("field before any surface id: %r" % line)
            if ":" not in line:
                raise CoverageError("field must be 'key: value' — got %r" % line)
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()

            if value == ">":  # folded block: swallow the more-indented tail
                block = []
                while i < len(lines):
                    nxt = lines[i]
                    if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= 4:
                        break
                    block.append(nxt.strip())
                    i += 1
                value = " ".join(b for b in block if b)
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                value = [v.strip() for v in inner.split(",") if v.strip()]
            else:
                value = value.strip('"').strip("'")

            doc["surfaces"][surface][key] = value
            continue

        raise CoverageError("bad indent (%d) at %r" % (indent, line))

    if doc["version"] is None:
        raise CoverageError("no `version:` key")
    return doc


# ── Discovery: what surfaces actually exist on disk ──────────────────────────

def eager_anchors(text):
    """Markdown headings inside the instructions heredoc, in order.

    Returns [(anchor, start_line, end_line)] with 1-based line numbers into the
    shell file, so a diff hunk can be attributed to the block it landed in.
    """
    lines = text.splitlines()
    inside = False
    found = []
    for n, line in enumerate(lines, start=1):
        if not inside:
            if HEREDOC_OPEN in line and "<<" in line:
                inside = True
            continue
        if line.strip() == HEREDOC_OPEN:
            break
        if re.match(r"^#{1,3} \S", line):
            found.append((line.strip(), n))

    end_of_body = next(
        (n for n, l in enumerate(lines, start=1)
         if l.strip() == HEREDOC_OPEN and n > (found[0][1] if found else 0)),
        len(lines),
    )
    blocks = []
    for idx, (anchor, start) in enumerate(found):
        end = found[idx + 1][1] - 1 if idx + 1 < len(found) else end_of_body - 1
        blocks.append((anchor, start, end))
    return blocks


def discover(root):
    """Every behavioral surface on disk → {"path::anchor" or "path": kind}."""
    found = {}
    for kind, pattern in DISCOVERY:
        for p in sorted(root.glob(pattern)):
            found[str(p.relative_to(root))] = kind

    if EAGER_BODY.exists():
        rel = str(EAGER_BODY.relative_to(root))
        for anchor, _s, _e in eager_anchors(EAGER_BODY.read_text()):
            found["%s::%s" % (rel, anchor)] = "eager-block"
    return found


def surface_key(entry):
    """The identity of a mapped surface, matching discover()'s keys."""
    if entry.get("kind") == "eager-block":
        return "%s::%s" % (entry["path"], entry.get("anchor", ""))
    return entry["path"]


def known_scenarios():
    ids = set()
    if not SCENARIOS.is_dir():
        return ids
    for d in sorted(SCENARIOS.iterdir()):
        sj = d / "scenario.json"
        if sj.is_file():
            m = re.search(r'"id"\s*:\s*"([^"]+)"', sj.read_text())
            if m:
                ids.add(m.group(1))
    return ids


# ── --check: the registry is complete and truthful ───────────────────────────

def check(doc, root):
    problems = []
    surfaces = doc["surfaces"]
    scenarios = known_scenarios()

    mapped = {}
    for sid, entry in surfaces.items():
        if "path" not in entry:
            problems.append("%s: no `path`" % sid)
            continue
        if "kind" not in entry:
            problems.append("%s: no `kind`" % sid)

        has_cov = "covered-by" in entry
        has_unc = "uncovered" in entry
        if has_cov and has_unc:
            problems.append(
                "%s: has BOTH `covered-by` and `uncovered` — pick one. A surface "
                "is measured or it is debt; it cannot be both." % sid)
        if not has_cov and not has_unc:
            problems.append(
                "%s: has neither `covered-by` nor `uncovered`. There is no third "
                "option — name the scenarios, or say in prose that none exist." % sid)

        p = root / entry["path"]
        if not p.exists():
            problems.append("%s: path does not exist: %s" % (sid, entry["path"]))

        if entry.get("kind") == "eager-block":
            anchor = entry.get("anchor")
            if not anchor:
                problems.append("%s: kind is eager-block but no `anchor`" % sid)
            elif p.exists():
                anchors = [a for a, _s, _e in eager_anchors(p.read_text())]
                if anchor not in anchors:
                    problems.append(
                        "%s: anchor not found in %s: %r (block moved or was "
                        "renamed — update the mapping)" % (sid, entry["path"], anchor))

        for scen in entry.get("covered-by", []):
            if scen not in scenarios:
                problems.append(
                    "%s: names scenario %s, which does not exist in "
                    "develop/evals/scenarios/" % (sid, scen))

        if has_unc and not str(entry["uncovered"]).strip():
            problems.append("%s: `uncovered` is empty — write the reason" % sid)

        mapped[surface_key(entry)] = sid

    on_disk = discover(root)
    for key, kind in sorted(on_disk.items()):
        if key not in mapped:
            problems.append(
                "UNMAPPED %s: %s\n"
                "      Every behavioral surface needs a row in coverage.yaml — "
                "either the scenarios that cover it, or an honest `uncovered:`."
                % (kind, key))

    for key, sid in sorted(mapped.items()):
        if key not in on_disk:
            problems.append(
                "STALE mapping %s → %s (no such surface on disk; delete the row "
                "or fix the path)" % (sid, key))

    return problems


# ── --diff: the change contract ──────────────────────────────────────────────

def git(args, cwd=REPO_ROOT):
    return subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True, check=False)


def changed_files(base):
    r = git(["diff", "--name-only", base])
    if r.returncode != 0:
        raise CoverageError("git diff failed against %r: %s" % (base, r.stderr.strip()))
    files = {f for f in r.stdout.splitlines() if f.strip()}

    # Untracked files are changes too. Without this, adding a brand-new scenario
    # directory — the single most common way to satisfy this contract — would be
    # invisible to it, and the validator would reject the very fix it demanded.
    u = git(["ls-files", "--others", "--exclude-standard"])
    if u.returncode == 0:
        files.update(f for f in u.stdout.splitlines() if f.strip())
    return files


def changed_lines(base, path):
    """New-file line numbers touched in `path`, from unified-0 hunk headers."""
    r = git(["diff", "-U0", base, "--", path])
    touched = set()
    for line in r.stdout.splitlines():
        m = re.match(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", line)
        if m:
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) else 1
            touched.update(range(start, start + max(count, 1)))
    return touched


def commit_bodies(base):
    r = git(["log", "--format=%B", "%s..HEAD" % base])
    return r.stdout if r.returncode == 0 else ""


def entry_at(base, sid):
    """That surface's mapping as it existed at `base` (for change detection)."""
    r = git(["show", "%s:develop/evals/coverage.yaml" % base])
    if r.returncode != 0:
        return None
    try:
        return parse_coverage(r.stdout)["surfaces"].get(sid)
    except CoverageError:
        return None


def check_diff(doc, root, base):
    if not (root / ".git").exists():
        print("⚠️  UNVERIFIABLE — not a git repository; cannot diff.", file=sys.stderr)
        return None

    files = changed_files(base)
    if not files:
        print("OK — nothing changed against %s." % base)
        return []

    neutral = NEUTRAL_TAG in commit_bodies(base)
    problems = []
    touched_surfaces = []

    # Line-level attribution for the eager body: one file, twenty surfaces.
    eager_rel = str(EAGER_BODY.relative_to(root))
    eager_hits = set()
    if eager_rel in files and EAGER_BODY.exists():
        hit_lines = changed_lines(base, eager_rel)
        for anchor, start, end in eager_anchors(EAGER_BODY.read_text()):
            if any(start <= n <= end for n in hit_lines):
                eager_hits.add(anchor)

    for sid, entry in doc["surfaces"].items():
        path = entry.get("path")
        if not path:
            continue
        if entry.get("kind") == "eager-block":
            if entry.get("anchor") not in eager_hits:
                continue
        elif path not in files:
            continue

        touched_surfaces.append(sid)

        covering = entry.get("covered-by", [])
        scenario_touched = any(
            f.startswith("develop/evals/scenarios/") and
            any(f.split("/")[3].startswith(s + "-") or f.split("/")[3] == s
                for s in covering)
            for f in files if f.count("/") >= 3
        )
        mapping_changed = (
            "develop/evals/coverage.yaml" in files
            and entry_at(base, sid) != entry
        )

        if scenario_touched or mapping_changed or neutral:
            continue

        if covering:
            problems.append(
                "%s changed, but none of its covering scenarios (%s) were "
                "touched.\n"
                "      Either the change is behavioral — in which case re-measure "
                "it — or it is not, in which case say so with %s in the commit "
                "body." % (sid, ", ".join(covering), NEUTRAL_TAG))
        else:
            problems.append(
                "%s changed, and nothing covers it (`uncovered`).\n"
                "      Three ways out: write a scenario and map it; revise the "
                "`uncovered:` reason to reflect the new behavior; or tag the "
                "commit %s if it changes no behavior." % (sid, NEUTRAL_TAG))

    if neutral and touched_surfaces:
        print("note: %s accepted for %d touched surface(s): %s"
              % (NEUTRAL_TAG, len(touched_surfaces), ", ".join(sorted(touched_surfaces))))
        print("      (logged, not waived — a reviewer can see this line.)")

    return problems


# ── Reporting ────────────────────────────────────────────────────────────────

def report_debt(doc):
    unc = [(s, e) for s, e in doc["surfaces"].items() if "uncovered" in e]
    cov = [(s, e) for s, e in doc["surfaces"].items() if "covered-by" in e]
    total = len(doc["surfaces"])
    print("Eval coverage — %d surfaces: %d covered, %d uncovered (%.0f%% debt)"
          % (total, len(cov), len(unc), 100.0 * len(unc) / total if total else 0))
    print()
    for sid, entry in sorted(unc):
        print("  %-36s %s" % (sid, str(entry["uncovered"])[:88]))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="registry integrity (default)")
    ap.add_argument("--diff", metavar="BASE",
                    help="enforce the change contract against a git ref")
    ap.add_argument("--list-uncovered", action="store_true",
                    help="print the coverage debt (feeds eval-baseline's appendix)")
    args = ap.parse_args()

    if not COVERAGE.exists():
        print("❌ FAIL — %s does not exist." % COVERAGE, file=sys.stderr)
        return 1

    try:
        doc = parse_coverage(COVERAGE.read_text())
    except CoverageError as e:
        print("❌ FAIL — coverage.yaml does not parse: %s" % e, file=sys.stderr)
        return 1

    if args.list_uncovered:
        return report_debt(doc)

    problems = check(doc, REPO_ROOT)

    if args.diff:
        try:
            diff_problems = check_diff(doc, REPO_ROOT, args.diff)
        except CoverageError as e:
            print("⚠️  UNVERIFIABLE — %s" % e, file=sys.stderr)
            return 2
        if diff_problems is None:
            return 2
        problems.extend(diff_problems)

    if problems:
        print("❌ FAIL — eval coverage contract violated (%d):\n" % len(problems),
              file=sys.stderr)
        for p in problems:
            print("  • %s" % p, file=sys.stderr)
        print("\n  ADR-14: a behavioral surface is measured, or its debt is "
              "written down. Silence is not an option.", file=sys.stderr)
        return 1

    n = len(doc["surfaces"])
    covered = sum(1 for e in doc["surfaces"].values() if "covered-by" in e)
    print("OK — %d surface(s) mapped; %d covered, %d honest `uncovered:` "
          "entries.%s" % (n, covered, n - covered,
                          " Change contract holds against %s." % args.diff
                          if args.diff else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
