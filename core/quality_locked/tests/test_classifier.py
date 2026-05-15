"""Tests for the review output classifier."""

from core.quality_locked.classifier import classify


def test_all_none():
    output = """
VERDICT: PASS
CRITICAL: None
MAJOR: None
MINOR-substantive: None
MINOR-cosmetic: None
"""
    counts = classify(output)
    assert counts.critical == 0
    assert counts.major == 0
    assert counts.substantive == 0
    assert counts.cosmetic == 0


def test_bracketed_none():
    output = """
CRITICAL: [None]
MAJOR: [None]
MINOR-substantive: [None]
MINOR-cosmetic: [None]
"""
    counts = classify(output)
    assert counts.critical == 0
    assert counts.major == 0


def test_one_critical_bullet_below():
    output = """
VERDICT: NEEDS REVISION
CRITICAL:
  - Spec doesn't define auth failure
MAJOR: None
MINOR-substantive: None
MINOR-cosmetic: None
"""
    counts = classify(output)
    assert counts.critical == 1
    assert counts.major == 0


def test_multiple_bullets_each_severity():
    output = """
CRITICAL:
- Issue 1
- Issue 2
- Issue 3
MAJOR:
- Major issue A
- Major issue B
MINOR-substantive:
- Substantive minor
MINOR-cosmetic:
- Cosmetic A
- Cosmetic B
- Cosmetic C
"""
    counts = classify(output)
    assert counts.critical == 3
    assert counts.major == 2
    assert counts.substantive == 1
    assert counts.cosmetic == 3


def test_quality_review_format():
    """quality-review uses WARNING / SUGGESTION-* — map to major / substantive / cosmetic."""
    output = """
GATE: code-quality
RESULT: FAIL
CRITICAL:
- src/auth.ts:42 - SQL injection vulnerability
WARNING:
- src/utils.ts:15 - swallowed exception
- src/api.ts:88 - missing validation
SUGGESTION-substantive:
- src/db.ts:50 - magic number
SUGGESTION-cosmetic: None
"""
    counts = classify(output)
    assert counts.critical == 1
    assert counts.major == 2          # WARNING mapped to major
    assert counts.substantive == 1    # SUGGESTION-substantive
    assert counts.cosmetic == 0


def test_mixed_with_blank_lines():
    """Blank lines end a section; counts should still be correct."""
    output = """
CRITICAL:
- One

MAJOR:
- Two

MINOR-substantive:
- Three
"""
    counts = classify(output)
    assert counts.critical == 1
    assert counts.major == 1
    assert counts.substantive == 1


def test_zero_token_variations():
    output = """
CRITICAL: 0
MAJOR: []
MINOR-substantive: none
MINOR-cosmetic: NONE
"""
    counts = classify(output)
    assert counts.critical == 0
    assert counts.major == 0
    assert counts.substantive == 0
    assert counts.cosmetic == 0


def test_minor_substantive_before_minor_cosmetic_in_header_map():
    """Ensure MINOR-substantive matches before MINOR (no such header) and
    doesn't get conflated with MINOR-cosmetic."""
    output = """
MINOR-substantive:
- Item A
MINOR-cosmetic:
- Item B
"""
    counts = classify(output)
    assert counts.substantive == 1
    assert counts.cosmetic == 1


def test_empty_input():
    counts = classify("")
    assert counts.critical == 0
    assert counts.major == 0
    assert counts.substantive == 0
    assert counts.cosmetic == 0


def test_no_severity_headers_in_text():
    counts = classify("This is just random text with no markers.")
    assert counts.critical == 0


def test_star_bullets():
    """Both - and * are valid bullet markers."""
    output = """
CRITICAL:
* Star bullet
MAJOR:
- Dash bullet
"""
    counts = classify(output)
    assert counts.critical == 1
    assert counts.major == 1


def test_indented_bullets():
    output = """
CRITICAL:
    - Deeply indented
    - Another deeply indented
"""
    counts = classify(output)
    assert counts.critical == 2


def test_case_insensitive_headers():
    output = """
critical: None
major:
  - lower case header
MiNoR-CoSmEtIc: None
"""
    counts = classify(output)
    assert counts.major == 1


def test_to_dict():
    counts = classify("CRITICAL:\n- One\nMAJOR: None\nMINOR-substantive: None\nMINOR-cosmetic: None\n")
    assert counts.to_dict() == {"critical": 1, "major": 0, "substantive": 0, "cosmetic": 0}
