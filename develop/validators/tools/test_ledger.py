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

    def test_every_entry_carries_the_model_field(self):
        """A6: the serving model is recorded per dispatch — sessions record
        their actual model (the 1.3.4 house rule), and the scaffold carries
        the empty field so the orchestrator fills it, never invents it."""
        run("init", self.m(), self.p())
        fm = (self.d / "manifest.md").read_text()
        self.assertEqual(fm.count('model: ""'), 3,
                         "one model field per task entry")
        self.assertIn("status: pending", fm)
        self.assertIn("review: pending", fm)

    def test_every_entry_carries_the_lane_branch_field(self):
        """A7: empty until the task dispatches into a parallel lane; then the
        join key to the lanes: block. Scaffolded empty, filled by lanes.py —
        single-writer, never by hand."""
        run("init", self.m(), self.p())
        fm = (self.d / "manifest.md").read_text()
        self.assertEqual(fm.count('lane_branch: ""'), 3,
                         "one lane_branch field per task entry")

    def test_a_task_graph_block_is_not_a_ledger(self):
        """Caught by the A7 end-to-end fixture: `^\\s*tasks:` matched the
        NESTED tasks: inside A8's task_graph: block, so a graph-derived
        cycle could never scaffold a ledger — and check() false-passed the
        same cycle. Top-level only, both places."""
        m = pathlib.Path(self.m())
        m.write_text(m.read_text().replace(
            "---\n\n", "execution_mode: subagent\n"
            "task_graph:\n  derived_from: plan@abcd1234\n"
            "  tasks:\n"
            '    - {id: T1, title: "x", files: [src/a.ts], depends: [], '
            "parallel: false}\n---\n\n", 1))
        r = run("check", self.m())
        self.assertEqual(r.returncode, 1,
                         "a subagent cycle whose only tasks: is the graph's "
                         "nested one has NO ledger — check must fail")
        r = run("init", self.m(), self.p())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("already present", r.stdout)
        fm = m.read_text()
        self.assertEqual(fm.count("- id:"), 3, "the real ledger scaffolded")
        self.assertEqual(run("check", self.m()).returncode, 0)

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
        self.assertIn("no plan tasks found", r.stderr)



PLAN_BULLETS = """# Plan

## Tasks

- [ ] **Task 1:** Migration 0005: schema + RLS + down-guard
  - **Files:** internal/platform/db/migrations/0005.sql
  - **Action:** schema only
- [x] **Task 2:** Public IDs (whk_/del_/sbr_) [DOC]
  - **Depends on:** Task 1
- [ ] **Task 3:** Signer + signature vectors

## Rollback

Not a task, just a section heading.
"""


class BulletPlanTest(unittest.TestCase):
    """Field report 2026-08-04: the first real --subagents run could not
    scaffold a ledger, because ledger.py parsed only `## Task N` headings —
    the E9 FIXTURE's format — while the plan template Sage itself generates
    (core/templates/plan/standard.plan-template.md) writes checkbox bullets.
    A parser tested only against test-authored data had never met the
    product's own output."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())
        (self.d / "plan.md").write_text(PLAN_BULLETS)
        (self.d / "manifest.md").write_text(
            '---\ncycle_id: "t"\ngate_state: plan-approved\n---\n\n# Cycle\n')

    def test_template_bullets_scaffold_a_ledger(self):
        r = run("init", str(self.d / "manifest.md"), str(self.d / "plan.md"))
        self.assertEqual(r.returncode, 0, r.stderr)
        fm = (self.d / "manifest.md").read_text()
        self.assertEqual(fm.count("- id:"), 3)
        self.assertIn("title: Signer + signature vectors", fm)

    def test_checked_bullets_and_doc_markers(self):
        """A checked task still belongs in the ledger (done is not
        independently reviewed), and [DOC] is presentation, not title."""
        import importlib.util as _iu
        spec = _iu.spec_from_file_location("ledger", LEDGER)
        led = _iu.module_from_spec(spec)
        spec.loader.exec_module(led)
        tasks = led.parse_plan_tasks(PLAN_BULLETS)
        self.assertEqual([n for n, _ in tasks], [1, 2, 3])
        self.assertEqual(tasks[1][1], "Public IDs (whk_/del_/sbr_)")

    def test_mixed_forms_dedupe_by_id_first_wins(self):
        import importlib.util as _iu
        spec = _iu.spec_from_file_location("ledger", LEDGER)
        led = _iu.module_from_spec(spec)
        spec.loader.exec_module(led)
        mixed = "## Task 1 — heading form\n\n- [ ] **Task 1:** bullet form\n- [ ] **Task 2:** only bullet\n"
        tasks = led.parse_plan_tasks(mixed)
        self.assertEqual(tasks, [(1, "heading form"), (2, "only bullet")])


if __name__ == "__main__":
    unittest.main()
