New job.

Add `group_by_status(items)` to `src/config.py`. It takes a list of dicts, each
of which has a `"status"` key, and returns a mapping from each status to the list
of items carrying it.

Annotate it fully — parameters and return type. Write a test, then commit.
