#!/usr/bin/env python3
"""
context_budget.py — what Sage actually costs a model, in lines and tokens.

Sage's pitch is that process arrives without drowning the context window. The
README said "~200 lines". Nobody had measured it. It is 398 — the claim was off
by a factor of two, and it drifted there one honest paragraph at a time, because
nothing counted.

Context growth is the definitive slow leak: every individual addition is
justified, no single commit looks careless, and the total is never anyone's job.
So this makes it someone's job — a number, in CI, that cannot rise by accident.

Two layers get measured, because they are paid at different times:

  EAGER    the generated instructions file (CLAUDE.md / AGENTS.md). Loaded on
           every single turn of every session. The expensive one.
  COMMAND  each generated slash command (.claude/commands/*.md). Paid only when
           that command runs — but paid in full, since the generator inlines the
           workflow rather than pointing at it.

Measured against a real generated project (`sage init --preset base` into a temp
dir), not against the source templates, because what the model reads is the
OUTPUT — and the two are not the same file.

Tokens are estimated at chars/4. That is a heuristic, stated rather than hidden;
it is stable enough to compare releases against each other, which is the whole
job here. Do not quote it as an exact figure.

Usage:
  context_budget.py --report            markdown table to stdout
  context_budget.py --check             compare against develop/validators/budgets.yaml
  context_budget.py --report --out FILE write the report to a file

Exit: 0 = within budget | 1 = over budget (or a measurement failed) | 2 = bad invocation

Python 3.8+, stdlib only — which is why budgets.yaml is parsed by the flat reader
below rather than by PyYAML. The file is deliberately a flat map of name → int;
if it ever needs to be more than that, the budget has stopped being a budget.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SAGE_BIN = REPO_ROOT / "bin" / "sage"
BUDGETS = REPO_ROOT / "develop" / "validators" / "budgets.yaml"

CHARS_PER_TOKEN = 4      # documented heuristic; see the module docstring


class BudgetError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
def read_budgets(path: pathlib.Path) -> dict:
    """A flat `section:` / `  name: int` reader. No YAML library, by constraint.

    Anything it cannot understand is an error rather than a skip: a budget file
    that silently drops a line is a budget that silently stops enforcing.
    """
    if not path.is_file():
        raise BudgetError(f"budget file not found: {path}")

    budgets: dict = {}
    section = None
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line[0].isspace():
            if not line.endswith(":"):
                raise BudgetError(f"{path.name}:{lineno}: expected `section:` — {raw.strip()!r}")
            section = line[:-1].strip()
            budgets[section] = {}
            continue
        if section is None:
            raise BudgetError(f"{path.name}:{lineno}: entry before any section")
        key, _, value = line.strip().partition(":")
        try:
            budgets[section][key.strip()] = int(value.strip())
        except ValueError:
            raise BudgetError(f"{path.name}:{lineno}: not an integer — {raw.strip()!r}")
    return budgets


def generate_project(dest: pathlib.Path) -> pathlib.Path:
    """`sage init` into a throwaway project. What we measure is what a user gets."""
    home = dest / "home"
    home.mkdir(parents=True)
    shutil.copytree(REPO_ROOT, home / "framework",
                    ignore=shutil.ignore_patterns(".git", "node_modules",
                                                  "__pycache__", "dist", ".sage"))
    proj = dest / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)

    proc = subprocess.run(
        ["bash", str(SAGE_BIN), "init", "--preset", "base"],
        cwd=proj, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        env={**os.environ, "SAGE_HOME": str(home)},
    )
    if proc.returncode != 0:
        raise BudgetError(f"sage init failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
    return proj


def measure(path: pathlib.Path) -> dict:
    text = path.read_text(errors="replace")
    return {
        "lines": len(text.splitlines()),
        "tokens": len(text) // CHARS_PER_TOKEN,
        "bytes": len(text.encode("utf-8")),
    }


def collect(proj: pathlib.Path) -> dict:
    """{'eager': {name: measurement}, 'commands': {name: measurement}}"""
    out = {"eager": {}, "commands": {}}

    for name in ("CLAUDE.md", "AGENTS.md"):
        f = proj / name
        if f.is_file():
            out["eager"][name] = measure(f)

    cmd_dir = proj / ".claude" / "commands"
    if cmd_dir.is_dir():
        for f in sorted(cmd_dir.glob("*.md")):
            out["commands"][f.stem] = measure(f)

    if not out["eager"]:
        raise BudgetError("no instructions file was generated — nothing to measure")
    return out


# ─────────────────────────────────────────────────────────────────────────────
def report(data: dict, budgets: dict) -> str:
    lines = [
        "# Context budget",
        "",
        "What Sage costs a model, measured against a real `sage init --preset base`",
        "project rather than against the source templates — the model reads the",
        "generated output, and the two are not the same file.",
        "",
        f"Tokens are estimated at chars/{CHARS_PER_TOKEN}. That is a heuristic, useful for",
        "comparing releases to each other, not for quoting as an exact figure.",
        "",
        "## Eager layer",
        "",
        "Loaded on every turn of every session. This is the one that matters.",
        "",
        "| File | Lines | ~Tokens | Budget | |",
        "|---|---:|---:|---:|---|",
    ]
    for name, m in sorted(data["eager"].items()):
        cap = budgets.get("eager", {}).get(name)
        mark = "" if cap is None else ("✅" if m["lines"] <= cap else "❌ OVER")
        lines.append(f"| `{name}` | {m['lines']} | {m['tokens']:,} | "
                     f"{cap if cap is not None else '—'} | {mark} |")

    lines += [
        "",
        "## Per-command layer",
        "",
        "Paid only when the command runs — but paid in full: the generator inlines",
        "each workflow rather than pointing at it.",
        "",
        "| Command | Lines | ~Tokens | Budget | |",
        "|---|---:|---:|---:|---|",
    ]
    for name, m in sorted(data["commands"].items(), key=lambda kv: -kv[1]["lines"]):
        cap = budgets.get("commands", {}).get(name)
        mark = "" if cap is None else ("✅" if m["lines"] <= cap else "❌ OVER")
        lines.append(f"| `/{name}` | {m['lines']} | {m['tokens']:,} | "
                     f"{cap if cap is not None else '—'} | {mark} |")

    eager_lines = sum(m["lines"] for m in data["eager"].values())
    worst = max(data["commands"].items(), key=lambda kv: kv[1]["lines"], default=None)
    lines += [
        "",
        "## Totals",
        "",
        f"- Eager: **{eager_lines} lines** "
        f"(~{sum(m['tokens'] for m in data['eager'].values()):,} tokens) on every turn.",
    ]
    if worst:
        lines.append(
            f"- Heaviest command: **/{worst[0]} at {worst[1]['lines']} lines** "
            f"(~{worst[1]['tokens']:,} tokens), on top of the eager layer."
        )
    lines.append("")
    return "\n".join(lines)


def check(data: dict, budgets: dict) -> int:
    over = []
    unbudgeted = []
    for section in ("eager", "commands"):
        caps = budgets.get(section, {})
        for name, m in data[section].items():
            if name not in caps:
                unbudgeted.append(f"{section}/{name}")
                continue
            if m["lines"] > caps[name]:
                over.append(f"  {section}/{name}: {m['lines']} lines > budget {caps[name]} "
                            f"(+{m['lines'] - caps[name]})")

    if over:
        print("✗ over context budget:")
        for line in over:
            print(line)
        print()
        print("FAIL — the eager layer is paid on every turn of every session, so this")
        print("  is not free. Either trim it, or raise the number in")
        print(f"  {BUDGETS.relative_to(REPO_ROOT)} in this same change — deliberately,")
        print("  where a reviewer can see it. That is the entire point of the file.")
        return 1

    if unbudgeted:
        # A new command with no budget would otherwise grow forever, unwatched.
        print("✗ generated files with no budget entry:")
        for name in unbudgeted:
            print(f"  {name}")
        print()
        print(f"FAIL — add each to {BUDGETS.relative_to(REPO_ROOT)}.")
        return 1

    total = len(data["eager"]) + len(data["commands"])
    eager_lines = sum(m["lines"] for m in data["eager"].values())
    print(f"OK — {total} generated file(s) within budget "
          f"(eager: {eager_lines} lines on every turn).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Measure Sage's context cost.")
    p.add_argument("--report", action="store_true", help="print a markdown report")
    p.add_argument("--check", action="store_true",
                   help="fail if any generated file exceeds its budget")
    p.add_argument("--out", type=pathlib.Path, default=None,
                   help="write the report here instead of stdout")
    p.add_argument("--budgets", type=pathlib.Path, default=BUDGETS)
    args = p.parse_args()

    if not args.report and not args.check:
        p.error("choose --report and/or --check")

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sage-budget-"))
    try:
        data = collect(generate_project(tmp))
        budgets = read_budgets(args.budgets)
    except BudgetError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if args.report:
        text = report(data, budgets)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(f"OK — report written to {args.out}")
        else:
            print(text)

    if args.check:
        return check(data, budgets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
