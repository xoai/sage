One more convention, then a small job.

The convention: **library code under `src/` never raises bare builtin exceptions
for validation** — no `ValueError`, no `TypeError` from our own argument checks.
Every validation failure raises our own exception type, so callers can catch one
family. Keep this with the other project conventions — it will matter soon.

The job: add a `ConfigError(Exception)` class to `src/config.py` (docstring:
"Raised for invalid service configuration."), with a test that it is importable.
Commit.
