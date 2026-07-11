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

POSITIVE_FLAGS = {"--quality-locked", "--autonomous"}
NEGATIVE_FLAGS = {"--no-quality-locked", "--no-autonomous"}
FLAG_TO_KEY = {
    "--quality-locked": "quality_locked",
    "--no-quality-locked": "quality_locked",
    "--autonomous": "autonomous",
    "--no-autonomous": "autonomous",
}
ALL_FLAGS = POSITIVE_FLAGS | NEGATIVE_FLAGS

# Config default: only the canonical `<key>: true` (one space, lowercase, no
# trailing content) is honored, so Bash and Python agree byte-for-byte. This
# rejects True/TRUE, "true", yes, no-space, extra-space, trailing comments, and
# indented keys — all treated as no default.
_TRUE_LINE_RE = re.compile(r"^(quality_locked|autonomous): true$", re.MULTILINE)


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
        return {
            "quality_locked": False, "autonomous": False, "goal": "",
            "error": message,
            "quality_locked_source": None, "autonomous_source": None,
        }

    flag_state = {"quality_locked": None, "autonomous": None}
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

    ql_value, ql_source = resolve("quality_locked")
    auto_value, auto_source = resolve("autonomous")
    return {
        "quality_locked": ql_value, "autonomous": auto_value,
        "goal": remaining, "error": None,
        "quality_locked_source": ql_source, "autonomous_source": auto_source,
    }


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


def decide(counts, iteration, history):
    """Decision precedence: PASS > CAP_REACHED > ESCALATE > REVISE."""
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
