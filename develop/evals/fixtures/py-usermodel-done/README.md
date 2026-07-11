# py-usermodel-done

The same `User` model as `py-usermodel`, but with `get_full_name()` already
implemented and tested.

It is a separate fixture on purpose. E8 needs a cycle whose work is FINISHED, so
that closing it is the only act left — and E4 needs the same file with the method
ABSENT, because E4's whole assertion is that the agent adds it. Sharing one fixture
would have made E4 pass without an agent, which the null-agent guard duly caught.
