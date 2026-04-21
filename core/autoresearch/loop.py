"""8-phase autoresearch loop state machine.

Phases marked 'agent' require LLM interaction (stdin stub in v1).
Phases marked 'runtime' are deterministic Python.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import git, harness, memory, results, scope, stuck as stuck_mod, timer
from .types import (
    BriefConfig,
    Decision,
    Direction,
    Iteration,
    Phase,
    PhaseState,
    Status,
    Termination,
    VerifyResult,
)

STATE_FILE = ".autoresearch-state.json"


def _run_git_reset(project_dir: Path, target_sha: str) -> None:
    """Reset to a specific commit SHA."""
    import subprocess
    subprocess.run(
        ["git", "reset", "--hard", target_sha],
        cwd=project_dir, capture_output=True, text=True, check=True,
    )
    subprocess.run(
        ["git", "clean", "-fd"],
        cwd=project_dir, capture_output=True, text=True, check=True,
    )


def _save_state(state: PhaseState, work_dir: Path) -> None:
    (work_dir / STATE_FILE).write_text(json.dumps(state.to_dict(), indent=2))


def _load_state(work_dir: Path) -> PhaseState | None:
    path = work_dir / STATE_FILE
    if not path.exists():
        return None
    return PhaseState.from_dict(json.loads(path.read_text()))


def _agent_review(work_dir: Path, jsonl_path: Path, iteration: int) -> str:
    """Phase 1: REVIEW — agent reads state and recent history."""
    tail = results.read_tail(jsonl_path)
    print(f"\n--- REVIEW (iteration {iteration}) ---")
    if tail:
        print(f"Last {len(tail)} iterations:")
        for it in tail[-5:]:
            print(f"  #{it.iteration} {it.status.value}: {it.description} → {it.metrics}")
    else:
        print("First iteration — no history yet.")
    return "reviewed"


def _agent_ideate(
    work_dir: Path, review_output: str, iteration: int,
    is_stuck: bool, all_iterations: list[Iteration],
) -> str:
    """Phase 2: IDEATE — agent proposes one change.

    In v1, prompts on stdin. Will be replaced by LLM call in Phase 2 (Sage integration).
    """
    if is_stuck:
        print("\n⚠ STUCK: Last 5 iterations were all discard/crash.")
        recovery = stuck_mod.build_recovery_context(all_iterations)
        print(recovery)
    prompt = f"\n--- IDEATE (iteration {iteration}) ---\nDescribe one change (1 sentence): "
    try:
        idea = input(prompt).strip()
    except EOFError:
        idea = f"automated change iteration {iteration}"
    if not idea:
        idea = f"automated change iteration {iteration}"
    return idea


def _agent_modify(work_dir: Path, idea: str, iteration: int) -> bool:
    """Phase 3: MODIFY — agent makes the change.

    In v1, prompts on stdin. Returns True if changes were made.
    """
    print(f"\n--- MODIFY (iteration {iteration}) ---")
    print(f"Idea: {idea}")
    print("Make your changes now. Press Enter when done (or 'skip' to skip):")
    try:
        response = input("> ").strip()
    except EOFError:
        response = ""
    return response.lower() != "skip"


def _decide(
    verify_result: VerifyResult,
    brief: BriefConfig,
    current_best_val: float | None,
) -> Decision:
    """Phase 6: DECIDE — deterministic decision based on verify output."""
    if verify_result.timed_out:
        return Decision(
            status=Status.CRASH,
            metrics={},
            improved=False,
            reason="timed out",
        )

    if verify_result.exit_code != 0:
        return Decision(
            status=Status.CRASH,
            metrics={},
            improved=False,
            reason=f"exit code {verify_result.exit_code}",
        )

    metrics = harness.parse(verify_result.stdout)
    if brief.metric.name not in metrics:
        return Decision(
            status=Status.CRASH,
            metrics=metrics,
            improved=False,
            reason=f"metric '{brief.metric.name}' not found in output",
        )

    value = metrics[brief.metric.name]
    if current_best_val is None:
        improved = True
        tied = False
    elif brief.metric.direction == Direction.LOWER:
        improved = value < current_best_val
        tied = value == current_best_val
    else:
        improved = value > current_best_val
        tied = value == current_best_val

    if improved:
        return Decision(status=Status.KEEP, metrics=metrics, improved=True, reason="improved")
    elif tied and brief.keep_on_tie:
        return Decision(status=Status.KEEP, metrics=metrics, improved=False, reason="tied (keep-on-tie)")
    else:
        return Decision(status=Status.DISCARD, metrics=metrics, improved=False, reason="no improvement")


def _check_termination(brief: BriefConfig, iterations: list[Iteration]) -> bool:
    """Phase 8: REPEAT — check if we should stop. Returns True to stop."""
    if brief.budget.termination == Termination.ITERATIONS:
        actual = sum(1 for it in iterations if it.status != Status.BASELINE)
        if brief.budget.max_iterations and actual >= brief.budget.max_iterations:
            print(f"\n🏁 Iteration budget reached ({brief.budget.max_iterations}).")
            return True

    if brief.budget.termination == Termination.TARGET:
        if brief.metric.target is not None:
            best = results.current_best(
                iterations, brief.metric.name, brief.metric.direction.value
            )
            if best is not None:
                if brief.metric.direction == Direction.LOWER and best <= brief.metric.target:
                    print(f"\n🎯 Target reached! {brief.metric.name}={best} ≤ {brief.metric.target}")
                    return True
                if brief.metric.direction == Direction.HIGHER and best >= brief.metric.target:
                    print(f"\n🎯 Target reached! {brief.metric.name}={best} ≥ {brief.metric.target}")
                    return True

    return False


def run_iteration(
    brief: BriefConfig,
    work_dir: Path,
    project_dir: Path,
    iteration: int,
    state: PhaseState | None = None,
) -> Iteration | None:
    """Run a single iteration through all 8 phases.

    Returns the Iteration record, or None if interrupted.
    """
    jsonl_path = work_dir / "autoresearch.jsonl"
    all_iterations = results.read_iterations(jsonl_path)

    # Phase 1: REVIEW
    _agent_review(work_dir, jsonl_path, iteration)

    # Phase 2: IDEATE
    is_stuck = stuck_mod.detect_stuck(all_iterations)
    idea = _agent_ideate(work_dir, "reviewed", iteration, is_stuck, all_iterations)

    pre_sha = git.short_sha(project_dir)
    state = PhaseState(
        iteration=iteration,
        phase=Phase.IDEATE,
        brief_path=str(work_dir / "brief.md"),
        work_dir=str(work_dir),
        branch=brief.branch_name,
        pre_iteration_sha=pre_sha,
        last_description=idea,
    )
    _save_state(state, work_dir)

    # Phase 3: MODIFY
    modified = _agent_modify(work_dir, idea, iteration)
    if not modified:
        print("  Skipped — no changes made.")
        return None

    # Scope check (gate)
    changed = git.changed_files(project_dir)
    if changed:
        ok, violations = scope.check_scope(changed, brief.scope.writable, brief.scope.frozen)
        if not ok:
            print(f"  ⚠ Scope violation: {violations}")
            git.reset_hard(project_dir)
            crash_it = Iteration(
                iteration=iteration,
                timestamp=datetime.now(timezone.utc).isoformat(),
                commit="",
                parent=git.short_sha(project_dir),
                description=idea,
                metrics={},
                duration_s=0,
                status=Status.CRASH,
                notes=f"scope violation: {violations}",
            )
            results.append_iteration(jsonl_path, crash_it)
            all_iterations.append(crash_it)
            results.write_tsv(work_dir / "results.tsv", all_iterations, brief.metric.name)
            return crash_it

    # Phase 4: COMMIT
    parent = git.short_sha(project_dir)
    sha = git.commit(f"autoresearch #{iteration}: {idea}", project_dir)
    state.phase = Phase.COMMIT
    state.last_commit = sha
    _save_state(state, work_dir)

    # Pre-verify gate: working tree must be clean
    if not git.is_clean(project_dir):
        print("  ⚠ Working tree not clean after commit — fixing...")
        git.commit("autoresearch: stage remaining changes", project_dir)
        sha = git.short_sha(project_dir)

    # Phase 5: VERIFY
    print(f"\n--- VERIFY (iteration {iteration}) ---")
    print(f"Running: {brief.verify}")
    vr = timer.run_with_budget(brief.verify, brief.budget.per_run_seconds, project_dir)

    state.phase = Phase.VERIFY
    _save_state(state, work_dir)

    # Save run log
    runs_dir = work_dir / "runs"
    runs_dir.mkdir(exist_ok=True)
    log_name = f"{iteration:04d}-{idea[:40].replace(' ', '-').replace('/', '_')}.log"
    (runs_dir / log_name).write_text(
        f"=== STDOUT ===\n{vr.stdout}\n=== STDERR ===\n{vr.stderr}\n"
        f"=== EXIT CODE: {vr.exit_code} | DURATION: {vr.duration_s:.1f}s ===\n"
    )

    # Phase 6: DECIDE
    best_val = results.current_best(
        all_iterations, brief.metric.name, brief.metric.direction.value
    )
    decision = _decide(vr, brief, best_val)

    print(f"  Result: {decision.status.value} — {decision.reason}")
    if decision.metrics:
        print(f"  Metrics: {decision.metrics}")

    # Revert if not keeping — undo the commit from Phase 4
    if decision.status != Status.KEEP:
        git.reset_hard(project_dir, undo_commit=True)

    # Phase 7: LOG
    it = Iteration(
        iteration=iteration,
        timestamp=datetime.now(timezone.utc).isoformat(),
        commit=sha if decision.status == Status.KEEP else "",
        parent=parent,
        description=idea,
        metrics=decision.metrics,
        duration_s=vr.duration_s,
        status=decision.status,
        notes=decision.reason if decision.status == Status.CRASH else "",
    )
    results.append_iteration(jsonl_path, it)
    all_iterations.append(it)
    results.write_tsv(work_dir / "results.tsv", all_iterations, brief.metric.name)

    state.phase = Phase.LOG
    state.last_metrics = decision.metrics
    state.last_status = decision.status.value
    _save_state(state, work_dir)

    return it


def run_baseline(
    brief: BriefConfig, work_dir: Path, project_dir: Path
) -> Iteration | None:
    """Run the verify command once to establish the baseline metric."""
    print("\n--- BASELINE ---")
    print(f"Running: {brief.verify}")

    vr = timer.run_with_budget(brief.verify, brief.budget.per_run_seconds, project_dir)
    metrics = harness.parse(vr.stdout)

    if brief.metric.name not in metrics:
        print(f"  ⚠ Metric '{brief.metric.name}' not found in verify output.")
        print(f"  stdout: {vr.stdout[:500]}")
        return None

    print(f"  Baseline: {metrics}")
    sha = git.short_sha(project_dir)

    it = Iteration(
        iteration=0,
        timestamp=datetime.now(timezone.utc).isoformat(),
        commit=sha,
        parent=sha,
        description="initial state",
        metrics=metrics,
        duration_s=vr.duration_s,
        status=Status.BASELINE,
    )

    jsonl_path = work_dir / "autoresearch.jsonl"
    results.append_iteration(jsonl_path, it)
    results.write_tsv(work_dir / "results.tsv", [it], brief.metric.name)

    return it


def run_session(brief: BriefConfig, work_dir: Path, project_dir: Path) -> None:
    """Run the full autoresearch session loop."""
    # Refuse to start on a dirty working tree
    if not git.is_clean(project_dir):
        print("❌ Working tree is dirty. Commit or stash your changes first.")
        print("   Autoresearch commits on every iteration — uncommitted changes")
        print("   would be mixed into the first autoresearch commit.")
        return

    jsonl_path = work_dir / "autoresearch.jsonl"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Check for crash recovery state (mid-phase resume)
    saved_state = _load_state(work_dir)
    if saved_state is not None:
        existing = results.read_iterations(jsonl_path)
        last_logged = existing[-1].iteration if existing else -1
        if saved_state.iteration > last_logged:
            # Crash happened after COMMIT but before LOG completed.
            # Reset to the exact pre-iteration SHA (handles double-commits
            # from the pre-verify gate cleanly).
            print(f"\n⚠ Recovering from crash during phase {saved_state.phase.value} "
                  f"(iteration {saved_state.iteration}).")
            if saved_state.phase in (Phase.COMMIT, Phase.VERIFY) and saved_state.pre_iteration_sha:
                print(f"  Resetting to pre-iteration state ({saved_state.pre_iteration_sha})...")
                _run_git_reset(project_dir, saved_state.pre_iteration_sha)
            elif saved_state.phase in (Phase.COMMIT, Phase.VERIFY):
                print("  Reverting last commit...")
                git.reset_hard(project_dir, undo_commit=True)
            # Clean up state file — JSONL is authoritative
            (work_dir / STATE_FILE).unlink(missing_ok=True)

    # Check for existing state (resume)
    existing = results.read_iterations(jsonl_path)
    if existing:
        print(f"\n📂 Resuming session — {len(existing)} iterations found.")
        start_iter = existing[-1].iteration + 1
    else:
        # Create branch and establish baseline
        git.create_branch(brief.branch_name, project_dir)
        baseline = run_baseline(brief, work_dir, project_dir)
        if baseline is None:
            print("❌ Cannot establish baseline. Fix verify command and retry.")
            return
        existing = [baseline]
        start_iter = 1

    iteration = start_iter
    try:
        while True:
            # Phase 8: REPEAT (check termination)
            all_iters = results.read_iterations(jsonl_path)
            if _check_termination(brief, all_iters):
                break

            it = run_iteration(brief, work_dir, project_dir, iteration)
            if it is not None:
                iteration += 1

    except KeyboardInterrupt:
        print("\n\n⏸ Interrupted. Session state saved — resume with same command.")

    # Final summary
    all_iters = results.read_iterations(jsonl_path)
    best = results.current_best(all_iters, brief.metric.name, brief.metric.direction.value)
    keeps = sum(1 for it in all_iters if it.status == Status.KEEP)
    print(f"\n📊 Session summary: {len(all_iters)} iterations, {keeps} kept, best={best}")
    print(f"   Results: {work_dir / 'results.tsv'}")
    print(f"   Branch: {brief.branch_name}")

    # Generate memory summary for the agent to store
    summary = memory.session_end_summary(brief, all_iters)
    storage_params = memory.format_summary_for_storage(summary, brief)
    summary_path = work_dir / "memory-summary.json"
    summary_path.write_text(json.dumps(storage_params, indent=2))
    print(f"   Memory summary: {summary_path}")
    print("   → Agent should store via sage_memory_store with the above parameters.")
