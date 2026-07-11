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


def make_home(dest: pathlib.Path) -> pathlib.Path:
    """Vendor the framework once, then init as many platforms as we like from it."""
    home = dest / "home"
    home.mkdir(parents=True)
    shutil.copytree(REPO_ROOT, home / "framework",
                    ignore=shutil.ignore_patterns(".git", "node_modules",
                                                  "__pycache__", "dist", ".sage"))
    return home


def generate_project(home: pathlib.Path, dest: pathlib.Path,
                     platform: str = "claude-code") -> pathlib.Path:
    """`sage init` into a throwaway project. What we measure is what a user gets."""
    proj = dest / f"proj-{platform}"
    proj.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)

    proc = subprocess.run(
        ["bash", str(SAGE_BIN), "init", "--preset", "base", "--platform", platform],
        cwd=proj, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        env={**os.environ, "SAGE_HOME": str(home)},
    )
    if proc.returncode != 0:
        raise BudgetError(f"sage init --platform {platform} failed:\n"
                          f"{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
    return proj


def measure(path: pathlib.Path) -> dict:
    text = path.read_text(errors="replace")
    return {
        "lines": len(text.splitlines()),
        "tokens": len(text) // CHARS_PER_TOKEN,
        "bytes": len(text.encode("utf-8")),
    }


def collect(proj: pathlib.Path) -> dict:
    """{'eager': {...}, 'commands': {...}, 'skills': {...}}"""
    out = {"eager": {}, "commands": {}, "skills": {}}

    for name in ("CLAUDE.md", "AGENTS.md"):
        f = proj / name
        if f.is_file():
            out["eager"][name] = measure(f)

    cmd_dir = proj / ".claude" / "commands"
    if cmd_dir.is_dir():
        for f in sorted(cmd_dir.glob("*.md")):
            out["commands"][f.stem] = measure(f)

    # System skills — the content ADR-9 moved OUT of the eager layer.
    #
    # These are measured for one reason: so the diet cannot be won by cheating.
    # Moving 250 lines from a file that is paid every turn into a file that is
    # paid on demand is a real improvement, but ONLY if someone is counting both
    # numbers. Otherwise "we cut the eager layer by 70%" is a sentence that stays
    # true while the total cost quietly goes up, and nobody notices because the
    # only instrument was pointed at the half that improved.
    skills_dir = proj / ".claude" / "skills"
    if skills_dir.is_dir():
        for f in sorted(skills_dir.glob("*/SKILL.md")):
            head = f.read_text(errors="replace")[:400]
            if "type: system" in head:
                out["skills"][f.parent.name] = measure(f)

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

    if data.get("skills"):
        lines += [
            "",
            "## On-demand layer (system skills)",
            "",
            "Content ADR-9 moved out of the eager layer. Fetched only when the",
            "platform's description-triggered discovery matches — so the TOTAL below is",
            "not a per-turn cost, and a session that never asks about tiers never pays",
            "for `sage-tiers`.",
            "",
            "It is measured anyway, because the diet is only real if someone counts both",
            "halves. Relocating cost from a file paid every turn to a file paid on demand",
            "is a genuine win; relocating it into a file nobody measures is an accounting",
            "trick that reads exactly the same in a release note.",
            "",
            "| Skill | Lines | ~Tokens | Budget | |",
            "|---|---:|---:|---:|---|",
        ]
        for name, m in sorted(data["skills"].items(), key=lambda kv: -kv[1]["lines"]):
            cap = budgets.get("skills", {}).get(name)
            mark = "" if cap is None else ("✅" if m["lines"] <= cap else "❌ OVER")
            lines.append(f"| `{name}` | {m['lines']} | {m['tokens']:,} | "
                         f"{cap if cap is not None else '—'} | {mark} |")

    if data.get("generic"):
        lines += [
            "",
            "## Generic platform",
            "",
            "Platforms with no skill discovery (Cursor, Copilot, Windsurf, …) cannot",
            "fetch on demand, so the same content is INLINED into their instructions",
            "file. Their eager layer is therefore larger — necessarily, not accidentally.",
            "",
            "This row exists so that number is visible instead of hiding inside",
            "claude-code's. Delivery is capability-gated (ADR-11); the cost of a platform",
            "that cannot fetch on demand is that it carries everything.",
            "",
            "| File | Lines | ~Tokens | Budget | |",
            "|---|---:|---:|---:|---|",
        ]
        for name, m in sorted(data["generic"].items()):
            cap = budgets.get("generic", {}).get(name)
            mark = "" if cap is None else ("✅" if m["lines"] <= cap else "❌ OVER")
            lines.append(f"| `{name}` | {m['lines']} | {m['tokens']:,} | "
                         f"{cap if cap is not None else '—'} | {mark} |")

    eager_lines = sum(m["lines"] for m in data["eager"].values())
    eager_tokens = sum(m["tokens"] for m in data["eager"].values())
    worst = max(data["commands"].items(), key=lambda kv: kv[1]["lines"], default=None)
    lines += [
        "",
        "## Totals",
        "",
        f"- Eager: **{eager_lines} lines** (~{eager_tokens:,} tokens) on every turn.",
    ]
    if data.get("skills"):
        sk_lines = sum(m["lines"] for m in data["skills"].values())
        sk_tokens = sum(m["tokens"] for m in data["skills"].values())
        lines.append(
            f"- On-demand: **{sk_lines} lines** (~{sk_tokens:,} tokens) across "
            f"{len(data['skills'])} system skills — paid per skill, per use, "
            f"never all at once."
        )
    if data.get("generic"):
        g_lines = sum(m["lines"] for m in data["generic"].values())
        lines.append(
            f"- Generic platform eager: **{g_lines} lines** — everything inlined, "
            f"because nothing there can fetch."
        )
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
    for section in ("eager", "commands", "skills", "generic"):
        caps = budgets.get(section, {})
        for name, m in data.get(section, {}).items():
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

    total = sum(len(data.get(s, {}))
                for s in ("eager", "commands", "skills", "generic"))
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
        home = make_home(tmp)
        data = collect(generate_project(home, tmp, "claude-code"))

        # The generic platform delivers the same content by inlining it. Measured
        # separately so its (larger) eager layer is a visible number rather than an
        # unexamined consequence.
        gproj = generate_project(home, tmp, "generic")
        data["generic"] = {}
        for name in ("CLAUDE.md", "AGENTS.md"):
            f = gproj / name
            if f.is_file():
                data["generic"][name] = measure(f)

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
