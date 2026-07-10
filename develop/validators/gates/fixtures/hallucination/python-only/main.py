"""Fixture for G4b — a Python file, no type-checker installed.

Gate 4 has no import analysis for Python, so with neither pyright nor mypy
available it has examined nothing and must exit 2 (UNVERIFIABLE), not 0.
"""


def add(a, b):
    return a + b
