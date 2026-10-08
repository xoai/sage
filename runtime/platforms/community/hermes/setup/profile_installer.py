#!/usr/bin/env python3
"""Staged install commit and managed stale-file pruning (spec 5.7).

One transactional flow, honestly ordered:

1. Authorities fail closed BEFORE any write — a missing, malformed, or
   cross-profile receipt/binding stops everything.
2. A managed destination that is a Git repository stops the run before
   mutation and reports the exact collision.
3. The plan is pure: planned writes from the artifact, planned removals
   from the prior receipt's stale managed targets, and a structural config
   candidate that touches only Sage-owned entries.
4. The candidate must pass the Task 14 hook policy before a byte moves.
5. The incomplete journal is durable BEFORE mutation; failure after it
   restores the pre-invocation managed set and config exactly.
6. Activation re-validates the on-disk result; only then does the final
   receipt land and the journal complete.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import sys
import tempfile
import uuid
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple
from contextlib import ExitStack, contextmanager

import hook_config
import profile_binding
import receipts
import workspace_layout


class InstallError(RuntimeError):
    """The install transaction failed; destinations are restored or untouched."""


def _acquire_profile_transaction_lock(
    binding: profile_binding.ProfileBinding,
) -> Any:
    """Acquire the binding-scoped transaction lock, translating receipts errors.

    The receipts primitive rejects concurrent same-process and concurrent
    cross-process transactions with ``ReceiptError``. The installer's public
    contract is ``InstallError``, so the receipts exception is wrapped without
    hiding the underlying reason. Returns a context manager that enters the
    critical section; the wrapped receipts ``ReceiptError`` is raised on
    ``__enter__`` so callers can use ``with _acquire_profile_transaction_lock
    (binding): ...`` and observe ``InstallError`` directly.
    """

    @contextmanager
    def _translated():
        stack = ExitStack()
        stack_released = False
        try:
            stack.enter_context(receipts.profile_transaction_lock(binding))
        except receipts.ReceiptError as exc:
            raise InstallError(
                "profile operation is already being changed: %s" % exc
            ) from exc
        try:
            yield
        except BaseException as body_error:
            exception_state = sys.exc_info()
            try:
                try:
                    suppressed = stack.__exit__(*exception_state)
                finally:
                    stack_released = True
            except receipts.ReceiptError as exc:
                release_failure = InstallError(
                    "cannot release profile transaction lock: %s" % exc
                )
                release_failure.__cause__ = exc
                if hasattr(body_error, "add_note"):
                    body_error.add_note(str(release_failure))
                try:
                    setattr(
                        body_error,
                        "profile_transaction_release_error",
                        release_failure,
                    )
                except (AttributeError, TypeError):
                    pass
                suppressed = False
            if not suppressed:
                raise
        finally:
            if not stack_released:
                try:
                    stack.close()
                except receipts.ReceiptError as exc:
                    raise InstallError(
                        "cannot release profile transaction lock: %s" % exc
                    ) from exc

    return _translated()


_DEFAULT_DURABLE_CONFIG = b"""# Sage enforcement configuration
# Gates only fire in sessions whose selected workspace contains this file.

hard_enforcement: true
tdd_enforcement: true
secrets_gate: true
verify_gate: true
bookkeeping_gate: true

review_loop:
  mode: v2
  witness_capping: true

auto_qa: true
"""


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write_bytes(path: pathlib.Path, data: bytes) -> None:
    """Same-directory mkstemp atomic write — receipts-grade durability.

    ``tempfile.mkstemp`` creates the temp file with ``O_CREAT | O_EXCL``, so a
    pre-existing symlink, reparse point, or stale temp cannot redirect the
    write. The descriptor is fsynced before ``os.replace`` (Windows has no
    portable directory fsync; same stance as receipts).
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = -1
    temporary_name = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".%s." % path.name,
            suffix=".tmp",
            dir=os.fspath(path.parent),
        )
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(os.fspath(temporary_name), os.fspath(path))
        temporary_name = None
        if os.name != "nt":
            flags = os.O_RDONLY
            if hasattr(os, "O_DIRECTORY"):
                flags |= os.O_DIRECTORY
            dir_fd = os.open(os.fspath(path.parent), flags)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    except Exception:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        raise


def _read_json_binding(config_text: str, binding: profile_binding.ProfileBinding) -> None:
    """The config must carry a sage_profile_binding matching this binding."""

    mismatched = _binding_mismatches(
        _config_binding_block(config_text), _expected_fields(binding)
    )
    if mismatched:
        raise InstallError(
            "config binding conflicts with the selected profile: %s" % ", ".join(mismatched)
        )


def _prior_receipt(binding: profile_binding.ProfileBinding):
    if not os.path.lexists(os.fspath(binding.receipt_path)):
        return None
    try:
        return receipts.load_install_receipt(binding)
    except receipts.ReceiptError as exc:
        raise InstallError("install receipt fails closed: %s" % exc)


def _git_collision(binding: profile_binding.ProfileBinding) -> None:
    candidates = (
        binding.profile_root / "plugins" / "sage" / ".git",
        binding.profile_root / "hooks" / ".git",
    )
    for path in candidates:
        if path.exists():
            raise InstallError(
                "managed destination is a Git repository/worktree: %s — "
                "preserve or relocate it before deployment" % path
            )


def preflight_profile_target(binding: profile_binding.ProfileBinding) -> None:
    """Refuse profile destinations Sage cannot transactionally own."""

    _git_collision(binding)


def _planned_writes(
    binding: profile_binding.ProfileBinding,
    artifact_dir: pathlib.Path,
    staged_workspace: Optional[workspace_layout.StagedWorkspace] = None,
) -> List[Tuple[pathlib.Path, pathlib.Path]]:
    writes: List[Tuple[pathlib.Path, pathlib.Path]] = []
    plugin_src = artifact_dir / "plugins" / "sage"
    if not plugin_src.is_dir():
        raise InstallError("artifact is missing plugins/sage")
    for source in sorted(plugin_src.rglob("*")):
        if source.is_file():
            writes.append(
                (source, binding.profile_root / "plugins" / "sage" / source.relative_to(plugin_src))
            )
    scripts = [entry["script"] for entry in hook_config.expected_registry()]
    scripts.append("sage-hermes-gate.sh")
    for script in scripts:
        source = artifact_dir / "hooks" / script
        if not source.is_file():
            raise InstallError("artifact is missing required hook script: %s" % script)
        writes.append((source, binding.profile_root / "hooks" / script))
    if staged_workspace is not None:
        writes.append(
            (
                staged_workspace.instructions_candidate,
                binding.workspace_root / ".hermes.md",
            )
        )
        for source in sorted(staged_workspace.runtime_candidate.rglob("*")):
            if source.is_file():
                writes.append(
                    (
                        source,
                        binding.workspace_root
                        / "sage"
                        / source.relative_to(staged_workspace.runtime_candidate),
                    )
                )
    return writes


def _command_value(binding: profile_binding.ProfileBinding, bash_path: str, script: str) -> str:
    if script == "sage-session-init.sh":
        target = os.fspath(binding.profile_root / "hooks" / script).replace("\\", "/")
        return '"%s" "%s"' % (bash_path, target)
    adapter = os.fspath(binding.profile_root / "hooks" / "sage-hermes-gate.sh").replace(
        "\\", "/"
    )
    return '"%s" "%s" %s' % (bash_path, adapter, script)


def _command_line(binding: profile_binding.ProfileBinding, bash_path: str, script: str) -> str:
    return "      command: %s" % json.dumps(
        _command_value(binding, bash_path, script)
    )


def _native_skill_directory_candidate(
    text: str, binding: profile_binding.ProfileBinding
) -> str:
    """Expose native slash skills without re-dumping unrelated config text."""
    yaml = hook_config.yaml
    if yaml is None:
        raise InstallError("PyYAML is unavailable; skills configuration cannot be parsed")
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InstallError("skills configuration is not valid YAML") from exc

    def field(mapping, name):
        matches = [(key, value) for key, value in mapping.value
                   if isinstance(key, yaml.ScalarNode) and key.value == name]
        if len(matches) > 1:
            raise InstallError("duplicate skills configuration field: %s" % name)
        return matches[0] if matches else None

    if not isinstance(root, yaml.MappingNode):
        raise InstallError("skills configuration requires a profile mapping")
    target = binding.profile_root / "plugins" / "sage" / "skills"
    quoted = json.dumps(target.as_posix())
    skills_field = field(root, "skills")
    if skills_field is None:
        if "skills" in document:
            raise InstallError("skills configuration must use an explicit top-level field")
        return text + "skills:\n  external_dirs:\n    - " + quoted + "\n"
    skills_key, skills_node = skills_field
    if not isinstance(skills_node, yaml.MappingNode):
        raise InstallError("profile config skills must be a mapping")
    dirs_field = field(skills_node, "external_dirs")
    settings = document["skills"]
    if dirs_field is None and "external_dirs" in settings:
        raise InstallError("skills.external_dirs must use an explicit field")
    if dirs_field is not None:
        values = settings["external_dirs"]
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise InstallError("skills.external_dirs must be a list of nonempty strings")
        for value in values:
            expanded = pathlib.Path(os.path.expanduser(os.path.expandvars(value.strip())))
            if not expanded.is_absolute():
                expanded = binding.profile_root / expanded
            if expanded.resolve() == target.resolve():
                return text  # Preserve pre-existing user-owned spelling and ordering.

    tokens = list(yaml.scan(text))
    if skills_node.start_mark.index < skills_key.end_mark.index or any(
        isinstance(token, (yaml.AnchorToken, yaml.AliasToken))
        and skills_key.end_mark.index <= token.start_mark.index < skills_node.end_mark.index
        for token in tokens
    ):
        raise InstallError("skills configuration uses shared YAML anchors/aliases; cannot edit it safely")

    def append_flow(node, entry):
        close = node.end_mark.index - 1
        if not node.value:
            return text[:close] + entry + text[close:]
        last = node.value[-1][1] if isinstance(node, yaml.MappingNode) else node.value[-1]
        end = last.end_mark.index
        trailing_comma = any(isinstance(token, yaml.FlowEntryToken)
                             and end <= token.start_mark.index < close for token in tokens)
        separator = "" if trailing_comma else ","
        return text[:end] + separator + text[end:close] + " " + entry + text[close:]

    if dirs_field is None:
        if skills_node.flow_style:
            return append_flow(skills_node, "external_dirs: [" + quoted + "]")
        first_key = skills_node.value[0][0]
        position = text.rfind("\n", 0, first_key.start_mark.index) + 1
        indent = " " * first_key.start_mark.column
        addition = indent + "external_dirs:\n" + indent + "  - " + quoted + "\n"
    else:
        dirs_node = dirs_field[1]
        if dirs_node.flow_style:
            return append_flow(dirs_node, quoted)
        position = text.rfind("\n", 0, dirs_node.end_mark.index) + 1
        addition = " " * dirs_node.start_mark.column + "- " + quoted + "\n"
    return text[:position] + addition + text[position:]


def _config_candidate(
    current_text: str,
    binding: profile_binding.ProfileBinding,
    bash_path: str,
) -> str:
    """Structural, idempotent: strip Sage-owned entries, append canonical ones."""

    lines = current_text.splitlines()
    kept: List[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.match(r"^hooks_auto_accept:\s*", line):
            index += 1
            continue
        if re.match(r"^\s*- (?:matcher|command):", line):
            block = [line]
            lookahead = index + 1
            while lookahead < len(lines) and (
                not lines[lookahead].strip() or lines[lookahead].startswith("      ")
            ):
                block.append(lines[lookahead])
                lookahead += 1
            if any(
                re.match(r"^\s*(?:- )?command:", entry)
                and (
                    "sage-hermes-gate.sh" in entry
                    or "sage-session-init.sh" in entry
                )
                for entry in block
            ):
                index = lookahead  # drop the whole Sage-owned entry
                continue
        kept.append(line)
        index += 1

    text = "\n".join(kept)
    try:
        document = hook_config.yaml.safe_load(text) if hook_config.yaml is not None else None
    except Exception as exc:
        raise InstallError("profile config cannot be parsed for plugin enablement: %s" % exc) from exc
    if document is None:
        document = {}
    if not isinstance(document, dict):
        raise InstallError("profile config must be a mapping")
    plugins = document.get("plugins")
    if plugins is None:
        if kept and kept[-1].strip():
            kept.append("")
        kept.extend(("plugins:", "  enabled: [sage]"))
    elif not isinstance(plugins, dict):
        raise InstallError("profile config plugins must be a mapping")
    else:
        enabled = plugins.get("enabled")
        if enabled is None:
            plugin_line = next(
                i for i, line in enumerate(kept) if re.match(r"^plugins:\s*$", line)
            )
            kept.insert(plugin_line + 1, "  enabled: [sage]")
        elif not isinstance(enabled, list) or not all(isinstance(item, str) for item in enabled):
            raise InstallError("profile config plugins.enabled must be a string list")
        elif "sage" not in enabled:
            enabled_line = next(
                (
                    i
                    for i, line in enumerate(kept)
                    if re.match(r"^  enabled:\s*", line)
                ),
                None,
            )
            if enabled_line is None:
                raise InstallError("profile config plugins.enabled cannot be located")
            if re.match(r"^  enabled:\s*\[", kept[enabled_line]):
                kept[enabled_line] = "  enabled: %s" % json.dumps(enabled + ["sage"])
            else:
                insert_at = enabled_line + 1
                while insert_at < len(kept) and (
                    not kept[insert_at].strip() or kept[insert_at].startswith("    ")
                ):
                    insert_at += 1
                kept.insert(insert_at, "    - sage")
    text = "\n".join(kept)
    if not re.search(r"^hooks:\s*$", text, re.MULTILINE):
        if kept and kept[-1].strip():
            kept.append("")
        kept.append("hooks:")
    registry = hook_config.expected_registry()
    events = tuple(dict.fromkeys(entry["event"] for entry in registry))
    hooks_line = next(
        i for i, line in enumerate(kept) if re.match(r"^hooks:\s*$", line)
    )
    hooks_end = hooks_line + 1
    while hooks_end < len(kept):
        line = kept[hooks_end]
        if line.strip() and len(line) - len(line.lstrip()) == 0:
            break
        hooks_end += 1
    while hooks_end > hooks_line + 1 and not kept[hooks_end - 1].strip():
        hooks_end -= 1
    for event in events:
        if not re.search(r"^  %s:\s*$" % event, "\n".join(kept), re.MULTILINE):
            kept.insert(hooks_end, "  %s:" % event)
            hooks_end += 1
    out = kept[:]
    for event in events:
        event_line = next(
            i for i, ln in enumerate(out) if re.match(r"^  %s:\s*$" % event, ln)
        )
        bodies = []
        for entry in (e for e in registry if e["event"] == event):
            if entry["matcher"] is None:
                bodies.append(
                    "    - command: %s"
                    % json.dumps(_command_value(binding, bash_path, entry["script"]))
                )
            else:
                bodies.append('    - matcher: \'%s\'' % entry["matcher"])
                bodies.append(_command_line(binding, bash_path, entry["script"]))
            bodies.append(
                "      fail_closed: %s" % ("true" if entry["fail_closed"] else "false")
            )
            bodies.append("      timeout: 30")
            if entry.get("file_preview_patterns"):
                bodies.append("      file_preview_patterns: %s" % json.dumps(entry["file_preview_patterns"]))
        out[event_line + 1:event_line + 1] = bodies
    # The parsed key is authoritative regardless of YAML quoting. Keep its
    # original text rather than appending a duplicate or re-dumping user config.
    if "sage_profile_binding" not in document:
        if out and out[-1].strip():
            out.append("")
        out.append("sage_profile_binding:")
        for key, value in binding.to_config_mapping().items():
            out.append("  %s: %s" % (key, json.dumps(value)))
    return _native_skill_directory_candidate("\n".join(out) + "\n", binding)


def _owner_root(binding: profile_binding.ProfileBinding, owner: str) -> pathlib.Path:
    if owner == "profile":
        return binding.profile_root
    if owner == "workspace":
        return binding.workspace_root
    raise InstallError("unknown managed-target owner: %s" % owner)


def _preflight(
    binding: profile_binding.ProfileBinding,
    artifact_dir: pathlib.Path,
    consent_granted: bool,
    *,
    allow_missing_config: bool = False,
) -> Tuple[str, bytes]:
    # Consent is deliberately the first observable operation.  Callers may
    # validate already-frozen in-memory arguments, but may not build artifacts,
    # create staging directories, or read/write selected-profile state first.
    if not consent_granted:
        raise InstallError("consent for the exact Sage (event, command) pairs was not granted")
    preflight_profile_target(binding)
    if not artifact_dir.is_dir():
        raise InstallError("artifact directory does not exist: %s" % artifact_dir)
    config_path = binding.profile_root / "config.yaml"
    if allow_missing_config and not os.path.lexists(os.fspath(config_path)):
        return "", b""
    try:
        raw = config_path.read_bytes()
        return raw.decode("utf-8"), raw
    except (OSError, UnicodeDecodeError) as exc:
        raise InstallError("selected profile config is unreadable UTF-8: %s" % exc)


def _config_binding_block(config_text: str) -> Mapping[str, Any]:
    # Hermes may re-wrap scalars when saving YAML. Use its existing YAML
    # dependency, inspecting nodes first so safe_load cannot hide duplicate
    # authorities by silently keeping the last value.
    yaml = hook_config.yaml
    if yaml is None:
        raise InstallError("PyYAML is unavailable; binding cannot be parsed")
    try:
        node = yaml.compose(config_text, Loader=yaml.SafeLoader)
        if not isinstance(node, yaml.MappingNode):
            raise InstallError("config must be a mapping")
        bindings = [value for key, value in node.value
                    if isinstance(key, yaml.ScalarNode) and key.value == "sage_profile_binding"]
        if len(bindings) > 1:
            raise InstallError("config contains duplicate sage_profile_binding authorities")
        if not bindings:
            raise InstallError("config is missing the sage_profile_binding authority")
        if not isinstance(bindings[0], yaml.MappingNode):
            raise InstallError("sage_profile_binding must be a mapping")
        seen = set()
        for key, _value in bindings[0].value:
            if not isinstance(key, yaml.ScalarNode) or key.tag != "tag:yaml.org,2002:str":
                raise InstallError("sage_profile_binding fields must be explicit string keys")
            if key.value in seen:
                raise InstallError("sage_profile_binding block contains a duplicate field: %s" % key.value)
            seen.add(key.value)
        return yaml.safe_load(config_text)["sage_profile_binding"]
    except yaml.YAMLError as exc:
        raise InstallError("config binding is not valid YAML: %s" % exc) from exc


def _binding_mismatches(block: Mapping[str, Any], expected_fields: Mapping[str, str]) -> List[str]:
    def _norm(value: Any) -> str:
        return os.path.normcase(os.path.normpath(str(value)))

    mismatched = []
    for key, wanted in expected_fields.items():
        if key not in block:
            mismatched.append(key)
        elif key == "profile_id":
            if block[key] != wanted:
                mismatched.append(key)
        elif _norm(block[key]) != wanted:
            mismatched.append(key)
    return mismatched


def _expected_fields(binding: profile_binding.ProfileBinding) -> Dict[str, str]:
    def _norm(value: Any) -> str:
        return os.path.normcase(os.path.normpath(str(value)))

    return {
        "profile_id": binding.profile_id,
        "workspace_root": _norm(binding.workspace_root),
        "state_root": _norm(binding.state_root),
        "memory_root": _norm(binding.memory_root),
        "receipt_path": _norm(binding.receipt_path),
    }


def _require_config_matches_receipt(
    config_text: str, prior: receipts.InstallReceipt
) -> None:
    mismatched = _binding_mismatches(
        _config_binding_block(config_text), _expected_fields(prior.binding)
    )
    if mismatched:
        raise InstallError(
            "binding conflict requires a migration operation: %s" % ", ".join(mismatched)
        )


def _backup_pack_path(
    binding: profile_binding.ProfileBinding, operation_id: str
) -> pathlib.Path:
    journal_path = binding.run_journal_path(operation_id)
    return journal_path.with_name("%s.backup" % operation_id)


def _require_backup_pack_absent(
    binding: profile_binding.ProfileBinding, operation_id: str
) -> pathlib.Path:
    pack = _backup_pack_path(binding, operation_id)
    if os.path.lexists(os.fspath(pack)):
        stat_result = os.lstat(os.fspath(pack))
        if os.path.islink(os.fspath(pack)):
            raise InstallError(
                "backup pack path is a symlink and cannot be reused: %s" % pack
            )
        if not stat.S_ISDIR(stat_result.st_mode):
            raise InstallError(
                "backup pack path already exists and is not a directory: %s" % pack
            )
        raise InstallError(
            "backup pack path already exists and cannot be reused: %s" % pack
        )
    return pack


def _write_backup_pack(
    binding: profile_binding.ProfileBinding,
    operation_id: str,
    config_bytes: bytes,
    writes: List[Tuple[pathlib.Path, pathlib.Path]],
    stale,
    *,
    candidate_config_bytes: Optional[bytes] = None,
    candidate_receipt: Optional[receipts.InstallReceipt] = None,
) -> pathlib.Path:
    """Durable rollback state, written BEFORE any mutation (spec 5.7.7).

    Every byte lands through atomic temp+replace+fsync, and every payload
    file carries its sha256 in the manifest so a torn or tampered pack is
    detected before a single byte is restored. Config is captured as BYTES —
    text-mode round-trips would silently translate CRLF on Windows.
    """

    pack = _require_backup_pack_absent(binding, operation_id)
    # Repeat the preflight at creation time to close the TOCTOU window.
    pack.mkdir(parents=False)
    _atomic_write_bytes(pack / "config.yaml.bak", config_bytes)

    receipt_existed = binding.receipt_path.is_file()
    receipt_bytes = binding.receipt_path.read_bytes() if receipt_existed else None
    candidate_receipt_bytes = (
        receipts._serialized_document(candidate_receipt.to_mapping())
        if candidate_receipt is not None
        else None
    )

    created_dirs: List[str] = []
    for _source, destination in writes:
        cursor = destination.parent
        while cursor != binding.profile_root and not cursor.exists():
            created_dirs.append(os.fspath(cursor))
            cursor = cursor.parent

    manifest: Dict[str, Any] = {
        "writes": [],
        "pruned": [],
        "created_dirs": created_dirs,
        "config_existed": (binding.profile_root / "config.yaml").exists(),
        "config_sha256": _sha256_bytes(config_bytes),
        "candidate_config_sha256": (
            _sha256_bytes(candidate_config_bytes)
            if candidate_config_bytes is not None
            else None
        ),
        "receipt": {
            "path": os.fspath(binding.receipt_path),
            "existed": receipt_existed,
            "bak": "install-receipt.bak" if receipt_existed else None,
            "sha256": _sha256_bytes(receipt_bytes) if receipt_bytes is not None else None,
            "candidate_sha256": (
                _sha256_bytes(candidate_receipt_bytes)
                if candidate_receipt_bytes is not None
                else None
            ),
        },
        "durable_bootstrap": {
            "path": os.fspath(binding.state_root / "config.yaml"),
            "existed": (binding.state_root / "config.yaml").is_file(),
            "candidate_sha256": _sha256_bytes(_DEFAULT_DURABLE_CONFIG),
        },
    }
    if receipt_bytes is not None:
        _atomic_write_bytes(pack / "install-receipt.bak", receipt_bytes)
    for index, (source, destination) in enumerate(writes):
        entry: Dict[str, Any] = {
            "dest": os.fspath(destination),
            "existed": destination.exists(),
            "bak": None,
            "sha256": None,
            "candidate_sha256": _sha256(source),
        }
        if entry["existed"]:
            name = "w%d.bak" % index
            data = destination.read_bytes()
            _atomic_write_bytes(pack / name, data)
            entry["bak"] = name
            entry["sha256"] = _sha256_bytes(data)
        manifest["writes"].append(entry)
    for index, target in enumerate(stale):
        doomed = _owner_root(binding, target.owner) / target.relative_path.replace("/", os.sep)
        entry = {"dest": os.fspath(doomed), "bak": None, "sha256": None}
        if doomed.is_file():
            name = "p%d.bak" % index
            data = doomed.read_bytes()
            _atomic_write_bytes(pack / name, data)
            entry["bak"] = name
            entry["sha256"] = _sha256_bytes(data)
        manifest["pruned"].append(entry)
    _atomic_write_bytes(
        pack / "manifest.json", json.dumps(manifest, indent=2).encode("utf-8")
    )
    return pack


def _read_backup_pack(
    binding: profile_binding.ProfileBinding, operation_id: str
) -> Tuple[pathlib.Path, Mapping[str, Any]]:
    """Read the pack, verifying every payload file against its manifest hash."""

    pack = _backup_pack_path(binding, operation_id)
    manifest_path = pack / "manifest.json"
    if not manifest_path.is_file():
        raise InstallError("no rollback pack for operation %s" % operation_id)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(
            "rollback pack manifest is torn or unreadable: %s" % exc
        ) from exc
    if (
        not isinstance(manifest, dict)
        or "writes" not in manifest
        or "pruned" not in manifest
        or not isinstance(manifest.get("receipt"), dict)
    ):
        raise InstallError("rollback pack manifest is malformed")
    payloads = [entry.get("bak") for key in ("writes", "pruned") for entry in manifest[key]]
    payloads.append("config.yaml.bak")
    payloads.append(manifest["receipt"].get("bak"))
    for name in payloads:
        if name is None:
            continue
        payload = pack / name
        if not payload.is_file():
            raise InstallError("rollback pack payload is missing: %s" % name)
    for key in ("writes", "pruned"):
        for entry in manifest[key]:
            if entry.get("bak") is not None and entry.get("sha256"):
                if _sha256(pack / entry["bak"]) != entry["sha256"]:
                    raise InstallError(
                        "rollback pack payload hash mismatch: %s" % entry["bak"]
                    )
    config_path = pack / "config.yaml.bak"
    if manifest.get("config_sha256") and _sha256(config_path) != manifest["config_sha256"]:
        raise InstallError("rollback pack config hash mismatch")
    receipt_state = manifest["receipt"]
    if receipt_state.get("bak") is not None and receipt_state.get("sha256"):
        if _sha256(pack / receipt_state["bak"]) != receipt_state["sha256"]:
            raise InstallError("rollback pack receipt hash mismatch")
    return pack, manifest


def _transact(
    *,
    binding: profile_binding.ProfileBinding,
    artifact_dir: pathlib.Path,
    operation: str,
    prior,
    current_config: str,
    current_config_bytes: bytes,
    source_version: str,
    source_commit: str,
    bash_path: str,
    operation_id: Optional[str],
    staged_workspace: Optional[workspace_layout.StagedWorkspace] = None,
    activation_probe: Optional[Callable[..., Mapping[str, Any]]] = None,
    activation_rollback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    with _acquire_profile_transaction_lock(binding):
        return _transact_locked(
            binding=binding,
            artifact_dir=artifact_dir,
            operation=operation,
            prior=prior,
            current_config=current_config,
            current_config_bytes=current_config_bytes,
            source_version=source_version,
            source_commit=source_commit,
            bash_path=bash_path,
            operation_id=operation_id,
            staged_workspace=staged_workspace,
            activation_probe=activation_probe,
            activation_rollback=activation_rollback,
        )


def _transact_locked(
    *,
    binding: profile_binding.ProfileBinding,
    artifact_dir: pathlib.Path,
    operation: str,
    prior,
    current_config: str,
    current_config_bytes: bytes,
    source_version: str,
    source_commit: str,
    bash_path: str,
    operation_id: Optional[str],
    staged_workspace: Optional[workspace_layout.StagedWorkspace],
    activation_probe: Optional[Callable[..., Mapping[str, Any]]],
    activation_rollback: Optional[Callable[..., None]],
) -> Dict[str, Any]:
    config_path = binding.profile_root / "config.yaml"
    config_existed = config_path.exists()
    receipt_existed = binding.receipt_path.exists()
    prior_receipt_bytes = binding.receipt_path.read_bytes() if receipt_existed else None
    _git_collision(binding)
    writes = _planned_writes(binding, artifact_dir, staged_workspace)
    candidate_config = _config_candidate(current_config, binding, bash_path)
    candidate_config_bytes = candidate_config.encode("utf-8")
    validation = hook_config.validate_candidate_config(candidate_config)
    if not validation["ok"]:
        raise InstallError(
            "config candidate fails the hook policy: %s" % "; ".join(validation["errors"])
        )
    try:
        candidate_records = hook_config.extract_sage_records(candidate_config)
    except ValueError as exc:
        raise InstallError("candidate hook records are invalid: %s" % exc) from exc

    # Once receipts contain exact records, drift in the live config is a
    # migration/repair question.  Legacy empty records are accepted once and
    # upgraded by this transaction rather than guessed during rollback.
    if prior is not None and prior.config_records:
        try:
            current_records = hook_config.extract_sage_records(current_config)
        except ValueError as exc:
            raise InstallError("installed hook records drifted from the receipt: %s" % exc) from exc
        if tuple(current_records["config_records"]) != prior.config_records:
            raise InstallError("installed config records do not match the receipt")
        if tuple(current_records["allowlist_records"]) != prior.allowlist_records:
            raise InstallError("installed allowlist records do not match the receipt")

    planned_managed = [
        receipts.ManagedTarget.from_path(binding, destination, _sha256(source))
        for source, destination in writes
    ]
    prior_managed = list(prior.managed_targets) if prior is not None else []
    prior_keys = {(t.owner, t.relative_path.casefold()) for t in prior_managed}
    for (_source, destination), target in zip(writes, planned_managed):
        key = (target.owner, target.relative_path.casefold())
        if destination.exists() and key not in prior_keys:
            raise InstallError(
                "managed destination exists without receipt ownership: %s — "
                "preserve it or use an explicit migration" % destination
            )
    new_keys = {(t.owner, t.relative_path.casefold()) for t in planned_managed}
    stale = [t for t in prior_managed if (t.owner, t.relative_path.casefold()) not in new_keys]

    receipt = receipts.InstallReceipt.create(
        binding=binding,
        source_version=source_version,
        source_commit=source_commit,
        managed_targets=planned_managed,
        config_records=candidate_records["config_records"],
        allowlist_records=candidate_records["allowlist_records"],
    )

    operation_id = operation_id or uuid.uuid4().hex
    _require_backup_pack_absent(binding, operation_id)
    receipts.begin_run_journal(
        binding=binding,
        operation_id=operation_id,
        operation=operation,
        source_version=source_version,
        source_commit=source_commit,
        previous_managed_targets=prior_managed,
        previous_config_records=(list(prior.config_records) if prior is not None else []),
        previous_allowlist_records=(list(prior.allowlist_records) if prior is not None else []),
        planned_writes=planned_managed,
        planned_removals=[
            receipts.TargetRef(owner=t.owner, relative_path=t.relative_path)
            for t in stale
        ],
    )
    _write_backup_pack(
        binding,
        operation_id,
        current_config_bytes,
        writes,
        stale,
        candidate_config_bytes=candidate_config_bytes,
        candidate_receipt=receipt,
    )

    created_dirs: List[pathlib.Path] = []
    written_this_run: List[pathlib.Path] = []
    overwritten: Dict[pathlib.Path, bytes] = {}
    pruned: Dict[pathlib.Path, bytes] = {}
    activation_attempted = False
    activation: Dict[str, Any] = {
        "ok": False,
        "fresh_process_verified": False,
        "detail": "fresh CLI and Gateway activation proof has not run",
    }
    durable_config_path = binding.state_root / "config.yaml"
    durable_config_existed = durable_config_path.is_file()
    durable_config_created = False
    try:
        for source, destination in writes:
            if destination.exists() and destination not in overwritten:
                overwritten[destination] = destination.read_bytes()
            cursor = destination.parent
            while cursor != binding.profile_root and not cursor.exists():
                created_dirs.append(cursor)
                cursor = cursor.parent
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            written_this_run.append(destination)
        for target in stale:
            doomed = _owner_root(binding, target.owner) / target.relative_path.replace(
                "/", os.sep
            )
            if doomed.is_file():
                if _sha256(doomed) != target.sha256:
                    continue
                pruned[doomed] = doomed.read_bytes()
                doomed.unlink()
        _atomic_write_bytes(config_path, candidate_config_bytes)
        if not durable_config_existed:
            if durable_config_path.exists():
                raise InstallError(
                    "durable Sage config appeared after preflight: %s"
                    % durable_config_path
                )
            _atomic_write_bytes(durable_config_path, _DEFAULT_DURABLE_CONFIG)
            durable_config_created = True
        on_disk = config_path.read_text(encoding="utf-8")
        on_disk_records = hook_config.extract_sage_records(on_disk)
        if on_disk_records != candidate_records:
            raise InstallError("activation validation found config/allowlist record drift")
        for source, destination in writes:
            if not destination.is_file() or _sha256(destination) != _sha256(source):
                raise InstallError(
                    "installed bytes drifted from the artifact: %s" % destination
                )

        # Plugin startup treats the selected profile receipt as a binding
        # authority. Publish the exact candidate receipt inside the rollback
        # envelope before activation; the still-incomplete run journal remains
        # the success authority until both fresh surfaces pass. Any failure
        # restores/deletes this provisional receipt byte-exact below.
        receipts.write_install_receipt(binding, receipt)

        # Install/update success requires the same real restart surfaces the
        # user will run. Static YAML/hash checks are necessary but never an
        # activation result. Both CLI and Gateway must pass before receipt
        # publication; absence or partial proof rolls the transaction back.
        if activation_probe is None:
            raise InstallError(
                "activation failed: fresh CLI and Gateway proof is required"
            )
        activation_attempted = True
        probed = activation_probe(
            binding=binding,
            operation=operation,
            config_records=tuple(candidate_records["config_records"]),
            allowlist_records=tuple(candidate_records["allowlist_records"]),
        )
        if (
            not isinstance(probed, Mapping)
            or probed.get("ok") is not True
            or probed.get("fresh_process_verified") is not True
        ):
            detail = (
                probed.get("detail")
                if isinstance(probed, Mapping)
                else "invalid activation result"
            )
            raise InstallError("activation failed: %s" % detail)
        activation = dict(probed)

        receipts.complete_run_journal(
            binding=binding,
            operation_id=operation_id,
            result={
                "managed_count": len(planned_managed),
                "pruned": len(pruned),
                "skipped_user_edited": len(stale) - len(pruned),
                "config_records": len(candidate_records["config_records"]),
                "allowlist_records": len(candidate_records["allowlist_records"]),
                "fresh_process_verified": bool(activation.get("fresh_process_verified")),
            },
        )
    except Exception as exc:
        activation_rollback_error: Optional[Exception] = None
        for path in reversed(written_this_run):
            try:
                if path in overwritten:
                    _atomic_write_bytes(path, overwritten[path])
                elif path.exists():
                    path.unlink()
            except OSError:
                pass
        for path, data in pruned.items():
            try:
                _atomic_write_bytes(path, data)
            except OSError:
                pass
        try:
            if config_existed:
                _atomic_write_bytes(config_path, current_config_bytes)
            elif config_path.exists():
                config_path.unlink()
        except OSError:
            pass
        try:
            if receipt_existed and prior_receipt_bytes is not None:
                _atomic_write_bytes(binding.receipt_path, prior_receipt_bytes)
            elif binding.receipt_path.exists():
                binding.receipt_path.unlink()
        except OSError:
            pass
        if durable_config_created and durable_config_path.is_file():
            try:
                if _sha256(durable_config_path) == _sha256_bytes(
                    _DEFAULT_DURABLE_CONFIG
                ):
                    durable_config_path.unlink()
            except OSError:
                pass
        for directory in sorted(
            set(created_dirs), key=lambda item: len(item.parts), reverse=True
        ):
            try:
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
            except OSError:
                pass
        if activation_attempted:
            if activation_rollback is None:
                activation_rollback_error = InstallError(
                    "fresh restored-state proof callback is required"
                )
            else:
                try:
                    restored = activation_rollback(
                        binding=binding,
                        operation=operation,
                        operation_id=operation_id,
                        config_records=(
                            tuple(prior.config_records) if prior is not None else ()
                        ),
                        allowlist_records=(
                            tuple(prior.allowlist_records) if prior is not None else ()
                        ),
                    )
                    if (
                        not isinstance(restored, Mapping)
                        or restored.get("ok") is not True
                        or restored.get("fresh_process_verified") is not True
                    ):
                        detail = (
                            restored.get("detail")
                            if isinstance(restored, Mapping)
                            else "invalid restored-state proof result"
                        )
                        raise InstallError(
                            "fresh restored-state proof failed: %s" % detail
                        )
                except Exception as rollback_exc:
                    activation_rollback_error = rollback_exc
        if activation_rollback_error is not None:
            raise InstallError(
                "commit failed; local prior state was restored but exact consent "
                "restoration/fresh registry proof failed: %s; %s"
                % (exc, activation_rollback_error)
            ) from exc
        raise InstallError(
            "commit failed and prior state was restored: %s" % exc
        ) from exc

    shutil.rmtree(_backup_pack_path(binding, operation_id), ignore_errors=True)
    return {
        "ok": True,
        "operation_id": operation_id,
        "operation": operation,
        "activation": activation,
    }

def _stage_workspace(
    binding: profile_binding.ProfileBinding,
    framework_root: Optional[pathlib.Path],
) -> Optional[workspace_layout.StagedWorkspace]:
    if framework_root is None:
        return None
    try:
        layout = workspace_layout.WorkspaceLayout.from_binding(binding)
        return layout.stage_from_framework(pathlib.Path(framework_root))
    except workspace_layout.LayoutError as exc:
        raise InstallError("workspace candidate staging failed: %s" % exc) from exc


def _cleanup_workspace_stage(staged: Optional[workspace_layout.StagedWorkspace]) -> None:
    if staged is None:
        return
    try:
        staged.cleanup()
    except workspace_layout.LayoutError as exc:
        raise InstallError("workspace candidate cleanup failed: %s" % exc) from exc


def install(
    *,
    binding: profile_binding.ProfileBinding,
    artifact_dir: pathlib.Path,
    consent_granted: bool,
    source_version: str,
    source_commit: str,
    bash_path: str = "bash",
    operation_id: Optional[str] = None,
    framework_root: Optional[pathlib.Path] = None,
    activation_probe: Optional[Callable[..., Mapping[str, Any]]] = None,
    activation_rollback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    artifact_dir = pathlib.Path(artifact_dir)
    current_config, current_config_bytes = _preflight(
        binding, artifact_dir, consent_granted, allow_missing_config=True
    )
    prior = _prior_receipt(binding)
    if prior is not None:
        _read_json_binding(current_config, binding)
    elif current_config.strip() and re.search(
        r"^sage_profile_binding:\s*", current_config, re.MULTILINE
    ):
        _read_json_binding(current_config, binding)
    staged = _stage_workspace(binding, framework_root)
    try:
        return _transact(
            binding=binding,
            artifact_dir=artifact_dir,
            operation="install",
            prior=prior,
            current_config=current_config,
            current_config_bytes=current_config_bytes,
            source_version=source_version,
            source_commit=source_commit,
            bash_path=bash_path,
            operation_id=operation_id,
            staged_workspace=staged,
            activation_probe=activation_probe,
            activation_rollback=activation_rollback,
        )
    finally:
        _cleanup_workspace_stage(staged)


def update(
    *,
    binding: profile_binding.ProfileBinding,
    artifact_dir: pathlib.Path,
    consent_granted: bool,
    source_version: str,
    source_commit: str,
    bash_path: str = "bash",
    operation_id: Optional[str] = None,
    framework_root: Optional[pathlib.Path] = None,
    activation_probe: Optional[Callable[..., Mapping[str, Any]]] = None,
    activation_rollback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """Receipt-bound profile update (spec 5.1.6-7, 5.7.7-9)."""

    artifact_dir = pathlib.Path(artifact_dir)
    current_config, current_config_bytes = _preflight(
        binding, artifact_dir, consent_granted
    )
    prior = _prior_receipt(binding)
    if prior is None:
        raise InstallError(
            "no install receipt for the selected profile — run install first, "
            "or request a migration operation"
        )
    _require_config_matches_receipt(current_config, prior)
    _read_json_binding(current_config, binding)
    staged = _stage_workspace(binding, framework_root)
    try:
        return _transact(
            binding=binding,
            artifact_dir=artifact_dir,
            operation="update",
            prior=prior,
            current_config=current_config,
            current_config_bytes=current_config_bytes,
            source_version=source_version,
            source_commit=source_commit,
            bash_path=bash_path,
            operation_id=operation_id,
            staged_workspace=staged,
            activation_probe=activation_probe,
            activation_rollback=activation_rollback,
        )
    finally:
        _cleanup_workspace_stage(staged)

def _strip_sage_entries(config_text: str) -> str:
    """Remove receipt-owned Sage hook entries and preserve every user entry."""

    lines = config_text.splitlines()
    kept: List[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.match(r"^\s*- (?:matcher|command):", line):
            block = [line]
            lookahead = index + 1
            while lookahead < len(lines) and (
                not lines[lookahead].strip() or lines[lookahead].startswith("      ")
            ):
                block.append(lines[lookahead])
                lookahead += 1
            if any(
                re.match(r"^\s*(?:- )?command:", entry)
                and (
                    "sage-hermes-gate.sh" in entry
                    or "sage-session-init.sh" in entry
                )
                for entry in block
            ):
                index = lookahead
                continue
        kept.append(line)
        index += 1
    return "\n".join(kept) + "\n"


def uninstall(
    *,
    binding: profile_binding.ProfileBinding,
    consent_granted: bool,
    operation_id: Optional[str] = None,
    absence_probe: Optional[Callable[..., Mapping[str, Any]]] = None,
    absence_rollback: Optional[Callable[..., Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    with _acquire_profile_transaction_lock(binding):
        return _uninstall_locked(
            binding=binding,
            consent_granted=consent_granted,
            operation_id=operation_id,
            absence_probe=absence_probe,
            absence_rollback=absence_rollback,
        )


def _uninstall_locked(
    *,
    binding: profile_binding.ProfileBinding,
    consent_granted: bool,
    operation_id: Optional[str],
    absence_probe: Optional[Callable[..., Mapping[str, Any]]],
    absence_rollback: Optional[Callable[..., Mapping[str, Any]]],
) -> Dict[str, Any]:
    """Receipt-guided uninstall (spec 5.7.8, 5.9.4).

    Removes only receipt-owned files and the exact Sage config entries. A
    missing or corrupt receipt never guesses ownership. Durable state
    (.sage, .sage-memory, identity, user files) is never touched, and a
    user edit inside a managed path (bytes differ from the receipt) is
    preserved and reported rather than swept.
    """

    if not consent_granted:
        raise InstallError("consent for uninstall was not granted")
    if absence_probe is None:
        raise InstallError(
            "fresh CLI and Gateway absence proof callback is required before uninstall"
        )
    if absence_rollback is None:
        raise InstallError(
            "fresh restored-state proof callback is required before uninstall"
        )
    if not os.path.lexists(os.fspath(binding.receipt_path)):
        raise InstallError(
            "no install receipt for the selected profile — uninstall never "
            "guesses ownership from filenames"
        )
    try:
        prior = receipts.load_install_receipt(binding)
    except receipts.ReceiptError as exc:
        raise InstallError("install receipt fails closed: %s" % exc)

    config_path = binding.profile_root / "config.yaml"
    try:
        current_config = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InstallError("selected profile config is unreadable: %s" % exc)
    _require_config_matches_receipt(current_config, prior)
    config_bytes = config_path.read_bytes()

    # The receipt's own file survives as durable .sage evidence: receipts
    # reject .sage/ paths as managed targets at load, so it can never be in
    # the removal set.
    removal_targets = list(prior.managed_targets)
    planned_paths = [
        _owner_root(binding, t.owner) / t.relative_path.replace("/", os.sep)
        for t in removal_targets
    ]

    operation_id = operation_id or uuid.uuid4().hex
    _require_backup_pack_absent(binding, operation_id)
    receipts.begin_run_journal(
        binding=binding,
        operation_id=operation_id,
        operation="remove",
        source_version=prior.source_version,
        source_commit=prior.source_commit,
        previous_managed_targets=list(prior.managed_targets),
        previous_config_records=list(prior.config_records),
        previous_allowlist_records=list(prior.allowlist_records),
        planned_writes=[],
        planned_removals=[
            receipts.TargetRef(owner=t.owner, relative_path=t.relative_path)
            for t in removal_targets
        ],
    )
    _write_backup_pack(
        binding,
        operation_id,
        config_bytes,
        [],
        removal_targets,
    )

    removed: Dict[pathlib.Path, bytes] = {}
    skipped_user_edited = 0
    emptied_dirs: List[pathlib.Path] = []
    absence: Dict[str, Any] = {
        "ok": False,
        "fresh_process_verified": False,
        "detail": "fresh CLI and Gateway absence proof has not run",
    }
    try:
        for target, doomed in zip(removal_targets, planned_paths):
            if doomed.is_file():
                if _sha256(doomed) != target.sha256:
                    skipped_user_edited += 1
                    continue
                removed[doomed] = doomed.read_bytes()
                doomed.unlink()
                emptied_dirs.append(doomed.parent)
        config_path.write_text(_strip_sage_entries(current_config), encoding="utf-8")
        stripped_text = config_path.read_text(encoding="utf-8")
        remaining = [
            ln
            for ln in stripped_text.splitlines()
            if re.match(r"^\s*command:", ln) and "sage-hermes-gate.sh" in ln
        ]
        if remaining:
            raise InstallError("absence proof failed: Sage entries remain in config")
        for target, doomed in zip(removal_targets, planned_paths):
            if doomed.is_file() and _sha256(doomed) == target.sha256:
                raise InstallError("absence proof failed: %s still present" % doomed)
        for directory in sorted(
            set(emptied_dirs), key=lambda item: len(item.parts), reverse=True
        ):
            try:
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
            except OSError:
                pass
        probed = absence_probe(
            binding=binding,
            operation="uninstall",
            operation_id=operation_id,
            config_records=tuple(prior.config_records),
            allowlist_records=tuple(prior.allowlist_records),
        )
        if (
            not isinstance(probed, Mapping)
            or probed.get("ok") is not True
            or probed.get("fresh_process_verified") is not True
        ):
            detail = (
                probed.get("detail")
                if isinstance(probed, Mapping)
                else "invalid absence proof result"
            )
            raise InstallError("fresh uninstall absence proof failed: %s" % detail)
        absence = dict(probed)
    except Exception as exc:
        for path, data in removed.items():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            except OSError:
                pass
        try:
            config_path.write_bytes(config_bytes)
        except OSError:
            pass
        rollback_error: Optional[Exception] = None
        try:
            restored = absence_rollback(
                binding=binding,
                operation="uninstall",
                operation_id=operation_id,
                config_records=tuple(prior.config_records),
                allowlist_records=tuple(prior.allowlist_records),
            )
            if (
                not isinstance(restored, Mapping)
                or restored.get("ok") is not True
                or restored.get("fresh_process_verified") is not True
            ):
                detail = (
                    restored.get("detail")
                    if isinstance(restored, Mapping)
                    else "invalid restored-state proof result"
                )
                raise InstallError("fresh restored-state proof failed: %s" % detail)
        except Exception as rollback_exc:
            rollback_error = rollback_exc
        if rollback_error is not None:
            raise InstallError(
                "uninstall failed; local prior state was restored but exact consent "
                "restoration/fresh registry proof failed: %s; %s"
                % (exc, rollback_error)
            ) from exc
        raise InstallError(
            "uninstall failed and prior state was restored: %s" % exc
        ) from exc

    receipts.complete_run_journal(
        binding=binding,
        operation_id=operation_id,
        result={
            "removed": len(removed),
            "preserved_user_edited": skipped_user_edited,
            "fresh_process_verified": bool(absence.get("fresh_process_verified")),
        },
    )
    shutil.rmtree(_backup_pack_path(binding, operation_id), ignore_errors=True)
    return {
        "ok": True,
        "operation_id": operation_id,
        "operation": "uninstall",
        "absence": absence,
    }


def resume_incomplete(
    *,
    binding: profile_binding.ProfileBinding,
    operation_id: str,
) -> Dict[str, Any]:
    with _acquire_profile_transaction_lock(binding):
        return _resume_incomplete_locked(
            binding=binding, operation_id=operation_id
        )


def _resume_incomplete_locked(
    *,
    binding: profile_binding.ProfileBinding,
    operation_id: str,
) -> Dict[str, Any]:
    """Restore the pre-invocation state from a crashed run's rollback pack.

    Every pack entry is cross-checked against the journal's planned writes
    and removals before a byte moves — resume never restores a state the
    journal did not record. Freshness wins: a file that exists with bytes
    the pack did not capture is newer than the crash and is preserved.
    """

    journal = receipts.load_run_journal(binding, operation_id)
    if journal.is_complete:
        raise InstallError("journal %s is already complete — nothing to resume" % operation_id)
    pack, manifest = _read_backup_pack(binding, operation_id)
    config_path = binding.profile_root / "config.yaml"

    def _norm(value: Any) -> str:
        return os.path.normcase(os.path.normpath(str(value)))

    planned_write_paths = {
        _norm(_owner_root(binding, t.owner) / t.relative_path.replace("/", os.sep))
        for t in journal.planned_writes
    }
    planned_removal_paths = {
        _norm(_owner_root(binding, t.owner) / t.relative_path.replace("/", os.sep))
        for t in journal.planned_removals
    }
    for entry in manifest["writes"]:
        if _norm(entry["dest"]) not in planned_write_paths:
            raise InstallError(
                "rollback pack names a destination the journal did not plan: %s"
                % entry["dest"]
            )
    for entry in manifest["pruned"]:
        if _norm(entry["dest"]) not in planned_removal_paths:
            raise InstallError(
                "rollback pack names a removal the journal did not plan: %s"
                % entry["dest"]
            )

    restored_writes = 0
    restored_pruned = 0
    skipped_fresh = 0
    conflicts: List[str] = []
    for entry in manifest["writes"]:
        destination = pathlib.Path(entry["dest"])
        current_hash = _sha256(destination) if destination.is_file() else None
        previous_hash = entry.get("sha256")
        candidate_hash = entry.get("candidate_sha256")
        if entry["existed"]:
            if current_hash == previous_hash:
                continue
            if current_hash is not None and current_hash != candidate_hash:
                skipped_fresh += 1
                conflicts.append(os.fspath(destination))
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_bytes(destination, (pack / entry["bak"]).read_bytes())
            restored_writes += 1
        elif current_hash is not None:
            if candidate_hash is None or current_hash != candidate_hash:
                skipped_fresh += 1
                conflicts.append(os.fspath(destination))
                continue
            destination.unlink()
    for entry in manifest["pruned"]:
        if entry["bak"] is None:
            continue
        destination = pathlib.Path(entry["dest"])
        if destination.exists():
            if _sha256(destination) != entry["sha256"]:
                skipped_fresh += 1
                conflicts.append(os.fspath(destination))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(destination, (pack / entry["bak"]).read_bytes())
        restored_pruned += 1
    durable_bootstrap = manifest.get("durable_bootstrap") or {}
    durable_path = pathlib.Path(
        durable_bootstrap.get("path", binding.state_root / "config.yaml")
    )
    expected_durable_path = binding.state_root / "config.yaml"
    if _norm(durable_path) != _norm(expected_durable_path):
        raise InstallError(
            "rollback pack names an invalid durable bootstrap path: %s"
            % durable_path
        )
    if not durable_bootstrap.get("existed", True) and durable_path.is_file():
        current_hash = _sha256(durable_path)
        candidate_hash = durable_bootstrap.get("candidate_sha256")
        if current_hash == candidate_hash:
            durable_path.unlink()
        else:
            skipped_fresh += 1
            conflicts.append(os.fspath(durable_path))
    config_bytes = (pack / "config.yaml.bak").read_bytes()
    current_config_hash = _sha256(config_path) if config_path.is_file() else None
    prior_config_hash = manifest.get("config_sha256")
    candidate_config_hash = manifest.get("candidate_config_sha256")
    if current_config_hash not in (None, prior_config_hash, candidate_config_hash):
        skipped_fresh += 1
        conflicts.append(os.fspath(config_path))
    elif manifest.get("config_existed", True):
        _atomic_write_bytes(config_path, config_bytes)
    elif config_path.exists():
        config_path.unlink()

    receipt_state = manifest["receipt"]
    receipt_path = pathlib.Path(receipt_state.get("path", ""))
    if _norm(receipt_path) != _norm(binding.receipt_path):
        raise InstallError(
            "rollback pack names an invalid install receipt path: %s" % receipt_path
        )
    current_receipt_hash = _sha256(receipt_path) if receipt_path.is_file() else None
    prior_receipt_hash = receipt_state.get("sha256")
    candidate_receipt_hash = receipt_state.get("candidate_sha256")
    if current_receipt_hash not in (
        None,
        prior_receipt_hash,
        candidate_receipt_hash,
    ):
        skipped_fresh += 1
        conflicts.append(os.fspath(receipt_path))
    elif receipt_state.get("existed", False):
        _atomic_write_bytes(receipt_path, (pack / receipt_state["bak"]).read_bytes())
    elif receipt_path.exists():
        receipt_path.unlink()

    if conflicts:
        raise InstallError(
            "bounded recovery preserved post-crash bytes and remains incomplete: %s"
            % ", ".join(sorted(conflicts))
        )
    for directory in sorted(
        (pathlib.Path(d) for d in manifest.get("created_dirs", [])),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        try:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        except OSError:
            pass

    receipts.complete_run_journal(
        binding=binding,
        operation_id=operation_id,
        result={
            "recovered": True,
            "restored_writes": restored_writes,
            "restored_pruned": restored_pruned,
            "skipped_fresh": skipped_fresh,
            "config_sha256": _sha256_bytes(config_bytes),
            "receipt_sha256": prior_receipt_hash,
            "pack": os.fspath(pack),
        },
    )
    shutil.rmtree(pack, ignore_errors=True)
    return {"restored": True, "operation_id": operation_id}
