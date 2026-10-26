#!/usr/bin/env python3
"""
test_review_budget.py — the loop ends, and its ceremony pays (review
2026-10-26, P1: L1 L3 L4).

  L1  one budget per cycle, counted by the tool: every review round of every
      checkpoint instance and every failed gate attempt spends it; gate
      retries are capped in code, not in a sentence.
  L3  a spent budget is a STOP with one summary for the user — never
      another round, never a pile of dispositions first.
  L4  a finding with no witness and no resolving citation is rejected on
      intake; each round names at most a few blocking findings to fix.

The field case these exist for: a red suite the cycle did not cause made
Gate 5 fail forever, and every "continue" ran another round against it.

Usage:  python3 develop/validators/review/test_review_budget.py
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
LIMITER = "\n".join("line %d" % i for i in range(1, 41)) + "\n"
REPRO = {"kind": "repro", "ref": "take(NaN) → bucket stays NaN; expected a "
                                  "rejected reading", "status": "n/a"}


def finding(claim, severity="major", region=(1, 4), witness=None, cited=None):
    return {"pass": "input-hostility", "severity": severity,
            "cited_rule": cited,
            "anchor": {"file": "src/limiter.js", "region": list(region)},
            "claim": claim,
            "witness": witness or {"kind": "none", "ref": None, "status": "n/a"},
            "exit_criteria": "the claim no longer holds"}


class Case(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="review-budget-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.cycle = self.root / ".sage" / "work" / "20261026-limiter"
        self.cycle.mkdir(parents=True)
        (self.root / "src").mkdir()
        (self.root / "src" / "limiter.js").write_text(LIMITER, encoding="utf-8")
        (self.cycle / "spec.md").write_text("## §2.1 Readings\nNaN is rejected.\n",
                                            encoding="utf-8")
        self.ledger = self.cycle / "review-ledger.json"
        self.config = dict(R.CONFIG_DEFAULTS)

    def intake(self, findings, iteration=1, config=None):
        return R.intake(self.ledger, findings, iteration, "code", self.root,
                        config or self.config)

    def entries(self):
        return json.loads(self.ledger.read_text(encoding="utf-8"))["findings"]

    def ledger_data(self):
        return json.loads(self.ledger.read_text(encoding="utf-8"))

    def close(self, iteration, config=None):
        return R.close_round(self.ledger, iteration, config or self.config)


class EvidenceTest(Case):
    def test_defaults(self):
        cfg = R.load_config(None)
        self.assertTrue(cfg["require_evidence"])
        self.assertEqual(cfg["cycle_round_budget"], 10)
        self.assertEqual(cfg["gate_retry_cap"], 3)
        self.assertEqual(cfg["max_fixes_per_round"], 3)
        self.assertEqual(cfg["witness_location"], "inline")
        self.assertFalse(cfg["sentinels"])

    def test_no_witness_no_citation_is_rejected_not_capped(self):
        rep = self.intake([finding("a NaN clock poisons the bucket"),
                           finding("naming could be clearer", "substantive",
                                   region=(5, 6))])
        self.assertEqual(rep["rejected_no_evidence"], ["F-001", "F-002"])
        for e in self.entries():
            self.assertEqual(e["status"], "rejected")
            self.assertEqual(e["rejected_for"], "no-evidence")

    def test_rejected_entries_never_block_or_need_a_disposition(self):
        self.intake([finding("a NaN clock poisons the bucket")])
        decision = self.close(1)
        self.assertEqual(decision["action"], "STOP_CLEAN")
        self.assertEqual(decision["dispositions_required"], [])
        self.assertFalse((self.cycle / "cleanup.md").exists())

    def test_a_repro_or_a_resolving_citation_is_evidence(self):
        self.intake([finding("a NaN clock poisons the bucket", witness=REPRO),
                     finding("NaN accepted", cited="spec §2.1", region=(5, 6)),
                     finding("NaN accepted", cited="spec §9.9", region=(7, 8))])
        status = {e["id"]: e["status"] for e in self.entries()}
        self.assertEqual(status, {"F-001": "open", "F-002": "open",
                                  "F-003": "rejected"})   # §9.9 resolves nowhere

    def test_a_declared_witness_with_nothing_in_it_is_not_evidence(self):
        self.intake([finding("NaN poisons", "critical",
                             witness={"kind": "repro", "ref": None, "status": "n/a"}),
                     finding("NaN poisons", "critical", region=(5, 6),
                             witness={"kind": "test", "ref": "  ", "status": "red"})])
        self.assertEqual([e["status"] for e in self.entries()], ["rejected", "rejected"])

    def test_a_citation_must_resolve_at_every_severity(self):
        self.intake([finding("naming", "cosmetic", cited="spec §99.9"),
                     finding("naming", "cosmetic", cited="spec §2.1", region=(5, 6))])
        self.assertEqual([e["status"] for e in self.entries()], ["rejected", "open"])

    def test_same_claim_with_evidence_is_a_new_finding_not_a_re_raise(self):
        self.intake([finding("a NaN clock poisons the bucket")])
        rep = self.intake([finding("a NaN clock poisons the bucket",
                                   witness=REPRO)], iteration=2)
        self.assertEqual(rep["new"], ["F-002"])
        self.assertEqual(rep["disputed"], [])
        self.assertEqual(self.entries()[1]["status"], "open")

    def test_same_claim_without_evidence_merges(self):
        self.intake([finding("a NaN clock poisons the bucket")])
        rep = self.intake([finding("a NaN clock poisons the bucket")], iteration=2)
        self.assertEqual(rep["merged"], ["F-001"])
        self.assertEqual(len(self.entries()), 1)

    def test_knob_off_restores_capping(self):
        cfg = dict(self.config, require_evidence=False)
        self.intake([finding("a NaN clock poisons the bucket")], config=cfg)
        e = self.entries()[0]
        self.assertEqual((e["status"], e["severity"]), ("open", "substantive"))


class FixListTest(Case):
    def test_at_most_three_blocking_most_severe_first(self):
        self.intake([finding("m%d" % i, region=(i * 2 + 1, i * 2 + 2),
                             witness=REPRO) for i in range(4)]
                    + [finding("c", "critical", region=(20, 21), witness=REPRO)])
        decision = self.close(1)
        self.assertEqual(decision["action"], "CONTINUE")
        self.assertEqual(decision["fix_this_round"], ["F-005", "F-001", "F-002"])
        rec = self.ledger_data()["history"][-1]
        self.assertEqual(rec["fix_this_round"], ["F-005", "F-001", "F-002"])

    def test_zero_means_all(self):
        self.intake([finding("m%d" % i, region=(i * 2 + 1, i * 2 + 2),
                             witness=REPRO) for i in range(4)])
        decision = self.close(1, dict(self.config, max_fixes_per_round=0))
        self.assertEqual(len(decision["fix_this_round"]), 4)


class BudgetTest(Case):
    def blocking(self, claim="NaN poisons", region=(1, 4), iteration=1):
        self.intake([finding(claim, region=region, witness=REPRO)], iteration)

    def test_budget_spans_checkpoint_instances(self):
        cfg = dict(self.config, cycle_round_budget=3)
        R.open_instance(self.ledger, "spec", cfg)
        self.blocking("spec gap", (1, 2))
        self.assertEqual(self.close(1, cfg)["action"], "CONTINUE")
        R.verify(self.ledger, [{"id": "F-001", "verdict": "FIXED",
                                "evidence": "fixed"}], 2)
        self.assertEqual(self.close(2, cfg)["action"], "STOP_CLEAN")
        R.open_instance(self.ledger, "code", cfg)        # 2 of 3 spent
        self.blocking("NaN poisons", (5, 6))
        decision = self.close(1, cfg)                     # 3 of 3
        self.assertEqual(decision["action"], "STOP_BUDGET")
        self.assertTrue(decision["budget"]["exhausted"])
        self.assertEqual(decision["fix_this_round"], [])

    def test_failed_gate_attempts_spend_the_same_budget(self):
        cfg = dict(self.config, cycle_round_budget=3)
        R.gate(self.ledger, "5", 1, cfg)
        R.gate(self.ledger, "5", 1, cfg)
        self.blocking()
        self.assertEqual(self.close(1, cfg)["action"], "STOP_BUDGET")

    def test_stop_budget_records_without_dispositions_and_logs(self):
        cfg = dict(self.config, cycle_round_budget=1)
        self.blocking()
        decision = self.close(1, cfg)
        self.assertEqual(decision["action"], "STOP_BUDGET")
        self.assertEqual(self.ledger_data()["history"][-1]["result"], "STOP_BUDGET")
        log = (self.cycle / "decisions.md").read_text(encoding="utf-8")
        self.assertIn("review-loop STOP_BUDGET", log)

    def test_a_clean_round_still_stops_clean_when_the_budget_is_spent(self):
        cfg = dict(self.config, cycle_round_budget=1)
        self.intake([])
        self.assertEqual(self.close(1, cfg)["action"], "STOP_CLEAN")

    def test_no_new_instance_once_spent(self):
        cfg = dict(self.config, cycle_round_budget=1)
        self.blocking()
        self.close(1, cfg)
        with self.assertRaises(R.Problem) as ctx:
            R.open_instance(self.ledger, "qa", cfg)
        self.assertIn("review.py summary", str(ctx.exception))

    def test_zero_disables_the_budget(self):
        cfg = dict(self.config, cycle_round_budget=0)
        for _ in range(4):
            R.gate(self.ledger, "5", 1, dict(cfg, gate_retry_cap=0))
        self.blocking()
        self.assertEqual(self.close(1, cfg)["action"], "CONTINUE")


class GateTest(Case):
    def test_verdicts(self):
        v = [R.gate(self.ledger, "5", code, self.config)["verdict"]
             for code in (1, 1, 0, 2, 1, 1)]
        self.assertEqual(v, ["RETRY", "RETRY", "PASS", "UNVERIFIABLE",
                             "RETRY", "RETRY"])

    def test_third_consecutive_failure_escalates_and_logs(self):
        v = [R.gate(self.ledger, "5", 1, self.config)["verdict"] for _ in range(3)]
        self.assertEqual(v, ["RETRY", "RETRY", "ESCALATE"])
        self.assertIn("gate-loop ESCALATE",
                      (self.cycle / "decisions.md").read_text(encoding="utf-8"))

    def test_unverifiable_neither_counts_nor_resets(self):
        cfg = dict(self.config, gate_retry_cap=2)
        v = [R.gate(self.ledger, "5", c, cfg)["verdict"] for c in (1, 2, 1)]
        self.assertEqual(v, ["RETRY", "UNVERIFIABLE", "ESCALATE"])

    def test_retries_are_per_gate(self):
        cfg = dict(self.config, gate_retry_cap=2)
        v = [R.gate(self.ledger, g, 1, cfg)["verdict"] for g in ("1", "5", "5")]
        self.assertEqual(v, ["RETRY", "RETRY", "ESCALATE"])

    def test_spent_budget_stops(self):
        cfg = dict(self.config, cycle_round_budget=2, gate_retry_cap=0)
        v = [R.gate(self.ledger, "5", 1, cfg)["verdict"] for _ in range(2)]
        self.assertEqual(v, ["RETRY", "STOP_BUDGET"])

    def test_bad_exit_code_fails_closed(self):
        with self.assertRaises(R.Problem):
            R.gate(self.ledger, "5", 7, self.config)

    def test_cli(self):
        proc = subprocess.run(
            [sys.executable, str(REVIEW_PY), "gate", str(self.ledger),
             "--gate", "5", "--exit", "1", "--evidence", "1 new failure"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual((out["verdict"], out["budget"]["spent"]), ("RETRY", 1))
        self.assertEqual(self.ledger_data()["gates"][0]["evidence"], "1 new failure")


class ConfigTest(Case):
    def test_a_foreign_config_cannot_bring_a_looser_budget(self):
        (self.root / ".sage" / "config.yaml").write_text(
            "review_loop:\n  cycle_round_budget: 2\n", encoding="utf-8")
        loose = self.root / "loose.yaml"
        loose.write_text("review_loop:\n  cycle_round_budget: 0\n"
                         "  gate_retry_cap: 0\n  max_fixes_per_round: 1\n",
                         encoding="utf-8")
        for _ in range(2):
            proc = subprocess.run(
                [sys.executable, str(REVIEW_PY), "gate", str(self.ledger),
                 "--gate", "5", "--exit", "1", "--config", str(loose)],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["verdict"], "STOP_BUDGET")       # 2, not "off"
        self.assertEqual(out["budget"]["limit"], 2)


class LedgerPathTest(Case):
    def test_a_second_ledger_in_a_cycle_is_refused(self):
        other = self.cycle / "review-ledger2.json"
        proc = subprocess.run(
            [sys.executable, str(REVIEW_PY), "gate", str(other),
             "--gate", "5", "--exit", "1"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("one per cycle", proc.stderr)
        self.assertFalse(other.exists())


class SummaryTest(Case):
    def test_spent_budget_summary_is_the_whole_hand_off(self):
        cfg = dict(self.config, cycle_round_budget=2)
        (self.cycle / "verify-baseline.json").write_text(
            json.dumps({"failing": ["a", "b"]}), encoding="utf-8")
        R.gate(self.ledger, "5", 1, cfg, "tests/x::y failed")
        R.open_instance(self.ledger, "code", cfg)
        self.intake([finding("NaN poisons", witness=REPRO),
                     finding("style", "cosmetic", region=(9, 9))])
        self.assertEqual(self.close(1, cfg)["action"], "STOP_BUDGET")
        text = R.summary(self.ledger, cfg)
        self.assertIn("used its review budget (2 of 2", text)
        self.assertIn("code 1 (STOP_BUDGET)", text)
        self.assertIn("Gate 5: 1 failed attempt(s)", text)
        self.assertIn("F-001 [major] NaN poisons", text)
        self.assertIn("Not acted on (no witness or citation): 1", text)
        self.assertIn("baseline): 2", text)
        self.assertIn("[C] Continue — raise review_loop.cycle_round_budget", text)

    def test_unspent_summary_offers_no_menu(self):
        self.intake([])
        self.close(1)
        self.assertNotIn("[C]", R.summary(self.ledger, self.config))


if __name__ == "__main__":
    unittest.main(verbosity=2)
