# Example: Bundle Size Reduction

## Setup

1. Have a JS/TS project with `npm run build` producing `dist/main.js`
2. Copy `brief.md` and `autoresearch.sh` to `.sage/work/YYYYMMDD-bundle/`
3. Make the verify script executable: `chmod +x autoresearch.sh`

## Run

```
/autoresearch
```

Or directly:
```bash
python -m core.autoresearch run --brief .sage/work/YYYYMMDD-bundle/brief.md
```

## What the agent will try

Typical winning patterns for bundle size reduction:
- Lazy-load routes and heavy components
- Tree-shake unused exports
- Replace heavy utilities with lighter alternatives
- Split vendor chunks
- Remove dead code paths

## Expected trajectory

Starting at ~340KB, typical sessions reach target in 15-30 iterations.
First 5 iterations usually capture the biggest wins (lazy-loading, tree-shaking).
Later iterations are diminishing returns.
