# Evals — does Sage actually change agent behaviour?

Sage claims that mechanically-enforced process makes an agent skip fewer tests,
invent fewer APIs, and claim success less often than it earns it. That claim was
prose for three phases. This harness makes it a number.

The design is one comparison, repeated: **the same scenario, the same prompts, the
same graders — run once in a project with Sage initialized and once without.** The
only variable is `sage init`. The delta is the claim.

```bash
# Validate every scenario and grader. No model calls, costs nothing. This is CI.
python3 develop/evals/run_evals.py --offline-check

# See what a real run would do, spend nothing.
python3 develop/evals/run_evals.py --dry-run

# A real run (needs an authenticated Claude Code; costs money).
python3 develop/evals/run_evals.py --scenario E1
python3 develop/evals/run_evals.py --runs 3 --report      # the baseline
```

## How a run works

1. The scenario's fixture is copied to a temp dir and `git init`-ed with a seed
   commit. The history is load-bearing: several graders read commit *order*.
2. In the `sage` condition only, `sage init --preset base` runs. `SAGE_HOME` points
   at this checkout, so the eval measures the Sage in the tree under test — not
   whatever the developer has installed globally.
3. The prompts are played into a headless agent session, in one conversation.
4. The final workspace and the full transcript are graded.

## Graders are deterministic, and that costs us something

No LLM judge (13-§30 R73). A grader that asks a model whether the model did well
is neither reproducible nor free, and it is the exact species of self-assessment
Sage exists to distrust. So every check is a fact: a file exists, a commit
precedes another commit, a gate exits 0, a command actually ran.

**This constraint genuinely limits coverage, and the limit should be stated rather
than hidden.** The six pressure documents in `develop/validators/pressure/` hold 33
sub-scenarios between them. They were written to be read aloud to an agent and
scored by a human, so they contain no fixtures and mandate no literal strings —
every "expected" is a paraphrase of desired *reasoning*. A large share of them
cannot be graded mechanically at all, because **the compliant and the
non-compliant agent emit identical code.** In "agent ignores constitution" #4, both
agents ship the same public webhook endpoint; the only difference is whether the
agent said why. There is no file to stat and no exit code to read.

So each scenario here is built from the sub-case in its pressure doc that leaves a
**mechanical trace**, and the scenario's `rationale` records which one and why. What
that leaves uncovered is real: the reasoning-only sub-cases stay in the pressure
docs as manual tests until a judge lands (13-§32, explicitly future work). An eval
suite that quietly graded those with a model and called the result deterministic
would be worse than one that admits the gap.

## Layout

```
run_evals.py     orchestrator, drivers, reporting
graders.py       the deterministic grader library
scenarios/<id>/  scenario.json + prompt-N.md
fixtures/<name>/ seed projects, copied per run
results/         gitignored — results.json, summary.md
```

A scenario is a fixture, an ordered list of prompts, and a list of checks. Adding
one means adding a directory; `--offline-check` then proves it is well-formed and
that every grader it names exists, so a typo fails CI instead of failing a paid run
twenty minutes in.

## Flake policy

Agents are stochastic. `--runs 3` runs each scenario/condition three times and a
scenario passes on a **majority**, not on a lucky green. Raw runs stay in
`results.json` so nobody has to trust the summary.

## Cost

A full run makes real model calls. `--max-budget-usd` caps each session (default
$2). The CI job is `--offline-check` only — per-PR evals would bill the project for
every typo fix.
