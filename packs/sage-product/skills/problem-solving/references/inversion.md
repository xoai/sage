# Inversion

Flip your core assumption. If you're stuck, it's often because
you're optimizing within a constraint you haven't questioned.

## The Pattern You're In

The solution feels forced. You've committed to an approach early
and every subsequent decision is constrained by that commitment.
Alternatives feel impossible because you're evaluating them within
the frame of your current approach.

## The Process

### Step 1: State your core assumption

Write down the fundamental premise of your current approach.
Be explicit — the assumption is often invisible because it feels
obvious.

Examples:
- "The user needs to log in before accessing the dashboard"
- "We need to validate all input at the API boundary"
- "The data must be normalized in the database"
- "This needs to be real-time"

### Step 2: Invert it

State the opposite. Don't judge whether it's good — just state it.

Inversions:
- "The user accesses the dashboard without logging in"
- "We don't validate input at the API boundary"
- "The data is denormalized"
- "This is batch/async, not real-time"

### Step 3: Explore the inverted world

For each inversion, ask: "Under what conditions would this be
the RIGHT approach?" Don't dismiss it — find the scenario where
the inversion makes sense.

Examples:
- "Dashboard without login → public dashboards, or magic link
  auth where the URL IS the authentication"
- "No API validation → validation happens at the domain layer,
  not the transport layer. The API just passes data through."
- "Denormalized data → read-heavy workload where joins are the
  bottleneck. Store the computed view, not the source."
- "Batch instead of real-time → user doesn't need instant results,
  they need reliable results. Queue it, process it, notify them."

### Step 4: Evaluate what the inversion reveals

The inversion might not be the answer — but it reveals the SHAPE
of your constraint. Now you can see:
- Was the assumption valid for your actual context?
- Is there a hybrid approach that relaxes the constraint partially?
- Did the inversion reveal a simpler architecture?

### Step 5: Decide

Three possible outcomes:
1. **Original was right** — but now you know WHY, not just by default
2. **Inversion is better** — the assumption was wrong for this context
3. **Hybrid emerges** — relax the constraint in specific cases

## Red Flags

- "There's only one way to do this"
- "We have to do X before Y" (is that actually true?)
- "That won't work" (without exploring why)
- "We've always done it this way"

## When It Works

Inversion works when you're stuck in a local optimum. The
assumption you're operating under was correct in a different
context (previous project, tutorial, best practice article) but
may not apply here.

## When It Doesn't

If the assumption is genuinely constrained by physics, math,
or a hard business requirement (legal compliance, security),
inversion won't help. The constraint is real. Try Simplification
or Scale Testing instead.
