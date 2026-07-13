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


if __name__ == "__main__":
    unittest.main(verbosity=2)
