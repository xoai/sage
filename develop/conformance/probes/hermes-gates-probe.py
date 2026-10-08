#!/usr/bin/env python3
"""Conformance probe for the exact generated 7+4 hook commands (spec 5.3.13-14).

Executes the EXACT command form the generator emits — resolved git-bash
argv[0], quoted adapter path, gate script arg — through the same shlex.split
Hermes applies, against real fixtures, and classifies the wire results with
the Task 14 policy module:

  allow          a project with no blocking Sage state returns {}
  block          an active pre-spec cycle vetoes a source edit (exit 2 path)
  veto (missing executable)  argv[0] that does not exist fails closed
  veto (timeout)             a hung gate fails closed
  observer                   the same failures stay visible, never block

Windows/MSYS-only (needs git-bash). Exit: 0 all assertions pass / 1 fail /
2 setup failure.
"""

import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(
    0, os.path.join(REPO, "runtime", "platforms", "community", "hermes", "setup")
)
import hook_config  # noqa: E402


def resolve_git_bash():
    """Resolve Git Bash without embedding one machine's install path."""

    for candidate in (os.environ.get("SAGE_BASH_EXE"), shutil.which("bash")):
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate).replace("\\", "/")
    return ""


BASH = resolve_git_bash()
ADAPTER_SRC = os.path.join(
    REPO, "runtime", "platforms", "community", "hermes", "hooks", "sage-hermes-gate.sh"
)
GATES_SRC = os.path.join(REPO, "runtime", "platforms", "claude-code", "hooks")

PASS = []
FAIL = []


def expect(name, ok, note=""):
    line = name + (": " + note if note else "")
    print(("  PASS " if ok else "  FAIL ") + line)
    (PASS if ok else FAIL).append(name)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_hooks_dir(root):
    hooks = root / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy2(ADAPTER_SRC, hooks / "sage-hermes-gate.sh")
    for gate in ("sage-spec-gate.sh", "sage-tdd-gate.sh"):
        shutil.copy2(os.path.join(GATES_SRC, gate), hooks / gate)
    _write(hooks / "sage-sleep-gate.sh", "#!/usr/bin/env bash\nsleep 30\n")
    return hooks


def _command(bash, hooks, script):
    return '"%s" "%s" %s' % (
        bash,
        os.fspath(hooks / "sage-hermes-gate.sh").replace("\\", "/"),
        script,
    )


def _run(command, project, timeout=15):
    argv = shlex.split(command)
    payload = {
        "hook_event_name": "pre_tool_call",
        "tool_name": "write_file",
        "tool_input": {"path": os.fspath(project / "src" / "edit.py").replace("\\", "/")},
        "cwd": os.fspath(project).replace("\\", "/"),
    }
    try:
        completed = subprocess.run(
            argv,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return completed.returncode, completed.stdout, False
    except FileNotFoundError:
        return None, "", False
    except subprocess.TimeoutExpired:
        return None, "", True


def _make_project(root, *, pre_spec_cycle):
    project = root / "project"
    (project / "src").mkdir(parents=True)
    if pre_spec_cycle:
        # The spec-gate enforces only under explicit hard_enforcement: true —
        # absent/false is a deliberate fail-open for opted-out projects.
        _write(project / ".sage" / "config.yaml", "hard_enforcement: true\n")
        _write(
            project / ".sage" / "work" / "20260810-probe-cycle" / "manifest.md",
            "---\nstatus: in-progress\ngate_state: pre-spec\n---\n",
        )
    return project


def main():
    if not shutil.which("cygpath"):
        print("SKIP Windows/MSYS-only probe (cygpath unavailable)")
        return 0
    if not os.path.isfile(BASH):
        print("SKIP git-bash unavailable (set SAGE_BASH_EXE or add bash to PATH)")
        return 0
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="sage-gates-probe-"))
    print("scratch:", scratch)
    try:
        hooks = _make_hooks_dir(scratch)
        open_project = _make_project(scratch / "open", pre_spec_cycle=False)
        locked_project = _make_project(scratch / "locked", pre_spec_cycle=True)

        # 0. The generated command form must shlex.split to the full spaced
        # bash path as argv[0] — an unquoted argv[0] splits at the space and
        # dies before the adapter ever runs (the WSL/127 class).
        command = _command(BASH, hooks, "sage-spec-gate.sh")
        argv0 = shlex.split(command)[0]
        expect("generated form: argv[0] is the full resolved git-bash",
               argv0 == BASH, "argv0=%r" % argv0)

        # 1. allow — no blocking state
        rc, out, timed_out = _run(_command(BASH, hooks, "sage-spec-gate.sh"), open_project)
        outcome = hook_config.classify_hook_result(
            returncode=rc, stdout=out, stderr="", timed_out=timed_out, fail_closed=True
        )
        expect("allow: unblocked project classifies allow", outcome == "allow",
               "rc=%s out=%r" % (rc, out[:80]))

        # 2. block — active pre-spec cycle vetoes the source edit
        rc, out, timed_out = _run(_command(BASH, hooks, "sage-spec-gate.sh"), locked_project)
        outcome = hook_config.classify_hook_result(
            returncode=rc, stdout=out, stderr="", timed_out=timed_out, fail_closed=True
        )
        expect("block: pre-spec cycle vetoes with a decision", outcome == "block",
               "rc=%s out=%r" % (rc, out[:80]))

        # 3. veto — missing executable (argv[0] does not exist)
        rc, out, timed_out = _run(
            _command("C:/nonexistent/git-bash.exe", hooks, "sage-spec-gate.sh"),
            open_project,
        )
        outcome = hook_config.classify_hook_result(
            returncode=rc, stdout=out, stderr="", timed_out=timed_out, fail_closed=True
        )
        expect("veto: missing executable blocks a fail-closed gate", outcome == "block",
               "rc=%r" % rc)

        # 4. veto — timeout on a hung gate
        rc, out, timed_out = _run(
            _command(BASH, hooks, "sage-sleep-gate.sh"), open_project, timeout=3
        )
        outcome = hook_config.classify_hook_result(
            returncode=rc, stdout=out, stderr="", timed_out=timed_out, fail_closed=True
        )
        expect("veto: timeout blocks a fail-closed gate", outcome == "block",
               "timed_out=%s" % timed_out)

        # 5. observer — identical failures never block
        observer_cases = [
            ("missing executable", "C:/nonexistent/git-bash.exe", "sage-spec-gate.sh", 15),
            ("timeout", BASH, "sage-sleep-gate.sh", 3),
        ]
        for label, bash, script, timeout in observer_cases:
            rc, out, timed_out = _run(_command(bash, hooks, script), open_project, timeout=timeout)
            outcome = hook_config.classify_hook_result(
                returncode=rc, stdout=out, stderr="", timed_out=timed_out,
                fail_closed=False,
            )
            expect("observer %s: visible but never blocks" % label,
                   outcome == "unverifiable", "outcome=%s" % outcome)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    print("\nResult: %d pass, %d fail" % (len(PASS), len(FAIL)))
    return 0 if not FAIL else 1


@unittest.skipUnless(shutil.which("cygpath"), "Windows/MSYS-only probe")
def test_hermes_gates_conformance():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
