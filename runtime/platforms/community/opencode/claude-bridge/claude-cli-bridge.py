#!/usr/bin/env python3
"""claude-cli-bridge.py — expose `claude -p` as an OpenAI-compatible model API,
so opencode can use Claude Code as an agent's model with NO relay model and NO
third-party provider package: opencode's built-in `@ai-sdk/openai-compatible`
talks to this bridge; this bridge runs sage-claude-implement.sh (-> claude -p).

    opencode.jsonc:
      "provider": { "claude-cli": {
          "npm": "@ai-sdk/openai-compatible",
          "options": { "baseURL": "http://127.0.0.1:8765/v1",
                       "apiKey": "{file:~/.config/opencode/sage/bridge.token}",
                       "headerTimeout": false, "chunkTimeout": 600000 },
          "models": { "sonnet": {}, "opus": {} } } },
      "agent": { "sage-implementer": { "model": "claude-cli/sonnet" } }

What it does per request (POST /v1/chat/completions):
  - model id ("sonnet", "opus", or a full claude model id) -> SAGE_CLAUDE_MODEL
  - working directory -> parsed from opencode's system prompt env block
  - task packet -> the LAST user message, verbatim
  - runs the wrapper (which refuses projects without sage's Claude Code hooks,
    bounds the run, kills the process tree, keeps a transcript) and returns its
    output as the assistant message. opencode's tool definitions are ignored:
    Claude executes its own tools, policed by sage's Claude Code hooks.
  - streaming: SSE keep-alive comments while Claude works (opencode drops a
    stream after `chunkTimeout` ms of silence); a client disconnect (cancel)
    sends TERM to the wrapper, whose trap takes claude down.

Install/run: `sage setup claude-bridge` (service on Linux/WSL systemd or macOS
launchd) — see docs/claude-bridge.md. Env: SAGE_BRIDGE_PORT (8765; 0 = any
free port), SAGE_BRIDGE_HOST (127.0.0.1), SAGE_BRIDGE_KEEPALIVE seconds (15),
SAGE_BRIDGE_STATE_DIR (~/.config/opencode/sage: bridge.token, bridge.log).
Endpoints: /v1/models, /v1/chat/completions, /healthz, POST /admin/reload-when-idle\n(all bearer-auth).
Python 3.8+, stdlib only.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import secrets
import select
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent
# Code lives in the sage framework (updated by `sage upgrade`); state lives in
# a per-user dir that survives upgrades. The default is where opencode users
# already keep it, so `apiKey: {file:~/.config/opencode/sage/bridge.token}`
# in opencode.jsonc stays valid across installs and upgrades.
WRAPPER = HERE / "sage-claude-implement.sh"
STATE_DIR = pathlib.Path(os.environ.get(
    "SAGE_BRIDGE_STATE_DIR", str(pathlib.Path.home() / ".config/opencode/sage")))
TOKEN_FILE = STATE_DIR / "bridge.token"
LOG_FILE = STATE_DIR / "bridge.log"
VERSION_FILE = HERE.parents[4] / "VERSION"      # <framework>/VERSION (claude-bridge→opencode→community→platforms→runtime→root)
HOST = os.environ.get("SAGE_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SAGE_BRIDGE_PORT", "8765"))
KEEPALIVE = float(os.environ.get("SAGE_BRIDGE_KEEPALIVE", "15"))
MODELS = ["sonnet", "opus", "haiku"]

# opencode's env block: "Working directory: /abs/path" (verified in the pilot).
# opencode's env block (1.18.32 template): "<env>\n  Working directory: <dir>".
# Anchored to <env>: project instructions (AGENTS.md, custom prompts) are also
# in the system text and could mention "Working directory:" earlier.
ENV_WORKDIR_RE = re.compile(r"<env>\s*\n\s*Working directory:\s*(/[^\n<]+)")
WORKDIR_RE = re.compile(r"Working directory:\s*(/[^\n<]+)")
# Housekeeping calls opencode may route to the agent's model. Matched on the
# EXACT openings of opencode's own prompts (read from the 1.18.32 binary) —
# never a loose keyword search: a real task that says "generate a title"
# must reach Claude, not get a canned reply with no STATUS line.
# sage --parallel lanes: the context packet's first section (sage
# core/templates/subagents/context-packet.md) names the lane worktree. Claude
# Code confines a headless session to its start directory — the pilot's lane
# run could not cd/commit there and gave up BLOCKED after 4 min, with sage's
# hooks judging lane edits against the MAIN checkout. So Claude must START
# in the lane worktree.
LANE_RE = re.compile(r"Everything you do happens in the lane worktree:\s*`([^`]+)`")
TITLE_OPENING = "You are a title generator."
SUMMARY_OPENING = "Summarize what was done in this conversation."


def git_common_dir(path: str):
    try:
        out = subprocess.run(["git", "-C", path, "rev-parse", "--path-format=absolute",
                              "--git-common-dir"], capture_output=True, text=True,
                             timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return os.path.realpath(out.stdout.strip()) if out.returncode == 0 else None


def resolve_lane(session_dir: str, packet: str):
    """(lane_dir, None) when the packet names a valid lane worktree of the
    session's repository; (None, None) when it names none; (None, reason)
    when it names one that must be refused — never fall back to the main
    checkout, that is the failure mode lanes exist to prevent."""
    m = LANE_RE.search(packet)
    if not m:
        return None, None
    lane = os.path.join(session_dir, os.path.expanduser(m.group(1).strip()))
    lane = os.path.realpath(lane)
    if not os.path.isdir(lane):
        return None, "lane worktree %s does not exist" % lane
    mine, theirs = git_common_dir(session_dir), git_common_dir(lane)
    if not mine or mine != theirs:
        return None, ("lane worktree %s is not a worktree of the session's "
                      "repository (%s)" % (lane, session_dir))
    return lane, None


def housekeeping_reply(system: str, packet: str):
    if system.lstrip().startswith(TITLE_OPENING):
        return "Sage implementer task"
    if packet.lstrip().startswith(SUMMARY_OPENING):
        return "Implemented the task via Claude Code; see the implementer report."
    return None


def log(msg: str) -> None:
    line = "%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()

# In-flight jobs (queued or running, until their response is fully written).
# /healthz reports the count; reload-when-idle and SIGTERM use the registry.
_JOBS: dict = {}
_JOBS_GUARD = threading.Lock()
_RELOAD_PENDING = threading.Event()
RELOAD_EXIT_CODE = 75       # "restart me": the service manager (Restart=always /
                            # KeepAlive) brings the bridge back on the new code


def active_runs() -> int:
    with _JOBS_GUARD:
        return len(_JOBS)


def maybe_reload() -> None:
    """Exit for a reload once nothing is in flight. `sage upgrade` asks for
    this instead of restarting outright: an outright restart cut a running
    implementer off mid-task and left its half-done edits in the tree
    (field, 2026-09-27)."""
    if _RELOAD_PENDING.is_set() and active_runs() == 0:
        log("reload-when-idle: idle — exiting %d for the service manager to "
            "restart on the current code" % RELOAD_EXIT_CODE)
        os._exit(RELOAD_EXIT_CODE)


def on_terminate(signum, frame) -> None:
    """A stray `kill` must not orphan Claude: stop every in-flight wrapper
    (its trap kills claude's tree), log it, exit. launchd signals only this
    process, not its children, so without this Claude would keep editing."""
    name = {signal.SIGTERM: "SIGTERM", signal.SIGINT: "SIGINT"}.get(signum, str(signum))
    with _JOBS_GUARD:
        jobs = list(_JOBS.items())
    log("received %s — stopping %d in-flight run(s) and exiting" % (name, len(jobs)))
    for rid, state in jobs:
        state["cancelled"] = True
        proc = state.get("proc")
        if proc is not None and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
    deadline = time.time() + 8
    for _, state in jobs:
        proc = state.get("proc")
        while proc is not None and proc.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if proc is not None and proc.poll() is None:
            proc.kill()
    os._exit(128 + signum)


def workdir_lock(workdir: str) -> threading.Lock:
    key = os.path.realpath(workdir)
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def stop_wrapper(state: dict, rid: str, why: str) -> None:
    """TERM the wrapper (its trap kills claude's tree), KILL after 20 s."""
    proc = state.get("proc")
    if proc is None or proc.poll() is not None:
        if proc is None:
            log("%s %s before Claude started — run skipped" % (rid, why))
        return
    log("%s %s — TERM to wrapper pid %d" % (rid, why, proc.pid))
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()


def load_token() -> str:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not TOKEN_FILE.exists():
        TOKEN_FILE.write_text(secrets.token_hex(24) + "\n", encoding="utf-8")
        os.chmod(TOKEN_FILE, 0o600)
    return TOKEN_FILE.read_text(encoding="utf-8").strip()


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content
                         if isinstance(p, dict) and p.get("type") == "text")
    return ""


def parse_request(body: dict):
    msgs = body.get("messages") or []
    system = "\n".join(text_of(m.get("content")) for m in msgs
                       if m.get("role") == "system")
    users = [text_of(m.get("content")) for m in msgs if m.get("role") == "user"]
    packet = users[-1] if users else ""
    m = ENV_WORKDIR_RE.search(system) or WORKDIR_RE.search(system)
    workdir = m.group(1).strip() if m else None
    return system, packet, workdir


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    token = ""

    def log_message(self, fmt, *args):  # quiet default stderr logging
        pass

    # ── helpers ──
    def _json(self, code: int, obj: dict) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self) -> bool:
        if self.headers.get("Authorization", "") == "Bearer " + self.token:
            return True
        self._json(401, {"error": {"message": "bad or missing bearer token"}})
        return False

    # ── routes ──
    def do_GET(self):
        if not self._authed():
            return
        if self.path.rstrip("/") == "/v1/models":
            self._json(200, {"object": "list", "data": [
                {"id": m, "object": "model", "owned_by": "claude-cli"}
                for m in MODELS]})
        elif self.path.rstrip("/") == "/healthz":
            # Identity, not liveness: the installer checks that THIS code
            # (this framework's bridge) answers as the service's pid — a
            # stale bridge on the same port must never pass verification.
            try:
                version = VERSION_FILE.read_text(encoding="utf-8").strip()
            except OSError:
                version = "unknown"
            self._json(200, {"ok": True, "pid": os.getpid(),
                             "code": str(pathlib.Path(__file__).resolve()),
                             "version": version, "state_dir": str(STATE_DIR),
                             "active_runs": active_runs(),
                             "reload_pending": _RELOAD_PENDING.is_set()})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        if not self._authed():
            return
        if self.path.rstrip("/") == "/admin/reload-when-idle":
            _RELOAD_PENDING.set()
            log("reload-when-idle requested (%d in flight)" % active_runs())
            self._json(202, {"reload_pending": True, "active_runs": active_runs()})
            threading.Timer(0.3, maybe_reload).start()   # after the 202 is sent
            return
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._json(404, {"error": {"message": "not found"}})
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, OSError):
            self._json(400, {"error": {"message": "invalid JSON body"}})
            return
        model = str(body.get("model") or "sonnet")
        stream = bool(body.get("stream"))
        system, packet, workdir = parse_request(body)
        if os.environ.get("SAGE_BRIDGE_DUMP"):
            (STATE_DIR / "last-request.json").write_text(json.dumps(body, indent=1),
                                                    encoding="utf-8")
        rid = "chatcmpl-" + uuid.uuid4().hex[:24]

        canned = housekeeping_reply(system, packet)
        if canned is not None:
            log("%s housekeeping request answered locally" % rid)
            return self._reply(rid, model, stream, canned, None)
        if not workdir:
            log("%s REFUSED: no working directory in system prompt" % rid)
            return self._reply(rid, model, stream,
                               "STATUS: BLOCKED\nclaude-cli bridge: no "
                               "'Working directory:' found in the request, "
                               "so it cannot tell where to run Claude.", None)

        lane, refusal = resolve_lane(workdir, packet)
        if refusal:
            log("%s REFUSED: %s" % (rid, refusal))
            return self._reply(rid, model, stream,
                               "STATUS: BLOCKED\nclaude-cli bridge: " + refusal
                               + ". Refusing to run in the main checkout instead.",
                               None)
        if lane:
            log("%s lane worktree: %s (session dir %s)" % (rid, lane, workdir))
            workdir = lane
        env = dict(os.environ, SAGE_CLAUDE_MODEL=model)
        log("%s queued model=%s workdir=%s packet_chars=%d stream=%s"
            % (rid, model, workdir, len(packet), stream))
        started = time.time()
        job = {"proc": None, "out": "", "cancelled": False, "rc": None}

        def run():
            # One Claude per working tree at a time: two implementers editing
            # and committing in the same checkout would corrupt each other's
            # work. Different projects still run in parallel.
            with workdir_lock(workdir):
                if job["cancelled"]:
                    return
                log("%s start (waited %.0fs)" % (rid, time.time() - started))
                proc = subprocess.Popen(
                    ["bash", str(WRAPPER), workdir], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
                job["proc"] = proc
                if job["cancelled"]:            # cancel raced the start
                    stop_wrapper(job, rid, "cancelled while starting")
                out, _ = proc.communicate(packet.encode())
                job["out"] = out.decode("utf-8", "replace")
                job["rc"] = proc.returncode

        with _JOBS_GUARD:
            _JOBS[rid] = job
        try:
            t = threading.Thread(target=run, daemon=True)
            t.start()
            self._reply(rid, model, stream, None, (job, t, started))
        finally:
            # released only after the response is fully written, so a
            # reload can never cut off a report on its way to opencode
            with _JOBS_GUARD:
                _JOBS.pop(rid, None)
            maybe_reload()

    def _client_gone(self) -> bool:
        """True once the client has closed its end (readable + EOF). The
        request body was fully read already, so any readability is EOF."""
        try:
            readable, _, _ = select.select([self.connection], [], [], 0)
            if not readable:
                return False
            return self.connection.recv(1, socket.MSG_PEEK) == b""
        except (OSError, ValueError):
            return True

    # ── response writer (streams keep-alives while the wrapper runs) ──
    def _reply(self, rid, model, stream, text, job):
        created = int(time.time())

        def chunk(delta, finish=None):
            return ("data: " + json.dumps({
                "id": rid, "object": "chat.completion.chunk",
                "created": created, "model": model,
                "choices": [{"index": 0, "delta": delta,
                             "finish_reason": finish}]}) + "\n\n").encode()

        def finish_job():
            state, t, started = job
            t.join()
            log("%s done exit=%s secs=%.0f" % (rid, state["rc"],
                                                time.time() - started))
            return state["out"]

        if not stream:
            final = text if job is None else finish_job()
            return self._json(200, {
                "id": rid, "object": "chat.completion", "created": created,
                "model": model,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant",
                                         "content": final}}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                          "total_tokens": 0}})

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(chunk({"role": "assistant", "content": ""}))
            self.wfile.flush()
            if job is not None:
                _, t, _ = job
                last_ping = time.time()
                while t.is_alive():
                    t.join(1.0)
                    if not t.is_alive():
                        break
                    # Cancel detection, every second: the client closing the
                    # socket makes it readable with EOF. Waiting for a failed
                    # keep-alive write instead took up to ~2x KEEPALIVE (the
                    # pilot measured 24 s of Claude still running after a
                    # cancel) — the kernel accepts the first write after the
                    # peer closes.
                    if self._client_gone():
                        raise ConnectionResetError("client closed the stream")
                    if time.time() - last_ping >= KEEPALIVE:
                        # An SSE comment: ignored by the parser, but bytes on
                        # the wire reset opencode's chunkTimeout.
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_ping = time.time()
                text = finish_job()
            self.wfile.write(chunk({"content": text}))
            self.wfile.write(chunk({}, "stop"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            if job is not None:
                state = job[0]
                # Flag first, then look for a process: run() re-checks the
                # flag right after it starts one, so a cancel racing the
                # queue→start transition still stops that run.
                state["cancelled"] = True
                stop_wrapper(state, rid, "client disconnected")
        self.close_connection = True


def main() -> int:
    if not WRAPPER.exists():
        print("missing wrapper: %s" % WRAPPER, file=sys.stderr)
        return 2
    Handler.token = load_token()
    signal.signal(signal.SIGTERM, on_terminate)
    signal.signal(signal.SIGINT, on_terminate)
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    port = srv.server_address[1]          # the real port when PORT is 0 (tests)
    log("bridge listening on http://%s:%d/v1 (pid %d)" % (HOST, port, os.getpid()))
    print("claude-cli bridge on http://%s:%d/v1 (log: %s)" % (HOST, port, LOG_FILE),
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
