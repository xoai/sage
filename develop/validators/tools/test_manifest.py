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


if __name__ == "__main__":
    unittest.main(verbosity=2)
