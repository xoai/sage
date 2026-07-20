#!/usr/bin/env python3
"""
sage_flags.py — workflow flag parsing + quality-locked loop decisions.

Consolidates the former core/flag_parser/ and core/quality_locked/ packages
(ADR-8) into one stdlib script so core/ carries no Python. Behavior is
preserved byte-for-byte; the test suite ports both packages' cases.

Subcommands (JSON to stdout):

  parse "<arguments>" [--config-path PATH]
      Parse workflow flags from $ARGUMENTS. Recognized (bare switches):
      --quality-locked / --no-quality-locked, --autonomous / --no-autonomous.
      Precedence: --no-X (off) > --X (on) > config default > off.
      Exit 1 on an unknown flag or a --X/--no-X conflict.

  check --review-output TEXT --iteration N [--history-json JSON]
      Classify review findings and decide the next quality-locked action
      (PASS / REVISE / CAP_REACHED / ESCALATE).

  classify --review-output TEXT
      Classify review findings into {critical, major, substantive, cosmetic}.

decide() also carries the review-loop v2 controller: called with a ledger
(see runtime/tools/review.py) it computes CONTINUE / ESCALATE / STOP_CAP /
STOP_ADVISORY / STOP_CLEAN from ledger facts instead of classified prose.
Without a ledger it is byte-identical to the v1 behavior above.

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# Flag parsing
# ═══════════════════════════════════════════════════════════════════════

# The flag vocabulary, in ONE place.
#
# It used to be enumerated by hand in five: two frozensets, a lookup table, a
# regex alternation, an initial-state dict, and the result dict. Adding
# `--subagents` meant finding all five, and missing one would have failed
# silently — the flag would parse and then simply not take effect. Derive them.
FLAG_KEYS = ("quality_locked", "autonomous", "subagents")

POSITIVE_FLAGS = {"--" + k.replace("_", "-") for k in FLAG_KEYS}
NEGATIVE_FLAGS = {"--no-" + k.replace("_", "-") for k in FLAG_KEYS}
FLAG_TO_KEY = {}
for _k in FLAG_KEYS:
    _dash = _k.replace("_", "-")
    FLAG_TO_KEY["--" + _dash] = _k
    FLAG_TO_KEY["--no-" + _dash] = _k
ALL_FLAGS = POSITIVE_FLAGS | NEGATIVE_FLAGS

# Config default: only the canonical `<key>: true` (one space, lowercase, no
# trailing content) is honored, so Bash and Python agree byte-for-byte. This
# rejects True/TRUE, "true", yes, no-space, extra-space, trailing comments, and
# indented keys — all treated as no default.
_TRUE_LINE_RE = re.compile(
    r"^(%s): true$" % "|".join(FLAG_KEYS), re.MULTILINE)


def load_defaults(config_path):
    """Top-level boolean flag defaults from a Sage config.yaml. Fail-soft:
    missing/unreadable/malformed config → empty dict, never raises."""
    defaults = {}
    if not config_path:
        return defaults
    path = Path(config_path)
    if not path.is_file():
        return defaults
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return defaults
    for m in _TRUE_LINE_RE.finditer(text):
        defaults[m.group(1)] = True
    return defaults


def parse_flags(arguments, defaults=None):
    """Return a result dict matching the former flag_parser contract:
    {quality_locked, autonomous, goal, error, quality_locked_source,
     autonomous_source}."""
    if arguments is None:
        arguments = ""
    defaults = defaults or {}

    def err(message):
        out = {"goal": "", "error": message}
        for k in FLAG_KEYS:
            out[k] = False
            out[k + "_source"] = None
        return out

    flag_state = {k: None for k in FLAG_KEYS}
    remaining = arguments.strip()
    while remaining.startswith("--"):
        parts = remaining.split(None, 1)
        token = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        if token not in ALL_FLAGS:
            supported = ", ".join(sorted(ALL_FLAGS))
            return err(f"Unknown flag '{token}'. Supported flags: {supported}.")
        key = FLAG_TO_KEY[token]
        new_state = "positive" if token in POSITIVE_FLAGS else "negative"
        if flag_state[key] is not None and flag_state[key] != new_state:
            dash = key.replace("_", "-")
            return err(f"Conflicting flags for {key}: both --{dash} and "
                       f"--no-{dash} passed.")
        flag_state[key] = new_state
        remaining = rest.lstrip()

    def resolve(key):
        state = flag_state[key]
        if state == "positive":
            return True, "flag"
        if state == "negative":
            return False, "flag"
        if defaults.get(key) is True:
            return True, "config"
        return False, None

    out = {"goal": remaining, "error": None}
    for k in FLAG_KEYS:
        value, source = resolve(k)
        out[k] = value
        out[k + "_source"] = source
    return out


# ═══════════════════════════════════════════════════════════════════════
# Quality-locked: classify review findings
# ═══════════════════════════════════════════════════════════════════════

# Order matters: hyphenated forms must match before the bare CRITICAL/MAJOR.
HEADER_MAP = [
    (re.compile(r"^MINOR-substantive\s*:", re.IGNORECASE), "substantive"),
    (re.compile(r"^MINOR-cosmetic\s*:", re.IGNORECASE), "cosmetic"),
    (re.compile(r"^SUGGESTION-substantive\s*:", re.IGNORECASE), "substantive"),
    (re.compile(r"^SUGGESTION-cosmetic\s*:", re.IGNORECASE), "cosmetic"),
    (re.compile(r"^CRITICAL\s*:", re.IGNORECASE), "critical"),
    (re.compile(r"^MAJOR\s*:", re.IGNORECASE), "major"),
    (re.compile(r"^WARNING\s*:", re.IGNORECASE), "major"),
]
ZERO_TOKENS = {"none", "[none]", "[]", "0"}


def _match_header(line):
    for pattern, key in HEADER_MAP:
        m = pattern.match(line)
        if m:
            return key, line[m.end():].strip()
    return None


def _is_bullet(line):
    return line.lstrip().startswith(("- ", "* ", "• "))


def classify(review_output):
    """Parse review sub-agent output into a counts dict
    {critical, major, substantive, cosmetic}."""
    counts = {"critical": 0, "major": 0, "substantive": 0, "cosmetic": 0}
    if not review_output:
        return counts

    current_key = None
    items = 0

    def flush():
        nonlocal items, current_key
        if current_key is not None:
            counts[current_key] += items
        items = 0

    for line in review_output.splitlines():
        stripped = line.strip()
        header = _match_header(stripped)
        if header is not None:
            flush()
            current_key, rest = header
            if rest.lower() in ZERO_TOKENS:
                current_key = None
            elif rest:
                if _is_bullet(rest) or rest.startswith("["):
                    inner = rest.strip("[]").strip()
                    if inner and inner.lower() != "none":
                        items += sum(
                            1 for part in re.split(r",\s*-\s*|^-\s*", inner)
                            if part.strip()
                        ) or 1
                elif rest.lower() not in ZERO_TOKENS:
                    items += 1
        elif current_key is not None:
            if _is_bullet(line):
                items += 1
            elif not stripped:
                flush()
                current_key = None
    flush()
    return counts


# ═══════════════════════════════════════════════════════════════════════
# Quality-locked: decide the next action
# ═══════════════════════════════════════════════════════════════════════

ITERATION_CAP = 10
STUCK_THRESHOLD = 3  # consecutive iterations with the same critical+major count

# ── Review-loop v2 controller (RR-5/RR-6) ──────────────────────────────
# When decide() is handed a ledger, counts come from ledger entries, not
# from regex over reviewer prose, and the verdict is computed from the
# decision table below. Without a ledger, v1 behavior is byte-identical.

SEVERITY_WEIGHT = {"critical": 8, "major": 3, "substantive": 1, "cosmetic": 0}
OPEN_STATUSES = ("open", "not-fixed")
V2_DEFAULTS = {"major_budget": 0, "iteration_cap": 5, "escalate_after_stalls": 2}


def _open_counts(findings):
    counts = {"critical": 0, "major": 0, "substantive": 0, "cosmetic": 0}
    for entry in findings:
        if entry.get("status") in OPEN_STATUSES:
            counts[entry["severity"]] += 1
    return counts


def weight(counts):
    """8·critical + 3·major + 1·substantive + 0·cosmetic — open entries
    only, post-capping. Substantive findings register (a stalled loop full
    of them is visible) but never drive CONTINUE."""
    return sum(SEVERITY_WEIGHT[k] * counts.get(k, 0) for k in SEVERITY_WEIGHT)


def _trailing_stalls(history_weights, current_weight):
    """Count the trailing rounds whose weight failed to improve on the
    round before. The field log's 1→2→3 major climb is two trailing
    stalls: escalation fires at round 4, not round 7."""
    seq = list(history_weights) + [current_weight]
    stalls = 0
    for i in range(len(seq) - 1, 0, -1):
        if seq[i] >= seq[i - 1]:
            stalls += 1
        else:
            break
    return stalls


def _is_pending_settlement(entry):
    """A defer/reject disposition recorded but not yet applied by
    close-round. Such an entry is decided — it must not drive another
    round — but it stays visible in the reported counts until the round
    that seals it."""
    d = entry.get("disposition")
    return isinstance(d, dict) and d.get("action") in ("defer", "reject")


def _decide_v2(iteration, ledger):
    """RR-6 decision table. Evaluation order makes every row reachable:
    an explicit fix-now buys its round; a stall or the cap preempts
    CONTINUE (the controller does not spend past either); only then do
    blocking findings drive another round.

    Verdicts: CONTINUE | ESCALATE | STOP_CAP | STOP_ADVISORY | STOP_CLEAN.
    """
    cfg = dict(V2_DEFAULTS)
    for key in V2_DEFAULTS:
        value = (ledger.get("config") or {}).get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            cfg[key] = value
    findings = ledger.get("findings", [])
    open_entries = [f for f in findings if f.get("status") in OPEN_STATUSES]
    blocking = [f for f in open_entries if not _is_pending_settlement(f)]
    counts = _open_counts(findings)
    blocking_counts = _open_counts(blocking)
    current_weight = weight(blocking_counts)
    history = ledger.get("history", [])
    stalls = _trailing_stalls([weight(h.get("counts", {})) for h in history],
                              current_weight)
    fix_now = [f["id"] for f in blocking if f.get("disposition") == "fix-now"]

    if not open_entries:
        action = "STOP_CLEAN"
    elif fix_now:
        action = "CONTINUE"                        # a human bought this round
    elif stalls >= cfg["escalate_after_stalls"]:
        action = "ESCALATE"
    elif iteration >= cfg["iteration_cap"]:
        action = "STOP_CAP"
    elif blocking_counts["critical"] > 0:
        action = "CONTINUE"
    elif blocking_counts["major"] > cfg["major_budget"]:
        action = "CONTINUE"
    else:
        action = "STOP_ADVISORY"                   # substantive/cosmetic only

    return {
        "counts": counts,
        "weight": current_weight,
        "open_ids": [f["id"] for f in open_entries],
        "fix_now": fix_now,
        "dispositions_required": [f["id"] for f in open_entries
                                  if not f.get("disposition")],
        "stalled": stalls >= cfg["escalate_after_stalls"],
        "cap_reached": iteration >= cfg["iteration_cap"],
        "action": action,
    }


def is_clean(counts):
    """Clean bar: zero Critical, zero Major, zero substantive Minor.
    Cosmetic Minors are allowed."""
    return counts["critical"] == 0 and counts["major"] == 0 and counts["substantive"] == 0


def is_stuck(history):
    """True when the last STUCK_THRESHOLD iterations show the same nonzero
    critical+major count — structural, not fixable-by-iteration."""
    if len(history) < STUCK_THRESHOLD:
        return False
    sums = []
    for entry in history[-STUCK_THRESHOLD:]:
        c = entry.get("counts", {})
        sums.append(c.get("critical", 0) + c.get("major", 0))
    return len(set(sums)) == 1 and sums[0] > 0


def decide(counts, iteration, history, ledger=None):
    """v1 (no ledger): precedence PASS > CAP_REACHED > ESCALATE > REVISE,
    counts classified from reviewer prose. Byte-identical to the pre-v2
    behavior for every existing caller.

    v2 (ledger given): the RR-6 table over ledger facts — counts and
    history arguments are ignored; the ledger is the single source of
    truth (`classify()` is retired on this path)."""
    if ledger is not None:
        return _decide_v2(iteration, ledger)
    if is_clean(counts):
        action, cap, stuck = "PASS", False, False
    elif iteration >= ITERATION_CAP:
        action, cap, stuck = "CAP_REACHED", True, is_stuck(history)
    elif is_stuck(history):
        action, cap, stuck = "ESCALATE", False, True
    else:
        action, cap, stuck = "REVISE", False, False
    return {
        "counts": counts,
        "is_clean": is_clean(counts),
        "cap_reached": cap,
        "stuck": stuck,
        "action": action,
    }


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main(argv=None):
    p = argparse.ArgumentParser(
        prog="sage-flags",
        description="Workflow flag parsing and quality-locked loop decisions.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Parse workflow flags from $ARGUMENTS")
    parse_cmd.add_argument("arguments", nargs="?", default="")
    parse_cmd.add_argument("--config-path", default=None)

    check = sub.add_parser("check", help="Classify findings + decide action")
    check.add_argument("--review-output", required=True)
    check.add_argument("--iteration", type=int, required=True)
    check.add_argument("--history-json", default="[]")

    cls = sub.add_parser("classify", help="Classify findings only")
    cls.add_argument("--review-output", required=True)

    args = p.parse_args(argv)

    if args.command == "parse":
        result = parse_flags(args.arguments, load_defaults(args.config_path))
        print(json.dumps(result))
        return 1 if result["error"] else 0

    if args.command == "check":
        counts = classify(args.review_output)
        try:
            history = json.loads(args.history_json)
            if not isinstance(history, list):
                raise ValueError("history must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            print(json.dumps({"error": f"Invalid --history-json: {e}"}))
            return 1
        decision = decide(counts, args.iteration, history)
        decision["iteration_record"] = {
            "iteration": args.iteration,
            "counts": counts,
            "result": decision["action"],
        }
        print(json.dumps(decision))
        return 0

    if args.command == "classify":
        print(json.dumps({"counts": classify(args.review_output)}))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())


# ═══════════════════════════════════════════════════════════════════════
# Subagent execution: availability (ADR-10 R97, ADR-11)
# ═══════════════════════════════════════════════════════════════════════
#
# Subagent mode is the one flag whose request can be REFUSED by the platform.
# --quality-locked and --autonomous are policies: if you ask for them, you get
# them. --subagents is a capability: asking for it on a platform with no
# subagent dispatch is asking for something that does not exist.
#
# The rule from ADR-10 is that unavailability is LOUD. It is announced, it is
# written to decisions.md by the existing degradation machinery, and the manifest
# records `execution_mode: inline (subagents-unavailable)`. What it must never do
# is silently fall back — a user who asked for per-task review and got a single
# inline context, with no indication, has been told a lie by omission, and the
# whole point of the v1.2.x work was that degradation is legible or it is nothing.

SUBAGENT_CAPABILITY = "subagent-dispatch"


def platform_supports_subagents(contract):
    """True iff the platform's capability contract grants subagent dispatch.

    `contract` is the parsed platform.yaml (schema v2, ADR-11). An `attested`
    value counts as true — the attestation carries its own evidence and expiry,
    which is Phase 4's problem, not this function's.

    A platform with NO contract at all is treated as NOT supporting subagents.
    That is deliberate: the safe default for an unknown platform is the degraded
    path, which is loud, rather than the enhanced path, which would dispatch into
    a void and fail in a way nobody planned for.
    """
    if not contract:
        return False
    caps = contract.get("capabilities") or {}
    value = caps.get(SUBAGENT_CAPABILITY)
    return value is True or value == "attested"


def resolve_execution_mode(requested_subagents, contract):
    """Reconcile what was asked for with what the platform can actually do.

    Returns {mode, degraded, manifest_value, announcement}:

      mode           "subagent" | "inline"
      degraded       True only when subagents were REQUESTED and REFUSED
      manifest_value the string the cycle manifest records for execution_mode
      announcement   what to say out loud, or None when there is nothing to say
    """
    if not requested_subagents:
        return {
            "mode": "inline",
            "degraded": False,
            "manifest_value": "inline",
            "announcement": None,        # the default. Not news.
        }

    if platform_supports_subagents(contract):
        return {
            "mode": "subagent",
            "degraded": False,
            "manifest_value": "subagent",
            "announcement": None,
        }

    name = (contract or {}).get("name", "this platform")
    return {
        "mode": "inline",
        "degraded": True,
        "manifest_value": "inline (subagents-unavailable)",
        "announcement": (
            "Subagent execution is unavailable: %s does not provide "
            "`%s`. Falling back to the inline build loop — implementation and "
            "review will share one context, so per-task review is NOT "
            "independent. Recorded in decisions.md."
            % (name, SUBAGENT_CAPABILITY)
        ),
    }
