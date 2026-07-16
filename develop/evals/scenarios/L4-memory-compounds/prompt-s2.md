Two things today.

First, a team convention you need to know, decided after a production incident:
**helpers never sleep.** Any retry/backoff helper must COMPUTE the delay and
return it — the CALLER decides whether and how to wait. `time.sleep` inside
library code under `src/` is banned. Make sure this is not lost either.

Second, a small unrelated job: `POOL_SIZE` in `src/config.py` has no test
coverage. Add a test asserting its current value, and commit.
