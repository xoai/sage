# Authoring a skill (or a workflow, or a hook, or a gate)

**The rule: write the scenario before you write the skill.**

Not after. Not "once it settles down". Before — because a scenario written
afterwards is a scenario written to pass, and you will not notice you have done it.

> Adapted from [Superpowers](https://github.com/obra/superpowers)' `writing-skills`
> (MIT), which applies a TDD cycle to documentation: state the failure the doc must
> prevent, prove the failure happens, then write the doc, then prove it stopped.
> Sage's version drops the drills — the harness is the drill — and grades the
> workspace instead of the wording.

---

## Why this rule exists

v1.2.0 was cut after the eval suite falsified a claim the README had been making for
months. The lesson people took from that was "we needed an eval suite." That was not
the lesson. **We had built one.** The lesson was that a suite only bites when
somebody remembers to point it at the thing they changed — and remembering is
culture, and culture is the first thing you lose.

So it stopped being a matter of remembering. `coverage.yaml` gives every behavioral
surface in Sage a row, and CI fails a PR that changes a mapped surface without
touching a covering scenario. There is no third option and no blank.

Then the context diet proved the rule's harder half. The entire test-first prose
block was deleted from the always-loaded layer — and test-first still measured 3/3
against a bare agent's 0/3. **The prose had never been doing the work. The hook
was.** Nobody could have known that by reading it. The only reason it is known now
is that a scenario existed to ask.

That is the point of writing the scenario first. Not to prove your skill works — to
find out whether it does anything at all.

---

## The loop

### 1. Name the failure

Not the feature. The **failure**. A skill exists because an agent does something
wrong without it, and if you cannot say what that is in one sentence, you are not
ready to write the skill.

> *"Asked to change one constant under pressure, the agent edits it and ships an
> untested value."* — the test-first scenario

Write it in the scenario's `rationale`. Every scenario in `develop/evals/scenarios/`
carries one, and they are long on purpose: the rationale is where the next person
learns what the scenario is *for*, and what it deliberately does **not** measure.

### 2. Prove the failure happens

Run the scenario **before** the skill exists, or with it disabled. If the unaided
agent passes anyway, **stop.** You have not found a failure; you have found a thing
agents already do. Writing a skill for it costs context on every turn and buys
nothing, and the eval will faithfully report "Sage works" forever.

This is the check that would have caught the eager layer's test-first prose years
earlier.

### 3. Make the check fail on a null agent

`run_evals.py --offline-check` grades every scenario against an agent that did
**nothing at all**, in every condition it declares. Two ways to fail it, and the
first real baseline run hit both:

- **A check the fixture already satisfies.** The scenario then passes in every
  condition, forever, and reads as evidence.
- **A check the fixture already fails**, for reasons that have nothing to do with the
  agent. The suspect-package scenario's hallucination gate scanned the whole
  workspace — including Sage's own vendored framework — found "phantom imports" in
  Sage's example code, and scored sage 0/3 against bare 3/3. A clean *"Sage makes the
  agent worse"* result, manufactured entirely by the harness.

### 4. *Now* write the skill

### 5. Run it again, in both conditions

The number that means anything is the **delta**. `sage 3/3, bare 3/3` is not a win;
it is a skill you can delete. And if bare wins, **bare wins** — publish it. The
v1.2.0 baseline falsified a README claim and shipped the falsification.

### 6. Map it in `coverage.yaml`

```yaml
  skill-my-thing:
    path: skills/my-thing/SKILL.md
    kind: skill
    covered-by: [my-thing-under-pressure]
```

or, honestly:

```yaml
    uncovered: >
      Nothing measures this. It is prose, and prose that has never been
      tested against a bare agent is a hypothesis.
```

**`uncovered:` is a legitimate answer.** 52 of 94 surfaces carry one. Writing it
costs nothing today and is visible forever; writing a scenario costs a day and a
model run. What is *not* legitimate is a blank — the validator rejects a surface
with neither, and rejects one with both.

---

## What the validator enforces

`develop/validators/check-eval-coverage.py`, on every PR:

| Rule | What fails |
|---|---|
| **Complete** | A behavioral surface with no row. New skill, no entry → red. |
| **Truthful** | A row with both `covered-by` and `uncovered`, or neither. |
| **Changed-surface** | You changed a mapped surface and touched none of its covering scenarios. |

### The escape, and its price

A genuinely behavior-neutral edit — a typo, reflowing a paragraph, rewording that
changes no rule — passes with `#eval-neutral` in the **commit body**.

It is **logged, not waived silently.** That is the whole design. An escape hatch
nobody can see is just a hole, and the reviewer's question — *"is this really
neutral?"* — is one a human has to ask. Use it when it is true. It is a claim you are
making, in the commit, with your name on it.

---

## Graders: the instrument is not above suspicion

**A grader is code. It has bugs like code. Only reality finds them.**

Of five apparent failures in the v1.3.0 eval run, **four were harness bugs.** The
suite was wrong, not the agent. So:

- **Deterministic only.** Files, git order, gate exit codes, transcript markers. No
  LLM judges — results must be reproducible and free.
- **Pin both directions.** Every grader in `test_graders.py` is tested for what it
  passes *and* what it fails. A grader that is wrong in the **lenient** direction
  converts "the agent misbehaved" into "Sage works", which is the exact claim the
  suite exists to test.
- **Instrument the mechanism, not the outcome.** Twice, a naive check would have
  reported success when *nothing had happened at all*: codex's read-only sandbox
  blocked an edit (recorded as a veto), and opencode's crashed runs left the file
  unchanged (same). **Nothing-happened and correctly-blocked are indistinguishable
  unless you look at the mechanism.** The memory-recall scenario asserts a memory
  tool was actually *called*, precisely so a pass cannot be a reread wearing memory's
  coat.
- **Watch the needle.** The resume scenario greps session 2's diff for `MAX_RETRIES = ` — with the
  trailing space. Without it, the needle is a substring of `MAX_RETRIES == 3`, which
  is what a perfectly correct new test asserts. The naive grader fails the very agent
  it exists to pass. One character. There is a unit test holding it in place.

---

## Long-horizon surfaces

If your skill's value is a claim about **memory, resumption, or anything surviving a
context window**, a single-session scenario cannot test it. The agent that finishes
the work is the agent that started it, and it simply remembers.

Declare `sessions` instead (see `L1-resume-fidelity`, `L2-memory-recall`). Each
session is a fresh model context against one persistent workspace: session 2 knows
only what session 1 left on disk. Scope your checks with `"session": "s2"`, or a
marker session 1 legitimately produced will satisfy a check about session 2.

---

## Checklist

- [ ] The failure is named in one sentence, in the rationale
- [ ] The unaided agent actually exhibits it
- [ ] `--offline-check` green: fails on a null agent, in every declared condition
- [ ] Both conditions run, and the **delta** is the result
- [ ] Graders are deterministic and pinned in both directions
- [ ] `coverage.yaml` names the scenarios — or admits, in prose, that nothing does
- [ ] What the scenario does **not** measure is written down
