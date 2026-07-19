Run the quality-locked review loop (review_loop v2, already enabled in
.sage/config.yaml) over this implementation against its spec.

- Cycle dir: `.sage/work/001-wallet/` (the ledger goes there as
  `review-ledger.json`).
- Artifact: `src/wallet.py`. Spec: `docs/spec.md`.
- Follow `sage/core/capabilities/orchestration/quality-locked/SKILL.md`
  "Review Loop v2" exactly: dispatch the reviewer with the v2 output
  contract from the quality-review capability, intake its findings with
  `review.py`, close each round with `review.py close-round`, and do what
  the controller says — fix on CONTINUE (witness-first, one finding one
  commit with Sage-* trailers, `review.py check-diff` after each fix
  commit), disposition-and-stop on a STOP verdict.

Defer (ticket ref: `WALLET-BACKLOG`) anything the controller leaves open
at a STOP. Do not hand-edit the ledger; the tool owns it.
