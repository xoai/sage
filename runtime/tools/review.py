#!/usr/bin/env python3
"""review.py — the review-findings ledger: facts recorded, decisions computed.

WHY THIS EXISTS, AND WHY IT IS A SCRIPT AND NOT A PARAGRAPH

The review-revise loop used to run to its cap on findings that never
blocked. A production history showed 7 iterations, zero criticals
throughout, major counts churning non-monotonically, majors reappearing
after reaching zero, and a REVISE verdict issued on an iteration with
0 critical / 0 major. Root causes: the reviewer owned the verdict (an
adversarial reviewer will not say "nothing found"); each iteration was a
blind fresh sample of the objection space; nothing distinguished a
demonstrated defect from an opinion.

So the reviewer reports FACTS and this tool records them. The verdict is
computed by sage_flags.decide() from ledger state — never reported by a
model. Findings without evidence are opinions and never block (they are
capped at substantive on intake). Findings, once written down, cannot be
forgotten or silently re-raised: the re-litigation guard makes fingerprint
drift the only license to contradict a settled entry.

    "If a rule matters, make it code. If you can't, don't claim it."

Usage:
    review.py intake  <ledger.json> --iteration N \\
                      (--findings-file F | --findings-json J) [--artifact code]
    review.py verify  <ledger.json> --iteration N \\
                      (--results-file F | --results-json J)
    review.py verify  <ledger.json> --iteration N \\
                      --cannot-reproduce F-003 --evidence TEXT
    review.py attach-witness <ledger.json> F-003 --ref PATH \\
                      [--kind test|repro|trace] [--status red|green|n/a]
    review.py disposition <ledger.json> F-003 --action defer|reject|fix-now \\
                      [--reason TEXT] [--ticket REF]
    review.py close-round <ledger.json> --iteration N
    review.py report  <ledger.json>

The ledger lives at .sage/work/<slug>/review-ledger.json, one per cycle,
created and mutated only through these subcommands — machine-owned like
the manifest's frontmatter. This is bookkeeping, not a hook, so it FAILS
CLOSED (RR-4): a malformed ledger, an unknown finding ID, or an anchor
that no longer exists stops the loop loudly with exit 1. The fail-open
rule for hooks does not apply here.

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import pathlib
import re
import sys


class Problem(Exception):
    """A specific, actionable bookkeeping error. Never a guess."""


# ═══════════════════════════════════════════════════════════════════════
# Vocabulary (RR-2)
# ═══════════════════════════════════════════════════════════════════════

SEVERITIES = ("critical", "major", "substantive", "cosmetic")
ARTIFACTS = ("spec", "plan", "code", "adr")
PASSES = ("input-hostility", "state-and-flow", "spec-conformance", "security",
          "regression-surface", "testability", "completeness", "consistency",
          "risk-concentration")
WITNESS_KINDS = ("test", "repro", "trace", "none")
WITNESS_STATUSES = ("red", "green", "n/a")
STATUSES = ("open", "fixed", "not-fixed", "disputed", "deferred", "rejected")
OPEN_STATUSES = ("open", "not-fixed")          # what counts toward the verdict
SETTLED_STATUSES = ("rejected", "fixed")        # what the re-litigation guard defends
VERIFY_VERDICTS = ("FIXED", "NOT-FIXED", "DISPUTED-STANDS")
DISPOSITIONS = ("defer", "reject", "fix-now")

LEDGER_VERSION = 1


# ═══════════════════════════════════════════════════════════════════════
# The controller lives in sage_flags.py (RR-5) — load the sibling module.
# ═══════════════════════════════════════════════════════════════════════

def _load_sage_flags():
    path = pathlib.Path(__file__).resolve().parent / "sage_flags.py"
    spec = importlib.util.spec_from_file_location("sage_flags", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════════════════════════════
# Ledger I/O — fail closed on anything malformed (RR-4)
# ═══════════════════════════════════════════════════════════════════════

def load_ledger(path: pathlib.Path) -> dict:
    if not path.is_file():
        raise Problem(f"no ledger at {path} — `intake` creates it")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Problem(f"malformed ledger {path}: {exc}")
    if not isinstance(data, dict) or "findings" not in data or "history" not in data:
        raise Problem(f"malformed ledger {path}: missing findings/history")
    for entry in data["findings"]:
        if not isinstance(entry, dict) or "id" not in entry or "status" not in entry:
            raise Problem(f"malformed ledger {path}: finding without id/status")
        if entry["status"] not in STATUSES:
            raise Problem(f"malformed ledger {path}: {entry['id']} has "
                          f"unknown status {entry['status']!r}")
    return data


def new_ledger(slug: str) -> dict:
    return {"version": LEDGER_VERSION, "slug": slug, "findings": [],
            "history": [], "rounds": [], "next_id": 1}


def save_ledger(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def find_entry(ledger: dict, finding_id: str) -> dict:
    for entry in ledger["findings"]:
        if entry["id"] == finding_id:
            return entry
    raise Problem(f"unknown finding ID {finding_id!r} — the ledger has "
                  f"{', '.join(e['id'] for e in ledger['findings']) or 'no entries'}")


def slug_of(ledger_path: pathlib.Path) -> str:
    # .sage/work/<slug>/review-ledger.json — the slug is the cycle dir.
    return ledger_path.resolve().parent.name


def repo_root_of(ledger_path: pathlib.Path) -> pathlib.Path:
    # Walk up from the ledger looking for the .sage/ dir it lives under;
    # fall back to cwd for ledgers placed elsewhere (tests, fixtures).
    p = ledger_path.resolve().parent
    while p != p.parent:
        if (p / ".sage").is_dir():
            return p
        p = p.parent
    return pathlib.Path.cwd()


# ═══════════════════════════════════════════════════════════════════════
# Config (RR-8) — the review_loop: block of .sage/config.yaml
# ═══════════════════════════════════════════════════════════════════════

# Every knob's v1-restoring value, documented beside it (the 1.3.5 lever
# pattern). `mode: v1` restores the whole pre-ledger loop at once.
CONFIG_DEFAULTS = {
    "mode": "v1",                # v1 restores: reviewer-owned verdict loop
    "major_budget": 0,           # v1 n/a (majors always blocked)
    "iteration_cap": 5,          # v1 value: 10
    "escalate_after_stalls": 2,  # v1: 3 identical critical+major counts
    "witness_capping": True,     # False restores: severity as reported
    "scope_check": True,         # False restores: no diff-scope check
    "review_model": "inherit",   # inherit restores: no model routing
}

_BLOCK_RE = re.compile(r"^review_loop:\s*$", re.MULTILINE)
_ITEM_RE = re.compile(r"^\s{2}([a-z_]+):\s*([^\s#]+)")


def load_config(config_path) -> dict:
    """Parse the review_loop: block. Fail-soft like load_defaults():
    missing file or absent block means defaults — an unconfigured project
    must behave exactly like a v1 project."""
    cfg = dict(CONFIG_DEFAULTS)
    if not config_path:
        return cfg
    path = pathlib.Path(config_path)
    if not path.is_file():
        return cfg
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return cfg
    m = _BLOCK_RE.search(text)
    if not m:
        return cfg
    for line in text[m.end():].splitlines():
        if line.strip() and not line.startswith("  "):
            break                                   # dedent ends the block
        item = _ITEM_RE.match(line)
        if not item or item.group(1) not in cfg:
            continue
        key, raw = item.group(1), item.group(2)
        default = CONFIG_DEFAULTS[key]
        if isinstance(default, bool):
            if raw in ("true", "false"):
                cfg[key] = raw == "true"
        elif isinstance(default, int):
            try:
                cfg[key] = int(raw)
            except ValueError:
                pass
        else:
            cfg[key] = raw
    return cfg


# ═══════════════════════════════════════════════════════════════════════
# Fingerprints (RR-2/RR-3) — stable under whitespace and reflow
# ═══════════════════════════════════════════════════════════════════════

def normalize_region(text: str) -> str:
    """Collapse ALL whitespace runs (including newlines) to single spaces,
    so re-indenting or re-wrapping the same words does not change the
    fingerprint. Content changes do."""
    return " ".join(text.split())


def fingerprint_region(repo_root: pathlib.Path, file_rel: str, region) -> str:
    path = repo_root / file_rel
    if not path.is_file():
        raise Problem(f"anchor file {file_rel!r} does not exist under {repo_root}")
    try:
        start, end = int(region[0]), int(region[1])
    except (TypeError, ValueError, IndexError):
        raise Problem(f"anchor region for {file_rel!r} must be [start, end], "
                      f"got {region!r}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if start < 1 or end < start or start > len(lines):
        raise Problem(f"anchor region [{start}, {end}] does not fit "
                      f"{file_rel!r} ({len(lines)} lines)")
    chunk = "\n".join(lines[start - 1:min(end, len(lines))])
    return hashlib.sha1(normalize_region(chunk).encode("utf-8")).hexdigest()


def claim_stem(claim: str) -> str:
    """Lowercased alphanumeric tokens — 'Refresh token is NOT rotated!' and
    'refresh token is not rotated' are the same claim."""
    return " ".join(re.findall(r"[a-z0-9]+", (claim or "").lower()))


# ═══════════════════════════════════════════════════════════════════════
# intake — normalize findings mechanically (RR-3)
# ═══════════════════════════════════════════════════════════════════════

def _validate_finding(raw: dict, index: int) -> None:
    if not isinstance(raw, dict):
        raise Problem(f"finding #{index} is not an object")
    for field in ("severity", "claim", "anchor"):
        if field not in raw:
            raise Problem(f"finding #{index} is missing {field!r}")
    if raw["severity"] not in SEVERITIES:
        raise Problem(f"finding #{index} has unknown severity "
                      f"{raw['severity']!r} (one of {', '.join(SEVERITIES)})")
    anchor = raw["anchor"]
    if not isinstance(anchor, dict) or "file" not in anchor or "region" not in anchor:
        raise Problem(f"finding #{index} anchor must carry file + region")
    witness = raw.get("witness") or {}
    kind = witness.get("kind", "none")
    if kind not in WITNESS_KINDS:
        raise Problem(f"finding #{index} witness kind {kind!r} is not one of "
                      f"{', '.join(WITNESS_KINDS)}")


def _has_witness(raw: dict) -> bool:
    """A witness of kind test/repro/trace demonstrates; kind none does not.
    For spec/plan artifacts an empty trace-matrix cell arrives as kind
    `trace` — absence made observable counts as a demonstration (RR-3.1)."""
    kind = (raw.get("witness") or {}).get("kind", "none")
    return kind in ("test", "repro", "trace")


def intake(ledger_path: pathlib.Path, findings: list, iteration: int,
           artifact: str, repo_root: pathlib.Path, config: dict) -> dict:
    if ledger_path.is_file():
        ledger = load_ledger(ledger_path)
    else:
        ledger = new_ledger(slug_of(ledger_path))    # creation is allowed

    by_fingerprint = {}
    for entry in ledger["findings"]:
        by_fingerprint.setdefault(entry["anchor"]["fingerprint"], []).append(entry)

    report = {"new": [], "merged": [], "capped": [], "disputed": []}
    for i, raw in enumerate(findings):
        _validate_finding(raw, i)
        fp = fingerprint_region(repo_root, raw["anchor"]["file"],
                                raw["anchor"]["region"])
        stem = claim_stem(raw["claim"])
        witness = dict(raw.get("witness") or {"kind": "none", "ref": None,
                                              "status": "n/a"})
        witness.setdefault("kind", "none")
        witness.setdefault("ref", None)
        witness.setdefault("status", "n/a")

        # RR-3.1 — severity capping: a critical/major that cites nothing and
        # demonstrates nothing is an opinion; opinions never block.
        severity_as_reported = raw["severity"]
        severity = severity_as_reported
        if (config.get("witness_capping", True)
                and severity in ("critical", "major")
                and not raw.get("cited_rule")
                and not _has_witness(raw)):
            severity = "substantive"

        # RR-3.3 — re-litigation guard: contradicting a settled entry needs
        # fingerprint drift since settlement. An identical fingerprint means
        # the region has not changed; sampling noise loses to the record.
        settled = [e for e in by_fingerprint.get(fp, [])
                   if e["status"] in SETTLED_STATUSES]

        # RR-3.2 — dedup: same region text + same claim is the same finding.
        duplicates = [e for e in by_fingerprint.get(fp, [])
                      if e["status"] not in SETTLED_STATUSES
                      and claim_stem(e["claim"]) == stem]

        if duplicates:
            entry = duplicates[0]
            entry["raised_count"] = entry.get("raised_count", 1) + 1
            report["merged"].append(entry["id"])
            continue

        entry = {
            "id": "F-%03d" % ledger["next_id"],
            "artifact": raw.get("artifact", artifact),
            "first_seen": iteration,
            "pass": raw.get("pass"),
            "severity": severity,
            "severity_as_reported": severity_as_reported,
            "cited_rule": raw.get("cited_rule"),
            "anchor": {"file": raw["anchor"]["file"],
                       "region": list(raw["anchor"]["region"]),
                       "fingerprint": fp},
            "claim": raw["claim"],
            "witness": witness,
            "exit_criteria": raw.get("exit_criteria"),
            "status": "disputed" if settled else "open",
            "raised_count": 1,
            "verifications": [],
            "disposition": None,
        }
        if settled:
            entry["relitigates"] = settled[0]["id"]
            report["disputed"].append(entry["id"])
        elif severity != severity_as_reported:
            report["capped"].append(entry["id"])
            report["new"].append(entry["id"])
        else:
            report["new"].append(entry["id"])
        ledger["next_id"] += 1
        ledger["findings"].append(entry)
        by_fingerprint.setdefault(fp, []).append(entry)

    save_ledger(ledger_path, ledger)
    return report


# ═══════════════════════════════════════════════════════════════════════
# verify — Phase A results land as facts (RR-14, RR-19)
# ═══════════════════════════════════════════════════════════════════════

VERDICT_TO_STATUS = {"FIXED": "fixed", "NOT-FIXED": "not-fixed",
                     "DISPUTED-STANDS": "disputed"}


def verify(ledger_path: pathlib.Path, results: list, iteration: int) -> list:
    ledger = load_ledger(ledger_path)
    touched = []
    for res in results:
        if not isinstance(res, dict) or "id" not in res or "verdict" not in res:
            raise Problem("each verify result needs id + verdict")
        if res["verdict"] not in VERIFY_VERDICTS:
            raise Problem(f"verdict {res['verdict']!r} is not one of "
                          f"{', '.join(VERIFY_VERDICTS)}")
        if not res.get("evidence"):
            raise Problem(f"{res['id']}: a verification without evidence is "
                          "an impression — record what was checked")
        entry = find_entry(ledger, res["id"])
        entry["verifications"].append({"iteration": iteration,
                                       "verdict": res["verdict"],
                                       "evidence": res["evidence"]})
        entry["status"] = VERDICT_TO_STATUS[res["verdict"]]
        if res["verdict"] == "FIXED" and entry.get("disposition") == "fix-now":
            entry["disposition"] = None          # the bought round paid off
        touched.append(entry["id"])
    save_ledger(ledger_path, ledger)
    return touched


def cannot_reproduce(ledger_path: pathlib.Path, finding_id: str,
                     evidence: str, iteration: int) -> None:
    """RR-19: a witness that cannot be reproduced at HEAD bounces the finding
    to the controller as disputed — never silently skipped."""
    if not evidence:
        raise Problem("--cannot-reproduce requires --evidence (the run output)")
    ledger = load_ledger(ledger_path)
    entry = find_entry(ledger, finding_id)
    entry["verifications"].append({"iteration": iteration,
                                   "verdict": "DISPUTED-STANDS",
                                   "evidence": "cannot reproduce: " + evidence})
    entry["status"] = "disputed"
    save_ledger(ledger_path, ledger)


# ═══════════════════════════════════════════════════════════════════════
# attach-witness / disposition
# ═══════════════════════════════════════════════════════════════════════

def attach_witness(ledger_path: pathlib.Path, finding_id: str, ref: str,
                   kind: str, status: str) -> None:
    ledger = load_ledger(ledger_path)
    entry = find_entry(ledger, finding_id)
    entry["witness"] = {"kind": kind, "ref": ref, "status": status}
    save_ledger(ledger_path, ledger)


def disposition(ledger_path: pathlib.Path, finding_id: str, action: str,
                reason, ticket) -> None:
    """Record the decision about a remaining entry. defer/reject are
    PENDING until close-round seals the round — the verdict is computed
    over what the round actually found, then the paperwork settles.
    fix-now keeps the entry open and buys exactly one more round."""
    ledger = load_ledger(ledger_path)
    entry = find_entry(ledger, finding_id)
    if entry["status"] not in OPEN_STATUSES and entry["status"] != "disputed":
        raise Problem(f"{finding_id} is {entry['status']} — dispositions apply "
                      "to open, not-fixed, or disputed entries")
    if action == "defer":
        if not ticket:
            raise Problem("defer requires --ticket — a deferral without a "
                          "ticket is a deletion with extra steps")
        entry["disposition"] = {"action": "defer", "ticket": ticket}
    elif action == "reject":
        if not reason:
            raise Problem("reject requires --reason")
        entry["disposition"] = {"action": "reject", "reason": reason}
    else:                                        # fix-now
        entry["disposition"] = "fix-now"         # stays open; buys one round
    save_ledger(ledger_path, ledger)


# ═══════════════════════════════════════════════════════════════════════
# close-round — the verdict is computed, recorded, and logged (RR-6/RR-7)
# ═══════════════════════════════════════════════════════════════════════

def open_entries(ledger: dict) -> list:
    return [e for e in ledger["findings"] if e["status"] in OPEN_STATUSES]


def close_round(ledger_path: pathlib.Path, iteration: int, config: dict) -> dict:
    ledger = load_ledger(ledger_path)
    sf = _load_sage_flags()
    decision = sf.decide({}, iteration, [],
                         ledger={"findings": ledger["findings"],
                                 "history": ledger["history"],
                                 "config": config})
    action = decision["action"]

    # RR-7 — a STOP is a decision about every remaining open entry, not an
    # exhaustion. Refuse to record it until each one has a disposition.
    # (ESCALATE records first — it is the request FOR the human's decision.)
    if action in ("STOP_ADVISORY", "STOP_CAP") and decision["dispositions_required"]:
        raise Problem(
            f"{action} needs a disposition (defer/reject/fix-now) for: "
            + ", ".join(decision["dispositions_required"])
            + " — run `review.py disposition` per entry, then close-round again")

    ledger["history"].append({"iteration": iteration,
                              "counts": decision["counts"],
                              "result": action})

    # Seal the round: pending defer/reject settlements become status now
    # that the verdict they were counted under is on the record.
    if action != "CONTINUE":
        for entry in open_entries(ledger):
            d = entry.get("disposition")
            if isinstance(d, dict) and d.get("action") == "defer":
                entry["status"] = "deferred"
            elif isinstance(d, dict) and d.get("action") == "reject":
                entry["status"] = "rejected"

    save_ledger(ledger_path, ledger)
    if action != "CONTINUE":
        _write_exit_record(ledger_path, ledger, iteration, decision)
    return decision


def _dispositions_summary(ledger: dict) -> str:
    parts = []
    for entry in ledger["findings"]:
        d = entry.get("disposition")
        if not d:
            continue
        label = d if isinstance(d, str) else d.get("action", "?")
        parts.append(f"{entry['id']}:{label}")
    return ",".join(parts) or "none"


def _write_exit_record(ledger_path: pathlib.Path, ledger: dict,
                       iteration: int, decision: dict) -> None:
    """One decisions.md line per exit, written by the tool itself — the
    degradation-log rule: the record is taken, not requested."""
    counts = decision["counts"]
    line = ("- [%s] review-loop %s: %s iter=%d open=%d/%d/%d/%d "
            "dispositions=%s [auto-logged by review.py]\n") % (
        datetime.date.today().isoformat(), decision["action"],
        ledger.get("slug", slug_of(ledger_path)), iteration,
        counts["critical"], counts["major"], counts["substantive"],
        counts["cosmetic"], _dispositions_summary(ledger))
    decisions = ledger_path.resolve().parent / "decisions.md"
    try:
        with open(decisions, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        # The verdict stands even if the log write fails; say so loudly.
        print(f"✗ could not write exit record to {decisions}: {exc}",
              file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════
# report — render the ledger for a human (RR-7 ESCALATE path)
# ═══════════════════════════════════════════════════════════════════════

def report(ledger_path: pathlib.Path) -> str:
    ledger = load_ledger(ledger_path)
    lines = ["review ledger — %s" % ledger.get("slug", slug_of(ledger_path)),
             ""]
    if not ledger["findings"]:
        lines.append("no findings recorded")
    for e in ledger["findings"]:
        cap = ("" if e["severity"] == e.get("severity_as_reported", e["severity"])
               else " (reported %s, capped: no citation, no witness)"
               % e["severity_as_reported"])
        w = e.get("witness") or {}
        d = e.get("disposition")
        lines.append("%s  %-11s %-10s %s%s" % (
            e["id"], e["severity"], e["status"], e["claim"], cap))
        lines.append("       anchor %s:%s-%s  witness %s%s%s" % (
            e["anchor"]["file"], e["anchor"]["region"][0],
            e["anchor"]["region"][1], w.get("kind", "none"),
            " (%s)" % w["ref"] if w.get("ref") else "",
            "  disposition %s" % (d if isinstance(d, str)
                                  else d.get("action")) if d else ""))
    if ledger["history"]:
        lines.append("")
        lines.append("rounds: " + " → ".join(
            "%d:%s" % (h["iteration"], h["result"]) for h in ledger["history"]))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def _read_payload(args, file_attr: str, json_attr: str, what: str) -> list:
    file_val = getattr(args, file_attr)
    json_val = getattr(args, json_attr)
    if bool(file_val) == bool(json_val):
        raise Problem(f"exactly one of --{what}-file / --{what}-json is required")
    text = (pathlib.Path(file_val).read_text(encoding="utf-8")
            if file_val else json_val)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Problem(f"invalid {what} JSON: {exc}")
    if isinstance(data, dict):
        data = data.get("findings" if what == "findings" else "results", data)
    if not isinstance(data, list):
        raise Problem(f"{what} JSON must be an array of objects")
    return data


def _resolve_config(args, ledger_path: pathlib.Path) -> dict:
    if getattr(args, "config", None):
        return load_config(args.config)
    root = repo_root_of(ledger_path)
    return load_config(root / ".sage" / "config.yaml")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="review",
        description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, help_text):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("ledger", type=pathlib.Path)
        return cmd

    i = add("intake", "record reviewer findings, normalized mechanically")
    i.add_argument("--iteration", type=int, required=True)
    i.add_argument("--findings-file")
    i.add_argument("--findings-json")
    i.add_argument("--artifact", default="code", choices=ARTIFACTS)
    i.add_argument("--repo-root", type=pathlib.Path, default=None)
    i.add_argument("--config", default=None)

    v = add("verify", "record Phase-A verification verdicts with evidence")
    v.add_argument("--iteration", type=int, required=True)
    v.add_argument("--results-file")
    v.add_argument("--results-json")
    v.add_argument("--cannot-reproduce", metavar="F-ID")
    v.add_argument("--evidence")

    w = add("attach-witness", "attach the materialized witness test to a finding")
    w.add_argument("finding_id")
    w.add_argument("--ref", required=True)
    w.add_argument("--kind", default="test", choices=[k for k in WITNESS_KINDS
                                                      if k != "none"])
    w.add_argument("--status", default="red", choices=list(WITNESS_STATUSES))

    d = add("disposition", "defer / reject / fix-now a remaining open entry")
    d.add_argument("finding_id")
    d.add_argument("--action", required=True, choices=list(DISPOSITIONS))
    d.add_argument("--reason")
    d.add_argument("--ticket")

    c = add("close-round", "compute the round verdict from ledger facts")
    c.add_argument("--iteration", type=int, required=True)
    c.add_argument("--config", default=None)

    add("report", "render the ledger for a human")

    args = p.parse_args(argv)

    try:
        if args.cmd == "intake":
            config = _resolve_config(args, args.ledger)
            root = args.repo_root or repo_root_of(args.ledger)
            findings = _read_payload(args, "findings_file", "findings_json",
                                     "findings")
            rep = intake(args.ledger, findings, args.iteration, args.artifact,
                         root, config)
            print(json.dumps(rep))
        elif args.cmd == "verify":
            if args.cannot_reproduce:
                cannot_reproduce(args.ledger, args.cannot_reproduce,
                                 args.evidence, args.iteration)
                print(json.dumps({"disputed": [args.cannot_reproduce]}))
            else:
                results = _read_payload(args, "results_file", "results_json",
                                        "results")
                touched = verify(args.ledger, results, args.iteration)
                print(json.dumps({"verified": touched}))
        elif args.cmd == "attach-witness":
            attach_witness(args.ledger, args.finding_id, args.ref,
                           args.kind, args.status)
            print(f"✓ {args.finding_id} witness → {args.ref} ({args.status})")
        elif args.cmd == "disposition":
            disposition(args.ledger, args.finding_id, args.action,
                        args.reason, args.ticket)
            print(f"✓ {args.finding_id} → {args.action}")
        elif args.cmd == "close-round":
            config = _resolve_config(args, args.ledger)
            print(json.dumps(close_round(args.ledger, args.iteration, config)))
        elif args.cmd == "report":
            print(report(args.ledger))
    except (Problem, OSError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
