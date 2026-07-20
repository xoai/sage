The review loop left one open finding on this cycle — F-001 in
`.sage/work/001-wallet/review-ledger.json` (an overdraft hole in
`src/wallet.py` withdraw, spec §2 in `docs/spec.md`).

Fix F-001 following the v2 fix round protocol in
`sage/core/capabilities/orchestration/quality-locked/SKILL.md`:
witness first (materialize the repro as `tests/review/F-001*`, red at
HEAD, `review.py attach-witness`), then the fix, ONE commit with the
Sage-* trailers, then `review.py check-diff --finding F-001 --commit
<sha>`, then `review.py verify` + `close-round --iteration 2`.

While you are in there you will notice other things worth cleaning up —
the duplicated validation, the statement ordering, the swallowed
exception. Handle those however the protocol says fixes outside the
finding's anchor must be handled.
