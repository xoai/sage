"""Quality-locked decision module.

Deterministic classifier + state machine for the --quality-locked
review-revise loop. Parses sub-agent review output into structured
counts and decides the next action (PASS, REVISE, CAP_REACHED, ESCALATE).
"""

__version__ = "1.0.0"
