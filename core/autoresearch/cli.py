"""CLI entry point for autoresearch runtime."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .brief import parse_brief
from .loop import run_session


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sage-autoresearch",
        description="Autonomous iteration toward measurable outcomes.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run an autoresearch session")
    run_parser.add_argument("--brief", required=True, help="Path to brief.md")
    run_parser.add_argument("--project", default=".", help="Project root directory")

    sub.add_parser("help", help="Show help")

    args = parser.parse_args(argv)

    if args.command is None or args.command == "help":
        parser.print_help()
        return 0

    if args.command == "run":
        brief_path = Path(args.brief).resolve()
        project_dir = Path(args.project).resolve()

        if not brief_path.exists():
            print(f"❌ Brief not found: {brief_path}", file=sys.stderr)
            return 1

        try:
            brief = parse_brief(brief_path)
        except Exception as e:
            print(f"❌ Failed to parse brief: {e}", file=sys.stderr)
            return 1

        if not brief.verify:
            print("❌ No verify command in brief.", file=sys.stderr)
            return 1

        work_dir = brief_path.parent
        print(f"🔬 Sage Autoresearch v{__version__}")
        print(f"   Goal: {brief.goal}")
        print(f"   Metric: {brief.metric.name} ({brief.metric.direction.value})")
        if brief.metric.target is not None:
            print(f"   Target: {brief.metric.target}")
        print(f"   Verify: {brief.verify}")
        print(f"   Branch: {brief.branch_name}")
        print()

        run_session(brief, work_dir, project_dir)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
