#!/usr/bin/env python3
"""test_scope_judge.py — the judge runtime, measured before a model exists.

Every SG-12 safety invariant and SG-17 anti-nag invariant is pinned here with
NO model in the loop: the runner is injected, the locks are real files, the
journal is a real journal. The one thing these tests cannot claim is that the
judge's verdicts are any GOOD — that is E-JUDGE-1's job, and `scope_judge`
ships false until it passes (30-§3).

Usage:  python3 develop/validators/scope-judge/test_scope_judge.py
Python 3.8+, stdlib only.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "tools"))

import scope_judge as SJ  # noqa: E402

JOURNAL_HOOK = (REPO_ROOT / "runtime" / "platforms" / "claude-code"
                / "hooks" / "sage-scope-journal.sh")

A_PLAN = """\
# Plan

- [x] **Task 1:** the finished one
  - **Files:** src/done.py
- [ ] **Task 2:** add input validation to auth
  - **Files:** src/auth.py
  - **Action:** validate inputs, nothing else
- [ ] **Task 3:** later
  - **Files:** src/later.py
"""


def edit_event(path="src/auth.py", **extra):
    d = {"tool_name": "Edit", "tool_input": {"file_path": path}}
    d.update(extra)
    return d


class Fixture(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="scope-judge-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.cycle = self.root / ".sage" / "work" / "demo"
        self.cycle.mkdir(parents=True)
        self.locks = self.root / "locks"
        self.locks.mkdir()
        self.env = {"SAGE_JUDGE_LOCK_DIR": str(self.locks)}
        self.spawned = []
        self.config(judge_every=3, judge_cooldown=4, judge_timeout=60)
        (self.cycle / "manifest.md").write_text(
            "---\ncycle_id: \"demo\"\nstatus: in-progress\n"
            "gate_state: building\nscope:\n  derived_from: plan@aa\n"
            "  globs:\n    - src/auth.py  # T2 add input validation\n"
            "  collateral: []\n---\n")
        (self.cycle / "plan.md").write_text(A_PLAN)
        (self.cycle / "spec.md").write_text(
            "# Spec\n\n## Out of scope\n\nThe logger stays ugly.\n")

    def config(self, **kv):
        lines = ["sage-version: \"1.3.10\"", "hard_enforcement: true",
                 "scope_judge: true"]
        lines += ["%s: %s" % (k, v) for k, v in kv.items()]
        (self.root / ".sage" / "config.yaml").write_text("\n".join(lines) + "\n")

    def spawn_spy(self, cycle_dir):
        self.spawned.append(cycle_dir)

    def hook(self, event=None, environ=None):
        return SJ.hook(event or edit_event(), self.root,
                       environ={**self.env, **(environ or {})},
                       spawn_fn=self.spawn_spy)

    def rows(self):
        return SJ.read_journal(self.cycle)


class RecursionGuardTest(Fixture):
    """SG-12: the judge's own model call can never re-trigger judging."""

    def test_module_level_guard(self):
        out = self.hook(environ={"SAGE_JUDGE": "1"})
        self.assertIsNone(out)
        self.assertEqual(self.rows(), [], "nothing may be journaled under SAGE_JUDGE")

    def test_bash_hook_no_ops_under_SAGE_JUDGE(self):
        p = subprocess.run(
            ["bash", str(JOURNAL_HOOK)],
            input=json.dumps(edit_event()), capture_output=True, text=True,
            cwd=str(self.root),
            env={**os.environ, "SAGE_JUDGE": "1",
                 "CLAUDE_PROJECT_DIR": str(self.root)})
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "")
        self.assertFalse((self.cycle / "scope-journal.jsonl").exists())

    def test_bash_hook_journals_when_armed(self):
        p = subprocess.run(
            ["bash", str(JOURNAL_HOOK)],
            input=json.dumps(edit_event()), capture_output=True, text=True,
            cwd=str(self.root),
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root),
                 "SAGE_JUDGE_LOCK_DIR": str(self.locks),
                 "SAGE_SCOPE_JUDGE_TOOL":
                     str(REPO_ROOT / "runtime" / "tools" / "scope_judge.py")})
        self.assertEqual(p.returncode, 0)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["path"], "src/auth.py")

    def test_bash_hook_is_inert_when_scope_judge_false(self):
        (self.root / ".sage" / "config.yaml").write_text(
            "hard_enforcement: true\nscope_judge: false\n")
        p = subprocess.run(
            ["bash", str(JOURNAL_HOOK)],
            input=json.dumps(edit_event()), capture_output=True, text=True,
            cwd=str(self.root),
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)})
        self.assertEqual(p.returncode, 0)
        self.assertFalse((self.cycle / "scope-journal.jsonl").exists())


class JournalTest(Fixture):
    def test_one_line_per_event_with_task_hint(self):
        self.hook(edit_event("src/auth.py"))
        self.hook({"tool_name": "Bash",
                   "tool_input": {"command": "x" * 500}})
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["task_hint"], "T2")
        self.assertEqual(len(rows[1]["cmd"]), SJ.CMD_TRUNCATE,
                         "bash commands are truncated at 200 chars")

    def test_subagent_events_are_flagged_sub_true(self):
        """SG-11 + [V2]: agent_id/agent_type are the documented markers."""
        self.hook(edit_event(agent_id="a-1", agent_type="implementer"))
        rows = self.rows()
        self.assertTrue(rows[0].get("sub"))

    def test_parent_session_id_flags_sub(self):
        """[V-B]: the opencode adapter forwards the child session's parentID
        under this key — same SG-11 suppression, different wire."""
        self.hook(edit_event(parent_session_id="ses_parent"))
        self.assertTrue(self.rows()[0].get("sub"))

    def test_rotation_at_the_size_cap(self):
        old = SJ.ROTATE_BYTES
        SJ.ROTATE_BYTES = 200
        self.addCleanup(setattr, SJ, "ROTATE_BYTES", old)
        for _ in range(12):
            self.hook()
        self.assertTrue((self.cycle / "scope-journal.jsonl.1").exists())

    def test_multiple_active_cycles_stand_down(self):
        other = self.root / ".sage" / "work" / "other"
        other.mkdir()
        (other / "manifest.md").write_text(
            "---\ncycle_id: \"other\"\nstatus: in-progress\n---\n")
        self.assertIsNone(self.hook())
        self.assertEqual(self.rows(), [],
                         "with two active cycles the judge does not guess "
                         "which one an edit belongs to")


class CadenceTest(Fixture):
    """SG-12: event-driven eligibility every judge_every events — never a
    timer — and a busy cycle queues nothing."""

    def test_spawns_at_the_cadence_not_before(self):
        self.hook(); self.hook()
        self.assertEqual(self.spawned, [], "2 events < judge_every=3")
        self.hook()
        self.assertEqual(len(self.spawned), 1)

    def test_a_busy_cycle_queues_nothing(self):
        for _ in range(3):
            self.hook()
        self.assertEqual(len(self.spawned), 1)
        (self.cycle / SJ.CYCLE_LOCK).write_text("123")   # the judge is running
        self.hook()
        self.assertEqual(len(self.spawned), 1, "no second pass queued")

    def test_a_verdict_resets_the_counter(self):
        for _ in range(3):
            self.hook()
        SJ.append_journal(self.cycle, {"type": "verdict", "verdict": "on-scope",
                                       "reason": "", "at_event": 3})
        self.spawned.clear()
        self.hook()
        self.assertEqual(self.spawned, [], "1 event since the verdict < 3")

    def test_sub_events_do_not_count_toward_cadence(self):
        for _ in range(3):
            self.hook(edit_event(agent_id="a-1"))
        self.assertEqual(self.spawned, [], "SG-11: sub events never trigger judging")

    def test_a_healthy_judge_keeps_its_event_driven_cadence(self):
        """Round-2 review #2: the spawn marker must not throttle a judge that
        RECORDS verdicts — a completed pass clears it, so the next
        judge_every events spawn the next pass regardless of judge_timeout.
        Event-driven means events, never a timer."""
        passes = []

        def run_now(cycle_dir):
            passes.append(1)
            SJ.run_judge(cycle_dir, environ=self.env,
                         runner=lambda p, c: '{"verdict":"on-scope","reason":"ok"}')

        for _ in range(9):                     # judge_every=3 → 3 passes
            SJ.hook(edit_event(), self.root, environ=self.env, spawn_fn=run_now)
        self.assertEqual(len(passes), 3,
                         "3 verdict-recording passes across 9 events")
        self.assertFalse((self.cycle / SJ.SPAWN_MARKER).exists(),
                         "a recorded verdict clears the marker")

    def test_a_skipped_pass_does_not_spawn_per_event(self):
        """Review #10: a pass that ends WITHOUT a verdict (cap, busy) leaves
        the cadence counter high; without the spawn marker every later event
        launched a fresh child (12 events → 9 spawns, probed). One attempt
        per judge_timeout."""
        for _ in range(12):
            self.hook()
        self.assertEqual(len(self.spawned), 1,
                         "one attempt, not a spawn-per-event storm")
        # And the marker expires: a stale marker re-arms the cadence.
        marker = self.cycle / SJ.SPAWN_MARKER
        old = time.time() - 3600
        os.utime(str(marker), (old, old))
        self.hook()
        self.assertEqual(len(self.spawned), 2)


class LockTest(Fixture):
    """SG-12: per-cycle serialization + the machine-wide cap."""

    def test_two_concurrent_triggers_one_judge(self):
        self.assertTrue(SJ.acquire_cycle_lock(self.cycle, SJ.DEFAULTS))
        self.assertFalse(SJ.acquire_cycle_lock(self.cycle, SJ.DEFAULTS))
        SJ.release_cycle_lock(self.cycle)
        self.assertTrue(SJ.acquire_cycle_lock(self.cycle, SJ.DEFAULTS))

    def test_a_stale_lock_is_replaced(self):
        lock = self.cycle / SJ.CYCLE_LOCK
        lock.write_text("dead")
        old = time.time() - 3600
        os.utime(str(lock), (old, old))
        self.assertTrue(SJ.acquire_cycle_lock(self.cycle, SJ.DEFAULTS))

    def test_machine_wide_cap_skips_over_capacity(self):
        for i in range(SJ.MACHINE_CAP):
            (self.locks / ("scope-judge-%d.lock" % i)).write_text("x")
        out = SJ.run_judge(self.cycle, environ=self.env,
                           runner=lambda p, c: '{"verdict":"drift"}')
        self.assertEqual(out, {"skipped": "concurrency-cap"})
        self.assertEqual(self.rows(), [], "over cap → skip, no verdict recorded")


class JudgePassTest(Fixture):
    def seed_events(self, n, path="src/auth.py"):
        for i in range(n):
            SJ.append_journal(self.cycle, {
                "type": "event", "ts": i, "tool": "Edit",
                "path": "%s-%d" % (path, i), "task_hint": "T2"})

    def test_window_is_bounded(self):
        """SG-12: no unbounded transcript reads — the last judge_window
        non-sub events since the previous verdict, nothing more."""
        self.config(judge_window=10)
        self.seed_events(30)
        packet, window, n_now = SJ.build_packet(self.cycle, SJ.read_config(self.root))
        self.assertEqual(len(window), 10)
        self.assertEqual(n_now, 30)
        self.assertIn("src/auth.py-29", packet)
        self.assertNotIn("src/auth.py-5 ", packet)

    def test_window_evidence_labels_match_journal_positions(self):
        """Review #11: with 25 events and window 10, the first window row is
        journal event 16 and must be labeled e16 — not e1. The judge's
        evidence refs (recorded, and read by E-JUDGE-1a's grader) point at
        these labels."""
        self.config(judge_window=10)
        self.seed_events(25)
        packet, _, _ = SJ.build_packet(self.cycle, SJ.read_config(self.root))
        self.assertIn("e16 Edit src/auth.py-15", packet)
        self.assertIn("e25 Edit src/auth.py-24", packet)
        self.assertNotIn("e1 ", packet)

    def test_packet_is_assembled_deterministically(self):
        """SG-13: plan task verbatim, spec boundary, declared scope, window —
        and the Scopey epistemics rule stated in the prompt."""
        self.seed_events(2)
        packet, _, _ = SJ.build_packet(self.cycle, SJ.read_config(self.root))
        self.assertIn("add input validation to auth", packet)
        self.assertIn("The logger stays ugly.", packet)
        self.assertIn("src/auth.py  # T2", packet)
        self.assertIn("absence of evidence is NOT drift", packet)

    def test_malformed_output_is_insufficient_evidence(self):
        self.seed_events(3)
        row = SJ.run_judge(self.cycle, environ=self.env,
                           runner=lambda p, c: "I think it drifted, maybe?")
        self.assertEqual(row["verdict"], "insufficient-evidence")

    def test_timeout_is_insufficient_evidence_never_drift(self):
        self.seed_events(3)
        row = SJ.run_judge(self.cycle, environ=self.env,
                           runner=lambda p, c: None)   # what a killed call yields
        self.assertEqual(row["verdict"], "insufficient-evidence")

    def test_empty_window_is_insufficient_evidence(self):
        row = SJ.run_judge(self.cycle, environ=self.env,
                           runner=lambda p, c: '{"verdict":"drift","reason":"x"}')
        self.assertEqual(row["verdict"], "insufficient-evidence")

    def test_a_drift_verdict_queues_exactly_one_pending_correction(self):
        self.seed_events(3)
        drift = ('{"verdict": "drift", "reason": "refactoring the logger", '
                 '"evidence": "e1,e2"}')
        SJ.run_judge(self.cycle, environ=self.env, runner=lambda p, c: drift)
        pending = json.loads((self.cycle / SJ.PENDING).read_text())
        self.assertEqual(pending["task"], "T2")
        self.assertIn("refactoring the logger", pending["reason"])

    def test_verdicts_append_to_the_journal(self):
        self.seed_events(3)
        SJ.run_judge(self.cycle, environ=self.env,
                     runner=lambda p, c: '{"verdict":"on-scope","reason":"ok"}')
        verdicts = [r for r in self.rows() if r.get("type") == "verdict"]
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0]["verdict"], "on-scope")
        self.assertEqual(verdicts[0]["at_event"], 3)

    def test_cost_is_recorded_when_the_cli_reports_usage(self):
        """SG-19: every judge call's model usage lands in the journal; the
        close-out totals read from here."""
        self.seed_events(3)
        out = json.dumps({"result": '{"verdict":"on-scope","reason":"ok"}',
                          "usage": {"input_tokens": 900, "output_tokens": 30}})
        SJ.run_judge(self.cycle, environ=self.env, runner=lambda p, c: out)
        costs = [r for r in self.rows() if r.get("type") == "cost"]
        self.assertEqual(len(costs), 1)
        self.assertEqual(costs[0]["usage"]["input_tokens"], 900)
        v, d, i, tin, tout = SJ.cycle_totals(self.cycle)
        self.assertEqual((v, d, i, tin, tout), (1, 0, 0, 900, 30))


class InjectionTest(Fixture):
    """SG-16/SG-17/SG-18: one correction, the exact envelope, the anti-nag
    invariants, and the audit line written by code."""

    def queue_drift(self, reason="refactoring the logger", task="T2"):
        (self.cycle / SJ.PENDING).write_text(json.dumps({
            "task": task, "task_label": '%s "add input validation"' % task,
            "reason": reason, "evidence": "e1", "at_event": 1}))

    def test_the_envelope_is_the_v1_verified_shape(self):
        self.queue_drift()
        out = self.hook()
        self.assertEqual(set(out.keys()), {"hookSpecificOutput"})
        inner = out["hookSpecificOutput"]
        self.assertEqual(inner["hookEventName"], "PostToolUse")
        self.assertIn("Sage scope-judge:", inner["additionalContext"])
        self.assertIn("add-collateral", inner["additionalContext"])
        self.assertIn("return to T2", inner["additionalContext"])

    def test_the_injection_writes_the_decisions_line_itself(self):
        self.queue_drift()
        self.hook()
        decisions = (self.cycle / "decisions.md").read_text()
        self.assertIn("scope correction injected", decisions)
        self.assertIn("T2", decisions)

    def test_cooldown_holds(self):
        """At most one injection per judge_cooldown journal events."""
        self.queue_drift()
        self.assertIsNotNone(self.hook())
        self.queue_drift(reason="a brand new reason")
        self.assertIsNone(self.hook(), "cooldown=4: too soon for a second")
        self.hook(); self.hook()
        self.assertIsNotNone(self.hook(), "cooldown elapsed, new reason → inject")

    def test_same_task_same_reason_never_repeats(self):
        self.config(judge_every=99, judge_cooldown=0)
        self.queue_drift()
        self.assertIsNotNone(self.hook())
        self.queue_drift()          # identical verdict-reason queued again
        self.assertIsNone(self.hook(),
                          "repeats require a NEW reason (SG-17)")
        self.assertFalse((self.cycle / SJ.PENDING).exists(),
                         "the deduped pending is consumed, not re-litigated")

    def test_rotation_does_not_suppress_injections_forever(self):
        """Review #16: after a 2 MB rotation the event count restarts small
        while last_injection_event stays large — which read as an eternal
        cooldown. A recorded injection point ABOVE the current count is
        rotation debris, not a cooldown."""
        (self.cycle / SJ.INJECT_STATE).write_text(json.dumps(
            {"last_injection_event": 5000, "injected": []}))
        self.queue_drift()
        self.assertIsNotNone(self.hook(),
                             "post-rotation, the correction still delivers")

    def test_never_inside_subagents(self):
        self.queue_drift()
        out = self.hook(edit_event(agent_id="a-1"))
        self.assertIsNone(out, "SG-11: a packet-scoped implementer receiving "
                               "cycle-scope corrections is being derailed")

    def test_on_scope_and_insufficient_evidence_never_inject(self):
        for _ in range(3):
            self.hook()
        self.assertFalse((self.cycle / SJ.PENDING).exists())
        self.assertIsNone(self.hook())


OC_STREAM = "\n".join([
    # Verbatim shape of `opencode run --format json` (1.18.12, [V-C] probe).
    json.dumps({"type": "step_start", "timestamp": 1, "sessionID": "s",
                "part": {"type": "step-start"}}),
    json.dumps({"type": "text", "timestamp": 2, "sessionID": "s",
                "part": {"type": "text",
                         "text": '{"verdict": "drift", "reason": '
                                 '"logger refactor", "evidence": "e2"}'}}),
    json.dumps({"type": "step_finish", "timestamp": 3, "sessionID": "s",
                "part": {"type": "step-finish", "reason": "stop",
                         "tokens": {"total": 8041, "input": 52, "output": 23,
                                    "reasoning": 30,
                                    "cache": {"write": 0, "read": 7936}}}}),
])


JUDGE_AGENT = ('{\n'
               '  "$schema": "https://opencode.ai/config.json",\n'
               '  "agent": {\n'
               '    "sage-scope-judge": {\n'
               '      "model": "deepseek/deepseek-v4-flash",\n'
               '      "permission": { "edit": "deny", "bash": "deny" }\n'
               '    }\n'
               '  }\n'
               '}\n')

# A2's note text, verbatim — the contract with the user, pinned exactly.
DESIGNATION_NOTE = ('scope-judge: no model designated — define agent '
                    '"sage-scope-judge" (with a model) in opencode.json, '
                    'or set judge_cmd explicitly. No model is inferred; '
                    'the judge stays idle until designated.')


class OpencodePortTest(Fixture):
    """SG-14 on the second platform (T4-rev2): `auto` accepts exactly one
    designation — a user-defined `sage-scope-judge` agent carrying a model
    — or soft-fails. Model spend requires explicit designation; nothing is
    inferred. And the NDJSON event stream parses like the claude envelope."""

    def setUp(self):
        super().setUp()
        self.xdg = self.root / "xdg"          # isolate from ~/.config
        self.xdg.mkdir()
        self.oc_env = {"SAGE_PLATFORM": "opencode",
                       "XDG_CONFIG_HOME": str(self.xdg), **self.env}
        self.cfg = SJ.read_config(self.root)

    def seed(self, n=3):
        for i in range(n):
            SJ.append_journal(self.cycle, {"type": "event", "ts": i,
                                           "tool": "Edit", "path": "src/a-%d" % i})

    def test_designated_agent_with_model_resolves(self):
        """The nested permission block is in the fixture on purpose — the
        brace-matched read must not stop at the inner object."""
        (self.root / "opencode.json").write_text(JUDGE_AGENT)
        cmd = SJ.resolve_judge_cmd(self.cfg, self.root, self.oc_env)
        self.assertEqual(cmd, "OPENCODE_PURE=true opencode run "
                              "--agent sage-scope-judge "
                              "--model deepseek/deepseek-v4-flash --format json")

    def test_designation_in_the_global_config_resolves(self):
        d = self.xdg / "opencode"
        d.mkdir()
        (d / "opencode.jsonc").write_text(
            '{\n  // user-authored designation\n  "agent": {\n'
            '    "sage-scope-judge": { "model": "p/m-mini" }\n  }\n}')
        cmd = SJ.resolve_judge_cmd(self.cfg, self.root, self.oc_env)
        self.assertIn("--agent sage-scope-judge --model p/m-mini", cmd)

    def test_explicit_judge_cmd_wins_over_the_agent(self):
        (self.root / "opencode.json").write_text(JUDGE_AGENT)
        cfg = dict(self.cfg, judge_cmd="my-cmd --flag")
        self.assertEqual(SJ.resolve_judge_cmd(cfg, self.root, self.oc_env),
                         "my-cmd --flag")

    def test_agent_without_model_is_undefined(self):
        """Defined-but-modelless must never mean 'inherit the session
        model' — that is a background judge on the expensive primary."""
        (self.root / "opencode.json").write_text(
            '{"agent": {"sage-scope-judge": '
            '{"permission": {"edit": "deny", "bash": "deny"}}}}')
        self.assertIsNone(SJ.resolve_judge_cmd(self.cfg, self.root, self.oc_env))
        self.seed()
        row = SJ.run_judge(self.cycle, environ=self.oc_env)
        self.assertEqual(row["verdict"], "insufficient-evidence")
        self.assertFalse((self.cycle / SJ.PENDING).exists())

    def test_other_agents_do_not_designate(self):
        (self.root / "opencode.json").write_text(
            '{"agent": {"sage-reviewer": {"model": "p/expensive"}}}')
        self.assertIsNone(SJ.resolve_judge_cmd(self.cfg, self.root, self.oc_env))

    def test_shell_metacharacters_are_not_a_model(self):
        """judge_cmd runs under a shell; a config value with metacharacters
        resolves to nothing rather than to an injection vector."""
        (self.root / "opencode.json").write_text(
            '{"agent": {"sage-scope-judge": {"model": "p/m; rm -rf ."}}}')
        self.assertIsNone(SJ.resolve_judge_cmd(self.cfg, self.root, self.oc_env))

    def test_no_designation_soft_fails_with_the_exact_note_once(self):
        """No agent anywhere → insufficient-evidence, never drift, never a
        guessed model — and the pointer note is A2's text verbatim, once
        per cycle, not once per pass. The second pass gets FRESH events on
        purpose: without them it would end at the empty-window branch and
        never re-enter the soft-fail path, and this test would pass with
        note_once broken (review catch, 2026-08-04)."""
        self.seed()
        row = SJ.run_judge(self.cycle, environ=self.oc_env)
        self.assertEqual(row["verdict"], "insufficient-evidence")
        self.assertIn("no model designated", row["reason"])
        self.assertFalse((self.cycle / SJ.PENDING).exists())
        self.seed()                    # new window → the resolve path again
        row2 = SJ.run_judge(self.cycle, environ=self.oc_env)
        self.assertIn("no model designated", row2["reason"],
                      "second pass must re-enter the soft-fail path")
        notes = [r for r in self.rows() if r.get("type") == "note"]
        self.assertEqual(len(notes), 1, "the pointer is a note, not a nag")
        self.assertEqual(notes[0]["text"], DESIGNATION_NOTE)
        verdicts = [r for r in self.rows() if r.get("type") == "verdict"]
        self.assertEqual(len(verdicts), 2)
        self.assertTrue(all(v["verdict"] == "insufficient-evidence"
                            for v in verdicts), "soft-fail is never drift")

    def test_claude_platform_resolution_is_unchanged(self):
        self.assertEqual(SJ.resolve_judge_cmd(self.cfg, self.root, self.env),
                         SJ.AUTO_CMD)

    def test_explicit_judge_cmd_is_returned_untouched(self):
        cfg = dict(self.cfg, judge_cmd="opencode run --model x/y --format json")
        self.assertEqual(SJ.resolve_judge_cmd(cfg, self.root, self.oc_env),
                         "opencode run --model x/y --format json")

    def test_event_stream_parses_to_verdict_and_usage(self):
        out = SJ.parse_verdict(OC_STREAM)
        self.assertEqual(out["verdict"], "drift")
        self.assertEqual(out["reason"], "logger refactor")
        self.assertEqual(out["usage"], {"input_tokens": 52, "output_tokens": 23})

    def test_run_judge_records_cost_from_the_event_stream(self):
        """SG-19 parity: the opencode wire feeds the same cost rows and
        close-out totals the claude envelope does."""
        (self.root / "opencode.json").write_text(JUDGE_AGENT)
        self.seed()
        seen = {}

        def runner(packet, cfg):
            seen["cmd"] = cfg.get("judge_cmd_resolved")
            seen["cwd"] = cfg.get("judge_cwd")
            return OC_STREAM

        row = SJ.run_judge(self.cycle, environ=self.oc_env, runner=runner)
        self.assertEqual(row["verdict"], "drift")
        self.assertIn("--agent sage-scope-judge "
                      "--model deepseek/deepseek-v4-flash", seen["cmd"])
        self.assertEqual(seen["cwd"], str(self.root))
        self.assertTrue((self.cycle / SJ.PENDING).exists(),
                        "drift → pending correction queued")
        v, d, i, tin, tout = SJ.cycle_totals(self.cycle)
        self.assertEqual((v, d, tin, tout), (1, 1, 52, 23))

    def test_on_scope_and_insufficient_leave_no_pending(self):
        (self.root / "opencode.json").write_text(JUDGE_AGENT)
        self.seed()
        SJ.run_judge(self.cycle, environ=self.oc_env,
                     runner=lambda p, c: '{"verdict":"on-scope","reason":"ok"}')
        self.assertFalse((self.cycle / SJ.PENDING).exists())
        SJ.run_judge(self.cycle, environ=self.oc_env,
                     runner=lambda p, c: "no json here")
        self.assertFalse((self.cycle / SJ.PENDING).exists())


class EndToEndTest(Fixture):
    def test_drift_detected_then_corrected_once(self):
        """The whole loop with a fake model: events → eligible pass → drift
        verdict → queued correction → next hook emits it once."""
        for _ in range(3):
            self.hook()
        self.assertEqual(len(self.spawned), 1)
        drift = '{"verdict":"drift","reason":"logger refactor crept in","evidence":"e2"}'
        SJ.run_judge(self.cycle, environ=self.env, runner=lambda p, c: drift)
        out = self.hook()
        self.assertIsNotNone(out)
        self.assertIn("logger refactor crept in",
                      out["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(self.hook(), "one correction, not a nag")


if __name__ == "__main__":
    unittest.main(verbosity=2)
