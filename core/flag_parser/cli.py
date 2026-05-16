"""CLI entry point for the flag parser.

Usage:
    python -m core.flag_parser parse "<args>" [--config-path PATH]

Outputs JSON to stdout. Exit code 0 on success (parsed cleanly or
empty input). Exit code 1 on unknown flag or conflicting flags (error
field populated; JSON still printed).
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .config_loader import load_defaults
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
    parse_cmd.add_argument("--config-path", default=None,
                           help="Path to .sage/config.yaml to load defaults from")

    sub.add_parser("help", help="Show help")

    args = p.parse_args(argv)

    if args.command == "parse":
        defaults = load_defaults(args.config_path)
        result = parse(args.arguments, defaults=defaults)
        print(json.dumps(result.to_dict()))
        return 1 if result.error else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
