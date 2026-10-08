#!/usr/bin/env python3
r"""
test_sage_cli_install.py — the CLI install path must produce an installation
the rest of the CLI lifecycle accepts (spec 1, 3, 5.1.1/5.1.6, 5.2.2).

T26 remediation (BD-4 of the T25 spec-compliance review): bin/sage called
profile_installer.update and profile_installer.uninstall but had NO
profile_installer.install caller. `sage init --platform hermes` ran the legacy
generator, which wrote the binding block but no install receipt, so the very
next `sage update` failed closed. The same generator wrote a workspace
`SOUL.md` (forbidden by spec section 3) while the spec-mandated instructions
surface `<workspace>\.hermes.md` was written by no production path.

These tests drive the REAL `bin/sage` end to end against disposable profiles:

  1. init writes a valid install receipt bound to the selected profile whose
     managed bytes match disk, owns every canonical profile hook and the full
     canonical Sage framework/plugin tree plus the transactional workspace
     runtime, and leaves the sibling profile and every byte outside the
     selected profile untouched;
  2. init writes `<workspace>\.hermes.md` and creates no workspace SOUL.md;
  3. the immediately following `sage update` commits (does not fail closed on
     a missing receipt) and is hash-idempotent for the managed set.

Usage:  python3 develop/validators/tools/test_sage_cli_install.py
Exit:   0 = all pass | 1 = a test failed

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SAGE_BIN = REPO_ROOT / "bin" / "sage"
SETUP_ROOT = (
    REPO_ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup"
)


def find_bash() -> str:
    """Prefer Git Bash on Windows; System32 bash.exe is the WSL launcher."""
    configured = os.environ.get("SAGE_BASH_EXE")
    if configured:
        return configured
    if os.name == "nt":
        for candidate in (
            pathlib.Path(r"C:\Program Files\Git\bin\bash.exe"),
            pathlib.Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
            pathlib.Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
        ):
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash") or "bash"


BASH = find_bash()

_RELEASE_STATE_PARTS = frozenset(
    (
        ".git",
        ".sage",
        ".sage-memory",
        ".serena",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "__pycache__",
        "dist",
        "htmlcov",
        "node_modules",
        "target",
    )
)
_RELEASE_GENERATED_ROOT_FILES = frozenset(
    (
        ".sage-framework-manifest.json",
        "memory_namespace.py",
        "profile_binding.py",
    )
)


def canonical_tracked_framework_files() -> set:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "-z"],
        check=True,
        capture_output=True,
    )
    result = set()
    for item in proc.stdout.split(b"\0"):
        if not item:
            continue
        rel = pathlib.PurePosixPath(os.fsdecode(item))
        if any(part in _RELEASE_STATE_PARTS for part in rel.parts):
            continue
        if rel.suffix in (".pyc", ".pyo"):
            continue
        result.add(rel.as_posix())
    return result


def copy_candidate_release_tree(destination: pathlib.Path) -> None:
    """Materialize current tracked candidate bytes without Git/local state."""

    destination.mkdir(parents=True)
    for relative in sorted(canonical_tracked_framework_files()):
        source = REPO_ROOT / pathlib.PurePosixPath(relative)
        target = destination / pathlib.PurePosixPath(relative)
        if source.is_symlink() or not source.is_file():
            raise RuntimeError("unsafe or missing tracked release source: %s" % relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def bash_path(path: pathlib.Path) -> str:
    return str(path).replace("\\", "/")


def fake_hermes_activation_env(root: pathlib.Path) -> dict:
    """Create an opaque public Hermes launcher for fresh-process proofs."""

    launcher = root / "fake-hermes.py"
    launcher.write_text(
        "import argparse\n"
        "import json\n"
        "import os\n"
        "\n"
        "parser = argparse.ArgumentParser(add_help=False)\n"
        "parser.add_argument('--profile', required=True)\n"
        "parser.add_argument('hooks')\n"
        "parser.add_argument('activation_proof')\n"
        "parser.add_argument('--surface', choices=('cli', 'gateway'), required=True)\n"
        "parser.add_argument('--expectation-file', required=True)\n"
        "args = parser.parse_args()\n"
        "report = {\n"
        "    'ok': True,\n"
        "    'pid': os.getpid(),\n"
        "    'surface': args.surface,\n"
        "    'policy_probes': [\n"
        "        {'outcome': 'allow'},\n"
        "        {'outcome': 'block'},\n"
        "        {'outcome': 'unverifiable'},\n"
        "    ],\n"
        "    'errors': [],\n"
        "}\n"
        "print(json.dumps(report, separators=(',', ':')))\n",
        encoding="utf-8",
    )
    return {
        "SAGE_HERMES_COMMAND": json.dumps(
            [
                os.fspath(pathlib.Path(sys.executable).resolve()),
                os.fspath(launcher.resolve()),
            ]
        )
    }


def test_fake_hermes_activation_env_uses_only_the_public_command(tmp_path) -> None:
    env = fake_hermes_activation_env(tmp_path)

    command = json.loads(env["SAGE_HERMES_COMMAND"])
    assert command[0] == os.fspath(pathlib.Path(sys.executable).resolve())
    assert pathlib.Path(command[1]).is_file()
    assert "HERMES_PYTHON" not in env
    assert "HERMES_PYTHON_SRC_ROOT" not in env
    assert "PYTHONPATH" not in env


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: pathlib.Path) -> dict:
    """Stable path/content inventory without following directory links."""
    inventory = {}
    if not root.exists():
        return inventory
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        base = pathlib.Path(dirpath)
        for name in sorted(filenames):
            full = base / name
            rel = full.relative_to(root).as_posix()
            try:
                inventory[rel] = hashlib.sha256(full.read_bytes()).hexdigest()
            except OSError:
                inventory[rel] = "<unreadable>"
    return inventory


def digest_outside_profile(home: pathlib.Path, profile: str) -> dict:
    out = {}
    skip = f"profiles/{profile}"
    for rel, sha in tree_digest(home).items():
        if rel == skip or rel.startswith(skip + "/"):
            continue
        out[rel] = sha
    return out


def load_setup_module(name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(name, SETUP_ROOT / file_name)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {file_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SageHermesCliInstallTest(unittest.TestCase):
    """`sage init --platform hermes` -> receipt -> `sage update` end to end."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("cygpath") is None and os.name != "nt":
            raise unittest.SkipTest("native Windows CLI install proof")
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="sage-cli-install-test-"))
        cls.sage_home = cls.tmp / "sage-home"
        cls.sage_home.mkdir()
        copy_candidate_release_tree(cls.sage_home / "framework")
        # Load the same strict receipt/config types the installer consumes.
        cls.profile_binding = load_setup_module("profile_binding", "profile_binding.py")
        cls.receipts = load_setup_module("receipts", "receipts.py")
        cls.hook_config = load_setup_module("hook_config", "hook_config.py")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.case = pathlib.Path(tempfile.mkdtemp(dir=self.tmp, prefix="case-"))
        self.hermes_home = self.case / "hermes"
        for profile in ("alpha", "beta"):
            (self.hermes_home / "profiles" / profile / "workspace").mkdir(
                parents=True
            )
            (self.hermes_home / "profiles" / profile / "config.yaml").write_text(
                f"# {profile} user-owned config sentinel\n", encoding="utf-8"
            )
        (self.hermes_home / "GLOBAL-SENTINEL.txt").write_text(
            "global sentinel\n", encoding="utf-8"
        )
        self.alpha = self.hermes_home / "profiles" / "alpha"
        self.beta = self.hermes_home / "profiles" / "beta"
        self.workspace = self.alpha / "workspace"
        self.env = {
            **os.environ,
            **fake_hermes_activation_env(self.case),
            "SAGE_HOME": bash_path(self.sage_home),
            "HERMES_HOME": bash_path(self.hermes_home),
            "SAGE_YES": "1",
        }
        self.before_outside = digest_outside_profile(self.hermes_home, "alpha")
        self.before_beta = tree_digest(self.beta)

    def tearDown(self):
        shutil.rmtree(self.case, ignore_errors=True)

    def run_sage(self, *args, cwd=None, env=None):
        return subprocess.run(
            [BASH, bash_path(SAGE_BIN), *args],
            cwd=cwd or self.workspace,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            env=env or self.env,
            check=False,
        )

    def run_init(self):
        return self.run_sage(
            "init",
            "--preset",
            "base",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
            "--hermes-profile",
            "alpha",
        )

    def _load_receipt(self):
        binding = self.profile_binding.ProfileBinding.from_explicit(
            collection_root=self.hermes_home,
            profile_id="alpha",
            profile_root=self.alpha,
            workspace_root=self.workspace,
        )
        return binding, self.receipts.load_install_receipt(binding)

    def test_cli_init_writes_a_valid_receipt_bound_to_the_selected_profile(self):
        result = self.run_init()
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-4000:])
        receipt_path = self.workspace / ".sage" / "receipts" / "install.json"
        self.assertTrue(receipt_path.is_file(), "no install receipt after CLI init")
        binding, receipt = self._load_receipt()
        self.assertEqual("alpha", receipt.binding.profile_id)
        self.assertEqual(self.workspace, pathlib.Path(os.fspath(receipt.binding.workspace_root)))
        managed = {
            (target.owner, target.relative_path): target.sha256
            for target in receipt.managed_targets
        }
        profile_managed = {
            relative: sha
            for (owner, relative), sha in managed.items()
            if owner == "profile"
        }
        workspace_managed = {
            relative: sha
            for (owner, relative), sha in managed.items()
            if owner == "workspace"
        }
        hooks = {r for r in profile_managed if r.startswith("hooks/")}
        plugin = {r for r in profile_managed if r.startswith("plugins/sage/")}
        expected_hooks = {"hooks/sage-hermes-gate.sh"}
        expected_hooks.update(
            "hooks/" + entry["script"]
            for entry in self.hook_config.expected_registry()
        )
        expected_plugin = canonical_tracked_framework_files()
        expected_plugin.update(_RELEASE_GENERATED_ROOT_FILES)
        installed_plugin = {
            relative[len("plugins/sage/") :]
            for relative in plugin
        }
        self.assertEqual(expected_hooks, hooks)
        self.assertEqual(expected_plugin, installed_plugin)
        self.assertEqual(hooks | plugin, set(profile_managed))
        self.assertIn(".hermes.md", workspace_managed)
        self.assertIn("sage/VERSION", workspace_managed)
        self.assertFalse(
            any(
                "__pycache__" in pathlib.PurePosixPath(relative).parts
                or relative.endswith((".pyc", ".pyo"))
                for relative in workspace_managed
            ),
            sorted(workspace_managed),
        )
        for (owner, rel), sha in managed.items():
            root = self.alpha if owner == "profile" else self.workspace
            dest = root / rel
            self.assertTrue(dest.is_file(), f"managed target missing: {rel}")
            self.assertEqual(sha, sha256_file(dest), f"managed bytes differ: {rel}")
        config_text = (self.alpha / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("sage_profile_binding:", config_text)
        validation = self.hook_config.validate_candidate_config(config_text)
        self.assertTrue(validation["ok"], validation["errors"])

    def test_cli_init_writes_hermes_md_and_no_workspace_soul(self):
        result = self.run_init()
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-4000:])
        hermes_md = self.workspace / ".hermes.md"
        self.assertTrue(
            hermes_md.is_file(),
            "spec 5.2.2 instructions surface <workspace>/.hermes.md not written",
        )
        self.assertGreater(len(hermes_md.read_text(encoding="utf-8").strip()), 0)
        self.assertFalse(
            (self.workspace / "SOUL.md").exists(),
            "spec 3 forbids a workspace SOUL.md from Hermes-only generation",
        )

    def test_cli_init_leaves_sibling_and_global_byte_identical(self):
        result = self.run_init()
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-4000:])
        self.assertEqual(self.before_beta, tree_digest(self.beta))
        self.assertEqual(
            self.before_outside, digest_outside_profile(self.hermes_home, "alpha")
        )

    def test_cli_update_after_cli_init_commits_and_is_hash_idempotent(self):
        init = self.run_init()
        self.assertEqual(0, init.returncode, (init.stdout + init.stderr)[-4000:])
        _, receipt_before = self._load_receipt()
        hashes_before = {
            t.relative_path: t.sha256 for t in receipt_before.managed_targets
        }
        # Spec 5.1.6: a bare `sage update` reuses the receipt binding — the
        # whole point of the receipt is that update no longer needs the
        # selection flags re-passed.
        update = self.run_sage("update")
        output = update.stdout + update.stderr
        self.assertEqual(
            0,
            update.returncode,
            "sage update failed closed after a CLI init:\n" + output[-4000:],
        )
        self.assertNotIn("install receipt is required", output)
        _, receipt_after = self._load_receipt()
        hashes_after = {
            t.relative_path: t.sha256 for t in receipt_after.managed_targets
        }
        self.assertEqual(hashes_before, hashes_after)
        self.assertEqual(self.before_beta, tree_digest(self.beta))


if __name__ == "__main__":
    unittest.main(verbosity=2)
