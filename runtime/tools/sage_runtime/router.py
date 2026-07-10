"""Deterministic Sage routing with explicit authority and inferred advice."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .catalog import CatalogError, validate_route_target
from .contracts import RunState


ROUTE_DECISION_SCHEMA = "route-decision/v1"
_EXPLICIT_COMMAND = re.compile(r"^\s*(/[A-Za-z0-9][A-Za-z0-9:_-]*)\b")
_WRONG_NAMESPACE = re.compile(r"^\s*sage:([A-Za-z0-9][A-Za-z0-9_-]*)\b", re.IGNORECASE)
_FENCED_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_INLINE_QUOTE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`")
_TRANSCRIPT_LABEL = re.compile(
    r"^\s*(?:user|assistant|system|human|agent|tool|transcript)\s*:", re.IGNORECASE
)


@dataclass(frozen=True)
class RouteDecision:
    """A stable decision object consumed by platform-specific adapters."""

    kind: str
    target: str | None = None
    authoritative: bool = False
    arm_gate: bool = False
    reason: str = "no route"
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ROUTE_DECISION_SCHEMA,
            "kind": self.kind,
            "target": self.target,
            "authoritative": self.authoritative,
            "arm_gate": self.arm_gate,
            "reason": self.reason,
            "diagnostics": list(self.diagnostics),
        }


def _run_is_active(active_run: RunState | Mapping[str, object] | None) -> bool:
    if isinstance(active_run, RunState):
        return active_run.status == "active"
    return isinstance(active_run, Mapping) and active_run.get("status") == "active"


def _routes(catalog: Mapping[str, object]) -> Mapping[str, object]:
    routes = catalog.get("routes")
    if not isinstance(routes, Mapping):
        raise CatalogError("invalid route catalog routes")
    return routes


def _workflow_target(catalog: Mapping[str, object], workflow: str) -> str | None:
    route_item = _routes(catalog).get(workflow)
    if not isinstance(route_item, Mapping):
        return None
    target = route_item.get("target")
    return target if isinstance(target, str) else None


def _advisory_text(prompt: str) -> str:
    without_fences = _FENCED_BLOCK.sub(" ", prompt)
    kept_lines: list[str] = []
    for line in without_fences.splitlines():
        if line.lstrip().startswith(">") or _TRANSCRIPT_LABEL.match(line):
            continue
        kept_lines.append(line)
    return _INLINE_QUOTE.sub(" ", "\n".join(kept_lines))


def _matched_workflows(prompt: str, catalog: Mapping[str, object]) -> list[str]:
    text = _advisory_text(prompt)
    matches: list[str] = []
    for workflow in sorted(_routes(catalog)):
        if not isinstance(workflow, str):
            continue
        pattern = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(workflow)}(?![A-Za-z0-9_-])", re.I)
        if pattern.search(text):
            matches.append(workflow)
    return matches


def route(
    prompt: str,
    catalog: Mapping[str, object],
    active_run: RunState | Mapping[str, object] | None,
) -> RouteDecision:
    """Route one current user message without using prose as authority."""

    if not isinstance(prompt, str):
        raise TypeError("prompt must be a string")
    active = _run_is_active(active_run)

    explicit = _EXPLICIT_COMMAND.match(prompt)
    if explicit:
        requested = explicit.group(1)
        if requested.lower() == "/cancel":
            if active:
                return RouteDecision(
                    kind="cancel",
                    authoritative=True,
                    reason="explicit cancel for active run",
                )
            return RouteDecision(kind="none", reason="no active run to cancel")
        try:
            target = validate_route_target(catalog, requested)
        except CatalogError:
            return RouteDecision(
                kind="none",
                reason="explicit command is outside the Sage route catalog",
                diagnostics=(f"route target {requested} is not installed; Sage inference skipped",),
            )
        return RouteDecision(
            kind="switch" if active else "explicit",
            target=target,
            authoritative=True,
            reason="validated explicit command",
        )

    if active:
        return RouteDecision(kind="none", reason="active run suppresses inferred routing")

    wrong_namespace = _WRONG_NAMESPACE.match(prompt)
    if wrong_namespace:
        workflow = wrong_namespace.group(1).lower()
        target = _workflow_target(catalog, workflow)
        if target is not None:
            resolved = validate_route_target(catalog, target)
            return RouteDecision(
                kind="suggestion",
                target=resolved,
                reason="corrected non-command Sage namespace",
                diagnostics=(f"{wrong_namespace.group(0).strip()} is not a command; use {resolved}",),
            )

    matches = _matched_workflows(prompt, catalog)
    if len(matches) == 1:
        target = _workflow_target(catalog, matches[0])
        if target is not None:
            return RouteDecision(
                kind="advisory",
                target=validate_route_target(catalog, target),
                reason="unique idle workflow match",
            )
    if len(matches) > 1:
        return RouteDecision(
            kind="ambiguous",
            reason="multiple idle workflow matches",
            diagnostics=(f"matched workflows: {', '.join(matches)}",),
        )
    return RouteDecision(kind="none")
