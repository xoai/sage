# Scale Testing

Test your solution at extreme scales to expose fundamental design
issues that are invisible at normal scale.

## The Pattern You're In

Your solution works in development, with test data, or at small
scale. But something feels fragile. You suspect it won't survive
production load, real data volumes, or edge cases — but you can't
articulate exactly what will break.

## The Process

### Step 1: Identify your scale dimensions

Every system has dimensions that can vary. List yours:

- **Data volume** — rows, records, file size, payload size
- **Concurrency** — simultaneous users, parallel requests, threads
- **Time** — duration, frequency, latency requirements
- **Variety** — input types, edge cases, character sets, locales
- **Depth** — nesting levels, dependency chains, call stack depth

### Step 2: Test at 1000x

For each dimension, ask: "What happens if this is 1000x larger
than my test case?"

Examples:
- "My test has 10 records. What happens with 10,000?"
- "I test with 1 user. What happens with 1,000 concurrent?"
- "My test input is 100 bytes. What happens with 100KB?"
- "The test runs once. What happens if it runs every second for a week?"

Don't just think about it — actually trace the code path at 1000x.
Where does memory grow? Where do queries slow down? Where do
timeouts hit?

### Step 3: Test at 1/1000th

For each dimension, ask: "What happens at the minimum?"

Examples:
- "What if there are zero records?"
- "What if the input is empty?"
- "What if this runs once per year?"
- "What if the user has no permissions at all?"

Minimum-scale testing reveals different bugs than maximum: null
handling, empty state UI, cold-start performance, degenerate cases.

### Step 4: Test at the boundary

For each dimension, find the threshold where behavior changes:

- "At what record count does the query exceed 1 second?"
- "At what concurrency level does the connection pool exhaust?"
- "At what payload size does the request timeout?"

Boundaries expose design assumptions that aren't documented. They
become your actual system limits.

### Step 5: Design for the real range

Now you know three things:
1. What breaks at scale (Step 2)
2. What breaks at minimum (Step 3)
3. Where the boundaries are (Step 4)

Design the solution for the ACTUAL expected range, with known
behavior at the boundaries. Don't optimize for 1000x if your real
max is 10x — but DO handle the boundary gracefully.

## Red Flags

- "Should scale fine" — without evidence
- "Works on my machine" — with synthetic data
- "We can optimize later" — for fundamental design choices
- "The database handles that" — it doesn't, always

## When It Works

Scale testing works when you suspect hidden assumptions about
data volume, concurrency, or time. It's especially useful for:
- Database query design
- API rate limiting and pagination
- Caching strategies
- Queue and worker architectures
- File processing pipelines

## When It Doesn't

If the problem is logical (wrong algorithm, wrong approach), scale
testing won't help — the solution is wrong at any scale. Try
Inversion or Minimal Reproduction instead.
