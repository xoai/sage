# Session Continuity

## Resume Protocol

When starting a new session (context reset, new conversation, platform
switch), follow these steps:

### 1. Find the work directory

Scan `.sage/work/` for directories containing `autoresearch.jsonl`.
If multiple exist, present them for user selection.

### 2. Read the living doc

Read `autoresearch.md` for high-level context:
- Original objective
- Key ideas tried
- Current best approach
- Dead ends to avoid

### 3. Read the JSONL tail

Read the last 20 lines of `autoresearch.jsonl`:
- Current iteration number
- Recent trajectory (improving? stuck? crashing?)
- Best metric achieved

### 4. Verify branch state

Check that the git branch matches the JSONL:
```
git log --oneline -1 autoresearch/<slug>
```
The commit hash should match the last `keep` or `baseline` entry
in the JSONL. If it doesn't, the branch was manually modified
between sessions — warn the user.

### 5. Continue

Resume at the next iteration number. The loop picks up as if
the session never ended.

## What to do if state is inconsistent

| Situation | Action |
|-----------|--------|
| JSONL exists but branch doesn't | Branch was deleted. Start fresh with `--force-baseline`. |
| Branch has commits not in JSONL | Someone committed manually. Re-run baseline to sync. |
| `.autoresearch-state.json` exists | Crash during mid-phase. Delete it — the JSONL is authoritative. |
| JSONL is empty | Session was interrupted before baseline. Start fresh. |

## Cross-Platform Resume

Because all state lives in `.sage/work/` (files) and the git branch
(commits), sessions are platform-independent. A session started on
Claude Code can resume on Antigravity and vice versa. The runtime
reads the same files regardless of platform.
