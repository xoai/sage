#!/usr/bin/env python3
"""Real bin/sage contracts for Hermes migrate and doctor lifecycle routing.

The transaction modules already have deep unit coverage. These tests instead
instrument a disposable installed Sage framework and execute the real Bash CLI,
so callback-shape and host-context wiring bugs cannot hide behind direct Python
module tests.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SAGE_BIN = REPO_ROOT / "bin" / "sage"


def _find_bash() -> str:
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
                return os.fspath(candidate)
    return shutil.which("bash") or "bash"


BASH = _find_bash()


def _bash_path(path: pathlib.Path) -> str:
    return os.fspath(path).replace("\\", "/")


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture()
def routed_cli(tmp_path: pathlib.Path):
    """Build an installed-framework shape with instrumented lifecycle modules."""

    sage_home = tmp_path / "sage-home"
    framework = sage_home / "framework"
    shutil.copytree(
        REPO_ROOT,
        framework,
        ignore=shutil.ignore_patterns(
            ".git", "node_modules", "__pycache__", "dist", ".sage"
        ),
    )
    setup = framework / "runtime" / "platforms" / "community" / "hermes" / "setup"
    record = tmp_path / "route-record.json"

    _write(
        setup / "profile_binding.py",
        "from __future__ import annotations\n"
        "import pathlib\n"
        "\n"
        "class ProfileBinding:\n"
        "    @classmethod\n"
        "    def from_explicit(cls, **values):\n"
        "        obj = cls()\n"
        "        for key, value in values.items():\n"
        "            setattr(obj, key, pathlib.Path(value) if key.endswith('_root') else value)\n"
        "        obj.receipt_path = obj.workspace_root / '.sage' / 'receipts' / 'install.json'\n"
        "        return obj\n",
    )
    _write(
        setup / "activation.py",
        "from __future__ import annotations\n"
        "import os\n"
        "\n"
        "class ActivationError(RuntimeError):\n"
        "    pass\n"
        "\n"
        "def resolve_hermes_command():\n"
        "    return (os.environ['SAGE_TEST_HERMES_COMMAND'],)\n"
        "\n"
        "def callbacks(binding, hermes_command):\n"
        "    assert binding.profile_id == 'alpha'\n"
        "    assert tuple(hermes_command) == resolve_hermes_command()\n"
        "    def probe(**_kwargs):\n"
        "        return {'ok': True, 'fresh_process_verified': True}\n"
        "    probe.sage_callback_kind = 'probe'\n"
        "    def rollback(**_kwargs):\n"
        "        return None\n"
        "    rollback.sage_callback_kind = 'rollback'\n"
        "    return probe, rollback\n",
    )
    _write(
        setup / "profile_migration.py",
        "from __future__ import annotations\n"
        "import json\n"
        "import os\n"
        "import pathlib\n"
        "\n"
        "class MigrationError(RuntimeError):\n"
        "    pass\n"
        "\n"
        "def _record(value):\n"
        "    pathlib.Path(os.environ['SAGE_TEST_ROUTE_RECORD']).write_text(\n"
        "        json.dumps(value, sort_keys=True), encoding='utf-8')\n"
        "\n"
        "def default_backup_root(binding):\n"
        "    return binding.collection_root.parent / 'backups'\n"
        "\n"
        "def migrate_receiptless_profile(**kwargs):\n"
        "    probe = kwargs['activation_probe']\n"
        "    rollback = kwargs['activation_rollback']\n"
        "    assert getattr(probe, 'sage_callback_kind', None) == 'probe'\n"
        "    assert getattr(rollback, 'sage_callback_kind', None) == 'rollback'\n"
        "    _record({'route': 'migrate', 'profile': kwargs['binding'].profile_id,\n"
        "             'probe': probe.sage_callback_kind,\n"
        "             'rollback': rollback.sage_callback_kind})\n"
        "    return {'ok': True, 'operation_id': 'migration-route-ok'}\n"
        "\n"
        "def rollback_receiptless_profile(**kwargs):\n"
        "    rollback = kwargs['activation_rollback']\n"
        "    assert getattr(rollback, 'sage_callback_kind', None) == 'rollback'\n"
        "    _record({'route': 'rollback', 'profile': kwargs['binding'].profile_id,\n"
        "             'operation_id': kwargs['operation_id'],\n"
        "             'rollback': rollback.sage_callback_kind})\n"
        "    return {'ok': True, 'operation_id': kwargs['operation_id']}\n",
    )
    _write(
        setup / "doctor_probe.py",
        "from __future__ import annotations\n"
        "import json\n"
        "import os\n"
        "import pathlib\n"
        "\n"
        "class ProbeError(RuntimeError):\n"
        "    pass\n"
        "\n"
        "def probe(**kwargs):\n"
        "    pathlib.Path(os.environ['SAGE_TEST_ROUTE_RECORD']).write_text(\n"
        "        json.dumps({\n"
        "            'route': 'doctor',\n"
        "            'profile': kwargs['binding'].profile_id,\n"
        "            'hermes_command': list(kwargs['hermes_command']),\n"
        "        }, sort_keys=True), encoding='utf-8')\n"
        "    return {'fresh_process_verified': True, 'read_only': True, 'checks': {}}\n",
    )
    _write(
        setup / "doctor.py",
        "def diagnose(binding, *, bash_path, behavioral_probe=None):\n"
        "    evidence = behavioral_probe(binding=binding)\n"
        "    ok = evidence.get('fresh_process_verified') is True\n"
        "    return {\n"
        "        'ok': ok,\n"
        "        'roots': {\n"
        "            'collection_root': str(binding.collection_root),\n"
        "            'profile_root': str(binding.profile_root),\n"
        "            'workspace_root': str(binding.workspace_root),\n"
        "            'receipt_path': str(binding.receipt_path),\n"
        "        },\n"
        "        'checks': [],\n"
        "    }\n",
    )
    _write(
        framework / "runtime" / "tools" / "build_plugin.py",
        "import argparse\n"
        "import pathlib\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--target')\n"
        "parser.add_argument('--out', required=True)\n"
        "args = parser.parse_args()\n"
        "pathlib.Path(args.out).mkdir(parents=True, exist_ok=True)\n",
    )

    collection = tmp_path / "hermes"
    profile = collection / "profiles" / "alpha"
    workspace = profile / "workspace"
    workspace.mkdir(parents=True)
    _write(profile / "config.yaml", "# disposable profile\n")

    env = {
        **os.environ,
        "SAGE_HOME": _bash_path(sage_home),
        "HERMES_HOME": _bash_path(collection),
        "SAGE_TEST_HERMES_COMMAND": os.fspath(pathlib.Path(sys.executable).resolve()),
        "SAGE_TEST_ROUTE_RECORD": os.fspath(record),
        "SAGE_YES": "1",
        "NO_COLOR": "1",
    }

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        record.unlink(missing_ok=True)
        return subprocess.run(
            [BASH, _bash_path(SAGE_BIN), *args],
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )

    return run, record, collection


def _selection(collection: pathlib.Path) -> list[str]:
    return [
        "--hermes-home",
        _bash_path(collection),
        "--hermes-profile",
        "alpha",
    ]


def test_real_cli_migration_binds_and_unpacks_activation_callbacks(routed_cli) -> None:
    run, record, collection = routed_cli

    completed = run("migrate", "hermes-profile", *_selection(collection))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(record.read_text(encoding="utf-8")) == {
        "route": "migrate",
        "profile": "alpha",
        "probe": "probe",
        "rollback": "rollback",
    }


def test_real_cli_migration_rollback_receives_bound_rollback_callback(routed_cli) -> None:
    run, record, collection = routed_cli

    completed = run(
        "migrate",
        "hermes-profile",
        "--rollback",
        "migration-123",
        *_selection(collection),
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(record.read_text(encoding="utf-8")) == {
        "route": "rollback",
        "profile": "alpha",
        "operation_id": "migration-123",
        "rollback": "rollback",
    }


def test_real_cli_doctor_uses_only_public_hermes_command(routed_cli) -> None:
    run, record, collection = routed_cli

    completed = run(
        "doctor",
        "--platform",
        "hermes",
        *_selection(collection),
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    route = json.loads(record.read_text(encoding="utf-8"))
    assert route == {
        "route": "doctor",
        "profile": "alpha",
        "hermes_command": [os.fspath(pathlib.Path(sys.executable).resolve())],
    }
