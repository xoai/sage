#!/usr/bin/env python3
"""
longhorizon_probe.py — does retrieval ever beat rereading, and where?

The multi-session memory claim ("Sage's memory compounds; a bare agent that
rereads its own log breaks down over dozens of sessions") looks like it needs 30
real agentic sessions to test. It doesn't. The real hypothesis is narrower:

    rereading the log stops working once the log outgrows the context window.

So we force the crossover instead of waiting for it. Plant one checkable
constraint, then bury it under a SYNTHETIC work-log grown to a target size, and
ask a question whose default answer is wrong unless the constraint is recalled —
in two conditions:

  reread    the whole synthetic log is in the prompt (what a bare agent does).
  retrieval a short summary + the constraint surfaced verbatim (perfect recall —
            the UPPER BOUND of what a memory system could deliver).

Sweep the log size across (and past) the model's context window and watch where
`reread` recall falls off a cliff while `retrieval` holds flat. That crossover —
if it exists at a realistic size — is the entire empirical case for the memory
layer. If `reread` never breaks, that is the case AGAINST it, delivered in
minutes instead of hours.

Honest limits (this is a fast SCREEN, not a verdict):
  • The padding is synthetic; a real accumulated log is messier.
  • `retrieval` here is PERFECT retrieval. Real MCP retrieval may surface the
    wrong thing, so this measures retrieval's ceiling, not its average.
  • Confirm any crossover it finds with a real multi-session run (the faithful,
    slow path). Screen fast here; confirm there.

Defaults to a small-context model (haiku) precisely so the crossover is
reachable cheaply — "shrink the window" rather than "add sessions".

Usage:
  longhorizon_probe.py --dry-run                 # plan + prompt sizes, no spend
  longhorizon_probe.py                            # default sweep (real calls)
  longhorizon_probe.py --sizes 20000 120000 240000 --runs 2 --model haiku
"""
from __future__ import annotations
import argparse, json, subprocess, sys

# ── the planted constraint: counter-intuitive so the DEFAULT answer is wrong ──
CONSTRAINT = (
    "PROJECT RULE (stated in session 1, binding for the whole project): the ONLY "
    "correct way to read the current time is `clock.now_ms()`. `time.time()`, "
    "`datetime.now()` and `Date.now()` are BANNED by a lint rule and fail CI."
)
TASK = (
    "Now write EXACTLY one line of Python that records the current timestamp into "
    "`event.ts`. Output only the line of code, nothing else."
)
HONORED = "clock.now_ms"                       # correct recall
VIOLATIONS = ("time.time", "datetime.now", "date.now", "time.monotonic")  # the defaults


def grade(text: str) -> bool:
    """Honored iff it uses the mandated call and none of the banned defaults."""
    low = text.lower()
    return HONORED.lower() in low and not any(v in low for v in VIOLATIONS)


def build_log(target_tokens: int) -> str:
    """A synthetic session log ~target_tokens long: the constraint stated once up
    top, then buried under varied, plausible-but-irrelevant work-log entries."""
    header = "=== PROJECT LOG (session 1) ===\n" + CONSTRAINT + "\n\n=== later work ===\n"
    # ~4 chars/token; each entry ~30 tokens. Vary content so it isn't trivially
    # greppable filler the model can pattern-match past.
    approx_chars = target_tokens * 4
    entries, i, size = [], 0, len(header)
    topics = ["auth", "billing", "search", "ingest", "cache", "webhooks", "reports",
              "migrations", "ratelimit", "telemetry", "uploads", "notifications"]
    while size < approx_chars:
        t = topics[i % len(topics)]
        line = (f"- entry {i}: refactored the {t} module; renamed handlers, tidied "
                f"imports, added a regression test for the {t} edge case #{i*7 % 991}.\n")
        entries.append(line); size += len(line); i += 1
    return header + "".join(entries)


def prompt_reread(log: str) -> str:
    return (f"You are resuming a project. Here is the full log so far:\n\n{log}\n\n{TASK}")


def prompt_retrieval() -> str:
    # Constant, tiny: a summary line + the one retrieved fact. No buried needle.
    return ("You are resuming a project. Summary of prior work: many modules were "
            "refactored with added tests.\n\nRETRIEVED PROJECT MEMORY:\n" + CONSTRAINT
            + "\n\n" + TASK)


def call_model(prompt: str, model: str, budget: float) -> tuple[str, float]:
    """One non-interactive, no-tools query. Prompt via stdin (histories are far
    too big for a command-line argument)."""
    cmd = ["claude", "-p", "--output-format", "json",
           "--permission-mode", "bypassPermissions", "--max-budget-usd", str(budget)]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        return (f"__ERROR__ rc={proc.returncode} {proc.stderr.strip()[:200]}", 0.0)
    try:
        obj = json.loads(proc.stdout)
        return (str(obj.get("result", "")), float(obj.get("total_cost_usd") or 0.0))
    except (json.JSONDecodeError, ValueError):
        # Fall back to raw stdout if the CLI didn't emit clean JSON.
        return (proc.stdout.strip(), 0.0)


def tok(n: int) -> str:
    return f"{n/1000:.0f}k" if n < 1_000_000 else f"{n/1_000_000:.2f}M"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", type=int, nargs="+",
                    default=[10000, 40000, 90000, 150000, 220000, 320000],
                    help="synthetic log sizes in tokens to sweep")
    ap.add_argument("--runs", type=int, default=2, help="queries per (size, condition)")
    ap.add_argument("--model", default="haiku",
                    help="small-context model makes the crossover cheap to reach")
    ap.add_argument("--budget-usd", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true", help="plan only; spend nothing")
    ap.add_argument("--out", default=None, help="write raw results JSON here")
    args = ap.parse_args()

    print(f"long-horizon crossover probe — model={args.model} runs={args.runs}")
    print(f"sizes: {', '.join(tok(s) for s in args.sizes)} tokens\n")

    if args.dry_run:
        for s in args.sizes:
            log = build_log(s)
            print(f"  {tok(s):>6}: reread prompt ≈ {len(prompt_reread(log))//1000}k chars "
                  f"(~{len(prompt_reread(log))//4//1000}k tok) · retrieval prompt "
                  f"{len(prompt_retrieval())} chars (constant)")
        n = len(args.sizes) * 2 * args.runs
        print(f"\nwould make {n} model call(s) ({len(args.sizes)*args.runs} reread + "
              f"{len(args.sizes)*args.runs} retrieval). Nothing spent.")
        return 0

    rows, raw = [], []
    for s in args.sizes:
        log = build_log(s)
        prompts = {"reread": prompt_reread(log), "retrieval": prompt_retrieval()}
        rec = {}
        for cond, p in prompts.items():
            hon = cost = 0.0; errs = 0
            for _ in range(args.runs):
                text, c = call_model(p, args.model, args.budget_usd)
                cost += c
                if text.startswith("__ERROR__"):
                    errs += 1
                elif grade(text):
                    hon += 1
                raw.append({"size": s, "cond": cond, "honored": grade(text) if not
                            text.startswith("__ERROR__") else None, "cost": c})
            rec[cond] = (hon, args.runs, cost, errs)
        rows.append((s, rec))
        rr = rec["reread"]; rt = rec["retrieval"]
        print(f"  {tok(s):>6}  reread {rr[0]}/{rr[1]}"
              f"{' (' + str(rr[3]) + ' err)' if rr[3] else ''}  "
              f"retrieval {rt[0]}/{rt[1]}  "
              f"| reread ${rr[2]:.2f} vs retrieval ${rt[2]:.2f}")

    # TWO reread failures that the instrument must NOT conflate — one is about the
    # model, the other is about the API:
    #   recall miss : reread RAN (errs==0) but lost the constraint (hon<runs).
    #                 THIS is the memory layer's real case — the model forgot.
    #   window wall : reread could not be SENT at all (errs>0) — the log exceeded
    #                 the context window. Retrieval becomes MANDATORY, not "better".
    # (An earlier version of this file scored the window wall as a recall miss.
    #  That is the "truncation grades as failure" trap; keep them separate.)
    recall_miss = next((s for s, r in rows
                        if r["reread"][3] == 0 and r["reread"][0] < r["reread"][1]), None)
    window_wall = next((s for s, r in rows if r["reread"][3] > 0), None)
    ok = [(s, r) for s, r in rows if r["reread"][3] == 0 and r["reread"][0] == r["reread"][1]]
    max_ok = max((s for s, _ in ok), default=None)

    print("\n" + ("─" * 48))
    if recall_miss is not None:
        print(f"RECALL CROSSOVER near {tok(recall_miss)} tok: reread RAN but lost the "
              f"constraint while retrieval held — the model forgot. This is the memory "
              f"layer earning its keep. Confirm with a real multi-session run.")
    else:
        print("NO recall degradation: wherever the log FIT, rereading recalled the "
              f"buried constraint as well as retrieval did"
              + (f" (verified to {tok(max_ok)} tok)." if max_ok else "."))
    if window_wall is not None:
        print(f"WINDOW WALL at {tok(window_wall)} tok: past here the log no longer FITS "
              f"the model's context window, so rereading is impossible — some form of "
              f"retrieval/summarisation is mandatory there, but that is a capacity "
              f"limit, not the model 'forgetting'.")
    # Even where reread WORKS, its cost grows with the log while retrieval stays flat.
    if ok:
        s_big, r_big = ok[-1]
        rr, rt = r_big["reread"][2], r_big["retrieval"][2]
        if rt > 0:
            print(f"COST: at the largest size that fit ({tok(s_big)} tok), reread cost "
                  f"${rr:.2f} vs retrieval ${rt:.3f} — ~{rr/rt:.0f}x. Rereading recalls "
                  f"fine; what it is not, at scale, is cheap.")

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"model": args.model, "runs": args.runs, "raw": raw}, fh, indent=2)
        print(f"raw results → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
