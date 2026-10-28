# Checkpoints in Desktop mode

How the zones in `sage-checkpoints` are asked inside Claude Desktop's Code tab
(or wherever `desktop_mode: on`). Read on demand: the session hook names this
file when Desktop mode is on.

The zones keep their options and change only how they are asked: with the
`AskUserQuestion` tool, not a printed footer. The tool takes 1–4 questions of
2–4 options each, and always adds "Other" (free text) itself.

| Zone | Asked as |
|---|---|
| **Choice** | one question; the options as buttons. |
| **Approval** | one question: **Approve**, **Revise**, **New session** (its description names the next slash command). Mark one "(Recommended)" only when you recommend it. |
| **Next step** | one question; each next command as a button. |
| **Open** | no buttons — end with the plain sentence. |

- **Show the work first, then ask.** The question comes after the spec, plan
  or deliverable is on the page — never instead of it.
- **Still a hard wait.** The tool call is the checkpoint: no work continues
  until the answer arrives.
- **One question per turn.** The checkpoint question is the turn's question
  (the autonomous block's overflow, below, is the one exception). If the
  host also offers its own end-of-turn question, do not ask the same thing
  twice.
- **Workflow menus map the same way** — `[A] Review / [S] Skip / [R] Revise`,
  `[A]/[M]/[R]/[V]`, the quality-locked `[F]/[R]/[E]/[A]` — one question with
  those options; the letters may stay in the labels.
- **More than four options** (e.g. architect's `A/S/R/Q/N`, fix's `A/S/R/K/N`,
  `A/S/R/E/N`, a numbered findings list): buttons for the menu's first three
  options in its own order, plus the one you recommend if it is not among
  them; name every other option, with its letter, in the question text — the
  user picks it through "Other" by typing the letter.
- **The autonomous `[Q1]…[Qn]` block:** each `[Qn]` is one question; its
  options are the answers you weighed (2–4), the one you would default to
  labelled "(default)". Up to four per call — more go in a second call after
  the answers. Mark none "(Recommended)": the block exists because you could
  not decide. "Take every default" is the user answering each with its
  "(default)".
- **Auto-picks are unchanged.** `--autonomous --quality-locked` still picks
  and logs as written; only the checkpoints it never auto-picks become
  questions.
- **No duplicate footer.** Do not also print the text footer for a question
  you asked with the tool.

Outside Desktop mode, nothing here applies: the footers are the protocol.
