"""Parity test: Bash fallback must produce identical output to Python parser.

The agent only trusts the JSON shape — both runtimes must emit the
exact same JSON for the same input.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core.flag_parser.config_loader import load_defaults
from core.flag_parser.parser import parse

PARSE_SH = Path(__file__).parent.parent / "parse.sh"


# ── Cases without config defaults ────────────────────────────────────

CASES_NO_CONFIG = [
    "",
    "ship dark mode",
    "--quality-locked ship dark mode",
    "--autonomous design billing v2",
    "--quality-locked --autonomous ship feature",
    "--autonomous --quality-locked ship feature",
    "--quality-locked",
    "--autonomous",
    "ship --quality-locked feature",  # flag not at start
    "   --quality-locked    ship    feature   ",
    "--no-quality-locked fix typo",
    "--no-autonomous design",
    "--quality-locked --no-autonomous mixed",
]


def _bash_parse(args: str, config_path: str | None = None) -> tuple[dict, int]:
    cmd = ["bash", str(PARSE_SH), args]
    if config_path is not None:
        cmd += ["--config-path", config_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout.strip()), result.returncode


def _python_parse(args: str, config_path: str | None = None) -> tuple[dict, int]:
    defaults = load_defaults(config_path) if config_path else {}
    r = parse(args, defaults=defaults)
    exit_code = 1 if r.error else 0
    return r.to_dict(), exit_code


@pytest.mark.parametrize("args", CASES_NO_CONFIG)
def test_python_and_bash_agree_no_config(args):
    py_dict, py_exit = _python_parse(args)
    bash_dict, bash_exit = _bash_parse(args)
    assert py_dict == bash_dict, f"Mismatch for input: {args!r}"
    assert py_exit == bash_exit, f"Exit code mismatch for input: {args!r}"


def test_unknown_flag_parity():
    py_dict, py_exit = _python_parse("--foo bar")
    bash_dict, bash_exit = _bash_parse("--foo bar")
    assert py_exit == 1
    assert bash_exit == 1
    # Both should have the same shape (key set + values). Error message
    # content may differ slightly; just verify both populate error.
    assert py_dict["error"] is not None
    assert bash_dict["error"] is not None
    assert py_dict["quality_locked"] == bash_dict["quality_locked"] is False
    assert py_dict["autonomous"] == bash_dict["autonomous"] is False


def test_typo_flag_parity():
    py_dict, py_exit = _python_parse("--quality-lock ship")
    bash_dict, bash_exit = _bash_parse("--quality-lock ship")
    assert py_exit == bash_exit == 1
    assert py_dict["error"] is not None
    assert bash_dict["error"] is not None


def test_conflict_parity():
    """Both runtimes detect --X / --no-X conflict."""
    py_dict, py_exit = _python_parse("--quality-locked --no-quality-locked ship")
    bash_dict, bash_exit = _bash_parse("--quality-locked --no-quality-locked ship")
    assert py_exit == bash_exit == 1
    assert py_dict["error"] is not None
    assert bash_dict["error"] is not None


# ── Cases with config defaults ───────────────────────────────────────

@pytest.fixture
def config_ql_true(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("project-name: test\nquality_locked: true\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def config_both_true(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("quality_locked: true\nautonomous: true\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def config_malformed(tmp_path):
    """Variants that the strict-match rejects — should be no-default."""
    p = tmp_path / "config.yaml"
    p.write_text('quality_locked: "true"\nautonomous: True\n', encoding="utf-8")
    return str(p)


@pytest.fixture
def config_empty(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("", encoding="utf-8")
    return str(p)


CASES_WITH_CONFIG = [
    ("",),                                # bare goal, config provides defaults
    ("ship it",),
    ("--no-quality-locked override",),    # explicit off overrides config
    ("--quality-locked agree",),           # flag agrees with config; source = flag
    ("--autonomous add",),                 # combine flag with config default
]


@pytest.mark.parametrize("case", CASES_WITH_CONFIG)
def test_python_and_bash_agree_with_ql_config(case, config_ql_true):
    args = case[0]
    py_dict, py_exit = _python_parse(args, config_ql_true)
    bash_dict, bash_exit = _bash_parse(args, config_ql_true)
    assert py_dict == bash_dict, f"Mismatch for {args!r} with config_ql_true"
    assert py_exit == bash_exit


@pytest.mark.parametrize("case", CASES_WITH_CONFIG)
def test_python_and_bash_agree_with_both_config(case, config_both_true):
    args = case[0]
    py_dict, py_exit = _python_parse(args, config_both_true)
    bash_dict, bash_exit = _bash_parse(args, config_both_true)
    assert py_dict == bash_dict, f"Mismatch for {args!r} with config_both_true"


def test_malformed_config_no_defaults_both_runtimes(config_malformed):
    """Both runtimes treat strict-match-rejected values as no default."""
    py_dict, py_exit = _python_parse("ship", config_malformed)
    bash_dict, bash_exit = _bash_parse("ship", config_malformed)
    assert py_dict == bash_dict
    assert py_dict["quality_locked"] is False
    assert py_dict["quality_locked_source"] is None
    assert py_dict["autonomous"] is False
    assert py_dict["autonomous_source"] is None


def test_empty_config_no_defaults(config_empty):
    py_dict, py_exit = _python_parse("ship", config_empty)
    bash_dict, bash_exit = _bash_parse("ship", config_empty)
    assert py_dict == bash_dict
    assert py_dict["quality_locked"] is False
    assert py_dict["autonomous"] is False


def test_missing_config_no_crash(tmp_path):
    nonexistent = str(tmp_path / "does-not-exist.yaml")
    py_dict, py_exit = _python_parse("ship", nonexistent)
    bash_dict, bash_exit = _bash_parse("ship", nonexistent)
    assert py_dict == bash_dict
    assert py_exit == bash_exit == 0
