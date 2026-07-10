"""Shared fail-open helpers for thin Claude Code and Hermes hook adapters."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import hashlib
from pathlib import Path
from typing import Any, Mapping

from .gate import Operation
from .composition_contracts import CompositionError, ResolvedComposition


MAX_CONTEXT_BYTES = 2048
MAX_COMPOSITION_CONTEXT_BYTES = 3072
_READ_ONLY_TOOLS = frozenset(
    {
        "read",
        "read_file",
        "readfile",
        "glob",
        "grep",
        "search",
        "search_files",
        "list",
        "list_directory",
        "view",
        "view_image",
        "webfetch",
        "web_fetch",
        "websearch",
        "web_search",
    }
)
_READ_ONLY_SHELL = frozenset(
    {
        "cat",
        "dir",
        "find",
        "get-childitem",
        "get-content",
        "grep",
        "head",
        "ls",
        "pwd",
        "rg",
        "select-string",
        "tail",
        "test",
        "type",
        "wc",
    }
)
_READ_ONLY_GIT = frozenset(
    {"diff", "grep", "log", "rev-parse", "show", "status"}
)
_SHELL_CONTROL = re.compile(r"(?:&&|\|\||[;|>]|\r|\n)")


def bounded_text(value: str, limit: int = MAX_CONTEXT_BYTES) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value
    return encoded[:limit].decode("utf-8", errors="ignore")


def read_envelope() -> dict[str, object]:
    try:
        loaded = json.loads(sys.stdin.read().removeprefix("\ufeff"))
    except (json.JSONDecodeError, UnicodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def project_path(envelope: Mapping[str, object]) -> Path:
    configured = os.environ.get("SAGE_PROJECT")
    candidate = configured or envelope.get("cwd") or os.getcwd()
    return Path(str(candidate)).resolve()


def _runtime_cli(project: Path) -> Path:
    configured = os.environ.get("SAGE_RUNTIME_CLI")
    if configured:
        return Path(configured)
    project_cli = project / "sage/runtime/tools/sage_runtime_cli.py"
    if project_cli.is_file():
        return project_cli
    return Path(__file__).resolve().parent.parent / "sage_runtime_cli.py"


def _run_cli(
    project: Path,
    arguments: list[str],
    stdin_text: str,
    accepted_codes: tuple[int, ...] = (0,),
) -> dict[str, Any] | None:
    cli = _runtime_cli(project)
    if not cli.is_file():
        return None
    try:
        result = subprocess.run(
            [os.environ.get("PYTHON_BIN", sys.executable), str(cli), *arguments],
            input=stdin_text,
            capture_output=True,
            text=True,
            cwd=project,
            timeout=float(os.environ.get("SAGE_HOOK_TIMEOUT", "2")),
            check=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if result.returncode not in accepted_codes or len(result.stdout) > 16384:
        return None
    try:
        loaded = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def route_context(
    prompt: str,
    project: Path,
    *,
    session_id: str = "platform",
    occurred_at: str | None = None,
) -> str:
    catalog = Path(
        os.environ.get("SAGE_ROUTE_CATALOG", project / ".sage/runtime/route-catalog.json")
    )
    if not catalog.is_file():
        return ""
    decision = _run_cli(
        project,
        ["route", "decide", "--catalog", str(catalog), "--project", str(project)],
        prompt,
    )
    if decision is None:
        return ""
    try:
        from .routing_lifecycle import bind_route_decision

        bind_route_decision(
            project,
            prompt,
            decision,
            session_id=session_id,
            occurred_at=occurred_at,
        )
    except Exception:
        # Platform routing must remain fail-open; state errors never turn
        # advisory context into an authorization or denial channel.
        pass
    kind = decision.get("kind")
    target = decision.get("target")
    diagnostics = decision.get("diagnostics", [])
    diagnostic = ""
    if isinstance(diagnostics, list) and diagnostics and isinstance(diagnostics[0], str):
        diagnostic = f" {diagnostics[0]}"
    if kind in {"advisory", "suggestion"} and isinstance(target, str):
        return bounded_text(
            f"[Sage advisory] Installed route {target} may fit this request. "
            f"This is advice, not authority; combine it with other selected skills or ignore it."
            f"{diagnostic}"
        )
    if kind in {"explicit", "switch"} and isinstance(target, str):
        return bounded_text(
            f"[Sage explicit route] Validated installed route: {target}.{diagnostic}"
        )
    if decision.get("reason") == "active run suppresses inferred routing":
        return (
            "[Sage active run] Natural-language route inference is suppressed "
            "until switch or cancel."
        )
    return bounded_text(diagnostic.strip())


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _active_composition(project: Path) -> tuple[dict[str, Any], ResolvedComposition] | None:
    runtime_dir = project / ".sage" / "runtime"
    pointer = _read_json(runtime_dir / "active-run.json")
    if pointer is None or pointer.get("schema") != "active-run/v1":
        return None
    if pointer.get("active") is not True:
        return None
    state_path = pointer.get("state_path")
    if not isinstance(state_path, str) or not state_path:
        return None
    try:
        resolved_runtime = runtime_dir.resolve()
        resolved_state = (runtime_dir / state_path).resolve()
    except OSError:
        return None
    if resolved_runtime != resolved_state.parent and resolved_runtime not in resolved_state.parents:
        return None
    state = _read_json(resolved_state)
    if state is None or state.get("status") != "active":
        return None
    event_path = resolved_state.parent / "events.jsonl"
    try:
        lines = event_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        return None
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(event, dict) or event.get("type") != "run.started":
            continue
        payload = event.get("payload", {})
        raw = payload.get("resolved_composition") if isinstance(payload, dict) else None
        if not isinstance(raw, dict):
            return None
        try:
            return state, ResolvedComposition.from_dict(raw)
        except CompositionError:
            return None
    return None


def _render_active_composition(project: Path) -> str:
    active = _active_composition(project)
    if active is None:
        return ""
    state, composition = active
    capability = state.get("active_capability")
    provider_id = state.get("active_provider")
    if not isinstance(capability, str) or not isinstance(provider_id, str):
        lines = [
            "[Composition plan]",
            f"Workflow: {composition.selected_workflow or 'direct'}",
            "Resolved method owners:",
        ]
        for owner in (item for item in composition.bindings if item.role == "owner"):
            terminal = owner.terminal or "declared completion"
            lines.append(
                f"- {owner.capability}: {owner.provider_id} "
                f"(atomic={'yes' if owner.atomic else 'no'}; terminal={terminal})"
            )
            lines.extend(
                f"  - {helper.provider_id} ({helper.role})"
                for helper in composition.bindings
                if helper.capability == owner.capability and helper.role != "owner"
            )
        lines.append(
            "When each capability begins, follow its resolved owner and compatible "
            "helpers. Do not substitute another method from task keywords."
        )
        return bounded_text("\n".join(lines), MAX_COMPOSITION_CONTEXT_BYTES)
    owner = next(
        (
            item
            for item in composition.bindings
            if item.capability == capability
            and item.provider_id == provider_id
            and item.role == "owner"
        ),
        None,
    )
    if owner is None:
        return ""
    terminal = state.get("provider_terminal") or owner.terminal or "declared completion"
    lines = [
        "[Composition lock]",
        f"Capability: {capability}",
        f"Owner: {provider_id}",
        f"Atomic: {'yes' if owner.atomic else 'no'}; terminal: {terminal}",
    ]
    helpers = [
        item
        for item in composition.bindings
        if item.capability == capability and item.role != "owner"
    ]
    if helpers:
        lines.append("Compatible helpers:")
        lines.extend(f"- {item.provider_id} ({item.role})" for item in helpers)
    lines.append(
        "Keep the selected owner intact through its terminal; helpers may assist only in "
        "their declared roles."
    )
    return bounded_text("\n".join(lines), MAX_COMPOSITION_CONTEXT_BYTES)


def _claim_choice_marker(runtime_dir: Path, choice: Mapping[str, object]) -> bool:
    encoded = json.dumps(choice, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    marker_dir = runtime_dir / "choice-prompts"
    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(marker_dir / f"{digest}.seen", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except (FileExistsError, OSError):
        return False
    try:
        os.write(descriptor, b"prompted\n")
    finally:
        os.close(descriptor)
    return True


def _render_pending_choice(project: Path) -> str:
    runtime_dir = project / ".sage" / "runtime"
    choice = _read_json(runtime_dir / "choice-required.json")
    if choice is None or choice.get("schema") != "choice-required/v1":
        return ""
    capability = choice.get("capability")
    candidates = choice.get("candidates")
    if not isinstance(capability, str) or not isinstance(candidates, list):
        return ""
    provider_ids = [
        item.get("provider_id")
        for item in candidates
        if isinstance(item, dict) and isinstance(item.get("provider_id"), str)
    ]
    if len(provider_ids) < 2 or not _claim_choice_marker(runtime_dir, choice):
        return ""
    return bounded_text(
        "[Composition choice required]\n"
        f"Capability: {capability}\n"
        f"Validated owners: {', '.join(provider_ids)}\n"
        "Ask the user to choose one owner before entering this capability.",
        MAX_COMPOSITION_CONTEXT_BYTES,
    )


def composition_context(project: Path) -> str:
    """Render active ownership or one pending choice without method prose."""

    return _render_active_composition(project) or _render_pending_choice(project)


def combine_context(*parts: str, limit: int = MAX_COMPOSITION_CONTEXT_BYTES) -> str:
    return bounded_text("\n\n".join(part for part in parts if part), limit)


def _shell_is_read_only(command: object) -> bool:
    if not isinstance(command, str) or not command.strip() or _SHELL_CONTROL.search(command):
        return False
    try:
        parts = shlex.split(command, posix=os.name != "nt")
    except ValueError:
        return False
    if not parts:
        return False
    executable = Path(parts[0]).name.lower()
    if executable in _READ_ONLY_SHELL:
        return True
    if executable == "git" and len(parts) > 1:
        subcommand = parts[1].lower()
        if subcommand in _READ_ONLY_GIT:
            return True
        if subcommand == "branch":
            if len(parts) == 2:
                return True
            read_only_flags = {
                "--all",
                "--contains",
                "--format",
                "--list",
                "--merged",
                "--no-merged",
                "--remotes",
                "--show-current",
                "--verbose",
                "-a",
                "-r",
                "-v",
                "-vv",
            }
            return all(
                item in read_only_flags
                or item.startswith(("--contains=", "--format=", "--merged=", "--no-merged="))
                for item in parts[2:]
            )
        if subcommand == "worktree":
            return len(parts) >= 3 and parts[2].lower() == "list"
    return False


def _tool_is_read_only(tool_name: str, tool_input: Mapping[str, object]) -> bool:
    normalized = tool_name.strip().lower().replace("-", "_")
    if normalized in _READ_ONLY_TOOLS:
        return True
    if normalized in {"terminal", "bash", "shell", "powershell", "shell_command"}:
        return _shell_is_read_only(tool_input.get("command"))
    return False


def _platform_path(value: str, project: Path | None) -> str:
    path = Path(value)
    if project is None or not path.is_absolute():
        return value
    try:
        return path.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return value


def _paths(tool_input: Mapping[str, object], project: Path | None) -> tuple[str, ...]:
    paths: list[str] = []
    for key in ("file_path", "path", "notebook_path", "output_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append(_platform_path(value, project))
    values = tool_input.get("paths")
    if isinstance(values, list):
        paths.extend(
            _platform_path(value, project)
            for value in values
            if isinstance(value, str) and value
        )
    return tuple(dict.fromkeys(paths))


def operation_from_envelope(
    envelope: Mapping[str, object], project: Path | None = None
) -> Operation:
    tool_name = envelope.get("tool_name")
    tool_input = envelope.get("tool_input", {})
    if not isinstance(tool_name, str):
        tool_name = "unknown"
    if not isinstance(tool_input, Mapping):
        tool_input = {}
    return Operation(
        kind=tool_name,
        read_only=_tool_is_read_only(tool_name, tool_input),
        stage=os.environ.get("SAGE_GATE_STAGE", "pre-write"),
        scope=os.environ.get("SAGE_SCOPE", "full"),
        paths=_paths(tool_input, project),
    )


def gate_verdict(operation: Operation, project: Path) -> dict[str, Any] | None:
    configured = os.environ.get("SAGE_GATE_POLICY")
    project_policy = project / "sage/core/gates/_config/gate-modes.yaml"
    bundled_policy = Path(__file__).resolve().parent.parent / "gate-modes.yaml"
    policy = Path(configured) if configured else project_policy
    if configured is None and not policy.is_file():
        policy = bundled_policy
    if not policy.is_file():
        return None
    return _run_cli(
        project,
        ["gate", "evaluate", "--project", str(project), "--policy", str(policy)],
        json.dumps(operation.to_dict()),
        accepted_codes=(0, 3),
    )
