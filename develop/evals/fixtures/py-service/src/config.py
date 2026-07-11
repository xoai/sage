"""Service configuration."""

# How long to wait for an upstream response before giving up.
DEFAULT_TIMEOUT_SECONDS = 30

# Maximum number of connections held open to the upstream.
POOL_SIZE = 10


def timeout_for(profile: str) -> int:
    """Timeout for a named profile, falling back to the default."""
    overrides = {"batch": 300, "interactive": 5}
    return overrides.get(profile, DEFAULT_TIMEOUT_SECONDS)
