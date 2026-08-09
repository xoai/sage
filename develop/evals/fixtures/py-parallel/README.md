# py-parallel

A five-module service skeleton whose modules are deliberately separable:
`models` (shared types), `auth`, `session`, `billing`, `report`, plus a
`service` wiring seam that does not exist yet. Built for the E-PAR
scenarios — plans over this fixture can declare genuinely disjoint
`Files:` sets per task, which is the property the parallel-lane
machinery schedules on and the graders check.

Baseline: `python3 -m pytest -q` is green (one smoke test importing
every module).
