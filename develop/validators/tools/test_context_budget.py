#!/usr/bin/env python3
"""
test_context_budget.py — tests for runtime/tools/context_budget.py (13-§31).

The budget tool is a ratchet, and a ratchet that can slip is worse than none: it
would certify growth it never actually looked at. So the cases that matter are
the ones where it must FAIL — over budget, and (the subtler one) a generated file
with no budget entry at all, which would otherwise grow forever unwatched.

Usage:  python3 develop/validators/tools/test_context_budget.py
Exit:   0 = all pass | 1 = a test failed

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import importlib.util
import io
import contextlib
import pathlib
import shutil
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
CB_PY = REPO_ROOT / "runtime" / "tools" / "context_budget.py"

spec = importlib.util.spec_from_file_location("context_budget", CB_PY)
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)


class BudgetFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def write(self, text: str) -> pathlib.Path:
        p = self.dir / "budgets.yaml"
        p.write_text(text)
        return p

    def test_reads_sections_and_ints(self):
        b = cb.read_budgets(self.write(
            "eager:\n  CLAUDE.md: 430\ncommands:\n  build: 580\n"))
        self.assertEqual(b["eager"]["CLAUDE.md"], 430)
        self.assertEqual(b["commands"]["build"], 580)

    def test_ignores_comments_and_blanks(self):
        b = cb.read_budgets(self.write(
            "# a comment\n\neager:\n  # why 430\n  CLAUDE.md: 430  # trailing\n"))
        self.assertEqual(b["eager"]["CLAUDE.md"], 430)

    def test_rejects_a_non_integer_budget(self):
        """A budget that is not a number is not a budget."""
        with self.assertRaises(cb.BudgetError):
            cb.read_budgets(self.write("eager:\n  CLAUDE.md: lots\n"))

    def test_rejects_an_entry_outside_any_section(self):
        with self.assertRaises(cb.BudgetError):
            cb.read_budgets(self.write("  CLAUDE.md: 430\n"))

    def test_rejects_a_missing_file(self):
        with self.assertRaises(cb.BudgetError):
            cb.read_budgets(self.dir / "nope.yaml")


class CheckTest(unittest.TestCase):
    BUDGETS = {"eager": {"CLAUDE.md": 430}, "commands": {"build": 580}}

    def check(self, data, budgets=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cb.check(data, budgets or self.BUDGETS)
        return rc, buf.getvalue()

    def test_within_budget_passes(self):
        rc, _ = self.check({
            "eager": {"CLAUDE.md": {"lines": 398, "tokens": 4433, "bytes": 0}},
            "commands": {"build": {"lines": 535, "tokens": 5888, "bytes": 0}},
        })
        self.assertEqual(rc, 0)

    def test_over_budget_fails_and_names_the_overage(self):
        rc, out = self.check({
            "eager": {"CLAUDE.md": {"lines": 498, "tokens": 5000, "bytes": 0}},
            "commands": {"build": {"lines": 535, "tokens": 5888, "bytes": 0}},
        })
        self.assertEqual(rc, 1)
        self.assertIn("CLAUDE.md", out)
        self.assertIn("+68", out)

    def test_exactly_on_budget_passes(self):
        rc, _ = self.check({
            "eager": {"CLAUDE.md": {"lines": 430, "tokens": 0, "bytes": 0}},
            "commands": {"build": {"lines": 580, "tokens": 0, "bytes": 0}},
        })
        self.assertEqual(rc, 0)

    def test_an_unbudgeted_file_fails(self):
        """A new command with no budget would grow forever, unwatched. The
        ratchet has to notice things it has never seen."""
        rc, out = self.check({
            "eager": {"CLAUDE.md": {"lines": 398, "tokens": 0, "bytes": 0}},
            "commands": {"build": {"lines": 535, "tokens": 0, "bytes": 0},
                         "brand-new": {"lines": 900, "tokens": 0, "bytes": 0}},
        })
        self.assertEqual(rc, 1)
        self.assertIn("brand-new", out)


class MeasureTest(unittest.TestCase):
    def test_measure_counts_lines_and_estimates_tokens(self):
        d = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        f = d / "x.md"
        f.write_text("abcd\nefgh\n")          # 10 chars → 2 tokens at chars/4
        m = cb.measure(f)
        self.assertEqual(m["lines"], 2)
        self.assertEqual(m["tokens"], 10 // cb.CHARS_PER_TOKEN)


class RealProjectTest(unittest.TestCase):
    """The numbers in budgets.yaml describe the tree as it is right now."""

    def _generate(self, tmp, platform="claude-code"):
        return cb.collect(cb.generate_project(cb.make_home(tmp), tmp, platform))

    def test_the_repo_is_within_its_own_budgets(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="cb-real-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        data = self._generate(tmp)
        budgets = cb.read_budgets(cb.BUDGETS)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cb.check(data, budgets)
        self.assertEqual(rc, 0, buf.getvalue())

    def test_the_eager_layer_is_actually_generated(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="cb-real-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        data = self._generate(tmp)
        self.assertIn("CLAUDE.md", data["eager"])
        self.assertGreater(data["eager"]["CLAUDE.md"]["lines"], 0)

    def test_system_skills_are_measured_not_just_shipped(self):
        """The diet must not be winnable by moving cost somewhere nobody counts.

        If ADR-9's content leaves the eager layer and lands in a skill that no
        instrument points at, "we cut the eager layer by 70%" stays true while the
        total goes up. This test is the reason the `skills:` section exists.
        """
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="cb-skills-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        data = self._generate(tmp)
        self.assertTrue(data["skills"], "no system skills were measured")
        self.assertIn("sage-routing", data["skills"])
        self.assertGreater(data["skills"]["sage-routing"]["lines"], 0)

    def test_generic_inlines_what_claude_code_fetches(self):
        """Capability-gated delivery, asserted rather than assumed (ADR-11).

        Generic has no skill discovery, so the same content must be INLINED — and
        its instructions file must therefore be substantially larger. If this ever
        fails, generic is silently shipping an instructions file that references
        skills it cannot load.
        """
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="cb-generic-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        home = cb.make_home(tmp)

        cc = cb.collect(cb.generate_project(home, tmp, "claude-code"))
        gp = cb.generate_project(home, tmp, "generic")
        generic_md = gp / "CLAUDE.md"

        self.assertTrue(generic_md.is_file(), "generic generated no instructions file")
        self.assertFalse((gp / ".claude" / "skills").is_dir(),
                         "generic emitted skills it has no mechanism to discover")

        generic_lines = len(generic_md.read_text().splitlines())
        self.assertGreater(generic_lines, cc["eager"]["CLAUDE.md"]["lines"],
                           "generic must inline what claude-code fetches on demand")


if __name__ == "__main__":
    unittest.main(verbosity=2)
