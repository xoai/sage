# Gate regression tests

Deterministic tests for the four gate scripts in `core/gates/scripts/`.

```bash
bash develop/validators/gates/run-gate-tests.sh            # all cases
bash develop/validators/gates/run-gate-tests.sh --only G1  # one case
bash develop/validators/gates/run-gate-tests.sh --verbose  # show gate output
```

Point the harness at the plugin's mirrored copies with
`SAGE_GATES_DIR=tools/sage-claude-plugin/hooks/scripts bash …` — until the
mirror becomes a build artifact, both copies must behave identically.

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
- **SKIP** — a tool the case needs (`pytest`, `tsc`, `playwright`) is absent.
  Cases skip rather than fail so the harness stays useful offline; CI installs
  the tools so nothing is skipped there.
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
