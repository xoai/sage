# UX Design Playbook — Constitution Additions

These principles are added to the project constitution when `@sage/play-ux-design`
is enabled. They apply to all user-facing implementations.

## UX Design Principles

1. Every user-facing feature MUST specify its error states. A feature without designed error handling is incomplete, not "happy path first."
2. Every user action MUST produce visible feedback within 100ms. Silence after an action is never acceptable — the user must know the system heard them.
3. Error messages MUST answer three questions: what happened, why, and what to do next. Technical error codes, stack traces, and jargon MUST NOT appear in user-facing messages.
4. The user MUST be able to undo or recover from any non-trivial action. Destructive actions MUST require explicit confirmation with a clear description of consequences.
5. No feature specification may skip the user's context: who is the user, what's their goal, what state are they in when they arrive, and where do they go after. "Add a button that does X" is not a specification.
6. Form data MUST be preserved on error. The system MUST NOT clear user input when validation fails. Losing a user's work is a critical usability failure.
