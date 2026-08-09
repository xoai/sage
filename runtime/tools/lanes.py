#!/usr/bin/env python3
"""lanes.py — the parallel-lane scheduler and the lanes' single writer (A7).

WHY A SCRIPT AND NOT A PARAGRAPH

Parallel dispatch is the highest-stakes scheduling decision in the build
loop: two coupled tasks in concurrent lanes produce a merge conflict at
best and a silently wrong integration at worst. Every prior time this
codebase let the model hold a rule in prose — the degradation record, the
task ledger, gate_state, the close-out — the rule held in roughly one run
out of three. The dispatch rule gets the same treatment as those did
after measurement: it is code, and the model asks the code.

THE RULES (from the pack, mechanical here):

  - A task is parallel-eligible iff `parallel: true` in the derived
    task_graph:, ALL its `depends` are MERGED (not merely done-looking),
    and its files set is disjoint from every in-flight lane's claim.
  - Declared overlap is a SERIALIZATION signal, never a worktree signal:
    overlapping tasks queue, they do not get cleverer isolation.
  - A task without [P] runs ALONE: it dispatches only when no lane is in
    flight, and nothing else dispatches beside it.
  - A parked/errored lane HOLDS its files claim; its dependents FREEZE;
    its siblings continue.
  - The orchestrator merges lanes in DEPENDENCY ORDER; a conflicting
    merge is aborted and reported — never resolved by model judgment.

SINGLE-WRITER: only this tool (invoked by the orchestrator via Bash)
writes the lanes: block and the ledger's lane fields. Lanes REPORT;
the orchestrator RECORDS. Hand-edits of the manifest are redirected by
the bookkeeping-gate — that is the invariant's enforcement, not this
docstring.

Usage:
    lanes.py schedule <manifest.md> [--cap N] [--json]
                      [--couplings FILE] [--budget-exhausted]
    lanes.py open     <manifest.md> --task N --branch B --worktree DIR
                      [--model M] [--base SHA] [--cap N]
                      [--couplings FILE] [--repo-root PATH]
    lanes.py mark     <manifest.md> --task N --state open|parked|errored|
                      failed|budget-stopped [--note "..."]
    lanes.py retry    <manifest.md> --task N     # errored only, once, ungraded
    lanes.py merge    <manifest.md> --task N [--repo-root PATH]

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import fnmatch
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import manifest as MAN  # noqa: E402
from sage_flags import HARD_LANE_CAP  # noqa: E402  — ONE hard cap, one home


class Problem(Exception):
    pass


DEFAULT_CAP = 2

# `mark` may set these; `merged` is deliberately NOT here — only a real
# `merge` (the git operation succeeding) writes merged, because merged is
# the ONLY state that satisfies a depends edge and it must never be
# claimable by prose.
MARKABLE_STATES = ("open", "parked", "errored", "failed", "budget-stopped")

# What a lane state means for the ledger's task status. None = the
# orchestrator's verdict processing owns it, this tool does not touch it.
_LEDGER_STATUS_FOR = {
    "open": "in-progress",
    "parked": "blocked",
    "failed": "blocked",          # needs a fix-loop or escalation decision
    "errored": "in-progress",     # A9: one staggered retry is coming
    "budget-stopped": "pending",  # next burst re-dispatches it
}


# ── claims ───────────────────────────────────────────────────────────────────

def _entries_overlap(a: str, b: str) -> bool:
    """Do two DECLARED file entries (paths or globs) overlap? Conservative:
    unclear means yes — a false overlap serializes (slower, correct); a
    missed overlap dispatches a conflict (wrong)."""
    if a == b:
        return True
    for x, y in ((a, b), (b, a)):
        if x.endswith("/**") and (y == x[:-3] or y.startswith(x[:-2])):
            return True
        # A bare directory entry (`src`, `src/auth`) claims everything
        # under it — `Files: src/` normalizes to `src`, and treating it
        # as one literal path dispatched two coupled lanes concurrently
        # (independent review, finding 1: the exact missed-overlap this
        # function's bias exists to prevent).
        if y.startswith(x + "/"):
            return True
        if fnmatch.fnmatch(y, x):
            return True
    return False


def claims_overlap(files_a, files_b):
    """The overlapping entries between two files sets, [] when disjoint."""
    hits = []
    for a in files_a:
        for b in files_b:
            if _entries_overlap(a, b):
                hits.append(a if a == b else "%s ∩ %s" % (a, b))
    return hits


# ── ledger access (read statuses; write one entry's lane fields) ─────────────

def read_ledger_statuses(text: str):
    """{task_id: status} from the manifest's tasks: ledger block."""
    fm, _ = MAN.split_frontmatter(text)
    if fm is None:
        return {}
    statuses, current = {}, None
    in_tasks = False
    for line in fm.splitlines():
        if re.match(r"^tasks\s*:", line):
            in_tasks = True
            continue
        if in_tasks and line.strip() and not line.startswith((" ", "\t")):
            break
        if not in_tasks:
            continue
        m = re.match(r"^\s*-\s*id\s*:\s*(\d+)", line)
        if m:
            current = int(m.group(1))
            statuses[current] = "pending"
            continue
        m = re.match(r"^\s*status\s*:\s*\"?([A-Za-z-]+)", line)
        if m and current is not None:
            statuses[current] = m.group(1)
    return statuses


def _update_ledger_entry(text: str, task_id: int, **fields) -> str:
    """Rewrite the given task's ledger fields in place. `attempts='+1'`
    increments. Raises Problem when the entry or a field is absent — a
    silent no-op here would let a dispatch go unrecorded."""
    fm, _ = MAN.split_frontmatter(text)
    if fm is None:
        raise Problem("manifest has no frontmatter")
    lines = fm.splitlines()
    start = next((i for i, l in enumerate(lines)
                  if re.match(r"^\s*-\s*id\s*:\s*%d\s*$" % task_id, l)), None)
    if start is None:
        raise Problem("no ledger entry for task %d — run ledger.py init "
                      "first (the ledger mirrors the plan)" % task_id)
    end = start + 1
    while end < len(lines) and not re.match(r"^\s*-\s*id\s*:", lines[end]) \
            and (not lines[end].strip()
                 or lines[end].startswith((" ", "\t"))):
        end += 1
    block = lines[start:end]
    for name, value in fields.items():
        pat = re.compile(r"^(\s*)%s\s*:.*$" % re.escape(name))
        for i, l in enumerate(block):
            m = pat.match(l)
            if not m:
                continue
            if name == "attempts" and value == "+1":
                cur = re.search(r"(\d+)", l)
                value = str((int(cur.group(1)) if cur else 0) + 1)
            rendered = ('%s%s: "%s"' % (m.group(1), name, value)
                        if name in ("model", "lane_branch")
                        else "%s%s: %s" % (m.group(1), name, value))
            block[i] = rendered
            break
        else:
            raise Problem("ledger entry for task %d has no %s: field "
                          "(pre-A7 ledger? re-scaffold or add the field)"
                          % (task_id, name))
    new_fm = "\n".join(lines[:start] + block + lines[end:])
    return text.replace(fm, new_fm, 1)


# ── the scheduler decision ───────────────────────────────────────────────────

def schedule(graph, statuses, lanes, cap, couplings=None,
             budget_exhausted=False):
    """The dispatch decision, pure. Returns
    {dispatch, serialized, frozen, waiting, capped, budget_held,
    exclusive} where serialized/frozen carry (task_id, reason) pairs.

    Inputs: graph = manifest.read_task_graph(); statuses =
    read_ledger_statuses(); lanes = manifest.read_lanes() or None;
    cap = the lane cap, clamped below to 1..HARD_LANE_CAP.

    couplings (A9): [{a, b, via}] pairs the ontology consult found
    module-coupled — a candidate coupled to an in-flight or
    already-chosen task WARNS-AND-SERIALIZES. None means the consult
    did not run; the CLI prints the standing loud-degradation line.

    budget_exhausted (A9): the burst's parallel_budget ran out — no new
    starts; eligible candidates land in budget_held with an explicit
    report, never silently truncated."""
    # The flag parser clamps --parallel=N, but this function is also
    # reachable through the raw CLI --cap — clamp HERE so no caller can
    # smuggle 0 (which silently starved exclusive tasks) or 10 past the
    # hard cap (independent review, finding 8).
    cap = max(1, min(cap, HARD_LANE_CAP))
    records = {r["task"]: r for r in (lanes["records"] if lanes else [])}
    tasks = graph["tasks"]
    by_id = {t["id"]: t for t in tasks}

    def lane_state(tid):
        return records[tid]["state"] if tid in records else None

    # merged: a lane that actually landed, or a task completed on the
    # sequential path (status done, no lane record contradicting it).
    merged = set()
    for t in tasks:
        st = lane_state(t["id"])
        if st == "merged" or (st is None and statuses.get(t["id"]) == "done"):
            merged.add(t["id"])

    active = [records[tid] for tid in records
              if records[tid]["state"] in MAN.LANE_ACTIVE_STATES]
    active_ids = {r["task"] for r in active}
    active_claims = [(r["task"], by_id[r["task"]]["files"])
                     for r in active if r["task"] in by_id]
    # An in-flight non-[P] lane owns the burst: nothing joins it.
    exclusive_active = any(not by_id[r["task"]].get("parallel", False)
                           for r in active if r["task"] in by_id)

    coupled_to = {}
    for pair in (couplings or []):
        a, b = int(pair["a"]), int(pair["b"])
        via = pair.get("via", "module dependency")
        coupled_to.setdefault(a, []).append((b, via))
        coupled_to.setdefault(b, []).append((a, via))

    STUCK = ("parked", "errored", "failed", "budget-stopped")
    out = {"dispatch": [], "serialized": [], "frozen": [], "waiting": [],
           "capped": [], "budget_held": [], "exclusive": False}
    chosen_claims = []
    for t in tasks:
        tid = t["id"]
        if tid in merged or tid in active_ids:
            continue
        unmet = [d for d in t["depends"] if d not in merged]
        if unmet:
            stuck = [d for d in unmet if lane_state(d) in STUCK]
            if stuck:
                out["frozen"].append(
                    (tid, "depends on T%d, whose lane is %s"
                     % (stuck[0], lane_state(stuck[0]))))
            else:
                out["waiting"].append(tid)
            continue
        if exclusive_active:
            out["serialized"].append(
                (tid, "a non-[P] task holds the burst — it runs alone"))
            continue
        if out["exclusive"]:
            out["serialized"].append(
                (tid, "T%d is not [P] and runs alone" % out["dispatch"][0]))
            continue
        if not t.get("parallel", False):
            if active or out["dispatch"]:
                out["serialized"].append(
                    (tid, "not [P] — runs alone, after the current burst"))
            elif budget_exhausted:
                out["budget_held"].append(tid)
            else:
                out["dispatch"].append(tid)
                out["exclusive"] = True
            continue
        overlap = None
        for other_id, files in active_claims + chosen_claims:
            hits = claims_overlap(t["files"], files)
            if hits:
                overlap = (other_id, hits)
                break
        if overlap:
            out["serialized"].append(
                (tid, "files overlap T%d (%s) — overlap serializes, it "
                 "never re-isolates" % (overlap[0], ", ".join(overlap[1][:3]))))
            continue
        concurrent = active_ids | {c for c, _ in chosen_claims}
        coupled = next(((o, via) for o, via in coupled_to.get(tid, [])
                        if o in concurrent), None)
        if coupled:
            out["serialized"].append(
                (tid, "ontology: coupled to T%d via %s — warn-and-serialize"
                 % coupled))
            continue
        if len(active) + len(out["dispatch"]) >= cap:
            out["capped"].append(tid)
            continue
        if budget_exhausted:
            out["budget_held"].append(tid)
            continue
        out["dispatch"].append(tid)
        chosen_claims.append((tid, t["files"]))
    return out


# ── subcommands ──────────────────────────────────────────────────────────────

def _load(manifest_path: pathlib.Path):
    if not manifest_path.is_file():
        raise Problem("no manifest at %s" % manifest_path)
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    graph = MAN.read_task_graph(text)
    if graph is None or not graph["tasks"]:
        raise Problem(
            "this cycle has no derived task_graph: — parallel lanes take "
            "the graph as their ONLY input. Run `manifest.py graph derive` "
            "at plan approval (an underivable plan cannot enter parallel "
            "mode).")
    return text, graph


def _load_couplings(path):
    """The ontology consult's output, or None when it did not run. The
    orchestrator writes this file per burst from the sage-memory code
    graph; this tool only ever READS it — the consult needs MCP, the
    decision must not."""
    if not path:
        return None
    import json
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return list(data.get("pairs", []))
    except (OSError, ValueError):
        return None


def cmd_schedule(manifest_path, cap, as_json=False, couplings_path=None,
                 budget_exhausted=False):
    text, graph = _load(manifest_path)
    couplings = _load_couplings(couplings_path)
    decision = schedule(graph, read_ledger_statuses(text),
                        MAN.read_lanes(text), cap, couplings=couplings,
                        budget_exhausted=budget_exhausted)
    if as_json:
        import json
        decision["ontology_consulted"] = couplings is not None
        print(json.dumps(decision))
        return 0
    if couplings is None:
        # The standing loud-degradation line (A9): an unchecked coupling
        # must never look like a checked-and-clean one.
        print("ontology consult: UNAVAILABLE — module coupling between "
              "candidate lanes is UNCHECKED this burst; interface coupling "
              "is caught only by plan review or the integration proof")
    if decision["budget_held"]:
        print("budget exhausted — NO NEW STARTS: %s held (in-flight lanes "
              "complete; mark held tasks budget-stopped at burst end — "
              "never grade a budget stop as failure)"
              % ", ".join("T%d" % t for t in decision["budget_held"]))
    if decision["dispatch"]:
        tag = " (exclusive — not [P], runs alone)" if decision["exclusive"] else ""
        print("dispatch now%s: %s" % (
            tag, ", ".join("T%d" % t for t in decision["dispatch"])))
    else:
        print("dispatch now: (nothing)")
    for tid, reason in decision["serialized"]:
        print("serialize T%d: %s" % (tid, reason))
    for tid, reason in decision["frozen"]:
        print("frozen T%d: %s" % (tid, reason))
    if decision["capped"]:
        print("capped (eligible, over the %d-lane cap): %s"
              % (cap, ", ".join("T%d" % t for t in decision["capped"])))
    if decision["waiting"]:
        print("waiting on depends: %s"
              % ", ".join("T%d" % t for t in decision["waiting"]))
    return 0


def cmd_open(manifest_path, task, branch, worktree, model, base, cap,
             repo_root=None, couplings_path=None):
    text, graph = _load(manifest_path)
    by_id = {t["id"]: t for t in graph["tasks"]}
    if task not in by_id:
        raise Problem("T%d is not in the task graph" % task)

    # A9(4), as an assertion rather than a prose instruction: a burst forks
    # from MERGED HEAD. When the integration checkout is reachable, the
    # claimed base must BE its HEAD — a base the orchestrator remembered
    # from before the last merge would hand dependent tasks a stale world.
    if base and repo_root is not None:
        r = _git(repo_root, "rev-parse", "HEAD")
        if r.returncode == 0:
            head = r.stdout.strip()
            if not (head.startswith(base) or base.startswith(head[:7])):
                raise Problem(
                    "burst base %s is not the integration checkout's HEAD "
                    "(%s) — lanes fork from merged HEAD, and dependent "
                    "context packets are built from it post-merge"
                    % (base, head[:12]))
        else:
            print("warning: could not verify the burst base against HEAD "
                  "(git unavailable at %s)" % repo_root)
    lanes = MAN.read_lanes(text) or {"burst_base": "", "records": []}
    existing = next((r for r in lanes["records"] if r["task"] == task), None)
    if existing and existing["state"] in MAN.LANE_ACTIVE_STATES + ("merged",):
        raise Problem("T%d already has a lane (%s, state %s)"
                      % (task, existing["branch"], existing["state"]))

    # The mechanical eligibility guard: open() re-derives the schedule and
    # refuses a dispatch the scheduler would not have made. The model does
    # not get to "just open" an ineligible lane.
    decision = schedule(graph, read_ledger_statuses(text), lanes, cap,
                        couplings=_load_couplings(couplings_path))
    if task not in decision["dispatch"]:
        why = dict(decision["serialized"] + decision["frozen"])
        reason = why.get(task)
        if reason is None and task in decision["capped"]:
            reason = "over the %d-lane cap" % cap
        if reason is None and task in decision["waiting"]:
            reason = "its depends are not merged"
        raise Problem("T%d is not dispatchable now: %s"
                      % (task, reason or "not a candidate"))

    records = [r for r in lanes["records"] if r["task"] != task]
    records.append({"task": task, "branch": branch, "worktree": worktree,
                    "state": "open", "model": model or "inherit",
                    "retries": 0, "note": ""})
    burst_base = lanes["burst_base"]
    active_before = [r for r in lanes["records"]
                     if r["state"] in MAN.LANE_ACTIVE_STATES]
    if base:
        if active_before and burst_base and base != burst_base:
            raise Problem(
                "burst base mismatch: lanes are in flight from %s, this open "
                "names %s — dependent work forks from merged HEAD in a NEW "
                "burst, never mid-burst" % (burst_base, base))
        if active_before and not burst_base:
            print("warning: this burst was opened UNPINNED — pinning %s now, "
                  "but the earlier lane(s)' fork point is unverified; treat "
                  "the pin as claimed, not proven" % base)
        burst_base = base
    elif not active_before:
        burst_base = ""            # new burst, unpinned — say so below

    text = MAN.write_lanes_block(
        text, MAN._lanes_block_lines(burst_base, records))
    text = _update_ledger_entry(text, task, status="in-progress",
                                attempts="+1", model=model or "inherit",
                                lane_branch=branch)
    manifest_path.write_text(MAN.stamp_updated(text), encoding="utf-8")
    print("lane open: T%d on %s (worktree %s, model %s)"
          % (task, branch, worktree, model or "inherit"))
    if not burst_base:
        print("warning: burst base not pinned — pass --base <sha of merged "
              "HEAD> so post-merge context packets are checkable")
    return 0


def cmd_mark(manifest_path, task, state, note):
    if state not in MARKABLE_STATES:
        raise Problem("state %r is not markable (merged comes only from "
                      "`lanes.py merge` — a depends edge must never be "
                      "satisfied by prose)" % state)
    text, graph = _load(manifest_path)
    lanes = MAN.read_lanes(text)
    rec = next((r for r in (lanes["records"] if lanes else [])
                if r["task"] == task), None)
    if rec is None:
        # budget-stopped may hit a task that never dispatched — the burst
        # ran out before its turn. That MUST still leave a record: an
        # explicit budget stop, never a silent truncation that grades as
        # failure (A9). Every other state describes an actual lane.
        if state != "budget-stopped":
            raise Problem("T%d has no lane record" % task)
        if task not in {t["id"] for t in graph["tasks"]}:
            raise Problem("T%d is not in the task graph" % task)
        if lanes is None:
            lanes = {"burst_base": "", "records": []}
        rec = {"task": task, "branch": "", "worktree": "",
               "state": state, "model": "", "retries": 0, "note": ""}
        lanes["records"].append(rec)
    rec["state"] = state
    if note:
        rec["note"] = " ".join(note.split())
    text = MAN.write_lanes_block(
        text, MAN._lanes_block_lines(lanes["burst_base"], lanes["records"]))
    ledger_status = _LEDGER_STATUS_FOR.get(state)
    if ledger_status:
        text = _update_ledger_entry(text, task, status=ledger_status)
    manifest_path.write_text(MAN.stamp_updated(text), encoding="utf-8")
    print("lane T%d → %s%s" % (task, state,
                               (" — " + rec["note"]) if note else ""))
    return 0


def cmd_retry(manifest_path, task):
    """The A9 errored contract: infra/rate-limit death (evidence per the
    1.3.3 rules — tokens, not turns) gets exactly ONE staggered retry.
    It is never graded and never consumes a quality-locked attempt, so
    this does NOT touch the ledger's attempts counter — `open` counts
    dispatches the quality loop judges; a retry re-runs one it never
    judged."""
    text, _ = _load(manifest_path)
    lanes = MAN.read_lanes(text)
    rec = next((r for r in (lanes["records"] if lanes else [])
                if r["task"] == task), None)
    if rec is None or rec["state"] != "errored":
        raise Problem("T%d has no ERRORED lane to retry (state: %s) — "
                      "retry exists for infra deaths only; a FAILED lane "
                      "goes back through the fix loop"
                      % (task, rec["state"] if rec else "none"))
    if rec.get("retries", 0) >= 1:
        raise Problem("T%d already used its one retry — a second infra "
                      "death is a real outage; park the lane and surface "
                      "it, don't grind the rate limit" % task)
    rec["state"] = "open"
    rec["retries"] = rec.get("retries", 0) + 1
    text = MAN.write_lanes_block(
        text, MAN._lanes_block_lines(lanes["burst_base"], lanes["records"]))
    text = _update_ledger_entry(text, task, status="in-progress")
    manifest_path.write_text(MAN.stamp_updated(text), encoding="utf-8")
    print("lane T%d → open (retry 1 of 1; not graded, attempts untouched). "
          "Stagger the re-dispatch (parallel_stagger_seconds) — the rate "
          "limit that killed it is probably still there." % task)
    return 0


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root)] + list(args),
                          capture_output=True, text=True)


def cmd_merge(manifest_path, task, repo_root):
    text, graph = _load(manifest_path)
    by_id = {t["id"]: t for t in graph["tasks"]}
    lanes = MAN.read_lanes(text)
    rec = next((r for r in (lanes["records"] if lanes else [])
                if r["task"] == task), None)
    if rec is None or rec["state"] != "open":
        raise Problem("T%d has no OPEN lane to merge (state: %s)"
                      % (task, rec["state"] if rec else "none"))

    # Dependency order is enforced, not requested.
    merged_ids = {r["task"] for r in lanes["records"]
                  if r["state"] == "merged"}
    statuses = read_ledger_statuses(text)
    for t in graph["tasks"]:
        if t["id"] not in {r["task"] for r in lanes["records"]} \
                and statuses.get(t["id"]) == "done":
            merged_ids.add(t["id"])
    unmet = [d for d in by_id[task]["depends"] if d not in merged_ids]
    if unmet:
        raise Problem("T%d depends on %s — merge lanes in dependency order"
                      % (task, ", ".join("T%d" % d for d in unmet)))

    dirty = _git(repo_root, "status", "--porcelain",
                 "--untracked-files=no").stdout.strip()
    if dirty:
        raise Problem("the integration checkout has uncommitted tracked "
                      "changes — commit or stash before merging a lane:\n"
                      + dirty)

    r = _git(repo_root, "merge", "--no-ff", rec["branch"],
             "-m", "merge lane T%d (%s)" % (task, rec["branch"]))
    if r.returncode != 0:
        conflicted = _git(repo_root, "diff", "--name-only",
                          "--diff-filter=U").stdout.split()
        _git(repo_root, "merge", "--abort")
        if conflicted:
            # Declared-disjoint was violated. The merge is aborted; the
            # conflict is a SCOPE finding, not a puzzle for the model.
            rec["note"] = "merge-conflict: " + ", ".join(conflicted[:6])
            new_text = MAN.write_lanes_block(
                text, MAN._lanes_block_lines(lanes["burst_base"],
                                             lanes["records"]))
            manifest_path.write_text(MAN.stamp_updated(new_text),
                                     encoding="utf-8")
            print("MERGE ABORTED — declared-disjoint violated: lane T%d "
                  "(%s) conflicts on: %s" % (task, rec["branch"],
                                             ", ".join(conflicted)))
            print("The conflict is a scope finding: these files were "
                  "touched outside their declaring task. Run check-diff "
                  "over the lane's commits, file the finding, and either "
                  "serialize the tasks or amend the plan. Never resolve a "
                  "lane conflict by model judgment.")
            return 1
        raise Problem("git merge failed without conflicts:\n"
                      + (r.stderr or r.stdout))

    rec["state"] = "merged"
    new_text = MAN.write_lanes_block(
        text, MAN._lanes_block_lines(lanes["burst_base"], lanes["records"]))
    manifest_path.write_text(MAN.stamp_updated(new_text), encoding="utf-8")
    print("lane T%d merged (%s → HEAD). Integration proof still required: "
          "full suite + gate sequence run once on merged HEAD per burst — "
          "lane-level green is lane evidence only." % (task, rec["branch"]))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("schedule", help="which tasks dispatch NOW, and why "
                                        "everything else waits")
    s.add_argument("manifest", type=pathlib.Path)
    s.add_argument("--cap", type=int, default=DEFAULT_CAP)
    s.add_argument("--json", action="store_true")
    s.add_argument("--couplings", default=None,
                   help="the burst's ontology-consult output (JSON with "
                        "pairs:[{a,b,via}]); absent = consult did not run, "
                        "announced loudly")
    s.add_argument("--budget-exhausted", action="store_true",
                   help="parallel_budget ran out — no new starts, held "
                        "tasks reported explicitly")

    o = sub.add_parser("open", help="record a lane dispatch (refuses what "
                                    "the scheduler would not dispatch)")
    o.add_argument("manifest", type=pathlib.Path)
    o.add_argument("--task", type=int, required=True)
    o.add_argument("--branch", required=True)
    o.add_argument("--worktree", required=True)
    o.add_argument("--model", default="inherit")
    o.add_argument("--base", default="",
                   help="the merged-HEAD sha this burst forks from")
    o.add_argument("--cap", type=int, default=DEFAULT_CAP)
    o.add_argument("--couplings", default=None)
    o.add_argument("--repo-root", type=pathlib.Path, default=None,
                   help="integration checkout; when given, --base must BE "
                        "its HEAD (the burst-base assertion)")

    m = sub.add_parser("mark", help="set a lane's state (never merged)")
    m.add_argument("manifest", type=pathlib.Path)
    m.add_argument("--task", type=int, required=True)
    m.add_argument("--state", required=True)
    m.add_argument("--note", default="")

    rt = sub.add_parser("retry", help="one staggered retry for an ERRORED "
                                      "lane — never graded, attempts "
                                      "untouched")
    rt.add_argument("manifest", type=pathlib.Path)
    rt.add_argument("--task", type=int, required=True)

    g = sub.add_parser("merge", help="merge an open lane, dependency order "
                                     "enforced; conflicts abort loudly")
    g.add_argument("manifest", type=pathlib.Path)
    g.add_argument("--task", type=int, required=True)
    g.add_argument("--repo-root", type=pathlib.Path,
                   default=pathlib.Path.cwd())

    args = p.parse_args(argv)
    try:
        if args.cmd == "schedule":
            return cmd_schedule(args.manifest, args.cap, args.json,
                                couplings_path=args.couplings,
                                budget_exhausted=args.budget_exhausted)
        if args.cmd == "open":
            return cmd_open(args.manifest, args.task, args.branch,
                            args.worktree, args.model, args.base, args.cap,
                            repo_root=args.repo_root,
                            couplings_path=args.couplings)
        if args.cmd == "mark":
            return cmd_mark(args.manifest, args.task, args.state, args.note)
        if args.cmd == "retry":
            return cmd_retry(args.manifest, args.task)
        if args.cmd == "merge":
            return cmd_merge(args.manifest, args.task,
                             args.repo_root.resolve())
    except (Problem, MAN.Problem, OSError) as exc:
        print("✗ %s" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
