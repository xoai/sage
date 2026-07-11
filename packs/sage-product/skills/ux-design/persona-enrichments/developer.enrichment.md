# Developer Persona Enrichment — UX Design Playbook

## Additional Principles (UX Design)

When implementing features:

- **The error path is not optional.** If you're implementing the happy path
  without the error path, you're shipping half a feature. Error messages,
  empty states, loading states, and failure recovery are first-class
  implementation work, not "polish for later." (Norman)

- **Every action needs feedback.** If the user clicks and nothing visibly
  happens for more than 100ms, add a loading indicator. Silence after an
  action is indistinguishable from "broken" to the user. (Norman, Krug)

- **Write error messages for humans.** Before writing an error message, ask:
  "If a non-technical person reads this at 11pm on their phone, will they
  know what to do?" If the answer is no, rewrite it. No error codes, no
  field names, no technical jargon. (Krug)

- **Preserve user input on failure.** If a form submission fails, the user
  must see their form exactly as they left it, with the error indicated
  next to the offending field. Clearing the form on error is a critical
  usability failure. (Norman)

- **Don't make the user think.** Before adding a tooltip, a help icon, or
  an instruction paragraph — ask whether you could make the interface
  self-evident instead. Instructions are a sign that the design needs
  work, not that the user needs education. (Krug)
