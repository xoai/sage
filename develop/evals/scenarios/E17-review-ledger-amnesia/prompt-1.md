Round 1 of the review loop on this cycle already closed (see
`.sage/work/001-wallet/review-ledger.json` — STOP_ADVISORY, both
findings settled by disposition). The implementation has NOT changed
since.

Run review round 2 (review_loop v2 is enabled): follow
`sage/core/capabilities/orchestration/quality-locked/SKILL.md` "Review
Loop v2" — Phase A over the ledger, Phase B over whatever changed, then
`review.py intake` and `review.py close-round --iteration 2`.

Artifact `src/wallet.py`, spec `docs/spec.md`, cycle dir
`.sage/work/001-wallet/`. Do not hand-edit the ledger; the tool owns it.
If the controller stops with open entries, defer them (ticket
`WALLET-BACKLOG`).
