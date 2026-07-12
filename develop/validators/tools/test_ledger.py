"""The ledger must be generated, not remembered. E9 is why."""
import pathlib, subprocess, sys, tempfile, unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
LEDGER = REPO / "runtime" / "tools" / "ledger.py"

PLAN = """# Plan

## Task 1 — MAX_RETRIES
Files: src/config.py

## Task 2 — get_timeout()
Files: src/config.py

## Task 3 — validate_config()
Files: src/config.py
"""

def run(*args):
    return subprocess.run([sys.executable, str(LEDGER), *args],
                          capture_output=True, text=True)

class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())
        (self.d / "plan.md").write_text(PLAN)
        (self.d / "manifest.md").write_text(
            '---\ncycle_id: "t"\ngate_state: plan-approved\n---\n\n# Cycle\n')

    def m(self): return str(self.d / "manifest.md")
    def p(self): return str(self.d / "plan.md")

    def test_ledger_is_generated_from_the_plan(self):
        """The whole point. E9: asked to write this from prose, the orchestrator
        did not, in 2 runs of 3 — and those runs looked like success."""
        r = run("init", self.m(), self.p())
        self.assertEqual(r.returncode, 0, r.stderr)
        fm = (self.d / "manifest.md").read_text()
        self.assertIn("tasks:", fm)
        self.assertEqual(fm.count("- id:"), 3)
        self.assertIn("status: pending", fm)
        self.assertIn("review: pending", fm)

    def test_it_arms_the_guard(self):
        """A ledger without execution_mode: subagent is a ledger the H41 guard
        ignores. The two must never disagree."""
        run("init", self.m(), self.p())
        self.assertIn("execution_mode: subagent",
                      (self.d / "manifest.md").read_text())

    def test_rerun_never_clobbers_in_flight_state(self):
        """init is called at build-loop entry, and /continue re-enters. If it
        overwrote the ledger, resuming a cycle would silently discard every
        review verdict earned so far."""
        run("init", self.m(), self.p())
        man = self.d / "manifest.md"
        man.write_text(man.read_text().replace("status: pending", "status: done", 1))
        run("init", self.m(), self.p())
        self.assertIn("status: done", man.read_text())

    def test_check_fails_a_subagent_cycle_with_no_ledger(self):
        man = self.d / "manifest.md"
        man.write_text('---\ncycle_id: "t"\nexecution_mode: subagent\n---\n\n# Cycle\n')
        self.assertEqual(run("check", self.m()).returncode, 1)

    def test_check_ignores_inline_cycles(self):
        """Backward compatibility: every pre-1.3.0 manifest and every inline cycle."""
        self.assertEqual(run("check", self.m()).returncode, 0)

    def test_a_plan_with_no_tasks_fails_loudly(self):
        (self.d / "plan.md").write_text("# Plan\n\nSome prose, no task headings.\n")
        r = run("init", self.m(), self.p())
        self.assertEqual(r.returncode, 1)
        self.assertIn("no `## Task N", r.stderr)

if __name__ == "__main__":
    unittest.main()
