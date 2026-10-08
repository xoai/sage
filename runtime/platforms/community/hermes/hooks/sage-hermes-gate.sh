#!/usr/bin/env bash
# Hermes transport for the unchanged canonical Sage hook scripts.
# Ordinary payloads produce explicit allow/block outcomes. Malformed tool input
# is unverifiable, not a successful gate check. Inside the existing .sage plus
# hard_enforcement boundary it uses Hermes's existing exit-2 block contract;
# outside that boundary this adapter does not claim the task. No proof markers
# select behavior and no canonical gate decision logic is copied here.
set -uo pipefail

GATE_SCRIPT="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/$GATE_SCRIPT"
# The complete framework is installed transactionally beside profile/hooks.
RUNNER="$SCRIPT_DIR/../plugins/sage/runtime/platforms/community/hermes/gate-runner.sh"
PYTHON_EXE="${SAGE_FORMAL_GATE_PYTHON:-$(type -P python3 || true)}"
if [ -z "$PYTHON_EXE" ] || [ ! -f "$PYTHON_EXE" ]; then
  printf '%s\n' 'sage-hermes-gate: Python unavailable; workspace boundary cannot be verified' >&2
  printf '%s\n' '{"outcome":"unverifiable","error":{"type":"adapter_unavailable","message":"Python unavailable"}}'
  exit 0
fi
export PYTHONUTF8=1
if command -v cygpath >/dev/null 2>&1; then
  export TMPDIR="$(cygpath -m "${TEMP:-${TMPDIR:-/tmp}}")"
  export MSYS_NO_PATHCONV=1
fi
PAYLOAD="$(cat 2>/dev/null || true)"

# Validate the Hermes envelope before mapping path -> file_path. The master
# switch follows the existing canonical source's workspace/config convention;
# it is not a new strict-run or workflow-policy mechanism. Emit control records
# as LF bytes even when the selected Python is Windows-native.
VALIDATION="$(printf '%s' "$PAYLOAD" | "$PYTHON_EXE" -c '
import json, os, re, sys
try:
    data = json.load(sys.stdin)
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}
cwd = data.get("cwd")
root = os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR") or
                       (cwd if isinstance(cwd, str) and cwd.strip() else os.getcwd()))
envelope = data.get("file_change_envelope")
namespace = envelope.get("native_namespace") if isinstance(envelope, dict) else None
namespace_present = isinstance(envelope, dict) and "native_namespace" in envelope
namespace_valid = (isinstance(namespace, dict) and namespace.get("status") == "valid"
                   and namespace.get("backend") == "local"
                   and isinstance(namespace.get("base_dir"), str)
                   and os.path.isabs(namespace["base_dir"]))
if namespace_valid:
    # Native per-task resolution outranks the process cwd or a foreign
    # platform environment variable. This is host metadata, never tool input.
    root = os.path.abspath(namespace["base_dir"])
enabled = False
if os.path.isdir(os.path.join(root, ".sage")):
    try:
        with open(os.path.join(root, ".sage", "config.yaml"), encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = re.match(r"\s*hard_enforcement\s*:\s*(true|false)\b", line, re.I)
                if match:
                    enabled = match.group(1).lower() == "true"
                    break  # The canonical reader uses the first master-switch declaration.
    except OSError:
        pass
event = data.get("hook_event_name") or "pre_tool_call"
gate_script = sys.argv[1]
tool = data.get("tool_name")
ti = data.get("tool_input")
write = event in ("pre_tool_call", "post_tool_call") and tool in ("write_file", "patch")
mode = "ENABLED" if enabled else "DISABLED"
outputs = []
bookkeeping_preimages = {}
def invalid(kind, message):
    return {"outcome": "unverifiable", "error": {"type": kind, "message": message}}
def translated(fields, canonical=None):
    # Preserve real session identity and observer context. Only the transport
    # name/arguments are translated; callers cannot override authoritative
    # target/content/edits with fields the native tool itself ignores.
    output = dict(data)
    output.update(hook_event_name=event, tool_name=canonical or tool,
                  tool_input=fields, cwd=root)
    return output

def canonical_target(path):
    # Windows aliases refer to the same native file, but the canonical shell
    # consumers compare reserved Sage paths case-sensitively. Normalize only
    # the consumer-owned relative spelling; preserve workspace-root identity.
    absolute = os.path.abspath(os.path.join(root, path))
    try:
        relative = os.path.normcase(os.path.relpath(absolute, root)).replace("\\", "/")
    except ValueError:
        return path
    owned = (gate_script == "sage-config-gate.sh" and relative == ".sage/config.yaml") or (
        gate_script == "sage-bookkeeping-gate.sh" and
        re.fullmatch(r"\.sage/work/[^/]+/(manifest|decisions)\.md", relative))
    return os.path.join(root, *relative.split("/")) if owned else path


def file_payload(change):
    fields = dict(ti) if isinstance(ti, dict) else {}
    for key in ("path", "file_path", "content", "old_string", "new_string", "edits"):
        fields.pop(key, None)
    path = canonical_target(change["path"])
    fields.update(path=path, file_path=path)
    operation = change["operation"]
    if operation in ("write", "add"):
        fields["content"] = change["content"]
        canonical = "Write"
    elif operation == "replace":
        fields.update(old_string=ti.get("old_string", ""), new_string=change["content"])
        if "edits" in change:
            fields["edits"] = change["edits"]
        canonical = "Edit"
    elif operation == "update":
        fields["edits"] = change["edits"]
        canonical = "MultiEdit"
    else:
        # Moves/deletes declare targets but no fabricated full-file image.
        # Introduced text follows same-patch move chains for content checks.
        fields.update(old_string="", new_string=change["content"])
        canonical = "Edit"
    return translated(fields, canonical)

if write and event == "pre_tool_call" and not enabled:
    mode = "PASS"
    outputs = [{"decision": "allow", "outcome": "allow"}]
elif write and "file_change_envelope" in data:
    envelope = data["file_change_envelope"]
    if namespace_present and not namespace_valid:
        mode, outputs = "INVALID", [invalid("unverifiable_namespace", "Native local file namespace is unavailable")]
    elif not isinstance(envelope, dict) or envelope.get("schema_version") != 1:
        mode, outputs = "INVALID", [invalid("invalid_envelope", "Unsupported host file-change envelope")]
    elif envelope.get("status") == "unverifiable":
        mode = "INVALID"
        error = envelope.get("error") or {}
        outputs = [invalid(str(error.get("type") or "invalid_tool_input"),
                           str(error.get("message") or "Host could not normalize file operation"))]
    elif envelope.get("status") == "none" and envelope.get("changes") == []:
        mode, outputs = "PASS", [{"decision": "allow", "outcome": "allow"}]
    elif envelope.get("status") == "valid" and isinstance(envelope.get("changes"), list) and envelope["changes"]:
        for change in envelope["changes"]:
            if (not isinstance(change, dict) or not isinstance(change.get("path"), str)
                    or not change["path"].strip() or not isinstance(change.get("content"), str)):
                mode, outputs = "INVALID", [invalid("invalid_envelope", "Malformed host file change")]
                break
            if namespace_present:
                path = change.get("resolved_path")
                if not isinstance(path, str) or not os.path.isabs(path):
                    mode, outputs = "INVALID", [invalid("invalid_resolved_path", "Native file change lacks an absolute resolved target")]
                    break
                change = dict(change, path=path)
            operation = change.get("operation")
            if operation not in ("write", "replace", "add", "update", "delete", "move_source", "move_destination"):
                mode, outputs = "INVALID", [invalid("invalid_envelope", "Unknown host operation")]
                break
            if operation == "update" and (not isinstance(change.get("edits"), list) or
                    not all(isinstance(edit, dict) and isinstance(edit.get("old_string"), str) and
                            isinstance(edit.get("new_string"), str) for edit in change["edits"])):
                mode, outputs = "INVALID", [invalid("invalid_envelope", "Missing native hunk edits")]
                break
            change = dict(change, path=canonical_target(change["path"]))
            # The config hook accepts an exact resulting file through Write.
            # Native fuzzy edits/insertions cannot be reconstructed by its
            # exact-string Edit interface. The HOST owns the real preview;
            # this adapter neither parses patches nor makes config decisions.
            if (enabled and event == "pre_tool_call" and gate_script == "sage-config-gate.sh"
                    and operation not in ("write", "add")
                    and os.path.abspath(os.path.join(root, change["path"])) == os.path.join(root, ".sage", "config.yaml")):
                preview = change.get("preview")
                if (not isinstance(preview, dict) or preview.get("status") != "valid"
                        or not isinstance(preview.get("content"), str)):
                    mode, outputs = "INVALID", [invalid("missing_config_preview", "Native config edit needs a verified host postimage")]
                    break
                change = dict(change, operation="write", content=preview["content"])
            if (enabled and event == "pre_tool_call" and gate_script == "sage-bookkeeping-gate.sh"
                    and operation not in ("write", "add")):
                target_path = os.path.abspath(os.path.join(root, change["path"]))
                try:
                    relative = os.path.relpath(target_path, root).replace("\\", "/")
                except ValueError:
                    relative = ""  # Other Windows drive: not this cycle; keep checking later targets.
                if re.fullmatch(r"\.sage/work/[^/]+/(manifest|decisions)\.md", relative):
                    preview = change.get("preview")
                    edits = change.get("edits")
                    valid = (isinstance(preview, dict) and preview.get("status") == "valid"
                             and isinstance(preview.get("before"), str) and isinstance(preview.get("content"), str))
                    valid = valid and isinstance(edits, list) and all(
                        isinstance(edit, dict) and isinstance(edit.get("old_string"), str)
                        and bool(edit["old_string"]) and isinstance(edit.get("new_string"), str)
                        and isinstance(edit.get("replace_all", False), bool) for edit in edits)
                    if valid:
                        # Match the canonical text-file reader without inventing
                        # old/context text or copying any bookkeeping policy.
                        def lf(text):
                            return text.replace("\r\n", "\n").replace("\r", "\n")
                        before = lf(preview["before"])
                        initial = bookkeeping_preimages.setdefault(os.path.normcase(target_path), before)
                        actual = before
                        normalized_edits = []
                        for edit in edits:
                            item = dict(edit, old_string=lf(edit["old_string"]), new_string=lf(edit["new_string"]))
                            actual = actual.replace(item["old_string"], item["new_string"], -1 if item.get("replace_all") else 1)
                            normalized_edits.append(item)
                        valid = before == initial and actual == lf(preview["content"])
                    if not valid:
                        mode, outputs = "INVALID", [invalid("unrepresentable_bookkeeping_edit", "Native edit cannot be represented faithfully; use sage/runtime/tools/manifest.py or an anchored exact replacement")]
                        break
                    change = dict(change, edits=normalized_edits)
            outputs.append(file_payload(change))
    else:
        mode, outputs = "INVALID", [invalid("invalid_envelope", "Invalid host file-change state")]
elif write and tool == "patch" and isinstance(ti, dict) and ti.get("mode") == "patch":
    mode, outputs = "INVALID", [invalid("missing_host_normalization", "V4A requires native host file-change metadata")]
elif write and (not isinstance(ti, dict) or not isinstance(ti.get("path"), str) or not ti["path"].strip()):
    mode = "INVALID"
    outputs = [invalid("invalid_tool_input", "write_file/patch requires a nonempty string path")]
else:
    ti = dict(ti) if isinstance(ti, dict) else {}
    if write:
        outputs = [file_payload({"operation": "write" if tool == "write_file" else "replace",
                                 "path": ti["path"], "content": ti.get("content", "") if tool == "write_file" else ti.get("new_string", "")})]
    else:
        outputs = [translated(ti, "Bash" if tool == "terminal" else tool)]
sys.stdout.buffer.write((mode + "\n" + "\n".join(json.dumps(item) for item in outputs) + "\n").encode("utf-8"))
' "$GATE_SCRIPT" 2>/dev/null)"
VALIDATION_RC=$?
if [ "$VALIDATION_RC" -ne 0 ]; then
  printf '%s\n' 'sage-hermes-gate: could not validate workspace boundary' >&2
  printf '%s\n' '{"outcome":"unverifiable","error":{"type":"adapter_unavailable","message":"Input validation failed"}}'
  exit 0
fi
MODE="${VALIDATION%%$'\n'*}"
TRANSLATED="${VALIDATION#*$'\n'}"
if [ "$MODE" = "PASS" ]; then
  printf '%s\n' "$TRANSLATED"
  exit 0
fi
if [ "$MODE" = "INVALID" ]; then
  printf '%s\n' "$TRANSLATED"
  printf '%s\n' 'sage-hermes-gate: file operation is unverifiable' >&2
  exit 2
fi

adapter_error() {
  printf 'sage-hermes-gate: %s\n' "$1" >&2
  if [ "$MODE" = "ENABLED" ]; then
    "$PYTHON_EXE" -c 'import json,sys; print(json.dumps({"outcome":"unverifiable","error":{"type":"adapter_unavailable","message":sys.argv[1]}}))' "$1"
    exit 2
  fi
  printf '%s\n' '{"decision":"allow","outcome":"allow"}'
  exit 0
}
if [ -z "$GATE_SCRIPT" ] || [ ! -f "$TARGET" ] || [ ! -f "$RUNNER" ]; then
  adapter_error 'Required canonical hook or execution boundary is unavailable'
fi
TMP_OUT="$(mktemp "${TMPDIR:-/tmp}/sage-hermes-gate-out-XXXXXX" 2>/dev/null)" || adapter_error 'Cannot create output capture'
TMP_ERR="$(mktemp "${TMPDIR:-/tmp}/sage-hermes-gate-err-XXXXXX" 2>/dev/null)" || { rm -f "$TMP_OUT"; adapter_error 'Cannot create error capture'; }
trap 'rm -f "$TMP_OUT" "$TMP_ERR"' EXIT

# The platform runner normalizes only Python -> Bash CRLF records. Canonical
# scripts, exit codes, stderr and credential/spec decisions remain unchanged.
while IFS= read -r TARGET_PAYLOAD; do
  # Root authority is already represented in the translated payload. Do not
  # let an inherited Claude-specific variable override Hermes task resolution.
  printf '%s' "$TARGET_PAYLOAD" | CLAUDE_PROJECT_DIR="" "$BASH" "$RUNNER" "$PYTHON_EXE" "$TARGET" >>"$TMP_OUT" 2>"$TMP_ERR"
  RC=$?
  if [ "$RC" -ne 0 ] && [ "$RC" -ne 2 ]; then
    adapter_error 'Canonical hook process did not complete successfully'
  fi
  if [ "$RC" -eq 2 ]; then
    "$PYTHON_EXE" -c '
import json, sys
reason = sys.stdin.read().strip()[:4000] or "blocked by sage gate"
print(json.dumps({"decision": "block", "reason": reason, "outcome": "block"}))
' < "$TMP_ERR" || adapter_error 'Cannot serialize canonical block result'
    exit 0
  fi
  printf '\0' >> "$TMP_OUT"
done <<< "$TRANSLATED"
# Preserve optional context as part of the same single outcome document.
"$PYTHON_EXE" -c '
import json, sys
output = {"decision": "allow", "outcome": "allow"}
contexts = []
for record in sys.stdin.buffer.read().split(b"\0"):
    try:
        data = json.loads(record)
    except Exception:
        continue
    if not isinstance(data, dict):
        continue
    details = data.get("hookSpecificOutput") or {}
    context = details.get("additionalContext") if isinstance(details, dict) else None
    context = context or data.get("context")
    if context:
        contexts.append(str(context))
if contexts:
    output["context"] = "\n".join(contexts)[:8000]
print(json.dumps(output))
' < "$TMP_OUT" || adapter_error 'Cannot serialize canonical allow result'
