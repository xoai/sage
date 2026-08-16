#!/usr/bin/env python3
"""
test_review_ledger.py — review.py bookkeeping, pinned (40-§1).

The ledger is the loop's memory: findings once written down cannot be
forgotten or silently re-raised. These tests pin the mechanics that make
that true — fingerprints stable under whitespace/reflow, dedup by
region+claim, severity capping (an uncited, unwitnessed critical is an
opinion), the re-litigation guard licensed only by fingerprint drift,
and fail-closed behavior on anything malformed (RR-4: this is
bookkeeping, not a hook — the fail-open rule does not apply).

Usage:  python3 develop/validators/review/test_review_ledger.py
Exit:   0 = all pass | 1 = a test failed
Python 3.8+, stdlib only.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "tools"))

import review as R  # noqa: E402

REVIEW_PY = REPO_ROOT / "runtime" / "tools" / "review.py"

AUTH_TS = """export function refresh(token: Token) {
  const grant = grants.lookup(token);
  return issue(grant);
}
"""


def raw_finding(claim="refresh token is not rotated on use", severity="major",
                file="src/auth.ts", region=(1, 4), cited=None, witness=None,
                **extra):
    f = {"pass": "state-and-flow", "severity": severity, "cited_rule": cited,
         "anchor": {"file": file, "region": list(region)}, "claim": claim,
         "witness": witness or {"kind": "none", "ref": None, "status": "n/a"},
         "exit_criteria": "token value differs across two consecutive calls"}
    f.update(extra)
    return f


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="review-ledger-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / ".sage" / "work" / "20260720-slug").mkdir(parents=True)
        (self.root / "src").mkdir()
        (self.root / "src" / "auth.ts").write_text(AUTH_TS, encoding="utf-8")
        self.ledger = (self.root / ".sage" / "work" / "20260720-slug"
                       / "review-ledger.json")
        self.config = dict(R.CONFIG_DEFAULTS, mode="v2")

    def intake(self, findings, iteration=1, config=None):
        return R.intake(self.ledger, findings, iteration, "code", self.root,
                        config or self.config)

    def entries(self):
        return json.loads(self.ledger.read_text(encoding="utf-8"))["findings"]


class FingerprintTest(LedgerCase):
    def test_stable_under_whitespace_and_reflow(self):
        fp1 = R.fingerprint_region(self.root, "src/auth.ts", [1, 4])
        reflowed = ("export function refresh(token: Token) "
                    "{\n  const grant =\n      grants.lookup(token);\n"
                    "  return issue(grant);\n}\n")
        (self.root / "src" / "auth.ts").write_text(reflowed, encoding="utf-8")
        fp2 = R.fingerprint_region(self.root, "src/auth.ts", [1, 5])
        self.assertEqual(fp1, fp2)

    def test_content_change_changes_it(self):
        fp1 = R.fingerprint_region(self.root, "src/auth.ts", [1, 4])
        (self.root / "src" / "auth.ts").write_text(
            AUTH_TS.replace("issue(grant)", "issue(rotate(grant))"),
            encoding="utf-8")
        fp2 = R.fingerprint_region(self.root, "src/auth.ts", [1, 4])
        self.assertNotEqual(fp1, fp2)

    def test_missing_file_fails_closed(self):
        with self.assertRaises(R.Problem):
            R.fingerprint_region(self.root, "src/gone.ts", [1, 2])

    def test_bad_region_fails_closed(self):
        with self.assertRaises(R.Problem):
            R.fingerprint_region(self.root, "src/auth.ts", [3, 2])
        with self.assertRaises(R.Problem):
            R.fingerprint_region(self.root, "src/auth.ts", [99, 120])


class CappingTest(LedgerCase):
    def test_uncited_unwitnessed_major_is_capped(self):
        rep = self.intake([raw_finding(severity="major")])
        entry = self.entries()[0]
        self.assertEqual(entry["severity"], "substantive")
        self.assertEqual(entry["severity_as_reported"], "major")
        self.assertEqual(rep["capped"], [entry["id"]])

    def test_cited_major_is_not_capped(self):
        self.intake([raw_finding(severity="major", cited="spec §4.2")])
        self.assertEqual(self.entries()[0]["severity"], "major")

    def test_witnessed_critical_is_not_capped(self):
        self.intake([raw_finding(severity="critical",
                                 witness={"kind": "test",
                                          "ref": "tests/review/F-001.test.ts",
                                          "status": "red"})])
        self.assertEqual(self.entries()[0]["severity"], "critical")

    def test_trace_kind_counts_as_witness(self):
        # An empty trace-matrix cell is absence made observable (RR-3.1).
        self.intake([raw_finding(severity="major",
                                 witness={"kind": "trace", "ref": "matrix",
                                          "status": "n/a"})])
        self.assertEqual(self.entries()[0]["severity"], "major")

    def test_capping_off_restores_reported_severity(self):
        cfg = dict(self.config, witness_capping=False)
        self.intake([raw_finding(severity="major")], config=cfg)
        self.assertEqual(self.entries()[0]["severity"], "major")

    def test_substantive_never_touched(self):
        self.intake([raw_finding(severity="substantive")])
        self.assertEqual(self.entries()[0]["severity"], "substantive")


class DedupTest(LedgerCase):
    def test_same_region_same_claim_merges(self):
        self.intake([raw_finding()])
        rep = self.intake([raw_finding(claim="Refresh token is NOT rotated, on use!")],
                          iteration=2)
        entries = self.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["raised_count"], 2)
        self.assertEqual(rep["merged"], [entries[0]["id"]])
        self.assertEqual(entries[0]["first_seen"], 1)

    def test_same_region_different_claim_is_new(self):
        self.intake([raw_finding()])
        self.intake([raw_finding(claim="grant object is shared across issuances")],
                    iteration=2)
        self.assertEqual(len(self.entries()), 2)


class RelitigationTest(LedgerCase):
    def settle(self, status):
        self.intake([raw_finding(cited="spec §4.2")])
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["findings"][0]["status"] = status
        self.ledger.write_text(json.dumps(data), encoding="utf-8")

    def test_unchanged_region_re_raise_is_disputed(self):
        self.settle("rejected")
        rep = self.intake([raw_finding(cited="spec §4.2")], iteration=2)
        entries = self.entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["status"], "disputed")
        self.assertEqual(entries[1]["relitigates"], entries[0]["id"])
        self.assertEqual(rep["disputed"], [entries[1]["id"]])

    def test_fingerprint_drift_licenses_re_raise(self):
        self.settle("fixed")
        (self.root / "src" / "auth.ts").write_text(
            AUTH_TS.replace("issue(grant)", "issue(rotate(grant))"),
            encoding="utf-8")
        self.intake([raw_finding(cited="spec §4.2")], iteration=2)
        self.assertEqual(self.entries()[1]["status"], "open")

    def test_disputed_entries_do_not_block(self):
        self.settle("rejected")
        self.intake([raw_finding(cited="spec §4.2")], iteration=2)
        config = dict(self.config)
        decision = R.close_round(self.ledger, 2, config)
        self.assertEqual(decision["action"], "STOP_CLEAN")


class VerifyTest(LedgerCase):
    def test_verify_records_evidence_and_status(self):
        self.intake([raw_finding(cited="spec §4.2")])
        R.verify(self.ledger, [{"id": "F-001", "verdict": "FIXED",
                                "evidence": "witness green at 4f2a91c"}], 2)
        entry = self.entries()[0]
        self.assertEqual(entry["status"], "fixed")
        self.assertEqual(entry["verifications"][0]["iteration"], 2)

    def test_verify_without_evidence_fails_closed(self):
        self.intake([raw_finding(cited="spec §4.2")])
        with self.assertRaises(R.Problem):
            R.verify(self.ledger, [{"id": "F-001", "verdict": "FIXED"}], 2)

    def test_unknown_id_fails_closed(self):
        self.intake([raw_finding()])
        with self.assertRaises(R.Problem):
            R.verify(self.ledger, [{"id": "F-999", "verdict": "FIXED",
                                    "evidence": "x"}], 2)

    def test_cannot_reproduce_disputes(self):
        self.intake([raw_finding(cited="spec §4.2")])
        R.cannot_reproduce(self.ledger, "F-001", "pytest: 1 passed at HEAD", 2)
        self.assertEqual(self.entries()[0]["status"], "disputed")


class CloseRoundTest(LedgerCase):
    def test_stop_refused_until_dispositions(self):
        self.intake([raw_finding(), raw_finding(
            claim="lookup result is never null-checked", region=(2, 3))])
        with self.assertRaises(R.Problem) as ctx:
            R.close_round(self.ledger, 1, self.config)
        self.assertIn("F-001", str(ctx.exception))
        self.assertIn("F-002", str(ctx.exception))
        # Nothing was recorded by the refusal.
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(data["history"], [])

    def test_stop_advisory_records_and_seals(self):
        self.intake([raw_finding()])
        R.disposition(self.ledger, "F-001", "defer", None, "TICKET-7")
        decision = R.close_round(self.ledger, 1, self.config)
        self.assertEqual(decision["action"], "STOP_ADVISORY")
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(data["history"][0]["result"], "STOP_ADVISORY")
        self.assertEqual(data["history"][0]["counts"]["substantive"], 1)
        self.assertEqual(data["findings"][0]["status"], "deferred")
        record = (self.ledger.parent / "decisions.md").read_text(encoding="utf-8")
        self.assertIn("review-loop STOP_ADVISORY: 20260720-slug iter=1", record)
        self.assertIn("F-001:defer", record)
        self.assertIn("auto-logged by review.py", record)

    def test_continue_records_no_exit_line(self):
        self.intake([raw_finding(severity="critical", cited="spec §4.2")])
        decision = R.close_round(self.ledger, 1, self.config)
        self.assertEqual(decision["action"], "CONTINUE")
        self.assertFalse((self.ledger.parent / "decisions.md").exists())

    def test_defer_requires_ticket_reject_requires_reason(self):
        self.intake([raw_finding()])
        with self.assertRaises(R.Problem):
            R.disposition(self.ledger, "F-001", "defer", None, None)
        with self.assertRaises(R.Problem):
            R.disposition(self.ledger, "F-001", "reject", None, None)


class DisputedGuardLedgerTest(LedgerCase):
    """The S2 hole, end to end (brief: evidence/verify_review_claims.py).
    A finding the fixer cannot reproduce, or the reviewer stands by, is
    contested — it must reach a human as a disposition, never vanish
    into STOP_CLEAN."""

    def witnessed_critical(self):
        return raw_finding(severity="critical",
                           witness={"kind": "test",
                                    "ref": "tests/review/F-001.test.ts",
                                    "status": "red"})

    def test_cannot_reproduce_blocks_stop_until_disposition(self):
        self.intake([self.witnessed_critical()])
        R.cannot_reproduce(self.ledger, "F-001", "witness green at HEAD", 2)
        with self.assertRaises(R.Problem) as ctx:
            R.close_round(self.ledger, 2, self.config)
        self.assertIn("F-001", str(ctx.exception))
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(data["history"], [])       # refusal records nothing

    def test_disputed_stands_blocks_stop_until_disposition(self):
        self.intake([self.witnessed_critical()])
        R.verify(self.ledger, [{"id": "F-001", "verdict": "DISPUTED-STANDS",
                                "evidence": "boundary is reachable"}], 2)
        with self.assertRaises(R.Problem):
            R.close_round(self.ledger, 2, self.config)

    def test_disposition_unblocks_seals_and_logs_disputed_field(self):
        self.intake([self.witnessed_critical()])
        R.cannot_reproduce(self.ledger, "F-001", "witness green at HEAD", 2)
        R.disposition(self.ledger, "F-001", "defer", None, "TICKET-3")
        decision = R.close_round(self.ledger, 2, self.config)
        self.assertEqual(decision["action"], "STOP_ADVISORY")
        self.assertEqual(self.entries()[0]["status"], "deferred")
        record = (self.ledger.parent / "decisions.md").read_text(encoding="utf-8")
        self.assertIn("disputed=", record)
        self.assertIn("F-001:defer", record)

    def test_report_renders_phase_a_evidence(self):
        self.intake([self.witnessed_critical()])
        R.cannot_reproduce(self.ledger, "F-001", "pytest: 1 passed at HEAD", 2)
        self.assertIn("cannot reproduce: pytest: 1 passed at HEAD",
                      R.report(self.ledger))

    def test_guard_off_restores_prior_behavior(self):
        cfg = dict(self.config, disputed_disposition=False)
        self.intake([self.witnessed_critical()], config=cfg)
        R.cannot_reproduce(self.ledger, "F-001", "witness green at HEAD", 2)
        self.assertEqual(R.close_round(self.ledger, 2, cfg)["action"],
                         "STOP_CLEAN")


class FixNowExpiryTest(LedgerCase):
    """fix-now buys EXACTLY one more round — the docstring's promise.
    Sticky fix-now was an unbounded loop: the disposition survived a
    NOT-FIXED verdict, and fix_now preempts both the stall check and the
    cap, so a fix that kept failing bought rounds forever. (Purchases here
    ride DISPUTED entries — under fix_now_blocking_only, open non-blocking
    entries can no longer buy at all; see FixNowEligibilityTest.)"""

    def disputed_entry(self):
        self.intake([raw_finding(severity="substantive")])
        R.verify(self.ledger, [{"id": "F-001", "verdict": "DISPUTED-STANDS",
                                "evidence": "reviewer stands by it"}], 1)

    def test_not_fixed_spends_the_bought_round(self):
        self.disputed_entry()
        R.disposition(self.ledger, "F-001", "fix-now", None, None)
        self.assertEqual(R.close_round(self.ledger, 1, self.config)["action"],
                         "CONTINUE")               # the bought round
        R.verify(self.ledger, [{"id": "F-001", "verdict": "NOT-FIXED",
                                "evidence": "still reproduces"}], 2)
        self.assertIsNone(self.entries()[0]["disposition"])
        with self.assertRaises(R.Problem):         # human decides anew,
            R.close_round(self.ledger, 2, self.config)   # not CONTINUE forever

    def test_cannot_reproduce_spends_the_bought_round(self):
        self.disputed_entry()
        R.disposition(self.ledger, "F-001", "fix-now", None, None)
        R.close_round(self.ledger, 1, self.config)
        R.cannot_reproduce(self.ledger, "F-001", "no repro at HEAD", 2)
        self.assertIsNone(self.entries()[0]["disposition"])

    def test_fixed_still_clears_it(self):
        self.disputed_entry()
        R.disposition(self.ledger, "F-001", "fix-now", None, None)
        R.verify(self.ledger, [{"id": "F-001", "verdict": "FIXED",
                                "evidence": "witness green"}], 2)
        self.assertIsNone(self.entries()[0]["disposition"])


class FixNowEligibilityTest(LedgerCase):
    """fix-now buys review rounds — a purchase only blocking or disputed
    entries may make. The field data behind the rule: agents picked
    fix-now for cosmetics because it was the only disposition needing no
    reason and no ticket, converting every advisory stop into another
    full round (pancake round 2 closed 0/0/1/2 open yet recorded
    CONTINUE; finhub's exit record: F-022:fix-now)."""

    def test_open_substantive_cannot_fix_now(self):
        self.intake([raw_finding(severity="substantive")])
        with self.assertRaises(R.Problem) as ctx:
            R.disposition(self.ledger, "F-001", "fix-now", None, None)
        msg = str(ctx.exception)
        for hint in ("defer", "reject", "disposition-batch",
                     "fix_now_blocking_only"):
            self.assertIn(hint, msg)
        self.assertIsNone(self.entries()[0]["disposition"])

    def test_open_cosmetic_cannot_fix_now(self):
        self.intake([raw_finding(severity="cosmetic")])
        with self.assertRaises(R.Problem):
            R.disposition(self.ledger, "F-001", "fix-now", None, None)

    def test_blocking_and_disputed_still_can(self):
        self.intake([raw_finding(severity="major",
                                 witness={"kind": "test", "ref": "t.py",
                                          "status": "red"}),
                     raw_finding(claim="second claim", severity="substantive",
                                 region=(2, 3))])
        R.verify(self.ledger, [{"id": "F-002", "verdict": "DISPUTED-STANDS",
                                "evidence": "stands"}], 2)
        R.disposition(self.ledger, "F-001", "fix-now", None, None)  # major
        R.disposition(self.ledger, "F-002", "fix-now", None, None)  # disputed
        self.assertEqual(self.entries()[0]["disposition"], "fix-now")
        self.assertEqual(self.entries()[1]["disposition"], "fix-now")

    def test_batch_fix_now_on_cosmetics_refused_atomically(self):
        self.intake([raw_finding(claim="c1", severity="cosmetic",
                                 region=(1, 2)),
                     raw_finding(claim="c2", severity="cosmetic",
                                 region=(2, 3))])
        with self.assertRaises(R.Problem):
            R.disposition_batch(self.ledger, [], "cosmetic", "fix-now",
                                None, None)
        self.assertTrue(all(e["disposition"] is None for e in self.entries()))

    def test_knob_off_restores_round_buying(self):
        cfg = dict(self.config, fix_now_blocking_only=False)
        self.intake([raw_finding(severity="substantive")], config=cfg)
        R.disposition(self.ledger, "F-001", "fix-now", None, None, config=cfg)
        self.assertEqual(self.entries()[0]["disposition"], "fix-now")

    def test_advisory_stop_cannot_become_continue(self):
        # The pancake round-2 shape: 0/0/1/2 open. No disposition path may
        # yield CONTINUE; batch defer/reject leads to the recorded stop.
        self.intake([
            raw_finding(claim="one substantive", severity="substantive",
                        region=(1, 2)),
            raw_finding(claim="nit one", severity="cosmetic", region=(2, 3)),
            raw_finding(claim="nit two", severity="cosmetic", region=(3, 4))])
        for fid in ("F-001", "F-002", "F-003"):
            with self.assertRaises(R.Problem):
                R.disposition(self.ledger, fid, "fix-now", None, None)
        R.disposition_batch(self.ledger, [], "substantive", "defer",
                            None, "cleanup.md")
        R.disposition_batch(self.ledger, [], "cosmetic", "reject",
                            "style only", None)
        decision = R.close_round(self.ledger, 2, self.config)
        self.assertEqual(decision["action"], "STOP_ADVISORY")


class StopRefusalBeltAndBracesTest(LedgerCase):
    """close_round refuses ANY stop verdict carrying pending dispositions
    — including STOP_CLEAN, which today's decision table cannot produce
    in that state (the disputed guard reroutes it to STOP_ADVISORY).
    The broadened refusal defends against a FUTURE decide() change or a
    new action; a mutation audit found it otherwise unpinned, and a
    claimed behavior with a surviving mutant is an unpinned claim. The
    stub bypasses the table to reach the impossible state directly."""

    def test_stop_clean_with_pending_dispositions_refused(self):
        self.intake([raw_finding(severity="substantive")])

        class StubFlags:
            @staticmethod
            def decide(counts, iteration, history, ledger=None):
                return {"counts": {"critical": 0, "major": 0,
                                   "substantive": 0, "cosmetic": 0},
                        "action": "STOP_CLEAN",
                        "dispositions_required": ["F-001"],
                        "disputed_pending": [], "fix_now": [],
                        "open_ids": [], "stalled": False,
                        "cap_reached": False, "weight": 0}

        real = R._load_sage_flags
        R._load_sage_flags = lambda: StubFlags
        self.addCleanup(setattr, R, "_load_sage_flags", real)
        with self.assertRaises(R.Problem):
            R.close_round(self.ledger, 1, self.config)
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(data["history"], [])       # nothing recorded


class AutoDeferTest(LedgerCase):
    """Rounds >1 discoveries that never blocked must not extend the loop:
    they intake as pending defers ticketed `cleanup.md` — recorded,
    non-blocking, sealed at the stop — and close-round writes the ticket
    file itself (machine-owned, like decisions.md). The field treadmill:
    fix → new diff → new nits → fix-now → repeat (finhub round 2 found 7
    new substantives; pancake found new cosmetics in rounds 2 AND 3)."""

    def first_round(self):
        self.intake([raw_finding(severity="major",
                                 witness={"kind": "test", "ref": "t.py",
                                          "status": "red"})])

    def late_nit(self, claim="late nit", region=(2, 3)):
        return raw_finding(claim=claim, severity="substantive", region=region)

    def test_late_substantive_auto_defers(self):
        self.first_round()
        rep = self.intake([self.late_nit()], iteration=2)
        entry = self.entries()[1]
        self.assertEqual(entry["disposition"],
                         {"action": "defer", "ticket": "cleanup.md"})
        self.assertEqual(rep["auto_deferred"], [entry["id"]])
        self.assertEqual(entry["status"], "open")    # pending until sealed

    def test_late_major_still_blocks(self):
        self.first_round()
        rep = self.intake([raw_finding(claim="late major", region=(2, 3),
                                       severity="major",
                                       witness={"kind": "test", "ref": "t2.py",
                                                "status": "red"})],
                          iteration=2)
        self.assertIsNone(self.entries()[1]["disposition"])
        self.assertEqual(rep["auto_deferred"], [])
        self.assertEqual(R.close_round(self.ledger, 2, self.config)["action"],
                         "CONTINUE")

    def test_round_one_never_auto_defers(self):
        self.intake([raw_finding(severity="substantive")])
        self.assertIsNone(self.entries()[0]["disposition"])

    def test_auto_deferred_never_blocks_or_requires_disposition(self):
        self.first_round()
        R.verify(self.ledger, [{"id": "F-001", "verdict": "FIXED",
                                "evidence": "witness green"}], 2)
        self.intake([self.late_nit()], iteration=2)
        decision = R.close_round(self.ledger, 2, self.config)
        self.assertEqual(decision["action"], "STOP_ADVISORY")
        self.assertEqual(decision["dispositions_required"], [])

    def test_sealing_stop_writes_cleanup_md(self):
        self.first_round()
        R.verify(self.ledger, [{"id": "F-001", "verdict": "FIXED",
                                "evidence": "witness green"}], 2)
        self.intake([self.late_nit()], iteration=2)
        R.close_round(self.ledger, 2, self.config)
        cleanup = self.ledger.parent / "cleanup.md"
        text = cleanup.read_text(encoding="utf-8")
        self.assertIn("F-002", text)
        self.assertIn("late nit", text)
        self.assertIn("src/auth.ts:2-3", text)
        self.assertIn("token value differs", text)   # exit_criteria
        self.assertEqual(self.entries()[1]["status"], "deferred")
        # a later stop APPENDS rather than overwriting
        self.intake([self.late_nit(claim="second wave", region=(3, 4))],
                    iteration=3)
        R.close_round(self.ledger, 3, self.config)
        text2 = cleanup.read_text(encoding="utf-8")
        self.assertIn("late nit", text2)
        self.assertIn("second wave", text2)

    def test_re_raise_merges_into_auto_deferred(self):
        self.first_round()
        self.intake([self.late_nit()], iteration=2)
        rep = self.intake([self.late_nit(claim="Late NIT!")], iteration=3)
        self.assertEqual(len(self.entries()), 2)
        self.assertEqual(rep["merged"], [self.entries()[1]["id"]])
        self.assertEqual(self.entries()[1]["raised_count"], 2)

    def test_relitigation_re_raise_is_never_auto_deferred(self):
        # A settled-fingerprint re-raise at iteration >1 lands as
        # intake-disputed (the guard's record) — auto-defer must NOT
        # claim it: a defer disposition would seal it `deferred`,
        # erasing its guard identity and polluting cleanup.md with
        # re-litigation noise. (Mutation audit: dropping `not settled`
        # from the auto-defer condition survived the suite before this.)
        self.intake([raw_finding(severity="substantive",
                                 cited="spec §4.2")])
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["findings"][0]["status"] = "rejected"
        self.ledger.write_text(json.dumps(data), encoding="utf-8")
        self.intake([raw_finding(severity="substantive",
                                 cited="spec §4.2")], iteration=2)
        entry = self.entries()[1]
        self.assertEqual(entry["status"], "disputed")
        self.assertEqual(entry["relitigates"], "F-001")
        self.assertIsNone(entry["disposition"])

    def test_knob_open_restores(self):
        cfg = dict(self.config, late_finding_disposition="open")
        self.intake([raw_finding(severity="major",
                                 witness={"kind": "test", "ref": "t.py",
                                          "status": "red"})], config=cfg)
        self.intake([self.late_nit()], iteration=2, config=cfg)
        self.assertIsNone(self.entries()[1]["disposition"])


class InstanceLedgerTest(LedgerCase):
    """One ledger, several checkpoint loops: cap and stall are
    per-instance (memchain's exit records ran iter=7/9/11/13 against a
    cap of 5). Markerless ledgers keep legacy behavior byte-identically —
    including accepting any --iteration unvalidated."""

    def blocking(self, claim="b", region=(1, 2)):
        return raw_finding(claim=claim, severity="major", region=region,
                           witness={"kind": "test", "ref": "t.py",
                                    "status": "red"})

    def test_open_instance_marker_and_derived_iteration(self):
        self.intake([self.blocking()])
        R.close_round(self.ledger, 1, self.config)          # CONTINUE
        R.open_instance(self.ledger, "plan")
        R.verify(self.ledger, [{"id": "F-001", "verdict": "FIXED",
                                "evidence": "green"}], 1)
        d = R.close_round(self.ledger, 1, self.config)      # derived = 1
        self.assertEqual(d["action"], "STOP_CLEAN")
        hist = json.loads(self.ledger.read_text(encoding="utf-8"))["history"]
        self.assertEqual([h.get("instance") for h in hist if "instance" in h],
                         ["plan"])

    def test_mismatched_iteration_fails_closed_when_markers_exist(self):
        self.intake([self.blocking()])
        R.open_instance(self.ledger, "code")
        with self.assertRaises(R.Problem) as ctx:
            R.close_round(self.ledger, 5, self.config)      # derived is 1
        # The refusal must be THE mismatch refusal — a mutation audit
        # showed `!=` weakened to `<` sliding through because STOP_CAP's
        # disposition refusal also raises Problem here.
        self.assertIn("does not match", str(ctx.exception))

    def test_markerless_accepts_any_iteration(self):
        self.intake([self.blocking()])
        R.verify(self.ledger, [{"id": "F-001", "verdict": "FIXED",
                                "evidence": "green"}], 13)
        d = R.close_round(self.ledger, 13, self.config)     # memchain shape
        self.assertEqual(d["action"], "STOP_CLEAN")

    def test_cap_counts_rounds_in_this_instance_only(self):
        self.intake([self.blocking()])
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        counts = {"critical": 0, "major": 1, "substantive": 0, "cosmetic": 0}
        data["history"] = [{"iteration": i, "counts": counts,
                            "result": "CONTINUE"} for i in range(1, 7)]
        data["history"].append({"instance": "qa"})
        self.ledger.write_text(json.dumps(data), encoding="utf-8")
        d = R.close_round(self.ledger, 1, self.config)      # fresh instance
        self.assertEqual(d["action"], "CONTINUE")           # not STOP_CAP

    def test_report_renders_markers(self):
        self.intake([self.blocking()])
        R.close_round(self.ledger, 1, self.config)
        R.open_instance(self.ledger, "plan")
        self.assertIn("[plan]", R.report(self.ledger))

    def test_instance_rounds_helper(self):
        rounds = [{"iteration": 1, "result": "CONTINUE", "counts": {}},
                  {"instance": "plan"},
                  {"iteration": 1, "result": "CONTINUE", "counts": {}},
                  {"iteration": 2, "result": "STOP_CLEAN", "counts": {}}]
        self.assertEqual(len(R.instance_rounds(rounds)), 2)
        self.assertEqual(len(R.instance_rounds(rounds[:1])), 1)
        self.assertEqual(len(R.instance_rounds([])), 0)


class CitationTest(LedgerCase):
    """RR-3.1 hardened: a citation that resolves nowhere is no citation.
    Fail-soft — with no source of the cited kind on disk, the check
    disables itself loudly rather than capping a legitimate finding."""

    def spec(self, text="## Requirements\n\n§4.2 refresh tokens rotate "
                        "on every use\n"):
        (self.ledger.parent / "spec.md").write_text(text, encoding="utf-8")

    def test_resolvable_spec_citation_keeps_severity(self):
        self.spec()
        self.intake([raw_finding(severity="critical", cited="spec §4.2")])
        self.assertEqual(self.entries()[0]["severity"], "critical")

    def test_unresolvable_citation_caps(self):
        self.spec()
        rep = self.intake([raw_finding(severity="critical", cited="spec §77.7")])
        entry = self.entries()[0]
        self.assertEqual(entry["severity"], "substantive")
        self.assertEqual(entry["severity_as_reported"], "critical")
        self.assertTrue(entry["citation_unresolved"])
        self.assertEqual(rep["citation_unresolved"], [entry["id"]])
        self.assertEqual(rep["capped"], [entry["id"]])

    def test_witness_rescues_unresolvable_citation(self):
        self.spec()
        self.intake([raw_finding(severity="critical", cited="spec §77.7",
                                 witness={"kind": "test",
                                          "ref": "tests/review/F-001.py",
                                          "status": "red"})])
        self.assertEqual(self.entries()[0]["severity"], "critical")

    def test_no_source_of_cited_kind_skips_loudly(self):
        rep = self.intake([raw_finding(severity="critical", cited="spec §77.7")])
        self.assertEqual(self.entries()[0]["severity"], "critical")
        self.assertEqual(rep["citation_skipped"], ["F-001"])

    def test_constitution_citation_resolves(self):
        (self.root / ".sage" / "constitution.md").write_text(
            "api.3: all queries parameterized\n", encoding="utf-8")
        self.intake([raw_finding(severity="major", cited="constitution:api.3")])
        self.assertEqual(self.entries()[0]["severity"], "major")

    def test_check_off_restores_unvalidated(self):
        self.spec()
        cfg = dict(self.config, citation_check=False)
        self.intake([raw_finding(severity="critical", cited="spec §77.7")],
                    config=cfg)
        self.assertEqual(self.entries()[0]["severity"], "critical")

    def test_adr_citations_resolve_against_cycle_docs(self):
        # Architect mode cites ADRs; their filenames vary, so the adr
        # kind resolves against every markdown doc in the cycle dir —
        # a real ADR reference holds severity, a bogus one caps.
        (self.ledger.parent / "adr-storage.md").write_text(
            "ADR-7 chosen: event sourcing\n", encoding="utf-8")
        rep = self.intake([raw_finding(severity="major", cited="adr ADR-7"),
                           raw_finding(severity="major", cited="adr ADR-99",
                                       claim="phantom decision", region=(2, 3))])
        self.assertEqual(self.entries()[0]["severity"], "major")
        self.assertEqual(self.entries()[1]["severity"], "substantive")
        self.assertEqual(rep["citation_unresolved"], [self.entries()[1]["id"]])


class BatchDispositionTest(LedgerCase):
    """RR-7 kept, the round-trips collapsed: every entry still gets a
    recorded decision; N interactive disposition calls become one."""

    def seed(self):
        self.intake([
            raw_finding(claim="c1", severity="cosmetic", region=(1, 2)),
            raw_finding(claim="c2", severity="cosmetic", region=(2, 3)),
            raw_finding(claim="c3", severity="cosmetic", region=(3, 4)),
            raw_finding(claim="s1", severity="substantive", region=(1, 4)),
        ])

    def test_severity_selector_rejects_all_cosmetics(self):
        self.seed()
        out = R.disposition_batch(self.ledger, [], "cosmetic", "reject",
                                  "style-only, no behavior change", None)
        self.assertEqual(out, ["F-001", "F-002", "F-003"])
        for e in self.entries()[:3]:
            self.assertEqual(e["disposition"]["action"], "reject")
        self.assertIsNone(self.entries()[3]["disposition"])

    def test_ids_share_one_ticket_and_close_round_seals(self):
        self.seed()
        R.disposition_batch(self.ledger, ["F-001", "F-002", "F-003"], None,
                            "reject", "nits", None)
        out = R.disposition_batch(self.ledger, ["F-004"], None, "defer",
                                  None, "TICKET-12")
        self.assertEqual(out, ["F-004"])
        decision = R.close_round(self.ledger, 1, self.config)
        self.assertEqual(decision["action"], "STOP_ADVISORY")
        self.assertEqual([e["status"] for e in self.entries()],
                         ["rejected", "rejected", "rejected", "deferred"])

    def test_batch_is_atomic_on_bad_input(self):
        self.seed()
        with self.assertRaises(R.Problem):
            R.disposition_batch(self.ledger, ["F-001", "F-999"], None,
                                "reject", "r", None)
        self.assertTrue(all(e["disposition"] is None for e in self.entries()))
        with self.assertRaises(R.Problem):
            R.disposition_batch(self.ledger, ["F-001"], None, "defer",
                                None, None)
        self.assertTrue(all(e["disposition"] is None for e in self.entries()))

    def test_empty_selection_fails_closed(self):
        self.seed()
        with self.assertRaises(R.Problem):
            R.disposition_batch(self.ledger, [], None, "reject", "r", None)
        with self.assertRaises(R.Problem):
            R.disposition_batch(self.ledger, [], "critical", "reject", "r",
                                None)

    def test_cli_subcommand(self):
        self.seed()
        proc = subprocess.run(
            [sys.executable, str(REVIEW_PY), "disposition-batch",
             str(self.ledger), "--severity", "cosmetic", "--action", "reject",
             "--reason", "style only"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["dispositioned"],
                         ["F-001", "F-002", "F-003"])


class FailClosedTest(LedgerCase):
    def test_malformed_ledger(self):
        self.ledger.write_text("{not json", encoding="utf-8")
        with self.assertRaises(R.Problem):
            R.load_ledger(self.ledger)
        self.ledger.write_text('{"findings": [{"claim": "no id"}]}',
                               encoding="utf-8")
        with self.assertRaises(R.Problem):
            R.load_ledger(self.ledger)

    def test_unknown_status_rejected(self):
        self.ledger.write_text(json.dumps(
            {"findings": [{"id": "F-001", "status": "wontfix"}],
             "history": []}), encoding="utf-8")
        with self.assertRaises(R.Problem):
            R.load_ledger(self.ledger)

    def test_cli_exits_1_with_specific_error(self):
        self.ledger.write_text("{not json", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(REVIEW_PY), "report", str(self.ledger)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("malformed ledger", proc.stderr)

    def test_intake_rejects_bad_severity(self):
        with self.assertRaises(R.Problem):
            self.intake([raw_finding(severity="blocker")])


class ConfigTest(LedgerCase):
    def test_defaults_without_config(self):
        cfg = R.load_config(None)
        self.assertEqual(cfg["mode"], "v2")     # the RR-28 flip, 2026-07-20
        self.assertEqual(cfg["iteration_cap"], 5)
        self.assertTrue(cfg["witness_capping"])

    def test_block_parsed(self):
        path = self.root / ".sage" / "config.yaml"
        path.write_text("hard_enforcement: true\n"
                        "review_loop:\n"
                        "  mode: v2\n"
                        "  major_budget: 1\n"
                        "  witness_capping: false\n"
                        "gate_review: combined\n", encoding="utf-8")
        cfg = R.load_config(path)
        self.assertEqual(cfg["mode"], "v2")
        self.assertEqual(cfg["major_budget"], 1)
        self.assertFalse(cfg["witness_capping"])
        self.assertEqual(cfg["iteration_cap"], 5)

    def test_dedent_ends_the_block(self):
        path = self.root / ".sage" / "config.yaml"
        path.write_text("review_loop:\n"
                        "  mode: v2\n"
                        "other_block:\n"
                        "  mode: v9\n", encoding="utf-8")
        self.assertEqual(R.load_config(path)["mode"], "v2")

    def test_last_block_wins(self):
        # The eval driver's config_append adds a second review_loop: block
        # after the init-written one — YAML duplicate-key convention.
        path = self.root / ".sage" / "config.yaml"
        path.write_text("review_loop:\n"
                        "  mode: v1\n"
                        "  iteration_cap: 5\n"
                        "\n"
                        "review_loop:\n"
                        "  mode: v2\n", encoding="utf-8")
        cfg = R.load_config(path)
        self.assertEqual(cfg["mode"], "v2")


if __name__ == "__main__":
    unittest.main()
