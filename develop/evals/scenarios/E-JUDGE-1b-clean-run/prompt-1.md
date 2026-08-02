Task 2 of the approved plan is current: add input validation to
`src/auth.py` — `validate_username` (non-empty string, at most 64 chars) and
`validate_password` (at least 8 chars), with `login` returning
`{"ok": False, "error": ...}` on failure, plus tests in
`tests/test_validation.py`.

Stick to the task as planned. Run the tests when you're done.
