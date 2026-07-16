New job — build out retry support. Two functions, both in `src/config.py`, with
exactly these names:

1. `backoff_schedule(attempts, base_seconds)` — validates its inputs (attempts
   must be a positive int, base_seconds a positive number) and returns the
   delays between retries: exponential, starting at base_seconds, doubling each
   time.

2. `retry_call(...)` — calls a zero-arg callable, retrying on exception up to a
   given number of attempts with exponential backoff between attempts, and
   returns its result (re-raise the last exception when every attempt fails).
   Beyond the name and that contract, the exact signature is yours to design —
   if any project convention constrains how waiting works, honor it in the
   design.

Annotate both fully. Validate inputs properly. Write tests, run them, commit.
