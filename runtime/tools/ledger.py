#!/usr/bin/env python3
"""ledger.py — scaffold the subagent task ledger from the approved plan.

WHY THIS EXISTS, AND WHY IT IS A SCRIPT AND NOT A PARAGRAPH

E9 measured subagent execution end-to-end and found this:

    E10 (ledger SEEDED in the fixture)     3/3 — flawless
    E9  (orchestrator must CREATE it)      1/3 — no ledger at all in 2 runs

The mode works. What does not work is *remembering to write the ledger*. The
sub-workflow tells the orchestrator to create one, in prose, at some length. Two
runs in three, it didn't — and the runs that didn't looked, from the outside,
exactly like a cycle that had done its work.

That is Sage's own thesis landing on Sage's newest feature. The ledger is the
ENTIRE evidence base for ADR-10's claim that every task was independently
reviewed — and it was being produced by the model's goodwill. The spec-gate's
H41 guard does not save it either: H41 blocks `gates-passed` on a subagent cycle
with no ledger, but an orchestrator that never reaches for gates-passed never
trips it.

So: the ledger is generated from the approved plan, deterministically, at
build-loop entry. Not remembered. Generated.

    "If a rule matters, make it code. If you can't, don't claim it."
    — README, written about a different rule, one release earlier.

Usage:
    ledger.py init  <manifest.md> <plan.md>   # write the tasks: block
    ledger.py check <manifest.md>             # exit 1 if a subagent cycle has none

Python 3.8+, stdlib only.
"""

import argparse
import pathlib
import re
import sys

TASK_RE = re.compile(r"^##\s*Task\s+(\d+)\s*[—:-]\s*(.+?)\s*$", re.M)


def parse_plan_tasks(plan_text):
    """Every `## Task N — title` in the approved plan, in order.

    The plan is the contract the ledger must mirror. If the plan has three tasks
    and the ledger has two, the cycle is claiming a review of work it never
    listed — which is the failure the ledger exists to make impossible.
    """
    return [(int(n), title.strip()) for n, title in TASK_RE.findall(plan_text)]


def split_frontmatter(text):
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?(.*)$", text.lstrip("﻿"), re.S)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def render_ledger(tasks):
    lines = ["tasks:"]
    for n, title in tasks:
        lines += [
            "  - id: %d" % n,
            "    title: %s" % title.replace('"', "'"),
            "    status: pending",
            "    attempts: 0",
            "    review: pending",
            '    commits: ""',
        ]
    return "\n".join(lines)


def init(manifest_path, plan_path):
    manifest = pathlib.Path(manifest_path)
    plan = pathlib.Path(plan_path)

    if not manifest.is_file():
        print("✗ no manifest at %s" % manifest, file=sys.stderr)
        return 1
    if not plan.is_file():
        print("✗ no plan at %s — the ledger mirrors the approved plan, so there "
              "must be one" % plan, file=sys.stderr)
        return 1

    tasks = parse_plan_tasks(plan.read_text(encoding="utf-8"))
    if not tasks:
        print("✗ no `## Task N — title` headings found in %s.\n"
              "   The ledger is generated from the plan's tasks; a plan with no "
              "parseable tasks cannot produce one." % plan, file=sys.stderr)
        return 1

    text = manifest.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        print("✗ %s has no frontmatter" % manifest, file=sys.stderr)
        return 1

    if re.search(r"^\s*tasks\s*:", fm, re.M):
        print("• ledger already present in %s — left alone (re-running init must "
              "never clobber in-flight task state)" % manifest.name)
        return 0

    # execution_mode is what arms the H41 guard. Set it here so the two can never
    # disagree: a cycle with a ledger but no mode, or a mode but no ledger, is a
    # cycle whose enforcement is half-installed.
    if re.search(r"^\s*execution_mode\s*:", fm, re.M):
        fm = re.sub(r"^\s*execution_mode\s*:.*$", "execution_mode: subagent",
                    fm, count=1, flags=re.M)
    else:
        fm = fm.rstrip() + "\nexecution_mode: subagent"

    fm = fm.rstrip() + "\n" + render_ledger(tasks)
    manifest.write_text("---\n%s\n---\n%s" % (fm, body), encoding="utf-8")

    print("✓ ledger scaffolded from %s — %d task(s), all pending:"
          % (plan.name, len(tasks)))
    for n, title in tasks:
        print("    %d. %s" % (n, title))
    print("  execution_mode: subagent (the H41 guard is now armed: this cycle")
    print("  cannot reach gates-passed until every task is done AND approved)")
    return 0


def check(manifest_path):
    """A subagent cycle with no ledger fails. Inline cycles are untouched."""
    manifest = pathlib.Path(manifest_path)
    if not manifest.is_file():
        print("✗ no manifest at %s" % manifest, file=sys.stderr)
        return 1

    fm, _ = split_frontmatter(manifest.read_text(encoding="utf-8"))
    if fm is None:
        return 0

    mode = re.search(r"^\s*execution_mode\s*:\s*\"?([A-Za-z0-9_-]+)", fm, re.M)
    mode = mode.group(1).lower() if mode else "inline"

    if mode != "subagent":
        print("OK — execution_mode: %s (no ledger required)" % mode)
        return 0

    if not re.search(r"^\s*tasks\s*:", fm, re.M):
        print("✗ FAIL — this cycle is in subagent execution and has NO task "
              "ledger.\n"
              "   The ledger is the only evidence that any task was independently\n"
              "   reviewed. Run:  ledger.py init <manifest> <plan>",
              file=sys.stderr)
        return 1

    print("OK — subagent cycle carries a ledger")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="scaffold the ledger from the approved plan")
    i.add_argument("manifest")
    i.add_argument("plan")

    c = sub.add_parser("check", help="a subagent cycle must carry a ledger")
    c.add_argument("manifest")

    args = ap.parse_args()
    if args.cmd == "init":
        return init(args.manifest, args.plan)
    return check(args.manifest)


if __name__ == "__main__":
    sys.exit(main())
