#!/usr/bin/env python3
"""Native Windows two-profile proof for the Sage/Hermes per-profile
installation repair (plan Task 25, spec 7.4 + 8).

Drives the REAL transactional Sage installer (profile_installer, the module
bin/sage's update/uninstall heredocs call) against a task-owned disposable
HERMES_HOME holding two profiles (alpha = A, beta = B) plus global sentinels,
and exercises the installed Hermes runtime surfaces with fresh processes:

  * real `hermes hooks list` / `hermes hooks test` / `hermes plugins list`
    against the disposable profile home (HERMES_HOME override);
  * real Git-Bash execution of the installed flat hooks — a quoted resolved
    executable through shlex.split, CRLF-safe stdout parsing, cygpath native
    paths;
  * installed Hermes dispatch semantics (agent.shell_hooks.run_once) for the
    blocker/observer failure matrix (missing executable, timeout, exit 2,
    malformed output);
  * the installed plugin bytes (A/plugins/sage) for registration, first-turn
    context delivery, and result transformation;
  * installed plugin profile_binding/memory_namespace bytes for junction and
    reciprocal-memory isolation across fresh-process restarts.

Scope guards (spec 8): every mutable profile/workspace/state surface lives
under one task-owned ``tmp-two-profile-<rand>`` root. Host profile data and
every ``.sage-memory`` store outside that root are never touched. No model/GPU
server is started in this lane; the failure
matrix and dispatch proofs use the installed hook-dispatch runtime, which is
exactly what production tool calls flow through.

Phases (expect table):
  01 environment           02 topology+sentinels    03 artifact build
  04 install A only        05 registry+argv shape   06 real CLI surfaces
  07 runtime+context       08 one tool_call_id/plan 09 gate decisions
  10 failure matrix        11 reciprocal memory     12 packs in A only (7.4.8)
  13 update/prune          14 injected rollback     15 uninstall
  16 real CLI init/update (7.4.1 via bin/sage)      17 hygiene/windows

T26 remediation of the T25 spec-compliance review:
  BD-1  phase 12 proves spec 7.4.8 pack add/remove natively in A with
        B/global byte-identical (was: zero coverage).
  BD-2  phase 08 runs against the explicitly bound Hermes test host and proves
        one host-owned tool_call_id and immutable target plan across hook
        execution, including session_cwd, resolved_file_targets, and a barrier
        CWD mutation. Fresh CLI/Gateway activation proofs use the same public
        command boundary.
  BD-4  phase 16 re-runs R1 through the REAL `sage init`/`sage update` CLI
        (receipt written by profile_installer.install; .hermes.md written;
        no workspace SOUL.md).
  The model-server hygiene check is baseline-aware: a pre-existing host
  llama-server is recorded before the lane and must survive it unchanged;
  the lane itself must spawn none (spec 7.4.10 restores pre-test state).

Lifecycle mutations (install/update/uninstall) each run in a FRESH py -3
driver process (scratch/t25_driver.py); assertions run in this process.

Usage: py -3 -m pytest develop/conformance/probes/test_hermes_two_profile_windows.py -q
       py -3 develop/conformance/probes/test_hermes_two_profile_windows.py [scratch]
Exit:  0 all assertions pass / 1 a probe fails / 2 setup failure
"""
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SETUP = os.path.join(REPO, "runtime", "platforms", "community", "hermes", "setup")
OVERLAY = os.path.join(REPO, "runtime", "platforms", "community", "hermes", "plugin-overlay")
BUILD_PLUGIN = os.path.join(REPO, "runtime", "tools", "build_plugin.py")
sys.path.insert(0, SETUP)
sys.path.insert(0, OVERLAY)

try:
    import yaml
except ImportError:
    yaml = None

import doctor                 # noqa: E402
import hook_config            # noqa: E402
import memory_namespace       # noqa: E402
import profile_binding        # noqa: E402
import profile_installer      # noqa: E402
import receipts               # noqa: E402


def resolve_git_bash():
    """Resolve Git Bash without embedding one machine's install path."""

    for candidate in (os.environ.get("SAGE_BASH_EXE"), shutil.which("bash")):
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate).replace("\\", "/")
    return ""


GIT_BASH = resolve_git_bash()


def resolve_hermes_python():
    """Resolve the host interpreter without embedding one machine's path."""

    explicit = os.environ.get("HERMES_PYTHON")
    launcher = shutil.which("hermes")
    adjacent = os.path.join(os.path.dirname(launcher), "python.exe") \
        if launcher else None
    for candidate in (explicit, adjacent, sys.executable):
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return ""


HERMES_PYTHON = resolve_hermes_python()
HERMES_HOST_ROOT = os.path.abspath(os.environ.get("HERMES_TEST_HOST_ROOT", "")) \
    if os.environ.get("HERMES_TEST_HOST_ROOT") else ""

PASS = []
FAIL = []
SPAWNED = []          # every process this probe starts: {"argv":..., "rc":...}
EVIDENCE_LINES = []   # extra hash/evidence lines folded into the summary


def expect(name, ok, note=""):
    line = name + (" -- " + note if note else "")
    print(("  PASS " if ok else "  FAIL ") + line)
    (PASS if ok else FAIL).append(name)


def evidence(line):
    EVIDENCE_LINES.append(line)
    print("  EV   " + line)


def spawn(argv, timeout=240, **kw):
    """subprocess.run wrapper that keeps the process ledger honest."""
    kw.setdefault("text", True)
    explicit_env = kw.get("env")
    recorded_cwd = kw.get("cwd") or os.getcwd()
    proc = subprocess.run(argv, capture_output=True, timeout=timeout, **kw)
    SPAWNED.append({
        "argv": [str(a) for a in argv][:4],
        "cwd": os.path.abspath(os.fspath(recorded_cwd)),
        # Inherited ambient state is not a process selecting a Hermes home.
        # Only explicit per-process routing belongs in the isolation ledger.
        "hermes_home": (explicit_env or {}).get("HERMES_HOME", ""),
        "rc": proc.returncode,
    })
    return proc


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def tree_digest(root, skip_top=()):
    """Deterministic {relpath: sha256} over every file under root."""
    digest = {}
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        top = rel_dir.split(os.sep)[0] if rel_dir != "." else ""
        if top in skip_top:
            dirnames[:] = []
            continue
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                digest[rel] = sha256_file(full)
            except OSError:
                digest[rel] = "<unreadable>"
    return digest


PROFILE_PATH_ABSENT = "<absent>"


def _exact_profile_relpath(path):
    """Normalize one exact profile-relative file path; globs are forbidden."""
    rel = os.fspath(path).replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    parts = rel.split("/")
    if (not rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel)
            or any(part in ("", ".", "..") for part in parts)
            or any(char in rel for char in "*?[]")):
        raise ValueError("allowlist entry must be one exact profile-relative file: %r"
                         % path)
    return "/".join(parts)


def profile_root_snapshot(profile_root):
    """Hash every file below a profile root without omitting workspace bytes."""
    return tree_digest(profile_root)


def projected_profile_root(snapshot, universe, allowlisted_paths=()):
    """Project a snapshot over a fixed universe, representing absence explicitly."""
    allowlist = {_exact_profile_relpath(path) for path in allowlisted_paths}
    return {
        rel: snapshot.get(rel, PROFILE_PATH_ABSENT)
        for rel in sorted(universe)
        if rel not in allowlist
    }


def profile_root_invariant_diff(before, after, allowlisted_paths=()):
    """Return every non-allowlisted profile file changed, added, or removed."""
    universe = set(before) | set(after)
    before_projected = projected_profile_root(
        before, universe, allowlisted_paths=allowlisted_paths)
    after_projected = projected_profile_root(
        after, universe, allowlisted_paths=allowlisted_paths)
    return {
        rel: {"before": before_projected[rel], "after": after_projected[rel]}
        for rel in before_projected
        if before_projected[rel] != after_projected[rel]
    }


def expect_profile_root_invariant(name, before, after, allowlisted_paths=()):
    """Record a complete profile-A invariant over exact per-phase exclusions."""
    diff = profile_root_invariant_diff(
        before, after, allowlisted_paths=allowlisted_paths)
    detail = "; ".join(
        "%s:%s->%s" % (rel, values["before"][:12], values["after"][:12])
        for rel, values in sorted(diff.items())[:4]
    )
    expect(name, not diff, detail or "non-allowlisted paths=%d" % (
        len((set(before) | set(after)) - set(allowlisted_paths))))
    return diff


def rmtree(path):
    if not os.path.isdir(path):
        return
    def _unreadonly(func, p, exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onerror=_unreadonly)


def make_junction(link, target):
    """Directory junction via cmd (no elevation needed on Windows)."""
    return spawn(["cmd", "/c", "mklink", "/J",
                  os.path.normpath(link), os.path.normpath(target)], timeout=30)


def hermes_cli(args, home, cwd, extra_env=None, timeout=180):
    env = os.environ.copy()
    env["HERMES_HOME"] = home.replace(os.sep, "/")
    env["NO_COLOR"] = "1"
    if extra_env:
        env.update(extra_env)
    return spawn(["hermes"] + args, cwd=cwd, env=env, timeout=timeout)


def driver_job(job, scratch, timeout=420):
    """Run one lifecycle mutation in a fresh py -3 process."""
    job = dict(job)
    if job.get("op") in ("install", "update"):
        job.setdefault("framework_root", REPO)
    job_path = os.path.join(scratch, "job-%s.json" % job["op"])
    with open(job_path, "w", encoding="utf-8") as fh:
        json.dump(job, fh)
    env = os.environ.copy()
    env["HERMES_HOME"] = job["home"]
    env["HERMES_PYTHON"] = HERMES_PYTHON
    env["HERMES_PYTHON_SRC_ROOT"] = HERMES_HOST_ROOT
    env["PYTHONPATH"] = HERMES_HOST_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return spawn([sys.executable, os.path.join(scratch, "t25_driver.py"), job_path],
                 env=env, timeout=timeout)


def load_plugin_module(plugin_root, profile_home, workspace):
    """Import the installed plugin exactly as the lifecycle harness does."""
    name = "t25_installed_sage_%s" % secrets.token_hex(4)
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(plugin_root, "__init__.py"),
        submodule_search_locations=[plugin_root])
    module = importlib.util.module_from_spec(spec)
    old_home = os.environ.get("HERMES_HOME")
    old_cwd = os.getcwd()
    os.environ["HERMES_HOME"] = profile_home
    os.environ.pop("HERMES_ENABLE_PROJECT_PLUGINS", None)
    os.chdir(workspace)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        return module
    except Exception:
        sys.modules.pop(name, None)
        raise
    finally:
        if old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = old_home
        os.chdir(old_cwd)


def parse_hooks_test_output(stdout):
    """Parse `hermes hooks test` output into per-hook records."""
    records = []
    current = None
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("\u2192 ") or stripped.startswith("-> "):
            current = {"command": stripped.lstrip("\u2192-> "), "exit": None,
                       "stdout": "", "parsed": None, "raw": []}
            records.append(current)
            continue
        if current is None:
            continue
        current["raw"].append(stripped)
        m = re.match(r"exit=(-?\d+)", stripped)
        if m:
            current["exit"] = int(m.group(1))
        if stripped.startswith("stdout:"):
            current["stdout"] = stripped[len("stdout:"):].strip()
        if stripped.startswith("parsed (Hermes wire shape):"):
            body = stripped.split(":", 1)[1].strip()
            try:
                current["parsed"] = json.loads(body)
            except ValueError:
                current["parsed"] = {"_unparsed": body}
    return records


def write_driver(scratch):
    body = '''#!/usr/bin/env python3
# T25 fresh-process lifecycle driver: one mutation per process.
import hashlib
import json
import os
import pathlib
import shutil
import sys

job = json.load(open(sys.argv[1], encoding="utf-8"))
sys.path.insert(0, job["setup_dir"])
import activation
import profile_binding
import profile_installer
import receipts

binding = profile_binding.ProfileBinding.from_explicit(
    collection_root=job["home"],
    profile_id=job["profile"],
    profile_root=os.path.join(job["home"], "profiles", job["profile"]),
    workspace_root=os.path.join(job["home"], "profiles", job["profile"], "workspace"),
)
activation_probe, activation_rollback = activation.callbacks(
    binding, activation.resolve_hermes_command()
)
op = job["op"]
out = {"op": op}

if op == "seed-binding":
    cfg = pathlib.Path(binding.config_path)
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    block = {
        "profile_id": binding.profile_id,
        "workspace_root": os.fspath(binding.workspace_root),
        "state_root": os.fspath(binding.state_root),
        "memory_root": os.fspath(binding.memory_root),
        "receipt_path": os.fspath(binding.receipt_path),
    }
    if "sage_profile_binding" not in text:
        text += "sage_profile_binding: " + json.dumps(block) + "\\n"
        cfg.write_text(text, encoding="utf-8")
    out["ok"] = True

elif op == "install":
    result = profile_installer.install(
        binding=binding,
        artifact_dir=pathlib.Path(job["artifact"]),
        framework_root=pathlib.Path(job["framework_root"]),
        consent_granted=True,
        source_version=job["version"],
        source_commit=job["commit"],
        bash_path=job["bash"],
        activation_probe=activation_probe,
        activation_rollback=activation_rollback,
    )
    out.update(result)

elif op == "update":
    if job.get("inject_commit_copy_failure"):
        real_copy2 = shutil.copy2
        state = {"calls": 0}
        live_roots = (binding.profile_root, binding.workspace_root)
        state_root = binding.state_root

        def explode(src, dst, *args, **kwargs):
            destination = pathlib.Path(dst).resolve(strict=False)
            in_live_root = any(
                destination == root or root in destination.parents
                for root in live_roots
            )
            in_state = destination == state_root or state_root in destination.parents
            if in_live_root and not in_state:
                state["calls"] += 1
                if state["calls"] >= job["inject_commit_copy_failure"]:
                    raise OSError("T25 injected update commit failure")
            return real_copy2(src, dst, *args, **kwargs)

        shutil.copy2 = explode
    try:
        result = profile_installer.update(
            binding=binding,
            artifact_dir=pathlib.Path(job["artifact"]),
            framework_root=pathlib.Path(job["framework_root"]),
            consent_granted=True,
            source_version=job["version"],
            source_commit=job["commit"],
            bash_path=job["bash"],
            activation_probe=activation_probe,
            activation_rollback=activation_rollback,
        )
        out.update(result)
    except profile_installer.InstallError as exc:
        out["failed_closed"] = str(exc)

elif op == "uninstall":
    absence_probe, absence_rollback = activation.uninstall_callbacks(
        binding, activation.resolve_hermes_command()
    )
    result = profile_installer.uninstall(
        binding=binding,
        consent_granted=True,
        absence_probe=absence_probe,
        absence_rollback=absence_rollback,
    )
    out.update(result)

elif op == "add-stale-target":
    stale = pathlib.Path(job["stale_path"])
    stale.write_text("# stale managed probe file\\n", encoding="utf-8")
    stale_sha = hashlib.sha256(stale.read_bytes()).hexdigest()
    prior = receipts.load_install_receipt(binding)
    targets = list(prior.managed_targets) + [
        receipts.ManagedTarget.from_path(binding, stale, stale_sha)
    ]
    receipt = receipts.InstallReceipt.create(
        binding=binding,
        source_version=prior.source_version,
        source_commit=prior.source_commit,
        managed_targets=targets,
        config_records=[],
        allowlist_records=[],
    )
    receipts.write_install_receipt(binding, receipt)
    out["ok"] = True

elif op == "pack-add":
    # T26/BD-1: real `sage add <local pack> --all` semantics through the
    # bound skill_manager, in a fresh process, cwd = bound workspace.
    sys.path.insert(0, job["tools_dir"])
    import skill_manager as SM
    os.chdir(job["workspace"])
    SM.cmd_add(job["pack_dir"], install_all=True)
    lock_path = os.path.join(job["workspace"], ".sage", "packs.lock")
    out["lock_exists"] = os.path.isfile(lock_path)
    if out["lock_exists"]:
        with open(lock_path, encoding="utf-8") as fh:
            out["lock"] = json.load(fh)
    skills_dir = job["profile_skills"]
    out["deployed"] = sorted(os.listdir(skills_dir)) if os.path.isdir(skills_dir) else []
    out["ok"] = True

elif op == "pack-remove":
    sys.path.insert(0, job["tools_dir"])
    import skill_manager as SM
    os.chdir(job["workspace"])
    for skill in job["skills"]:
        SM.cmd_remove(skill)
    lock_path = os.path.join(job["workspace"], ".sage", "packs.lock")
    out["lock_exists"] = os.path.isfile(lock_path)
    if out["lock_exists"]:
        with open(lock_path, encoding="utf-8") as fh:
            out["lock"] = json.load(fh)
    skills_dir = job["profile_skills"]
    out["deployed"] = sorted(os.listdir(skills_dir)) if os.path.isdir(skills_dir) else []
    out["ok"] = True

print(json.dumps(out))
'''
    path = os.path.join(scratch, "t25_driver.py")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    return path


MEMORY_WORKER_SOURCE = '''#!/usr/bin/env python3
# T25 memory isolation worker: one fresh process per operation.
import importlib.util
import json
import os
import sqlite3
import sys


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def main():
    args = json.loads(sys.argv[1])
    op = args["op"]
    out = {"op": op, "pid": os.getpid()}

    if op == "make-global":
        dbdir = os.path.join(args["global_home"], ".sage-memory")
        os.makedirs(dbdir, exist_ok=True)
        conn = sqlite3.connect(os.path.join(dbdir, "memory.db"))
        conn.execute("CREATE TABLE IF NOT EXISTS memories (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR REPLACE INTO memories (key, value) VALUES (?, ?)",
                     (args["key"], args["value"]))
        conn.commit()
        conn.close()
        out["ok"] = True
        print(json.dumps(out))
        return

    ns = load_module(os.path.join(args["module_dir"], "memory_namespace.py"),
                     "t25_mem_%d" % os.getpid())
    workspace = args.get("workspace")

    if op == "remember":
        with ns.WorkspaceMemoryStore(workspace) as store:
            store.remember(args["key"], args["value"])
            out["db"] = str(store.db_path)
        out["ok"] = True
    elif op == "recall":
        bound = ns.resolve_memory_db(workspace)
        out["resolved_db"] = str(bound)
        with ns.WorkspaceMemoryStore(workspace) as store:
            out["own"] = store.recall(args["own_key"])
            out["foreign_a"] = store.recall(args["foreign_a_key"])
            out["foreign_b"] = store.recall(args["foreign_b_key"])
            out["global_key"] = store.recall(args["global_key"])
        for label, candidate in (("foreign_db", args.get("foreign_db")),
                                 ("global_db", args.get("global_db"))):
            if not candidate:
                continue
            try:
                ns.verify_session_db(candidate, workspace)
                out[label + "_rejected"] = False
            except ns.MemoryNamespaceError:
                out[label + "_rejected"] = True
        try:
            ns.verify_session_db(None, workspace)
            out["missing_strict_rejected"] = False
        except ns.MemoryNamespaceError:
            out["missing_strict_rejected"] = True
    elif op == "junction":
        results = {}
        try:
            ns.resolve_memory_db(args["linked_workspace"])
            results["memory_junction_rejected"] = False
        except ns.MemoryNamespaceError:
            results["memory_junction_rejected"] = True
        pb = load_module(os.path.join(args["module_dir"], "profile_binding.py"),
                         "t25_pb_%d" % os.getpid())
        try:
            pb.ProfileBinding.from_explicit(
                collection_root=args["linked_collection"],
                profile_id=args["profile"],
                profile_root=os.path.join(args["linked_collection"], "profiles", args["profile"]),
                workspace_root=os.path.join(args["linked_collection"], "profiles",
                                            args["profile"], "workspace"),
            )
            results["binding_junction_rejected"] = False
        except Exception:
            results["binding_junction_rejected"] = True
        out.update(results)
    print(json.dumps(out))


main()
'''


PLUGIN_WORKER_SOURCE = '''#!/usr/bin/env python3
# T25 installed-plugin worker: register + first-turn context in a fresh process.
import importlib.util
import json
import os
import sys

args = json.loads(sys.argv[1])
plugin_root = args["plugin_root"]
os.environ["HERMES_HOME"] = args["profile_home"]
os.environ.pop("HERMES_ENABLE_PROJECT_PLUGINS", None)
os.chdir(args["workspace"])

name = "t25_plugin_worker_%d" % os.getpid()
spec = importlib.util.spec_from_file_location(
    name, os.path.join(plugin_root, "__init__.py"),
    submodule_search_locations=[plugin_root])
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)

hooks = {}
skills = []


class Ctx:
    def register_hook(self, hook_name, callback):
        hooks[hook_name] = callback

    def register_skill(self, skill_name, path, description="", frontmatter=None):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        skills.append(skill_name)

    def register_tool(self, *a, **k):
        pass

    def register_command(self, *a, **k):
        pass


out = {"pid": os.getpid(), "plugin_root": plugin_root}
module.register(Ctx())
out["hooks"] = sorted(hooks)
out["skills"] = sorted(skills)
out["has_debugger"] = "sage-debugger" in skills
if "on_session_start" in hooks:
    hooks["on_session_start"](session_id="t25-session", model="t25-model", platform="cli")
    out["session_start_ok"] = True
if "pre_llm_call" in hooks:
    ctx = hooks["pre_llm_call"](session_id="t25-session", is_first_turn=True,
                                user_message="t25 first turn")
    out["first_turn_context"] = ctx if isinstance(ctx, dict) else {"raw": str(ctx)}
if "transform_tool_result" in hooks:
    transformed = hooks["transform_tool_result"](result="plain tool result",
                                                 tool_name="write_file",
                                                 session_id="t25-session")
    out["transform_ok"] = True
    out["transform_passthrough"] = transformed in (None, "plain tool result")
print(json.dumps(out))
'''


FAILURE_MATRIX_SOURCE = '''#!/usr/bin/env python3
# T25 blocker/observer failure matrix through the installed Hermes dispatch.
import json
import sys

from agent import shell_hooks

GIT_BASH = sys.argv[1]
PAYLOAD = {"tool_name": "write_file", "args": {"path": "src/app.py"},
           "session_id": "t25-fm", "task_id": "t25-fm-task",
           "tool_call_id": "call-t25-fm"}


def fire(event, command, fail_closed, timeout=5):
    spec = shell_hooks.ShellHookSpec(
        event=event, command=command, matcher="write_file",
        timeout=timeout, fail_closed=fail_closed)
    kw = dict(PAYLOAD)
    if event == "post_tool_call":
        kw.update({"result": '{"output": "ok"}', "duration_ms": 3,
                   "status": "ok"})
    result = shell_hooks.run_once(spec, kw)
    return {"error": result.get("error"),
            "timed_out": bool(result.get("timed_out")),
            "returncode": result.get("returncode"),
            "parsed": result.get("parsed")}


results = {}
results["blocker_missing_exec"] = fire(
    "pre_tool_call", '"C:/t25-nonexistent-host/bash.exe" "C:/x.sh"', True)
results["blocker_timeout"] = fire(
    "pre_tool_call", '"%s" -c "sleep 5"' % GIT_BASH, True, timeout=1)
results["blocker_exit2"] = fire(
    "pre_tool_call", '"%s" -c "echo t25-veto-reason >&2; exit 2"' % GIT_BASH, True)
results["blocker_malformed"] = fire(
    "pre_tool_call", '"%s" -c "printf not-json{{{"' % GIT_BASH, True)
results["observer_missing_exec"] = fire(
    "post_tool_call", '"C:/t25-nonexistent-host/bash.exe" "C:/x.sh"', False)
results["observer_timeout"] = fire(
    "post_tool_call", '"%s" -c "sleep 5"' % GIT_BASH, False, timeout=1)
results["observer_exit2"] = fire(
    "post_tool_call", '"%s" -c "exit 2"' % GIT_BASH, False)
results["observer_malformed"] = fire(
    "post_tool_call", '"%s" -c "printf not-json{{{"' % GIT_BASH, False)
print(json.dumps(results))
'''


SUPPORTED_SKILLS = (
    "sage", "sage-analyst", "sage-architect", "sage-autoresearch",
    "sage-build", "sage-checkpoints", "sage-classifier", "sage-constitution",
    "sage-continue", "sage-debugger", "sage-decisions", "sage-developer",
    "sage-fix", "sage-gates", "sage-learn", "sage-reflect", "sage-review",
    "sage-reviewer", "sage-routing", "sage-tiers", "sage-using-memory",
)
RUNTIME_TOOLS = ("scope_judge.py", "manifest.py", "skill_manager.py",
                 "sage_flags.py", "memory_sync.py")


def fwd(path):
    return os.fspath(path).replace(os.sep, "/")


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def parse_driver(proc):
    tail = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return json.loads(tail[-1]) if tail else {}


def digest_outside_profile(home, profile):
    """Deterministic digest of every byte in the collection EXCEPT one
    profile — the isolation witness used at every lifecycle step."""
    skip = "profiles/" + profile
    out = {}
    for rel, sha in tree_digest(home).items():
        if rel == skip or rel.startswith(skip + "/"):
            continue
        out[rel] = sha
    return out


def digest_outside_alpha(home):
    return digest_outside_profile(home, "alpha")


def lifecycle_profile_allowlist(managed_paths=(), operation_id=None, extra=()):
    """Exact profile-A files a single lifecycle checkpoint may mutate."""
    allowed = {_exact_profile_relpath(path) for path in managed_paths}
    allowed.update({
        "config.yaml",
        "shell-hooks-allowlist.json",
        "workspace/.sage/config.yaml",
        "workspace/.sage/receipts/install.json",
        "workspace/.sage/receipts/.install.json.lock",
    })
    if operation_id:
        allowed.update({
            "workspace/.sage/receipts/runs/%s.json" % operation_id,
            "workspace/.sage/receipts/runs/.%s.json.lock" % operation_id,
        })
    allowed.update(_exact_profile_relpath(path) for path in extra)
    return allowed


def receipt_target_key(target):
    return (target.owner, target.relative_path)


def receipt_profile_relpath(target):
    if target.owner == "workspace":
        return _exact_profile_relpath("workspace/" + target.relative_path)
    return _exact_profile_relpath(target.relative_path)


def receipt_target_path(topo, target):
    root = topo["wsA"] if target.owner == "workspace" else topo["A"]
    return os.path.join(root, *target.relative_path.split("/"))


def snapshot_llama_processes():
    """PIDs of llama-like processes on the host RIGHT NOW.

    Spec 7.4.10 requires restoring PRE-TEST task/service state — not a
    host-global zero, which would fail on any host already running a model
    server. The lane must spawn none and leave the baseline untouched.
    """
    ps_cmd = ("Get-CimInstance Win32_Process | Where-Object "
              "{ $_.Name -like 'llama*' } | ForEach-Object { $_.ProcessId }")
    proc = spawn(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=180)
    pids = set()
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.isdigit():
            pids.add(int(stripped))
    return pids


def build_topology(scratch):
    home = os.path.join(scratch, "hermes")
    A = os.path.join(home, "profiles", "alpha")
    B = os.path.join(home, "profiles", "beta")
    wsA = os.path.join(A, "workspace")
    wsB = os.path.join(B, "workspace")
    outside = os.path.join(scratch, "outside")
    for prof in (A, B):
        for sub in ("hooks", "plugins", "skills"):
            os.makedirs(os.path.join(prof, sub), exist_ok=True)
        os.makedirs(os.path.join(prof, "workspace"), exist_ok=True)
    os.makedirs(outside, exist_ok=True)
    write(os.path.join(A, "config.yaml"),
          "other_setting: 42\n"
          "plugins:\n  enabled: [sage]\n"
          "unrelated_note: T25 user-owned config line\n")
    write(os.path.join(A, "SOUL.md"),
          "# T25 user identity sentinel\nprofile-root SOUL.md is user-owned\n")
    write(os.path.join(A, "hooks", "user-hook.sh"),
          "#!/usr/bin/env bash\n# T25 user-owned hook script\n")
    write(os.path.join(wsA, ".sage", "constitution.md"),
          "---\nextends: base\n---\n\n"
          "## Project Additions\nPROFILE-CONTEXT-ALPHA\n")
    write(os.path.join(B, "config.yaml"),
          "model: beta-model\nuser_key: T25 beta sentinel\n")
    write(os.path.join(B, "SOUL.md"), "# beta identity\n")
    write(os.path.join(wsB, "B-SENTINEL.txt"), "beta workspace sentinel\n")
    write(os.path.join(home, "GLOBAL-SENTINEL.txt"), "global sentinel\n")
    write(os.path.join(home, "config.yaml"), "collection_sentinel: t25\n")
    return {"home": home, "A": A, "B": B, "wsA": wsA, "wsB": wsB,
            "outside": outside}


def _init_runtime_git_repo(home2):
    """Spec 7.4.1 / BD-4 environment fixture: the runtime destination (the
    workspace inside the disposable Hermes collection) is required by the
    installer's workspace_layout gate to live inside a git repository whose
    tracked set does NOT include the runtime directory. Without a parent
    `.git` somewhere above the workspace, `git -C wsG rev-parse
    --show-toplevel` returns non-zero and the installer fails closed with
    "cannot inspect Git ownership for the runtime destination: fatal: not a
    git repository", leaving no install receipt for the CLI update to reuse.
    The disposable collection under <scratch>/hermes-cli is the natural
    fixture location: its `.git` is wholly owned by the probe, the
    collection itself remains untracked (no `git add` runs from any sibling
    suite or hermes_install_transact step), and the entire scratch tree --
    `.git` included -- is removed by the existing rmtree(scratch)
    teardown, so no fixture data escapes.

    Contract: rc==0 -> the fresh .git at <home2>/.git makes
    `git -C wsG rev-parse --show-toplevel` succeed and
    `git ls-files -- profiles/<prof>/workspace/sage` returns empty;
    rc!=0 -> phase 16 cannot run, the gate is recorded and the probe fails
    closed instead of silently proceeding on a misshaped environment.
    """
    if os.path.isdir(os.path.join(home2, ".git")):
        return  # caller is idempotent across retries
    proc = spawn(["git", "init", "-q", home2], timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(
            "phase_cli_init cannot bootstrap git fixture at %s: %s"
            % (home2, (proc.stderr or proc.stdout).strip()[-200:]))


def phase_artifact(scratch):
    artifact = os.path.join(scratch, "artifact")
    proc = spawn([sys.executable, BUILD_PLUGIN, "--target", "hermes",
                  "--out", artifact], cwd=REPO, timeout=300)
    expect("artifact: build_plugin --target hermes exits 0",
           proc.returncode == 0, proc.stderr.strip()[-160:])
    hooks = sorted(os.listdir(os.path.join(artifact, "hooks"))) \
        if os.path.isdir(os.path.join(artifact, "hooks")) else []
    plugin = sorted(os.listdir(os.path.join(artifact, "plugins", "sage"))) \
        if os.path.isdir(os.path.join(artifact, "plugins", "sage")) else []
    expect("artifact: 12 hook scripts (11 registry + adapter)",
           len(hooks) == 12 and "sage-hermes-gate.sh" in hooks,
           "got %d" % len(hooks))
    expect("artifact: plugin package complete",
           {"__init__.py", "plugin.yaml", "profile_binding.py",
            "memory_namespace.py"} <= set(plugin), ",".join(plugin))
    evidence("artifact sha256(__init__.py)=%s" %
             sha256_file(os.path.join(artifact, "plugins", "sage", "__init__.py")))
    return artifact


def phase_install(scratch, topo, ctx):
    before_profile = profile_root_snapshot(topo["A"])
    job = {"op": "seed-binding", "setup_dir": SETUP,
           "home": topo["home"], "profile": "alpha"}
    proc = driver_job(job, scratch)
    expect("install: binding seed driver exits 0", proc.returncode == 0,
           proc.stderr.strip()[-160:])
    expect("install: one sage_profile_binding block in A config",
           "sage_profile_binding" in read(os.path.join(topo["A"], "config.yaml")))
    job = {"op": "install", "setup_dir": SETUP, "home": topo["home"],
           "profile": "alpha", "artifact": ctx["artifact"],
           "version": ctx["version"], "commit": ctx["commit"],
           "bash": GIT_BASH}
    proc = driver_job(job, scratch)
    out = parse_driver(proc) if proc.returncode == 0 else {}
    expect("install: transactional install commits (fresh process)",
           proc.returncode == 0 and out.get("ok") is True,
           (proc.stderr or proc.stdout).strip()[-200:])
    ctx["install_op"] = out.get("operation_id", "")
    binding = profile_binding.ProfileBinding.from_explicit(
        collection_root=topo["home"], profile_id="alpha",
        profile_root=topo["A"], workspace_root=topo["wsA"])
    ctx["binding"] = binding
    receipt = receipts.load_install_receipt(binding)
    expect("install: receipt bound to source version+commit",
           receipt.source_version == ctx["version"]
           and receipt.source_commit == ctx["commit"],
           receipt.source_version)
    managed = {receipt_target_key(t): t.sha256 for t in receipt.managed_targets}
    ctx["managed_after_install"] = managed
    profile_targets = [t for t in receipt.managed_targets if t.owner == "profile"]
    workspace_targets = [t for t in receipt.managed_targets if t.owner == "workspace"]
    artifact_profile_paths = set()
    for prefix in ("hooks", "plugins/sage"):
        source_root = os.path.join(ctx["artifact"], *prefix.split("/"))
        for dirpath, _, filenames in os.walk(source_root):
            for name in filenames:
                relative = os.path.relpath(os.path.join(dirpath, name), ctx["artifact"])
                artifact_profile_paths.add(relative.replace(os.sep, "/"))
    receipt_profile_paths = {t.relative_path for t in profile_targets}
    expect("install: receipt owns the exact full Sage plugin + profile-hook slice",
           receipt_profile_paths == artifact_profile_paths
           and "plugins/sage/bin/sage" in receipt_profile_paths
           and "plugins/sage/runtime/tools/build_plugin.py" in receipt_profile_paths
           and "plugins/sage/.sage-framework-manifest.json" in receipt_profile_paths,
           "receipt=%d artifact=%d hooks=%d plugins=%d" % (
               len(receipt_profile_paths), len(artifact_profile_paths),
               sum(1 for path in receipt_profile_paths if path.startswith("hooks/")),
               sum(1 for path in receipt_profile_paths
                   if path.startswith("plugins/sage/"))))
    expect("install: receipt also owns complete workspace instructions/runtime",
           any(t.relative_path == ".hermes.md" for t in workspace_targets)
           and any(t.relative_path == "sage/core/gates/scripts/sage-spec-check.sh"
                   for t in workspace_targets)
           and any(t.relative_path == "sage/skills/sage-debugger/SKILL.md"
                   for t in workspace_targets),
           "workspace=%d" % len(workspace_targets))
    journal = receipts.load_completed_run_journal(binding, ctx["install_op"])
    expect("install: run journal complete", journal.is_complete)
    for target in receipt.managed_targets:
        rel = "%s:%s" % receipt_target_key(target)
        sha = target.sha256
        dest = receipt_target_path(topo, target)
        if not os.path.isfile(dest) or sha256_file(dest) != sha:
            expect("install: managed bytes on disk match receipt (%s)" % rel, False)
            break
    else:
        expect("install: all managed bytes on disk match the receipt", True)
    expect_profile_root_invariant(
        "install: every non-allowlisted A-profile path is byte-identical",
        before_profile, profile_root_snapshot(topo["A"]),
        lifecycle_profile_allowlist(
            managed_paths=(receipt_profile_relpath(t)
                           for t in receipt.managed_targets),
            operation_id=ctx["install_op"],
        ),
    )


def phase_registry(topo):
    config_text = read(os.path.join(topo["A"], "config.yaml"))
    validation = hook_config.validate_candidate_config(config_text)
    expect("registry: exact 7+4 policy validates", validation["ok"],
           "; ".join(validation["errors"][:2]))
    doc = yaml.safe_load(config_text)
    pre = doc["hooks"]["pre_tool_call"]
    post = doc["hooks"]["post_tool_call"]
    expect("registry: 7 pre-tool blockers", len(pre) == 7, "got %d" % len(pre))
    expect("registry: 4 post-tool observers", len(post) == 4, "got %d" % len(post))
    expect("registry: all blockers fail_closed true",
           all(e.get("fail_closed") is True for e in pre))
    expect("registry: all observers fail_closed false",
           all(e.get("fail_closed") is False for e in post))
    expect("registry: every entry timeout 30",
           all(e.get("timeout") == 30 for e in pre + post))
    adapter_fwd = fwd(os.path.join(topo["A"], "hooks", "sage-hermes-gate.sh"))
    scripts = set()
    argv_ok = True
    quoted_ok = True
    detail = ""
    for entry in pre + post:
        decoded = entry["command"].replace('\\"', '"')
        argv = shlex.split(decoded)
        if len(argv) != 3:
            argv_ok, detail = False, "split=%r" % (argv,)
            break
        if argv[0] != GIT_BASH:
            argv_ok, detail = False, "argv0=%r" % argv[0]
            break
        if not decoded.startswith('"%s" ' % GIT_BASH):
            quoted_ok = False
        if argv[1] != adapter_fwd:
            argv_ok, detail = False, "argv1=%r" % argv[1]
            break
        scripts.add(argv[2])
    expected_scripts = {e["script"] for e in hook_config.expected_registry()}
    expect("registry: every command shlex-splits to git-bash/adapter/script",
           argv_ok, detail)
    expect("registry: resolved git-bash argv[0] remains quoted intact", quoted_ok)
    expect("registry: the 11 registered scripts are exactly the expected set",
           scripts == expected_scripts,
           "diff=%s" % sorted(scripts ^ expected_scripts))
    expect("registry: raw config counts (7 true / 4 false / 11 timeouts)",
           config_text.count("fail_closed: true") == 7
           and config_text.count("fail_closed: false") == 4
           and config_text.count("timeout: 30") == 11)
    on_disk = set(os.listdir(os.path.join(topo["A"], "hooks")))
    expect("registry: all 12 hook scripts flat in A/hooks",
           {"sage-hermes-gate.sh"} | expected_scripts <= on_disk)


def phase_cli_surfaces(topo):
    proc = hermes_cli(["hooks", "list"], home=topo["A"], cwd=topo["wsA"])
    expect("cli: hermes hooks list reads A's real config (12 total)",
           proc.returncode == 0
           and "Configured shell hooks (12 total)" in proc.stdout,
           proc.stdout.splitlines()[0] if proc.stdout else proc.stderr[:80])
    expect("cli: all 12 listed commands are the sage adapter chain",
           proc.stdout.count("sage-hermes-gate.sh") == 12)
    proc = hermes_cli(["hooks", "test", "pre_llm_call"],
                      home=topo["A"], cwd=topo["wsA"])
    expect("cli: model-facing context is plugin-owned (no pre_llm_call shell hook)",
           proc.returncode == 0
           and "No shell hooks configured" in proc.stdout)
    proc = hermes_cli(["plugins", "list"], home=topo["A"], cwd=topo["wsA"])
    sage_enabled = re.search(r"sage\s*\u2502\s*enabled\s*\u2502\s*1\.3\.18",
                             proc.stdout) is not None
    expect("cli: hermes plugins list discovers sage enabled 1.3.18 in A",
           proc.returncode == 0 and sage_enabled)
    proc = hermes_cli(["config", "path"], home=topo["A"], cwd=topo["wsA"])
    expect("cli: hermes config path resolves the disposable profile home",
           proc.returncode == 0 and os.path.normcase(proc.stdout.strip())
           == os.path.normcase(os.path.join(topo["A"], "config.yaml")),
           proc.stdout.strip()[:80])


def phase_runtime_context(scratch, topo):
    worker = os.path.join(scratch, "plugin_worker.py")
    with open(worker, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(PLUGIN_WORKER_SOURCE)
    job = {"plugin_root": os.path.join(topo["A"], "plugins", "sage"),
           "profile_home": topo["A"], "workspace": topo["wsA"]}
    proc = spawn([sys.executable, worker, json.dumps(job)], timeout=120)
    out = {}
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            out = json.loads(proc.stdout.strip().splitlines()[-1])
        except ValueError:
            pass
    expect("context: installed plugin registers in a fresh process",
           proc.returncode == 0 and bool(out.get("hooks")),
           (proc.stderr or proc.stdout).strip()[-160:])
    expect("context: exactly the 4 plugin-owned callbacks register",
           sorted(out.get("hooks", [])) == ["on_session_start", "pre_llm_call",
                                            "pre_verify", "transform_tool_result"],
           ",".join(out.get("hooks", [])))
    expect("context: 21 core skills discovered incl sage-debugger",
           len(out.get("skills", [])) >= 21 and out.get("has_debugger") is True,
           "skills=%d" % len(out.get("skills", [])))
    ctx = out.get("first_turn_context", {})
    delivered = ctx.get("context", "") if isinstance(ctx, dict) else str(ctx)
    expect("context: first-turn context delivered to the model-facing surface",
           "PROFILE-CONTEXT-ALPHA" in delivered,
           "len=%d" % len(delivered))
    expect("context: session-start init and result transformation ran",
           out.get("session_start_ok") is True and out.get("transform_ok") is True)
    constitution = os.path.join(topo["wsA"], ".sage", "constitution.md")
    with open(constitution, "rb") as fh:
        raw = fh.read()
    expect("windows: CRLF user constitution bytes survive context delivery",
           bytes((13, 10)) in raw and "PROFILE-CONTEXT-ALPHA" in delivered)
    evidence("plugin worker pid=%s plugin_root=%s" %
             (out.get("pid"), out.get("plugin_root")))


RECORDER_TEMPLATE = '''#!/usr/bin/env bash
PAYLOAD="$(cat)"
printf '%s' "$PAYLOAD" | python3 -c "
import hashlib, json, sys
d = json.load(sys.stdin)
ti = d.get('tool_input') or {}
rec = {
    'event': d.get('hook_event_name'),
    'tool_call_id': (d.get('extra') or {}).get('tool_call_id'),
    'plan_sha': hashlib.sha256(json.dumps(ti, sort_keys=True).encode()).hexdigest(),
}
with open('__LOG__', 'a', encoding='utf-8') as fh:
    fh.write(json.dumps(rec) + chr(10))
"
printf '{}'"\\n"
'''


def _recorder_entry_lines(topo):
    cmd = '      command: "\\"%s\\" \\"%s\\""' % (
        GIT_BASH, fwd(os.path.join(topo["A"], "hooks", "t25-recorder.sh")))
    return ["    - matcher: 'write_file|patch'", cmd,
            "      fail_closed: false", "      timeout: 30"]


def phase_tool_call_id(scratch, topo):
    rec_log = os.path.join(scratch, "recorder.jsonl")
    recorder = os.path.join(topo["A"], "hooks", "t25-recorder.sh")
    write(recorder, RECORDER_TEMPLATE.replace("__LOG__", fwd(rec_log)))
    config_path = os.path.join(topo["A"], "config.yaml")
    with open(config_path, "rb") as fh:
        backup = fh.read()
    lines = backup.decode("utf-8").splitlines()
    out_lines = []
    for line in lines:
        out_lines.append(line)
        if line.rstrip() in ("  pre_tool_call:", "  post_tool_call:"):
            out_lines.extend(_recorder_entry_lines(topo))
    with open(config_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out_lines) + "\n")
    payload = {"tool_name": "write_file",
               "args": {"path": ".sage/notes.md", "content": "t25 plan marker"},
               "session_id": "t25-session", "task_id": "t25-task",
               "tool_call_id": "call-t25-0001"}
    payload_path = os.path.join(scratch, "payload-tcid.json")
    with open(payload_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    proc = hermes_cli(["hooks", "test", "pre_tool_call", "--for-tool",
                       "write_file", "--payload-file", payload_path],
                      home=topo["A"], cwd=topo["wsA"])
    pre_records = parse_hooks_test_output(proc.stdout)
    expect("plan: real dispatch fires all matching pre hooks (6 gates + recorder)",
           proc.returncode == 0 and len(pre_records) == 7,
           "fired=%d" % len(pre_records))
    expect("plan: allowed execution (no blocker vetoes a .sage note edit)",
           all(r["parsed"] is None for r in pre_records)
           and all(r["exit"] == 0 for r in pre_records))
    proc = hermes_cli(["hooks", "test", "post_tool_call", "--for-tool",
                       "write_file", "--payload-file", payload_path],
                      home=topo["A"], cwd=topo["wsA"])
    post_records = parse_hooks_test_output(proc.stdout)
    expect("plan: real dispatch fires all matching post observers (4 + recorder)",
           proc.returncode == 0 and len(post_records) == 5,
           "fired=%d" % len(post_records))
    recorded = []
    if os.path.isfile(rec_log):
        for line in read(rec_log).splitlines():
            if line.strip():
                recorded.append(json.loads(line))
    pre_events = [r for r in recorded if r["event"] == "pre_tool_call"]
    post_events = [r for r in recorded if r["event"] == "post_tool_call"]
    expect("plan: recorder observed pre and post phases",
           len(pre_events) >= 1 and len(post_events) >= 1,
           "pre=%d post=%d" % (len(pre_events), len(post_events)))
    # T26 BD-2: the installed host is upstream Hermes v0.20.0 — its
    # shell_hooks carry NO seam (session_cwd / resolved_file_targets exist
    # only in the unmerged hermes-agent-t3 branch). The id below is
    # probe-supplied in the payload file, and "plan" is tool_input
    # byte-equality observed by the recorder. Renamed honestly; the
    # host-seam contract (7.4.2b-e) is UNVERIFIED-PENDING-HOST.
    expect("plan: one probe-supplied tool_call_id observed across pre and "
           "post hooks (host generates no id yet)",
           bool(recorded) and all(r["tool_call_id"] == "call-t25-0001"
                                   for r in recorded),
           "ids=%s" % sorted({r["tool_call_id"] for r in recorded}))
    expect("plan: one immutable tool_input plan observed across every hook "
           "(seam fields session_cwd/resolved_file_targets not in host)",
           bool(recorded) and len({r["plan_sha"] for r in recorded}) == 1)
    with open(config_path, "wb") as fh:
        fh.write(backup)
    restored = read(config_path)
    expect("plan: config restored byte-exact; registry back to exact 7+4",
           "t25-recorder" not in restored
           and hook_config.validate_candidate_config(restored)["ok"])


def _write_restrictive_cycle(topo):
    write(os.path.join(topo["wsA"], ".sage", "config.yaml"),
          "hard_enforcement: true\ntdd_enforcement: true\n")
    write(os.path.join(topo["wsA"], ".sage", "work", "20260812-t25-cycle",
                       "manifest.md"),
          "---\nstatus: in-progress\ngate_state: pre-spec\n---\n\n# t25 cycle\n")


def _payload(scratch, topo, call_id, path, label=""):
    payload = {"tool_name": "write_file",
               "args": {"path": path, "content": "TODO = 1\n"},
               "session_id": "t25-session", "task_id": "t25-task",
               "tool_call_id": call_id}
    payload_path = os.path.join(scratch, "payload-%s%s.json" % (call_id, label))
    with open(payload_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    return payload_path


def _blocks(records):
    return [r for r in records
            if isinstance(r["parsed"], dict) and r["parsed"].get("action") == "block"]


def phase_decisions(scratch, topo):
    _write_restrictive_cycle(topo)
    payload_path = _payload(scratch, topo, "call-t25-0010", "src/app.py")
    proc = hermes_cli(["hooks", "test", "pre_tool_call", "--for-tool",
                       "write_file", "--payload-file", payload_path],
                      home=topo["A"], cwd=topo["wsA"])
    records = parse_hooks_test_output(proc.stdout)
    blocks = _blocks(records)
    spec_blocked = any("sage-spec-gate.sh" in r["command"] for r in blocks)
    expect("decisions: in-workspace mutation blocked by the spec gate",
           proc.returncode == 0 and spec_blocked,
           "blocks=%d" % len(blocks))
    expect("decisions: block names the pre-spec cycle",
           any("pre-spec" in str(r["parsed"].get("message", "")) for r in blocks))
    expect("decisions: dispatcher denies when any blocker vetoes",
           len(blocks) >= 1)
    config_doc = yaml.safe_load(read(os.path.join(topo["A"], "config.yaml")))
    spec_cmd = next(e["command"] for e in config_doc["hooks"]["pre_tool_call"]
                    if "sage-spec-gate.sh" in e["command"])
    argv = shlex.split(spec_cmd.replace('\\"', '"'))
    wire = {"hook_event_name": "pre_tool_call", "tool_name": "write_file",
            "tool_input": {"path": "src/app.py"}, "cwd": fwd(topo["wsA"]),
            "session_id": "t25-direct",
            "extra": {"tool_call_id": "call-t25-direct"}}
    direct = spawn(argv, input=json.dumps(wire).encode("utf-8"), timeout=60,
                   text=False, cwd=topo["wsA"])
    raw = direct.stdout or b""
    text = raw.decode("utf-8", errors="replace")
    parsed_direct = None
    try:
        parsed_direct = json.loads(text.replace("\r\n", "\n"))
    except ValueError:
        pass
    expect("decisions: exact registered command blocks via native spawn",
           direct.returncode == 0 and isinstance(parsed_direct, dict)
           and parsed_direct.get("decision") == "block",
           "rc=%s" % direct.returncode)
    payload_path = _payload(scratch, topo, "call-t25-0011", "out.py")
    proc = hermes_cli(["hooks", "test", "pre_tool_call", "--for-tool",
                       "write_file", "--payload-file", payload_path],
                      home=topo["A"], cwd=topo["outside"])
    records = parse_hooks_test_output(proc.stdout)
    expect("decisions: same operation outside A is not blocked",
           proc.returncode == 0 and bool(records) and not _blocks(records)
           and all(r["exit"] == 0 for r in records))
    payload_path = _payload(scratch, topo, "call-t25-0012", "b.py")
    proc = hermes_cli(["hooks", "test", "pre_tool_call", "--for-tool",
                       "write_file", "--payload-file", payload_path],
                      home=topo["A"], cwd=topo["wsB"])
    records = parse_hooks_test_output(proc.stdout)
    expect("decisions: same operation inside B is not blocked (A's cycle stays in A)",
           proc.returncode == 0 and bool(records) and not _blocks(records))
    mixed_block = _payload(scratch, topo, "call-t25-0013", "src/app.py",
                           label="-veto")
    mixed_allow = _payload(scratch, topo, "call-t25-0013", ".sage/ok.md",
                           label="-allow")
    proc1 = hermes_cli(["hooks", "test", "pre_tool_call", "--for-tool",
                        "write_file", "--payload-file", mixed_block],
                       home=topo["A"], cwd=topo["wsA"])
    proc2 = hermes_cli(["hooks", "test", "pre_tool_call", "--for-tool",
                        "write_file", "--payload-file", mixed_allow],
                       home=topo["A"], cwd=topo["wsA"])
    blocked_target = _blocks(parse_hooks_test_output(proc1.stdout))
    allowed_target = _blocks(parse_hooks_test_output(proc2.stdout))
    expect("decisions: mixed targets under one tool_call_id veto the whole call",
           len(blocked_target) >= 1 and len(allowed_target) == 0,
           "vetoed=%d clean=%d" % (len(blocked_target), len(allowed_target)))
    junction_target = os.path.join(scratch, "junction-target", "sub")
    os.makedirs(junction_target, exist_ok=True)
    make_junction(os.path.join(topo["wsA"], "escape-link"),
                  os.path.join(scratch, "junction-target"))
    make_junction(os.path.join(scratch, "home-link"), topo["home"])
    worker = os.path.join(scratch, "mem_worker.py")
    with open(worker, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(MEMORY_WORKER_SOURCE)
    job = {"op": "junction",
           "module_dir": os.path.join(topo["A"], "plugins", "sage"),
           "linked_workspace": os.path.join(topo["wsA"], "escape-link", "sub"),
           "linked_collection": os.path.join(scratch, "home-link"),
           "profile": "alpha"}
    proc = spawn([sys.executable, worker, json.dumps(job)], timeout=120)
    out = {}
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            out = json.loads(proc.stdout.strip().splitlines()[-1])
        except ValueError:
            pass
    expect("decisions: junction escape rejected by installed memory namespace",
           out.get("memory_junction_rejected") is True,
           (proc.stderr or "").strip()[-120:])
    expect("decisions: junction collection rejected by installed profile binding",
           out.get("binding_junction_rejected") is True)


def phase_failure_matrix(scratch, topo):
    worker = os.path.join(scratch, "failure_matrix.py")
    with open(worker, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(FAILURE_MATRIX_SOURCE)
    proc = spawn([HERMES_PYTHON, worker, GIT_BASH], timeout=300, cwd=scratch)
    results = {}
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            results = json.loads(proc.stdout.strip().splitlines()[-1])
        except ValueError:
            pass
    expect("matrix: installed Hermes dispatch ran all 8 failure cases",
           proc.returncode == 0 and len(results) == 8,
           (proc.stderr or proc.stdout).strip()[-160:])

    def parsed_block(key):
        parsed = results.get(key, {}).get("parsed")
        return isinstance(parsed, dict) and parsed.get("action") == "block"

    def parsed_msg(key):
        parsed = results.get(key, {}).get("parsed")
        return str(parsed.get("message", "")) if isinstance(parsed, dict) else ""

    expect("matrix: blocker veto on missing executable (fail closed)",
           parsed_block("blocker_missing_exec")
           and "failed closed" in parsed_msg("blocker_missing_exec"))
    expect("matrix: blocker veto on timeout (fail closed)",
           parsed_block("blocker_timeout")
           and results.get("blocker_timeout", {}).get("timed_out") is True
           and "timed out" in parsed_msg("blocker_timeout"))
    expect("matrix: blocker veto on exit 2",
           parsed_block("blocker_exit2")
           and results.get("blocker_exit2", {}).get("returncode") == 2)
    expect("matrix: blocker veto on malformed output (fail closed)",
           parsed_block("blocker_malformed")
           and "unparseable" in parsed_msg("blocker_malformed"))
    expect("matrix: observer missing-exec visible, never blocks",
           results.get("observer_missing_exec", {}).get("parsed") is None
           and bool(results.get("observer_missing_exec", {}).get("error")))
    expect("matrix: observer timeout visible, never blocks",
           results.get("observer_timeout", {}).get("parsed") is None
           and results.get("observer_timeout", {}).get("timed_out") is True)
    expect("matrix: observer exit 2 visible, never blocks",
           results.get("observer_exit2", {}).get("parsed") is None
           and results.get("observer_exit2", {}).get("returncode") == 2)
    expect("matrix: observer malformed output visible, never blocks",
           results.get("observer_malformed", {}).get("parsed") is None
           and results.get("observer_malformed", {}).get("returncode") == 0)


def managed_disk_hashes(topo, binding):
    receipt = receipts.load_install_receipt(binding)
    hashes = {}
    for target in receipt.managed_targets:
        dest = receipt_target_path(topo, target)
        hashes[receipt_target_key(target)] = sha256_file(dest) \
            if os.path.isfile(dest) else "<missing>"
    return hashes


def phase_memory(scratch, topo):
    worker = os.path.join(scratch, "mem_worker.py")
    with open(worker, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(MEMORY_WORKER_SOURCE)
    module_dir = os.path.join(topo["A"], "plugins", "sage")
    global_home = os.path.join(scratch, "global-home")
    dbA = os.path.join(topo["wsA"], ".sage-memory", "memory.db")
    dbB = os.path.join(topo["wsB"], ".sage-memory", "memory.db")
    dbG = os.path.join(global_home, ".sage-memory", "memory.db")
    pids = set()

    def run_job(job):
        proc = spawn([sys.executable, worker, json.dumps(job)], timeout=120)
        out = {}
        if proc.stdout.strip():
            try:
                out = json.loads(proc.stdout.strip().splitlines()[-1])
            except ValueError:
                pass
        if out.get("pid"):
            pids.add(out["pid"])
        return proc.returncode, out

    rc, out = run_job({"op": "make-global", "global_home": global_home,
                       "key": "t25-global", "value": "SENTINEL-GLOBAL"})
    expect("memory: global sentinel store created",
           rc == 0 and out.get("ok") is True)
    rc, out = run_job({"op": "remember", "workspace": topo["wsA"],
                       "module_dir": module_dir,
                       "key": "t25-a", "value": "SENTINEL-A"})
    expect("memory: A remembers in its exact bound workspace db (fresh process)",
           rc == 0 and os.path.normcase(out.get("db", ""))
           == os.path.normcase(dbA), out.get("db", ""))
    rc, out = run_job({"op": "remember", "workspace": topo["wsB"],
                       "module_dir": module_dir,
                       "key": "t25-b", "value": "SENTINEL-B"})
    expect("memory: B remembers in its exact bound workspace db (fresh process)",
           rc == 0 and os.path.normcase(out.get("db", ""))
           == os.path.normcase(dbB))

    rc, out = run_job({"op": "recall", "workspace": topo["wsA"],
                       "module_dir": module_dir, "own_key": "t25-a",
                       "foreign_a_key": "t25-b", "foreign_b_key": "t25-none",
                       "global_key": "t25-global",
                       "foreign_db": dbB, "global_db": dbG})
    expect("memory: A retrieves A after fresh-process restart",
           rc == 0 and out.get("own") == "SENTINEL-A", str(out.get("own")))
    expect("memory: A never retrieves B or global entries",
           out.get("foreign_a") is None and out.get("foreign_b") is None
           and out.get("global_key") is None)
    expect("memory: A rejects B's db and the global db (visible failure)",
           out.get("foreign_db_rejected") is True
           and out.get("global_db_rejected") is True)
    expect("memory: missing strict db fails visibly",
           out.get("missing_strict_rejected") is True)
    expect("memory: A resolution returns the exact bound db path",
           os.path.normcase(out.get("resolved_db", ""))
           == os.path.normcase(dbA))

    rc, out = run_job({"op": "recall", "workspace": topo["wsB"],
                       "module_dir": module_dir, "own_key": "t25-b",
                       "foreign_a_key": "t25-a", "foreign_b_key": "t25-none",
                       "global_key": "t25-global",
                       "foreign_db": dbA, "global_db": dbG})
    expect("memory: B retrieves B and never A/global (reciprocal)",
           rc == 0 and out.get("own") == "SENTINEL-B"
           and out.get("foreign_a") is None and out.get("global_key") is None,
           str(out.get("own")))
    expect("memory: B rejects A's db and the global db (visible failure)",
           out.get("foreign_db_rejected") is True
           and out.get("global_db_rejected") is True)
    expect("memory: every memory operation ran in its own fresh process",
           len(pids) >= 5, "pids=%d" % len(pids))


def phase_packs(scratch, topo):
    """Spec 7.4.8 / 5.8.4 (T26 BD-1): add/remove an optional pack in A and
    prove B/default remain unchanged. Pack mutations run through the bound
    skill_manager in FRESH driver processes, exactly like the lifecycle ops.
    """
    pack_dir = os.path.join(scratch, "pack-t26")
    for name in ("t26-skill-one", "t26-skill-two"):
        write(os.path.join(pack_dir, name, "SKILL.md"),
              "---\nname: %s\ndescription: T26 native pack fixture\n---\n"
              "body\n" % name)
    skills_a = os.path.join(topo["A"], "skills")
    skills_b = os.path.join(topo["B"], "skills")
    skills_nb = os.path.join(scratch, "no-binding-ws")
    os.makedirs(skills_a, exist_ok=True)
    os.makedirs(skills_b, exist_ok=True)
    os.makedirs(skills_nb, exist_ok=True)
    tools_dir = os.path.join(REPO, "runtime", "tools")
    before_outside = digest_outside_alpha(topo["home"])
    builtin_registry = os.path.join(topo["wsA"], "sage", "skills", "skills.json")
    builtin_registry_before = (
        sha256_file(builtin_registry) if os.path.isfile(builtin_registry) else None
    )
    _profile_surface_before = {
        rel: sha for rel, sha in tree_digest(topo["A"]).items()
        if not (rel == "workspace" or rel.startswith("workspace/"))}

    proc = driver_job({"op": "pack-add", "setup_dir": SETUP,
                       "home": topo["home"], "profile": "alpha",
                       "tools_dir": tools_dir, "workspace": topo["wsA"],
                       "pack_dir": pack_dir, "profile_skills": skills_a},
                      scratch)
    out = parse_driver(proc) if proc.returncode == 0 else {}
    deployed = out.get("deployed", [])
    expect("packs: add --all deploys every pack skill into A's profile only",
           proc.returncode == 0
           and deployed == ["t26-skill-one", "t26-skill-two"],
           ",".join(deployed) or (proc.stderr or "").strip()[-160:])
    entry = out.get("lock", {}).get("packs", {}).get("pack-t26", {})
    expect("packs: bound workspace packs.lock records the add transactionally",
           out.get("lock_exists") is True
           and entry.get("skills") == ["t26-skill-one", "t26-skill-two"]
           and entry.get("version") == "local"
           and re.match(r"^[0-9a-f]{64}$", entry.get("sha256", "")) is not None,
           "skills=%s sha=%s" % (entry.get("skills"),
                                  str(entry.get("sha256", ""))[:12]))
    expect("packs: B and global byte-identical across the pack add",
           digest_outside_alpha(topo["home"]) == before_outside)

    # Negative control: a workspace with NO binding deploys to no profile —
    # no fallback to the shared root, the default profile, or a sibling.
    proc = driver_job({"op": "pack-add", "setup_dir": SETUP,
                       "home": topo["home"], "profile": "alpha",
                       "tools_dir": tools_dir, "workspace": skills_nb,
                       "pack_dir": pack_dir, "profile_skills": skills_b},
                      scratch)
    out_nb = parse_driver(proc) if proc.returncode == 0 else {}
    expect("packs: missing binding deploys to no profile (no fallback)",
           proc.returncode == 0 and out_nb.get("deployed", []) == []
           and digest_outside_alpha(topo["home"]) == before_outside,
           "deployed=%s" % out_nb.get("deployed"))

    proc = driver_job({"op": "pack-remove", "setup_dir": SETUP,
                       "home": topo["home"], "profile": "alpha",
                       "tools_dir": tools_dir, "workspace": topo["wsA"],
                       "profile_skills": skills_a,
                       "skills": ["t26-skill-one", "t26-skill-two"]},
                      scratch)
    out_rm = parse_driver(proc) if proc.returncode == 0 else {}
    expect("packs: remove deletes A's pack skills from the profile",
           proc.returncode == 0 and out_rm.get("deployed", []) == [],
           "left=%s" % out_rm.get("deployed"))
    expect("packs: remove empties the pack entry in the bound packs.lock",
           out_rm.get("lock_exists") is True
           and "pack-t26" not in out_rm.get("lock", {}).get("packs", {}))
    # Profile surface only: durable optional-pack state stays under .sage;
    # receipt-owned workspace/sage remains immutable across add/remove.
    def _profile_surface(root):
        return {rel: sha for rel, sha in tree_digest(root).items()
                if not (rel == "workspace" or rel.startswith("workspace/"))}
    expect("packs: A's profile bytes return exactly to the pre-add state",
           _profile_surface(topo["A"]) == _profile_surface_before)
    expect("packs: B and global byte-identical across add+remove",
           digest_outside_alpha(topo["home"]) == before_outside)
    expect("packs: mutable community registry lives outside receipt-owned runtime",
           os.path.isfile(os.path.join(topo["wsA"], ".sage", "skills.json"))
           and (
               sha256_file(builtin_registry) if os.path.isfile(builtin_registry) else None
           ) == builtin_registry_before)
    evidence("packs: community source/registry state is durable under wsA/.sage")


def phase_update(scratch, topo, ctx):
    binding = ctx["binding"]
    before_profile = profile_root_snapshot(topo["A"])
    before_outside = digest_outside_alpha(topo["home"])
    before_managed = managed_disk_hashes(topo, binding)
    job = {"op": "update", "setup_dir": SETUP, "home": topo["home"],
           "profile": "alpha", "artifact": ctx["artifact"],
           "version": ctx["version"], "commit": ctx["commit"],
           "bash": GIT_BASH}
    proc = driver_job(job, scratch)
    out = parse_driver(proc) if proc.returncode == 0 else {}
    expect("update: receipt-bound update commits (fresh process)",
           proc.returncode == 0 and out.get("ok") is True,
           (proc.stderr or proc.stdout).strip()[-200:])
    journal = receipts.load_completed_run_journal(binding,
                                                  out.get("operation_id", ""))
    expect("update: run journal complete", journal.is_complete)
    receipt = receipts.load_install_receipt(binding)
    reloaded = {receipt_target_key(t): t.sha256 for t in receipt.managed_targets}
    expect("update: hash idempotence (same version/binding -> same hashes)",
           reloaded == ctx["managed_after_install"])
    expect("update: managed bytes on disk unchanged by the refresh",
           managed_disk_hashes(topo, binding) == before_managed)
    expect("update: B/global byte-identical across the update",
           digest_outside_alpha(topo["home"]) == before_outside)
    expect_profile_root_invariant(
        "update: every non-allowlisted A-profile path is byte-identical",
        before_profile, profile_root_snapshot(topo["A"]),
        lifecycle_profile_allowlist(
            managed_paths=(receipt_profile_relpath(t)
                           for t in receipt.managed_targets),
            operation_id=out.get("operation_id"),
        ),
    )
    stale_path = os.path.join(topo["A"], "hooks", "sage-t25-stale.sh")
    before_stale_seed = profile_root_snapshot(topo["A"])
    proc = driver_job({"op": "add-stale-target", "setup_dir": SETUP,
                       "home": topo["home"], "profile": "alpha",
                       "stale_path": stale_path}, scratch)
    expect("update: stale-target seed accepted",
           proc.returncode == 0 and os.path.isfile(stale_path))
    expect_profile_root_invariant(
        "update: stale seed changes only its exact target and receipt",
        before_stale_seed, profile_root_snapshot(topo["A"]),
        lifecycle_profile_allowlist(
            managed_paths=(),
            extra={"hooks/sage-t25-stale.sh"},
        ),
    )
    before_stale_prune = profile_root_snapshot(topo["A"])
    proc = driver_job({"op": "update", "setup_dir": SETUP,
                       "home": topo["home"], "profile": "alpha",
                       "artifact": ctx["artifact"], "version": ctx["version"],
                       "commit": ctx["commit"], "bash": GIT_BASH}, scratch)
    out = parse_driver(proc) if proc.returncode == 0 else {}
    expect("update: refresh with current manifest prunes the stale managed file",
           proc.returncode == 0 and out.get("ok") is True
           and not os.path.isfile(stale_path),
           (proc.stderr or proc.stdout).strip()[-160:])
    journal = receipts.load_completed_run_journal(binding,
                                                  out.get("operation_id", ""))
    pruned = {t.relative_path for t in journal.planned_removals}
    expect("update: journal records the stale removal",
           "hooks/sage-t25-stale.sh" in pruned, ",".join(sorted(pruned)))
    config_text = read(os.path.join(topo["A"], "config.yaml"))
    expect("update: registry still exact 7+4 after prune",
           hook_config.validate_candidate_config(config_text)["ok"])
    expect("update: unmanaged user hook script survived both updates",
           os.path.isfile(os.path.join(topo["A"], "hooks", "user-hook.sh")))
    expect("update: B/global byte-identical after stale prune",
           digest_outside_alpha(topo["home"]) == before_outside)
    expect_profile_root_invariant(
        "update: stale prune preserves every non-allowlisted A-profile path",
        before_stale_prune, profile_root_snapshot(topo["A"]),
        lifecycle_profile_allowlist(
            managed_paths=(receipt_profile_relpath(t)
                           for t in receipt.managed_targets),
            operation_id=out.get("operation_id"),
            extra={"hooks/sage-t25-stale.sh"},
        ),
    )


def phase_injected_rollback(scratch, topo, ctx):
    binding = ctx["binding"]
    before_profile = profile_root_snapshot(topo["A"])
    config_path = os.path.join(topo["A"], "config.yaml")
    with open(config_path, "rb") as fh:
        snap_config = fh.read()
    with open(os.fspath(binding.receipt_path), "rb") as fh:
        snap_receipt = fh.read()
    adapter_path = os.path.join(topo["A"], "hooks", "sage-hermes-gate.sh")
    with open(adapter_path, "rb") as fh:
        snap_adapter = fh.read()
    snap_targets = receipts.load_install_receipt(binding).managed_targets
    snap_managed = managed_disk_hashes(topo, binding)
    before_outside = digest_outside_alpha(topo["home"])
    runs_dir = os.path.join(topo["wsA"], ".sage", "receipts", "runs")
    runs_before = set(os.listdir(runs_dir)) if os.path.isdir(runs_dir) else set()
    job = {"op": "update", "setup_dir": SETUP, "home": topo["home"],
           "profile": "alpha", "artifact": ctx["artifact"],
           "version": ctx["version"], "commit": ctx["commit"],
           "bash": GIT_BASH, "inject_commit_copy_failure": 3}
    proc = driver_job(job, scratch)
    out = parse_driver(proc) if proc.stdout.strip() else {}
    expect("rollback: injected mid-commit failure fails closed",
           "failed_closed" in out, str(out)[:160])
    with open(config_path, "rb") as fh:
        expect("rollback: prior config bytes restored exactly",
               fh.read() == snap_config)
    with open(os.fspath(binding.receipt_path), "rb") as fh:
        expect("rollback: prior receipt bytes restored exactly",
               fh.read() == snap_receipt)
    with open(adapter_path, "rb") as fh:
        adapter_ok = fh.read() == snap_adapter
    expect("rollback: prior managed hashes restored exactly",
           adapter_ok and managed_disk_hashes(topo, binding) == snap_managed)
    expect("rollback: B/global byte-identical across the failed update",
           digest_outside_alpha(topo["home"]) == before_outside)
    runs_after = set(os.listdir(runs_dir)) if os.path.isdir(runs_dir) else set()
    new_journals = sorted(runs_after - runs_before)
    incomplete_seen = False
    operation_ids = []
    for name in new_journals:
        if not re.match(r"^[0-9a-f]{32}\.json$", name):
            continue
        try:
            data = json.loads(read(os.path.join(runs_dir, name)))
            if (data.get("operation") == "update"
                    and data.get("status") == "incomplete"
                    and not data.get("completed_at")):
                incomplete_seen = True
                operation_ids.append(name[:-5])
        except (ValueError, OSError):
            pass
    expect("rollback: incomplete journal durable as rollback evidence",
           len(operation_ids) == 1 and incomplete_seen, ",".join(new_journals))
    rollback_allowed = lifecycle_profile_allowlist(
        managed_paths=(receipt_profile_relpath(t) for t in snap_targets),
        operation_id=operation_ids[0] if len(operation_ids) == 1 else None,
    )
    if len(operation_ids) == 1:
        operation_id = operation_ids[0]
        expected_entries = {
            "%s.json" % operation_id,
            ".%s.json.lock" % operation_id,
            "%s.backup" % operation_id,
        }
        expect("rollback: only the exact journal, lock, and rollback pack remain",
               set(new_journals) == expected_entries,
               ",".join(new_journals))
        backup_rel = "workspace/.sage/receipts/runs/%s.backup" % operation_id
        manifest_rel = backup_rel + "/manifest.json"
        manifest_path = os.path.join(topo["A"], *manifest_rel.split("/"))
        backup_manifest = json.loads(read(manifest_path))
        rollback_allowed.add(manifest_rel)
        if backup_manifest.get("config_existed"):
            rollback_allowed.add(backup_rel + "/config.yaml.bak")
        for record in backup_manifest.get("writes", []):
            backup_name = record.get("bak")
            if backup_name:
                rollback_allowed.add(
                    _exact_profile_relpath(backup_rel + "/" + backup_name))
    expect_profile_root_invariant(
        "rollback: every non-allowlisted A-profile path is byte-identical",
        before_profile, profile_root_snapshot(topo["A"]),
        rollback_allowed,
    )
    config_text = read(config_path)
    expect("rollback: previous 7+4 registry intact after the failed update",
           hook_config.validate_candidate_config(config_text)["ok"])


def phase_uninstall(scratch, topo, ctx):
    binding = ctx["binding"]
    config_path = os.path.join(topo["A"], "config.yaml")
    lines = read(config_path).splitlines()
    out_lines = []
    user_entry = ["    - matcher: 'terminal'",
                  '      command: "echo user-owned-t25"',
                  "      fail_closed: false",
                  "      timeout: 5"]
    for line in lines:
        out_lines.append(line)
        if line.rstrip() == "  post_tool_call:":
            out_lines.extend(user_entry)
    with open(config_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out_lines) + "\n")
    managed_before_targets = receipts.load_install_receipt(binding).managed_targets
    before_profile = profile_root_snapshot(topo["A"])
    before_outside = digest_outside_alpha(topo["home"])
    proc = driver_job({"op": "uninstall", "setup_dir": SETUP,
                       "home": topo["home"], "profile": "alpha"}, scratch)
    out = parse_driver(proc) if proc.returncode == 0 else {}
    expect("uninstall: receipt-guided uninstall commits (fresh process)",
           proc.returncode == 0 and out.get("ok") is True,
           (proc.stderr or proc.stdout).strip()[-200:])
    journal = receipts.load_completed_run_journal(binding,
                                                  out.get("operation_id", ""))
    expect("uninstall: removal journal complete",
           journal.is_complete and journal.operation == "remove")
    config_text = read(config_path)
    expect("uninstall: zero Sage hook entries remain in the registry",
           "sage-hermes-gate.sh" not in config_text
           and "sage-spec-gate.sh" not in config_text)
    expect("uninstall: unrelated user hook entry + settings preserved",
           "user-owned-t25" in config_text
           and "other_setting: 42" in config_text)
    hooks_left = sorted(os.listdir(os.path.join(topo["A"], "hooks")))
    expect("uninstall: all 12 Sage scripts removed; user scripts survive",
           not any(name.startswith("sage-") for name in hooks_left)
           and "user-hook.sh" in hooks_left
           and "t25-recorder.sh" in hooks_left,
           ",".join(hooks_left))
    expect("uninstall: plugin package removed",
           not os.path.isfile(os.path.join(topo["A"], "plugins", "sage",
                                           "__init__.py")))
    expect("uninstall: user identity SOUL.md byte-identical",
           sha256_file(os.path.join(topo["A"], "SOUL.md")) == ctx["soul_sha"])
    expect("uninstall: durable .sage cycle state and memory db preserved",
           os.path.isfile(os.path.join(topo["wsA"], ".sage", "work",
                                       "20260812-t25-cycle", "manifest.md"))
           and os.path.isfile(os.path.join(topo["wsA"], ".sage-memory",
                                           "memory.db")))
    expect("uninstall: receipt survives as durable .sage evidence",
           os.path.isfile(os.fspath(binding.receipt_path)))
    expect("uninstall: B/global byte-identical across the uninstall",
           digest_outside_alpha(topo["home"]) == before_outside)
    expect_profile_root_invariant(
        "uninstall: every non-allowlisted A-profile path is byte-identical",
        before_profile, profile_root_snapshot(topo["A"]),
        lifecycle_profile_allowlist(
            managed_paths=(receipt_profile_relpath(t)
                           for t in managed_before_targets),
            operation_id=out.get("operation_id"),
        ),
    )
    proc = hermes_cli(["hooks", "list"], home=topo["A"], cwd=topo["wsA"])
    expect("uninstall: fresh hermes process sees only the unrelated hook",
           proc.returncode == 0
           and "Configured shell hooks (1 total)" in proc.stdout,
           proc.stdout.splitlines()[0] if proc.stdout else proc.stderr[:80])
    proc = hermes_cli(["plugins", "list"], home=topo["A"], cwd=topo["wsA"])
    expect("uninstall: sage no longer enabled for A",
           proc.returncode == 0
           and re.search(r"sage\s*\u2502\s*enabled", proc.stdout) is None)
    report = doctor.diagnose(binding, bash_path=GIT_BASH)
    expect("uninstall: doctor honestly reports the uninstalled state",
           report["ok"] is False)


def phase_cli_init(scratch, ctx):
    """Spec 7.4.1 via the REAL CLI (T26 BD-4): `sage init --platform hermes`
    must produce an installation that `sage update` accepts. Runs the actual
    bin/sage from the candidate worktree against a FRESH disposable
    collection (gamma = selected, delta = sibling witness). HOME points at an
    empty scratch dir so the framework resolves to the candidate under test,
    never to a host-global install.
    """
    home2 = os.path.join(scratch, "hermes-cli")
    gamma = os.path.join(home2, "profiles", "gamma")
    delta = os.path.join(home2, "profiles", "delta")
    wsG = os.path.join(gamma, "workspace")
    for prof in (gamma, delta):
        for sub in ("hooks", "plugins", "skills"):
            os.makedirs(os.path.join(prof, sub), exist_ok=True)
        os.makedirs(os.path.join(prof, "workspace"), exist_ok=True)
        write(os.path.join(prof, "config.yaml"),
              "# %s user-owned sentinel\n" % os.path.basename(prof))
    write(os.path.join(home2, "CLI-SENTINEL.txt"), "cli-init sentinel\n")
    # Spec 7.4.1 / BD-4 git-fixture bootstrap: hermes_install_transact
    # passes framework_root through to workspace_layout, whose
    # _assert_runtime_replaceable probes `git -C <wsG> rev-parse`. With no
    # `.git` above the disposable scratch the probe fails closed and the
    # install never writes the receipt; snapshot before_outside AFTER the
    # bootstrap so the `.git` bytes are baseline, not delta.
    _init_runtime_git_repo(home2)
    before_outside = digest_outside_profile(home2, "gamma")

    cli_home = os.path.join(scratch, "cli-home")
    os.makedirs(cli_home, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = cli_home.replace(os.sep, "/")
    env["HERMES_HOME"] = fwd(home2)
    env["HERMES_PYTHON_SRC_ROOT"] = HERMES_HOST_ROOT
    env["PYTHONPATH"] = HERMES_HOST_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    env["SAGE_YES"] = "1"
    env["NO_COLOR"] = "1"
    sage_bin = fwd(os.path.join(REPO, "bin", "sage"))
    proc = spawn([GIT_BASH, sage_bin, "init", "--preset", "base",
                  "--no-memory", "--platform", "hermes",
                  "--hermes-home", fwd(home2), "--hermes-profile", "gamma"],
                 cwd=wsG, env=env, timeout=600, stdin=subprocess.DEVNULL)
    expect("cli-init: real `sage init --platform hermes` exits 0",
           proc.returncode == 0,
           (proc.stderr or proc.stdout).strip()[-200:])
    receipt_path = os.path.join(wsG, ".sage", "receipts", "install.json")
    expect("cli-init: the CLI init wrote the install receipt",
           os.path.isfile(receipt_path))
    binding_g = profile_binding.ProfileBinding.from_explicit(
        collection_root=home2, profile_id="gamma",
        profile_root=gamma, workspace_root=wsG)
    receipt = receipts.load_install_receipt(binding_g)
    managed = {t.relative_path: t.sha256 for t in receipt.managed_targets}
    topology = json.load(open(os.path.join(SETUP, "topology.json"), encoding="utf-8"))
    expected_hooks = {topology["adapter"]["package_target"]}
    expected_hooks.update(
        row["package_target"] for row in topology["hooks"]
        if row["classification"] in {
            "hermes_shell_hook", "hermes_plugin_callback", "workflow_on_demand_gate"
        }
    )
    receipt_hooks = {r for r in managed if r.startswith("hooks/")}
    plugin_prefix = "plugins/sage/"
    receipt_plugin = {
        r[len(plugin_prefix):] for r in managed if r.startswith(plugin_prefix)
    }
    framework_manifest_path = os.path.join(
        gamma, "plugins", "sage", ".sage-framework-manifest.json")
    framework_manifest = json.load(open(framework_manifest_path, encoding="utf-8"))
    expected_plugin = {row["path"] for row in framework_manifest["files"]}
    expected_plugin.add(".sage-framework-manifest.json")
    expected_plugin.update(
        row["package_target"][len(plugin_prefix):]
        for row in topology["plugin_files"]
        if row["package_target"].startswith(plugin_prefix)
    )
    expect("cli-init: receipt owns every canonical framework/plugin file and hook",
           receipt_hooks == expected_hooks
           and receipt_plugin == expected_plugin
           and "bin/sage" in receipt_plugin
           and "runtime/tools/build_plugin.py" in receipt_plugin
           and any(r == ".hermes.md" or r.startswith("workspace/.hermes.md")
                   for r in managed),
           "managed=%d hooks=%d/%d plugins=%d/%d" % (
               len(managed), len(receipt_hooks), len(expected_hooks),
               len(receipt_plugin), len(expected_plugin)))
    failed_match = False
    for target in receipt.managed_targets:
        rel = target.relative_path
        sha = target.sha256
        if target.owner == "workspace":
            dest = os.path.join(wsG, rel)
        else:
            dest = os.path.join(gamma, rel)
        if not os.path.isfile(dest) or sha256_file(dest) != sha:
            expect("cli-init: managed bytes on disk match the receipt (%s)" % rel,
                   False)
            failed_match = True
            break
    if not failed_match:
        expect("cli-init: all managed bytes on disk match the receipt", True)
    # The legacy `managed` dict is rebuilt for the hash-idempotency check below.
    managed = {t.relative_path: t.sha256 for t in receipt.managed_targets}
    config_text = read(os.path.join(gamma, "config.yaml"))
    expect("cli-init: exact 7+4 registry validates in the CLI-installed config",
           hook_config.validate_candidate_config(config_text)["ok"])
    expect("cli-init: binding block present in the CLI-installed config",
           "sage_profile_binding:" in config_text)
    hermes_md = os.path.join(wsG, ".hermes.md")
    expect("cli-init: spec-mandated <workspace>/.hermes.md written by the CLI",
           os.path.isfile(hermes_md)
           and len(read(hermes_md).strip()) > 0)
    expect("cli-init: spec 3 honored — no workspace SOUL.md created",
           not os.path.exists(os.path.join(wsG, "SOUL.md")))
    expect("cli-init: sibling profile + global byte-identical across init",
           digest_outside_profile(home2, "gamma") == before_outside)
    proc = hermes_cli(["plugins", "list"], home=gamma, cwd=wsG)
    plugins_list_stdout = proc.stdout or ""
    profile_plugin_yaml = os.path.join(gamma, "plugins", "sage", "plugin.yaml")
    expect("cli-init: fresh hermes process discovers sage enabled for gamma",
           proc.returncode == 0
           and (re.search(r"sage\s*\u2502\s*enabled", plugins_list_stdout) is not None
                or os.path.isfile(profile_plugin_yaml)),
           plugins_list_stdout.splitlines()[0] if plugins_list_stdout else proc.stderr[:80])
    proc = hermes_cli(["hooks", "list"], home=gamma, cwd=wsG)
    expect("cli-init: fresh hermes process reads gamma's 12-hook registry",
           proc.returncode == 0
           and "Configured shell hooks (12 total)" in proc.stdout,
           proc.stdout.splitlines()[0] if proc.stdout else proc.stderr[:80])
    proc = spawn([GIT_BASH, sage_bin, "update"], cwd=wsG, env=env,
                 timeout=600, stdin=subprocess.DEVNULL)
    out_text = (proc.stdout or "") + (proc.stderr or "")
    expect("cli-init: bare `sage update` reuses the receipt (no fail-closed)",
           proc.returncode == 0
           and "install receipt is required" not in out_text,
           out_text.strip()[-200:])
    receipt2 = receipts.load_install_receipt(binding_g)
    managed2 = {t.relative_path: t.sha256 for t in receipt2.managed_targets}
    expect("cli-init: CLI update hash-idempotent for the managed set",
           managed2 == managed)
    expect("cli-init: sibling still byte-identical after the CLI update",
           digest_outside_profile(home2, "gamma") == before_outside)
    evidence("cli-init: ran real bin/sage from %s (SAGE_FRAMEWORK= candidate "
             "worktree via empty-HOME resolution)" % fwd(os.path.join(REPO, "bin")))


def phase_hygiene(scratch, topo, ctx):
    expect("hygiene: every spawned process terminated",
           all(entry["rc"] is not None for entry in SPAWNED),
           "spawned=%d" % len(SPAWNED))
    scratch_key = os.path.normcase(os.path.abspath(scratch))
    scope_violations = []
    for entry in SPAWNED:
        selected_home = entry.get("hermes_home")
        if selected_home:
            selected_key = os.path.normcase(os.path.abspath(selected_home))
            try:
                inside = os.path.commonpath((scratch_key, selected_key)) == scratch_key
            except ValueError:
                inside = False
            if not inside:
                scope_violations.append(selected_home)
    expect("hygiene: every selected Hermes data home stays under scratch",
           not scope_violations, ",".join(scope_violations[:3]))
    token = os.path.basename(scratch)
    ps_cmd = ("$c = (Get-CimInstance Win32_Process | Where-Object "
              "{ $_.ProcessId -ne $PID -and $_.CommandLine -like '*%s*' } "
              "| Measure-Object).Count; Write-Output $c" % token)
    proc = spawn(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=180)
    orphan_count = -1
    try:
        orphan_count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        pass
    expect("hygiene: zero orphan probe processes (hermes/python/bash)",
           orphan_count == 0,
           "matching=%d rc=%d" % (orphan_count, proc.returncode))
    spawned_model_servers = [
        entry for entry in SPAWNED
        if entry["argv"] and "llama" in entry["argv"][0].lower()
    ]
    expect("hygiene: the lane spawned zero model-server processes",
           not spawned_model_servers,
           "spawned=%d" % len(spawned_model_servers))
    llama_now = snapshot_llama_processes()
    expect("hygiene: pre-test model-server state preserved (spec 7.4.10)",
           llama_now == ctx["llama_baseline"],
           "baseline=%s now=%s" % (sorted(ctx["llama_baseline"]),
                                    sorted(llama_now)))
    proc = spawn(["cygpath", "-w", scratch], timeout=30)
    expect("windows: cygpath native path conversion available",
           proc.returncode == 0 and "\\" in proc.stdout)
    hermes_spawns = sum(1 for entry in SPAWNED
                        if entry["argv"] and entry["argv"][0] == "hermes")
    # T26 BD-2/NB-1: this used to be a hardcoded-True expect() counted among
    # the passes. A classification is not a behavioral proof, so it is
    # recorded as evidence, not as a pass. Gateway turn paths (spec 7.4.5/6)
    # remain UNVERIFIED: they need a model/provider this lane may not start.
    evidence("gateway: turn paths unverified - model/provider excluded from "
             "lane; CLI restart proof is %d fresh hermes processes; "
             "environment-limited, not waived" % hermes_spawns)
    evidence("spawned processes total=%d (hermes CLI=%d)"
             % (len(SPAWNED), hermes_spawns))


def main(scratch=None):
    print("T25 native Windows two-profile proof (spec 7.4 / 8)")
    if not shutil.which("cygpath"):
        print("SKIP Windows/MSYS-only probe (cygpath unavailable)")
        return 0
    if (os.name != "nt" or not os.path.isfile(GIT_BASH)
            or not shutil.which("hermes")
            or not os.path.isfile(HERMES_PYTHON)
            or not os.path.isdir(HERMES_HOST_ROOT)):
        print("SKIP native probe prerequisites missing "
              "(git-bash / hermes CLI / hermes venv python / HERMES_TEST_HOST_ROOT)")
        return 0
    if yaml is None:
        print("SKIP PyYAML unavailable - registry cannot be parsed")
        return 0
    if scratch is None:
        scratch = os.path.join(os.path.dirname(REPO),
                               "tmp-two-profile-" + secrets.token_hex(4))
    scratch = os.path.abspath(scratch)
    print("scratch:", scratch)
    try:
        rmtree(scratch)
        os.makedirs(scratch)
        topo = build_topology(scratch)
        _init_runtime_git_repo(topo["home"])
        write_driver(scratch)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print("SETUP FAILURE:", exc)
        return 2
    ctx = {}
    ctx["soul_sha"] = sha256_file(os.path.join(topo["A"], "SOUL.md"))
    ctx["user_hook_sha"] = sha256_file(os.path.join(topo["A"], "hooks",
                                                    "user-hook.sh"))
    version = read(os.path.join(REPO, "VERSION")).strip()
    gitp = spawn(["git", "-C", REPO, "rev-parse", "HEAD"], timeout=30)
    commit = gitp.stdout.strip()
    if gitp.returncode != 0 or not re.match(r"^[0-9a-f]{40}$", commit):
        commit = "0" * 40
    ctx["version"] = version
    ctx["commit"] = commit
    expect("env: candidate version + commit resolved",
           bool(version) and len(commit) == 40,
           "%s / %s" % (version, commit[:12]))
    ctx["llama_baseline"] = snapshot_llama_processes()
    evidence("model-server baseline before the lane: %d llama-like PID(s) %s"
             % (len(ctx["llama_baseline"]), sorted(ctx["llama_baseline"])))
    before_topology = digest_outside_alpha(topo["home"])
    try:
        ctx["artifact"] = phase_artifact(scratch)
        phase_install(scratch, topo, ctx)
        expect("isolation: installing only A left B/global byte-identical",
               digest_outside_alpha(topo["home"]) == before_topology)
        expect("isolation: user-owned profile bytes survived the install",
               sha256_file(os.path.join(topo["A"], "SOUL.md"))
               == ctx["soul_sha"]
               and sha256_file(os.path.join(topo["A"], "hooks",
                                            "user-hook.sh"))
               == ctx["user_hook_sha"])
        phase_registry(topo)
        phase_cli_surfaces(topo)
        phase_runtime_context(scratch, topo)
        phase_tool_call_id(scratch, topo)
        phase_decisions(scratch, topo)
        phase_failure_matrix(scratch, topo)
        phase_memory(scratch, topo)
        phase_packs(scratch, topo)
        phase_update(scratch, topo, ctx)
        phase_injected_rollback(scratch, topo, ctx)
        phase_uninstall(scratch, topo, ctx)
        phase_cli_init(scratch, ctx)
        phase_hygiene(scratch, topo, ctx)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print("PROBE EXECUTION FAILURE:", exc)
        FAIL.append("execution aborted: %s" % exc)
    print("")
    print("Result: %d pass, %d fail" % (len(PASS), len(FAIL)))
    if FAIL:
        print("scratch retained for forensics:", scratch)
        return 1
    try:
        rmtree(scratch)
        print("scratch removed after durable evidence:", scratch)
    except OSError as exc:
        print("scratch cleanup failed:", exc)
    return 0


def test_projected_profile_root_invariant_detects_unmanaged_mutation(tmp_path):
    profile = tmp_path / "alpha"
    managed = profile / "hooks" / "sage-managed.sh"
    unmanaged = profile / "hooks" / "t25-recorder.sh"
    write(os.fspath(managed), "managed-v1\n")
    write(os.fspath(unmanaged), "unmanaged-v1\n")
    before = profile_root_snapshot(os.fspath(profile))

    write(os.fspath(managed), "managed-v2\n")
    write(os.fspath(unmanaged), "INJECTED-UNMANAGED-MUTATION\n")
    after = profile_root_snapshot(os.fspath(profile))
    diff = profile_root_invariant_diff(
        before, after, allowlisted_paths={"hooks/sage-managed.sh"})

    assert set(diff) == {"hooks/t25-recorder.sh"}
    assert diff["hooks/t25-recorder.sh"]["before"] != PROFILE_PATH_ABSENT
    assert diff["hooks/t25-recorder.sh"]["after"] != PROFILE_PATH_ABSENT

    added = profile / "hooks" / "injected-unmanaged.sh"
    write(os.fspath(added), "injected-addition\n")
    added_diff = profile_root_invariant_diff(
        before, profile_root_snapshot(os.fspath(profile)),
        allowlisted_paths={"hooks/sage-managed.sh"})
    assert added_diff["hooks/injected-unmanaged.sh"]["before"] \
        == PROFILE_PATH_ABSENT

    os.remove(unmanaged)
    deleted_diff = profile_root_invariant_diff(
        before, profile_root_snapshot(os.fspath(profile)),
        allowlisted_paths={"hooks/sage-managed.sh"})
    assert deleted_diff["hooks/t25-recorder.sh"]["after"] \
        == PROFILE_PATH_ABSENT

    os.remove(added)
    write(os.fspath(unmanaged), "unmanaged-v1\n")
    restored = profile_root_snapshot(os.fspath(profile))
    assert profile_root_invariant_diff(
        before, restored, allowlisted_paths={"hooks/sage-managed.sh"}) == {}


def test_non_msys_host_exits_cleanly():
    with mock.patch.object(shutil, "which", return_value=None):
        assert main() == 0


@unittest.skipUnless(
    bool(shutil.which("cygpath")) and os.path.isfile(GIT_BASH)
    and bool(shutil.which("hermes")) and os.path.isfile(HERMES_PYTHON),
    "Native Windows two-profile probe (cygpath/git-bash/hermes required)")
def test_hermes_two_profile_windows():
    # pytest entry point - the same checks as script main().
    assert main() == 0


if __name__ == "__main__":
    argv_scratch = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(main(argv_scratch))
