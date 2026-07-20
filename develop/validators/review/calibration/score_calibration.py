#!/usr/bin/env python3
"""
score_calibration.py — deterministic scoring for the calibration fixture (RR-27).

The fixture (develop/evals/fixtures/py-calibration) carries planted
defects; answers.json is the key. This scorer takes a reviewer's
findings — a raw RR-10 array or a review-ledger.json — and reports:

  recall     matched critical+major plants / planted critical+major (>= 0.8)
  precision  reported critical/major findings that match ANY plant (>= 0.7)
  absences   both spec clauses with no implementation caught by trace rows
  decoy      the pre-rejected finding NOT re-raised

Exit 0 when every threshold holds, 1 otherwise. Drift in these numbers
under a live model is a reviewer-prompt regression — run per release
alongside the gate tests.

Usage:
  python3 score_calibration.py --findings <findings.json|review-ledger.json>
  python3 score_calibration.py --self-test    # score the answer key's own
                                              # exemplars; must be perfect

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def load_answers():
    return json.loads((HERE / "answers.json").read_text(encoding="utf-8"))


def load_findings(path: pathlib.Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("findings", [])
    if not isinstance(data, list):
        raise SystemExit(f"✗ {path}: expected a findings array or a ledger")
    return data


def overlaps(a, b) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def claim_of(f) -> str:
    return str(f.get("claim") or "").lower()


def matches_plant(finding, plant) -> bool:
    anchor = finding.get("anchor") or {}
    if anchor.get("file") != plant["file"]:
        return False
    region = anchor.get("region") or [0, 0]
    if not overlaps([int(region[0]), int(region[1])], plant["region"]):
        return False
    return any(k in claim_of(finding) for k in plant["keywords"])


def matches_absence(finding, absence) -> bool:
    # An absence counts when it was made OBSERVABLE — an empty matrix cell
    # (kind trace, or a matrix pass) or an actual demonstration (a written
    # failing test / repro observing the missing behavior). The first
    # measured run punished reviewers who wrote a real red test for the
    # absence instead of a trace cell; a demonstration outranks a cell,
    # it must never score below one.
    kind = (finding.get("witness") or {}).get("kind")
    in_matrix_pass = finding.get("pass") in ("completeness", "spec-conformance")
    if kind not in ("trace", "test", "repro") and not in_matrix_pass:
        return False
    return any(k in claim_of(finding) for k in absence["keywords"])


def score(findings: list, answers: dict) -> dict:
    plants = answers["plants"]
    blocking_plants = [p for p in plants if p["severity"] in ("critical", "major")]

    matched = set()
    for plant in plants:
        if any(matches_plant(f, plant) for f in findings):
            matched.add(plant["id"])

    reported_blocking = [f for f in findings
                         if f.get("severity") in ("critical", "major")]
    true_positive = [f for f in reported_blocking
                     if any(matches_plant(f, p) for p in plants)
                     or any(matches_absence(f, a) for a in answers["absences"])]

    recall = (len([p for p in blocking_plants if p["id"] in matched])
              / len(blocking_plants))
    precision = (len(true_positive) / len(reported_blocking)
                 if reported_blocking else 1.0)

    absences_caught = [a["id"] for a in answers["absences"]
                       if any(matches_absence(f, a) for f in findings)]

    decoy = answers["decoy"]
    decoy_re_raised = any(
        (f.get("anchor") or {}).get("file") == decoy["file"]
        and any(k in claim_of(f) for k in decoy["keywords"])
        for f in findings)

    t = answers["thresholds"]
    result = {
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "matched_plants": sorted(matched),
        "absences_caught": absences_caught,
        "decoy_re_raised": decoy_re_raised,
        "thresholds": t,
        "pass": (recall >= t["recall"] and precision >= t["precision"]
                 and len(absences_caught) == len(answers["absences"])
                 and not decoy_re_raised),
    }
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--findings", type=pathlib.Path)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    answers = load_answers()
    if args.self_test:
        result = score(answers["exemplars"], answers)
        perfect = (result["recall"] == 1.0 and result["precision"] == 1.0
                   and result["pass"])
        print(json.dumps(result))
        if not perfect:
            print("✗ self-test: the answer key's own exemplars do not score "
                  "perfectly — key and scorer disagree", file=sys.stderr)
            return 1
        return 0

    if not args.findings:
        ap.error("--findings or --self-test required")
    result = score(load_findings(args.findings), answers)
    print(json.dumps(result))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
