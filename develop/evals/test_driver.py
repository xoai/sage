#!/usr/bin/env python3
"""
test_driver.py — the driver must tell a refused session from a failed agent.

The bug this pins was found live, on L1's first post-fix baseline run: a
five-hour-limit 429 rejected both sessions in under 3 seconds and $0.00, the
driver recorded them as clean (`error: None`), and the harness graded the
untouched fixture — reporting a Sage failure when no agent ever ran. Same
lesson as E9's budget cap, one layer down: a truncated run grades identically
to a broken feature, and only the driver can tell them apart.

Usage:  python3 develop/evals/test_driver.py
Python 3.8+, stdlib only.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import run_evals as RE  # noqa: E402


class FakeProc:
    returncode = 0
    stderr = ""

    def __init__(self, events):
        self.stdout = "\n".join(json.dumps(e) for e in events)


def result_event(**over):
    ev = {"type": "result", "subtype": "success", "is_error": False,
          "session_id": "s-1", "result": "done", "total_cost_usd": 0.5,
          "usage": {"input_tokens": 10, "output_tokens": 5}}
    ev.update(over)
    return ev


class DriverErrorResultTest(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="driver-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.out = self.d / "transcript.jsonl"
        self.driver = RE.ClaudeCodeDriver()

    def drive(self, events):
        with mock.patch.object(RE.subprocess, "run",
                               return_value=FakeProc(events)):
            return self.driver.run(self.d, ["go"], self.out)

    def test_THE_BUG_a_429_result_is_an_error_not_a_session(self):
        """The CLI exits 0 and emits a well-formed result event for a rate-limit
        rejection. Before the fix, that graded as a clean session. (Found twice,
        independently, off the same rate-limit event — the in-loop check shipped
        in v1.3.3 is canonical; this pins it at the driver level.)"""
        run = self.drive([result_event(
            is_error=True, api_error_status=429, total_cost_usd=0,
            usage={"input_tokens": 0, "output_tokens": 0},
            result="You've hit your session limit · resets 3:10am")])
        self.assertFalse(run["ok"])
        self.assertIn("session limit", run["error"])
        self.assertIn("measures nothing", run["error"],
                      "the error must say the run is void, not that Sage failed")

    def test_an_error_after_real_work_is_truncation_not_void(self):
        """The other half of the distinction (v1.3.3): an error result AFTER the
        agent read tokens is a budget-cap/timeout truncation — the workspace holds
        what it managed, so the session is graded and FLAGGED, not voided."""
        run = self.drive([result_event(
            is_error=True, subtype="error_max_budget_usd",
            result="budget exceeded")])
        self.assertTrue(run["ok"])
        self.assertEqual(run["truncated"], "error_max_budget_usd")

    def test_a_resumed_turn_error_after_prior_turn_work_is_truncation(self):
        """L4 v3's driver bug, pinned: turn 2 (--resume) hit error_max_budget_usd
        with 0 tokens in ITS OWN usage — after turn 1 of the same session did
        real, committed work — and the session was voided as 'nothing ran',
        discarding $6+ of gradeable workspace. SESSION tokens, not this turn's,
        decide whether anything ran."""
        turn1 = FakeProc([result_event()])
        turn2 = FakeProc([result_event(
            is_error=True, subtype="error_max_budget_usd", total_cost_usd=6.25,
            usage={"input_tokens": 0, "output_tokens": 0}, result="")])
        with mock.patch.object(RE.subprocess, "run", side_effect=[turn1, turn2]):
            run = self.driver.run(self.d, ["go", "now finish"], self.out)
        self.assertTrue(run["ok"], f"wrongly voided: {run.get('error')}")
        self.assertEqual(run["truncated"], "error_max_budget_usd",
                         "graded AND flagged — a truncated pass did the work")

    def test_a_clean_result_still_drives(self):
        run = self.drive([result_event()])
        self.assertTrue(run["ok"])
        self.assertIsNone(run["error"])
        self.assertEqual(run["cost_usd"], 0.5)

    def test_the_model_that_served_is_recorded(self):
        """The results used to record only the --model override (null when
        defaulted) — which is how a baseline and its re-run silently ran on two
        different models when the CLI's session default changed underneath the
        harness. The init event knows; now the session record does too."""
        run = self.drive([
            {"type": "system", "subtype": "init", "session_id": "s-1",
             "model": "claude-opus-4-8[1m]"},
            result_event(),
        ])
        self.assertEqual(run["model"], "claude-opus-4-8[1m]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
