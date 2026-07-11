# Gate regression tests

Deterministic tests for the four gate scripts in `core/gates/scripts/`.

```bash
bash develop/validators/gates/run-gate-tests.sh            # all cases
bash develop/validators/gates/run-gate-tests.sh --only G1  # one case
bash develop/validators/gates/run-gate-tests.sh --verbose  # show gate output
```

`SAGE_GATES_DIR=<dir>` points the harness at a different copy of the scripts.
It used to be aimed at the plugin's committed mirror, which had to behave
identically; that mirror is gone (P3-T2b) and the plugin's copies are generated
from the scripts tested here — `build_plugin.py --check` asserts they land
byte-identical, so there is no second implementation left to test.

## The exit contract these tests pin

| Exit | Meaning | Final line |
|---|---|---|
| 0 | verified pass | `✅ PASS — …` |
| 1 | verified fail | `❌ FAIL — …` |
| 2 | unverifiable — nothing to check, or the tooling is absent | `⚠️ UNVERIFIABLE — …` |

Exit 2 is the state the gates previously lacked. A caller must never treat it
as a pass; workflow prose offers `[P] Proceed unverified / [F] Fix
verification setup` instead.

## Case outcomes

- **PASS / FAIL** — the gate behaved, or did not behave, as declared.
- **SKIP** — a tool the case needs is absent. Cases skip rather than fail so
  the harness stays useful offline. CI installs `pytest` and `tsc`, but **not**
  playwright, so `G11c` (Gate 6's pass path) skips there and is only exercised
  by maintainers who have a browser installed. `G11b` is its mirror image: it
  runs *only* when playwright is absent.
- **XFAIL** — the case documents behavior that is currently *wrong* and is
  scheduled to be fixed. The reason names the task that fixes it.
- **XPASS** — an `xfail` case started passing. The harness treats this as a
  failure: the fix landed, so the marker must be deleted. This is what keeps
  the markers from rotting into permanent excuses.

## Adding a case

Regression-first: every gate bug gets a numbered fixture here **before** the
fix, marked `--xfail` with the reason and the fixing task. The fix then flips
it to PASS and deletes the marker in the same commit.

Assert on more than the exit code. Several of these gates used to reach `PASS`
having examined nothing at all — `G2` and `G10a` therefore assert on the
"Checked N…" line and the extracted filename, so they cannot pass vacuously.
An exit-code-only assertion would have gone green against the broken gate.
