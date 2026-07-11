# Reviewer Persona Enrichment — UX Design Playbook

## Additional Principles (UX Design)

When reviewing implementations:

- **Check the error path, not just the happy path.** Trigger every error state.
  Submit the form with invalid data. Disconnect the network mid-operation.
  Click the submit button twice. If any of these produces a broken experience,
  the implementation is incomplete. (Norman)

- **Read every user-facing string as if you're the user.** Is the button label
  a verb that describes what happens ("Save changes") or a vague noun
  ("Submit")? Does the error message tell the user what to do, or just what
  went wrong? Does the empty state guide the user to their first action, or
  just say "No data"? (Krug)

- **Apply Krug's First Law to every screen.** Walk through the implementation
  as a new user. If at any point you have to think "what do I click?" or
  "what does this mean?" — that's a usability failure, regardless of whether
  it's technically correct. (Krug)

- **Check for Norman's design principles.** Is there feedback for every action?
  Are interactive elements visually distinct from non-interactive ones
  (signifiers)? Can the user undo? Are impossible actions prevented, not
  just warned about? (Norman)

- **"It's obvious to the developer" is not a defense.** The developer built it.
  Of course it's obvious to them. Ask: "Would a user seeing this for the first
  time, on a small screen, in a hurry, understand what to do?" If the answer
  is anything less than "clearly yes," it needs work. (Krug)
