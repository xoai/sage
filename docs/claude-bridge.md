# Claude bridge — Claude Code as an opencode model

Run sage on opencode with a different model per role, and let one of those
roles — typically `sage-implementer` — be served by **Claude Code**
(`claude -p`). You pick the Claude model per agent in `opencode.jsonc`
(`claude-cli/sonnet`, `claude-cli/opus`, `claude-cli/haiku`), and sage's
gates still police every edit Claude makes.

```
opencode ──HTTP──► claude-cli bridge (local, 127.0.0.1) ──► claude -p (in your project)
  built-in "@ai-sdk/openai-compatible"                        policed by sage's Claude Code hooks
```

## Requirements

- The `claude` CLI installed and logged in.
- Python 3.8+.
- **Linux/WSL:** a systemd user session. On WSL, enable systemd in
  `/etc/wsl.conf` (`[boot]` / `systemd=true`), then `wsl --shutdown` and reopen.
  **macOS:** launchd (built in).
- **Each project** must also have sage's Claude Code platform installed —
  Claude edits in its own process, so opencode's sage plugin never sees those
  edits; sage's Claude Code hooks are what enforce the gates:

  ```bash
  sage update --platform opencode,claude-code
  ```

  The bridge refuses to run Claude in a project without them.

## Install

```bash
sage setup claude-bridge            # install + start the service, print the config snippet
sage setup claude-bridge --status   # service, identity, port, config wiring
sage setup claude-bridge --remove   # stop + remove the service (keeps token + log)
sage setup claude-bridge --remove --purge   # … and delete token + log
sage setup claude-bridge --run      # foreground, no service
sage setup claude-bridge --timeout 3600   # allow runs up to an hour
```

`--port N` changes the port (default 8765); `--timeout SECS` changes how long
one Claude run may take before it is stopped (default 1500 = 25 minutes;
minimum 60). Install runs a user service —
**systemd** (`~/.config/systemd/user/sage-claude-bridge.service`) on
Linux/WSL, **launchd** (`~/Library/LaunchAgents/dev.sage.claude-bridge.plist`)
on macOS — that starts at login and restarts after a crash. The installer
verifies the running bridge is *this* sage's code (not just that the port
answers) and captures your shell `PATH` for it, so Claude can run your
project's toolchains (`go`, `node`, `flutter`, …). If you install new
toolchains later, re-run `sage setup claude-bridge`.

`sage upgrade` refreshes the service definition (keeping your port, timeout
and PATH) and asks the bridge to **reload when idle**: a running Claude task
finishes first, then the bridge restarts on the new code. `sage setup
claude-bridge` itself refuses to restart a bridge that is serving a run
(`--force` to override).

**It stays up.** The service restarts after *any* exit — a crash, `kill`,
`kill -9` — within a few seconds (`systemctl --user stop` / `--remove` still
stop it for good), and a stray SIGTERM also stops the Claude run it was
serving rather than orphaning it. Every signal is logged in `bridge.log`.

## Wire it into opencode

Install prints this; merge it into `~/.config/opencode/opencode.jsonc`:

```jsonc
"provider": {
  "claude-cli": {
    "npm": "@ai-sdk/openai-compatible",
    "name": "Claude CLI bridge",
    "options": {
      "baseURL": "http://127.0.0.1:8765/v1",
      "apiKey": "{file:~/.config/opencode/sage/bridge.token}",
      "headerTimeout": false,
      "chunkTimeout": 600000
    },
    "models": { "sonnet": {}, "opus": {}, "haiku": {} }
  }
},
"agent": {
  "sage-implementer": { "mode": "subagent", "model": "claude-cli/sonnet" }
}
```

sage never edits your opencode config; `--status` tells you whether it is
wired.

## What the bridge does per request

- Runs Claude in the directory opencode reports for the session — or, for a
  sage `--parallel` lane task, **in that lane's worktree** (only if it is a
  worktree of the same repository; anything else is refused, never run in
  the main checkout).
- Passes the task verbatim; returns Claude's report plus a metadata block
  (model, turns, sage gate blocks, transcript path). Transcripts are kept in
  `.sage/tmp/claude-implementer/` (git-ignored).
- One Claude per working tree at a time (others queue); different projects
  and lanes run in parallel.
- Keep-alive pings stop opencode dropping long runs; cancelling in opencode
  stops Claude within about a second; a run is bounded (25 minutes by
  default, `--timeout` at install) and then reported as `STATUS: BLOCKED`.
- Answers opencode's own title/summary prompts locally without starting
  Claude.

Only requests carrying the token in `~/.config/opencode/sage/bridge.token`
are accepted, and the bridge listens on 127.0.0.1 only.

## Troubleshooting

- `--status` first. Logs: `~/.config/opencode/sage/bridge.log` (plus
  `launchd.err.log` on macOS; `journalctl --user -u sage-claude-bridge` on Linux).
- `go: command not found` (or similar) in a report → re-run
  `sage setup claude-bridge` from a shell where the tool is on `PATH`.
- A report says the project lacks sage's Claude Code hooks → run
  `sage update --platform opencode,claude-code` in that project.
- opencode says **"Cannot connect to API: Unable to connect"** → the bridge is
  not listening. `sage setup claude-bridge --status`; if it is down, look for
  `received SIGTERM` in `bridge.log` (something killed it) and re-run
  `sage setup claude-bridge` — installs before 1.3.24 did not restart after a
  kill. On Linux/WSL the service runs while you have a session open; to keep
  it up with no terminal open: `loginctl enable-linger $USER`.

## Accounts and terms

The bridge runs your installed `claude` CLI as you. Whether a Claude
subscription may be used this way is governed by Anthropic's current terms —
check them; using an API key is unambiguous.
