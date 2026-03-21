# Simplification

Find one insight that eliminates multiple components. The best
solutions don't add — they remove.

## The Pattern You're In

You've been adding cases, conditions, branches. Each new requirement
adds another `if`. The code works but it's fragile, hard to test,
and growing in complexity. You sense there's a simpler way but
can't see it because you're too deep in the details.

## The Process

### Step 1: List what you're managing

Write down every special case, condition, branch, or exception
your current approach handles. Don't explain them — just list them.

Example:
```
- Admin users skip rate limiting
- Free users get 10 requests/min
- Pro users get 100 requests/min
- Enterprise users get unlimited
- API keys have different limits than session tokens
- Webhooks bypass all rate limiting
- Internal services use a separate limit pool
```

### Step 2: Ask "What do these have in common?"

Look for the pattern underneath. These aren't seven separate things —
they're variations of one thing. What is that one thing?

Example insight: "Everything has a rate limit. Some are just set
to infinity."

### Step 3: Test the unifying insight

If the insight is true, what can you REMOVE? List the components,
conditions, or code paths that become unnecessary.

Example: "If everything has a rate limit (including infinity),
I don't need special cases for admin, enterprise, webhooks, or
internal services. I just need a lookup: identity → limit."

### Step 4: Validate

Does the simplified approach handle ALL the original cases? Walk
through each item from Step 1 and confirm.

If one case doesn't fit, either:
- The insight needs refinement (go back to Step 2)
- That case is genuinely different (keep it as the one exception)

## Red Flags

- "Just one more condition" — you've said this 3+ times
- The test file is longer than the implementation
- You can't explain the logic in one sentence
- New requirements keep breaking existing cases

## When It Works

Simplification works when the complexity comes from treating
related things as unrelated. The insight is always: "these are
all instances of the same pattern."

## When It Doesn't

If the cases are genuinely unrelated (different domains, different
data types, different users), forcing them into one pattern creates
a false abstraction. In that case, try Inversion or Scale Testing.
