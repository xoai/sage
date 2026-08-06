#!/usr/bin/env python3
"""Level-2 equivalent probe: exercise the Hermes plugin's hook entry points
directly, with the same (tool_name, args) shapes Hermes passes.

This is NOT a mock of Hermes — it calls the exact functions Hermes calls
(_on_pre_tool_call / _on_post_tool_call) against a real scratch .sage
project on disk, and prints what the model would have seen.

Usage:  python3 develop/conformance/probes/hermes-gates-probe.py [proj_dir]
Exit:   0 all gates behaved · 1 a gate misbehaved · 2 setup failure
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PLUGIN = os.path.join(REPO, "__init__.py")

spec = importlib.util.spec_from_file_location("sage_plugin", PLUGIN)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

PASS = []
FAIL = []


def expect(name, got, want_block=None, want_gate=None):
    """got = hook return. want_block True/False, want_gate substring."""
    is_block = isinstance(got, dict) and got.get("action") == "block"
    ok = (is_block == want_block) and (
        want_gate is None or (is_block and want_gate in got.get("message", "")))
    line = "%s: %s" % (name, "BLOCKED" if is_block else "allowed")
    if is_block:
        line += " — " + got["message"].splitlines()[0][:110]
    print(("  PASS " if ok else "  FAIL ") + line)
    (PASS if ok else FAIL).append(name)


def setup(proj):
    if os.path.isdir(proj):
        def _unreadonly(func, path, exc_info):
            os.chmod(path, 0o777)
            func(path)
        shutil.rmtree(proj, onerror=_unreadonly)
    os.makedirs(os.path.join(proj, ".sage", "work", "probe-cycle"))
    os.makedirs(os.path.join(proj, ".sage", "gates"))
    with open(os.path.join(proj, ".sage", "config.yaml"), "w") as fh:
        fh.write("hard_enforcement: true\ntdd_enforcement: true\n")
    with open(os.path.join(proj, ".sage", "work", "probe-cycle", "manifest.md"), "w") as fh:
        fh.write("---\ncycle: probe-cycle\ntier: tier2\nstatus: active\n"
                 "gate_state: pre-spec\nqa: pending\n---\n# Probe cycle\n")
    # git repo with a TRACKED test (tdd-gate precondition)
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    with open(os.path.join(proj, "test_probe.py"), "w") as fh:
        fh.write("def test_placeholder():\n    assert True\n")
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    subprocess.run(["git", "-c", "user.email=probe@sage", "-c",
                    "user.name=probe", "commit", "-qm", "test first"],
                   cwd=proj, check=True)


def main():
    if len(sys.argv) > 1:
        proj = os.path.abspath(sys.argv[1])
    else:
        proj = os.path.join(os.path.dirname(REPO), "tmp-sage-tier-a-probe")
    print("probe project:", proj)
    try:
        setup(proj)
    except Exception as exc:
        print("SETUP FAILURE:", exc)
        return 2

    # Terminal-shaped calls resolve the project from cwd (documented plugin
    # behavior: the gate follows the file for edits, but from cwd for terminal).
    os.chdir(proj)

    src = os.path.join(proj, "app.py")
    cfg = os.path.join(proj, ".sage", "config.yaml")
    man = os.path.join(proj, ".sage", "work", "probe-cycle", "manifest.md")

    print("\n── pre_tool_call probes (what the model sees BEFORE the tool runs) ──")

    # 1. spec-gate — source edit while cycle is pre-spec
    got = plugin._on_pre_tool_call(
        tool_name="write_file", args={"path": src, "content": "print('hi')\n"})
    expect("spec-gate blocks pre-spec source edit", got, True, "spec-gate")

    # 2. secrets-gate — hardcoded key in source (fires before spec-gate)
    got = plugin._on_pre_tool_call(
        tool_name="write_file",
        args={"path": src, "content": "KEY = 'sk-AbCdEfGh1234567890xYz'\n"})
    expect("secrets-gate blocks hardcoded key", got, True, "secrets-gate")

    # 3. config-gate — agent tries to disarm enforcement
    with open(cfg) as fh:
        cfg_now = fh.read()
    got = plugin._on_pre_tool_call(
        tool_name="patch",
        args={"path": cfg, "old_string": "hard_enforcement: true",
              "new_string": "hard_enforcement: false"})
    expect("config-gate blocks self-disarmament", got, True, "config-gate")
    _ = cfg_now

    # 4. tdd-gate — advance the cycle past pre-spec (spec-gate fires first
    #    otherwise), move HEAD off the test-only commit so ALLOW 2 doesn't
    #    apply, and leave no pending test file so ALLOW 1 doesn't either.
    with open(man, "w") as fh:
        fh.write("---\ncycle: probe-cycle\ntier: tier2\nstatus: active\n"
                 "gate_state: building\nqa: pending\n---\n# Probe cycle\n")
    with open(os.path.join(proj, ".sage", "work", "probe-cycle", "spec.md"), "w") as fh:
        fh.write("# Probe spec\nApproved for the probe.\n")
    subprocess.run(["git", "-c", "user.email=probe@sage", "-c",
                    "user.name=probe", "commit", "-q", "--allow-empty",
                    "-m", "empty"], cwd=proj, check=True)  # move HEAD off test-only
    got = plugin._on_pre_tool_call(
        tool_name="write_file", args={"path": src, "content": "X = 1\n"})
    expect("tdd-gate blocks code-without-test", got, True, "TDD gate")

    # 5. bookkeeping-gate — hand-edit of an active cycle's manifest
    got = plugin._on_pre_tool_call(
        tool_name="patch",
        args={"path": man, "old_string": "# Probe cycle",
              "new_string": "# Probe cycle (edited by hand)"})
    expect("bookkeeping-gate blocks hand-edited manifest", got, True,
           "bookkeeping-gate")

    # 6. verify-gate — commit after source edit, no test run since
    plugin._on_post_tool_call(tool_name="write_file",
                              args={"path": src})  # seeds last_source_edit
    got = plugin._on_pre_tool_call(
        tool_name="terminal", args={"command": "git commit -m done"})
    expect("verify-gate blocks unverified commit", got, True, "verify-gate")

    print("\n── post_tool_call probes (observers, must never block) ──")

    # 7. verify-tracker — pytest run records last_test_run
    plugin._on_post_tool_call(tool_name="terminal",
                              args={"command": "pytest -q"})
    state = plugin._verify_read_state(os.path.join(proj, ".sage"))
    ok = "last_test_run" in state and "last_source_edit" in state
    print(("  PASS" if ok else "  FAIL") + " verify-tracker state: " + str(state))
    (PASS if ok else FAIL).append("verify-tracker")

    # 8. commit allowed AFTER tests ran (discipline: test then commit)
    time.sleep(1.1)
    got = plugin._on_pre_tool_call(
        tool_name="terminal", args={"command": "git commit -m done"})
    expect("commit allowed after fresh test run", got, False)

    # 9. R29 degradation audit — skipped QA must be auto-logged
    with open(man, "w") as fh:
        fh.write("---\ncycle: probe-cycle\ntier: tier2\nstatus: active\n"
                 "gate_state: gates-passed\nqa: skipped-no-subagent\n---\n"
                 "# Probe cycle\n")
    plugin._on_post_tool_call(tool_name="write_file", args={"path": man})
    dec = os.path.join(proj, ".sage", "decisions.md")
    logged = os.path.isfile(dec) and "qa:skipped-no-subagent" in open(
        dec, encoding="utf-8").read()
    print(("  PASS" if logged else "  FAIL") + " R29 degradation logged to decisions.md")
    (PASS if logged else FAIL).append("r29-degradation-audit")

    # ── duplicate-key self-disarmament (maintainer review, 2026-08-05) ──
    # A config where hard_enforcement holds BOTH values is a reader-divergence
    # bomb: a last-wins main reader disarms while a first-wins gate reader
    # stays armed. The canonical sage-config-gate.sh refuses to create such a
    # config (contradictory_flag); the port must too.
    print("\n── duplicate-key self-disarmament probes ──")

    # 10. main reader must stay ARMED on a contradictory config (first-wins)
    with open(cfg, "w") as fh:
        fh.write("hard_enforcement: true\ntdd_enforcement: true\n"
                 "hard_enforcement: false\n")
    _sd, flags = plugin._config(proj)
    armed = flags.get("hard_enforcement") is True
    print(("  PASS" if armed else "  FAIL") +
          " main reader stays armed on contradictory config: %s" % armed)
    (PASS if armed else FAIL).append("contradictory-config-stays-armed")

    # 11. with that config on disk, enforcement must still veto (secrets-gate
    #     is manifest-independent, so it isolates the reader question)
    got = plugin._on_pre_tool_call(
        tool_name="write_file",
        args={"path": src, "content": "KEY = 'sk-AbCdEfGh1234567890xYz'\n"})
    expect("gates still veto under contradictory config", got, True,
           "secrets-gate")

    # 12. config-gate must refuse to CREATE the contradictory config — both
    #     the whole-file write and the append-by-patch form. Start from a
    #     CLEAN config so the write is what introduces the contradiction.
    with open(cfg, "w") as fh:
        fh.write("hard_enforcement: true\ntdd_enforcement: true\n")
    # content keeps tdd_enforcement so the ONLY objection is the duplicate key
    got = plugin._on_pre_tool_call(
        tool_name="write_file",
        args={"path": cfg, "content": "hard_enforcement: true\n"
                                      "tdd_enforcement: true\n"
                                      "hard_enforcement: false\n"})
    expect("config-gate refuses contradictory write_file", got, True,
           "config-gate")
    got = plugin._on_pre_tool_call(
        tool_name="patch",
        args={"path": cfg, "old_string": "hard_enforcement: true",
              "new_string": "hard_enforcement: true\nhard_enforcement: false"})
    expect("config-gate refuses contradictory append-by-patch", got, True,
           "config-gate")

    # restore a clean config for anything run after this block
    with open(cfg, "w") as fh:
        fh.write("hard_enforcement: true\ntdd_enforcement: true\n")

    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
