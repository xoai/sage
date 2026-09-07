#!/usr/bin/env python3
"""
test_sage_init.py — `sage init` produces a project a machine can actually read.

Nothing checked what `sage init` WROTE. It is the single most-run command in the
framework, and it was emitting a `.sage/config.yaml` that no YAML parser accepts.

The heredoc that writes it, `cat > "$sage_dir/config.yaml" << YAML`, has an
unquoted delimiter, and a comment inside it contained backticks around
`sage worktree`. In an unquoted heredoc, backticks are command substitution — so
bash EXECUTED `sage worktree` while initializing the project and spliced its
ANSI-coloured usage text into the config. Every Sage project on earth has one.

It went unnoticed because the only consumers read config.yaml with line regexes
rather than a YAML parser, so the corruption was invisible until something tried
to parse it. These tests make sure the next one is caught by a machine.

Usage:  python3 develop/validators/tools/test_sage_init.py
Exit:   0 = all pass | 1 = a test failed

Python 3.8+, stdlib only (PyYAML is used for a real parse when available, and its
absence never turns a failure into a pass — the structural checks always run).
"""
from __future__ import annotations

import os
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SAGE_BIN = REPO_ROOT / "bin" / "sage"


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

ANSI = re.compile(r"\x1b\[")
# A YAML line that is not blank, not a comment, and not indented continuation.
TOP_LEVEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:")


def bash_path(path: pathlib.Path) -> str:
    """Return a path Bash can consume on both POSIX and Windows hosts."""
    return str(path).replace("\\", "/")


def fake_hermes_activation_env(root: pathlib.Path) -> dict:
    """Create an opaque public Hermes launcher for fresh-process proofs."""

    launcher = root / "fake-hermes.py"
    launcher.write_text(
        "import argparse\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "\n"
        "if sys.argv[-2:] == ['config', 'path']:\n"
        "    print(os.environ['FAKE_HERMES_CONFIG_PATH'])\n"
        "    raise SystemExit(0)\n"
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


def test_source_cli_precedes_an_implicit_stale_home_framework(tmp_path) -> None:
    stale = tmp_path / ".sage" / "framework"
    (stale / "core").mkdir(parents=True)
    (stale / "skills").mkdir()
    (stale / "VERSION").write_text("0.0.0-stale\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("SAGE_HOME", None)
    env["HOME"] = bash_path(tmp_path)

    result = subprocess.run(
        [BASH, bash_path(SAGE_BIN), "version"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == expected


def canonical_bash_path(path: pathlib.Path) -> str:
    result = subprocess.run(
        [BASH, "-c", 'cd "$1" && pwd -P', "sage-test", bash_path(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def tree_digest(root: pathlib.Path) -> dict:
    """Return a stable path/content inventory without following directory links."""
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[rel] = ("symlink", os.readlink(path))
        elif path.is_dir():
            result[rel] = ("dir", "")
        elif path.is_file():
            result[rel] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return result


class SageInitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="sage-init-test-"))
        home = cls.tmp / "home"
        (home).mkdir(parents=True)
        # A framework root the way install.sh lays one out.
        shutil.copytree(REPO_ROOT, home / "framework",
                        ignore=shutil.ignore_patterns(".git", "node_modules",
                                                      "__pycache__", "dist", ".sage"))
        cls.proj = cls.tmp / "proj"
        cls.proj.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=cls.proj, check=True)

        proc = subprocess.run(
            [BASH, bash_path(SAGE_BIN), "init", "--preset", "base"],
            cwd=cls.proj, capture_output=True, text=True,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "SAGE_HOME": bash_path(home)},
        )
        cls.rc, cls.out = proc.returncode, proc.stdout + proc.stderr
        cls.config = cls.proj / ".sage" / "config.yaml"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_init_succeeds(self):
        self.assertEqual(self.rc, 0, self.out[-2000:])

    def test_config_was_written(self):
        self.assertTrue(self.config.is_file(), self.out[-1000:])

    def test_config_has_no_terminal_escape_codes(self):
        """ANSI in a config file means some command's coloured output leaked in."""
        text = self.config.read_text()
        self.assertIsNone(ANSI.search(text),
                          "ANSI escape sequence in .sage/config.yaml — a command "
                          "substituted its output into the heredoc")

    def test_config_did_not_execute_a_subcommand(self):
        """`sage worktree` was really being RUN during init, not quoted."""
        text = self.config.read_text()
        for leak in ("Usage: sage", "sage worktree remove <"):
            self.assertNotIn(leak, text,
                             f"{leak!r} in config.yaml — a backtick inside the "
                             f"unquoted heredoc ran as a command")

    def test_config_is_parseable_yaml(self):
        text = self.config.read_text()
        try:
            import yaml
        except ImportError:
            # No parser here — fall back to a structural check rather than
            # skipping, so a missing library can never read as a pass.
            for i, line in enumerate(text.splitlines(), 1):
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if line[0].isspace():
                    continue          # a continuation / nested mapping
                self.assertRegex(line, TOP_LEVEL,
                                 f"line {i} is neither blank, comment, nor key: {line!r}")
            return
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as exc:
            self.fail(f".sage/config.yaml is not valid YAML: "
                      f"{str(exc).splitlines()[0]}")

    def test_version_is_stamped_from_the_VERSION_file(self):
        """Not a literal. bin/sage hardcoded 1.0.0 here while VERSION said 1.2.0,
        so every project misreported the Sage it was running."""
        version = (REPO_ROOT / "VERSION").read_text().strip()
        self.assertIn(f'sage-version: "{version}"', self.config.read_text())


class SageHermesProfileSelectionTest(unittest.TestCase):
    """Hermes CLI selection is explicit, single-profile, and pre-mutation."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="sage-hermes-selection-test-"))
        cls.sage_home = cls.tmp / "sage-home"
        cls.sage_home.mkdir()
        shutil.copytree(
            REPO_ROOT,
            cls.sage_home / "framework",
            ignore=shutil.ignore_patterns(
                ".git", "node_modules", "__pycache__", "dist", ".sage"
            ),
        )

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
        self.outside = self.case / "outside"
        self.outside.mkdir()
        self.env = {
            **os.environ,
            **fake_hermes_activation_env(self.case),
            "SAGE_HOME": bash_path(self.sage_home),
            "HERMES_HOME": bash_path(self.hermes_home),
        }

    def tearDown(self):
        shutil.rmtree(self.case, ignore_errors=True)

    def run_sage(self, *args, cwd=None, env=None):
        return subprocess.run(
            [BASH, bash_path(SAGE_BIN), *args],
            cwd=cwd or self.outside,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            env=env or self.env,
            check=False,
        )

    def test_migrate_requires_hermes_profile_subtarget(self):
        result = self.run_sage("migrate", "wrong-target")
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Usage: sage migrate hermes-profile", output)

    def test_migrate_requires_explicit_profile_selection(self):
        result = self.run_sage(
            "migrate", "hermes-profile",
            "--hermes-home", bash_path(self.hermes_home),
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Hermes profile selection is required", output)

    def test_migrate_rollback_requires_operation_id(self):
        workspace = self.hermes_home / "profiles" / "alpha" / "workspace"
        result = self.run_sage(
            "migrate", "hermes-profile", "--rollback",
            "--hermes-home", bash_path(self.hermes_home),
            "--hermes-profile", "alpha",
            cwd=workspace,
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--rollback requires an operation id", output)

    def test_help_advertises_explicit_hermes_migration(self):
        result = self.run_sage("help")
        self.assertEqual(0, result.returncode)
        self.assertIn("sage migrate hermes-profile", result.stdout)

    def test_hermes_profile_selection_missing_noninteractive_fails_before_writes(self):
        before_project = tree_digest(self.outside)
        before_home = tree_digest(self.hermes_home)
        result = self.run_sage(
            "init",
            "--preset",
            "base",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
        )
        output = result.stdout + result.stderr
        expected = (
            "sage init --platform hermes --hermes-home "
            f"{bash_path(self.hermes_home)} --hermes-profile <name>"
        )
        self.assertNotEqual(0, result.returncode, output[-4000:])
        self.assertIn("Hermes profile selection is required", output)
        self.assertIn(expected, output)
        self.assertEqual(before_project, tree_digest(self.outside))
        self.assertEqual(before_home, tree_digest(self.hermes_home))

    def test_hermes_profile_selection_unknown_platform_fails_before_writes(self):
        before_project = tree_digest(self.outside)
        before_home = tree_digest(self.hermes_home)
        result = self.run_sage(
            "init", "--no-memory", "--platform", "not-a-platform"
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output[-4000:])
        self.assertIn("Unknown platform: not-a-platform", output)
        self.assertEqual(before_project, tree_digest(self.outside))
        self.assertEqual(before_home, tree_digest(self.hermes_home))

    def test_hermes_init_without_consent_changes_no_workspace_or_profile_bytes(self):
        selected = self.hermes_home / "profiles" / "alpha"
        before_home = tree_digest(self.hermes_home)
        before_workspace = tree_digest(selected / "workspace")

        result = self.run_sage(
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
            cwd=selected / "workspace",
        )
        output = result.stdout + result.stderr

        self.assertNotEqual(0, result.returncode, output[-4000:])
        self.assertIn("requires explicit consent", output)
        self.assertEqual(before_home, tree_digest(self.hermes_home))
        self.assertEqual(before_workspace, tree_digest(selected / "workspace"))

    def test_hermes_home_is_discovered_from_the_public_profile_config_path(self):
        selected = self.hermes_home / "profiles" / "alpha"
        config_path = selected / "config.yaml"
        config_path.write_text("plugins:\n  enabled: []\n", encoding="utf-8")
        before_home = tree_digest(self.hermes_home)
        env = dict(self.env)
        env.pop("HERMES_HOME", None)
        env.pop("SAGE_YES", None)
        env["FAKE_HERMES_CONFIG_PATH"] = os.fspath(config_path)

        result = self.run_sage(
            "init",
            "--preset",
            "base",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-profile",
            "alpha",
            cwd=selected / "workspace",
            env=env,
        )
        output = result.stdout + result.stderr

        self.assertNotEqual(0, result.returncode, output[-4000:])
        self.assertIn("requires explicit consent", output)
        self.assertNotIn("collection root is required", output)
        self.assertEqual(before_home, tree_digest(self.hermes_home))

    def test_hermes_init_git_managed_plugin_refuses_before_workspace_state(self):
        selected = self.hermes_home / "profiles" / "alpha"
        plugin = selected / "plugins" / "sage"
        (plugin / ".git").mkdir(parents=True)
        (plugin / "USER-OWNED.txt").write_text("preserve\n", encoding="utf-8")
        before_home = tree_digest(self.hermes_home)
        before_workspace = tree_digest(selected / "workspace")
        env = {**self.env, "SAGE_YES": "1"}

        result = self.run_sage(
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
            cwd=selected / "workspace",
            env=env,
        )
        output = result.stdout + result.stderr

        self.assertNotEqual(0, result.returncode, output[-4000:])
        self.assertIn("Git repository/worktree", output)
        self.assertEqual(before_home, tree_digest(self.hermes_home))
        self.assertEqual(before_workspace, tree_digest(selected / "workspace"))

    def test_hermes_profile_selection_explicit_targets_only_one_profile(self):
        selected = self.hermes_home / "profiles" / "alpha"
        sibling = self.hermes_home / "profiles" / "beta"
        sibling_before = tree_digest(sibling)
        fake_bin = self.case / "bin"
        fake_bin.mkdir()
        fake_hermes = fake_bin / "hermes"
        fake_hermes.write_text(
            "#!/usr/bin/env sh\n"
            "case \"$*\" in *'plugins list'*) printf 'sage\\n' ;; esac\n"
            "exit 0\n",
            encoding="utf-8",
        )
        fake_hermes.chmod(0o755)
        env = {
            **self.env,
            "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
            # Transactional init (T26) installs through
            # profile_installer.install, which requires explicit consent.
            # This test verifies selection behavior, not the consent prompt.
            "SAGE_YES": "1",
        }
        result = self.run_sage(
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
            cwd=selected / "workspace",
            env=env,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-4000:])
        workspace_config = selected / "workspace" / ".sage" / "config.yaml"
        self.assertIn('platforms: ["hermes"]', workspace_config.read_text())
        self.assertTrue((selected / "plugins" / "sage" / "plugin.yaml").is_file())
        self.assertTrue((selected / "config.yaml").is_file())
        profile_config = (selected / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("sage_profile_binding:", profile_config)
        self.assertIn('  profile_id: "alpha"', profile_config)
        self.assertIn("workspace_root:", profile_config)
        self.assertIn("state_root:", profile_config)
        self.assertIn("memory_root:", profile_config)
        self.assertIn("receipt_path:", profile_config)
        install_receipt = json.loads(
            (selected / "workspace" / ".sage" / "receipts" / "install.json").read_text(
                encoding="utf-8"
            )
        )
        owned = {
            (entry["owner"], entry["path"])
            for entry in install_receipt["managed_targets"]
        }
        self.assertIn(("workspace", ".hermes.md"), owned)
        self.assertIn(("workspace", "sage/VERSION"), owned)
        self.assertEqual(12, len(install_receipt["config_records"]))
        self.assertEqual(12, len(install_receipt["allowlist_records"]))
        self.assertIn("Profile: alpha", output)
        self.assertNotIn("command not found", output)
        self.assertNotIn("can't open file", output)
        self.assertNotIn("tr: warning", output)
        self.assertEqual(sibling_before, tree_digest(sibling))

    def test_hermes_profile_selection_generator_requires_binding_before_writes(self):
        generator = (
            self.sage_home
            / "framework"
            / "runtime"
            / "platforms"
            / "community"
            / "hermes"
            / "setup"
            / "generate-hermes.sh"
        )
        before_project = tree_digest(self.outside)
        before_home = tree_digest(self.hermes_home)
        result = subprocess.run(
            [BASH, bash_path(generator), bash_path(self.outside)],
            cwd=self.outside,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            env=self.env,
            check=False,
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output[-4000:])
        self.assertIn("explicit Hermes profile binding is required", output)
        self.assertEqual(before_project, tree_digest(self.outside))
        self.assertEqual(before_home, tree_digest(self.hermes_home))

    def test_hermes_profile_selection_duplicate_flags_fail_before_writes(self):
        before_project = tree_digest(self.outside)
        before_home = tree_digest(self.hermes_home)
        result = self.run_sage(
            "init",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
            "--hermes-profile",
            "alpha",
            "--hermes-profile",
            "beta",
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output[-4000:])
        self.assertIn("--hermes-profile may be provided only once", output)
        self.assertEqual(before_project, tree_digest(self.outside))
        self.assertEqual(before_home, tree_digest(self.hermes_home))

    def test_hermes_profile_selection_normalizes_profile_scoped_hermes_home(self):
        selected = self.hermes_home / "profiles" / "alpha"
        fixture_home = self.case / "fixture-sage-home"
        shutil.copytree(self.sage_home / "framework", fixture_home / "framework")
        generator = (
            fixture_home
            / "framework"
            / "runtime"
            / "platforms"
            / "community"
            / "hermes"
            / "setup"
            / "generate-hermes.sh"
        )
        generator.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "printf 'collection=%s\\nprofile=%s\\nroot=%s\\nworkspace=%s\\n' "
            '"$SAGE_HERMES_COLLECTION_ROOT" "$SAGE_HERMES_PROFILE" '
            '"$SAGE_HERMES_PROFILE_ROOT" "$SAGE_HERMES_WORKSPACE_ROOT" '
            '> "$1/hermes-selection.txt"\n'
            # Transactional init (T26): the install transaction reads the
            # binding authority out of the profile config, so the stub must
            # emit it exactly as the real generator does (native spelling).
            'WS_NATIVE="$SAGE_HERMES_WORKSPACE_ROOT"\n'
            'if command -v cygpath >/dev/null 2>&1; then\n'
            '  WS_NATIVE="$(cygpath -m "$SAGE_HERMES_WORKSPACE_ROOT")"\n'
            'fi\n'
            '{\n'
            '  printf "\\nsage_profile_binding:\\n"\n'
            '  printf "  profile_id: \\"%s\\"\\n" "$SAGE_HERMES_PROFILE"\n'
            '  printf "  workspace_root: \\"%s\\"\\n" "$WS_NATIVE"\n'
            '  printf "  state_root: \\"%s/.sage\\"\\n" "$WS_NATIVE"\n'
            '  printf "  memory_root: \\"%s/.sage-memory\\"\\n" "$WS_NATIVE"\n'
            '  printf "  receipt_path: \\"%s/.sage/receipts/install.json\\"\\n" "$WS_NATIVE"\n'
            '} >> "$SAGE_HERMES_PROFILE_ROOT/config.yaml"\n',
            encoding="utf-8",
        )
        generator.chmod(0o755)
        env = {
            **self.env,
            "SAGE_HOME": bash_path(fixture_home),
            "HERMES_HOME": bash_path(self.hermes_home / "profiles" / "beta"),
            # Transactional init requires explicit consent (see above).
            "SAGE_YES": "1",
        }
        result = self.run_sage(
            "init",
            "--preset",
            "base",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-profile",
            "alpha",
            cwd=selected / "workspace",
            env=env,
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-4000:])
        receipt_path = selected / "workspace" / ".sage" / "receipts" / "install.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("alpha", receipt["binding"]["profile_id"])
        self.assertEqual(
            os.path.normcase(os.path.normpath(str(self.hermes_home))),
            os.path.normcase(
                os.path.normpath(receipt["binding"]["collection_root"])
            ),
        )

    def test_hermes_profile_selection_requires_unambiguous_collection_root(self):
        selected = self.hermes_home / "profiles" / "alpha"
        empty_home = self.case / "empty-user-home"
        empty_home.mkdir()
        env = {**self.env, "HOME": bash_path(empty_home)}
        env.pop("HERMES_HOME", None)
        before_workspace = tree_digest(selected / "workspace")
        before_home = tree_digest(self.hermes_home)
        result = self.run_sage(
            "init",
            "--platform",
            "hermes",
            "--hermes-profile",
            "alpha",
            cwd=selected / "workspace",
            env=env,
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output[-4000:])
        self.assertIn("Hermes collection root is required", output)
        self.assertIn("--hermes-home <collection>", output)
        self.assertEqual(before_workspace, tree_digest(selected / "workspace"))
        self.assertEqual(before_home, tree_digest(self.hermes_home))

    def test_hermes_profile_selection_rejects_noncanonical_profile_id(self):
        before_project = tree_digest(self.outside)
        before_home = tree_digest(self.hermes_home)
        result = self.run_sage(
            "init",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
            "--hermes-profile",
            "Alpha.profile",
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output[-4000:])
        self.assertIn("Invalid Hermes profile name", output)
        self.assertEqual(before_project, tree_digest(self.outside))
        self.assertEqual(before_home, tree_digest(self.hermes_home))

    def test_hermes_profile_selection_help_documents_flags_and_native_form(self):
        result = self.run_sage("help")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--hermes-profile <name>", result.stdout)
        self.assertIn("--hermes-home <path>", result.stdout)
        self.assertIn(
            "cd <hermes-home>/profiles/<profile>/workspace && sage init "
            "--platform hermes --hermes-home <hermes-home> "
            "--hermes-profile <profile>",
            result.stdout,
        )
        # Shipped help must never carry live-machine paths or real profile
        # names (privacy scan T24 finding).
        self.assertNotIn("/g/hermes", result.stdout)
        self.assertNotIn("rei-stewart", result.stdout)


class SageHermesUpdateBindingTest(unittest.TestCase):
    """Framework upgrades and receipt-bound profile updates are distinct."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="sage-hermes-update-test-"))
        cls.sage_home = cls.tmp / "sage-home"
        cls.sage_home.mkdir()
        shutil.copytree(
            REPO_ROOT,
            cls.sage_home / "framework",
            ignore=shutil.ignore_patterns(
                ".git", "node_modules", "__pycache__", "dist", ".sage"
            ),
        )

        setup_root = (
            REPO_ROOT
            / "runtime"
            / "platforms"
            / "community"
            / "hermes"
            / "setup"
        )
        import importlib.util

        binding_spec = importlib.util.spec_from_file_location(
            "test_profile_binding", setup_root / "profile_binding.py"
        )
        module = importlib.util.module_from_spec(binding_spec)
        sys.modules[binding_spec.name] = module
        binding_spec.loader.exec_module(module)
        cls.ProfileBinding = module.ProfileBinding

        # Build update fixtures through the same strict receipt type consumed by
        # profile_installer.update. Hand-written schema stubs silently drifted
        # when transactional receipts became authoritative.
        prior_profile_binding = sys.modules.get("profile_binding")
        sys.modules["profile_binding"] = module
        try:
            receipts_spec = importlib.util.spec_from_file_location(
                "test_update_receipts", setup_root / "receipts.py"
            )
            if receipts_spec is None or receipts_spec.loader is None:
                raise RuntimeError("could not load canonical Hermes receipt module")
            receipts_module = importlib.util.module_from_spec(receipts_spec)
            sys.modules[receipts_spec.name] = receipts_module
            receipts_spec.loader.exec_module(receipts_module)
        finally:
            if prior_profile_binding is None:
                sys.modules.pop("profile_binding", None)
            else:
                sys.modules["profile_binding"] = prior_profile_binding
        cls.receipts = receipts_module

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.case = pathlib.Path(tempfile.mkdtemp(dir=self.tmp, prefix="case-"))
        self.hermes_home = self.case / "hermes"
        for profile in ("alpha", "beta"):
            workspace = self.hermes_home / "profiles" / profile / "workspace"
            (workspace / ".sage" / "receipts").mkdir(parents=True)
            (workspace / "sage").mkdir()
            (workspace / "sage" / "STALE").write_text(profile, encoding="utf-8")
            (workspace / ".sage" / "config.yaml").write_text(
                'platforms: ["hermes"]\n'
                'sage-version: "1.3.18"\n'
                "hard_enforcement: true\n"
                "tdd_enforcement: true\n"
                "review_loop:\n  mode: v2\n",
                encoding="utf-8",
            )
        self.alpha = self._binding("alpha")
        self.beta = self._binding("beta")
        self._write_receipt(self.alpha.workspace_root, self.alpha)
        self._write_receipt(self.beta.workspace_root, self.beta)
        self._write_config_binding(self.alpha)
        self._write_config_binding(self.beta)
        (self.sage_home / "framework" / "TASK7-SENTINEL").write_text(
            "shared-framework", encoding="utf-8"
        )
        self.env = {
            **os.environ,
            **fake_hermes_activation_env(self.case),
            "SAGE_HOME": bash_path(self.sage_home),
            "HERMES_HOME": bash_path(self.hermes_home),
            # These tests exercise receipt-bound update behavior, not the
            # interactive consent prompt. Missing-consent rollback is covered
            # by the hook-policy activation tests.
            "SAGE_YES": "1",
        }

    def tearDown(self):
        shutil.rmtree(self.case, ignore_errors=True)
        (self.sage_home / "framework" / "TASK7-SENTINEL").unlink(missing_ok=True)

    def _binding(self, profile):
        profile_root = self.hermes_home / "profiles" / profile
        return self.ProfileBinding.from_explicit(
            collection_root=self.hermes_home,
            profile_id=profile,
            profile_root=profile_root,
            workspace_root=profile_root / "workspace",
        )

    def _write_receipt(self, workspace, binding):
        self.assertEqual(workspace, binding.workspace_root)
        receipt = self.receipts.InstallReceipt.create(
            binding=binding,
            source_version="1.3.18",
            source_commit="0" * 40,
            managed_targets=(),
            config_records=(),
            allowlist_records=(),
        )
        self.receipts.write_install_receipt(binding, receipt)

    def _forge_receipt_at(self, path, binding):
        # Simulate a drifted receipt naming a different binding. The strict
        # receipt writer refuses cross-binding writes by design, so the
        # conflict fixture must be forged from raw bytes exactly as a
        # corrupted or migrated state would appear on disk.
        receipt = self.receipts.InstallReceipt.create(
            binding=binding,
            source_version="1.3.18",
            source_commit="0" * 40,
            managed_targets=(),
            config_records=(),
            allowlist_records=(),
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt.to_mapping(), indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _write_config_binding(binding):
        config = binding.config_path
        config.parent.mkdir(parents=True, exist_ok=True)
        lines = ["sage_profile_binding:"]
        for key, value in binding.to_config_mapping().items():
            lines.append(f"  {key}: {json.dumps(value)}")
        config.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run_sage(self, *args, cwd=None, env=None):
        return subprocess.run(
            [BASH, bash_path(SAGE_BIN), *args],
            cwd=cwd or self.alpha.workspace_root,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            env=env or self.env,
            check=False,
        )

    def test_hermes_update_without_consent_changes_no_workspace_or_profile_bytes(self):
        before_home = tree_digest(self.hermes_home)
        before_workspace = tree_digest(self.alpha.workspace_root)
        env = dict(self.env)
        env.pop("SAGE_YES", None)

        result = self.run_sage(
            "update",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
            "--hermes-profile",
            "alpha",
            env=env,
        )
        output = result.stdout + result.stderr

        self.assertNotEqual(0, result.returncode, output[-5000:])
        self.assertIn("requires explicit consent", output)
        self.assertEqual(before_home, tree_digest(self.hermes_home))
        self.assertEqual(before_workspace, tree_digest(self.alpha.workspace_root))

    def test_hermes_update_binding_matching_profile_does_not_replace_shared_framework(self):
        sibling_before = tree_digest(self.beta.profile_root)
        framework_sentinel = self.sage_home / "framework" / "TASK7-SENTINEL"
        result = self.run_sage(
            "update",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
            "--hermes-profile",
            "alpha",
        )
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-5000:])
        self.assertIn("Hermes profile update", output)
        self.assertIn("shared framework unchanged", output)
        self.assertEqual("shared-framework", framework_sentinel.read_text())
        self.assertEqual(sibling_before, tree_digest(self.beta.profile_root))
        receipt = self.receipts.load_install_receipt(self.alpha)
        self.assertEqual("alpha", receipt.binding.profile_id)
        self.assertTrue(receipt.managed_targets)
        self.assertTrue((self.alpha.plugin_root / "plugin.yaml").is_file())

    def test_hermes_update_binding_bare_update_reuses_receipt(self):
        result = self.run_sage("update", "--no-memory")
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-5000:])
        self.assertIn("Hermes profile update", output)
        receipt = self.receipts.load_install_receipt(self.alpha)
        self.assertEqual("alpha", receipt.binding.profile_id)
        self.assertTrue(receipt.managed_targets)
        self.assertTrue((self.alpha.plugin_root / "plugin.yaml").is_file())

    def test_hermes_update_binding_conflict_names_both_and_fails_before_writes(self):
        self._forge_receipt_at(self.alpha.receipt_path, self.beta)
        workspace_before = tree_digest(self.alpha.workspace_root)
        profiles_before = tree_digest(self.hermes_home)
        result = self.run_sage(
            "update",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
            "--hermes-profile",
            "alpha",
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output[-5000:])
        self.assertIn("Existing Hermes binding", output)
        self.assertIn("Requested Hermes binding", output)
        self.assertIn("profile_id: beta", output)
        self.assertIn("profile_id: alpha", output)
        self.assertIn("sage migrate hermes-profile", output)
        self.assertEqual(workspace_before, tree_digest(self.alpha.workspace_root))
        self.assertEqual(profiles_before, tree_digest(self.hermes_home))

    def test_hermes_update_binding_explicit_cli_conflict_names_both_before_writes(self):
        workspace_before = tree_digest(self.alpha.workspace_root)
        profiles_before = tree_digest(self.hermes_home)
        result = self.run_sage(
            "update",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
            "--hermes-profile",
            "beta",
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output[-5000:])
        self.assertIn("Existing Hermes binding", output)
        self.assertIn("Requested Hermes binding", output)
        self.assertIn("profile_id: alpha", output)
        self.assertIn("profile_id: beta", output)
        self.assertIn("sage migrate hermes-profile", output)
        self.assertEqual(workspace_before, tree_digest(self.alpha.workspace_root))
        self.assertEqual(profiles_before, tree_digest(self.hermes_home))

    def test_hermes_update_accepts_hermes_redumped_plain_config_binding(self):
        # Hermes config writers re-dump Sage's JSON-quoted binding values as
        # plain YAML scalars. The update path must still authorize the exact
        # receipt-bound binding after that round-trip.
        config = self.alpha.config_path
        lines = ["sage_profile_binding:"]
        for key, value in self.alpha.to_config_mapping().items():
            lines.append(f"  {key}: {value}")
        config.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = self.run_sage("update", "--no-memory")
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-5000:])
        self.assertIn("Hermes profile update", output)
        receipt = self.receipts.load_install_receipt(self.alpha)
        self.assertEqual("alpha", receipt.binding.profile_id)

    def test_hermes_update_binding_missing_receipt_fails_before_writes(self):
        self.alpha.receipt_path.unlink()
        workspace_before = tree_digest(self.alpha.workspace_root)
        profiles_before = tree_digest(self.hermes_home)
        result = self.run_sage(
            "update",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
            "--hermes-profile",
            "alpha",
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output[-5000:])
        self.assertIn("Hermes install receipt is required", output)
        self.assertEqual(workspace_before, tree_digest(self.alpha.workspace_root))
        self.assertEqual(profiles_before, tree_digest(self.hermes_home))

    def test_hermes_update_binding_missing_profile_config_authority_fails_before_writes(self):
        self.alpha.config_path.unlink()
        workspace_before = tree_digest(self.alpha.workspace_root)
        profiles_before = tree_digest(self.hermes_home)
        result = self.run_sage(
            "update",
            "--no-memory",
            "--platform",
            "hermes",
            "--hermes-home",
            bash_path(self.hermes_home),
            "--hermes-profile",
            "alpha",
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output[-5000:])
        self.assertIn("Hermes profile config binding is required", output)
        self.assertEqual(workspace_before, tree_digest(self.alpha.workspace_root))
        self.assertEqual(profiles_before, tree_digest(self.hermes_home))

    def test_hermes_recover_exposes_incomplete_transaction_resume(self):
        installer_module = (
            self.sage_home
            / "framework"
            / "runtime"
            / "platforms"
            / "community"
            / "hermes"
            / "setup"
            / "profile_installer.py"
        )
        original = installer_module.read_bytes()
        marker = self.case / "recover-marker.json"
        installer_module.write_text(
            "import json\n"
            "import os\n"
            "import pathlib\n"
            "def resume_incomplete(*, binding, operation_id):\n"
            "    pathlib.Path(os.environ['SAGE_RECOVERY_MARKER']).write_text(\n"
            "        json.dumps({'profile_id': binding.profile_id, 'operation_id': operation_id}),\n"
            "        encoding='utf-8',\n"
            "    )\n"
            "    return {'restored': True, 'operation_id': operation_id}\n",
            encoding="utf-8",
        )
        env = {**self.env, "SAGE_RECOVERY_MARKER": os.fspath(marker)}
        try:
            result = self.run_sage(
                "recover",
                "hermes-profile",
                "op-123",
                "--hermes-home",
                bash_path(self.hermes_home),
                "--hermes-profile",
                "alpha",
                env=env,
            )
        finally:
            installer_module.write_bytes(original)

        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-5000:])
        self.assertIn("Hermes profile recovery complete", output)
        self.assertEqual(
            {"profile_id": "alpha", "operation_id": "op-123"},
            json.loads(marker.read_text(encoding="utf-8")),
        )
        help_result = self.run_sage("help")
        self.assertIn("sage recover hermes-profile", help_result.stdout)

    def test_hermes_update_binding_framework_upgrade_does_not_mutate_profiles(self):
        upgrade_home = self.case / "upgrade-home"
        shutil.copytree(self.sage_home / "framework", upgrade_home / "framework")
        installer = upgrade_home / "framework" / "install.sh"
        installer.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            'printf upgraded > "$SAGE_HOME/framework/UPGRADED"\n',
            encoding="utf-8",
        )
        installer.chmod(0o755)
        profiles_before = tree_digest(self.hermes_home)
        env = {**self.env, "SAGE_HOME": bash_path(upgrade_home)}
        result = self.run_sage("upgrade", cwd=self.case, env=env)
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output[-5000:])
        self.assertIn("Shared framework upgrade", output)
        self.assertIn("Hermes profiles unchanged", output)
        self.assertTrue((upgrade_home / "framework" / "UPGRADED").is_file())
        self.assertEqual(profiles_before, tree_digest(self.hermes_home))


if __name__ == "__main__":
    unittest.main(verbosity=2)
