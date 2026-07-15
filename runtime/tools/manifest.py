#!/usr/bin/env python3
"""manifest.py — keep the cycle manifest's `gate_state` true, mechanically.

WHY THIS EXISTS, AND WHY IT IS A SCRIPT AND NOT A PARAGRAPH

L1 measured resume fidelity end-to-end — the first scenario in Sage's history to
cross a context boundary — and found this. Three runs of the IDENTICAL cycle, all
three completing all three tasks and committing them:

    run 1    gate_state: gates-passed
    run 2    gate_state: plan-approved     <-- "plan approved, no tasks started"
    run 3    gate_state: complete

Run 2 is the bug. Every task was implemented, tested and committed, and the
manifest still said the work had not begun. **A session resuming from that manifest
would read "no tasks started" and do it all again.** The artifact whose entire
purpose is to carry work across a context boundary had drifted from the tree it
describes — which is the one thing it must never do.

There was no enum in force and no state machine. `cycle-protocol.md` said, in
prose, "Advance it at every checkpoint", and prose is read by the same model that
is deciding whether to bother. Three runs produced three vocabularies.

This is the third time this exact bug has been found in this codebase:

    R29  the degradation record   promised in prose  ->  logged 1 of 3 runs
    ADR-10 the task ledger        promised in prose  ->  written 2 of 3 runs
    R120 the manifest gate_state  promised in prose  ->  correct 1 of 3 runs

The first two are hooks and scripts now. So is this.

    "If a rule matters, make it code. If you can't, don't claim it."

WHAT THIS DELIBERATELY WILL NOT DO

It will not advance a cycle to `gates-passed` or `complete`. Those are APPROVAL
states — granted by a human, or by the quality-locked loop after the gates actually
run. A script that advanced a cycle to `gates-passed` because the files looked
finished would be forging the signature the gate exists to collect, and that is a
worse bug than the one it fixes. Evidence may report that work HAS BEGUN. It may
never report that work has been APPROVED.

So the ceiling on derivation is `building`, and the fix is precisely scoped to the
failure that was measured: a manifest that still claims to be pre-implementation
while the implementation is sitting in the tree.

Usage:
    manifest.py advance <manifest.md> --wrote <path>   # a source file was written
    manifest.py sync    <manifest.md>                  # repair from git evidence
    manifest.py check   [<manifest.md> ...]            # exit 1 on an incoherent manifest
    manifest.py resume  [<manifest.md>]                # the resume brief, generated

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

# The vocabulary, in order. The spec-gate hook already rejects anything outside it
# (KNOWN_STATES); this is the same list, and it is the only one.
GATE_STATES = (
    "pre-spec",
    "spec-approved",
    "plan-approved",
    "building",
    "gates-passed",
    "complete",
)
RANK = {s: i for i, s in enumerate(GATE_STATES)}

# Evidence may raise a manifest this far and no further. See the module docstring.
DERIVABLE_CEILING = "building"

# States from which observing a source write means "building has begun". NOT
# pre-spec: a pre-spec cycle that is somehow being edited is a Rule 3 violation, and
# silently advancing it would erase the violation rather than report it.
ADVANCEABLE_FROM = ("spec-approved", "plan-approved")

FRONTMATTER_RE = re.compile(r"\A﻿?---\r?\n(.*?)\r?\n---\s*?\r?\n", re.S)
GATE_RE = re.compile(
    r"^(?P<indent>\s*)gate_state\s*:\s*\"?(?P<val>[A-Za-z0-9_-]+)\"?\s*(?P<tail>#.*)?$",
    re.M,
)

# Paths that are Sage's own machinery, not the user's source. Writing one of these is
# bookkeeping, not implementation, and must not flip a cycle to `building`.
NOT_SOURCE = (".sage/", "sage/", ".claude/", ".agent/", "docs/", "node_modules/")
NOT_SOURCE_SUFFIX = (".md", ".txt", ".lock", ".log")
# Build/interpreter droppings — not source ANYWHERE in the path, not only at the
# root. A fixture without a .gitignore showers these over the evidence otherwise.
NOISE_PARTS = ("__pycache__",)
NOISE_SUFFIX = (".pyc", ".pyo")

# A cycle in one of these states is resumable. `blocked` is deliberately included:
# a blocked cycle needs SURFACING on resume, not skipping — hiding it is how a
# blocker outlives the session that could have answered it.
ACTIVE_STATUS = ("in-progress", "paused", "blocked")


class Problem(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
def split_frontmatter(text: str):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text


def read_gate_state(text: str):
    """(state, ok). ok=False when the frontmatter has no gate_state, or it is not a
    legal value — which is itself a finding, not something to paper over."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        return None, False
    m = GATE_RE.search(fm)
    if not m:
        return None, False
    val = m.group("val").lower()
    return val, val in RANK


def write_gate_state(text: str, new_state: str) -> str:
    """Replace gate_state INSIDE the frontmatter only.

    A `gate_state: building` written in the body prose — and cycle manifests do
    quote their own state in the body — must not be rewritten. The hook would then
    be editing the agent's narration instead of the machine field.
    """
    fm, _ = split_frontmatter(text)
    if fm is None:
        raise Problem("manifest has no frontmatter")
    if not GATE_RE.search(fm):
        raise Problem("manifest frontmatter has no gate_state")

    new_fm = GATE_RE.sub(
        lambda m: f"{m.group('indent')}gate_state: {new_state}"
                  + (f" {m.group('tail')}" if m.group("tail") else ""),
        fm, count=1)
    return text.replace(fm, new_fm, 1)


def is_source(rel: str) -> bool:
    """Is this path the user's implementation, as opposed to Sage's bookkeeping?

    NOTE the prefix stripping. `"./x".lstrip("./")` removes any leading '.' OR '/'
    character — so `.claude/settings.json` becomes `claude/settings.json` and slips
    straight past a `.claude/` exclusion. A unit test caught that here; in
    production it would have advanced a cycle to `building` because the agent
    touched a settings file.
    """
    rel = rel.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    rel = rel.lstrip("/")
    if not rel:
        return False
    if any(rel == p.rstrip("/") or rel.startswith(p) for p in NOT_SOURCE):
        return False
    if rel.endswith(NOT_SOURCE_SUFFIX):
        return False
    if _is_noise(rel):
        return False
    return True


def _is_noise(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return (any(part in rel.split("/") for part in NOISE_PARTS)
            or rel.endswith(NOISE_SUFFIX))


def cycle_is_active(text: str) -> bool:
    fm, _ = split_frontmatter(text)
    if fm is None:
        return False
    m = re.search(r"^\s*status\s*:\s*\"?([A-Za-z-]+)", fm, re.M)
    return not (m and m.group(1).lower() in ("complete", "completed", "abandoned"))


def read_field(text: str, name: str):
    """A single-line scalar out of the frontmatter, or None. Quotes stripped."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        return None
    m = re.search(rf"^\s*{re.escape(name)}\s*:\s*(?P<val>.*)$", fm, re.M)
    if not m:
        return None
    val = m.group("val").split("#", 1)[0].strip().strip('"').strip("'").strip()
    return val or None


def manifest_body(text: str) -> str:
    """Everything after the frontmatter — the sections the previous session wrote."""
    m = FRONTMATTER_RE.match(text)
    return (text[m.end():] if m else text).strip()


# ─────────────────────────────────────────────────────────────────────────────
def advance(manifest_path: pathlib.Path, wrote: str) -> tuple:
    """A source file was written. If this cycle still claims to be pre-implementation,
    say what is true: building.

    Returns (old, new) — new is None when nothing changed.
    """
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    if not cycle_is_active(text):
        return None, None
    if not is_source(wrote):
        return None, None

    state, ok = read_gate_state(text)
    if not ok:
        return state, None                    # illegal/absent — `check` reports it
    if state not in ADVANCEABLE_FROM:
        return state, None                    # already building+, or pre-spec (a violation)

    manifest_path.write_text(write_gate_state(text, DERIVABLE_CEILING),
                             encoding="utf-8")
    return state, DERIVABLE_CEILING


# ─────────────────────────────────────────────────────────────────────────────
def _git(root: pathlib.Path, *args) -> str:
    try:
        p = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout if p.returncode == 0 else ""


def _birth_commit(root: pathlib.Path, manifest: pathlib.Path):
    """The commit that ADDED this manifest — the cycle's anchor in history.
    None when git cannot say (no repo, never committed, outside the root)."""
    rel = manifest.resolve()
    try:
        rel = rel.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    born = [s for s in _git(root, "log", "--diff-filter=A", "--format=%H",
                            "--", rel).splitlines() if s.strip()]
    return born[-1].strip() if born else None


def cycle_evidence(root: pathlib.Path, manifest: pathlib.Path):
    """(commits, changed, untracked) since the cycle began. Empty lists when git
    cannot say — evidence is never guessed."""
    base = _birth_commit(root, manifest)
    if base is None:
        return [], [], []
    commits = [l.strip() for l in
               _git(root, "log", "--format=%h %s", f"{base}..HEAD").splitlines()
               if l.strip()]
    changed = [l.strip() for l in
               _git(root, "diff", "--name-only", base).splitlines() if l.strip()]
    untracked = [l.strip() for l in
                 _git(root, "ls-files", "--others", "--exclude-standard").splitlines()
                 if l.strip()]
    return commits, changed, untracked


def implementation_has_begun(root: pathlib.Path, manifest: pathlib.Path) -> bool:
    """Has any source file changed since this cycle's manifest appeared?

    Committed changes AND uncommitted ones — an agent that writes a file and never
    commits it has still written it, and a check that only read the git log would
    call that a clean tree.

    Fail-soft: no git, no answer, no claim. Returns False rather than guessing.
    """
    _, changed, untracked = cycle_evidence(root, manifest)
    return any(is_source(c) for c in set(changed) | set(untracked))


def sync(manifest_path: pathlib.Path, root: pathlib.Path) -> tuple:
    """Repair a manifest from git evidence. Same ceiling: never past `building`."""
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    if not cycle_is_active(text):
        return None, None
    state, ok = read_gate_state(text)
    if not ok or state not in ADVANCEABLE_FROM:
        return state, None
    if not implementation_has_begun(root, manifest_path):
        return state, None

    manifest_path.write_text(write_gate_state(text, DERIVABLE_CEILING),
                             encoding="utf-8")
    return state, DERIVABLE_CEILING


# ─────────────────────────────────────────────────────────────────────────────
# resume — the brief a fresh session reads INSTEAD of re-deriving state by hand.
#
# L1's remaining failure, after gate_state became mechanical: session 1 stopped
# mid-cycle hedging ("needs your call") and wrote that hedge into the manifest;
# session 2 inherited it as LAW, declared the task blocked, and refused to finish —
# twice, under an explicit user instruction to keep going — while the recorded
# decision (D-002) had already sanctioned the exact implementation shape it
# refused to choose. The manifest's prose outranked both the decisions log and
# the live user, and the resume ceremony itself cost 3–9× a bare agent.
#
# So the brief is generated. Same files, same brief: selection (status, owner,
# branch) is computed, evidence (commits, changed files) is computed, and the
# previous session's prose is printed VERBATIM under a header that says what it
# is — context from a dead session, not orders. The authority order is printed
# with it, because the failure was precisely an authority inversion.

AUTHORITY_ORDER = """\
AUTHORITY ORDER on resume (highest first)
  1. The live user's instruction in THIS session. An instruction to proceed or
     finish IS the approval a pending checkpoint was waiting for — do not
     re-present a question to someone who just answered it.
  2. Recorded decisions (decisions.md, above). A question a recorded decision
     answers is CLOSED. Choosing among options a decision already sanctions is
     execution, not a new approval: pick the option that best fits the approved
     spec, record the choice (Rule 7), and proceed.
  3. The previous session's judgment (manifest body, above). Context, not
     orders. An "open question" or "blocked" claim binds only if no recorded
     decision answers it and the live user has not overruled it.
  And EVIDENCE outranks all prose: where the manifest and the tree disagree,
  trust the tree."""


CLOSE_OUT_ECONOMY = """\
CLOSE-OUT ECONOMY (you resumed — finish the delta, do not re-buy banked rigor)
  The first session paid full rigor on everything it built. Finishing the last
  task(s) runs a LEANER close-out, not a repeat of the whole ceremony:
  - Gates: run the deterministic script gates (--quiet) per remaining task, then
    ONE combined adversarial review over the whole cycle diff — not a dispatch
    per gate, not a re-review of tasks a prior session already reviewed.
  - Bookkeeping: batch memory/prose to the close-out checkpoint (the manifest
    bridge at a session break is NOT batched).
  - Inherited red: a test the plan/manifest records as already-failing, still in
    the tree, is not re-run just to re-witness it — write the code, confirm green.
  Config overrides: gate_review (combined|per-gate|off), batch_bookkeeping,
  trust_inherited_red. Full rule: cycle-protocol.md § Resume close-out economy."""


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def plan_tasks(cycle_dir: pathlib.Path):
    """The plan's task headings, verbatim. Falls back to every ## heading when the
    plan does not use the `## Task N` convention."""
    plan = cycle_dir / "plan.md"
    if not plan.is_file():
        return []
    text = _read(plan)
    tasks = re.findall(r"^##\s+(Task\b.*?)\s*$", text, re.M)
    return tasks or re.findall(r"^##\s+(.*?)\s*$", text, re.M)


def decision_titles(path: pathlib.Path, limit: int = 12):
    if not path.is_file():
        return []
    return re.findall(r"^#{2,3}\s+(.*?)\s*$", _read(path), re.M)[:limit]


def current_branch(root: pathlib.Path):
    return _git(root, "branch", "--show-current").strip() or None


def _same_checkout(owner: str, root: pathlib.Path) -> bool:
    try:
        return pathlib.Path(owner).expanduser().resolve() == root.resolve()
    except OSError:
        return False


def resume_candidates(root: pathlib.Path):
    """(resumable manifests, count excluded as another checkout's). Selection is
    computed, not judged: active status, owner exclusion — the same rules
    continue.workflow states, in code."""
    cands, foreign = [], 0
    for m in find_manifests(root):
        text = _read(m)
        status = (read_field(text, "status") or "").lower()
        if status not in ACTIVE_STATUS:
            continue
        owner = read_field(text, "owner")
        if owner and not _same_checkout(owner, root):
            foreign += 1
            continue
        cands.append(m)
    return cands, foreign


def print_brief(manifest: pathlib.Path, root: pathlib.Path) -> None:
    text = _read(manifest)
    cycle_dir = manifest.parent
    rel = cycle_dir.as_posix()
    try:
        rel = cycle_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        pass

    status = (read_field(text, "status") or "?").lower()
    state, state_ok = read_gate_state(text)
    branch = read_field(text, "branch")
    head = current_branch(root)

    print(f"RESUME BRIEF — {rel}  (generated: same files, same brief)")
    print()
    print("FACTS (frontmatter — machine fields)")
    print(f"  workflow: {read_field(text, 'workflow') or '?'}"
          f"   phase: {read_field(text, 'phase') or '?'}"
          f"   status: {status}")
    print(f"  gate_state: {state or 'MISSING'}"
          + ("" if state_ok else "  <-- not a legal value; run `manifest.py check`"))
    if branch or head:
        marker = "" if (not branch or branch == head) else "  <-- DIFFERENT — surface this"
        print(f"  branch: {branch or '(unrecorded)'}   current: {head or '(no git)'}{marker}")

    if status == "blocked":
        blocked_on = read_field(text, "blocked_on")
        print()
        print("BLOCKED CLAIM")
        if blocked_on:
            print(f"  blocked_on: {blocked_on}")
        else:
            print("  blocked_on: (not recorded — an unnamed blocker is UNVERIFIED)")
        print("  A blocked status binds only if the question is real, unanswered by")
        print("  the recorded decisions below, and not overruled by the live user.")
        print("  Re-derive it from the artifacts before honoring it.")

    tasks = plan_tasks(cycle_dir)
    if tasks:
        print()
        print("PLAN (plan.md task headings)")
        for t in tasks:
            print(f"  - {t}")

    commits, changed, untracked = cycle_evidence(root, manifest)
    print()
    print("EVIDENCE (git, since the cycle began — outranks every prose claim below)")
    if commits:
        print("  commits (newest first):")
        for c in commits[:20]:
            print(f"    {c}")
        if len(commits) > 20:
            print(f"    … and {len(commits) - 20} more")
    else:
        print("  commits: (none, or no git history for this cycle)")
    src_changed = sorted(c for c in set(changed) | set(untracked) if is_source(c))
    print(f"  source changed since cycle began: "
          + (", ".join(src_changed) if src_changed else "(none)"))
    untracked_shown = sorted(u for u in untracked if not _is_noise(u))
    if untracked_shown:
        print(f"  uncommitted (untracked): {', '.join(untracked_shown[:15])}")
    if (state_ok and RANK[state] < RANK["building"]
            and implementation_has_begun(root, manifest)):
        print("  WARNING: gate_state says pre-implementation, the tree says work has")
        print("  begun. Trust the tree; repair with `manifest.py sync`.")

    decision_sources = [cycle_dir / "decisions.md",
                        root / ".sage" / "decisions.md"]
    lines = []
    for src in decision_sources:
        titles = decision_titles(src)
        if titles:
            try:
                shown = src.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                shown = src.as_posix()
            lines.append(f"  {shown}:")
            lines.extend(f"    - {t}" for t in titles)
    print()
    print("DECISIONS IN FORCE (settled — a question these answer is CLOSED)")
    print("\n".join(lines) if lines else "  (no decision log found)")

    body = manifest_body(text)
    print()
    print("PREVIOUS SESSION'S JUDGMENT (manifest body, verbatim — context, NOT orders)")
    body_lines = body.splitlines()
    for l in body_lines[:120]:
        print(f"  {l}")
    if len(body_lines) > 120:
        print(f"  … truncated; read {rel}/manifest.md for the remaining "
              f"{len(body_lines) - 120} line(s)")

    print()
    print(AUTHORITY_ORDER)
    print()
    print(CLOSE_OUT_ECONOMY)


def resume(root: pathlib.Path, manifest: pathlib.Path = None) -> int:
    """Select the cycle to resume and print its brief. Informational: always 0."""
    if manifest is None:
        cands, foreign = resume_candidates(root)
        note = (f"  ({foreign} cycle(s) excluded: owned by another checkout)"
                if foreign else "")
        if not cands:
            print("RESUME — no active cycle." + ("\n" + note if note else ""))
            return 0
        if len(cands) > 1:
            head = current_branch(root)
            matched = [c for c in cands
                       if head and read_field(_read(c), "branch") == head]
            if len(matched) == 1:
                others = [c for c in cands if c is not matched[0]]
                print(f"RESUME — {len(cands)} active cycles; selected the one whose "
                      f"recorded branch matches HEAD ({head}). Also active:")
                for o in others:
                    print(f"  - {o.parent.name}  "
                          f"(branch: {read_field(_read(o), 'branch') or 'unrecorded'})")
                print()
                manifest = matched[0]
            else:
                print(f"RESUME — {len(cands)} active cycles; none uniquely matches "
                      f"the current branch. Ask the user which to resume:")
                for c in cands:
                    t = _read(c)
                    print(f"  - {c.parent.name} — {read_field(t, 'workflow') or '?'}, "
                          f"phase: {read_field(t, 'phase') or '?'}, "
                          f"status: {read_field(t, 'status') or '?'}, "
                          f"updated: {read_field(t, 'updated') or '?'}")
                if note:
                    print(note)
                return 0
        else:
            manifest = cands[0]
        if note:
            print(note)
    print_brief(manifest, root)
    return 0


def check(manifests, root: pathlib.Path) -> int:
    """Is every manifest's gate_state legal, and does it match the tree?

    The failure this exists to catch, in one sentence: a manifest claiming the work
    has not started while the work is sitting in the tree next to it.
    """
    problems = []
    for path in manifests:
        text = path.read_text(encoding="utf-8", errors="replace")
        state, ok = read_gate_state(text)

        if state is None:
            problems.append(f"{path}: no gate_state in frontmatter")
            continue
        if not ok:
            problems.append(
                f"{path}: gate_state {state!r} is not one of "
                f"{', '.join(GATE_STATES)}")
            continue
        if not cycle_is_active(text):
            continue

        if ((read_field(text, "status") or "").lower() == "blocked"
                and not read_field(text, "blocked_on")):
            problems.append(
                f"{path}: status is 'blocked' but blocked_on: is empty or absent.\n"
                f"      A blocker nobody can name is not a blocker — it is a dead\n"
                f"      session's hesitation, and the next session will inherit it "
                f"as law.\n"
                f"      Fix: record blocked_on: (the question, the options, whose "
                f"call it is)\n"
                f"      or set status back to in-progress.")

        if (RANK[state] < RANK["building"]
                and implementation_has_begun(root, path)):
            problems.append(
                f"{path}: gate_state is {state!r}, but source files have changed "
                f"since this cycle began.\n"
                f"      The manifest says the work has not started. The tree says "
                f"it has.\n"
                f"      A session resuming from this manifest would redo the work.\n"
                f"      Fix: python3 sage/runtime/tools/manifest.py sync {path}")

    if problems:
        print("✗ incoherent cycle manifest(s):\n")
        for p in problems:
            print(f"  {p}\n")
        return 1

    print(f"OK — {len(manifests)} manifest(s); every gate_state is legal and "
          f"consistent with the tree.")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
def find_manifests(root: pathlib.Path) -> list:
    work = root / ".sage" / "work"
    if not work.is_dir():
        return []
    return sorted(work.glob("*/manifest.md"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("advance", help="a source file was written — record that")
    a.add_argument("manifest", type=pathlib.Path)
    a.add_argument("--wrote", required=True, help="the path that was written")

    s = sub.add_parser("sync", help="repair gate_state from git evidence")
    s.add_argument("manifest", type=pathlib.Path)
    s.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())

    c = sub.add_parser("check", help="exit 1 if a manifest contradicts the tree")
    c.add_argument("manifest", type=pathlib.Path, nargs="*")
    c.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())

    r = sub.add_parser("resume", help="print the resume brief for the active cycle")
    r.add_argument("manifest", type=pathlib.Path, nargs="?",
                   help="a specific cycle's manifest (default: select automatically)")
    r.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())

    args = p.parse_args(argv)

    try:
        if args.cmd == "advance":
            old, new = advance(args.manifest, args.wrote)
            if new:
                print(f"gate_state: {old} → {new}")
            return 0

        if args.cmd == "sync":
            old, new = sync(args.manifest, args.repo_root.resolve())
            print(f"gate_state: {old} → {new}" if new
                  else f"gate_state: {old} (unchanged — nothing to repair)")
            return 0

        if args.cmd == "resume":
            return resume(args.repo_root.resolve(), args.manifest)

        manifests = args.manifest or find_manifests(args.repo_root.resolve())
        if not manifests:
            print("OK — no cycle manifests.")
            return 0
        return check(manifests, args.repo_root.resolve())

    except (Problem, OSError) as exc:
        print(f"✗ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
