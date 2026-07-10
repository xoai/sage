"""Compile and validate the route targets actually installed on a platform."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml


CATALOG_SCHEMA = "route-catalog/v1"
_TARGET_PATTERN = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9:_-]*$")


class CatalogError(ValueError):
    """Raised when workflow discovery and installed route targets disagree."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _frontmatter(path: Path) -> Mapping[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise CatalogError(f"workflow has no YAML frontmatter: {path}")
    try:
        closing = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise CatalogError(f"workflow has unterminated YAML frontmatter: {path}") from exc
    try:
        loaded = yaml.safe_load("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError as exc:
        raise CatalogError(f"workflow has malformed YAML frontmatter: {path}: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise CatalogError(f"workflow frontmatter must be a mapping: {path}")
    return loaded


def discover_workflows(workflow_dir: Path) -> dict[str, Path]:
    """Return canonical workflow names mapped to their source files."""

    directory = Path(workflow_dir)
    if not directory.is_dir():
        raise CatalogError(f"workflow directory does not exist: {directory}")
    workflows: dict[str, Path] = {}
    for path in sorted(directory.glob("*.workflow.md")):
        metadata = _frontmatter(path)
        name = metadata.get("name")
        if not isinstance(name, str) or not name.strip():
            raise CatalogError(f"workflow has no valid name: {path}")
        name = name.strip()
        expected_name = path.name[: -len(".workflow.md")]
        if name != expected_name:
            raise CatalogError(
                f"workflow name {name!r} does not match filename {expected_name!r}: {path}"
            )
        if name in workflows:
            raise CatalogError(f"duplicate workflow name: {name}")
        workflows[name] = path.resolve()
    if not workflows:
        raise CatalogError(f"no workflows found in: {directory}")
    return workflows


def _normalize_target(target: str) -> str:
    if not isinstance(target, str):
        raise CatalogError("invalid route target: expected a string")
    normalized = target.strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if not _TARGET_PATTERN.fullmatch(normalized):
        raise CatalogError(f"invalid route target: {target!r}")
    return normalized


def _catalog_hash(platform: str, routes: Mapping[str, Mapping[str, str]]) -> str:
    stable_routes = {
        name: {"workflow": route["workflow"], "target": route["target"]}
        for name, route in sorted(routes.items())
    }
    material = {
        "schema": CATALOG_SCHEMA,
        "platform": platform,
        "routes": stable_routes,
    }
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compile_route_catalog(
    workflow_dir: Path, platform: str, command_map: Mapping[str, str]
) -> dict[str, Any]:
    """Compile workflows and concrete installed IDs into a validated catalog."""

    if not isinstance(platform, str) or not platform.strip():
        raise CatalogError("platform must be a non-empty string")
    if not isinstance(command_map, Mapping):
        raise CatalogError("command map must be a mapping")
    platform = platform.strip()
    workflows = discover_workflows(Path(workflow_dir))
    unknown = sorted(set(command_map) - set(workflows))
    if unknown:
        raise CatalogError(f"unknown workflow in command map: {unknown[0]}")
    missing = sorted(set(workflows) - set(command_map))
    if missing:
        raise CatalogError(f"missing installed target for workflow: {missing[0]}")

    routes: dict[str, dict[str, str]] = {}
    targets: dict[str, str] = {}
    for workflow in sorted(workflows):
        target = _normalize_target(command_map[workflow])
        if target in targets:
            raise CatalogError(
                f"duplicate platform target {target!r} for {targets[target]!r} and {workflow!r}"
            )
        targets[target] = workflow
        routes[workflow] = {
            "workflow": workflow,
            "target": target,
            "source": str(workflows[workflow]),
        }

    return {
        "schema": CATALOG_SCHEMA,
        "platform": platform,
        "routes": routes,
        "generated_at": _utc_now(),
        "hash": _catalog_hash(platform, routes),
    }


def validate_route_target(catalog: Mapping[str, object], target: str) -> str:
    """Resolve a requested identifier to the platform's installed target."""

    if not isinstance(catalog, Mapping) or catalog.get("schema") != CATALOG_SCHEMA:
        raise CatalogError("invalid route catalog schema")
    routes = catalog.get("routes")
    if not isinstance(routes, Mapping):
        raise CatalogError("invalid route catalog routes")
    requested = _normalize_target(target)
    for route in routes.values():
        if isinstance(route, Mapping) and route.get("target") == requested:
            return requested

    token = requested[1:]
    if token.startswith("sage:"):
        token = token[len("sage:") :]
    elif token.startswith("sage-"):
        token = token[len("sage-") :]
    route = routes.get(token)
    if isinstance(route, Mapping) and isinstance(route.get("target"), str):
        return route["target"]
    raise CatalogError(f"unloadable route target: {target}")
