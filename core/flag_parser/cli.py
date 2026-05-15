"""CLI entry point for the flag parser.

Usage:
    python -m core.flag_parser parse "<args>"

Outputs JSON to stdout. Exit code 0 on success (parsed cleanly or
empty input). Exit code 1 on unknown flag (error field is populated
but still printed for the agent to surface).
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .parser import parse


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sage-flag-parser",
        description="Parse Sage workflow flags from $ARGUMENTS.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command", required=True)
    parse_cmd = sub.add_parser("parse", help="Parse arguments string")
    parse_cmd.add_argument("arguments", nargs="?", default="",
                           help="The $ARGUMENTS string to parse")

    args = p.parse_args(argv)

    if args.command == "parse":
        result = parse(args.arguments)
        print(json.dumps(result.to_dict()))
        # Non-zero exit when an unknown flag was found, so the caller
        # can branch on exit code alone if they prefer.
        return 1 if result.error else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
