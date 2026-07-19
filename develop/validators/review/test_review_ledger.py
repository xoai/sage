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
        self.assertEqual(cfg["mode"], "v1")
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
