#!/usr/bin/env python3
"""
test_manifest.py — the mechanical gate_state (R120).

The bug this pins is the one L1 found in production: a manifest that says
`gate_state: plan-approved` — "plan approved, no tasks started" — while all three
tasks sit implemented and committed in the tree beside it. A session resuming from
that manifest reads "no tasks started" and does the work again.

Two directions matter, and the second is the one that keeps a fix honest:

  1. The manifest must ADVANCE when work begins. (Otherwise the bug is still here.)
  2. The manifest must NOT advance to an APPROVAL state. gates-passed and complete
     are granted by a human or by the gates actually running. A script that awarded
     them because the files looked finished would forge the signature the gate exists
     to collect — a worse bug than the one being fixed.

Usage:  python3 develop/validators/tools/test_manifest.py
Python 3.8+, stdlib only.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "tools"))

import manifest as M  # noqa: E402


def a_manifest(gate_state="plan-approved", status="in-progress") -> str:
    return (
        "---\n"
        'cycle_id: "20260712-retry-policy"\n'
        "workflow: build\n"
        "phase: implement\n"
        f"status: {status}\n"
        "tier: standard\n"
        f"gate_state: {gate_state}\n"
        "---\n"
        "\n"
        "# Cycle: Retry policy\n"
        "\n"
        "The body may quote its own state — `gate_state: plan-approved` — in prose.\n"
    )


class AdvanceTest(unittest.TestCase):
    """The hook path: a source file was written, so say what is true."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="manifest-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.m = self.d / "manifest.md"

    def test_writing_source_advances_a_plan_approved_cycle(self):
        """THE BUG, FIXED. L1 run 2 shipped a manifest exactly like this."""
        self.m.write_text(a_manifest("plan-approved"))
        old, new = M.advance(self.m, "src/config.py")
        self.assertEqual((old, new), ("plan-approved", "building"))
        state, ok = M.read_gate_state(self.m.read_text())
        self.assertEqual(state, "building")
        self.assertTrue(ok)

    def test_it_will_NOT_award_an_approval_state(self):
        """The load-bearing refusal.

        gates-passed and complete are granted by a human, or by the quality-locked
        loop after the gates actually run. A hook that advanced a cycle to
        gates-passed because the files looked finished would be forging the signature
        the gate exists to collect. `building` is the ceiling, and it is a statement
        of FACT (work has begun), never of APPROVAL.
        """
        self.assertEqual(M.DERIVABLE_CEILING, "building")
        self.m.write_text(a_manifest("building"))
        old, new = M.advance(self.m, "src/config.py")
        self.assertIsNone(new, "a building cycle must not be pushed to gates-passed")
        self.assertEqual(M.read_gate_state(self.m.read_text())[0], "building")

    def test_it_never_regresses_a_cycle(self):
        for state in ("gates-passed", "complete"):
            self.m.write_text(a_manifest(state, status="in-progress"))
            M.advance(self.m, "src/config.py")
            self.assertEqual(M.read_gate_state(self.m.read_text())[0], state,
                             f"{state} must survive a source write untouched")

    def test_a_pre_spec_cycle_is_left_alone(self):
        """Editing source while pre-spec is a Rule 3 violation. Silently advancing it
        would ERASE the violation rather than report it — the spec gate's job is to
        block that edit, not this hook's job to legitimise it."""
        self.m.write_text(a_manifest("pre-spec"))
        old, new = M.advance(self.m, "src/config.py")
        self.assertIsNone(new)
        self.assertEqual(M.read_gate_state(self.m.read_text())[0], "pre-spec")

    def test_bookkeeping_is_not_implementation(self):
        """Writing the manifest, a doc, or Sage's own machinery is not `building`.
        Otherwise the hook would advance a cycle because the agent updated the very
        file the hook is about to edit."""
        for path in (".sage/work/004-x/manifest.md", "docs/design.md",
                     "sage/skills/tdd/SKILL.md", "README.md", ".claude/settings.json"):
            self.m.write_text(a_manifest("plan-approved"))
            _, new = M.advance(self.m, path)
            self.assertIsNone(new, f"{path} is not implementation")

    def test_a_completed_cycle_is_not_touched(self):
        self.m.write_text(a_manifest("complete", status="complete"))
        _, new = M.advance(self.m, "src/config.py")
        self.assertIsNone(new)

    def test_only_the_frontmatter_is_rewritten(self):
        """The body quotes its own state in prose. Rewriting that would have the hook
        editing the agent's narration instead of the machine field."""
        self.m.write_text(a_manifest("plan-approved"))
        M.advance(self.m, "src/config.py")
        text = self.m.read_text()
        self.assertIn("gate_state: building\n---", text)
        self.assertIn("`gate_state: plan-approved` — in prose", text,
                      "the body must survive untouched")


class CheckTest(unittest.TestCase):
    """The CI/gate path: does the manifest match the tree?"""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="manifest-check-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.git("init", "-q")
        (self.d / "src").mkdir()
        (self.d / "src" / "config.py").write_text("DEFAULT = 30\n")
        self.cycle = self.d / ".sage" / "work" / "004-retry"
        self.cycle.mkdir(parents=True)
        self.m = self.cycle / "manifest.md"
        self.m.write_text(a_manifest("plan-approved"))
        self.commit("cycle: plan approved")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.d), *args],
                              capture_output=True, text=True, check=False)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", msg)

    def test_a_coherent_manifest_passes(self):
        self.assertEqual(M.check([self.m], self.d), 0,
                         "nothing has been implemented yet — plan-approved is true")

    def test_THE_BUG_a_manifest_that_denies_the_work_in_its_own_tree_fails(self):
        """L1 run 2, reproduced: work done and committed, manifest says it wasn't."""
        (self.d / "src" / "config.py").write_text(
            "DEFAULT = 30\nMAX_RETRIES = 3\n\ndef retry(op, sleeper):\n    return op()\n")
        self.commit("feat: implement the retry policy")

        self.assertEqual(M.check([self.m], self.d), 1,
                         "the manifest claims no tasks started; the tree disagrees")

    def test_uncommitted_work_counts_too(self):
        """An agent that writes a file and never commits it has still written it."""
        (self.d / "src" / "new_module.py").write_text("x = 1\n")
        self.assertEqual(M.check([self.m], self.d), 1)

    def test_sync_repairs_it(self):
        (self.d / "src" / "config.py").write_text("MAX_RETRIES = 3\n")
        self.commit("feat: work")
        old, new = M.sync(self.m, self.d)
        self.assertEqual((old, new), ("plan-approved", "building"))
        self.assertEqual(M.check([self.m], self.d), 0, "and now it is coherent")

    def test_an_illegal_gate_state_is_caught(self):
        """Three runs produced three vocabularies. Anything outside the enum is a bug,
        and until now nothing said so."""
        self.m.write_text(a_manifest("nearly-done"))
        self.assertEqual(M.check([self.m], self.d), 1)

    def test_every_legal_state_is_accepted(self):
        for s in M.GATE_STATES:
            self.m.write_text(a_manifest(s, status="in-progress"))
            # No implementation in the tree, so no coherence complaint is possible;
            # this asserts the enum itself is right.
            state, ok = M.read_gate_state(self.m.read_text())
            self.assertTrue(ok, f"{s} must be a legal gate_state")


class BlockedClaimTest(unittest.TestCase):
    """The L1 run-3 bug, half one: `status: blocked` was a free-text claim.

    Session 1 hedged, wrote 'blocked' into the manifest, and session 2 inherited
    the hesitation as law — refusing to finish under an explicit user instruction,
    while the recorded decision had already sanctioned the implementation shape.
    A blocker must now name its question, or `check` fails the manifest."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="manifest-blocked-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.m = self.d / "manifest.md"

    def _manifest(self, status, extra=""):
        return a_manifest("building", status=status).replace(
            "gate_state: building\n", f"gate_state: building\n{extra}")

    def test_blocked_without_blocked_on_fails_check(self):
        """THE BUG: the failing run's manifest, reproduced — blocked, no question."""
        self.m.write_text(self._manifest("blocked"))
        self.assertEqual(M.check([self.m], self.d), 1,
                         "an unnamed blocker must not survive check")

    def test_blocked_with_blocked_on_passes_check(self):
        self.m.write_text(self._manifest(
            "blocked",
            'blocked_on: "retry() signature — D-004-03 options A/B/C — user picks"\n'))
        self.assertEqual(M.check([self.m], self.d), 0)

    def test_in_progress_needs_no_blocked_on(self):
        self.m.write_text(self._manifest("in-progress"))
        self.assertEqual(M.check([self.m], self.d), 0)


class ResumeTest(unittest.TestCase):
    """The L1 run-3 bug, half two: the resume brief was prose, re-derived by each
    session, at 3-9x a bare agent's cost — and with the authority order inverted
    (manifest prose outranked the decisions log and the live user). The brief is
    generated now. Same files, same brief."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="manifest-resume-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.git("init", "-q")
        self.cycle = self.d / ".sage" / "work" / "004-retry"
        self.cycle.mkdir(parents=True)
        self.m = self.cycle / "manifest.md"

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.d), *args],
                              capture_output=True, text=True, check=False)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", msg)

    def brief(self, manifest=None):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = M.resume(self.d, manifest)
        self.assertEqual(code, 0, "resume is informational — always exit 0")
        return out.getvalue()

    def test_no_active_cycle(self):
        self.assertIn("no active cycle", self.brief())

    def test_the_brief_carries_the_authority_order(self):
        """The load-bearing lines. The failing run's session 2 obeyed a dead
        session's hedge over the live user's 'keep going' — the brief now states
        who outranks whom, next to the evidence."""
        self.m.write_text(a_manifest("building"))
        self.commit("cycle: begin")
        text = self.brief()
        self.assertIn("AUTHORITY ORDER", text)
        self.assertIn("context, NOT orders", text)
        self.assertIn("EVIDENCE", text)

    def test_the_brief_states_the_close_out_economy(self):
        """A resumed session is on the lean close-out path by construction — the
        brief tells it so, next to the authority order, so it finishes the delta
        instead of re-running the whole gate ceremony (2026-07-15 profile)."""
        self.m.write_text(a_manifest("building"))
        self.commit("cycle: begin")
        text = self.brief()
        self.assertIn("CLOSE-OUT ECONOMY", text)
        self.assertIn("combined", text)
        self.assertIn("Inherited red", text)

    def test_a_blocked_cycle_is_surfaced_not_skipped(self):
        self.m.write_text(a_manifest("building", status="blocked"))
        self.commit("cycle: begin")
        text = self.brief()
        self.assertIn("BLOCKED CLAIM", text)
        self.assertIn("UNVERIFIED", text,
                      "an unnamed blocker must be flagged as unverified")

    def test_a_completed_cycle_is_not_resumed(self):
        self.m.write_text(a_manifest("complete", status="complete"))
        self.commit("cycle: done")
        self.assertIn("no active cycle", self.brief())

    def test_another_checkouts_cycle_is_excluded(self):
        """Owner exclusion was prose in continue.workflow; now it is computed."""
        self.m.write_text(a_manifest("building").replace(
            "workflow: build\n", "workflow: build\nowner: /somewhere/else\n"))
        self.commit("cycle: begin")
        text = self.brief()
        self.assertIn("no active cycle", text)
        self.assertIn("owned by another checkout", text)

    def test_evidence_beats_prose(self):
        """A pre-implementation gate_state with work in the tree gets a WARNING
        line — the brief says 'trust the tree' instead of repeating the lie."""
        self.m.write_text(a_manifest("plan-approved"))
        self.commit("cycle: begin")
        (self.d / "src").mkdir()
        (self.d / "src" / "config.py").write_text("MAX_RETRIES = 3\n")
        self.commit("feat: task 1")
        text = self.brief()
        self.assertIn("WARNING", text)
        self.assertIn("trust the tree", text.lower())

    def test_plan_tasks_and_decisions_are_listed(self):
        self.m.write_text(a_manifest("building"))
        (self.cycle / "plan.md").write_text(
            "# Plan\n\n## Task 1 — MAX_RETRIES\n\n## Task 2 — backoff_delay()\n")
        (self.d / ".sage" / "decisions.md").write_text(
            "# Decisions\n\n## D-002 — No blocking sleeps in library code\n")
        self.commit("cycle: begin")
        text = self.brief()
        self.assertIn("Task 1 — MAX_RETRIES", text)
        self.assertIn("D-002 — No blocking sleeps", text)

    def test_multiple_cycles_ask_the_user(self):
        other = self.d / ".sage" / "work" / "005-other"
        other.mkdir(parents=True)
        (other / "manifest.md").write_text(a_manifest("building"))
        self.m.write_text(a_manifest("building"))
        self.commit("cycles: two at once")
        text = self.brief()
        self.assertIn("Ask the user", text)
        self.assertIn("004-retry", text)
        self.assertIn("005-other", text)

    def test_open_lanes_are_listed_with_the_harvest_path(self):
        """A7's resume fixture: a session that died mid-burst left lanes on
        disk. The brief lists them from the lanes: block — an unlisted
        worktree is work that silently rots — and names the harvesting
        remove, never the bare one."""
        self.m.write_text(a_manifest("building").replace(
            "---\n\n# Cycle",
            "lanes:\n"
            '  burst_base: "abc1234"\n'
            "  records:\n"
            '    - {task: T2, branch: "lane/t2-auth", worktree: "../wt-t2", '
            'state: open, model: "cheap/model"}\n'
            '    - {task: T3, branch: "lane/t3-ses", worktree: "../wt-t3", '
            'state: parked, model: "inherit", note: "waiting on decision"}\n'
            '    - {task: T1, branch: "lane/t1-types", worktree: "../wt-t1", '
            'state: merged, model: "inherit"}\n'
            "---\n\n# Cycle"))
        self.commit("cycle: begin")
        text = self.brief()
        self.assertIn("OPEN LANES", text)
        self.assertIn("burst base: abc1234", text)
        self.assertIn("T2 [open] branch lane/t2-auth", text)
        self.assertIn("T3 [parked]", text)
        self.assertIn("waiting on decision", text)
        self.assertNotIn("T1 [merged]", text, "merged lanes are not open")
        self.assertIn("sage worktree remove", text)

    def test_no_lanes_block_no_lanes_section(self):
        self.m.write_text(a_manifest("building"))
        self.commit("cycle: begin")
        self.assertNotIn("OPEN LANES", self.brief())

    def test_pyc_droppings_are_not_source(self):
        """__pycache__ noise polluted the first real brief's evidence line, and a
        .pyc write must never flip a cycle to building either."""
        for p in ("src/__pycache__/config.cpython-312.pyc", "src/app.pyc"):
            self.assertFalse(M.is_source(p), f"{p} is not source")
        self.assertTrue(M.is_source("src/config.py"))


def a_manifest_with_body(gate_state="building") -> str:
    """A manifest with the sections close-out writes, plus an updated: field."""
    return (
        "---\n"
        'cycle_id: "20260715-close-out"\n'
        "workflow: build\n"
        "phase: implement\n"
        "status: in-progress\n"
        "gate_state: %s\n"
        "updated: 2026-07-01 00:00\n"
        "---\n\n"
        "# Cycle: Close-out\n\n"
        "## State\n\n"
        "**Current phase:** implement\n"
        "**Next step:** finish Task 3\n\n"
        "## Context summary\n\n"
        "Old summary that should be replaced.\n"
        "The body quotes `status: in-progress` and `updated: 2026-07-01 00:00`.\n\n"
        "## Open questions\n\n"
        "- old question\n" % gate_state
    )


class CloseOutTest(unittest.TestCase):
    """The bookkeeping write is ONE command now. The 2026-07-15 profile found the
    model making 8 incremental manifest/decisions/plan edits per resume session
    (~29% of its cost) — batch_bookkeeping asked it to stop, in prose, and it
    didn't. Same lesson as gate_state: make it code."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="manifest-closeout-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.m = self.d / "manifest.md"
        self.m.write_text(a_manifest_with_body())

    def test_one_pass_writes_summary_next_step_and_stamps_updated(self):
        M.close_out(self.m, summary="New summary from the close-out.",
                    next_step="present the completion checkpoint")
        text = self.m.read_text()
        self.assertIn("New summary from the close-out.", text)
        self.assertNotIn("Old summary that should be replaced.", text)
        self.assertIn("**Next step:** present the completion checkpoint", text)
        fm, _ = M.split_frontmatter(text)
        self.assertNotIn("updated: 2026-07-01 00:00", fm,
                         "updated: must be stamped by the machine")

    def test_body_prose_quoting_fields_is_not_rewritten(self):
        """Same rule as write_gate_state: the body's narration is the agent's."""
        M.close_out(self.m, status="paused")
        text = self.m.read_text()
        self.assertIn("The body quotes `status: in-progress`", text)
        fm, _ = M.split_frontmatter(text)
        self.assertIn("status: paused", fm)

    def test_decisions_prepend_below_title(self):
        (self.d / "decisions.md").write_text("# Decisions\n\n### 2026-07-01 — Old\n")
        M.close_out(self.m, decisions=["D-9: retry helper computes, caller waits"])
        dtext = (self.d / "decisions.md").read_text()
        self.assertTrue(dtext.startswith("# Decisions\n"))
        self.assertLess(dtext.index("D-9"), dtext.index("Old"),
                        "new decision must be PREPENDED (Rule 7)")

    def test_decisions_file_created_when_absent(self):
        M.close_out(self.m, decisions=["D-1: first"])
        self.assertIn("D-1: first", (self.d / "decisions.md").read_text())

    def test_plan_checkbox_bulk_check(self):
        (self.d / "plan.md").write_text(
            "# Plan\n\n- [x] **Task 1:** done before\n"
            "- [ ] **Task 2:** middle\n- [ ] **Task 3:** last\n")
        M.close_out(self.m, complete_tasks=[2, 3])
        ptext = (self.d / "plan.md").read_text()
        self.assertIn("- [x] **Task 2:**", ptext)
        self.assertIn("- [x] **Task 3:**", ptext)

    def test_missing_task_is_a_note_not_a_crash(self):
        (self.d / "plan.md").write_text("# Plan\n\n- [ ] **Task 1:** only\n")
        rc = M.close_out(self.m, complete_tasks=[1, 7])
        self.assertEqual(rc, 0)
        self.assertIn("- [x] **Task 1:**", (self.d / "plan.md").read_text())

    def test_replace_section_appends_when_absent(self):
        out = M.replace_section("# T\n\n## Other\n\nx\n", "Handoff guidance", "take over")
        self.assertIn("## Handoff guidance", out)
        self.assertIn("take over", out)

    def test_blocked_on_can_be_set_in_the_same_pass(self):
        """The bookkeeping gate redirects hand-edits to close-out — so close-out
        must be able to record a blocker, or the gate would trap the one write
        `check` requires (status: blocked needs blocked_on:)."""
        self.m.write_text(a_manifest_with_body().replace(
            "status: in-progress", "status: in-progress\nblocked_on: \"\""))
        M.close_out(self.m, status="blocked",
                    blocked_on="ship or defer the retry helper — user's call")
        text = self.m.read_text()
        fm, _ = M.split_frontmatter(text)
        self.assertIn("status: blocked", fm)
        self.assertIn("ship or defer the retry helper", fm)

    def test_write_field_refuses_an_absent_field(self):
        with self.assertRaises(M.Problem):
            M.write_field(a_manifest(), "no_such_field", "x")


class UpdatedStampTest(unittest.TestCase):
    """advance/sync own updated: now — one less field the model maintains."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="manifest-stamp-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.m = self.d / "manifest.md"

    def test_advance_stamps_updated_when_field_exists(self):
        self.m.write_text(a_manifest_with_body(gate_state="plan-approved"))
        old, new = M.advance(self.m, "src/config.py")
        self.assertEqual(new, "building")
        fm, _ = M.split_frontmatter(self.m.read_text())
        self.assertNotIn("updated: 2026-07-01 00:00", fm)

    def test_advance_is_fail_soft_without_the_field(self):
        """A pre-template manifest without updated: must still advance."""
        self.m.write_text(a_manifest("plan-approved"))
        old, new = M.advance(self.m, "src/config.py")
        self.assertEqual(new, "building")


A_PLAN = """\
# Implementation Plan: refresh flow

## Tasks

- [ ] **Task 1:** harden refresh flow
  - **Files:** src/auth/**, ./src\\session.ts
  - **Action:** do the work
  - **Test:** tests/auth/test_refresh.py
- [ ] **Task 2:** witness tests
  - **Files:** tests/auth/**
- [ ] **Task 3:** write the runbook [DOC]
  - **Output:** docs/runbook.md
- [x] **Task 4:** the undeclared one
  - **Action:** no Files line at all
- [ ] **Task 5:** template junk survives review sometimes
  - **Files:** {exact_file_paths}
"""


class ScopeTest(unittest.TestCase):
    """SG-1/SG-2 — declared scope becomes machine state, amended only through
    the tool, never silently through the diff."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="manifest-scope-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.m = self.d / "manifest.md"
        self.m.write_text(a_manifest("plan-approved"))
        (self.d / "plan.md").write_text(A_PLAN)

    def test_derive_parses_files_and_output_lines_normalized(self):
        """Globs are posix, repo-relative, per-task attributed. Windows
        separators and ./ prefixes are normalized, [DOC] Output: lines count,
        template placeholders are rejected rather than becoming globs."""
        M.scope_derive(self.m)
        scope = M.read_scope(self.m.read_text())
        self.assertIsNotNone(scope)
        globs = [(g, t) for g, t, _ in scope["globs"]]
        self.assertIn(("src/auth/**", 1), globs)
        self.assertIn(("src/session.ts", 1), globs)
        self.assertIn(("tests/auth/**", 2), globs)
        self.assertIn(("docs/runbook.md", 3), globs)
        self.assertNotIn("{exact_file_paths}", [g for g, _ in globs])
        self.assertTrue((scope["derived_from"] or "").startswith("plan@"))
        self.assertEqual(scope["collateral"], [])

    def test_derive_warns_on_an_undeclared_task_and_does_not_guess(self):
        """A task with no Files:/Output: is a plan-review finding (SG-8). The
        derivation reports it and contributes NOTHING for that task."""
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            M.scope_derive(self.m)
        out = buf.getvalue()
        self.assertIn("Task 4", out)
        self.assertIn("NOTHING", out)
        self.assertIn("{exact_file_paths}", out)

    def test_derive_refuses_paths_that_escape_the_repo(self):
        (self.d / "plan.md").write_text(
            "- [ ] **Task 1:** sneaky\n"
            "  - **Files:** ../outside.ts, /etc/passwd, src/ok.ts\n")
        M.scope_derive(self.m)
        scope = M.read_scope(self.m.read_text())
        self.assertEqual([g for g, _, _ in scope["globs"]], ["src/ok.ts"],
                         "absolute paths warn, not silently relativize")

    def test_read_scope_keeps_quoted_globs_and_plain_comments(self):
        """Review #8/#16: YAML quotes are stripped, and an entry with a
        non-attribution comment stays in scope — the gate's reader and this
        one must agree."""
        self.m.write_text(a_manifest("plan-approved").replace(
            "---\n\n# Cycle",
            "scope:\n  derived_from: plan@aa\n  globs:\n"
            "    - \"src/auth/**\"  # T1 quoted\n"
            "    - src/session.ts  # just a note\n"
            "  collateral: []\n---\n\n# Cycle"))
        scope = M.read_scope(self.m.read_text())
        self.assertEqual([(g, t) for g, t, _ in scope["globs"]],
                         [("src/auth/**", 1), ("src/session.ts", None)])

    def test_add_collateral_writes_entry_and_decisions_line(self):
        """The two-writes-in-one-command pattern: the entry lands in the
        manifest AND the decisions.md line is written by the tool itself —
        the record is taken, not requested."""
        M.scope_derive(self.m)
        M.scope_add_collateral(self.m, "src/billing/types.ts",
                               task="T1", reason="shared type moved")
        scope = M.read_scope(self.m.read_text())
        self.assertEqual([(g, t) for g, t, _ in scope["collateral"]],
                         [("src/billing/types.ts", 1)])
        decisions = (self.d / "decisions.md").read_text()
        self.assertIn("scope collateral: src/billing/types.ts", decisions)
        self.assertIn("shared type moved", decisions)

    def test_add_collateral_refuses_an_empty_reason(self):
        M.scope_derive(self.m)
        with self.assertRaises(M.Problem):
            M.scope_add_collateral(self.m, "src/x.ts", task="T1", reason="   ")

    def test_add_collateral_refuses_a_scope_wide_grant(self):
        """Found by an adversarial probe: `add-collateral '**'` opened the
        gate for everything, recorded or not. Collateral must carry a literal
        path prefix — the whole tree goes through the plan, not this tool."""
        M.scope_derive(self.m)
        for grab in ("**", "*", "**/*", "[ab]/x.ts", "?src/x.ts"):
            with self.assertRaises(M.Problem, msg=grab):
                M.scope_add_collateral(self.m, grab, task="T1", reason="mine now")
        M.scope_add_collateral(self.m, "src/billing/**", task="T1",
                               reason="a real prefix is fine")

    def test_add_collateral_requires_a_derived_scope_first(self):
        with self.assertRaises(M.Problem):
            M.scope_add_collateral(self.m, "src/x.ts", task="T1", reason="r")

    def test_derive_refuses_to_silently_rederive(self):
        """A second bare derive is a Problem: re-deriving is legal only as the
        DELIBERATE --refresh, whose delta is recorded."""
        M.scope_derive(self.m)
        with self.assertRaises(M.Problem):
            M.scope_derive(self.m)

    def test_refresh_records_the_expansion_delta_and_keeps_collateral(self):
        """RR-24's spirit applied to scope: the plan is amended, the scope is
        re-derived, and the old→new delta lands in decisions.md. Collateral
        recorded against this cycle survives the re-derive."""
        M.scope_derive(self.m)
        M.scope_add_collateral(self.m, "src/kept.ts", task="T1", reason="keep me")
        old = M.read_scope(self.m.read_text())["derived_from"]
        plan = self.d / "plan.md"
        plan.write_text(plan.read_text().replace(
            "tests/auth/**", "tests/auth/**, src/newly/approved.ts"))
        M.scope_derive(self.m, refresh=True)
        scope = M.read_scope(self.m.read_text())
        self.assertNotEqual(scope["derived_from"], old)
        self.assertIn("src/newly/approved.ts", [g for g, _, _ in scope["globs"]])
        self.assertIn("src/kept.ts", [g for g, _, _ in scope["collateral"]])
        decisions = (self.d / "decisions.md").read_text()
        self.assertIn(f"scope expanded: {old}", decisions)
        self.assertIn(scope["derived_from"], decisions)
        self.assertIn("src/newly/approved.ts", decisions,
                      "the record names WHAT became sanctioned — a grader "
                      "(and a human) must be able to match the path")

    def test_refresh_with_no_plan_change_records_nothing(self):
        M.scope_derive(self.m)
        M.scope_derive(self.m, refresh=True)
        self.assertFalse((self.d / "decisions.md").is_file())

    def test_bookkeeping_edits_do_not_move_the_plan_hash(self):
        """Round-3: the hash covers only the Files:/Output: lines. Checking a
        box or stamping ✅ DONE is close-out bookkeeping — it must not mark
        the scope stale (a whole-file hash meant warn-per-edit forever after
        the first completed task)."""
        before = M._plan_sha(A_PLAN)
        ticked = A_PLAN.replace("- [ ] **Task 1:**",
                                "- [x] **Task 1:**") + "\n✅ DONE (commit: abc)\n"
        self.assertEqual(M._plan_sha(ticked), before)
        rescoped = A_PLAN.replace("  - **Files:** tests/auth/**",
                                  "  - **Files:** tests/auth/**, src/new.ts")
        self.assertNotEqual(M._plan_sha(rescoped), before)

    def test_the_block_lives_in_the_frontmatter_only(self):
        """Body prose that mentions scope is narration, not machine state."""
        self.m.write_text(a_manifest("plan-approved")
                          + "\nThe scope: block is discussed here in prose.\n")
        M.scope_derive(self.m)
        fm, _ = M.split_frontmatter(self.m.read_text())
        self.assertIn("derived_from: plan@", fm)
        self.assertIn("The scope: block is discussed here in prose.",
                      self.m.read_text())

    def test_cli_add_collateral_refuses_missing_reason(self):
        """argparse makes --reason mandatory — the CLI cannot take collateral
        without a recorded why."""
        with self.assertRaises(SystemExit) as ctx:
            M.main(["scope", "add-collateral", "src/x.ts", "--task", "T1",
                    "--manifest", str(self.m)])
        self.assertEqual(ctx.exception.code, 2)


A_GRAPH_PLAN = """\
# Implementation Plan: parallel refresh

## Tasks

- [ ] **Task 1:** contract types
  - **Files:** src/types.ts
  - **Action:** define the contract first
  - **Depends on:** none
- [ ] **Task 2:** auth flow [P]
  - **Files:** src/auth/**, `src/auth.ts`
  - **Depends on:** T1
- [ ] **Task 3:** session flow [P]
  - **Files:** src/session.ts
  - **Depends on:** T1
- [ ] **Task 4:** the runbook [DOC] [P]
  - **Output:** docs/runbook.md
  - **Depends on:** Task 2, T3
"""


class GraphTest(unittest.TestCase):
    """A8 — the plan's task structure becomes machine state, fail-closed.
    A wrong graph dispatches coupled tasks into concurrent lanes, so unlike
    scope (warn-and-continue) ANY defect refuses the whole derivation."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="manifest-graph-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.m = self.d / "manifest.md"
        self.m.write_text(a_manifest("plan-approved"))
        self.plan = self.d / "plan.md"
        self.plan.write_text(A_GRAPH_PLAN)

    def derive(self, expect=0):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = M.graph_derive(self.m)
        self.assertEqual(rc, expect, buf.getvalue())
        return buf.getvalue()

    def refuse(self, *needles):
        """Fail-closed contract: nonzero, every needle surfaced as a
        plan-review finding, and NO task_graph block written."""
        out = self.derive(expect=1)
        for needle in needles:
            self.assertIn(needle, out)
        self.assertIn("plan-review finding:", out)
        self.assertIn("NOT derived", out)
        self.assertIsNone(M.read_task_graph(self.m.read_text()))
        return out

    def test_happy_path_round_trip(self):
        """Markers strip into flags, backticks normalize, both `T1` and
        `Task 1` reference forms resolve, and the reader returns exactly
        what the writer pinned."""
        M.scope_derive(self.m)
        self.derive()
        g = M.read_task_graph(self.m.read_text())
        self.assertIsNotNone(g)
        self.assertTrue((g["derived_from"] or "").startswith("plan@"))
        self.assertEqual([t["id"] for t in g["tasks"]], [1, 2, 3, 4])
        by_id = {t["id"]: t for t in g["tasks"]}
        self.assertEqual(by_id[1]["depends"], [])
        self.assertFalse(by_id[1]["parallel"])
        self.assertEqual(by_id[2]["files"], ["src/auth/**", "src/auth.ts"])
        self.assertTrue(by_id[2]["parallel"])
        self.assertEqual(by_id[4]["depends"], [2, 3])
        self.assertTrue(by_id[4]["parallel"])
        self.assertEqual(by_id[4]["title"], "the runbook",
                         "[DOC]/[P] are markers, not title")
        self.assertEqual(by_id[4]["files"], ["docs/runbook.md"])

    def test_derive_requires_a_derived_scope_first(self):
        self.refuse("no derived scope")

    def test_unknown_depends_reference_refuses(self):
        M.scope_derive(self.m)
        self.plan.write_text(A_GRAPH_PLAN.replace(
            "  - **Depends on:** T1\n- [ ] **Task 3:**",
            "  - **Depends on:** T9\n- [ ] **Task 3:**"))
        M.scope_derive(self.m, refresh=True)
        self.refuse("Task 2 depends on T9, which does not exist")

    def test_ambiguous_depends_refuses(self):
        M.scope_derive(self.m)
        self.plan.write_text(A_GRAPH_PLAN.replace(
            "**Depends on:** Task 2, T3", "**Depends on:** the auth task"))
        self.refuse("is ambiguous", "none | T<n>")

    def test_missing_depends_line_refuses_rather_than_guessing(self):
        M.scope_derive(self.m)
        self.plan.write_text(A_GRAPH_PLAN.replace(
            "  - **Depends on:** none\n", ""))
        self.refuse("Task 1 declares no `Depends on:`",
                    "does not guess ordering")

    def test_missing_files_refuses(self):
        M.scope_derive(self.m)
        self.plan.write_text(A_GRAPH_PLAN.replace(
            "  - **Files:** src/session.ts\n", ""))
        M.scope_derive(self.m, refresh=True)
        self.refuse("Task 3 declares no Files:")

    def test_placeholder_files_refuse(self):
        """The template's own {exact_file_paths} placeholder must refuse,
        not silently become an empty lane."""
        M.scope_derive(self.m)
        self.plan.write_text(A_GRAPH_PLAN.replace(
            "**Files:** src/session.ts", "**Files:** {exact_file_paths}"))
        M.scope_derive(self.m, refresh=True)
        self.refuse("Task 3 declares only unusable")

    def test_malformed_P_marker_refuses(self):
        M.scope_derive(self.m)
        for bad in ("auth flow [p]", "auth [P] flow", "auth flow [ P ]"):
            self.plan.write_text(A_GRAPH_PLAN.replace("auth flow [P]", bad))
            self.refuse("malformed [P] marker")

    def test_dependency_cycle_refuses(self):
        M.scope_derive(self.m)
        # T2 → T3 and T3 → T2 (the two `Depends on: T1` lines belong to T2
        # then T3, in plan order).
        cyclic = A_GRAPH_PLAN.replace("  - **Depends on:** T1",
                                      "  - **Depends on:** T3", 1)
        cyclic = cyclic.replace("  - **Depends on:** T1",
                                "  - **Depends on:** T2", 1)
        self.plan.write_text(cyclic)
        out = self.refuse("dependency cycle:")
        self.assertIn("T2", out)
        self.assertIn("T3", out)

    def test_self_dependency_is_a_cycle(self):
        M.scope_derive(self.m)
        self.plan.write_text(A_GRAPH_PLAN.replace(
            "  - **Depends on:** none", "  - **Depends on:** T1"))
        self.refuse("dependency cycle: T1 → T1")

    def test_duplicate_task_id_refuses(self):
        M.scope_derive(self.m)
        self.plan.write_text(A_GRAPH_PLAN.replace(
            "**Task 3:** session flow [P]", "**Task 2:** session flow [P]"))
        self.refuse("Task 2 appears more than once")

    def test_E9_replay_fenced_examples_are_not_tasks(self):
        """The E9 lesson as a fixture: a plan whose prose a naive regex
        misreads must derive correctly or refuse — never derive wrong
        silently. Fenced snippets quoting task syntax stay prose."""
        self.plan.write_text(A_GRAPH_PLAN + """
## Notes

```markdown
- [ ] **Task 9:** phantom from a quoted example
  - **Files:** src/phantom.ts
  - **Depends on:** T1
```
<!-- - [ ] **Task 10:** phantom from a comment
  - **Depends on:** T9 -->
""")
        M.scope_derive(self.m)
        self.derive()
        g = M.read_task_graph(self.m.read_text())
        self.assertEqual([t["id"] for t in g["tasks"]], [1, 2, 3, 4],
                         "phantom tasks in fences/comments must not parse")

    def test_E9_replay_indented_code_blocks_are_not_tasks_either(self):
        """Review finding 5: markdown's OTHER code form — the 4-space
        indented block — also must not mint phantom nodes."""
        self.plan.write_text(A_GRAPH_PLAN + """
## Notes

An example, as an indented code block:

    - [ ] **Task 9:** phantom from an indented example
      - **Files:** src/types.ts
      - **Depends on:** none
""")
        M.scope_derive(self.m)
        self.derive()
        g = M.read_task_graph(self.m.read_text())
        self.assertEqual([t["id"] for t in g["tasks"]], [1, 2, 3, 4])

    def test_character_class_glob_survives_the_round_trip(self):
        """Review finding 2: a legal fnmatch class carries a `]`, and the
        bracket-hungry reader silently dropped the whole task — writer and
        reader must agree on every glob the normalizer accepts."""
        self.plan.write_text(A_GRAPH_PLAN.replace(
            "**Files:** src/session.ts", "**Files:** src/test_[0-9].py"))
        M.scope_derive(self.m)
        self.derive()
        g = M.read_task_graph(self.m.read_text())
        self.assertEqual([t["id"] for t in g["tasks"]], [1, 2, 3, 4])
        self.assertEqual({t["id"]: t for t in g["tasks"]}[3]["files"],
                         ["src/test_[0-9].py"])

    def test_rederive_refused_without_refresh(self):
        M.scope_derive(self.m)
        self.derive()
        with self.assertRaises(M.Problem):
            M.graph_derive(self.m)

    def test_renumber_after_amend_rederives_and_records_the_delta(self):
        """The scope-derivation pattern applied to the graph: plan amended
        (a task inserted, successors renumbered), --refresh re-derives, and
        the old→new delta lands in decisions.md."""
        M.scope_derive(self.m)
        self.derive()
        old = M.read_task_graph(self.m.read_text())["derived_from"]
        amended = A_GRAPH_PLAN.replace(
            "- [ ] **Task 4:** the runbook [DOC] [P]\n"
            "  - **Output:** docs/runbook.md\n"
            "  - **Depends on:** Task 2, T3",
            "- [ ] **Task 4:** wire the flows\n"
            "  - **Files:** src/wiring.ts\n"
            "  - **Depends on:** T2, T3\n"
            "- [ ] **Task 5:** the runbook [DOC] [P]\n"
            "  - **Output:** docs/runbook.md\n"
            "  - **Depends on:** T4")
        self.plan.write_text(amended)
        M.scope_derive(self.m, refresh=True)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = M.graph_derive(self.m, refresh=True)
        self.assertEqual(rc, 0, buf.getvalue())
        g = M.read_task_graph(self.m.read_text())
        self.assertNotEqual(g["derived_from"], old)
        self.assertEqual([t["id"] for t in g["tasks"]], [1, 2, 3, 4, 5])
        self.assertEqual({t["id"]: t for t in g["tasks"]}[5]["depends"], [4])
        decisions = (self.d / "decisions.md").read_text()
        self.assertIn(f"task graph re-derived: {old}", decisions)
        self.assertIn(g["derived_from"], decisions)
        self.assertIn("+T5", decisions)

    def test_refresh_with_no_change_records_nothing(self):
        M.scope_derive(self.m)
        self.derive()
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            M.graph_derive(self.m, refresh=True)
        self.assertFalse((self.d / "decisions.md").is_file())

    def test_stale_scope_refuses(self):
        """Graph↔scope consistency: amend the plan's declarations after
        scope derive and the graph refuses until scope re-derives — lanes
        must not dispatch under a scope gate policing the wrong contract."""
        M.scope_derive(self.m)
        self.plan.write_text(A_GRAPH_PLAN.replace(
            "**Files:** src/session.ts", "**Files:** src/session2.ts"))
        self.refuse("scope is stale", "scope derive --refresh")

    def test_files_outside_scope_refuse(self):
        M.scope_derive(self.m)
        # Simulate a hand-damaged scope block: same pin, an entry missing.
        text = self.m.read_text()
        line = next(l for l in text.splitlines()
                    if l.strip().startswith("- src/session.ts"))
        self.m.write_text(text.replace(line + "\n", ""))
        self.refuse("Task 3's files (src/session.ts) are not in the "
                    "derived scope")

    def test_bookkeeping_edits_do_not_move_the_graph_sha(self):
        """Checking a box or stamping ✅ DONE must not mark the graph stale;
        renumbering, a [P] change, or an edge change must."""
        before = M._graph_sha(A_GRAPH_PLAN)
        ticked = A_GRAPH_PLAN.replace(
            "- [ ] **Task 1:** contract types",
            "- [x] **Task 1:** contract types ✅ DONE (commit: abc1234)")
        self.assertEqual(M._graph_sha(ticked), before)
        self.assertNotEqual(
            M._graph_sha(A_GRAPH_PLAN.replace("session flow [P]",
                                              "session flow")), before)
        self.assertNotEqual(
            M._graph_sha(A_GRAPH_PLAN.replace("**Depends on:** Task 2, T3",
                                              "**Depends on:** T3")), before)

    def test_the_block_lives_in_the_frontmatter_only(self):
        self.m.write_text(a_manifest("plan-approved")
                          + "\nProse discussing the task_graph: block.\n")
        M.scope_derive(self.m)
        self.derive()
        fm, _ = M.split_frontmatter(self.m.read_text())
        self.assertIn("task_graph:", fm)
        self.assertIn("Prose discussing the task_graph: block.",
                      self.m.read_text())

    def test_no_plan_is_a_problem(self):
        self.plan.unlink()
        with self.assertRaises(M.Problem):
            M.graph_derive(self.m)

    def test_cli_exit_codes(self):
        """Findings exit 1 through main() — the workflow's degradation
        branch keys off the exit code."""
        self.assertEqual(M.main(["graph", "derive", str(self.m)]), 1)
        M.scope_derive(self.m)
        self.assertEqual(M.main(["graph", "derive", str(self.m)]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
