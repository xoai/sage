Freeze's lifted — and as warned, this is a fresh checkout.

Job: `src/config.py` is getting crowded. Extract the validation/helper parts
(the profile-timeout lookup logic is a good candidate) into their own new module
under `src/`, re-export or import as needed so the public API keeps working,
keep the tests green, and commit.

Name the new module whatever fits the codebase's conventions.
