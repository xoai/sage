#!/usr/bin/env python3
"""Command-line boundary shared by Sage platform adapters."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from sage_runtime.contracts import ContractError, NormalizedEvent
from sage_runtime.composition import compile_composition_to_path
from sage_runtime.composition_contracts import CompositionError
from sage_runtime.catalog import (
    CatalogError,
    compile_route_catalog,
    discover_workflows,
    validate_route_target,
)
from sage_runtime.io import atomic_write_json
from sage_runtime.learning import (
    LearningConfigError,
    create_learning_backend,
    recall_before_work,
    render_recall_context,
    resolve_learning_config,
)
from sage_runtime.learning_contracts import LearningContext, LearningContractError
from sage_runtime.learning_candidates import (
    detect_learning_candidates,
    load_candidate,
    render_candidate_context,
)
from sage_runtime.gate import GateError, Operation, evaluate, load_gate_policy
from sage_runtime.hook_config import (
    HookConfigError,
    install_claude_hooks,
    install_hermes_hooks,
    validate_hook_config,
)
from sage_runtime.router import route
from sage_runtime.reflection import complete_reflection, skip_reflection
from sage_runtime.resolver import (
    ChoiceRequired,
    CompositionCatalog,
    CompositionRequest,
    resolve as resolve_composition,
)
from sage_runtime.state import (
    StateBusyError,
    StateError,
    append_event,
    load_active_bound_at,
    load_active_run,
    reconcile_run,
)


def _workflow_for_installed_id(installed_id: str, workflow_names: set[str]) -> str | None:
    if installed_id in workflow_names:
        return installed_id
    for prefix in ("sage:", "sage-"):
        if installed_id.startswith(prefix) and installed_id[len(prefix) :] in workflow_names:
            return installed_id[len(prefix) :]
    return None


def _discover_command_map(command_dir: Path, workflow_dir: Path) -> dict[str, str]:
    workflows = set(discover_workflows(workflow_dir))
    directory = Path(command_dir)
    if not directory.is_dir():
        raise CatalogError(f"command directory does not exist: {directory}")
    installed_ids: list[str] = []
    for entry in sorted(directory.iterdir()):
        if entry.is_file() and entry.suffix == ".md":
            installed_ids.append(entry.stem)
        elif entry.is_dir() and (entry / "SKILL.md").is_file():
            installed_ids.append(entry.name)

    command_map: dict[str, str] = {}
    for installed_id in installed_ids:
        workflow = _workflow_for_installed_id(installed_id, workflows)
        if workflow is None:
            continue
        if workflow in command_map:
            raise CatalogError(f"duplicate installed command for workflow: {workflow}")
        command_map[workflow] = f"/{installed_id}"
    return command_map


def _catalog_compile(args: argparse.Namespace) -> int:
    workflow_dir = Path(args.workflow_dir)
    command_map = _discover_command_map(Path(args.command_dir), workflow_dir)
    catalog = compile_route_catalog(workflow_dir, args.platform, command_map)
    atomic_write_json(Path(args.output), catalog)
    print(json.dumps({"ok": True, "output": str(Path(args.output)), "hash": catalog["hash"]}))
    return 0


def _catalog_validate(args: argparse.Namespace) -> int:
    with Path(args.catalog).open("r", encoding="utf-8") as handle:
        catalog = json.load(handle)
    resolved = validate_route_target(catalog, args.target)
    print(json.dumps({"ok": True, "target": resolved}))
    return 0


def _runtime_dir(project: str) -> Path:
    return Path(project) / ".sage" / "runtime"


def _read_stdin_json() -> dict[str, object]:
    try:
        value = json.loads(sys.stdin.read().removeprefix("\ufeff"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"stdin must contain one JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("stdin must contain one JSON object")
    return value


def _event_append(args: argparse.Namespace) -> int:
    item = NormalizedEvent.from_dict(_read_stdin_json())
    run_id = args.run_id or item.payload.get("run_id")
    if not isinstance(run_id, str) or not run_id or any(char in run_id for char in "/\\"):
        raise StateError("event append requires a safe --run-id or payload.run_id")
    run_dir = _runtime_dir(args.project) / "runs" / run_id
    appended = append_event(run_dir, item)
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    print(json.dumps({"ok": True, "appended": appended, "state": state}, sort_keys=True))
    return 0


def _state_reconcile(args: argparse.Namespace) -> int:
    state = reconcile_run(_runtime_dir(args.project) / "runs" / args.run_id)
    print(json.dumps({"ok": True, "state": state.to_dict()}, sort_keys=True))
    return 0


def _state_active(args: argparse.Namespace) -> int:
    state = load_active_run(_runtime_dir(args.project))
    if state is None:
        print(json.dumps({"active": False}))
    else:
        print(json.dumps({"active": True, "state": state.to_dict()}, sort_keys=True))
    return 0


def _route_decide(args: argparse.Namespace) -> int:
    with Path(args.catalog).open("r", encoding="utf-8") as handle:
        catalog = json.load(handle)
    prompt = sys.stdin.read()
    active_run = load_active_run(_runtime_dir(args.project))
    print(json.dumps(route(prompt, catalog, active_run).to_dict(), sort_keys=True))
    return 0


def _gate_evaluate(args: argparse.Namespace) -> int:
    operation = Operation.from_dict(_read_stdin_json())
    state = load_active_run(_runtime_dir(args.project))
    now = (
        datetime.now(timezone.utc)
        if args.now is None
        else datetime.fromisoformat(args.now.replace("Z", "+00:00"))
    )
    bound_at = load_active_bound_at(_runtime_dir(args.project))
    if bound_at is None:
        bound_at = now.isoformat().replace("+00:00", "Z")
    policy = load_gate_policy(Path(args.policy), bound_at)
    verdict = evaluate(operation, state, policy, now)
    print(json.dumps(verdict.to_dict(), sort_keys=True))
    return 0 if verdict.allowed else 3


def _hooks_validate(args: argparse.Namespace) -> int:
    validate_hook_config(Path(args.config), args.platform, backup_malformed=True)
    print(json.dumps({"ok": True, "config": args.config}))
    return 0


def _hooks_install(args: argparse.Namespace) -> int:
    config = Path(args.config)
    if args.platform == "claude-code":
        if not args.session_command:
            raise HookConfigError("Claude Code hook installation requires --session-command")
        install_claude_hooks(
            config,
            session_command=args.session_command,
            route_command=args.route_command,
            gate_command=args.gate_command,
            learning_recall_command=args.learning_recall_command,
            learning_observe_command=args.learning_observe_command,
            reflect_command=args.reflect_command,
        )
    elif args.platform == "hermes":
        install_hermes_hooks(
            config,
            route_command=args.route_command,
            gate_command=args.gate_command,
            learning_recall_command=args.learning_recall_command,
            learning_observe_command=args.learning_observe_command,
            reflect_command=args.reflect_command,
        )
    else:
        raise HookConfigError(f"unsupported hook platform: {args.platform}")
    print(json.dumps({"ok": True, "config": str(config)}))
    return 0


def _skill_directories(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {path.parent.name for path in root.rglob("SKILL.md")}


def _composition_compile(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    sage = project / "sage"
    if args.platform == "claude-code":
        platform_roots = [project / ".claude" / "skills"]
        command_dir = project / ".claude" / "commands"
    else:
        platform_roots = [project / "skills"]
        command_dir = project / "skills"
    platform_roots.extend(Path(path) for path in args.skill_root)
    skill_roots = [sage / "core" / "capabilities", sage / "skills", *platform_roots]
    installed: set[str] = set()
    for root in skill_roots:
        installed.update(_skill_directories(root))
    if command_dir.is_dir():
        installed.update(path.stem for path in command_dir.glob("*.md"))
    base_overlay = sage / "core" / "composition" / "defaults.yaml"
    user_overlay = Path.home() / ".sage" / "composition.yaml"
    project_overlay = project / ".sage" / "composition.yaml"
    catalog = compile_composition_to_path(
        Path(args.output),
        skill_roots,
        user_overlay if user_overlay.is_file() else None,
        project_overlay if project_overlay.is_file() else None,
        installed,
        base_overlay=base_overlay if base_overlay.is_file() else None,
    )
    print(json.dumps({"ok": True, "output": args.output, "hash": catalog["hash"]}))
    return 0


def _composition_resolve(args: argparse.Namespace) -> int:
    with Path(args.catalog).open("r", encoding="utf-8") as handle:
        catalog = CompositionCatalog.from_dict(json.load(handle))
    request = CompositionRequest.from_dict(_read_stdin_json())
    result = resolve_composition(catalog, request)
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 4 if isinstance(result, ChoiceRequired) else 0


def _learning_recall(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    config = resolve_learning_config(project)
    backend = create_learning_backend(config.backend, config=config)
    context = LearningContext(
        current_request=args.request,
        project_root=str(project),
        repo_name=project.name,
        platform=args.platform,
        active_capability=args.capability,
        selected_providers=tuple(args.provider),
        touched_subsystem=args.subsystem,
        touched_paths=tuple(args.path),
        seen_record_ids=tuple(args.seen_record_id),
    )
    result = recall_before_work(
        backend,
        context,
        limit=args.limit,
        max_bytes=args.max_bytes,
    )
    if args.format == "text":
        print(render_recall_context(result, max_bytes=args.max_bytes), end="")
    else:
        print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


def _learning_detect(args: argparse.Namespace) -> int:
    result = detect_learning_candidates(Path(args.run_dir))
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


def _learning_candidate_context(args: argparse.Namespace) -> int:
    candidate = load_candidate(Path(args.run_dir), args.id)
    print(render_candidate_context(candidate, max_bytes=args.max_bytes), end="")
    return 0


def _reflection_complete(args: argparse.Namespace) -> int:
    result = complete_reflection(
        Path(args.run_dir),
        stored=args.stored,
        novel_candidates=args.novel_candidates,
        occurred_at=args.occurred_at,
    )
    print(
        json.dumps(
            {
                "completed": result.completed,
                "status": result.status,
                "stored": result.stored,
                "novel_candidates": result.novel_candidates,
                "event_id": result.event_id,
            },
            sort_keys=True,
        )
    )
    return 0


def _reflection_skip(args: argparse.Namespace) -> int:
    result = skip_reflection(
        Path(args.run_dir),
        reason=args.reason,
        occurred_at=args.occurred_at,
    )
    print(
        json.dumps(
            {
                "skipped": result.skipped,
                "status": result.status,
                "reason": result.reason,
                "event_id": result.event_id,
            },
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sage-runtime")
    groups = parser.add_subparsers(dest="group", required=True)
    catalog = groups.add_parser("catalog", help="compile or validate a route catalog")
    catalog_actions = catalog.add_subparsers(dest="action", required=True)

    compile_parser = catalog_actions.add_parser("compile", help="compile installed route IDs")
    compile_parser.add_argument("--workflow-dir", required=True)
    compile_parser.add_argument("--platform", required=True)
    compile_parser.add_argument("--command-dir", required=True)
    compile_parser.add_argument("--output", required=True)
    compile_parser.set_defaults(handler=_catalog_compile)

    validate_parser = catalog_actions.add_parser("validate", help="validate a route target")
    validate_parser.add_argument("--catalog", required=True)
    validate_parser.add_argument("--target", required=True)
    validate_parser.set_defaults(handler=_catalog_validate)

    event_group = groups.add_parser("event", help="append a normalized runtime event")
    event_actions = event_group.add_subparsers(dest="action", required=True)
    append_parser = event_actions.add_parser("append", help="append JSON from stdin")
    append_parser.add_argument("--project", required=True)
    append_parser.add_argument("--run-id")
    append_parser.set_defaults(handler=_event_append)

    state_group = groups.add_parser("state", help="reconcile or inspect run state")
    state_actions = state_group.add_subparsers(dest="action", required=True)
    reconcile_parser = state_actions.add_parser("reconcile", help="replay a run event log")
    reconcile_parser.add_argument("--project", required=True)
    reconcile_parser.add_argument("--run-id", required=True)
    reconcile_parser.set_defaults(handler=_state_reconcile)
    active_parser = state_actions.add_parser("active", help="load the active run")
    active_parser.add_argument("--project", required=True)
    active_parser.set_defaults(handler=_state_active)

    route_group = groups.add_parser("route", help="decide an explicit or advisory route")
    route_actions = route_group.add_subparsers(dest="action", required=True)
    decide_parser = route_actions.add_parser("decide", help="read a prompt from stdin")
    decide_parser.add_argument("--catalog", required=True)
    decide_parser.add_argument("--project", required=True)
    decide_parser.set_defaults(handler=_route_decide)

    gate_group = groups.add_parser("gate", help="evaluate concrete strict invariants")
    gate_actions = gate_group.add_subparsers(dest="action", required=True)
    evaluate_parser = gate_actions.add_parser("evaluate", help="read an operation from stdin")
    evaluate_parser.add_argument("--project", required=True)
    evaluate_parser.add_argument("--policy", required=True)
    evaluate_parser.add_argument("--now")
    evaluate_parser.set_defaults(handler=_gate_evaluate)

    hooks_group = groups.add_parser("hooks", help="validate or merge platform hooks")
    hooks_actions = hooks_group.add_subparsers(dest="action", required=True)
    hooks_validate = hooks_actions.add_parser("validate", help="validate hook config")
    hooks_validate.add_argument("--platform", choices=("claude-code", "hermes"), required=True)
    hooks_validate.add_argument("--config", required=True)
    hooks_validate.set_defaults(handler=_hooks_validate)
    hooks_install = hooks_actions.add_parser("install", help="merge Sage hook commands")
    hooks_install.add_argument("--platform", choices=("claude-code", "hermes"), required=True)
    hooks_install.add_argument("--config", required=True)
    hooks_install.add_argument("--session-command")
    hooks_install.add_argument("--route-command", required=True)
    hooks_install.add_argument("--gate-command", required=True)
    hooks_install.add_argument("--learning-recall-command")
    hooks_install.add_argument("--learning-observe-command")
    hooks_install.add_argument("--reflect-command")
    hooks_install.set_defaults(handler=_hooks_install)

    composition_group = groups.add_parser("composition", help="compile skill composition")
    composition_actions = composition_group.add_subparsers(dest="action", required=True)
    composition_compile = composition_actions.add_parser(
        "compile", help="compile installed provider metadata"
    )
    composition_compile.add_argument("--project", required=True)
    composition_compile.add_argument(
        "--platform", choices=("claude-code", "hermes"), required=True
    )
    composition_compile.add_argument("--output", required=True)
    composition_compile.add_argument("--skill-root", action="append", default=[])
    composition_compile.set_defaults(handler=_composition_compile)
    composition_resolve = composition_actions.add_parser(
        "resolve", help="resolve provider ownership from a request on stdin"
    )
    composition_resolve.add_argument("--catalog", required=True)
    composition_resolve.set_defaults(handler=_composition_resolve)

    learning_group = groups.add_parser("learning", help="recall stored learnings")
    learning_actions = learning_group.add_subparsers(dest="action", required=True)
    learning_recall = learning_actions.add_parser(
        "recall", help="attempt bounded learning recall before work"
    )
    learning_recall.add_argument("--project", required=True)
    learning_recall.add_argument("--platform", required=True)
    learning_recall.add_argument("--request", required=True)
    learning_recall.add_argument("--capability")
    learning_recall.add_argument("--provider", action="append", default=[])
    learning_recall.add_argument("--subsystem")
    learning_recall.add_argument("--path", action="append", default=[])
    learning_recall.add_argument("--seen-record-id", action="append", default=[])
    learning_recall.add_argument("--limit", type=int, default=5)
    learning_recall.add_argument("--max-bytes", type=int, default=4096)
    learning_recall.add_argument("--format", choices=("json", "text"), default="json")
    learning_recall.set_defaults(handler=_learning_recall)
    learning_detect = learning_actions.add_parser(
        "detect", help="append candidates derived from structured run evidence"
    )
    learning_detect.add_argument("--run-dir", required=True)
    learning_detect.set_defaults(handler=_learning_detect)
    candidate_context = learning_actions.add_parser(
        "candidate-context", help="render a canonical self-learning skill request"
    )
    candidate_context.add_argument("--run-dir", required=True)
    candidate_context.add_argument("--id", required=True)
    candidate_context.add_argument("--max-bytes", type=int, default=2048)
    candidate_context.set_defaults(handler=_learning_candidate_context)

    reflection_group = groups.add_parser(
        "reflection", help="complete or skip a requested reflection"
    )
    reflection_actions = reflection_group.add_subparsers(dest="action", required=True)
    reflection_complete = reflection_actions.add_parser(
        "complete", help="durably complete a requested reflection"
    )
    reflection_complete.add_argument("--run-dir", required=True)
    reflection_complete.add_argument("--stored", type=int, required=True)
    reflection_complete.add_argument("--novel-candidates", type=int, required=True)
    reflection_complete.add_argument("--occurred-at")
    reflection_complete.set_defaults(handler=_reflection_complete)
    reflection_skip = reflection_actions.add_parser(
        "skip", help="durably skip a requested reflection"
    )
    reflection_skip.add_argument("--run-dir", required=True)
    reflection_skip.add_argument("--reason", required=True)
    reflection_skip.add_argument("--occurred-at")
    reflection_skip.set_defaults(handler=_reflection_skip)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except StateBusyError as exc:
        print(json.dumps({"ok": False, "fail_open": True, "error": str(exc)}), file=sys.stderr)
        return 75
    except (
        CatalogError,
        ContractError,
        CompositionError,
        GateError,
        HookConfigError,
        LearningConfigError,
        LearningContractError,
        StateError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
