"""Load flag defaults from .sage/config.yaml.

Strict-match contract (per spec §5.4): only lines matching exactly
`<key>: true` (with one space after the colon, lowercase `true`, no
trailing characters except optional whitespace) are honored. All other
variants are treated as no default.

This deliberately rejects:
- `quality_locked: True` (titlecase)
- `quality_locked: "true"` (quoted)
- `quality_locked: yes` (YAML alias)
- `quality_locked:true` (no space)
- `quality_locked:  true` (extra space)
- `quality_locked: true  # comment` (trailing content)

The strictness ensures Python and Bash agree byte-for-byte and matches
the canonical form Sage itself writes. Failure modes are fail-soft —
malformed config returns no defaults, never raises.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# Match `<key>: true` with exactly one space, anchored at line start and end.
# No trailing comments, no extra whitespace, lowercase `true` only.
_TRUE_LINE_RE = re.compile(r"^(quality_locked|autonomous): true$", re.MULTILINE)


def load_defaults(config_path: Optional[str | Path]) -> dict:
    """Read top-level boolean flag defaults from a Sage config.yaml.

    Returns a dict like {"quality_locked": True, "autonomous": True}
    containing only keys whose canonical `true` value is found. Missing
    or malformed config produces an empty dict.

    Args:
        config_path: path to .sage/config.yaml (or None / nonexistent)

    Returns:
        dict with True values for keys found in canonical form. Empty
        dict if config is missing, unreadable, or has no matching keys.
    """
    defaults: dict = {}
    if config_path is None:
        return defaults

    path = Path(config_path)
    if not path.is_file():
        return defaults

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return defaults

    for match in _TRUE_LINE_RE.finditer(text):
        defaults[match.group(1)] = True

    return defaults
