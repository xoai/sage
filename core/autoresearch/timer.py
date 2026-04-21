"""Subprocess runner with wall-clock budget and kill semantics."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from .types import VerifyResult

GRACE_PERIOD = 5


def run_with_budget(cmd: str, seconds: int, cwd: Path) -> VerifyResult:
    """Run a shell command with a wall-clock budget.

    If the command exceeds the budget: SIGTERM, wait GRACE_PERIOD seconds,
    then SIGKILL. Returns VerifyResult with timed_out=True.
    """
    start = time.monotonic()
    timed_out = False

    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid if os.name != "nt" else None,
        )

        try:
            stdout, stderr = proc.communicate(timeout=seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name != "nt":
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=GRACE_PERIOD)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                else:
                    proc.kill()
                stdout, stderr = proc.communicate()

        duration = time.monotonic() - start
        return VerifyResult(
            stdout=stdout or "",
            stderr=stderr or "",
            exit_code=proc.returncode if not timed_out else -1,
            duration_s=duration,
            timed_out=timed_out,
        )

    except Exception as e:
        duration = time.monotonic() - start
        return VerifyResult(
            stdout="",
            stderr=str(e),
            exit_code=-1,
            duration_s=duration,
            timed_out=False,
        )
