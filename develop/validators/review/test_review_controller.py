#!/usr/bin/env python3
"""
test_review_controller.py — the RR-6 decision table, pinned (40-§1 R1–R6).

R1 replays the motivating bug: a production review-revise loop that ran
7 iterations with zero criticals throughout, major counts churning
non-monotonically (3→1→2→3→0→1→1), majors reappearing after reaching
zero, and a REVISE verdict issued on an iteration with 0 critical /
0 major. Under the v2 controller the same findings — none witnessed,
none cited — terminate at round 1 as STOP_ADVISORY. The v1 path must
keep reproducing the old behavior byte-for-byte (R6): the field history
is a regression fixture in both directions.

The per-iteration counts here are reconstructed from the field report's
description (the major sequence and the 0/0-REVISE round are exact; the
substantive/cosmetic fill is representative — the doc did not record it).

Usage:  python3 develop/validators/review/test_review_controller.py
Exit:   0 = all pass | 1 = a test failed
Python 3.8+, stdlib only.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "tools"))

import sage_flags as sf  # noqa: E402

# ── The observed production history (field report, reconstructed) ──────
# Majors 3→1→2→3→0→1→1, zero criticals, REVISE on the 0-major round.
FIELD_HISTORY = [
    {"iteration": 1, "counts": {"critical": 0, "major": 3, "substantive": 2, "cosmetic": 1}, "result": "REVISE"},
    {"iteration": 2, "counts": {"critical": 0, "major": 1, "substantive": 3, "cosmetic": 0}, "result": "REVISE"},
    {"iteration": 3, "counts": {"critical": 0, "major": 2, "substantive": 1, "cosmetic": 2}, "result": "REVISE"},
    {"iteration": 4, "counts": {"critical": 0, "major": 3, "substantive": 2, "cosmetic": 0}, "result": "REVISE"},
    {"iteration": 5, "counts": {"critical": 0, "major": 0, "substantive": 2, "cosmetic": 1}, "result": "REVISE"},
    {"iteration": 6, "counts": {"critical": 0, "major": 1, "substantive": 1, "cosmetic": 0}, "result": "REVISE"},
    {"iteration": 7, "counts": {"critical": 0, "major": 1, "substantive": 2, "cosmetic": 1}, "result": "REVISE"},
]


def finding(fid, severity, status="open", disposition=None, witnessed=False,
            cited=None):
    return {
        "id": fid,
        "severity": severity,
        "severity_as_reported": severity,
        "status": status,
        "disposition": disposition,
        "cited_rule": cited,
        "witness": {"kind": "test" if witnessed else "none",
                    "ref": "tests/review/%s.test.ts" % fid if witnessed else None,
                    "status": "red" if witnessed else "n/a"},
        "anchor": {"file": "src/x.ts", "region": [1, 2], "fingerprint": "f" + fid},
        "claim": "claim for " + fid,
    }


def ledger(findings, history=None, config=None):
    return {"findings": findings, "history": history or [], "config": config or {}}


def counts_ledger(critical=0, major=0, substantive=0, cosmetic=0, **kw):
    """A ledger whose open findings produce the given counts."""
    fs = []
    for sev, n in (("critical", critical), ("major", major),
                   ("substantive", substantive), ("cosmetic", cosmetic)):
        for i in range(n):
            fs.append(finding("F-%s%d" % (sev[0].upper(), i), sev, witnessed=True))
    return ledger(fs, **kw)


class R1FieldHistoryTest(unittest.TestCase):
    """The motivating bug, pinned forever in both directions."""

    def test_v2_terminates_round_1(self):
        # Round 1 of the field history, findings modeled as they were:
        # citation-less, witness-less. Intake capping makes every one
        # substantive, so nothing blocks and nothing buys round 2.
        capped = [finding("F-%03d" % i, "substantive") for i in range(1, 7)]
        d = sf.decide({}, 1, [], ledger=ledger(capped))
        self.assertEqual(d["action"], "STOP_ADVISORY")
        self.assertEqual(d["counts"]["substantive"], 6)
        self.assertEqual(d["weight"], 6)

    def test_v1_reproduced_the_pathology(self):
        # The same history through the v1 path: REVISE on the round with
        # 0 critical / 0 major (substantive blocked the clean bar), and
        # no termination before iteration 7.
        for h in FIELD_HISTORY:
            d = sf.decide(h["counts"], h["iteration"],
                          FIELD_HISTORY[:h["iteration"] - 1])
            self.assertEqual(d["action"], "REVISE",
                             "v1 at iteration %d" % h["iteration"])
        five = FIELD_HISTORY[4]
        self.assertEqual(five["counts"]["critical"], 0)
        self.assertEqual(five["counts"]["major"], 0)


class R2CriticalTest(unittest.TestCase):
    def test_open_witnessed_critical_continues(self):
        d = sf.decide({}, 1, [], ledger=ledger([finding("F-001", "critical",
                                                        witnessed=True)]))
        self.assertEqual(d["action"], "CONTINUE")


class R3AdvisoryTest(unittest.TestCase):
    def test_substantive_only_stops_advisory(self):
        d = sf.decide({}, 2, [], ledger=counts_ledger(substantive=5))
        self.assertEqual(d["action"], "STOP_ADVISORY")
        self.assertEqual(d["dispositions_required"],
                         ["F-S0", "F-S1", "F-S2", "F-S3", "F-S4"])

    def test_majors_at_budget_do_not_block(self):
        lg = counts_ledger(major=2, substantive=1,
                           config={"major_budget": 2})
        d = sf.decide({}, 2, [], ledger=lg)
        self.assertEqual(d["action"], "STOP_ADVISORY")

    def test_majors_over_budget_continue(self):
        d = sf.decide({}, 2, [], ledger=counts_ledger(major=1))
        self.assertEqual(d["action"], "CONTINUE")


class R4StallTest(unittest.TestCase):
    def test_escalates_at_second_stall(self):
        history = [
            {"iteration": 1, "counts": {"critical": 0, "major": 1, "substantive": 0, "cosmetic": 0}, "result": "CONTINUE"},
            {"iteration": 2, "counts": {"critical": 0, "major": 1, "substantive": 0, "cosmetic": 0}, "result": "CONTINUE"},
        ]
        lg = counts_ledger(major=1, history=history)
        d = sf.decide({}, 3, [], ledger=lg)
        self.assertEqual(d["action"], "ESCALATE")
        self.assertTrue(d["stalled"])

    def test_one_stall_still_continues(self):
        history = [{"iteration": 1, "counts": {"critical": 0, "major": 1,
                                               "substantive": 0, "cosmetic": 0},
                    "result": "CONTINUE"}]
        d = sf.decide({}, 2, [], ledger=counts_ledger(major=1, history=history))
        self.assertEqual(d["action"], "CONTINUE")

    def test_field_log_major_climb_triggers_round_4(self):
        # Weights 9 → 3 → 6 → 9 (majors 3→1→2→3). The 1→2→3 climb is two
        # trailing non-improving rounds: escalation at round 4, not 7.
        history = [{"iteration": h["iteration"],
                    "counts": dict(h["counts"], substantive=0, cosmetic=0),
                    "result": "CONTINUE"}
                   for h in FIELD_HISTORY[:3]]
        d = sf.decide({}, 4, [], ledger=counts_ledger(major=3, history=history))
        self.assertEqual(d["action"], "ESCALATE")

    def test_improvement_resets_the_stall(self):
        history = [
            {"iteration": 1, "counts": {"critical": 0, "major": 2, "substantive": 0, "cosmetic": 0}, "result": "CONTINUE"},
            {"iteration": 2, "counts": {"critical": 0, "major": 2, "substantive": 0, "cosmetic": 0}, "result": "CONTINUE"},
        ]
        d = sf.decide({}, 3, [], ledger=counts_ledger(major=1, history=history))
        self.assertEqual(d["action"], "CONTINUE")


class R5CapTest(unittest.TestCase):
    def test_cap_with_open_major_stops(self):
        d = sf.decide({}, 5, [], ledger=counts_ledger(major=1))
        self.assertEqual(d["action"], "STOP_CAP")
        self.assertTrue(d["cap_reached"])

    def test_fix_now_converts_stop_to_continue(self):
        lg = counts_ledger(major=1)
        lg["findings"][0]["disposition"] = "fix-now"
        d = sf.decide({}, 5, [], ledger=lg)
        self.assertEqual(d["action"], "CONTINUE")
        self.assertEqual(d["fix_now"], [lg["findings"][0]["id"]])

    def test_pending_defer_still_stops_at_cap(self):
        lg = counts_ledger(major=1)
        lg["findings"][0]["disposition"] = {"action": "defer", "ticket": "T-1"}
        d = sf.decide({}, 5, [], ledger=lg)
        self.assertEqual(d["action"], "STOP_CAP")
        self.assertEqual(d["dispositions_required"], [])


class CleanAndSettledTest(unittest.TestCase):
    def test_nothing_open_stops_clean(self):
        d = sf.decide({}, 3, [], ledger=ledger(
            [finding("F-001", "major", status="fixed"),
             finding("F-002", "substantive", status="rejected"),
             finding("F-003", "major", status="deferred")]))
        self.assertEqual(d["action"], "STOP_CLEAN")

    def test_disputed_does_not_count_open(self):
        d = sf.decide({}, 1, [], ledger=ledger(
            [finding("F-001", "critical", status="disputed", witnessed=True)]))
        self.assertEqual(d["action"], "STOP_CLEAN")

    def test_not_fixed_counts_open(self):
        d = sf.decide({}, 2, [], ledger=ledger(
            [finding("F-001", "major", status="not-fixed", witnessed=True)]))
        self.assertEqual(d["action"], "CONTINUE")


class R6V1ByteIdenticalTest(unittest.TestCase):
    """The ledger-absent path is the existing decide(), untouched. The full
    corpus lives in develop/validators/tools/test_sage_flags.py; these pin
    the seam itself."""

    def test_default_argument_is_v1(self):
        clean = {"critical": 0, "major": 0, "substantive": 0, "cosmetic": 3}
        self.assertEqual(sf.decide(clean, 1, []),
                         {"counts": clean, "is_clean": True,
                          "cap_reached": False, "stuck": False,
                          "action": "PASS"})

    def test_v1_shape_carries_no_v2_fields(self):
        d = sf.decide({"critical": 1, "major": 0, "substantive": 0,
                       "cosmetic": 0}, 1, [])
        self.assertEqual(sorted(d.keys()),
                         ["action", "cap_reached", "counts", "is_clean",
                          "stuck"])

    def test_v1_cap_is_still_ten(self):
        dirty = {"critical": 0, "major": 1, "substantive": 0, "cosmetic": 0}
        self.assertEqual(sf.decide(dirty, 9, [])["action"], "REVISE")
        self.assertEqual(sf.decide(dirty, 10, [])["action"], "CAP_REACHED")


if __name__ == "__main__":
    unittest.main()
