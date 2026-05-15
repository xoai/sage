"""Parse review sub-agent output into structured counts.

Handles both auto-review/auto-qa format (CRITICAL/MAJOR/MINOR-substantive/MINOR-cosmetic)
and quality-review format (CRITICAL/WARNING/SUGGESTION-substantive/SUGGESTION-cosmetic).
Maps both into a unified schema: {critical, major, substantive, cosmetic}.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Header patterns — both review formats map to the unified schema.
# Order matters: more-specific patterns (with hyphens) must match before
# the shorter ones to avoid "MINOR-substantive" matching the "MINOR" prefix.
HEADER_MAP = [
    (re.compile(r"^MINOR-substantive\s*:", re.IGNORECASE), "substantive"),
    (re.compile(r"^MINOR-cosmetic\s*:", re.IGNORECASE), "cosmetic"),
    (re.compile(r"^SUGGESTION-substantive\s*:", re.IGNORECASE), "substantive"),
    (re.compile(r"^SUGGESTION-cosmetic\s*:", re.IGNORECASE), "cosmetic"),
    (re.compile(r"^CRITICAL\s*:", re.IGNORECASE), "critical"),
    (re.compile(r"^MAJOR\s*:", re.IGNORECASE), "major"),
    (re.compile(r"^WARNING\s*:", re.IGNORECASE), "major"),
]

# Tokens that mean "zero findings" when they appear on the header line
# (e.g., "CRITICAL: None" or "MAJOR: [None]").
ZERO_TOKENS = {"none", "[none]", "[]", "0"}


@dataclass
class Counts:
    critical: int = 0
    major: int = 0
    substantive: int = 0
    cosmetic: int = 0

    def to_dict(self) -> dict:
        return {
            "critical": self.critical,
            "major": self.major,
            "substantive": self.substantive,
            "cosmetic": self.cosmetic,
        }


def _match_header(line: str) -> tuple[str, str] | None:
    """If the line is a severity header, return (severity_key, rest_of_line)."""
    for pattern, key in HEADER_MAP:
        match = pattern.match(line)
        if match:
            rest = line[match.end():].strip()
            return key, rest
    return None


def _is_zero_value(rest: str) -> bool:
    """Returns True if the value on a header line means zero findings."""
    return rest.strip().lower() in ZERO_TOKENS


def _is_bullet(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(("- ", "* ", "• "))


def classify(review_output: str) -> Counts:
    """Parse review sub-agent output into severity counts.

    Looks for severity headers (CRITICAL, MAJOR, WARNING, MINOR-*, SUGGESTION-*)
    and counts the bullet items under each. Handles "None"/"[None]"/"0" values
    on the header line itself as zero.
    """
    counts = Counts()
    if not review_output:
        return counts

    lines = review_output.splitlines()
    current_key: str | None = None
    items_in_section = 0

    def flush():
        nonlocal items_in_section
        if current_key is not None:
            setattr(counts, current_key, getattr(counts, current_key) + items_in_section)
            items_in_section = 0

    for line in lines:
        stripped = line.strip()
        header = _match_header(stripped)

        if header is not None:
            # Finalize the previous section's count
            flush()
            current_key, rest = header
            if _is_zero_value(rest):
                # Inline zero — close this section immediately
                current_key = None
            elif rest and not _is_zero_value(rest):
                # Header had inline content that wasn't "None" — could be a
                # bullet item, an item description, or just text. Count if
                # it looks like a list element.
                if _is_bullet(rest) or rest.startswith("["):
                    # `[ - foo, - bar ]` style or "- foo"
                    inner = rest.strip("[]").strip()
                    if inner and inner.lower() != "none":
                        # Count comma-separated bullets if present
                        items_in_section += sum(
                            1 for part in re.split(r",\s*-\s*|^-\s*", inner) if part.strip()
                        ) or 1
                elif rest.lower() not in ZERO_TOKENS:
                    # Plain text after the colon — treat as one finding only
                    # if it isn't empty/zero
                    items_in_section += 1
        elif current_key is not None:
            if _is_bullet(line):
                items_in_section += 1
            elif not stripped:
                # blank line ends the section
                flush()
                current_key = None

    # Final flush
    flush()
    return counts
