#!/usr/bin/env python3
"""
test_review_schema.py — schema-v2 conformance across the four review
capabilities (40-§1).

Three claims, grep-level and end-to-end: (1) every v2 section carries
the load-bearing verbatim texts — the no-verdict line, witness-or-
downgrade, and the precision-not-volume calibration block; (2) no v2
section offers the reviewer a verdict channel (VERDICT/ACCEPT/REVISE/
RESULT) — the observed pathology was the reviewer protecting its
diligence signal, and the channel stays removed; (3) a canned reviewer
transcript in the documented format round-trips through review.py
intake — the schema the prompts promise is the schema the tool parses.

Usage:  python3 develop/validators/review/test_review_schema.py
Exit:   0 = all pass | 1 = a test failed
Python 3.8+, stdlib only.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "tools"))

import review as R  # noqa: E402

CAPABILITIES = {
    "auto-review": REPO_ROOT / "core/capabilities/review/auto-review/SKILL.md",
    "spec-review": REPO_ROOT / "core/capabilities/review/spec-review/SKILL.md",
    "quality-review": REPO_ROOT / "core/capabilities/review/quality-review/SKILL.md",
    "auto-qa": REPO_ROOT / "core/capabilities/review/auto-qa/SKILL.md",
}

NO_VERDICT_LINE = "You do not decide the loop; you report findings."
WITNESS_TEXT = "A critical or major must come with a witness"
CALIBRATION_TEXT = ("An empty finding list is a valid, creditable outcome; "
                    "you are scored\n> on precision, not volume.")
VERDICT_TOKENS = ("VERDICT:", "ACCEPT", "REVISE", "RESULT: PASS")


def v2_section(text: str) -> str:
    m = re.search(r"^## Review Loop v2.*?(?=^## |\Z)", text,
                  re.MULTILINE | re.DOTALL)
    return m.group(0) if m else ""


CANNED_TRANSCRIPT = """I reviewed the diff against the spec. Reasoning prose
here is fine — it is not parsed.

```json
[{
  "pass": "spec-conformance",
  "severity": "major",
  "cited_rule": "spec §2",
  "anchor": {"file": "src/wallet.py", "region": [1, 2]},
  "claim": "withdraw permits an overdraft",
  "witness": {"kind": "repro", "ref": "deposit 100, withdraw 150", "status": "n/a"},
  "exit_criteria": "overdraft raises InsufficientFunds"
},
{
  "pass": "completeness",
  "severity": "major",
  "cited_rule": "spec §8",
  "anchor": {"file": "src/wallet.py", "region": [1, 1]},
  "claim": "spec section 8 close has no implementation",
  "witness": {"kind": "trace", "ref": "matrix row 8: empty", "status": "n/a"},
  "exit_criteria": "close implemented and tested"
}]
```

Trailing prose is also not parsed.
"""


class VerbatimTextsTest(unittest.TestCase):
    def test_every_capability_carries_the_contract(self):
        for name, path in CAPABILITIES.items():
            section = v2_section(path.read_text(encoding="utf-8"))
            self.assertTrue(section, f"{name}: no '## Review Loop v2' section")
            for required in (NO_VERDICT_LINE, WITNESS_TEXT, CALIBRATION_TEXT):
                self.assertIn(required, section,
                              f"{name}: v2 section lost the verbatim text "
                              f"{required[:40]!r}")
            self.assertIn("```json", section,
                          f"{name}: v2 section has no JSON output schema")

    def test_no_verdict_channel_in_v2_sections(self):
        for name, path in CAPABILITIES.items():
            section = v2_section(path.read_text(encoding="utf-8"))
            for token in VERDICT_TOKENS:
                self.assertNotIn(token, section,
                                 f"{name}: v2 section contains the verdict "
                                 f"token {token!r} — the channel returned")

    def test_pass_vocabulary_matches_the_ledger(self):
        for name, path in CAPABILITIES.items():
            section = v2_section(path.read_text(encoding="utf-8"))
            m = re.search(r'"pass":\s*"([^"]+)"', section)
            self.assertTrue(m, f"{name}: no pass field in the v2 schema")
            for token in (t.strip() for t in m.group(1).split("|")):
                self.assertIn(token, R.PASSES,
                              f"{name}: pass {token!r} is not in review.py "
                              f"PASSES — the vocabulary drifted")

    def test_loop_skill_drives_the_tool(self):
        loop = (REPO_ROOT / "core/capabilities/orchestration/quality-locked"
                / "SKILL.md").read_text(encoding="utf-8")
        section = v2_section(loop)
        for cmd in ("review.py verify", "review.py intake",
                    "review.py close-round", "review.py check-diff",
                    "review.py attach-witness"):
            self.assertIn(cmd, section, f"loop skill lost {cmd}")


class CannedTranscriptTest(unittest.TestCase):
    """The documented emission format parses through the real tool."""

    def test_fenced_block_round_trips_through_intake(self):
        root = pathlib.Path(tempfile.mkdtemp(prefix="schema-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / ".sage" / "work" / "s").mkdir(parents=True)
        (root / "src").mkdir()
        (root / "src" / "wallet.py").write_text("a\nb\n", encoding="utf-8")
        blocks = re.findall(r"```json\n(.*?)```", CANNED_TRANSCRIPT, re.DOTALL)
        self.assertEqual(len(blocks), 1)
        findings = json.loads(blocks[0])
        ledger = root / ".sage" / "work" / "s" / "review-ledger.json"
        rep = R.intake(ledger, findings, 1, "code", root,
                       dict(R.CONFIG_DEFAULTS, mode="v2"))
        self.assertEqual(len(rep["new"]), 2)
        entries = json.loads(ledger.read_text(encoding="utf-8"))["findings"]
        self.assertEqual(entries[0]["severity"], "major")   # witnessed: no cap
        self.assertEqual(entries[1]["witness"]["kind"], "trace")


if __name__ == "__main__":
    unittest.main()
