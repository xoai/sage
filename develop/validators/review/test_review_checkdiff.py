#!/usr/bin/env python3
"""
test_review_checkdiff.py — the fix stays inside its finding (40-§1, RR-21/23/24).

check-diff is the insurance that makes aggressive fixing safe: a fix
round cannot silently manufacture the next round's findings. In-scope
hunks pass; an out-of-scope hunk exits 1 AND lands in the ledger as a
machine finding witnessed by the hunk itself; a modified non-witness
test without a Sage-License trailer exits 1 (correctness is amended
through the spec, never redefined in the diff); malformed trailers are
advisory — a finding, not a block.

Usage:  python3 develop/validators/review/test_review_checkdiff.py
Exit:   0 = all pass | 1 = a test failed
Python 3.8+, stdlib only (git required, as for manifest.py sync).
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

SRC = """def apply_discount(total, percent):
    if percent < 0:
        raise ValueError("negative")
    return total - (total * percent / 100)


def unrelated_helper():
    return 42
"""


class CheckDiffCase(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="review-diff-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / ".sage" / "work" / "20260720-fix").mkdir(parents=True)
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "src" / "cart.py").write_text(SRC, encoding="utf-8")
        (self.root / "tests" / "test_cart.py").write_text(
            "def test_existing():\n    assert True\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", "-A")
        self.commit_all("seed")
        self.ledger = (self.root / ".sage" / "work" / "20260720-fix"
                       / "review-ledger.json")
        self.config = dict(R.CONFIG_DEFAULTS, mode="v2")
        # The finding: anchored on the discount function body (lines 1-4).
        R.intake(self.ledger, [{
            "pass": "input-hostility", "severity": "major",
            "cited_rule": "spec §2.1",
            "anchor": {"file": "src/cart.py", "region": [1, 4]},
            "claim": "percent over 100 is not rejected",
            "witness": {"kind": "test", "ref": "tests/review/F-001.py",
                        "status": "red"},
            "exit_criteria": "percent > 100 raises ValueError",
        }], 1, "code", self.root, self.config)

    def git(self, *args):
        subprocess.run(["git"] + list(args), cwd=str(self.root), check=True,
                       capture_output=True)

    def commit_all(self, message):
        self.git("add", "-A")
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-q", "-m", message], cwd=str(self.root),
                       check=True, capture_output=True)
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(self.root),
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()

    TRAILERS = ("Sage-Fix: F-001\nSage-Cause: bound never checked\n"
                "Sage-Change: reject percent > 100\n"
                "Sage-Risk: callers passing 150 now raise\n")

    def check(self, sha, **kw):
        return R.check_diff(self.ledger, "F-001", sha, self.root,
                            kw.pop("config", self.config), **kw)

    def entries(self):
        return json.loads(self.ledger.read_text(encoding="utf-8"))["findings"]

    def test_in_scope_fix_passes(self):
        (self.root / "src" / "cart.py").write_text(
            SRC.replace('raise ValueError("negative")',
                        'raise ValueError("negative")\n'
                        '    if percent > 100:\n'
                        '        raise ValueError("over 100")'),
            encoding="utf-8")
        (self.root / "tests" / "review").mkdir(parents=True)
        (self.root / "tests" / "review" / "F-001.py").write_text(
            "def test_over():\n    pass\n", encoding="utf-8")
        sha = self.commit_all("fix\n\n" + self.TRAILERS)
        result = self.check(sha)
        self.assertTrue(result["in_scope"])
        self.assertTrue(result["license_ok"])
        self.assertEqual(result["trailer_findings"], [])
        self.assertEqual(len(self.entries()), 1)     # no machine finding

    def test_out_of_scope_hunk_becomes_a_finding(self):
        # The "while I'm here" temptation: an edit far from the anchor.
        (self.root / "src" / "cart.py").write_text(
            SRC.replace("return 42", "return 43"), encoding="utf-8")
        sha = self.commit_all("fix\n\n" + self.TRAILERS)
        result = self.check(sha)
        self.assertFalse(result["in_scope"])
        entries = self.entries()
        self.assertEqual(len(entries), 2)
        machine = entries[1]
        self.assertEqual(machine["pass"], "regression-surface")
        self.assertEqual(machine["severity"], "major")
        self.assertEqual(machine["status"], "open")
        self.assertIn("outside", machine["claim"])
        self.assertEqual(machine["witness"]["kind"], "repro")

    def test_declared_collateral_passes(self):
        (self.root / "src" / "cart.py").write_text(
            SRC.replace("return 42", "return 43"), encoding="utf-8")
        sha = self.commit_all(
            "fix\n\n" + self.TRAILERS
            + "Sage-Collateral: src/cart.py:7-8 (helper return updated)\n")
        result = self.check(sha)
        self.assertTrue(result["in_scope"])
        self.assertEqual(len(self.entries()), 1)

    def test_modified_test_without_license_exits_1(self):
        (self.root / "tests" / "test_cart.py").write_text(
            "def test_existing():\n    assert 1 == 1\n", encoding="utf-8")
        sha = self.commit_all("fix\n\n" + self.TRAILERS)
        result = self.check(sha)
        self.assertFalse(result["license_ok"])
        self.assertEqual(result["license_needed"], ["tests/test_cart.py"])

    def test_modified_test_with_license_passes(self):
        (self.root / "tests" / "test_cart.py").write_text(
            "def test_existing():\n    assert 1 == 1\n", encoding="utf-8")
        sha = self.commit_all("fix\n\n" + self.TRAILERS
                              + "Sage-License: spec §2.1\n")
        result = self.check(sha)
        self.assertTrue(result["license_ok"])

    def test_witness_test_needs_no_license(self):
        (self.root / "tests" / "review").mkdir(parents=True)
        (self.root / "tests" / "review" / "F-001.py").write_text(
            "def test_over():\n    pass\n", encoding="utf-8")
        sha = self.commit_all("fix\n\n" + self.TRAILERS)
        result = self.check(sha)
        self.assertTrue(result["license_ok"])
        self.assertTrue(result["in_scope"])

    def test_missing_trailers_are_advisory_not_blocking(self):
        (self.root / "src" / "cart.py").write_text(
            SRC.replace('"negative"', '"neg"'), encoding="utf-8")
        sha = self.commit_all("fix with no trailers")
        result = self.check(sha)
        self.assertTrue(result["in_scope"])          # scope itself is fine
        self.assertTrue(result["trailer_findings"])
        entries = self.entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["severity"], "substantive")

    def test_scope_check_off_restores_v1(self):
        (self.root / "src" / "cart.py").write_text(
            SRC.replace("return 42", "return 43"), encoding="utf-8")
        sha = self.commit_all("fix\n\n" + self.TRAILERS)
        cfg = dict(self.config, scope_check=False)
        result = self.check(sha, config=cfg)
        self.assertTrue(result["in_scope"])
        self.assertIn("skipped", result)

    def test_cli_exit_codes(self):
        (self.root / "src" / "cart.py").write_text(
            SRC.replace("return 42", "return 43"), encoding="utf-8")
        sha = self.commit_all("fix\n\n" + self.TRAILERS)
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "runtime" / "tools" / "review.py"),
             "check-diff", str(self.ledger), "--finding", "F-001",
             "--commit", sha, "--repo-root", str(self.root)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn('"in_scope": false', proc.stdout)


class TrailerParserTest(unittest.TestCase):
    def test_parses_all_keys_and_repeats(self):
        t = R.parse_trailers(
            "fix the thing\n\nSage-Fix: F-003\nSage-Cause: reused grant\n"
            "Sage-Change: rotate() called\nSage-Risk: one forced re-auth\n"
            "Sage-Collateral: src/a.ts:1-2 (x)\n"
            "Sage-Collateral: src/b.ts:3-4 (y)\nSage-License: spec §4.2\n")
        self.assertEqual(t["Fix"], ["F-003"])
        self.assertEqual(len(t["Collateral"]), 2)
        self.assertEqual(t["License"], ["spec §4.2"])

    def test_ignores_unknown_and_prose(self):
        t = R.parse_trailers("Sage-Vibes: good\nno trailers here\n")
        self.assertEqual(t, {})

    def test_hunk_parser_unified0(self):
        diff = ("diff --git a/src/x.py b/src/x.py\n"
                "--- a/src/x.py\n+++ b/src/x.py\n"
                "@@ -7 +7 @@ def f():\n-    return 42\n+    return 43\n"
                "@@ -12,0 +13,2 @@\n+a\n+b\n")
        hunks = R.parse_hunks(diff)
        self.assertEqual(hunks, [("src/x.py", 7, 1, 7, 1),
                                 ("src/x.py", 12, 0, 13, 2)])

    def test_test_path_detection(self):
        for p in ("tests/test_x.py", "src/__tests__/x.js", "a/x.test.ts",
                  "a/x.spec.js", "test/x.py", "pkg/foo_test.go"):
            self.assertTrue(R.is_test_path(p), p)
        for p in ("src/x.py", "contest/x.py", "src/attest.py"):
            self.assertFalse(R.is_test_path(p), p)


if __name__ == "__main__":
    unittest.main()
