# Minimal Reproduction

Strip the problem to the smallest possible case that still
exhibits the issue. This is the single most effective debugging
technique and the default when you don't know which technique
to apply.

## The Pattern You're In

You can't isolate the cause because there's too much context.
The bug only appears in the full system. Multiple components
interact and you can't tell which one is responsible. Or you've
been staring at the code for too long and can't see the issue
because of all the surrounding complexity.

## The Process

### Step 1: Reproduce the failure

Before reducing, confirm you can trigger the issue reliably.
If the failure is intermittent, note the conditions that make it
more likely (timing, data, load, order of operations).

Write down:
- Exact steps to reproduce
- Expected behavior
- Actual behavior
- Error message or observable symptom

### Step 2: Remove half the context

Binary search for the cause. Take the failing system and remove
roughly half of the components, configuration, or data.

Does the issue still occur?
- **Yes** → The cause is in the remaining half. Remove half again.
- **No** → The cause was in what you removed. Put it back,
  then remove the OTHER half of what remains.

### Step 3: Keep removing until you can't

Each round removes half of the remaining context. After 4-5
rounds, you should have a minimal case: the smallest setup that
still reproduces the issue.

A good minimal reproduction:
- Has the fewest possible files, functions, or components
- Uses the simplest possible data
- Has no unrelated configuration
- Can be run in isolation (no full system needed)

### Step 4: The cause is now visible

With a minimal reproduction, the cause is usually obvious. The
reproduction IS the diagnosis — it shows exactly which interaction,
data, or condition triggers the failure.

If the cause is STILL not obvious with a minimal reproduction,
the reproduction isn't minimal enough. Keep removing.

### Step 5: Fix and verify

Fix the issue in the minimal reproduction first. Confirm it works.
Then apply the same fix to the full system.

If the fix works in minimal but not in full, there's a SECOND
issue interacting with the first. Create a new minimal reproduction
for the remaining failure.

## Techniques for Reducing

**For code:** Comment out functions, modules, middleware. Replace
complex dependencies with stubs. Hardcode values instead of
computing them.

**For data:** Reduce the dataset. Use 1 record instead of 1000.
Simplify the schema. Remove optional fields.

**For configuration:** Use defaults. Remove environment variables.
Disable features. Strip middleware, plugins, extensions.

**For tests:** Extract the failing test into a standalone script
that doesn't depend on the test framework's setup.

## Red Flags

- "It only happens in production" — can you reproduce the
  production conditions locally? (data, config, load)
- "It's too complex to isolate" — this means the reproduction
  isn't minimal enough yet
- "I need the full system running" — which parts of the full
  system? Start removing them
- "It's intermittent" — timing-dependent issues often become
  reliable with minimal reproduction (fewer race conditions)

## When It Works

Minimal reproduction works for almost any problem. It's the
default technique when you don't know what's wrong. It works
especially well for:
- Integration bugs (which component is responsible?)
- Data-dependent failures (which data triggers it?)
- Configuration issues (which setting matters?)
- Race conditions (fewer components = fewer timing variables)

## When It Doesn't

If the problem is architectural (wrong approach, not wrong
implementation), minimal reproduction finds the symptom but not
the design issue. In that case, apply Inversion or Simplification
after you've confirmed what the symptom is.
