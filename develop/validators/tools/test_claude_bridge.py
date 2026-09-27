#!/usr/bin/env python3
"""
test_claude_bridge.py — the opencode → Claude Code bridge, pinned.

The bridge (runtime/platforms/community/opencode/claude-bridge/) exposes
`claude -p` as an OpenAI-compatible model API for opencode. It was piloted
and reviewed against a real Claude before becoming a built-in; every defect
those rounds found is pinned here, end to end, through the REAL bridge and
the REAL wrapper — only `claude` itself is a fake (a bash script on PATH), so
this runs anywhere, CI included, with no Claude account.

Pinned (brief.md §Defects): exact-match housekeeping (a task that says
"generate a title" still runs); workdir from opencode's <env> block; the
ungated-project refusal; lane packets start Claude IN the lane worktree (same
repo only); same-tree runs serialize; cancel kills Claude (running) or skips
it (queued); the wrapper timeout returns a structured BLOCKED report; no
orphaned claude processes; /healthz identity.

Usage:  python3 develop/validators/tools/test_claude_bridge.py
Python 3.8+, stdlib only. Needs git + bash.
"""
from __future__ import annotations

import http.client
import importlib.util
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
BRIDGE_DIR = REPO_ROOT / "runtime" / "platforms" / "community" / "opencode" / "claude-bridge"
BRIDGE = BRIDGE_DIR / "claude-cli-bridge.py"

FAKE_CLAUDE = r"""#!/usr/bin/env bash
# Fake `claude -p` for tests: records who ran where, obeys a sleep control
# file, then prints a stream-json result like the real CLI does.
packet=$(cat)
echo "start $(date +%s) pid=$$ cwd=$(pwd -P)" >> "$FAKE_CLAUDE_LOG"
secs=0
[ -f "$FAKE_CLAUDE_SLEEP_FILE" ] && secs=$(cat "$FAKE_CLAUDE_SLEEP_FILE")
sleep "$secs"
echo "end $(date +%s) pid=$$" >> "$FAKE_CLAUDE_LOG"
printf '%s\n' '{"type":"system","subtype":"init"}'
python3 -c 'import json,sys; print(json.dumps({"type":"result","result":"STATUS: DONE\nfake report for: "+sys.argv[1][:60],"num_turns":1,"is_error":False}))' "$packet"
"""


def load_bridge_module():
    spec = importlib.util.spec_from_file_location("claude_cli_bridge", BRIDGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(args),
                   cwd=str(cwd), check=True, capture_output=True)


def make_project(root: pathlib.Path, gated=True) -> pathlib.Path:
    root.mkdir(parents=True)
    git(root, "init", "-q")
    (root / "README.md").write_text("x\n")
    if gated:
        (root / ".claude").mkdir()
        (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {
            "PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command",
                "command": "bash .claude/hooks/sage-tdd-gate.sh"}]}]}}))
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed")
    return root.resolve()


def system_for(workdir) -> str:
    return ("You are powered by the model named sonnet.\n"
            "<env>\n  Working directory: %s\n  Workspace root folder: %s\n"
            "  Is directory a git repo: yes\n</env>" % (workdir, workdir))


class BridgeUnitTest(unittest.TestCase):
    """Pure functions — no server."""

    @classmethod
    def setUpClass(cls):
        cls.b = load_bridge_module()

    def test_housekeeping_exact_openings_only(self):
        hk = self.b.housekeeping_reply
        self.assertIsNotNone(hk("You are a title generator. You output ONLY a thread title.", "x"))
        self.assertIsNotNone(hk("sys", "Summarize what was done in this conversation. Write like"))
        self.assertIsNone(hk("sys", "Task T3: generate a title for each post and "
                                    "summarize the conversation log"))

    def test_env_block_wins_over_earlier_mention(self):
        sysmsg = ("Instructions from: AGENTS.md\nWorking directory: /wrong\n\n"
                  "<env>\n  Working directory: /right/place\n</env>")
        _, _, wd = self.b.parse_request({"messages": [
            {"role": "system", "content": sysmsg}, {"role": "user", "content": "t"}]})
        self.assertEqual(wd, "/right/place")

    def test_task_is_last_user_message_verbatim(self):
        _, packet, _ = self.b.parse_request({"messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "old"},
            {"role": "user", "content": [{"type": "text", "text": "line1\n  line2"}]}]})
        self.assertEqual(packet, "line1\n  line2")


class BridgeServer:
    """The real bridge on a free port, with a fake claude on PATH."""

    def __init__(self, tmp: pathlib.Path, extra_env=None):
        self.tmp = tmp
        self.state = tmp / "state"
        self.bin = tmp / "bin"
        self.bin.mkdir(exist_ok=True)
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(0o755)
        self.log = tmp / "fake-claude.log"
        self.sleep_file = tmp / "fake-sleep"
        env = dict(os.environ,
                   PATH="%s:%s" % (self.bin, os.environ.get("PATH", "")),
                   SAGE_BRIDGE_PORT="0", SAGE_BRIDGE_STATE_DIR=str(self.state),
                   SAGE_BRIDGE_KEEPALIVE="1",
                   FAKE_CLAUDE_LOG=str(self.log),
                   FAKE_CLAUDE_SLEEP_FILE=str(self.sleep_file))
        env.update(extra_env or {})
        self.proc = subprocess.Popen([sys.executable, str(BRIDGE)], env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True)
        line = self.proc.stdout.readline()
        if "127.0.0.1:" not in line:
            self.stop()
            raise RuntimeError("bridge did not start: %r" % line)
        self.port = int(line.split("127.0.0.1:")[1].split("/")[0])
        self.token = (self.state / "bridge.token").read_text().strip()

    def sleep(self, secs):
        self.sleep_file.write_text(str(secs))

    def runs(self):
        if not self.log.exists():
            return []
        return [l.split() for l in self.log.read_text().splitlines() if l.startswith("start")]

    def request(self, method, path, body=None, token=True, timeout=60):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + self.token
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        resp = conn.getresponse()
        data = resp.read().decode()
        conn.close()
        return resp.status, data

    def chat(self, workdir, packet, system=None, stream=True, model="sonnet"):
        body = {"model": model, "stream": stream, "messages": [
            {"role": "system", "content": system if system is not None else system_for(workdir)},
            {"role": "user", "content": packet}]}
        status, data = self.request("POST", "/v1/chat/completions", body)
        if not stream:
            return status, json.loads(data)["choices"][0]["message"]["content"]
        text = ""
        for line in data.splitlines():
            if line.startswith("data: {"):
                delta = json.loads(line[6:])["choices"][0]["delta"]
                text += delta.get("content") or ""
        return status, text

    def open_stream(self, workdir, packet):
        """A raw streaming request we can abandon mid-flight (a cancel)."""
        body = json.dumps({"model": "sonnet", "stream": True, "messages": [
            {"role": "system", "content": system_for(workdir)},
            {"role": "user", "content": packet}]}).encode()
        s = socket.create_connection(("127.0.0.1", self.port))
        s.sendall(b"POST /v1/chat/completions HTTP/1.1\r\nHost: x\r\n"
                  b"Authorization: Bearer " + self.token.encode() + b"\r\n"
                  b"Content-Type: application/json\r\nContent-Length: "
                  + str(len(body)).encode() + b"\r\n\r\n" + body)
        return s

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.proc.stdout.close()


def fake_claude_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # a zombie is dead for our purposes. `ps` works on Linux AND macOS
    # (/proc does not exist on macOS, where this suite also runs in CI).
    out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                         capture_output=True, text=True).stdout.strip()
    return bool(out) and not out.startswith("Z")


class BridgeIntegrationTest(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="claude-bridge-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.srv = BridgeServer(self.tmp)
        self.addCleanup(self.srv.stop)
        self.proj = make_project(self.tmp / "proj")

    def test_auth_models_and_healthz_identity(self):
        self.assertEqual(self.srv.request("GET", "/v1/models", token=False)[0], 401)
        status, data = self.srv.request("GET", "/v1/models")
        self.assertEqual(status, 200)
        self.assertIn("sonnet", [m["id"] for m in json.loads(data)["data"]])
        status, data = self.srv.request("GET", "/healthz")
        h = json.loads(data)
        self.assertEqual(h["pid"], self.srv.proc.pid)
        self.assertEqual(pathlib.Path(h["code"]), BRIDGE.resolve())
        self.assertEqual(pathlib.Path(h["state_dir"]), self.srv.state)
        # the version must be the framework's (a wrong parents[] depth reported
        # "unknown" on the first live install)
        self.assertEqual(h["version"], (REPO_ROOT / "VERSION").read_text().strip())
        self.assertEqual(oct((self.srv.state / "bridge.token").stat().st_mode & 0o777), "0o600")

    def test_happy_path_returns_report_and_metadata(self):
        status, text = self.srv.chat(self.proj, "Task T1: do the thing")
        self.assertEqual(status, 200)
        self.assertIn("STATUS: DONE", text)
        self.assertIn("fake report for: Task T1: do the thing", text)
        self.assertIn("--- run metadata ---", text)
        self.assertEqual(len(self.srv.runs()), 1)
        self.assertEqual(self.srv.runs()[0][3], "cwd=%s" % self.proj)

    def test_non_stream_path(self):
        status, text = self.srv.chat(self.proj, "Task T1b", stream=False)
        self.assertIn("STATUS: DONE", text)

    def test_housekeeping_never_launches_claude(self):
        _, t1 = self.srv.chat(self.proj, "hi", system="You are a title generator. You output ONLY a thread title.")
        _, t2 = self.srv.chat(self.proj, "Summarize what was done in this conversation. Write like a PR.")
        self.assertEqual(self.srv.runs(), [])
        self.assertNotIn("STATUS", t1)
        _, t3 = self.srv.chat(self.proj, "Task T2: generate a title for every blog post")
        self.assertIn("STATUS: DONE", t3)                 # a real task still runs
        self.assertEqual(len(self.srv.runs()), 1)

    def test_missing_workdir_refused(self):
        _, text = self.srv.chat(self.proj, "Task", system="no env block here")
        self.assertIn("STATUS: BLOCKED", text)
        self.assertEqual(self.srv.runs(), [])

    def test_nonexistent_workdir_blocked_with_status(self):
        _, text = self.srv.chat("/nonexistent/proj", "Task")
        self.assertIn("STATUS: BLOCKED", text)
        self.assertIn("does not exist", text)

    def test_ungated_project_refused_before_claude(self):
        bare = make_project(self.tmp / "bare", gated=False)
        _, text = self.srv.chat(bare, "Task")
        self.assertIn("STATUS: BLOCKED", text)
        self.assertIn("sage update --platform opencode,claude-code", text)
        self.assertEqual(self.srv.runs(), [])

    def test_lane_packet_runs_in_the_lane_worktree(self):
        lane = self.tmp / "proj-lane"
        git(self.proj, "worktree", "add", "-q", "-b", "lane", str(lane))
        pkt = ("## Your working directory — read this first\n\nEverything you do "
               "happens in the lane worktree: `%s`, on\nbranch `lane`.\n\nTask T5" % lane)
        _, text = self.srv.chat(self.proj, pkt)
        self.assertIn("STATUS: DONE", text)
        self.assertEqual(self.srv.runs()[0][3], "cwd=%s" % lane.resolve())

    def test_lane_outside_the_repo_or_missing_is_refused(self):
        other = make_project(self.tmp / "other")
        for bad in (str(other), "/nonexistent/lane"):
            pkt = "Everything you do happens in the lane worktree: `%s`, on" % bad
            _, text = self.srv.chat(self.proj, pkt)
            self.assertIn("STATUS: BLOCKED", text)
            self.assertIn("Refusing to run in the main checkout", text)
        self.assertEqual(self.srv.runs(), [])

    def test_same_tree_runs_serialize(self):
        self.srv.sleep(2)
        results = []
        t1 = threading.Thread(target=lambda: results.append(self.srv.chat(self.proj, "Task A")))
        t2 = threading.Thread(target=lambda: results.append(self.srv.chat(self.proj, "Task B")))
        t1.start(); time.sleep(0.5); t2.start(); t1.join(); t2.join()
        lines = self.srv.log.read_text().splitlines()
        # strictly alternating: start, end, start, end — never start, start
        self.assertEqual([l.split()[0] for l in lines], ["start", "end", "start", "end"])
        self.assertTrue(all("STATUS: DONE" in r[1] for r in results))

    def test_cancel_while_running_kills_claude(self):
        self.srv.sleep(60)
        s = self.srv.open_stream(self.proj, "Task long")
        deadline = time.time() + 15
        while not self.srv.runs() and time.time() < deadline:
            time.sleep(0.2)
        self.assertTrue(self.srv.runs(), "fake claude never started")
        pid = int(self.srv.runs()[0][2].split("=")[1])
        s.close()                                       # the user cancels
        deadline = time.time() + 8
        while fake_claude_alive(pid) and time.time() < deadline:
            time.sleep(0.2)
        self.assertFalse(fake_claude_alive(pid), "claude survived the cancel")

    def test_cancel_while_queued_never_starts_claude(self):
        self.srv.sleep(4)
        first = threading.Thread(target=lambda: self.srv.chat(self.proj, "Task first"))
        first.start(); time.sleep(0.7)
        s = self.srv.open_stream(self.proj, "Task queued")
        time.sleep(1.5); s.close()                      # cancel while it waits
        first.join()
        time.sleep(2)
        self.assertEqual(len(self.srv.runs()), 1, "the queued run started anyway")


class WrapperTimeoutTest(unittest.TestCase):
    def test_timeout_returns_structured_blocked_and_kills(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="claude-bridge-to-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        srv = BridgeServer(tmp, {"SAGE_CLAUDE_TIMEOUT": "2"})
        self.addCleanup(srv.stop)
        proj = make_project(tmp / "proj")
        srv.sleep(60)
        _, text = srv.chat(proj, "Task slow")
        self.assertIn("STATUS: BLOCKED", text)
        self.assertIn("TIMED OUT", text)
        self.assertIn("timed_out=True", text)
        pid = int(srv.runs()[0][2].split("=")[1])
        time.sleep(1)
        self.assertFalse(fake_claude_alive(pid))


SETUP = REPO_ROOT / "runtime" / "tools" / "claude_bridge_setup.py"
SPACEY_PATH = "/usr/local/go/bin:/usr/bin:/mnt/c/Program Files/Some Tool/bin:/bin"


def load_setup_module():
    spec = importlib.util.spec_from_file_location("claude_bridge_setup", SETUP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class InstallerRenderTest(unittest.TestCase):
    """Service definitions are pure renders — tested on any OS."""

    @classmethod
    def setUpClass(cls):
        cls.s = load_setup_module()
        cls.args = dict(python="/opt/py 3/bin/python3", bridge=str(BRIDGE),
                        path_env=SPACEY_PATH, port=8765,
                        state_dir="/home/u/.config/opencode/sage")

    def test_unit_quotes_path_intact(self):
        unit = self.s.render_unit(**self.args)
        # the review's critical bug: unquoted, systemd truncated PATH at the
        # first space and dropped go/flutter for every Go project
        self.assertIn('Environment="PATH=%s"' % SPACEY_PATH, unit)
        self.assertIn('ExecStart="/opt/py 3/bin/python3" "%s"' % BRIDGE, unit)
        self.assertIn('Environment="SAGE_BRIDGE_PORT=8765"', unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("WantedBy=default.target", unit)
        self.assertNotIn("After=default.target", unit)   # ordering noise

    @unittest.skipUnless(shutil.which("systemd-analyze"), "no systemd-analyze")
    def test_unit_passes_systemd_verify_with_spacey_path(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="unit-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        args = dict(self.args, python=sys.executable)
        u = d / "sage-claude-bridge.service"
        u.write_text(self.s.render_unit(**args))
        out = subprocess.run(["systemd-analyze", "--user", "verify", str(u)],
                             capture_output=True, text=True)
        self.assertNotIn("Invalid environment assignment", out.stderr + out.stdout)

    def test_plist_is_valid_launchd(self):
        import plistlib
        pl = plistlib.loads(self.s.render_plist(**self.args).encode())
        self.assertEqual(pl["Label"], "dev.sage.claude-bridge")
        self.assertEqual(pl["ProgramArguments"], ["/opt/py 3/bin/python3", str(BRIDGE)])
        self.assertEqual(pl["EnvironmentVariables"]["PATH"], SPACEY_PATH)
        self.assertEqual(pl["EnvironmentVariables"]["SAGE_BRIDGE_PORT"], "8765")
        self.assertTrue(pl["RunAtLoad"])
        self.assertEqual(pl["KeepAlive"], {"SuccessfulExit": False})
        self.assertTrue(pl["StandardErrorPath"].startswith(self.args["state_dir"]))

    def test_token_created_0600_and_preserved(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="tok-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        t1 = self.s.ensure_token(d / "state")
        self.assertEqual(oct((d / "state" / "bridge.token").stat().st_mode & 0o777), "0o600")
        self.assertEqual(self.s.ensure_token(d / "state"), t1)   # re-install keeps it

    def test_legacy_personal_install_moved_not_deleted(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="leg-")) / "state"
        self.addCleanup(shutil.rmtree, d.parent, ignore_errors=True)
        d.mkdir()
        for n in ("claude-cli-bridge.py", "sage-claude-implement.sh",
                  "claude-implementer-shim.md", "last-request.json",
                  "bridge.token", "bridge.log"):
            (d / n).write_text(n)
        (d / "__pycache__").mkdir()                              # legacy bytecode
        (d / "__pycache__" / "claude-cli-bridge.cpython-312.pyc").write_text("x")
        moved = self.s.migrate_legacy(d)
        self.assertEqual(sorted(pathlib.Path(m).name for m in moved),
                         ["__pycache__", "claude-cli-bridge.py", "claude-implementer-shim.md",
                          "last-request.json", "sage-claude-implement.sh"])
        self.assertTrue((d / "bridge.token").exists())          # kept
        self.assertTrue((d / "bridge.log").exists())
        legacy = [p for p in d.iterdir() if p.name.startswith("legacy-")]
        self.assertEqual(len(legacy), 1)
        self.assertEqual((legacy[0] / "claude-cli-bridge.py").read_text(),
                         "claude-cli-bridge.py")
        self.assertEqual(self.s.migrate_legacy(d), [])          # idempotent

    def test_config_wiring_detection(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="cfg-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        cfg = d / "opencode.jsonc"
        self.assertFalse(self.s.config_wired(cfg, 8765))
        cfg.write_text('{\n  // comment\n  "provider": { "claude-cli": {\n'
                       '    "options": { "baseURL": "http://127.0.0.1:8765/v1" } } }\n}\n')
        self.assertTrue(self.s.config_wired(cfg, 8765))
        self.assertFalse(self.s.config_wired(cfg, 9999))        # wrong port
        snippet = self.s.opencode_snippet(8765, "/home/u/.config/opencode/sage")
        self.assertIn('"npm": "@ai-sdk/openai-compatible"', snippet)
        self.assertIn('"baseURL": "http://127.0.0.1:8765/v1"', snippet)
        self.assertIn("{file:/home/u/.config/opencode/sage/bridge.token}", snippet)


if __name__ == "__main__":
    unittest.main()
