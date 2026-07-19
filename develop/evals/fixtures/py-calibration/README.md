# py-calibration

A wallet service with a spec (`docs/spec.md`), an implementation, and a
green happy-path suite. Run the tests with `python3 -m pytest`.

This fixture exists for the review-loop calibration (RR-27): the
implementation contains PLANTED defects — do not "fix" this fixture.
The answer key and scorer live in `develop/validators/review/calibration/`.
