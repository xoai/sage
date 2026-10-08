#!/usr/bin/env python3
"""Conformance probe for the shell-hook 127 fix in generate-hermes.sh.

The bug: the generator registered hook commands as bare `bash "G:/..."`.
Hermes spawns hooks via shlex.split + shell=False; on Windows CreateProcess
searches System32 before PATH, so bare `bash` resolves to WSL's
C:\\Windows\\System32\\bash.exe, which cannot read G:/ script paths ->
exit 127 on every sage shell hook (fail-open, decorative gates).

The fix has two parts, both exercised here:
  1. SAGE_BASH_EXE: the generator resolves the bash actually running it to
     an absolute Windows path at install time and uses it as argv[0].
  2. In-place rewrite: when an existing entry's command uses the broken
     bare-`bash` form, the generator rewrites the WHOLE folded block (not
     just the first line -- orphaned continuations break yaml.safe_load).

Fixture: a profile config holding 3 broken folded entries (the shape of the
real live config: command line at 6-space indent, continuations at 8).
HOOKS_WANTED has 11 entries, so run 1 must rewrite the 3 broken ones AND
append the 8 missing ones; run 2 must be a no-op (added=0 updated=0).

Binding contract (T6/T7/T8): the generator refuses to run without an explicit
profile binding, so the fixture exports SAGE_HERMES_COLLECTION_ROOT / _PROFILE /
_PROFILE_ROOT / _WORKSPACE_ROOT (and PROJECT_ROOT == workspace) around it.

Layout ruling (2026-08-10, supersedes the 2026-08-09 cycle decision): gate
scripts install FLAT into <profile>/hooks/ — never agent-hooks/, never a
hooks/sage bundle subfolder. The broken fixture entries keep the legacy
agent-hooks form as INPUT; run 1 must relocate registrations to hooks/ and
leave no agent-hooks remnant in the merged config.

Known-good facts encoded here (settled by read-only review passes):
  - The entry-count regex must allow hyphens: script names like
    sage-spec-gate.sh never match \\w+ alone.
  - The post-merge config must parse with yaml.safe_load (folded-block
    rewrites that orphan continuation lines corrupt the file).
  - `timeout: 30` sits at the SAME indent as `command:` (6 spaces) and
    must survive the rewrite -- the block terminator derives from the
    command line's own indent, never a hardcoded shallow threshold.

Usage: python3 develop/conformance/probes/test_hermes_bash_fix_probe.py
Exit:  0 all assertions pass / 1 a probe fails / 2 setup failure
"""
import os
import re
import shlex
import shutil
import subprocess
import sys
import unittest
from unittest import mock

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(
    0, os.path.join(REPO, "runtime", "platforms", "community", "hermes", "setup")
)
import hook_config  # noqa: E402
GENERATOR = os.path.join(REPO, "runtime", "platforms", "community", "hermes",
                          "setup", "generate-hermes.sh")


def resolve_git_bash():
    """Resolve Git Bash without embedding one machine's install path."""

    for candidate in (os.environ.get("SAGE_BASH_EXE"), shutil.which("bash")):
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate).replace("\\", "/")
    return ""


BASH = resolve_git_bash()

# 3 broken folded entries, real live shape: command at 6-space indent,
# adapter path + script name on continuation lines at 8-space indent,
# timeout: 30 back at 6 spaces.
BROKEN_CONFIG = """hooks:
  pre_tool_call:
    - matcher: write_file|patch
      command: bash
        "G:/hermes/profiles/test/agent-hooks/sage/sage-hermes-gate.sh"
        sage-scope-gate.sh
      timeout: 30
    - matcher: write_file|patch
      command: bash
        "G:/hermes/profiles/test/agent-hooks/sage/sage-hermes-gate.sh"
        sage-spec-gate.sh
      timeout: 30
  post_tool_call:
    - matcher: write_file|patch
      command: bash
        "G:/hermes/profiles/test/agent-hooks/sage/sage-hermes-gate.sh"
        sage-verify-tracker.sh
      timeout: 30
hooks_auto_accept: true
"""

N_WANTED = 12  # HOOKS_WANTED in generate-hermes.sh (1 session + 7 pre + 4 post)

PASS = []
FAIL = []


def expect(name, ok, note=""):
    line = name + (" -- " + note if note else "")
    print(("  PASS " if ok else "  FAIL ") + line)
    (PASS if ok else FAIL).append(name)


def setup_project(scratch):
    if os.path.isdir(scratch):
        def _unreadonly(func, path, exc):
            os.chmod(path, 0o777)
            func(path)
        shutil.rmtree(scratch, onerror=_unreadonly)
    home = os.path.join(scratch, "hermes")
    prof = os.path.join(home, "profiles", "rei-stewart")
    os.makedirs(os.path.join(prof, "hooks"), exist_ok=True)
    os.makedirs(os.path.join(prof, "workspace"), exist_ok=True)
    os.makedirs(os.path.join(prof, "plugins", "sage"), exist_ok=True)
    with open(os.path.join(prof, "config.yaml"), "w", encoding="utf-8") as fh:
        fh.write(BROKEN_CONFIG)
    return scratch, home, prof


def run_generator(home, prof):
    env = os.environ.copy()
    workspace = os.path.join(prof, "workspace")
    env["HERMES_HOME"] = home.replace("\\", "/")
    env["SAGE_HERMES_COLLECTION_ROOT"] = home.replace("\\", "/")
    env["SAGE_HERMES_PROFILE"] = "rei-stewart"
    env["SAGE_HERMES_PROFILE_ROOT"] = prof.replace("\\", "/")
    env["SAGE_HERMES_WORKSPACE_ROOT"] = workspace.replace("\\", "/")
    result = subprocess.run(
        [BASH, GENERATOR, workspace.replace("\\", "/")],
        capture_output=True, text=True, timeout=120, env=env,
    )
    with open(os.path.join(prof, "config.yaml"), encoding="utf-8") as fh:
        text = fh.read()
    return result.returncode, result.stdout, text


ENTRY_RE = re.compile(r'(?:sage-hermes-gate\.sh\\?"?\s+)?sage-session-init\.sh|(?:sage-hermes-gate\.sh\\?"?\s+)(sage-[\w-]+\.sh)')
BARE_BASH_RE = re.compile(r'^\s*command:\s*bash(\s|$)', re.MULTILINE)


def main(scratch=None):
    if not shutil.which("cygpath"):
        print("SKIP Windows/MSYS-only probe (cygpath unavailable)")
        return 0
    if not os.path.isfile(BASH):
        print("SKIP git-bash unavailable (set SAGE_BASH_EXE or add bash to PATH)")
        return 0
    if scratch is None:
        scratch = os.path.join(os.path.dirname(REPO), "tmp-bash-fix-probe")
    else:
        scratch = os.path.abspath(scratch)
    print("scratch:", scratch)
    try:
        scratch, home, prof = setup_project(scratch)
    except Exception as exc:
        print("SETUP FAILURE:", exc)
        return 2

    # ---- Run 1: rewrite the 3 broken blocks, append the 9 missing ----
    rc, out, merged = run_generator(home, prof)
    expect("run 1: generator exit=0", rc == 0, f"rc={rc}")

    entries = set(ENTRY_RE.findall(merged))
    expect(f"run 1: all {N_WANTED} wanted entries present",
           len(entries) == N_WANTED,
           f"got {len(entries)}: {sorted(entries)}")

    bare = list(BARE_BASH_RE.finditer(merged))
    expect("run 1: zero bare-bash command lines", len(bare) == 0,
           f"found {len(bare)}")

    configured_bash = []
    if yaml is not None:
        doc = yaml.safe_load(merged)
        for event in ("on_session_start", "pre_tool_call", "post_tool_call"):
            for entry in doc["hooks"][event]:
                decoded = entry["command"].replace('\\"', '"')
                configured_bash.append(shlex.split(decoded)[0])
    bash_ok = (
        len(configured_bash) == N_WANTED
        and len({os.path.normcase(path) for path in configured_bash}) == 1
        and all(
            os.path.isabs(path)
            and os.path.isfile(path)
            and os.path.basename(path).lower() in ("bash", "bash.exe")
            for path in configured_bash
        )
    )
    expect("run 1: one existing absolute bash argv[0] is configured",
           bash_ok, "argv0=%r" % configured_bash[:1])

    expect("run 1: registrations relocated to flat profile hooks/",
           "/hooks/sage-hermes-gate.sh" in merged and "agent-hooks" not in merged,
           "merged config must reference <profile>/hooks/ with no agent-hooks remnant")

    expect("run 1: MERGED_OK reports the in-place rewrites",
           "added=9 updated=3" in out,
           "expected added=9 updated=3 in generator output")

    expect("run 1: timeout: 30 survived all rewrites",
           merged.count("timeout: 30") == N_WANTED,
           f"found {merged.count('timeout: 30')} of {N_WANTED}")

    if yaml is not None:
        try:
            yaml.safe_load(merged)
            expect("run 1: merged config parses (yaml.safe_load)", True)
        except Exception as exc:
            expect("run 1: merged config parses (yaml.safe_load)", False, str(exc)[:120])
    else:
        print("  SKIP yaml.safe_load check (PyYAML not installed)")

    # ---- Run 2: idempotent no-op ----
    rc2, out2, merged2 = run_generator(home, prof)
    expect("run 2: generator exit=0", rc2 == 0, f"rc={rc2}")

    entries2 = ENTRY_RE.findall(merged2)
    expect(f"run 2: still exactly {N_WANTED} entries (no duplicates)",
           len(entries2) == N_WANTED, f"got {len(entries2)}")

    expect("run 2: MERGED_OK is a clean no-op",
           "added=0 updated=0" in out2,
           "expected added=0 updated=0 in generator output")

    if yaml is not None:
        try:
            yaml.safe_load(merged2)
            expect("run 2: merged config parses (yaml.safe_load)", True)
        except Exception as exc:
            expect("run 2: merged config parses (yaml.safe_load)", False, str(exc)[:120])

    # Round-trip: Sage's own hook-policy validator must accept the merged
    # config once the legacy blanket consent key is migrated away (the
    # transactional installer owns that migration — spec 5.3.12). This pins
    # matcher decoding, fail_closed emission, and the 1+7+4 registry shape
    # against REAL generator output, not fixture expectations.
    migrated = "\n".join(
        line for line in merged2.splitlines() if "hooks_auto_accept" not in line
    )
    validation = hook_config.validate_candidate_config(migrated)
    expect("round-trip: merged config passes hook policy validation",
           validation["ok"], "; ".join(validation["errors"][:2]))

    for line in out.splitlines() + out2.splitlines():
        if "MERGED_OK" in line:
            print("  " + line.strip())

    print(f"\nResult: {len(PASS)} pass, {len(FAIL)} fail")
    return 0 if not FAIL else 1


def test_non_msys_host_exits_cleanly():
    with mock.patch.object(shutil, "which", return_value=None):
        assert main() == 0


def test_git_managed_plugin_skips_before_profile_hook_or_config_mutation(tmp_path):
    _scratch, home, prof = setup_project(os.fspath(tmp_path / "case"))
    plugin = os.path.join(prof, "plugins", "sage")
    os.makedirs(os.path.join(plugin, ".git"), exist_ok=True)
    with open(os.path.join(plugin, ".git", "HEAD"), "w", encoding="utf-8") as fh:
        fh.write("ref: refs/heads/main\n")
    sentinel = os.path.join(plugin, "USER-OWNED.txt")
    with open(sentinel, "w", encoding="utf-8") as fh:
        fh.write("preserve\n")
    config_path = os.path.join(prof, "config.yaml")
    with open(config_path, encoding="utf-8") as fh:
        config_before = fh.read()

    rc, output, merged = run_generator(home, prof)

    assert rc == 1
    assert "Skipped profiles (not provisioned): rei-stewart" in output
    assert "Sage → Hermes Agent setup incomplete" in output
    assert "Sage → Hermes Agent setup complete" not in output
    assert merged == config_before
    assert not os.path.exists(os.path.join(prof, "hooks", "sage-hermes-gate.sh"))
    with open(sentinel, encoding="utf-8") as fh:
        assert fh.read() == "preserve\n"


def test_stale_plugin_sweep_has_no_arbitrary_depth_cap():
    with open(GENERATOR, encoding="utf-8") as fh:
        source = fh.read()

    assert "find . -mindepth 1 -maxdepth" not in source


@unittest.skipUnless(
    shutil.which("cygpath") and os.path.isfile(BASH),
    "Windows/MSYS-only probe",
)
def test_session_hook_is_structurally_normalized(tmp_path):
    assert yaml is not None
    cases = {
        "unrelated-comment": """# docs mention sage-session-init.sh only
hooks:
  on_session_start:
    - command: user-session-hook
      fail_closed: false
      timeout: 5
""",
        "wrong-event": """hooks:
  on_session_start:
    - command: user-session-hook
      fail_closed: false
      timeout: 5
  pre_tool_call:
    - matcher: terminal
      command: bash \"G:/wrong/sage-session-init.sh\"
      fail_closed: true
      timeout: 30
""",
        "malformed-direct": """hooks:
  on_session_start:
    - command: user-session-hook
      fail_closed: false
      timeout: 5
    - matcher: terminal
      command: bash \"G:/wrong/sage-session-init.sh\" --bad
      fail_closed: true
      timeout: 30
""",
        "duplicate": """hooks:
  on_session_start:
    - command: user-session-hook
      fail_closed: false
      timeout: 5
    - command: bash \"G:/one/sage-session-init.sh\"
      fail_closed: false
      timeout: 30
    - command: bash \"G:/two/sage-session-init.sh\"
      fail_closed: false
      timeout: 30
""",
    }

    for name, config in cases.items():
        scratch = os.fspath(tmp_path / name)
        _scratch, home, prof = setup_project(scratch)
        config_path = os.path.join(prof, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as handle:
            handle.write(config)

        rc, output, merged = run_generator(home, prof)
        assert rc == 0, (name, output)
        document = yaml.safe_load(merged)
        session_entries = document["hooks"]["on_session_start"]
        sage_entries = []
        for event, entries in document["hooks"].items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict) and "sage-session-init.sh" in str(
                    entry.get("command", "")
                ):
                    sage_entries.append((event, entry))

        assert len(sage_entries) == 1, (name, sage_entries)
        event, sage_entry = sage_entries[0]
        assert event == "on_session_start"
        assert "matcher" not in sage_entry
        assert sage_entry["fail_closed"] is False
        assert sage_entry["timeout"] == 30
        decoded = sage_entry["command"].replace('\\"', '"')
        argv = shlex.split(decoded)
        assert len(argv) == 2, (name, argv)
        assert argv[1].replace("\\", "/").endswith("/hooks/sage-session-init.sh")
        assert any(
            entry.get("command") == "user-session-hook"
            for entry in session_entries
            if isinstance(entry, dict)
        )
        validation = hook_config.validate_candidate_config(merged)
        assert validation["ok"], (name, validation["errors"])

        rc2, output2, merged2 = run_generator(home, prof)
        assert rc2 == 0, (name, output2)
        assert "added=0 updated=0" in output2
        second = yaml.safe_load(merged2)
        second_sage_entries = [
            (event, entry)
            for event, entries in second["hooks"].items()
            if isinstance(entries, list)
            for entry in entries
            if isinstance(entry, dict)
            and "sage-session-init.sh" in str(entry.get("command", ""))
        ]
        assert len(second_sage_entries) == 1, (name, second_sage_entries)
        assert second_sage_entries[0][0] == "on_session_start"
        assert hook_config.validate_candidate_config(merged2)["ok"]


@unittest.skipUnless(
    shutil.which("cygpath") and os.path.isfile(BASH),
    "Windows/MSYS-only probe",
)
def test_hermes_bash_fix():
    """pytest entry point — the same checks as script main()."""
    assert main() == 0


if __name__ == "__main__":
    argv_scratch = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(main(argv_scratch))
