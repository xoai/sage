"""CLI entry point for the quality-locked decision module.

Usage:
    python -m core.quality_locked check \\
        --review-output "<text>" \\
        --iteration 3 \\
        --history-json '[]'

Outputs JSON to stdout. Exit code 0 on success.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .classifier import classify
from .decision import decide


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sage-quality-locked",
        description="Classify review findings and decide next action.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Classify findings + decide action")
    check.add_argument("--review-output", required=True,
                       help="Raw text output from the review sub-agent")
    check.add_argument("--iteration", type=int, required=True,
                       help="Current iteration number (1-indexed)")
    check.add_argument("--history-json", default="[]",
                       help="JSON array of prior iteration records (default: [])")

    # Sub-command for just classifying (no decision)
    cls_cmd = sub.add_parser("classify", help="Classify findings only")
    cls_cmd.add_argument("--review-output", required=True)

    args = p.parse_args(argv)

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

        # Build the iteration record the agent should append to history
        iteration_record = {
            "iteration": args.iteration,
            "counts": counts.to_dict(),
            "result": decision.action.value,
        }

        output = decision.to_dict()
        output["iteration_record"] = iteration_record
        print(json.dumps(output))
        return 0

    if args.command == "classify":
        counts = classify(args.review_output)
        print(json.dumps({"counts": counts.to_dict()}))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
