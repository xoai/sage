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
  3. drives one or more headless agent sessions with the scenario's prompts,
     capturing the full transcript;
  4. grades the resulting workspace + transcript with deterministic graders
     (develop/evals/graders.py — file existence, git-log order, gate exit codes,
     transcript markers; no LLM judge, so results are reproducible and free);
  5. emits JSON: {scenario, condition, mode, pass, checks, tokens, cost, duration}.

MULTI-SESSION (ADR-13 / R116). Sage's headline claim is long-horizon: that a
cycle survives a context window. Every scenario up to E11 ran in ONE session,
which means the claim was structurally untestable — the agent that finished the
work was the agent that started it, and it simply remembered. A scenario may
instead declare `sessions`: an ordered list, each with its own prompts, run
against ONE PERSISTENT WORKSPACE. Each session is a FRESH model context (no
--resume across the boundary). That boundary is the whole experiment: session 2
knows only what session 1 wrote to disk. A session may declare
`interrupt_after_turns` to model the laptop closing mid-cycle.

EXECUTION MODE (R119). `--mode subagents` sets the flag Sage's own flag parser
reads (`subagents: true` in .sage/config.yaml), so the same scenario can be run
inline and in subagent mode and the two compared. Mode applies to the `sage`
condition only; bare has no Sage to configure.

Usage:
  run_evals.py --offline-check           validate scenarios + graders; NO model calls
  run_evals.py                           run everything, both conditions
  run_evals.py --scenario E1 --scenario E3
  run_evals.py --condition sage          one condition only
  run_evals.py --mode subagents          force subagent execution (sage condition)
  run_evals.py --mode both               the mode matrix: inline AND subagents
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
import re
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

# Execution modes (R119). `inline` is Sage's default loop; `subagents` dispatches
# a fresh implementer and an independent reviewer per plan task (ADR-10). The mode
# is a property of the RUN, not of the scenario: the same scenario run both ways is
# the entire point of the comparison, so it must not be baked into scenario.json.
MODES = ("inline", "subagents")

# Mode is meaningless in the bare condition — there is no Sage to put in a mode.
# Recording it as "inline" there would be a quiet lie in the results table: it
# would imply bare ran Sage's inline loop, when bare ran no loop at all.
MODE_NA = "n/a"

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
class Session:
    """One model context. The unit that ENDS at a context boundary.

    A session is not a turn. Prompts inside a session resume the same session id,
    so the agent remembers them. Prompts in the NEXT session do not: it is a new
    context that has never seen the previous one, and everything it knows about the
    work it must read off the disk. That is the only honest way to test a claim
    about surviving a context window — and every scenario before L1 ran in one
    session, which is why the claim was never tested.
    """

    def __init__(self, spec: dict, scenario_dir: pathlib.Path, index: int):
        self.dir = scenario_dir
        self.name = spec.get("name") or f"s{index + 1}"
        self.prompt_files = spec.get("prompts") or []
        # "Kill after N turns" (R116). The agent completes turn N and then never
        # gets turn N+1 — the user closed the laptop. It is NOT a mid-turn SIGKILL:
        # turn N finishes, so any checkpoint the workflow writes at the end of a
        # turn still gets written. Use interrupt_after_s for the harder case.
        self.interrupt_after_turns = spec.get("interrupt_after_turns")
        # A real interruption: kill the process mid-turn after S seconds. The
        # transcript is truncated and the workspace is left wherever it was. The
        # runner must NOT record this as a harness error — an expected kill and a
        # crash look identical in a results table unless one of them is declared.
        self.interrupt_after_s = spec.get("interrupt_after_s")

    @property
    def interrupted(self) -> bool:
        return bool(self.interrupt_after_turns or self.interrupt_after_s)

    def prompts(self) -> list:
        texts = [(self.dir / rel).read_text().strip() for rel in self.prompt_files]
        if self.interrupt_after_turns:
            texts = texts[:self.interrupt_after_turns]
        return texts


class Scenario:
    """One pressure scenario: a fixture, some adversarial prompts, some checks."""

    REQUIRED = ("id", "name", "fixture", "checks")
    # Optional: budget_usd — a per-session cap for scenarios that dispatch
    # subagents and legitimately need more than the flat default.
    # Optional: sessions — see Session. XOR with `prompts`.

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
        self.checks = spec["checks"]

        # A single-session scenario is the degenerate multi-session one. Normalizing
        # here means E1–E11 keep working untouched and the runner has exactly one
        # code path to get right, rather than a legacy path and a new path that
        # drift until only one of them is tested.
        self.multi_session = "sessions" in spec
        if self.multi_session and "prompts" in spec:
            raise EvalError(
                f"{path.name}: declares BOTH 'prompts' and 'sessions' — "
                f"the harness cannot know which is the truth")
        if not self.multi_session and "prompts" not in spec:
            raise EvalError(f"{path.name}: scenario.json missing prompts (or sessions)")

        raw_sessions = (spec["sessions"] if self.multi_session
                        else [{"name": "main", "prompts": spec["prompts"]}])
        self.sessions = [Session(s, path, i) for i, s in enumerate(raw_sessions)]

        # Files written AFTER sage init, so a scenario can seed Sage's own state
        # (a cycle manifest, say) — something the fixture cannot do, because
        # `sage init` is what creates .sage/ in the first place.
        self.setup = spec.get("setup", {})
        # Extra driver flags. E8 has to make the Task tool genuinely absent;
        # asking the agent to pretend it is absent tests nothing.
        self.driver_args = spec.get("driver_args", [])

    @property
    def session_names(self) -> list:
        return [s.name for s in self.sessions]

    def validate(self) -> list:
        """Everything --offline-check can prove without spending a cent."""
        problems = []

        if not (FIXTURES / self.fixture).is_dir():
            problems.append(f"fixture not found: fixtures/{self.fixture}")

        if not self.sessions:
            problems.append("no sessions — the agent would be given nothing to do")

        seen = set()
        for sess in self.sessions:
            if sess.name in seen:
                problems.append(
                    f"duplicate session name {sess.name!r} — checks scoped to it "
                    f"would be ambiguous")
            seen.add(sess.name)

            if not sess.prompt_files:
                problems.append(f"session {sess.name!r}: no prompts")
            for rel in sess.prompt_files:
                p = self.dir / rel
                if not p.is_file():
                    problems.append(f"session {sess.name!r}: prompt file not found: {rel}")
                elif not p.read_text().strip():
                    problems.append(f"session {sess.name!r}: prompt file is empty: {rel}")

            n = sess.interrupt_after_turns
            if n is not None:
                if not isinstance(n, int) or n < 1:
                    problems.append(
                        f"session {sess.name!r}: interrupt_after_turns must be a "
                        f"positive int, got {n!r}")
                elif n >= len(sess.prompt_files):
                    # Silently sending every prompt and calling it an interruption
                    # is the harness lying to itself: the scenario would report that
                    # it tested a resume when nothing was ever interrupted.
                    problems.append(
                        f"session {sess.name!r}: interrupt_after_turns={n} but the "
                        f"session has {len(sess.prompt_files)} prompt(s) — nothing "
                        f"would be cut off, so no interruption is being simulated")

        for cond in self.conditions:
            if cond not in CONDITIONS:
                problems.append(f"unknown condition: {cond}")

        if not self.checks:
            problems.append("no checks — the scenario could never fail")
        for i, check in enumerate(self.checks):
            problems += graders.validate_check(check, f"checks[{i}]")
            # A check scoped to a session that does not exist silently grades the
            # empty transcript, and an empty transcript passes every `_lacks` check
            # there is. That is a green result produced by a typo.
            scope = check.get("session")
            if scope is not None and scope not in seen:
                problems.append(
                    f"checks[{i}]: scoped to session {scope!r}, which this scenario "
                    f"does not declare (has: {', '.join(self.session_names)})")

        return problems

    def prompts(self) -> list:
        """Every prompt across every session — for --dry-run counts only."""
        out = []
        for s in self.sessions:
            out += s.prompts()
        return out


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


_MANIFEST_SUBAGENT_FLAG = re.compile(r"^(\s*subagents:\s*)(true|false)\s*$", re.MULTILINE)


def apply_mode_to_setup(text: str, mode: str) -> str:
    """Force a seeded manifest's `subagents:` flag to match the run's mode.

    E9 seeds a manifest that hard-codes `subagents: true`. Running E9 in inline
    mode for the comparison (R119) would otherwise be a contradiction the harness
    quietly resolved in favour of the scenario file: the config would say inline,
    the manifest would say subagents, and the results table would report a mode the
    run did not use. The scenario declares the SITUATION; the mode is the variable.
    """
    if mode not in MODES:
        return text
    return _MANIFEST_SUBAGENT_FLAG.sub(
        lambda m: f"{m.group(1)}{'true' if mode == 'subagents' else 'false'}", text)


def set_execution_mode(ws: pathlib.Path, mode: str) -> None:
    """Put the project's flag default where Sage's own flag parser reads it.

    sage_flags.load_defaults() honours exactly one spelling — a top-level
    `subagents: true`, one space, no trailing content — so that Bash and Python
    agree byte-for-byte. Write that spelling and nothing else. Writing `false`
    explicitly (rather than omitting the key) is deliberate: the inline arm of a
    mode comparison should be visible in the config it ran under, not inferred
    from an absence.
    """
    config = ws / ".sage" / "config.yaml"
    if not config.is_file():
        return
    text = config.read_text(encoding="utf-8")
    line = f"subagents: {'true' if mode == 'subagents' else 'false'}"
    if re.search(r"^subagents:.*$", text, re.MULTILINE):
        text = re.sub(r"^subagents:.*$", line, text, count=1, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{line}\n"
    config.write_text(text, encoding="utf-8")


def make_workspace(scenario: Scenario, condition: str, root: pathlib.Path,
                   mode: str = None) -> pathlib.Path:
    """Fixture → temp dir → git repo → (optionally) sage init → (optionally) mode.

    The git history matters: several graders read commit ORDER, and an agent that
    can see a real repo behaves differently from one staring at a bare directory.

    Built ONCE per run, then reused across every session (R116). The workspace is
    the only thing that crosses a session boundary — which is precisely the claim
    under test, so it must not be rebuilt between sessions.
    """
    ws = root / f"{scenario.id}-{condition}"
    shutil.copytree(FIXTURES / scenario.fixture, ws)

    git(ws, "init", "-q")
    git(ws, "add", "-A")
    git(ws, "-c", "user.email=evals@sage.test", "-c", "user.name=sage-evals",
        "commit", "-q", "-m", "fixture: initial state")

    if condition == "sage":
        sage_init(ws)
        if mode in MODES:
            set_execution_mode(ws, mode)

    # Seeded after init, and committed, so a scenario starts from state the agent
    # did not create and the git history says so.
    for rel, text in scenario.setup.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        body = text if isinstance(text, str) else "\n".join(text)
        if condition == "sage" and mode in MODES:
            body = apply_mode_to_setup(body, mode)
        p.write_text(body, encoding="utf-8")
    if scenario.setup:
        git(ws, "add", "-A")
        git(ws, "-c", "user.email=evals@sage.test", "-c", "user.name=sage-evals",
            "commit", "-q", "-m", "fixture: scenario setup")

    return ws


def head_sha(ws: pathlib.Path) -> str:
    """The commit a session starts from — the anchor for its diff.

    Recorded at every session boundary so a grader can ask "what did SESSION 2
    change", which is a different and much sharper question than "what does the
    tree look like now". L1's decision-respected check is exactly that question:
    session 1 legitimately wrote the plan, so grading the whole-run diff for the
    foreclosed path would indict session 1's planning for session 2's sins.
    """
    return (git(ws, "rev-parse", "HEAD").stdout or "").strip()


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
            timeout_s: int = None, kill_after_s: int = None) -> dict:
        """Drive ONE session: every prompt here resumes the same session id.

        A new call to run() is a new context. That is how a multi-session scenario
        gets its boundary — not by clearing anything, but by simply never passing
        --resume across it.
        """
        events, turns = [], []
        session_id = None
        cost, tok_in, tok_out = 0.0, 0, 0
        started = time.time()
        budget = budget_usd or self.budget_usd
        timeout = timeout_s or self.timeout_s
        interrupted = False

        def snapshot(ok, error):
            out.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
            return {"ok": ok, "error": error, "events": events, "turns": turns,
                    "interrupted": interrupted,
                    "cost_usd": round(cost, 4),
                    "tokens_in": tok_in, "tokens_out": tok_out,
                    "duration_s": round(time.time() - started, 1)}

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

            # A declared mid-turn kill is the interruption, not a failure. The
            # distinction has to be made HERE, because downstream a killed session
            # and a hung one are the same truncated transcript — and the harness has
            # already been burned once by a truncated run grading as a broken
            # feature (E9, the budget cap).
            deadline = kill_after_s if (kill_after_s and i == len(prompts) - 1) else timeout

            try:
                proc = subprocess.run(cmd, cwd=str(ws), capture_output=True,
                                      text=True, timeout=deadline)
            except subprocess.TimeoutExpired as exc:
                if kill_after_s and i == len(prompts) - 1:
                    interrupted = True
                    # TimeoutExpired carries the bytes captured before the kill —
                    # and hands them back as bytes even under text=True, depending
                    # on the CPython version. Decode defensively; a partial
                    # transcript is the whole evidence of an interrupted session.
                    partial = exc.stdout or ""
                    if isinstance(partial, bytes):
                        partial = partial.decode("utf-8", errors="replace")
                    for line in partial.splitlines():
                        try:
                            events.append(json.loads(line.strip()))
                        except (json.JSONDecodeError, ValueError):
                            continue
                    return snapshot(True, None)
                return snapshot(
                    False, f"prompt {i + 1} timed out after {deadline}s")

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
                return snapshot(
                    False, f"claude exited {proc.returncode}: "
                           f"{(proc.stderr or '')[-1500:]}")

        return snapshot(True, None)


DRIVERS = {"claude-code": ClaudeCodeDriver}


# ─────────────────────────────────────────────────────────────────────────────
# Running
# ─────────────────────────────────────────────────────────────────────────────
def run_once(scenario: Scenario, condition: str, driver: Driver,
             root: pathlib.Path, mode: str = None) -> dict:
    """One workspace, every session in order, then grade.

    The workspace is built once and survives every session. Nothing else does: each
    session gets a fresh model context, so whatever session N+1 knows about the work,
    it read off the disk that session N left behind. That is the experiment.
    """
    effective_mode = mode if (condition == "sage" and mode in MODES) else MODE_NA
    result = {
        "scenario": scenario.id, "name": scenario.name, "condition": condition,
        "mode": effective_mode,
        "pass": False, "checks": [], "error": None, "sessions": [],
        "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "duration_s": 0.0,
    }

    try:
        ws = make_workspace(scenario, condition, root, mode=mode)
    except EvalError as exc:
        result["error"] = str(exc)
        return result

    # Per-session transcripts, kept separate. Concatenating them would let a marker
    # session 1 legitimately produced satisfy a check that is asking about session 2
    # — and for the resume scenarios that is the entire question, so a check must be
    # able to say WHICH session it means.
    by_session = {}
    all_events, all_turns = [], []

    for sess in scenario.sessions:
        anchor = head_sha(ws)
        out = ws.parent / f"{scenario.id}-{condition}-{sess.name}.jsonl"
        run = driver.run(ws, sess.prompts(), out,
                         extra_args=scenario.driver_args,
                         budget_usd=scenario.raw.get(SCENARIO_BUDGET_KEY),
                         timeout_s=scenario.raw.get(SCENARIO_TIMEOUT_KEY),
                         kill_after_s=sess.interrupt_after_s)

        result["tokens_in"] += run["tokens_in"]
        result["tokens_out"] += run["tokens_out"]
        result["cost_usd"] = round(result["cost_usd"] + run["cost_usd"], 4)
        result["duration_s"] = round(result["duration_s"] + run["duration_s"], 1)
        result["sessions"].append({
            "name": sess.name,
            "interrupted": bool(run.get("interrupted")) or bool(sess.interrupt_after_turns),
            "turns_sent": len(sess.prompts()),
            "tokens_in": run["tokens_in"], "tokens_out": run["tokens_out"],
            "cost_usd": run["cost_usd"], "duration_s": run["duration_s"],
            "error": run["error"],
        })

        by_session[sess.name] = graders.Transcript(
            run["events"], run["turns"], since=anchor, session=sess.name)
        all_events += run["events"]
        all_turns += run["turns"]

        # A session that dies takes the rest of the scenario with it: session 3
        # graded against a workspace session 2 never reached is measuring nothing.
        if not run["ok"]:
            result["error"] = f"session {sess.name!r}: {run['error']}"
            return result

    whole = graders.Transcript(all_events, all_turns,
                               since=None, session=None)

    checks = []
    for check in scenario.checks:
        scope = check.get("session")
        tx = by_session.get(scope) if scope else whole
        if scope and tx is None:                # validate() rejects this; belt and braces
            checks.append({"grader": check.get("grader", "?"),
                           "describe": check.get("describe", ""),
                           "pass": False,
                           "detail": f"scoped to unknown session {scope!r}"})
            continue
        checks.append(graders.run_check(check, ws, tx))
    result["checks"] = checks
    # Every check must hold. A scenario that passes on a technicality is not
    # evidence of anything.
    result["pass"] = bool(checks) and all(c["pass"] for c in checks)
    return result


def modes_for(condition: str, modes: list) -> list:
    """Which modes to run for this condition.

    `bare` gets exactly one run no matter what the matrix says. There is no Sage in
    the bare condition, so "bare in subagent mode" is not a thing that exists — and
    running it twice under two labels would double the bill to produce the same
    number twice and then present it as two data points.
    """
    if condition != "sage":
        return [None]
    return modes or [None]


def run_all(scenarios: list, conditions: list, driver: Driver, runs: int,
            keep: bool, modes: list = None) -> list:
    results = []
    root = pathlib.Path(tempfile.mkdtemp(prefix="sage-evals-"))
    try:
        for scenario in scenarios:
            for condition in conditions:
                if condition not in scenario.conditions:
                    continue
                for mode in modes_for(condition, modes):
                    for n in range(1, runs + 1):
                        label = f"{scenario.id}/{condition}"
                        if mode:
                            label += f"/{mode}"
                        if runs > 1:
                            label += f" run {n}/{runs}"
                        print(f"  ▸ {label} … ", end="", flush=True)

                        sub = root / f"run{n}-{mode or 'native'}"
                        sub.mkdir(exist_ok=True, parents=True)
                        r = run_once(scenario, condition, driver, sub, mode=mode)
                        r["run"] = n
                        results.append(r)

                        if r["error"]:
                            print(f"ERROR — {r['error'][:80]}")
                        else:
                            passed = sum(c["pass"] for c in r["checks"])
                            extra = ""
                            if len(r["sessions"]) > 1:
                                extra = f", {len(r['sessions'])} sessions"
                            print(f"{'PASS' if r['pass'] else 'FAIL'} "
                                  f"({passed}/{len(r['checks'])} checks, "
                                  f"${r['cost_usd']:.2f}{extra})")
    finally:
        if keep:
            print(f"\n  workspaces kept: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)
    return results


def verdicts(results: list, runs: int) -> dict:
    """Flake policy: a scenario/condition/mode passes if it passes a MAJORITY of runs.

    Agents are stochastic. One green run is an anecdote; 2-of-3 is a result. The
    raw runs stay in the JSON so nobody has to take this function's word for it.

    Keyed by mode as well as condition: a mode comparison that averaged inline and
    subagent runs into one verdict would answer the question it exists to ask by
    erasing it.
    """
    by_key = {}
    for r in results:
        key = (r["scenario"], r["condition"], r.get("mode", MODE_NA))
        by_key.setdefault(key, []).append(r)

    out = {}
    for key, rs in by_key.items():
        passed = sum(1 for r in rs if r["pass"])
        out[key] = {
            "passed_runs": passed, "total_runs": len(rs),
            "verdict": passed * 2 > len(rs),
            "cost_usd": round(sum(r["cost_usd"] for r in rs), 4),
            "tokens_in": sum(r["tokens_in"] for r in rs),
            "tokens_out": sum(r["tokens_out"] for r in rs),
            "duration_s": round(
                sum(r.get("duration_s") or 0.0 for r in rs) / max(len(rs), 1), 1),
        }
    return out


def sage_modes(v: dict) -> list:
    """Which sage-condition modes actually ran, in a stable order."""
    found = {k[2] for k in v if k[1] == "sage"}
    ordered = [m for m in (MODE_NA,) + MODES if m in found]
    return ordered or [MODE_NA]


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────
def write_report(results: list, runs: int, path: pathlib.Path) -> None:
    v = verdicts(results, runs)
    scenarios = sorted({k[0] for k in v})
    modes = sage_modes(v)

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

    def cell(x):
        if not x:
            return "— *n/a*"
        mark = "✅" if x["verdict"] else "❌"
        return f"{mark} {x['passed_runs']}/{x['total_runs']}"

    # Denominators are per-condition on purpose. Some scenarios are sage-only
    # (routing, hooks — things Sage ADDS), and putting those in bare's denominator
    # reports the absence of a feature as a behavioural loss. The first draft of
    # this report did exactly that: it printed "bare: 1/2" when bare had run one
    # scenario and passed it. That is padding the delta, which is the one thing
    # this suite must not do.
    sage_wins = sage_ran = bare_wins = bare_ran = contested = 0
    for sid in scenarios:
        b = v.get((sid, "bare", MODE_NA))
        if b:
            bare_ran += 1
            bare_wins += bool(b["verdict"])

        for mode in modes:
            s = v.get((sid, "sage", mode))
            if not s and mode != modes[0]:
                continue
            label = sid if mode == MODE_NA else f"{sid} *({mode})*"

            if s:
                sage_ran += 1
                sage_wins += bool(s["verdict"])

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
            lines.append(f"| {label} | {cell(s)} | {cell(b)} | {delta} |")

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

    # ── Mode breakout (R119) ────────────────────────────────────────────────
    # Only when a comparison actually ran. A one-mode table would imply a choice
    # was measured when no choice was offered.
    real_modes = [m for m in modes if m in MODES]
    if len(real_modes) > 1:
        lines += [
            "",
            "## Execution mode — inline vs. subagents",
            "",
            "The same scenarios, the same graders, the sage condition throughout.",
            "The only variable is whether each plan task was implemented and reviewed",
            "by fresh subagent contexts (ADR-10) or by the inline loop. Wall time is",
            "the mean across runs, not the sum — it is a latency, not a bill.",
            "",
            "| Mode | passed | tokens in | tokens out | cost | mean wall |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for mode in real_modes:
            rows = [x for k, x in v.items() if k[1] == "sage" and k[2] == mode]
            if not rows:
                continue
            won = sum(1 for r in rows if r["verdict"])
            wall = sum(r["duration_s"] for r in rows) / len(rows)
            lines.append(
                f"| {mode} | {won}/{len(rows)} | "
                f"{sum(r['tokens_in'] for r in rows):,} | "
                f"{sum(r['tokens_out'] for r in rows):,} | "
                f"${sum(r['cost_usd'] for r in rows):.2f} | "
                f"{wall / 60:.1f} min |"
            )
        lines += [
            "",
            "This table reports what the two modes COST and whether they PASS. It does",
            "not report which produces better code — no grader here reads for quality,",
            "and none should pretend to. That comparison needs a different instrument.",
        ]

    # ── Session breakout (R116) ─────────────────────────────────────────────
    multi = [r for r in results if len(r.get("sessions") or []) > 1]
    if multi:
        lines += [
            "",
            "## Sessions — where the cost and the recovery actually happen",
            "",
            "A multi-session scenario runs N fresh contexts against ONE workspace.",
            "Session 2 knows only what session 1 left on disk. An interrupted session",
            "was cut off on purpose — it is the scenario, not a failure.",
            "",
            "| Scenario | condition | mode | session | interrupted | tokens in | cost |",
            "|---|---|---|---|---|---:|---:|",
        ]
        for r in sorted(multi, key=lambda x: (x["scenario"], x["condition"],
                                              x.get("mode", ""), x.get("run", 0))):
            for s in r["sessions"]:
                lines.append(
                    f"| {r['scenario']} | {r['condition']} | {r.get('mode', MODE_NA)} | "
                    f"{s['name']} | {'yes' if s['interrupted'] else '—'} | "
                    f"{s['tokens_in']:,} | ${s['cost_usd']:.2f} |"
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
                shape = (f"{len(s.sessions)} session(s)" if s.multi_session
                         else f"{len(s.prompts())} prompt(s)")
                interrupted = [x.name for x in s.sessions if x.interrupted]
                mark = f", interrupt@{'+'.join(interrupted)}" if interrupted else ""
                print(f"  ✓ {s.id:3} {s.name:26} "
                      f"{shape}{mark}, {len(s.checks)} check(s), "
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
    p.add_argument("--mode", choices=sorted(MODES) + ["both"], default=None,
                   help="force Sage's execution mode (sage condition only). "
                        "'both' runs the mode matrix. Default: whatever the "
                        "scenario itself sets — the harness forces nothing.")
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
    # None means "force nothing" — the scenario's own setup decides. That is the
    # default because forcing `inline` on every existing scenario would silently
    # rewrite E9's seeded manifest and change what the current suite measures.
    modes = (list(MODES) if args.mode == "both"
             else [args.mode] if args.mode else [None])

    if args.dry_run:
        arms = sum(len(modes_for(c, modes)) for c in conditions)
        print(f"Would run {len(scenarios)} scenario(s) × {arms} arm(s) "
              f"× {args.runs} run(s) with driver {args.driver}:")
        for s in scenarios:
            shape = (f"sessions={len(s.sessions)}" if s.multi_session
                     else f"prompts={len(s.prompts())}")
            print(f"  {s.id:3} {s.name:26} fixture={s.fixture} "
                  f"{shape} checks={len(s.checks)}")
        if args.mode:
            print(f"\nExecution mode: {', '.join(m for m in modes if m)} "
                  f"(sage condition only).")
        print(f"\nPer-session cap ${args.budget_usd}. Nothing was spent.")
        return 0

    driver = DRIVERS[args.driver](model=args.model, budget_usd=args.budget_usd)
    unavailable = driver.available()
    if unavailable:
        print(f"✗ driver {args.driver!r} unavailable: {unavailable}")
        return 1

    arms = sum(len(modes_for(c, modes)) for c in conditions)
    print(f"Running {len(scenarios)} scenario(s) × {arms} arm(s) "
          f"× {args.runs} run(s) — driver {driver.name}\n")
    results = run_all(scenarios, conditions, driver, args.runs,
                      args.keep_workspaces, modes=modes)

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
