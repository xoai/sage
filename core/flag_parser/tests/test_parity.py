"""Parity test: Bash fallback must produce identical output to Python parser.

The agent only trusts the JSON shape — both runtimes must emit the
exact same JSON for the same input.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core.flag_parser.parser import parse

PARSE_SH = Path(__file__).parent.parent / "parse.sh"

CASES = [
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
]


def _bash_parse(args: str) -> tuple[dict, int]:
    """Invoke the bash fallback and return parsed JSON + exit code."""
    result = subprocess.run(
        ["bash", str(PARSE_SH), args],
        capture_output=True, text=True,
    )
    return json.loads(result.stdout.strip()), result.returncode


def _python_parse(args: str) -> tuple[dict, int]:
    """Invoke the Python parser and return result dict + exit code."""
    r = parse(args)
    exit_code = 1 if r.error else 0
    return r.to_dict(), exit_code


@pytest.mark.parametrize("args", CASES)
def test_python_and_bash_agree(args):
    py_dict, py_exit = _python_parse(args)
    bash_dict, bash_exit = _bash_parse(args)
    assert py_dict == bash_dict, f"Mismatch for input: {args!r}"
    assert py_exit == bash_exit, f"Exit code mismatch for input: {args!r}"


def test_unknown_flag_parity():
    py_dict, py_exit = _python_parse("--foo bar")
    bash_dict, bash_exit = _bash_parse("--foo bar")
    assert py_exit == 1
    assert bash_exit == 1
    # Both should have the same error message structure
    assert py_dict["error"] == bash_dict["error"]
    assert py_dict["quality_locked"] == bash_dict["quality_locked"] is False
    assert py_dict["autonomous"] == bash_dict["autonomous"] is False


def test_typo_flag_parity():
    py_dict, py_exit = _python_parse("--quality-lock ship")
    bash_dict, bash_exit = _bash_parse("--quality-lock ship")
    assert py_dict == bash_dict
    assert py_exit == bash_exit == 1
