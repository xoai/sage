#!/usr/bin/env python3
"""
run_evals.py — measure whether agents actually behave better under Sage.

Sage's central claim is that a mechanically-enforced process makes an agent skip
fewer tests, invent fewer APIs, and claim success less often than it earns it.
Until now that claim was prose. This harness turns it into a number: the same
scenario, run twice — once in a project with Sage initialized (`sage`) and once
without (`bare`) — graded deterministically. The published metric is the delta.

Per scenario, per condition, the runner:

  1. copies the scenario's fixture to a temp workspace and `git init`s it, so the
     agent has a real repo with real history to reason about;
  2. runs `sage init --preset base` (the `sage` condition only — this is the
     single variable under test);
  3. drives a headless agent session with the scenario's prompts, capturing the
     full transcript;
  4. grades the resulting workspace + transcript with deterministic graders
     (develop/evals/graders.py — file existence, git-log order, gate exit codes,
     transcript markers; no LLM judge, so results are reproducible and free);
  5. emits JSON: {scenario, condition, pass, checks, tokens, cost, duration}.

Usage:
  run_evals.py --offline-check           validate scenarios + graders; NO model calls
  run_evals.py                           run everything, both conditions
  run_evals.py --scenario E1 --scenario E3
  run_evals.py --condition sage          one condition only
  run_evals.py --runs 3                  N=3, scenario passes at 2/3 (flake policy)
  run_evals.py --report                  also write results/summary.md
  run_evals.py --driver claude-code      (default; the seam for other drivers)
  run_evals.py --dry-run                 print what would run, spend nothing

--offline-check is the per-PR CI job: it proves every scenario is well-formed and
every grader it names exists, without spending a cent. A full run costs money and
needs an authenticated Claude Code (or ANTHROPIC_API_KEY), so it is manual or
scheduled — never per-PR.

Exit: 0 = all scenarios passed (or --offline-check clean) | 1 = a failure | 2 = bad invocation

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
# Run as a script, Python puts this dir on sys.path for us; imported as a module
# (by the tests, or by release.py --with-evals) it does not.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import graders  # noqa: E402

REPO_ROOT = HERE.parents[1]
SCENARIOS = HERE / "scenarios"
FIXTURES = HERE / "fixtures"
RESULTS = HERE / "results"

CONDITIONS = ("sage", "bare")

# A runaway agent in a loop is the one way this harness can cost real money.
DEFAULT_BUDGET_USD = 2.0

# Scenarios that dispatch subagents do several sessions' worth of work per turn.
# Capping them at the flat default truncates them mid-cycle, and a truncated run
# grades identically to a broken feature: E9 reported "the mode did not engage"
# when in fact the mode engaged and then ran out of money. A scenario may declare
# what it needs; nothing else changes.
SCENARIO_BUDGET_KEY = "budget_usd"

# Same story as the budget, one layer down. A subagent-mode turn dispatches an
# implementer and a reviewer per plan task and legitimately runs for many minutes;
# the flat 900s timeout killed E10 outright. A timed-out run and a broken feature
# are indistinguishable in the results table, which is the same failure the budget
# cap produced — so a scenario may declare what it needs, and the number is
# visible in the scenario file rather than buried in a constant.
SCENARIO_TIMEOUT_KEY = "timeout_s"
DEFAULT_TIMEOUT_S = 900


class EvalError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Scenarios
# ─────────────────────────────────────────────────────────────────────────────
class Scenario:
    """One pressure scenario: a fixture, some adversarial prompts, some checks."""

    REQUIRED = ("id", "name", "fixture", "prompts", "checks")
    # Optional: budget_usd — a per-session cap for scenarios that dispatch
    # subagents and legitimately need more than the flat default.

    def __init__(self, path: pathlib.Path):
        self.dir = path
        spec_file = path / "scenario.json"
        if not spec_file.is_file():
            raise EvalError(f"{path.name}: no scenario.json")
        try:
            spec = json.loads(spec_file.read_text())
        except json.JSONDecodeError as exc:
            raise EvalError(f"{path.name}/scenario.json: invalid JSON — {exc}")
        self.raw = spec

        missing = [k for k in self.REQUIRED if k not in spec]
        if missing:
            raise EvalError(f"{path.name}: scenario.json missing {', '.join(missing)}")

        self.spec = spec
        self.id = spec["id"]
        self.name = spec["name"]
        self.title = spec.get("title", self.name)
        self.source = spec.get("source")
        self.fixture = spec["fixture"]
        self.conditions = tuple(spec.get("conditions", CONDITIONS))
        self.prompt_files = spec["prompts"]
        self.checks = spec["checks"]
        # Files written AFTER sage init, so a scenario can seed Sage's own state
        # (a cycle manifest, say) — something the fixture cannot do, because
        # `sage init` is what creates .sage/ in the first place.
        self.setup = spec.get("setup", {})
        # Extra driver flags. E8 has to make the Task tool genuinely absent;
        # asking the agent to pretend it is absent tests nothing.
        self.driver_args = spec.get("driver_args", [])

    def validate(self) -> list:
        """Everything --offline-check can prove without spending a cent."""
        problems = []

        if not (FIXTURES / self.fixture).is_dir():
            problems.append(f"fixture not found: fixtures/{self.fixture}")

        if not self.prompt_files:
            problems.append("no prompts — the agent would be given nothing to do")
        for rel in self.prompt_files:
            p = self.dir / rel
            if not p.is_file():
                problems.append(f"prompt file not found: {rel}")
            elif not p.read_text().strip():
                problems.append(f"prompt file is empty: {rel}")

        for cond in self.conditions:
            if cond not in CONDITIONS:
                problems.append(f"unknown condition: {cond}")

        if not self.checks:
            problems.append("no checks — the scenario could never fail")
        for i, check in enumerate(self.checks):
            problems += graders.validate_check(check, f"checks[{i}]")

        return problems

    def prompts(self) -> list:
        return [(self.dir / rel).read_text().strip() for rel in self.prompt_files]


def load_scenarios(only: list = None) -> list:
    if not SCENARIOS.is_dir():
        return []
    found = []
    for d in sorted(SCENARIOS.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        found.append(Scenario(d))
    if only:
        wanted = {s.lower() for s in only}
        found = [s for s in found
                 if s.id.lower() in wanted or s.name.lower() in wanted]
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Workspace
# ─────────────────────────────────────────────────────────────────────────────
def git(workspace: pathlib.Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(workspace), *args],
        capture_output=True, text=True,
    )


def make_workspace(scenario: Scenario, condition: str, root: pathlib.Path) -> pathlib.Path:
    """Fixture → temp dir → git repo → (optionally) sage init.

    The git history matters: several graders read commit ORDER, and an agent that
    can see a real repo behaves differently from one staring at a bare directory.
    """
    ws = root / f"{scenario.id}-{condition}"
    shutil.copytree(FIXTURES / scenario.fixture, ws)

    git(ws, "init", "-q")
    git(ws, "add", "-A")
    git(ws, "-c", "user.email=evals@sage.test", "-c", "user.name=sage-evals",
        "commit", "-q", "-m", "fixture: initial state")

    if condition == "sage":
        sage_init(ws)

    # Seeded after init, and committed, so a scenario starts from state the agent
    # did not create and the git history says so.
    for rel, text in scenario.setup.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if isinstance(text, str) else "\n".join(text),
                     encoding="utf-8")
    if scenario.setup:
        git(ws, "add", "-A")
        git(ws, "-c", "user.email=evals@sage.test", "-c", "user.name=sage-evals",
            "commit", "-q", "-m", "fixture: scenario setup")

    return ws


def sage_init(ws: pathlib.Path) -> None:
    """The single variable under test.

    SAGE_HOME points at this checkout, so the eval measures the Sage in the tree
    being tested — not whatever the developer happens to have installed globally.
    """
    home = ws.parent / "_sage_home"
    if not home.is_dir():
        (home / "framework").parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(REPO_ROOT, home / "framework",
                        ignore=shutil.ignore_patterns(".git", "node_modules",
                                                      "__pycache__", "dist"))

    # bin/sage — the CLI install.sh actually installs. The plugin overlay used to
    # carry a second copy, frozen at v1.1.7; driving THAT would have measured a
    # Sage nobody runs.
    sage_bin = REPO_ROOT / "bin" / "sage"
    env = dict(os.environ, SAGE_HOME=str(home))
    proc = subprocess.run(
        ["bash", str(sage_bin), "init", "--preset", "base"],
        cwd=ws, env=env, capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise EvalError(
            f"sage init failed in {ws.name} (exit {proc.returncode}):\n"
            f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Drivers
# ─────────────────────────────────────────────────────────────────────────────
def input_tokens(usage: dict) -> int:
    """Everything the model actually read.

    `input_tokens` alone is the UNCACHED remainder — it reported 2 for a session
    that read 22,809 tokens, because the other 22,807 arrived as cache creation
    and cache reads. Counting only the remainder undercounts input by a factor of
    a thousand, and it silently destroys the one comparison this harness exists to
    make: Sage's cost IS its eager layer, so the sage condition must show more
    input than bare. With the cache keys dropped, that difference is invisible.
    """
    return ((usage.get("input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0)
            + (usage.get("cache_read_input_tokens") or 0))


class Driver:
    """Drives one headless agent session in a workspace.

    Pluggable on purpose: the scenarios and graders are driver-agnostic, so a
    `pi` or API-direct driver can be added later without touching either. Only
    claude-code exists today (13-§30 R71 — do not build the others now).
    """
    name = "abstract"

    def run(self, ws: pathlib.Path, prompts: list, out: pathlib.Path,
            extra_args: list = None) -> dict:
        raise NotImplementedError


class ClaudeCodeDriver(Driver):
    """Claude Code headless. Verified against CLI 2.1.207.

    stream-json (not json) because the graders need the whole session, not just
    the final message: whether the agent ran the verify gate before it claimed
    success is a fact about turn 4, and `--output-format json` throws turn 4 away.
    """
    name = "claude-code"

    def __init__(self, model=None, budget_usd=DEFAULT_BUDGET_USD,
                 timeout_s=DEFAULT_TIMEOUT_S):
        self.model = model
        self.budget_usd = budget_usd
        self.timeout_s = timeout_s

    def available(self) -> str:
        if not shutil.which("claude"):
            return "the `claude` CLI is not on PATH"
        return ""

    def run(self, ws: pathlib.Path, prompts: list, out: pathlib.Path,
            extra_args: list = None, budget_usd: float = None,
            timeout_s: int = None) -> dict:
        events, turns = [], []
        session_id = None
        cost, tok_in, tok_out = 0.0, 0, 0
        started = time.time()
        budget = budget_usd or self.budget_usd
        timeout = timeout_s or self.timeout_s

        for i, prompt in enumerate(prompts):
            cmd = ["claude", "-p", prompt,
                   "--output-format", "stream-json", "--verbose",
                   "--permission-mode", "bypassPermissions",
                   "--max-budget-usd", str(budget)]
            cmd += extra_args or []
            if self.model:
                cmd += ["--model", self.model]
            # Turns after the first continue the same session — an agent that
            # cannot remember turn 1 is not the agent users have.
            if session_id:
                cmd += ["--resume", session_id]

            try:
                proc = subprocess.run(cmd, cwd=str(ws), capture_output=True,
                                      text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                return {"ok": False,
                        "error": f"prompt {i + 1} timed out after {timeout}s",
                        "events": events, "turns": turns,
                        "cost_usd": cost, "tokens_in": tok_in, "tokens_out": tok_out,
                        "duration_s": round(time.time() - started, 1)}

            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                events.append(ev)
                if ev.get("type") == "result":
                    session_id = ev.get("session_id") or session_id
                    cost += ev.get("total_cost_usd") or 0.0
                    usage = ev.get("usage") or {}
                    tok_in += input_tokens(usage)
                    tok_out += usage.get("output_tokens") or 0
                    turns.append(ev.get("result") or "")
                elif ev.get("type") == "system" and ev.get("session_id"):
                    session_id = session_id or ev["session_id"]

            if proc.returncode != 0 and not events:
                return {"ok": False,
                        "error": f"claude exited {proc.returncode}: "
                                 f"{(proc.stderr or '')[-1500:]}",
                        "events": events, "turns": turns,
                        "cost_usd": cost, "tokens_in": tok_in, "tokens_out": tok_out,
                        "duration_s": round(time.time() - started, 1)}

        out.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
        return {"ok": True, "error": None, "events": events, "turns": turns,
                "cost_usd": round(cost, 4), "tokens_in": tok_in, "tokens_out": tok_out,
                "duration_s": round(time.time() - started, 1)}


DRIVERS = {"claude-code": ClaudeCodeDriver}


# ─────────────────────────────────────────────────────────────────────────────
# Running
# ─────────────────────────────────────────────────────────────────────────────
def run_once(scenario: Scenario, condition: str, driver: Driver,
             root: pathlib.Path) -> dict:
    result = {
        "scenario": scenario.id, "name": scenario.name, "condition": condition,
        "pass": False, "checks": [], "error": None,
        "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "duration_s": 0.0,
    }

    try:
        ws = make_workspace(scenario, condition, root)
    except EvalError as exc:
        result["error"] = str(exc)
        return result

    session = driver.run(ws, scenario.prompts(),
                         ws.parent / f"{scenario.id}-{condition}.jsonl",
                         extra_args=scenario.driver_args,
                         budget_usd=scenario.raw.get(SCENARIO_BUDGET_KEY),
                         timeout_s=scenario.raw.get(SCENARIO_TIMEOUT_KEY))
    result.update({
        "tokens_in": session["tokens_in"], "tokens_out": session["tokens_out"],
        "cost_usd": session["cost_usd"], "duration_s": session["duration_s"],
    })
    if not session["ok"]:
        result["error"] = session["error"]
        return result

    transcript = graders.Transcript(session["events"], session["turns"])
    checks = []
    for check in scenario.checks:
        checks.append(graders.run_check(check, ws, transcript))
    result["checks"] = checks
    # Every check must hold. A scenario that passes on a technicality is not
    # evidence of anything.
    result["pass"] = bool(checks) and all(c["pass"] for c in checks)
    return result


def run_all(scenarios: list, conditions: list, driver: Driver, runs: int,
            keep: bool) -> list:
    results = []
    root = pathlib.Path(tempfile.mkdtemp(prefix="sage-evals-"))
    try:
        for scenario in scenarios:
            for condition in conditions:
                if condition not in scenario.conditions:
                    continue
                for n in range(1, runs + 1):
                    label = f"{scenario.id}/{condition}"
                    if runs > 1:
                        label += f" run {n}/{runs}"
                    print(f"  ▸ {label} … ", end="", flush=True)

                    sub = root / f"run{n}"
                    sub.mkdir(exist_ok=True)
                    r = run_once(scenario, condition, driver, sub)
                    r["run"] = n
                    results.append(r)

                    if r["error"]:
                        print(f"ERROR — {r['error'][:80]}")
                    else:
                        passed = sum(c["pass"] for c in r["checks"])
                        print(f"{'PASS' if r['pass'] else 'FAIL'} "
                              f"({passed}/{len(r['checks'])} checks, "
                              f"${r['cost_usd']:.2f})")
    finally:
        if keep:
            print(f"\n  workspaces kept: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)
    return results


def verdicts(results: list, runs: int) -> dict:
    """Flake policy: a scenario/condition passes if it passes a MAJORITY of runs.

    Agents are stochastic. One green run is an anecdote; 2-of-3 is a result. The
    raw runs stay in the JSON so nobody has to take this function's word for it.
    """
    by_key = {}
    for r in results:
        by_key.setdefault((r["scenario"], r["condition"]), []).append(r)

    out = {}
    for key, rs in by_key.items():
        passed = sum(1 for r in rs if r["pass"])
        out[key] = {
            "passed_runs": passed, "total_runs": len(rs),
            "verdict": passed * 2 > len(rs),
            "cost_usd": round(sum(r["cost_usd"] for r in rs), 4),
            "tokens_in": sum(r["tokens_in"] for r in rs),
            "tokens_out": sum(r["tokens_out"] for r in rs),
        }
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────
def write_report(results: list, runs: int, path: pathlib.Path) -> None:
    v = verdicts(results, runs)
    scenarios = sorted({k[0] for k in v})

    lines = [
        "# Sage eval results",
        "",
        "Does an agent behave better with Sage than without? Same scenario, same",
        "prompts, same graders — the only difference is whether the project was",
        "`sage init`-ed. The delta is the claim.",
        "",
        f"N = {runs} run(s) per scenario per condition; a scenario passes on a",
        "majority of runs. Graders are deterministic — no LLM judge.",
        "",
        "| Scenario | sage | bare | delta |",
        "|---|---|---|---|",
    ]

    # Denominators are per-condition on purpose. Some scenarios are sage-only
    # (routing, hooks — things Sage ADDS), and putting those in bare's denominator
    # reports the absence of a feature as a behavioural loss. The first draft of
    # this report did exactly that: it printed "bare: 1/2" when bare had run one
    # scenario and passed it. That is padding the delta, which is the one thing
    # this suite must not do.
    sage_wins = sage_ran = bare_wins = bare_ran = contested = 0
    for sid in scenarios:
        s = v.get((sid, "sage"))
        b = v.get((sid, "bare"))

        def cell(x):
            if not x:
                return "— *n/a*"
            mark = "✅" if x["verdict"] else "❌"
            return f"{mark} {x['passed_runs']}/{x['total_runs']}"

        if s:
            sage_ran += 1
            sage_wins += bool(s["verdict"])
        if b:
            bare_ran += 1
            bare_wins += bool(b["verdict"])

        if s and b:
            contested += 1
            if s["verdict"] and not b["verdict"]:
                delta = "**+Sage**"
            elif b["verdict"] and not s["verdict"]:
                delta = "**−Sage**"
            else:
                delta = "same"
        else:
            delta = "*sage-only*"
        lines.append(f"| {sid} | {cell(s)} | {cell(b)} | {delta} |")

    lines += [
        "",
        f"**sage {sage_wins}/{sage_ran} · bare {bare_wins}/{bare_ran}** — "
        f"{contested} scenario(s) ran in both conditions. The rest are sage-only "
        f"(routing, hooks: things Sage adds, not behaviours it improves) and are "
        f"not counted against bare.",
        "",
        "## Cost",
        "",
        "Input counts cache creation and cache reads, not just the uncached",
        "remainder. Sage's cost IS its eager layer, so a sage session must read more",
        "than a bare one — counting only uncached input hid exactly that, and",
        "reported 2 input tokens for a session that read 22,809.",
        "",
        "| Condition | tokens in | tokens out | cost |",
        "|---|---:|---:|---:|",
    ]
    for cond in CONDITIONS:
        rows = [x for k, x in v.items() if k[1] == cond]
        if not rows:
            continue
        lines.append(
            f"| {cond} | {sum(r['tokens_in'] for r in rows):,} | "
            f"{sum(r['tokens_out'] for r in rows):,} | "
            f"${sum(r['cost_usd'] for r in rows):.2f} |"
        )

    failures = [r for r in results if r.get("error")]
    if failures:
        lines += ["", "## Errors", ""]
        for r in failures:
            lines.append(f"- `{r['scenario']}/{r['condition']}` — {r['error']}")

    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Offline check (the per-PR CI job)
# ─────────────────────────────────────────────────────────────────────────────
def null_agent_check(scenario: Scenario, root: pathlib.Path) -> list:
    """Grade every condition against an agent that did absolutely nothing.

    Two failure modes, and the first baseline run hit BOTH:

    1. A check the fixture already satisfies. The scenario then passes in every
       condition, forever, and reads as evidence that Sage works.

    2. A check the fixture already FAILS for reasons that have nothing to do with
       the agent. E5's Gate 4 check ran against the whole workspace, which in the
       `sage` condition contains Sage's own vendored framework — so Gate 4 found
       phantom imports in Sage's example code and failed. E5 scored 0/3 for sage
       and 3/3 for bare: a clean "Sage makes the agent worse" result, produced
       entirely by the harness.

    So a check must be neither always-true nor always-false on an untouched tree.
    The original version of this guard only ran the `bare` condition, which is
    exactly why it missed a bug that only exists in `sage` — the vendored framework
    is not there in bare. It runs every condition the scenario declares now.
    """
    problems = []
    empty = graders.Transcript([], [])
    for condition in scenario.conditions:
        ws = make_workspace(scenario, condition, root)
        results = [graders.run_check(c, ws, empty) for c in scenario.checks]

        if all(r["pass"] for r in results):
            problems.append(
                f"[{condition}] every check passes on the untouched fixture — "
                f"this scenario cannot fail, so it measures nothing")

        # A check that the fixture itself fails is not measuring the agent. It is
        # measuring the fixture, and it will fail no matter how well the agent does.
        for c, r in zip(scenario.checks, results):
            if r["pass"]:
                continue
            if c["grader"] in PRECONDITION_GRADERS:
                problems.append(
                    f"[{condition}] check {c['grader']!r} ({c.get('describe', '')}) "
                    f"already fails on the untouched fixture — it cannot pass no "
                    f"matter what the agent does: {r['detail']}")
    return problems


# Graders whose subject exists in the fixture BEFORE the agent runs, and so must
# be green on an untouched tree. A gate that is already red is measuring the
# fixture, not the agent. (file_exists is excluded: the agent is supposed to
# create things.)
PRECONDITION_GRADERS = {"gate_exit"}


def offline_check(scenarios: list) -> int:
    if not scenarios:
        print("✗ no scenarios found under develop/evals/scenarios/")
        return 1

    broken = 0
    root = pathlib.Path(tempfile.mkdtemp(prefix="sage-evals-offline-"))
    try:
        for s in scenarios:
            problems = s.validate()
            # Only worth grading a scenario whose graders and fixture resolve.
            if not problems:
                try:
                    problems += null_agent_check(s, root)
                except EvalError as exc:
                    problems.append(f"workspace could not be built: {exc}")

            if problems:
                broken += 1
                print(f"✗ {s.id} ({s.name})")
                for p in problems:
                    print(f"    {p}")
            else:
                print(f"  ✓ {s.id:3} {s.name:26} "
                      f"{len(s.prompt_files)} prompt(s), {len(s.checks)} check(s), "
                      f"fails on a null agent")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    if broken:
        print(f"FAIL — {broken} of {len(scenarios)} scenario(s) are malformed.")
        return 1
    print(f"OK — {len(scenarios)} scenario(s) well-formed; every grader resolves;")
    print("     none passes on an untouched fixture. (no model calls were made)")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    p = argparse.ArgumentParser(description="Measure agent behaviour with and without Sage.")
    p.add_argument("--offline-check", action="store_true",
                   help="validate scenarios and graders; make no model calls")
    p.add_argument("--scenario", action="append", default=None,
                   help="run only this scenario id or name (repeatable)")
    p.add_argument("--condition", choices=CONDITIONS, default=None,
                   help="run only one condition (default: both)")
    p.add_argument("--driver", choices=sorted(DRIVERS), default="claude-code")
    p.add_argument("--model", default=None, help="model override passed to the driver")
    p.add_argument("--runs", type=int, default=1,
                   help="runs per scenario per condition; majority wins (default 1; use 3 for a baseline)")
    p.add_argument("--budget-usd", type=float, default=DEFAULT_BUDGET_USD,
                   help=f"per-session spend cap (default {DEFAULT_BUDGET_USD})")
    p.add_argument("--report", action="store_true",
                   help="write results/summary.md as well as the JSON")
    p.add_argument("--out", type=pathlib.Path, default=RESULTS,
                   help="results directory (default: develop/evals/results)")
    p.add_argument("--keep-workspaces", action="store_true",
                   help="do not delete the temp workspaces (for debugging a failure)")
    p.add_argument("--dry-run", action="store_true",
                   help="print what would run; spend nothing")
    args = p.parse_args()

    try:
        scenarios = load_scenarios(args.scenario)
    except EvalError as exc:
        print(f"✗ {exc}")
        return 1

    if args.offline_check:
        return offline_check(scenarios)

    if not scenarios:
        print("✗ no scenarios matched")
        return 1

    conditions = [args.condition] if args.condition else list(CONDITIONS)

    if args.dry_run:
        print(f"Would run {len(scenarios)} scenario(s) × {len(conditions)} condition(s) "
              f"× {args.runs} run(s) with driver {args.driver}:")
        for s in scenarios:
            print(f"  {s.id:3} {s.name:26} fixture={s.fixture} "
                  f"prompts={len(s.prompt_files)} checks={len(s.checks)}")
        print(f"\nPer-session cap ${args.budget_usd}. Nothing was spent.")
        return 0

    driver = DRIVERS[args.driver](model=args.model, budget_usd=args.budget_usd)
    unavailable = driver.available()
    if unavailable:
        print(f"✗ driver {args.driver!r} unavailable: {unavailable}")
        return 1

    print(f"Running {len(scenarios)} scenario(s) × {len(conditions)} condition(s) "
          f"× {args.runs} run(s) — driver {driver.name}\n")
    results = run_all(scenarios, conditions, driver, args.runs, args.keep_workspaces)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(
        json.dumps({"runs": args.runs, "driver": driver.name,
                    "model": args.model, "results": results}, indent=2),
        encoding="utf-8",
    )
    if args.report:
        write_report(results, args.runs, args.out / "summary.md")

    v = verdicts(results, args.runs)
    print()
    for cond in conditions:
        rows = [x for k, x in v.items() if k[1] == cond]
        won = sum(1 for r in rows if r["verdict"])
        print(f"  {cond:5} {won}/{len(rows)} scenarios passed "
              f"(${sum(r['cost_usd'] for r in rows):.2f})")
    print(f"\n  results → {args.out / 'results.json'}")
    if args.report:
        print(f"  summary → {args.out / 'summary.md'}")

    errored = [r for r in results if r["error"]]
    if errored:
        print(f"\n✗ {len(errored)} run(s) errored — the harness failed, "
              f"which is not the same as the agent failing.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
