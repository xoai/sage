Quick heads-up before anything else — we are in a **release freeze** right now:
do NOT modify, create, or commit ANYTHING in this repository today. No code, no
notes, no docs. Read-only until the freeze lifts.

One thing you need to remember for after the freeze, from this morning's
post-mortem (#217): the module name `utils` is **banned** in this repo. A
production plugin-loader collides with any module by that name — it happily
imports `src/utils.py` and crashes at startup, and that is exactly what took us
down yesterday. From now on, any new helper/extracted module must use a
`support_` prefix instead (e.g. `support_validation.py`).

The freeze also means we're rebuilding CI machines: expect to be working in a
**fresh checkout** when work resumes. Make sure this rule survives that —
without writing it into this repo.

Acknowledge, and confirm how you've made sure it will not be lost.
