#!/usr/bin/env python3
"""profile_session.py — where does a session's spend actually go?

Built to answer one question the L-series left open: Sage resumes correctly and
pays ~9x a bare agent for it — paying for WHAT? The results table can't say; only
the transcript can. This reads the kept stream-json transcripts and attributes
cost per API call to the activity the call performed.

Method, and the two things it deliberately normalises away:

  1. Every assistant message carries usage (cache read/write per call), but the
     CLI never updates output_tokens on assistant events (they read ~1). So
     output cost comes from the RESULT event's authoritative total, distributed
     across calls proportional to emitted content length.
  2. Absolute API rates drift and per-message events can duplicate under
     retries. So input-side cost is a WEIGHT (rate-shaped), normalised so each
     session's computed total equals the CLI's own total_cost_usd exactly.
     Shares are therefore calibrated; the rates only shape the distribution.

Attribution: each call's cost goes to the tool it invoked (classified by
target: implement, test-runs, gates, bookkeeping, memory, framework reads,
orientation reads, the resume brief), to "prose-checkpoints" when it only
talked, or to "subagent-work" when parent_tool_use_id marks it as a dispatched
agent's traffic.

Usage:
    profile_session.py <transcript.jsonl> [more.jsonl ...]

Aggregates across all transcripts given (e.g. every s2 of one arm). Compare
arms by running it twice. Python 3.8+, stdlib only.

First finding (2026-07-15, L1 resume, opus, N=3 per arm): the 9x is
4.1x more API calls x 2.1x fatter context per call. Orientation — the thing
v1.3.4 mechanised — is ~2%. The money goes to the execution discipline:
adversarial gate subagents ~24%, a finer-grained loop (3x the implement calls,
2.5x the test runs), and the context tax every extra call pays.
"""
import json
import pathlib
import re
import sys
from collections import defaultdict

# opus-4 family API pricing per MTok. 1h cache writes bill at 2x input.
RATES = {"in": 15.0, "out": 75.0, "cw5": 18.75, "cw1": 30.0, "cr": 1.5}
# fable pricing differs; calibration will tell us if these are wrong for a file.


def price(u):
    cw = u.get("cache_creation") or {}
    cw5 = cw.get("ephemeral_5m_input_tokens")
    cw1 = cw.get("ephemeral_1h_input_tokens")
    if cw5 is None and cw1 is None:
        cw5, cw1 = u.get("cache_creation_input_tokens") or 0, 0
    return (
        (u.get("input_tokens") or 0) * RATES["in"]
        + (u.get("output_tokens") or 0) * RATES["out"]
        + (cw5 or 0) * RATES["cw5"]
        + (cw1 or 0) * RATES["cw1"]
        + (u.get("cache_read_input_tokens") or 0) * RATES["cr"]
    ) / 1e6


SAGE_STATE = re.compile(r"\.sage/")
FRAMEWORK = re.compile(r"(^|/)sage/(core|skills|runtime)/|CLAUDE\.md$|\.claude/")
CODE = re.compile(r"(^|/)(src|tests)/")
TESTRUN = re.compile(r"pytest|python3? -m pytest|python3? -m unittest")
GATE = re.compile(r"sage-verify|sage-check|gates?/|quality|sage-hallucination|sage-spec-check")
RESUME = re.compile(r"manifest\.py[\"' ]+resume")
BOOKKEEP_BASH = re.compile(r"manifest\.py (advance|sync|check)|decisions\.md|conventions\.md")
GIT_RO = re.compile(r"^git (log|status|diff|show|branch|rev-parse)")


def classify(name, inp):
    s = json.dumps(inp)
    path = inp.get("file_path") or inp.get("path") or ""
    cmd = inp.get("command") or ""
    if name in ("mcp__sage-memory__sage_memory_search", "mcp__sage-memory__sage_memory_store",
                "ToolSearch") or name.startswith("mcp__sage"):
        return "memory+toolsearch"
    if name == "Skill":
        return "framework-read"
    if name in ("Agent", "Task"):
        return "subagent-dispatch"
    if name == "Bash":
        if RESUME.search(cmd):
            return "resume-brief"
        if GATE.search(cmd):
            return "gates+verify"
        if TESTRUN.search(cmd):
            return "test-runs"
        if BOOKKEEP_BASH.search(cmd):
            return "sage-bookkeeping"
        if GIT_RO.match(cmd.strip()):
            return "orientation-reads"
        if cmd.strip().startswith("git "):
            return "implement"           # commits, branch work
        if SAGE_STATE.search(cmd) or FRAMEWORK.search(cmd):
            return "framework-read"
        return "implement"
    if name in ("Read", "Grep", "Glob"):
        tgt = path or s
        if FRAMEWORK.search(tgt):
            return "framework-read"
        if SAGE_STATE.search(tgt):
            return "orientation-reads"
        if CODE.search(tgt):
            return "implement"
        return "orientation-reads"
    if name in ("Edit", "Write", "NotebookEdit"):
        if SAGE_STATE.search(path):
            return "sage-bookkeeping"
        if CODE.search(path):
            return "implement"
        return "implement"
    return "other"


def profile(path):
    calls = {}
    order = []
    reported = 0.0
    res_out = 0
    for line in open(path):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            reported += ev.get("total_cost_usd") or 0.0
            res_out += (ev.get("usage") or {}).get("output_tokens") or 0
        if ev.get("type") != "assistant":
            continue
        msg = ev.get("message") or {}
        mid = msg.get("id") or id(msg)
        sub = bool(ev.get("parent_tool_use_id"))
        c = calls.setdefault(mid, {"usage": msg.get("usage") or {}, "cats": [],
                                   "sub": sub, "chars": 0})
        if mid not in order:
            order.append(mid)
        c["usage"] = msg.get("usage") or c["usage"]
        for blk in msg.get("content") or []:
            if blk.get("type") == "tool_use":
                cat = classify(blk.get("name") or "?", blk.get("input") or {})
                if cat not in c["cats"] or True:
                    c["cats"].append(cat)
                c["chars"] += len(json.dumps(blk.get("input") or {}))
            elif blk.get("type") == "text":
                c["chars"] += len(blk.get("text") or "")

    # Input-side raw weight per call (rate errors + event duplication wash out
    # in the normalisation below).
    def in_weight(u):
        cw = u.get("cache_creation") or {}
        cw5 = cw.get("ephemeral_5m_input_tokens")
        cw1 = cw.get("ephemeral_1h_input_tokens")
        if cw5 is None and cw1 is None:
            cw5, cw1 = u.get("cache_creation_input_tokens") or 0, 0
        return ((u.get("input_tokens") or 0) * RATES["in"]
                + (cw5 or 0) * RATES["cw5"] + (cw1 or 0) * RATES["cw1"]
                + (u.get("cache_read_input_tokens") or 0) * RATES["cr"]) / 1e6

    out_cost_total = res_out * RATES["out"] / 1e6
    in_budget = max(reported - out_cost_total, 0.0)
    w_in = {m: in_weight(calls[m]["usage"]) for m in order}
    w_ch = {m: calls[m]["chars"] for m in order}
    sw_in = sum(w_in.values()) or 1.0
    sw_ch = sum(w_ch.values()) or 1.0

    by_cat = defaultdict(lambda: [0.0, 0])
    tok = defaultdict(int)
    for mid in order:
        c = calls[mid]
        cost = in_budget * w_in[mid] / sw_in + out_cost_total * w_ch[mid] / sw_ch
        u = c["usage"]
        tok["cw"] += u.get("cache_creation_input_tokens") or 0
        tok["cr"] += u.get("cache_read_input_tokens") or 0
        if c["sub"]:
            cats = ["subagent-work"]
        elif c["cats"]:
            cats = c["cats"]
        else:
            cats = ["prose-checkpoints"]
        for k in cats:
            by_cat[k][0] += cost / len(cats)
            by_cat[k][1] += 1
    tok["out"] = res_out
    return {"computed": reported, "reported": reported, "by_cat": dict(by_cat),
            "n_calls": len(order), "tok": dict(tok),
            "out_cost": out_cost_total}


if __name__ == "__main__":
    agg = defaultdict(lambda: [0.0, 0])
    tot = rep = 0.0
    ncalls = 0
    tok = defaultdict(int)
    for f in sys.argv[1:]:
        r = profile(f)
        tot += r["computed"]; rep += r["reported"]; ncalls += r["n_calls"]
        for k, v in r["tok"].items():
            tok[k] += v
        for k, (c, n) in r["by_cat"].items():
            agg[k][0] += c; agg[k][1] += n
        print(f"# {pathlib.Path(f).parent.name}/{pathlib.Path(f).name}: "
              f"computed ${r['computed']:.2f} vs reported ${r['reported']:.2f} "
              f"({r['n_calls']} calls)")
    print(f"\nTOTAL computed ${tot:.2f} vs reported ${rep:.2f} "
          f"(calibration {tot/rep*100 if rep else 0:.0f}%) · {ncalls} API calls")
    print(f"tokens: out={tok['out']:,} cache_write={tok['cw']:,} "
          f"cache_read={tok['cr']:,} uncached_in={tok['in']:,}")
    print(f"\n{'category':<22}{'cost':>9}{'share':>8}{'calls':>7}")
    for k, (c, n) in sorted(agg.items(), key=lambda x: -x[1][0]):
        print(f"{k:<22}{c:>9.2f}{c/tot*100:>7.1f}%{n:>7}")
