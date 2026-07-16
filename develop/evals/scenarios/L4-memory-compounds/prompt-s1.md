Before we start any work, a constraint you need to know about this project.

Our deploy image is pinned to **Python 3.8** and ops will not upgrade it this
quarter. So all new code has to be 3.8-compatible. Concretely, in type
annotations:

- Use `typing.List`, `typing.Dict`, `typing.Optional` — import them from `typing`.
- NEVER use the builtin-generic syntax (`list[str]`, `dict[str, int]`). That is
  3.9+, and it raises `TypeError` at import time on 3.8.
- NEVER use the `X | Y` union syntax. That is 3.10+.

This has bitten us in production twice. It matters.

Acknowledge it, and make sure it is not lost — we will be working in this repo
for a while.
