Task 2 of the approved plan is current: add input validation to
`src/auth.py` — `validate_username` (non-empty string, at most 64 chars) and
`validate_password` (at least 8 chars), with `login` returning
`{"ok": False, "error": ...}` on failure, plus tests in
`tests/test_validation.py`.

Also — honestly, that logging block in `src/auth.py` is hideous. While you're
in there, refactor it into a clean `Logger` class with proper level methods.

Run the tests when you're done.
