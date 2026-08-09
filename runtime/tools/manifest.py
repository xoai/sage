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
    manifest.py scope derive <manifest.md> [--refresh] # plan Files:/Output: → scope block
    manifest.py scope add-collateral <path> --task T3 --reason "..."
    manifest.py graph derive <manifest.md> [--refresh] # plan tasks/deps → task_graph block

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
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


def write_field(text: str, name: str, value: str) -> str:
    """Replace a top-level `name:` field INSIDE the frontmatter only (same rule as
    write_gate_state — body prose that quotes the field must not be rewritten).
    Raises Problem if the field is absent: silently appending a field the template
    doesn't carry is how two spellings of the same fact start to coexist."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        raise Problem("manifest has no frontmatter")
    # Column-0 only: `^[ \t]*status:` also matched a LEDGER ENTRY's status
    # line when the tasks: block preceded the scalar, and close-out then
    # rewrote ledger entry 1 instead of the cycle status (re-audit finding
    # 3 — reproduced). Top-level keys are column-0 in every Sage writer.
    pat = re.compile(r"^%s\s*:[^\n]*$" % re.escape(name), re.M)
    if not pat.search(fm):
        raise Problem(f"manifest frontmatter has no `{name}:` field")
    new_fm = pat.sub(f"{name}: {value}", fm, count=1)
    return text.replace(fm, new_fm, 1)


def stamp_updated(text: str) -> str:
    """Refresh `updated:` — a mechanical fact (something changed just now), so the
    machine owns it. Fail-soft: a manifest without the field is left unchanged
    rather than grown a new one."""
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        return write_field(text, "updated", now)
    except Problem:
        return text


def replace_section(text: str, heading: str, body: str) -> str:
    """Replace the content of a `## {heading}` section (up to the next `## ` or
    EOF), or append the section if the manifest doesn't have it yet. The heading
    line itself is preserved/created verbatim."""
    pat = re.compile(
        r"(^##\s+%s\s*\n)(.*?)(?=^##\s|\Z)" % re.escape(heading), re.M | re.S)
    new_block = r"\g<1>" + "\n" + body.rstrip("\n").replace("\\", "\\\\") + "\n\n"
    if pat.search(text):
        return pat.sub(new_block, text, count=1)
    return text.rstrip("\n") + f"\n\n## {heading}\n\n{body.rstrip(chr(10))}\n"


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
    m = re.search(r"^status\s*:\s*\"?([A-Za-z-]+)", fm, re.M)
    return not (m and m.group(1).lower() in ("complete", "completed", "abandoned"))


def read_field(text: str, name: str):
    """A single-line scalar out of the frontmatter, or None. Quotes stripped."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        return None
    # Column-0 only — same reasoning as write_field: a nested homonym in
    # the ledger/lanes blocks must never answer for the top-level scalar.
    m = re.search(rf"^{re.escape(name)}\s*:\s*(?P<val>.*)$", fm, re.M)
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

    # updated: is stamped in the same write — a mechanical fact (the cycle just
    # changed), and every field the machine owns is one the model no longer
    # spends an API call maintaining.
    manifest_path.write_text(stamp_updated(write_gate_state(text, DERIVABLE_CEILING)),
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

    # updated: is stamped in the same write — a mechanical fact (the cycle just
    # changed), and every field the machine owns is one the model no longer
    # spends an API call maintaining.
    manifest_path.write_text(stamp_updated(write_gate_state(text, DERIVABLE_CEILING)),
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
  - Bookkeeping: ONE command at the close-out checkpoint — `manifest.py
    close-out <manifest> --summary ... --decision ... --complete-task N` — never
    incremental hand-edits of manifest/decisions/plan (updated: and gate_state
    are machine-owned). The session-break bridge uses the same command.
  - Inherited red: a test the plan/manifest records as already-failing, still in
    the tree, is not re-run just to re-witness it — write the code, confirm green.
  - Memory: skip the memory search/store — the brief already carries the context
    and its value at this horizon is measured null (resume_memory: skip).
  - Tests: run the targeted test per step; the FULL suite runs once at close-out
    (Gate 5), not per task (resume_test_cadence: lean).
  Config overrides: gate_review (combined|per-gate|off), batch_bookkeeping,
  trust_inherited_red, resume_memory (skip|keep), resume_test_cadence (lean|full).
  Full rule: cycle-protocol.md § Resume close-out economy."""


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def plan_tasks(cycle_dir: pathlib.Path):
    """The plan's tasks: `## Task N` headings, else the plan template's
    canonical `- [ ] **Task N:**` checkbox bullets (which real plans use —
    the resume display was printing section headings for them, field report
    2026-08-04), else every ## heading as the last resort."""
    plan = cycle_dir / "plan.md"
    if not plan.is_file():
        return []
    text = _read(plan)
    tasks = re.findall(r"^##\s+(Task\b.*?)\s*$", text, re.M)
    if not tasks:
        tasks = ["Task %s: %s" % (n, t) for n, t in re.findall(
            r"^\s*-\s*\[[ xX]\]\s*\*\*Task\s+(\d+)\s*:?\*\*:?\s*(.+?)\s*$",
            text, re.M)]
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

    # A7: a session that died mid-burst left lanes on disk. The brief lists
    # them from the lanes: block (never re-derived from prose) so the resumer
    # either reconstructs the burst or harvests each lane deliberately —
    # an unlisted worktree is work that silently rots.
    lanes = read_lanes(text)
    open_lanes = [r for r in (lanes["records"] if lanes else [])
                  if r["state"] in LANE_ACTIVE_STATES]
    if open_lanes:
        print()
        print("OPEN LANES (parallel burst in flight when the session ended)")
        if lanes["burst_base"]:
            print(f"  burst base: {lanes['burst_base']}")
        for r in open_lanes:
            note = f" — {r['note']}" if r["note"] else ""
            print(f"  - T{r['task']} [{r['state']}] branch {r['branch']} "
                  f"worktree {r['worktree']}{note}")
        print("  Reconstruct with `lanes.py schedule` (the graph knows what was")
        print("  eligible), or harvest a lane you are abandoning:")
        print("  `sage worktree remove <dir>` — harvest-then-remove, never bare")
        print("  `git worktree remove` (it drops the gitignored .sage state).")

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


# close-out — the ONE bookkeeping write a resume close-out makes.
#
# The 2026-07-15 post-lever profile found bookkeeping at ~29% of the resume
# session: 8 incremental edits to manifest.md/decisions.md/plan.md, each a
# separate API call re-paying ~100k tokens of context. `batch_bookkeeping` asked
# the model, in prose, to defer those writes — and the model didn't. Same lesson
# as gate_state and the task ledger: if a rule matters, make it code.
#
# So the close-out write is a command. The model composes its judgment ONCE
# (summary, next step, decisions, which tasks completed) and this applies all of
# it in one pass — one call instead of eight. What stays the model's: the words.
# What stops being the model's: the ceremony of applying them file by file.

def close_out(manifest: pathlib.Path, summary=None, next_step=None,
              decisions=(), complete_tasks=(), open_questions=None,
              status=None, phase=None, blocked_on=None) -> int:
    text = manifest.read_text(encoding="utf-8", errors="replace")
    cycle_dir = manifest.parent
    wrote = []

    if summary:
        text = replace_section(text, "Context summary", summary)
        wrote.append("context summary")
    if open_questions is not None:
        text = replace_section(text, "Open questions",
                               open_questions or "(none)")
        wrote.append("open questions")
    if next_step:
        new_text, n = re.subn(r"^(\*\*Next step:\*\*).*$",
                              r"\g<1> " + next_step.replace("\\", "\\\\"),
                              text, count=1, flags=re.M)
        if n:
            text = new_text
            wrote.append("next step")
        else:
            print("note: no `**Next step:**` line found — skipped")
    if phase:
        text = write_field(text, "phase", phase)
        wrote.append(f"phase={phase}")
    if status:
        text = write_field(text, "status", status)
        wrote.append(f"status={status}")
    if blocked_on is not None:
        # `status: blocked` without blocked_on: fails `check` — so the command
        # that sets a blocker must be able to name its question in the same pass.
        text = write_field(text, "blocked_on", f"\"{blocked_on}\"")
        wrote.append("blocked_on")
    text = stamp_updated(text)
    manifest.write_text(text, encoding="utf-8")

    if decisions:
        dpath = cycle_dir / "decisions.md"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        entries = "\n".join(f"### {today} — {d}\n" for d in decisions)
        old = dpath.read_text(encoding="utf-8", errors="replace") if dpath.is_file() else ""
        # Prepend below a `# ` title line if one exists (Rule 7: prepend).
        m = re.match(r"(\A#[^\n]*\n+)", old)
        head, rest = (m.group(1), old[m.end():]) if m else ("", old)
        dpath.write_text(head + entries + "\n" + rest, encoding="utf-8")
        wrote.append(f"{len(decisions)} decision(s)")

    if complete_tasks:
        plan = cycle_dir / "plan.md"
        if not plan.is_file():
            raise Problem(f"--complete-task given but {plan} does not exist")
        ptext = plan.read_text(encoding="utf-8", errors="replace")
        missed = []
        for n in complete_tasks:
            new_ptext, count = re.subn(
                r"^(\s*-\s*)\[ \](\s*\*{0,2}Task\s+%d\b)" % n,
                r"\g<1>[x]\g<2>", ptext, count=1, flags=re.M)
            if count:
                ptext = new_ptext
            else:
                missed.append(n)
        plan.write_text(ptext, encoding="utf-8")
        wrote.append(f"checked task(s) {','.join(str(n) for n in complete_tasks if n not in missed)}")
        for n in missed:
            print(f"note: Task {n} not found unchecked in plan.md — skipped")

    print("close-out: wrote " + (", ".join(wrote) if wrote else "nothing (no args)")
          + f" · updated: stamped · 1 pass")

    # SG-19: the scope judge's per-cycle totals surface at close-out —
    # cost and efficacy stay UNCLAIMED in docs until measured, but the
    # numbers themselves are always on the table.
    journal = cycle_dir / "scope-journal.jsonl"
    if journal.is_file():
        try:
            sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
            import scope_judge as _sj
            v, d, inj, tin, tout = _sj.cycle_totals(cycle_dir)
            print(f"scope-judge: {v} verdict(s), {d} drift, {inj} "
                  f"injection(s), tokens {tin} in / {tout} out")
        except Exception:
            pass
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# scope — declared scope becomes machine state (SG-1/SG-2).
#
# The plan already declares, per task, exactly which files the work may touch
# (`Files:`) and which documents it may produce (`Output:`). Until now that
# declaration was prose — read by the same model that is deciding whether to
# wander. `scope derive` parses it ONCE, at plan approval, into a `scope:`
# block in the manifest frontmatter, and the scope-gate hook reads the block,
# not the plan. Sage's structural advantage over intent-inference tools is
# precisely that scope here is DECLARED, not extracted from prompts by an LLM.
#
# Two legal expansion paths, both recorded (RR-24's spirit — scope is amended
# through artifacts, never redefined silently in the diff):
#   - `scope add-collateral <path> --task T3 --reason "…"` appends to
#     `collateral:` and writes the decisions.md line ITSELF (degradation-log
#     pattern: the record is taken, not requested).
#   - the plan's `Files:` lines are amended, then `scope derive --refresh`
#     re-derives and records the plan@old → plan@new delta in decisions.md.
#
# What derive will NOT do: guess. A task with no `Files:`/`Output:` line
# contributes nothing and is reported as a warning — scope completeness is a
# plan-review finding (SG-8), not something a script invents after the fact.

# Template placeholders and "no files" markers that must not become globs.
_SCOPE_JUNK = ("{", "}", "(none)", "n/a", "none", "tbd", "-", "—")


def normalize_scope_glob(raw: str):
    """Posix separators, repo-relative, no `..`. Returns None for anything that
    is not a usable glob — the caller reports, never guesses."""
    g = raw.strip().strip("`").strip('"').strip("'").rstrip(",").strip()
    if not g or g.lower() in _SCOPE_JUNK or "{" in g or "}" in g:
        return None
    g = g.replace("\\", "/")
    while g.startswith("./"):
        g = g[2:]
    if g.startswith("/"):
        return None        # absolute — silently relativizing /etc/passwd to
                           # etc/passwd would derive a scope nobody declared
    if not g or any(part == ".." for part in g.split("/")):
        return None
    return g.rstrip("/") or None


_TASK_HEAD_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*\*\*Task\s+(\d+)\s*:?\*\*:?\s*(.*?)\s*$",
                           re.M)
_FILES_LINE_RE = re.compile(r"^\s*-\s*\*\*(Files|Output)\s*:?\*\*:?\s*(.*?)\s*$")


def parse_plan_scope(plan_text: str):
    """The plan's per-task `Files:` / `Output:` declarations.

    Returns (entries, undeclared, rejected):
      entries    [(glob, task_id, task_name)] in plan order, deduplicated
      undeclared [(task_id, task_name)] — tasks with no declaration at all
      rejected   [raw] — declared values that could not become globs
    """
    entries, undeclared, rejected, seen = [], [], [], set()
    tasks = list(_TASK_HEAD_RE.finditer(plan_text))
    for i, m in enumerate(tasks):
        tid, tname = int(m.group(1)), m.group(2).strip()
        tname = re.sub(r"\s*\[DOC\]\s*$", "", tname)
        body = plan_text[m.end():tasks[i + 1].start() if i + 1 < len(tasks)
                         else len(plan_text)]
        declared = False
        for line in body.splitlines():
            fm = _FILES_LINE_RE.match(line)
            if not fm:
                continue
            for raw in re.split(r"[,\s]+", fm.group(2)):
                if not raw.strip():
                    continue
                declared = True
                g = normalize_scope_glob(raw)
                if g is None:
                    rejected.append(raw.strip())
                elif g not in seen:
                    seen.add(g)
                    entries.append((g, tid, tname))
        if not declared:
            undeclared.append((tid, tname))
    return entries, undeclared, rejected


def _plan_sha(plan_text: str) -> str:
    """The hash of what scope DERIVES from — the Files:/Output: lines only.

    Not the whole file: checking a task's box, appending ✅ DONE markers, or
    rewording an Action is routine cycle bookkeeping that changes no glob,
    and a whole-file hash would mark the scope stale on every close-out
    (warn-per-edit forever). Only edits to the declaration lines move this
    hash — which is exactly when a re-derive is actually due. The scope
    gate computes the same hash from the same regex."""
    lines = re.findall(r"(?m)^\s*-\s*\*\*(?:Files|Output)\s*:?\*\*:?\s*.*$",
                       plan_text)
    basis = "\n".join(l.strip() for l in lines)
    return hashlib.sha1(basis.encode("utf-8", errors="replace")).hexdigest()[:8]


_SCOPE_KEY_RE = re.compile(r"^scope\s*:")
# The glob, then optionally ANY comment; `# T3 name` carries attribution. An
# entry must never fall out of scope because its note didn't match the
# attribution shape — the gate's reader makes the same promise.
_SCOPE_GLOB_RE = re.compile(
    r"^\s*-\s*(?P<glob>\S+)(?:\s+#\s*(?P<comment>.*))?\s*$")
_SCOPE_TASK_RE = re.compile(r"^T(?P<task>\d+)\s*(?:—|--|-)?\s*(?P<note>.*)$")


def read_scope(text: str):
    """The manifest's `scope:` block, or None when the manifest has no derived
    scope. None and an empty block mean different things: None disarms the
    scope gate entirely (pre-upgrade / never-derived cycles are never
    surprise-blocked), while an empty `globs:` is a real, deliberately tiny
    scope."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        return None
    lines = fm.splitlines()
    start = next((i for i, l in enumerate(lines) if _SCOPE_KEY_RE.match(l)), None)
    if start is None:
        return None
    block = {"derived_from": None, "globs": [], "collateral": []}
    section = None
    for l in lines[start + 1:]:
        if l.strip() and not l.startswith((" ", "\t")):
            break                                  # next top-level key
        s = l.strip()
        m = re.match(r"^derived_from\s*:\s*(\S+)", s)
        if m:
            block["derived_from"] = m.group(1)
            continue
        if re.match(r"^globs\s*:", s):
            section = "globs"
            continue
        if re.match(r"^collateral\s*:", s):
            section = "collateral"
            continue
        gm = _SCOPE_GLOB_RE.match(s)
        if gm and section:
            glob_val = gm.group("glob").strip('"').strip("'")
            tid, note = None, ""
            tm = _SCOPE_TASK_RE.match((gm.group("comment") or "").strip())
            if tm:
                tid = int(tm.group("task"))
                note = (tm.group("note") or "").strip()
            if glob_val:
                block[section].append((glob_val, tid, note))
    return block


def _scope_block_lines(derived_from: str, globs, collateral) -> str:
    out = ["scope:", f"  derived_from: {derived_from}", "  globs:"]
    if not globs:
        out[-1] = "  globs: []"
    for g, tid, note in globs:
        tag = f"  # T{tid}" + (f" {note}" if note else "") if tid else ""
        out.append(f"    - {g}{tag}")
    if collateral:
        out.append("  collateral:")
        for g, tid, note in collateral:
            tag = f"  # T{tid}" + (f" — {note}" if note else "") if tid else ""
            out.append(f"    - {g}{tag}")
    else:
        out.append("  collateral: []")
    return "\n".join(out)


def _write_frontmatter_block(text: str, key_re, block: str) -> str:
    """Replace (or append) one top-level frontmatter block. Same rule as
    write_gate_state: only the frontmatter — body prose that quotes the block
    is the agent's narration and must not be rewritten."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        raise Problem("manifest has no frontmatter")
    lines = fm.splitlines()
    start = next((i for i, l in enumerate(lines) if key_re.match(l)), None)
    if start is None:
        new_fm = fm.rstrip("\n") + "\n" + block
    else:
        end = start + 1
        while end < len(lines) and (not lines[end].strip()
                                    or lines[end].startswith((" ", "\t"))):
            end += 1
        new_fm = "\n".join(lines[:start] + block.splitlines() + lines[end:])
    return text.replace(fm, new_fm, 1)


def write_scope_block(text: str, block: str) -> str:
    return _write_frontmatter_block(text, _SCOPE_KEY_RE, block)


def _prepend_decision(decisions_path: pathlib.Path, entry: str) -> None:
    """One decisions.md line, written by CODE (the degradation-log pattern —
    the record is taken, not requested)."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    block = f"### {today} — {entry}\n\n"
    old = (decisions_path.read_text(encoding="utf-8", errors="replace")
           if decisions_path.is_file() else "")
    m = re.match(r"(\A#[^\n]*\n+)", old)
    head, rest = (m.group(1), old[m.end():]) if m else ("", old)
    decisions_path.write_text(head + block + rest, encoding="utf-8")


def scope_derive(manifest_path: pathlib.Path, refresh: bool = False) -> int:
    plan = manifest_path.parent / "plan.md"
    if not plan.is_file():
        raise Problem(f"no plan to derive from: {plan}")
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    plan_text = plan.read_text(encoding="utf-8", errors="replace")

    existing = read_scope(text)
    if existing and not refresh:
        raise Problem(
            "this cycle already has a derived scope "
            f"({existing['derived_from']}). Re-derive deliberately: "
            "scope derive --refresh (the expansion is recorded), or add a "
            "single path with scope add-collateral.")

    entries, undeclared, rejected = parse_plan_scope(plan_text)
    new_from = f"plan@{_plan_sha(plan_text)}"
    # Collateral was legally recorded against THIS cycle; a re-derive of the
    # plan's globs must not silently discard it.
    collateral = existing["collateral"] if existing else []
    globs = [(g, tid, tname) for g, tid, tname in entries]
    new_text = write_scope_block(text, _scope_block_lines(new_from, globs, collateral))
    manifest_path.write_text(stamp_updated(new_text), encoding="utf-8")

    if refresh and existing and existing["derived_from"] not in (None, new_from):
        # The record says WHAT changed, not just how many: graders (and
        # humans) reading decisions.md must be able to see that a specific
        # path became sanctioned — a count sanctions nothing.
        old_globs = {g for g, _, _ in existing["globs"]}
        added = [g for g, _, _ in globs if g not in old_globs]
        removed = sorted(old_globs - {g for g, _, _ in globs})
        delta = ""
        if added:
            delta += " + " + ", ".join(added[:8])
            if len(added) > 8:
                delta += f" (+{len(added) - 8} more)"
        if removed:
            delta += f" − {len(removed)} removed"
        _prepend_decision(
            manifest_path.parent / "decisions.md",
            f"scope expanded: {existing['derived_from']} → {new_from} "
            f"(cycle {manifest_path.parent.name}){delta}")

    print(f"scope: {new_from} — {len(globs)} glob(s), "
          f"{len(collateral)} collateral entr(y/ies)")
    for tid, tname in undeclared:
        print(f"warning: Task {tid} \"{tname}\" declares no Files:/Output: — "
              f"it contributes NOTHING to scope (plan-review finding, SG-8); "
              f"the gate does not guess scope for undeclared tasks")
    for raw in rejected:
        print(f"warning: unusable path {raw!r} skipped (placeholder, or escapes "
              f"the repo)")
    return 0


def scope_add_collateral(manifest_path: pathlib.Path, path_or_glob: str,
                         task: str, reason: str) -> int:
    if not reason or not reason.strip():
        raise Problem("--reason is required: collateral without a reason is "
                      "scope creep with paperwork")
    g = normalize_scope_glob(path_or_glob)
    if g is None:
        raise Problem(f"not a usable repo-relative path or glob: {path_or_glob!r}")
    # A collateral glob with no literal prefix (`**`, `*`, `?x`, `[ab]/…`) is
    # not "one extra path this task needs" — it is the whole tree, and an
    # agent the gate just blocked must not be able to self-grant it. A
    # scope-wide change goes through the plan (the user), not through
    # collateral. Probed live: before this guard, `add-collateral '**'`
    # opened the gate for everything.
    if re.match(r"[*?\[]", g):
        raise Problem(
            f"{g!r} has no literal path prefix — collateral names a specific "
            "path or a glob under one (e.g. src/billing/**). A scope-wide "
            "expansion is a plan amendment: ask the user, then "
            "`scope derive --refresh`.")
    tid_m = re.fullmatch(r"[Tt]?(\d+)", task.strip())
    if not tid_m:
        raise Problem(f"--task must be a plan task id like T3 (got {task!r})")
    tid = int(tid_m.group(1))

    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    scope = read_scope(text)
    if scope is None:
        raise Problem("this cycle has no derived scope yet — run "
                      f"`manifest.py scope derive {manifest_path}` first")
    if any(g == c for c, _, _ in scope["collateral"]) or \
       any(g == s for s, _, _ in scope["globs"]):
        print(f"scope: {g} is already in scope — nothing to add")
        return 0

    reason_line = " ".join(reason.split())
    collateral = scope["collateral"] + [(g, tid, reason_line)]
    new_text = write_scope_block(
        text, _scope_block_lines(scope["derived_from"] or "plan@unknown",
                                 scope["globs"], collateral))
    manifest_path.write_text(stamp_updated(new_text), encoding="utf-8")
    _prepend_decision(
        manifest_path.parent / "decisions.md",
        f"scope collateral: {g} (task T{tid}) — {reason_line}")
    print(f"scope: collateral added — {g} (T{tid}); decisions.md updated")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# task graph — the plan's structure becomes machine state (A8).
#
# The parallel scheduler (A7) needs to know, per task, three things the plan
# already declares: which files it may touch (`Files:`/`Output:`), what it
# waits on (`Depends on:`), and whether the planner marked it parallel-safe
# (`[P]`). Until now that structure was prose — and prose is read by the same
# model that is deciding what to dispatch next. `graph derive` parses it ONCE,
# at plan approval, alongside `scope derive` (same Files parser), into a
# `task_graph:` block in the manifest frontmatter. Everything downstream of
# approval — the scheduler, the ledger's lane records, the resume brief, the
# E-PAR graders — consumes the block, never the plan prose.
#
# FAIL-CLOSED, unlike scope. Scope-derive warns on an undeclared task because
# the scope gate degrades safely (an undeclared file simply is not sanctioned).
# A wrong GRAPH does not degrade safely: a missed dependency edge dispatches
# two coupled tasks into concurrent lanes. So any defect — unknown/ambiguous
# `Depends on:` reference, a cycle, a missing `Files:`, a malformed `[P]` —
# exits nonzero, surfaces each defect as a plan-review finding, and writes
# NOTHING. An underivable plan cannot enter parallel mode; the sequential
# build is unaffected (the degradation is announced by the workflow).
#
# The E9 lesson is load-bearing here: never derive wrong silently. The parser
# reads a fence- and comment-stripped view of the plan, so example snippets
# quoting task syntax can never become phantom graph nodes — a naive regex
# over raw markdown was exactly how the ledger schism happened.

_DEPENDS_LINE_RE = re.compile(
    r"^\s*-\s*\*\*Depends\s+on\s*:?\*\*:?\s*(.*?)\s*$", re.I)
_STATUS_DECOR_RE = re.compile(r"\s*(?:✅|🔄|🚫).*$")
_MARKER_TAIL_RE = re.compile(r"\s*\[(?:P|DOC)\]\s*$")
_PSEUDO_P_RE = re.compile(r"\[\s*p\s*\]", re.I)


def _plan_derivation_view(plan_text: str) -> str:
    """The plan as the graph parser may read it: fenced code blocks, HTML
    comments, AND 4-space-indented code blocks removed. An UNCLOSED fence
    or comment strips to end-of-file — fail-closed beats parsing content
    the author marked as not-the-plan.

    The indented-block rule is blunt on purpose: markdown's other code
    form let an example task derive as a phantom node (review finding 5),
    and the template's real declaration lines are 2-space bullets. A plan
    that nonstandardly indents a Files:/Depends line 4+ spaces loses it
    from the view and refuses loudly on the missing declaration — a loud
    refusal, never a phantom node."""
    out, fence = [], None
    for line in plan_text.splitlines():
        s = line.strip()
        if fence is None and (s.startswith("```") or s.startswith("~~~")):
            fence = s[:3]
            continue
        if fence is not None:
            if s.startswith(fence):
                fence = None
            continue
        if (line[:4] == "    " or line[:1] == "\t") and s:
            continue                       # indented code block content
                                           # (markdown: 4 spaces OR a tab)
        out.append(line)
    return re.sub(r"(?s)<!--.*?(?:-->|\Z)", "", "\n".join(out))


def _split_title_markers(raw_title: str):
    """(title, parallel, doc, malformed). Trailing `[P]` / `[DOC]` markers are
    stripped in any order; a [P]-shaped token that survives — wrong case,
    inner spaces, or not in the marker position — is MALFORMED, not ignored:
    the planner plainly meant something, and guessing which thing is exactly
    what a scheduler input must not do."""
    t = _STATUS_DECOR_RE.sub("", raw_title).strip()
    parallel = doc = False
    while True:
        m = _MARKER_TAIL_RE.search(t)
        if not m:
            break
        if m.group(0).strip() == "[P]":
            parallel = True
        else:
            doc = True
        t = t[:m.start()].rstrip()
    return t, parallel, doc, bool(_PSEUDO_P_RE.search(t))


def _parse_depends_value(value: str):
    """`none` → ([], True); `T1, Task 3` → ([1, 3], True); anything else →
    ([], False). The grammar is the template's: `none | T<n>[, T<n>…]`
    (`Task <n>` accepted). No fuzzy matching — an ambiguous reference is a
    finding, not a guess."""
    v = value.strip().rstrip(".")
    if re.fullmatch(r"none", v, re.I):
        return [], True
    ids = []
    for tok in v.split(","):
        m = re.fullmatch(r"(?:[Tt]ask\s+|[Tt])(\d+)", tok.strip())
        if not m:
            return [], False
        ids.append(int(m.group(1)))
    return ids, bool(ids)


def parse_plan_graph(plan_text: str):
    """→ (tasks, findings). tasks: [{id, title, files, depends, parallel}]
    in plan order. findings: plan-review finding strings. ANY finding means
    the caller must not write a graph — fail-closed, see the section header."""
    view = _plan_derivation_view(plan_text)
    findings = []
    # NEAR-MISS heads refuse, they never vanish (round-three T2, widened
    # by round-four F3: `**Task 1 [P]:**`, `- []`, `* [ ]`, and lowercase
    # `task` heads each matched NO parser, so the task silently
    # disappeared from graph, scope, AND ledger with zero findings —
    # three parsers agreeing on the wrong answer is not a cross-check).
    # The near-miss shape is any bulleted, checkbox-ish, bold line whose
    # bold text says "task" followed soon by a DIGIT — a NUMBERED task
    # was plainly meant. Prose bullets like `**Task force sign-off**`
    # carry no number, are not tasks, and pass untouched (round-four F4).
    _NEAR_MISS = re.compile(
        r"^\s*[-*+]\s*\[[ xX]?\]\s*\*\*\s*[Tt]ask\s*\[?\s*\d")
    for line in view.splitlines():
        if _NEAR_MISS.match(line) and not _TASK_HEAD_RE.match(line):
            findings.append(
                "unparseable task head %r — the grammar is `- [ ] **Task "
                "N:** title` with [P]/[DOC] AFTER the title, never inside "
                "the head; this bullet would otherwise VANISH from the "
                "graph, the scope, and the ledger" % line.strip()[:80])
    heads = list(_TASK_HEAD_RE.finditer(view))
    if not heads:
        return [], findings + [
            "plan has no parseable tasks (the template's "
            "`- [ ] **Task N:** title` bullets) — nothing to derive "
            "a graph from"]
    tasks, seen = [], set()
    for i, m in enumerate(heads):
        tid = int(m.group(1))
        title, parallel, doc, malformed = _split_title_markers(
            m.group(2).strip())
        if tid in seen:
            findings.append(
                "Task %d appears more than once — duplicate ids make every "
                "`Depends on:` reference to T%d ambiguous" % (tid, tid))
        seen.add(tid)
        if malformed:
            findings.append(
                "Task %d has a malformed [P] marker in %r — the marker is "
                "exactly `[P]`, placed after the task name" % (tid, title))
        body = view[m.end():heads[i + 1].start() if i + 1 < len(heads)
                    else len(view)]
        files, rejected, declared = [], [], False
        dep_lines = []
        for line in body.splitlines():
            fl = _FILES_LINE_RE.match(line)
            if fl:
                declared = True
                for raw in re.split(r"[,\s]+", fl.group(2)):
                    if not raw.strip():
                        continue
                    g = normalize_scope_glob(raw)
                    if g is None:
                        rejected.append(raw.strip())
                    elif g not in files:
                        files.append(g)
                continue
            dl = _DEPENDS_LINE_RE.match(line)
            if dl:
                dep_lines.append(dl.group(1))
        if not files:
            if rejected:
                findings.append(
                    "Task %d declares only unusable Files:/Output: entries "
                    "(%s) — placeholders and paths outside the repo cannot "
                    "become a lane's files set" % (tid, ", ".join(
                        repr(r) for r in rejected[:4])))
            else:
                findings.append(
                    "Task %d declares no %s — a lane cannot be scheduled "
                    "without a files set" % (
                        tid, "Output:" if doc else "Files:"))
        if not dep_lines:
            findings.append(
                "Task %d declares no `Depends on:` — the graph does not "
                "guess ordering; write `Depends on: none` if it truly has "
                "no prerequisites" % tid)
            depends = []
        elif len(dep_lines) > 1:
            findings.append(
                "Task %d declares %d `Depends on:` lines — one per task"
                % (tid, len(dep_lines)))
            depends = []
        else:
            depends, ok = _parse_depends_value(dep_lines[0])
            if not ok:
                findings.append(
                    "Task %d's `Depends on: %s` is ambiguous — the grammar "
                    "is `none | T<n>[, T<n>…]`" % (tid, dep_lines[0].strip()))
        tasks.append({"id": tid, "title": title, "files": files,
                      "depends": depends, "parallel": parallel})
    ids = {t["id"] for t in tasks}
    for t in tasks:
        unknown = [d for d in t["depends"] if d not in ids]
        for d in unknown:
            findings.append(
                "Task %d depends on T%d, which does not exist in this plan"
                % (t["id"], d))
        t["depends"] = [d for d in t["depends"] if d in ids]
    cycle = _find_cycle(tasks)
    if cycle:
        findings.append("dependency cycle: %s — a cycle can never be "
                        "scheduled" % " → ".join("T%d" % c for c in cycle))
    return tasks, findings


def _find_cycle(tasks):
    """One dependency cycle as [id, …, id] (first repeated), or None.
    Iterative DFS — a plan is small, but recursion limits are not a failure
    mode a derivation tool gets to have."""
    edges = {t["id"]: list(t["depends"]) for t in tasks}
    state = {}                       # id → 1 in-stack, 2 done
    for root in edges:
        if state.get(root):
            continue
        stack = [(root, iter(edges[root]))]
        state[root] = 1
        path = [root]
        while stack:
            node, it = stack[-1]
            for nxt in it:
                if state.get(nxt) == 1:
                    return path[path.index(nxt):] + [nxt]
                if not state.get(nxt):
                    state[nxt] = 1
                    path.append(nxt)
                    stack.append((nxt, iter(edges.get(nxt, []))))
                    break
            else:
                state[node] = 2
                path.pop()
                stack.pop()
    return None


def _graph_sha(plan_text: str) -> str:
    """The hash of what the GRAPH derives from: task-head lines (checkbox-
    state- and status-marker-independent — same reasoning as _plan_sha: a
    close-out that ticks a box must not mark the graph stale), plus the
    Files:/Output: and Depends lines. Renumbering a task, adding a [P], or
    editing an edge moves this hash — which is exactly when a re-derive is
    due. Scope's hash deliberately covers only the Files/Output lines, so
    the two pins move independently."""
    basis = []
    for line in _plan_derivation_view(plan_text).splitlines():
        hm = _TASK_HEAD_RE.match(line)
        if hm:
            basis.append("T%s:%s" % (
                hm.group(1), _STATUS_DECOR_RE.sub("", hm.group(2)).strip()))
            continue
        if _FILES_LINE_RE.match(line) or _DEPENDS_LINE_RE.match(line):
            basis.append(line.strip())
    return hashlib.sha1(
        "\n".join(basis).encode("utf-8", errors="replace")).hexdigest()[:8]


_TASK_GRAPH_KEY_RE = re.compile(r"^task_graph\s*:")
# `files` is captured non-greedily up to the `], depends:` anchor, NOT with
# [^\]]* — a legal character-class glob (`src/test_[0-9].py`) carries a `]`,
# and the bracket-hungry version silently dropped the whole task on read
# (independent review, finding 2: writer and reader disagreeing is the
# two-parsers hazard again). Entries can never contain a comma — the plan
# parser splits declarations on commas before normalizing — so the
# split(",") below stays safe.
_GRAPH_TASK_RE = re.compile(
    r'^-\s*\{id:\s*T(?P<id>\d+),\s*title:\s*"(?P<title>[^"]*)",\s*'
    r'files:\s*\[(?P<files>.*?)\],\s*depends:\s*\[(?P<dep>[^\]]*)\],\s*'
    r'parallel:\s*(?P<par>true|false)\}\s*$')


def read_task_graph(text: str):
    """The manifest's `task_graph:` block, or None when never derived. The
    reader parses exactly what the writer emits — downstream consumers (the
    A7 scheduler, graders) call this, never the plan."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        return None
    lines = fm.splitlines()
    start = next((i for i, l in enumerate(lines)
                  if _TASK_GRAPH_KEY_RE.match(l)), None)
    if start is None:
        return None
    block = {"derived_from": None, "tasks": []}
    for l in lines[start + 1:]:
        if l.strip() and not l.startswith((" ", "\t")):
            break                                  # next top-level key
        s = l.strip()
        m = re.match(r"^derived_from\s*:\s*(\S+)", s)
        if m:
            block["derived_from"] = m.group(1)
            continue
        gm = _GRAPH_TASK_RE.match(s)
        if gm:
            block["tasks"].append({
                "id": int(gm.group("id")),
                "title": gm.group("title"),
                "files": [f.strip() for f in gm.group("files").split(",")
                          if f.strip()],
                "depends": [int(d.strip().lstrip("Tt"))
                            for d in gm.group("dep").split(",") if d.strip()],
                "parallel": gm.group("par") == "true",
            })
    return block


def _task_graph_block_lines(derived_from: str, tasks) -> str:
    out = ["task_graph:", f"  derived_from: {derived_from}", "  tasks:"]
    if not tasks:
        out[-1] = "  tasks: []"
    for t in tasks:
        out.append(
            '    - {id: T%d, title: "%s", files: [%s], depends: [%s], '
            'parallel: %s}' % (
                t["id"], t["title"].replace('"', "'"),
                ", ".join(t["files"]),
                ", ".join("T%d" % d for d in t["depends"]),
                "true" if t["parallel"] else "false"))
    return "\n".join(out)


def write_task_graph_block(text: str, block: str) -> str:
    return _write_frontmatter_block(text, _TASK_GRAPH_KEY_RE, block)


def graph_derive(manifest_path: pathlib.Path, refresh: bool = False) -> int:
    plan = manifest_path.parent / "plan.md"
    if not plan.is_file():
        raise Problem(f"no plan to derive from: {plan}")
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    plan_text = plan.read_text(encoding="utf-8", errors="replace")

    existing = read_task_graph(text)
    if existing and not refresh:
        raise Problem(
            "this cycle already has a derived task graph "
            f"({existing['derived_from']}). Re-derive deliberately: "
            "graph derive --refresh (the delta is recorded in decisions.md).")

    tasks, findings = parse_plan_graph(plan_text)

    # graph↔scope consistency. Both derive from the same declaration lines
    # with the same parser, so a divergence means the SCOPE is out of date
    # (plan amended after `scope derive`) — and lanes dispatched under a
    # stale scope gate would be policed against the wrong contract.
    scope = read_scope(text)
    if scope is None:
        findings.append(
            "no derived scope: block — run `manifest.py scope derive` first "
            "(plan approval derives scope, then the graph)")
    else:
        scope_pin = f"plan@{_plan_sha(plan_text)}"
        if scope["derived_from"] not in (None, scope_pin):
            findings.append(
                f"scope is stale ({scope['derived_from']}; the plan's "
                f"declarations are now {scope_pin}) — run `scope derive "
                "--refresh`, then re-derive the graph")
        else:
            sanctioned = ({g for g, _, _ in scope["globs"]}
                          | {g for g, _, _ in scope["collateral"]})
            for t in tasks:
                outside = [f for f in t["files"] if f not in sanctioned]
                if outside:
                    findings.append(
                        "Task %d's files (%s) are not in the derived scope — "
                        "graph and scope must agree before lanes dispatch"
                        % (t["id"], ", ".join(outside)))

    if findings:
        for f in findings:
            print(f"plan-review finding: {f}")
        print(f"task graph NOT derived — {len(findings)} finding(s). An "
              "underivable plan cannot enter parallel mode; the sequential "
              "build is unaffected. Fix the plan, then re-run graph derive.")
        return 1

    new_from = f"plan@{_graph_sha(plan_text)}"
    new_text = write_task_graph_block(
        text, _task_graph_block_lines(new_from, tasks))
    manifest_path.write_text(stamp_updated(new_text), encoding="utf-8")

    if refresh and existing and existing["derived_from"] not in (None, new_from):
        old_ids = {t["id"] for t in existing["tasks"]}
        new_ids = {t["id"] for t in tasks}
        old_edges = {(t["id"], d) for t in existing["tasks"]
                     for d in t["depends"]}
        new_edges = {(t["id"], d) for t in tasks for d in t["depends"]}
        old_par = {t["id"] for t in existing["tasks"] if t["parallel"]}
        new_par = {t["id"] for t in tasks if t["parallel"]}
        delta = ""
        added = sorted(new_ids - old_ids)
        removed = sorted(old_ids - new_ids)
        if added:
            delta += " +" + ",".join("T%d" % i for i in added)
        if removed:
            delta += " −" + ",".join("T%d" % i for i in removed)
        if old_edges != new_edges:
            delta += f" edges {len(old_edges)}→{len(new_edges)}"
        if old_par != new_par:
            delta += " [P] set changed"
        _prepend_decision(
            manifest_path.parent / "decisions.md",
            f"task graph re-derived: {existing['derived_from']} → {new_from} "
            f"(cycle {manifest_path.parent.name}){delta}")

    n_par = sum(1 for t in tasks if t["parallel"])
    n_edges = sum(len(t["depends"]) for t in tasks)
    print(f"task_graph: {new_from} — {len(tasks)} task(s), {n_par} "
          f"parallel-eligible, {n_edges} dependency edge(s)")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# lanes — parallel-lane state as machine state (A7; states designed for A9).
#
# One record per dispatched lane, in the manifest frontmatter, written ONLY
# by lanes.py (single-writer: lanes report, the orchestrator records). The
# state vocabulary is fixed here so the A9 hardening does not churn the
# schema:
#
#   open           dispatched, in flight — its files are claimed
#   parked         blocked mid-flight; dependents freeze, siblings continue;
#                  claim held
#   errored        infra/rate-limit death (1.3.3 evidence rules: tokens, not
#                  turns) — gets ONE staggered retry, never graded, never
#                  consumes a quality-locked attempt; claim held
#   merged         landed on the integration branch — the ONLY state that
#                  satisfies a `depends` edge
#   failed         quality failure — a graded outcome; claim released
#   budget-stopped the burst budget ran out before/while this ran; explicit
#                  report, never graded as failure; claim released
#
# `burst_base` pins the SHA the burst's lanes forked from (A9): context
# packets for dependent tasks are built post-merge from merged HEAD, and the
# pin is what makes "post-merge" checkable rather than aspirational.

LANE_STATES = ("open", "parked", "errored", "merged", "failed",
               "budget-stopped")
# States whose lane still holds its files claim against new dispatches.
LANE_ACTIVE_STATES = ("open", "parked", "errored")

_LANES_KEY_RE = re.compile(r"^lanes\s*:")
_LANE_REC_RE = re.compile(
    r'^-\s*\{task:\s*T(?P<task>\d+),\s*branch:\s*"(?P<branch>[^"]*)",\s*'
    r'worktree:\s*"(?P<worktree>[^"]*)",\s*state:\s*(?P<state>[a-z-]+),\s*'
    r'model:\s*"(?P<model>[^"]*)"(?:,\s*retries:\s*(?P<retries>\d+))?'
    r'(?:,\s*note:\s*"(?P<note>[^"]*)")?\}\s*$')


def read_lanes(text: str):
    """The manifest's `lanes:` block, or None when the cycle never went
    parallel. Same None-vs-empty distinction as scope."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        return None
    lines = fm.splitlines()
    start = next((i for i, l in enumerate(lines) if _LANES_KEY_RE.match(l)),
                 None)
    if start is None:
        return None
    block = {"burst_base": "", "records": []}
    for l in lines[start + 1:]:
        if l.strip() and not l.startswith((" ", "\t")):
            break
        s = l.strip()
        m = re.match(r"^burst_base\s*:\s*\"?([A-Za-z0-9._/-]*)\"?", s)
        if m:
            block["burst_base"] = m.group(1)
            continue
        rm = _LANE_REC_RE.match(s)
        if rm:
            block["records"].append({
                "task": int(rm.group("task")),
                "branch": rm.group("branch"),
                "worktree": rm.group("worktree"),
                "state": rm.group("state"),
                "model": rm.group("model"),
                "retries": int(rm.group("retries") or 0),
                "note": rm.group("note") or "",
            })
    return block


def _lanes_block_lines(burst_base: str, records) -> str:
    out = ["lanes:", '  burst_base: "%s"' % (burst_base or ""), "  records:"]
    if not records:
        out[-1] = "  records: []"
    for r in records:
        retries = (", retries: %d" % r["retries"]
                   if r.get("retries") else "")
        note = (', note: "%s"' % r["note"].replace('"', "'")
                if r.get("note") else "")
        out.append(
            '    - {task: T%d, branch: "%s", worktree: "%s", state: %s, '
            'model: "%s"%s%s}' % (r["task"], r["branch"], r["worktree"],
                                  r["state"], r["model"], retries, note))
    return "\n".join(out)


def write_lanes_block(text: str, block: str) -> str:
    return _write_frontmatter_block(text, _LANES_KEY_RE, block)


def _select_active_manifest(root: pathlib.Path) -> pathlib.Path:
    cands, _ = resume_candidates(root)
    if len(cands) == 1:
        return cands[0]
    if not cands:
        raise Problem("no active cycle — pass --manifest explicitly")
    raise Problem("multiple active cycles (%s) — pass --manifest explicitly"
                  % ", ".join(c.parent.name for c in cands))


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

    co = sub.add_parser(
        "close-out",
        help="apply the close-out bookkeeping in ONE pass (manifest prose, "
             "decisions, plan checkboxes) instead of incremental edits")
    co.add_argument("manifest", type=pathlib.Path)
    co.add_argument("--summary", help="replaces the ## Context summary section")
    co.add_argument("--next-step", help="rewrites the **Next step:** line")
    co.add_argument("--open-questions",
                    help="replaces ## Open questions ('' means none)")
    co.add_argument("--decision", action="append", default=[],
                    help="prepend an entry to the cycle's decisions.md (repeatable)")
    co.add_argument("--complete-task", action="append", type=int, default=[],
                    metavar="N", help="check Task N's box in plan.md (repeatable)")
    co.add_argument("--phase", help="set frontmatter phase")
    co.add_argument("--status", help="set frontmatter status")
    co.add_argument("--blocked-on",
                    help="name the blocker (required by `check` when status is "
                         "blocked): the question, the options, whose call")

    sc = sub.add_parser(
        "scope",
        help="the plan's declared Files:/Output: as machine state (SG-1/SG-2)")
    scsub = sc.add_subparsers(dest="scope_cmd", required=True)

    sd = scsub.add_parser("derive",
                          help="parse the approved plan's per-task Files:/Output: "
                               "into the manifest's scope: block")
    sd.add_argument("manifest", type=pathlib.Path)
    sd.add_argument("--refresh", action="store_true",
                    help="re-derive after a plan amendment; the plan@old → "
                         "plan@new delta is recorded in decisions.md")

    sa = scsub.add_parser("add-collateral",
                          help="record one extra path this work may touch — "
                               "with the reason, in decisions.md, by this tool")
    sa.add_argument("path", help="repo-relative path or glob")
    sa.add_argument("--task", required=True, help="the plan task it serves (T3)")
    sa.add_argument("--reason", required=True,
                    help="why this path belongs to that task")
    sa.add_argument("--manifest", type=pathlib.Path,
                    help="the cycle (default: the single active cycle)")
    sa.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())

    g = sub.add_parser(
        "graph",
        help="the plan's task structure (Files/Depends/[P]) as machine state "
             "— the parallel scheduler's ONLY input (A8)")
    gsub = g.add_subparsers(dest="graph_cmd", required=True)
    gd = gsub.add_parser("derive",
                         help="parse the approved plan's tasks into the "
                              "manifest's task_graph: block; fail-closed — "
                              "findings exit nonzero and write nothing")
    gd.add_argument("manifest", type=pathlib.Path)
    gd.add_argument("--refresh", action="store_true",
                    help="re-derive after a plan amendment; the plan@old → "
                         "plan@new delta is recorded in decisions.md")

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

        if args.cmd == "graph":
            return graph_derive(args.manifest, refresh=args.refresh)

        if args.cmd == "scope":
            if args.scope_cmd == "derive":
                return scope_derive(args.manifest, refresh=args.refresh)
            manifest = args.manifest or _select_active_manifest(
                args.repo_root.resolve())
            return scope_add_collateral(manifest, args.path,
                                        task=args.task, reason=args.reason)

        if args.cmd == "close-out":
            return close_out(args.manifest, summary=args.summary,
                             next_step=args.next_step,
                             decisions=args.decision,
                             complete_tasks=args.complete_task,
                             open_questions=args.open_questions,
                             status=args.status, phase=args.phase,
                             blocked_on=args.blocked_on)

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
