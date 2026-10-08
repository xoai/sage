#!/usr/bin/env python3
"""Exact 7+4 hook policy for the Hermes Sage install (spec 5.3.6-14).

Owns three things, honestly:

1. The canonical registry: seven blocking pre-tool gates (fail_closed: true)
   and four post-tool observers (fail_closed: false). Any parity change that
   is not deliberately recorded here fails validation.
2. Candidate validation: parses the actual candidate YAML, asserts the exact
   counts and script set, and refuses profile-wide ``hooks_auto_accept`` —
   Sage consent is the exact (event, command) pairs, never a blanket switch.
3. The failure matrix: after activation, a missing executable, timeout,
   crash, exit 2, or malformed output from a blocking hook vetoes the
   operation; observer equivalents stay visible (unverifiable) but never
   block. Failed activation restores the prior config untouched.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping, Optional

try:
    import yaml
except ImportError:  # Hermes ships PyYAML; absence must fail closed, not crash.
    yaml = None


_REGISTRY = (
    # Canonical session lifecycle hook. Hermes runs the same script from the
    # selected profile; plugin context injection complements rather than
    # replaces its mechanical session lock and worktree checks.
    {"event": "on_session_start", "matcher": None, "script": "sage-session-init.sh", "fail_closed": False},
    # Seven blocking pre-tool gates (spec 5.3.6-7).
    {"event": "pre_tool_call", "matcher": "write_file|patch", "script": "sage-spec-gate.sh", "fail_closed": True},
    {"event": "pre_tool_call", "matcher": "write_file|patch", "script": "sage-tdd-gate.sh", "fail_closed": True},
    {"event": "pre_tool_call", "matcher": "write_file|patch", "script": "sage-bookkeeping-gate.sh", "fail_closed": True, "file_preview_patterns": (".sage/work/*/manifest.md", ".sage/work/*/decisions.md")},
    {"event": "pre_tool_call", "matcher": "write_file|patch", "script": "sage-secrets-gate.sh", "fail_closed": True},
    {"event": "pre_tool_call", "matcher": "terminal", "script": "sage-verify-gate.sh", "fail_closed": True},
    {"event": "pre_tool_call", "matcher": "write_file|patch|terminal", "script": "sage-config-gate.sh", "fail_closed": True, "file_preview_patterns": (".sage/config.yaml",)},
    {"event": "pre_tool_call", "matcher": "write_file|patch", "script": "sage-scope-gate.sh", "fail_closed": True},
    # Four post-tool observers.
    {"event": "post_tool_call", "matcher": "write_file|patch|terminal", "script": "sage-verify-tracker.sh", "fail_closed": False},
    {"event": "post_tool_call", "matcher": "write_file|patch", "script": "sage-degradation-log.sh", "fail_closed": False},
    {"event": "post_tool_call", "matcher": "write_file|patch", "script": "sage-manifest-sync.sh", "fail_closed": False},
    {"event": "post_tool_call", "matcher": "write_file|patch|terminal", "script": "sage-scope-journal.sh", "fail_closed": False},
)

_SCRIPT_RE = re.compile(r"(?<![\w.-])(sage-[\w-]+\.sh)(?![\w.])")
_ADAPTER_MARKER = "sage-hermes-gate.sh"


def expected_registry() -> List[Dict[str, Any]]:
    """A fresh copy of the canonical session + 7 blocking + 4 observer registry."""

    return [dict(entry, **({"file_preview_patterns": list(entry["file_preview_patterns"])}
                          if "file_preview_patterns" in entry else {})) for entry in _REGISTRY]


def _entry_scripts(command: str) -> List[str]:
    return [m for m in _SCRIPT_RE.findall(command) if m != _ADAPTER_MARKER]


def validate_candidate_config(text: str) -> Dict[str, Any]:
    """Parse candidate YAML and assert the canonical session + 7+4 shape."""

    errors: List[str] = []
    if yaml is None:
        return {
            "ok": False,
            "blocking_count": 0,
            "observer_count": 0,
            "lifecycle_count": 0,
            "errors": ["PyYAML is unavailable; candidate cannot be parsed"],
        }
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return {
            "ok": False,
            "blocking_count": 0,
            "observer_count": 0,
            "lifecycle_count": 0,
            "errors": ["candidate config is not valid YAML: %s" % exc],
        }
    if not isinstance(document, dict):
        return {
            "ok": False,
            "blocking_count": 0,
            "observer_count": 0,
            "lifecycle_count": 0,
            "errors": ["candidate config must be a mapping"],
        }

    if document.get("hooks_auto_accept"):
        errors.append(
            "hooks_auto_accept is never an acceptable substitute for the exact "
            "Sage (event, command) consent pairs"
        )

    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        errors.append("candidate config has no hooks: mapping")
        hooks = {}

    expected_pre = {
        entry["script"]: entry
        for entry in _REGISTRY
        if entry["event"] == "pre_tool_call"
    }
    expected_post = {
        entry["script"]: entry
        for entry in _REGISTRY
        if entry["event"] == "post_tool_call"
    }
    expected_lifecycle = {
        entry["script"]: entry
        for entry in _REGISTRY
        if entry["event"] == "on_session_start"
    }

    blocking_count = 0
    observer_count = 0
    lifecycle_count = 0
    seen_pre: set = set()
    seen_post: set = set()
    seen_lifecycle: set = set()

    def _audit_entry(entry: Any, event: str, expected: Mapping[str, Any], seen: set) -> None:
        if not isinstance(entry, dict):
            errors.append("%s entry is not a mapping" % event)
            return
        command = entry.get("command")
        if not isinstance(command, str):
            return
        scripts = _entry_scripts(command)
        if _ADAPTER_MARKER not in command and "sage-session-init.sh" not in scripts:
            return  # not a Sage entry — the user's own hooks are not ours to judge
        if len(scripts) != 1:
            errors.append(
                "Sage adapter entry must name exactly one gate script, found %d: %s"
                % (len(scripts), command[:80])
            )
            return
        script = scripts[0]
        canonical = expected.get(script)
        if canonical is None:
            seen.add(script)  # surfaced by the drift check below
            return
        if entry.get("matcher") != canonical["matcher"]:
            errors.append(
                "%s matcher drift: %r != canonical %r"
                % (script, entry.get("matcher"), canonical["matcher"])
            )
        # Older receipts legitimately omit this additive transport capability.
        # If declared, it must be the exact narrowly owned request, not a
        # broad full-file scan. Fresh activation separately requires it.
        if "file_preview_patterns" in entry:
            expected_patterns = canonical.get("file_preview_patterns")
            if (expected_patterns is None or
                    entry["file_preview_patterns"] != list(expected_patterns)):
                errors.append("%s file preview request drift" % script)
        if script in seen:
            errors.append("duplicate Sage entry: %s" % script)
        seen.add(script)
        if event == "on_session_start":
            nonlocal_lifecycle[0] += 1
            if entry.get("fail_closed") is not False:
                errors.append("session hook %s must set fail_closed: false" % script)
        elif canonical["fail_closed"]:
            nonlocal_blocking[0] += 1
            if entry.get("fail_closed") is not True:
                errors.append("blocking gate %s must set fail_closed: true" % script)
        else:
            nonlocal_observer[0] += 1
            if entry.get("fail_closed") is not False:
                errors.append("observer %s must set fail_closed: false" % script)

    nonlocal_blocking = [0]
    nonlocal_observer = [0]
    nonlocal_lifecycle = [0]

    lifecycle_entries = hooks.get("on_session_start") or []
    if not isinstance(lifecycle_entries, list):
        errors.append("hooks.on_session_start must be a list")
        lifecycle_entries = []
    for entry in lifecycle_entries:
        _audit_entry(entry, "on_session_start", expected_lifecycle, seen_lifecycle)

    pre_entries = hooks.get("pre_tool_call") or []
    if not isinstance(pre_entries, list):
        errors.append("hooks.pre_tool_call must be a list")
        pre_entries = []
    for entry in pre_entries:
        _audit_entry(entry, "pre_tool_call", expected_pre, seen_pre)

    post_entries = hooks.get("post_tool_call") or []
    if not isinstance(post_entries, list):
        errors.append("hooks.post_tool_call must be a list")
        post_entries = []
    for entry in post_entries:
        _audit_entry(entry, "post_tool_call", expected_post, seen_post)

    blocking_count = nonlocal_blocking[0]
    observer_count = nonlocal_observer[0]
    lifecycle_count = nonlocal_lifecycle[0]

    if seen_lifecycle != set(expected_lifecycle):
        errors.append(
            "session registry drift: missing %s, unexpected %s"
            % (
                sorted(set(expected_lifecycle) - seen_lifecycle),
                sorted(seen_lifecycle - set(expected_lifecycle)),
            )
        )
    if seen_pre != set(expected_pre):
        errors.append(
            "blocking registry drift: missing %s, unexpected %s"
            % (sorted(set(expected_pre) - seen_pre), sorted(seen_pre - set(expected_pre)))
        )
    if seen_post != set(expected_post):
        errors.append(
            "observer registry drift: missing %s, unexpected %s"
            % (sorted(set(expected_post) - seen_post), sorted(seen_post - set(expected_post)))
        )
    if blocking_count != 7:
        errors.append("expected exactly 7 blocking entries, found %d" % blocking_count)
    if observer_count != 4:
        errors.append("expected exactly 4 observer entries, found %d" % observer_count)
    if lifecycle_count != 1:
        errors.append("expected exactly 1 session entry, found %d" % lifecycle_count)

    return {
        "ok": not errors,
        "blocking_count": blocking_count,
        "observer_count": observer_count,
        "lifecycle_count": lifecycle_count,
        "errors": errors,
    }


def extract_sage_records(text: str) -> Dict[str, Any]:
    """Return the exact installed Sage config and consent records.

    The receipt stores decoded YAML command strings, not reconstructed command
    guesses.  This makes update/rollback compare the same `(event, command)`
    pairs Hermes actually loads while preserving unrelated profile entries.
    """

    validation = validate_candidate_config(text)
    if not validation["ok"]:
        raise ValueError("candidate config is not canonical: %s" % "; ".join(validation["errors"]))
    if yaml is None:  # Defensive: validation already rejects this case.
        raise ValueError("PyYAML is unavailable")
    document = yaml.safe_load(text)
    hooks = document["hooks"]
    records: List[Dict[str, Any]] = []
    by_identity = {
        (entry["event"], entry["script"]): entry for entry in _REGISTRY
    }
    for event in ("on_session_start", "pre_tool_call", "post_tool_call"):
        for entry in hooks.get(event) or []:
            command = entry.get("command") if isinstance(entry, dict) else None
            if not isinstance(command, str):
                continue
            scripts = _entry_scripts(command)
            if _ADAPTER_MARKER not in command and "sage-session-init.sh" not in scripts:
                continue
            if len(scripts) != 1:
                raise ValueError("Sage adapter entry must name exactly one script")
            canonical = by_identity.get((event, scripts[0]))
            if canonical is None:
                raise ValueError("unexpected Sage hook record: %s/%s" % (event, scripts[0]))
            records.append(
                {
                    "event": event,
                    "command": command,
                    "matcher": entry.get("matcher"),
                    "fail_closed": entry.get("fail_closed"),
                    **({"file_preview_patterns": list(entry["file_preview_patterns"])}
                       if "file_preview_patterns" in entry else {}),
                }
            )
    ordered: List[Dict[str, Any]] = []
    for canonical in _REGISTRY:
        matches = [
            record
            for record in records
            if record["event"] == canonical["event"]
            and canonical["script"] in _entry_scripts(record["command"])
        ]
        if len(matches) != 1:
            raise ValueError("missing or duplicate Sage hook record: %s" % canonical["script"])
        ordered.append(matches[0])
    allowlist = [
        {"event": record["event"], "command": record["command"]}
        for record in ordered
    ]
    return {"config_records": ordered, "allowlist_records": allowlist}


def classify_hook_result(
    *,
    returncode: Optional[int],
    stdout: str,
    stderr: str,
    timed_out: bool,
    fail_closed: bool,
) -> str:
    """Map one hook execution onto the failure matrix (spec 5.3.13-14).

    Blocking hooks (fail_closed=True): a missing executable, timeout, crash,
    exit 2, or malformed output vetoes the operation — "block". Observer
    hooks (fail_closed=False): the same failures stay visible as
    "unverifiable" and never block.
    """

    def veto() -> str:
        return "block" if fail_closed else "unverifiable"

    if timed_out or returncode is None:
        return veto()
    if returncode != 0:
        return veto()
    text = (stdout or "").strip()
    if not text:
        return "allow"
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return veto()
    if not isinstance(payload, dict):
        return veto()
    decision = payload.get("decision") or payload.get("action")
    if decision == "allow":
        return "allow"
    if decision == "block":
        return veto() if fail_closed else "unverifiable"
    # A well-formed JSON document with an unrecognized decision is still
    # malformed output: it must never read as an allow for a blocking hook.
    return veto()


def plan_activation(
    *,
    current_config: str,
    candidate_config: str,
    consent_granted: bool,
) -> Dict[str, Any]:
    """Decide whether the candidate replaces the live config.

    Any failure — missing consent, malformed candidate, registry drift —
    leaves the prior config as the restore target and applies nothing.
    """

    errors: List[str] = []
    if not consent_granted:
        errors.append(
            "consent for the exact Sage (event, command) pairs was not granted"
        )
    validation = validate_candidate_config(candidate_config)
    errors.extend(validation["errors"])
    apply = not errors
    plan: Dict[str, Any] = {
        "apply": apply,
        "restore_config": current_config,
        "errors": errors,
    }
    if apply:
        plan["candidate_config"] = candidate_config
    return plan
