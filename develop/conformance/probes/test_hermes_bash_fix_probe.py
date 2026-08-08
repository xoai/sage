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
import shutil
import subprocess
import sys

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GENERATOR = os.path.join(REPO, "runtime", "platforms", "community", "hermes",
                          "setup", "generate-hermes.sh")

BASH = r"C:/Program Files/Git/bin/bash.exe"

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

N_WANTED = 11  # HOOKS_WANTED in generate-hermes.sh (7 pre + 4 post)

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
    os.makedirs(os.path.join(prof, "agent-hooks", "sage"), exist_ok=True)
    os.makedirs(os.path.join(prof, "plugins", "sage"), exist_ok=True)
    with open(os.path.join(prof, "config.yaml"), "w", encoding="utf-8") as fh:
        fh.write(BROKEN_CONFIG)
    return scratch, home, prof


def run_generator(home, prof):
    env = os.environ.copy()
    env["HERMES_HOME"] = home
    result = subprocess.run(
        [BASH, GENERATOR, prof],
        capture_output=True, text=True, timeout=120, env=env,
    )
    with open(os.path.join(prof, "config.yaml"), encoding="utf-8") as fh:
        text = fh.read()
    return result.returncode, result.stdout, text


ENTRY_RE = re.compile(r'sage-hermes-gate\.sh\\?"?\s+(sage-[\w-]+\.sh)')
BARE_BASH_RE = re.compile(r'^\s*command:\s*bash(\s|$)', re.MULTILINE)


def main(scratch=None):
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

    # ---- Run 1: rewrite the 3 broken blocks, append the 8 missing ----
    rc, out, merged = run_generator(home, prof)
    expect("run 1: generator exit=0", rc == 0, f"rc={rc}")

    entries = set(ENTRY_RE.findall(merged))
    expect(f"run 1: all {N_WANTED} wanted entries present",
           len(entries) == N_WANTED,
           f"got {len(entries)}: {sorted(entries)}")

    bare = list(BARE_BASH_RE.finditer(merged))
    expect("run 1: zero bare-bash command lines", len(bare) == 0,
           f"found {len(bare)}")

    expect("run 1: absolute bash path present",
           "Program Files/Git" in merged or "Git/usr/bin/bash" in merged,
           "argv[0] is not the resolved git-bash")

    expect("run 1: MERGED_OK reports the in-place rewrites",
           "added=8 updated=3" in out,
           "expected added=8 updated=3 in generator output")

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

    for line in out.splitlines() + out2.splitlines():
        if "MERGED_OK" in line:
            print("  " + line.strip())

    print(f"\nResult: {len(PASS)} pass, {len(FAIL)} fail")
    return 0 if not FAIL else 1


def test_hermes_bash_fix():
    """pytest entry point — the same checks as script main()."""
    assert main() == 0


if __name__ == "__main__":
    argv_scratch = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(main(argv_scratch))
