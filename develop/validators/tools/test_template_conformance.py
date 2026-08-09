"""Every parser of a Sage artifact, run against the TEMPLATE that produces it.

THE CLASS THIS KILLS. The ledger schism (2026-08-04): ledger.py parsed only
`## Task N` headings — the E9 fixture's convention — while the plan template
Sage generates writes `- [ ] **Task N:**` bullets. Green suite, broken
product: the parser had been tested exclusively against fixture-authored
data and had never once met Sage's own output. The first real --subagents
cycle was the first meeting, and it failed.

So: the templates are the contract, and this suite is the handshake. Every
consumer of plan.md / spec.md / the ledger block parses the ACTUAL template
file (or an artifact scaffolded from it) and must find what the template
promises. A parser change that breaks template conformance fails HERE, in
fastcheck, before any field report. If you add a template or a parser, add
its handshake.

Python 3.8+, stdlib only.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runtime" / "tools"))

import ledger as LED            # noqa: E402
import manifest as MAN          # noqa: E402
import scope_judge as SJ        # noqa: E402

PLAN_TEMPLATE = REPO / "core" / "templates" / "plan" / "standard.plan-template.md"
SPEC_TEMPLATES = (REPO / "core" / "templates" / "spec" / "full.spec-template.md",
                  REPO / "core" / "templates" / "spec" / "minimal.spec-template.md")
SPEC_GATE = (REPO / "runtime" / "platforms" / "claude-code" / "hooks"
             / "sage-spec-gate.sh")

PLAN_TEXT = PLAN_TEMPLATE.read_text(encoding="utf-8")


class PlanTemplateHandshake(unittest.TestCase):
    """plan.md consumers × the plan template, verbatim."""

    def test_ledger_parses_the_template_tasks(self):
        tasks = LED.parse_plan_tasks(PLAN_TEXT)
        self.assertGreaterEqual(len(tasks), 2,
                                "the template ships a code task AND a DOC task")
        self.assertEqual(tasks[0][0], 1)
        self.assertNotIn("[DOC]", tasks[1][1],
                         "[DOC] is presentation, not title")

    def test_manifest_plan_tasks_sees_tasks_not_section_headings(self):
        d = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "plan.md").write_text(PLAN_TEXT)
        tasks = MAN.plan_tasks(d)
        self.assertTrue(tasks and all(t.startswith("Task ") for t in tasks),
                        "bullet plans must yield tasks, not section headings "
                        "(the /continue display printed 'Gate Log' as a task "
                        "before 2026-08-04): %r" % tasks[:3])

    def test_scope_judge_current_task_reads_the_template(self):
        d = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "plan.md").write_text(PLAN_TEXT)
        tid, title = SJ.current_task(d)
        self.assertEqual(tid, 1)
        block = SJ.current_task_block(d)
        self.assertIn("**Files:**", block,
                      "the packet must carry the task's declaration lines")

    def test_scope_derive_files_regex_matches_the_template_lines(self):
        files_lines = [l for l in PLAN_TEXT.splitlines()
                       if MAN._FILES_LINE_RE.match(l)]
        self.assertGreaterEqual(
            len(files_lines), 2,
            "the template's `- **Files:**` and `- **Output:**` lines are what "
            "scope derive reads; if this regex stops matching them, every "
            "derived scope is empty")


class SpecTemplateHandshake(unittest.TestCase):
    """spec.md consumers × both spec templates."""

    def test_judge_boundary_section_found_in_both_templates(self):
        for tpl in SPEC_TEMPLATES:
            d = pathlib.Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, d, ignore_errors=True)
            (d / "spec.md").write_text(tpl.read_text(encoding="utf-8"))
            self.assertTrue(SJ.spec_boundary(d),
                            "%s: the judge packet's boundary section came "
                            "back empty — heading drifted?" % tpl.name)


class LedgerRoundTrip(unittest.TestCase):
    """The cross-language seam: ledger.py WRITES the tasks block, the
    spec-gate hook READS it (R101). Scaffolded from a template-form plan,
    driven through the real gate, both directions — the live probe from the
    2026-08-04 review, pinned."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        cyc = self.root / ".sage" / "work" / "001-x"
        cyc.mkdir(parents=True)
        (self.root / ".sage" / "config.yaml").write_text(
            "hard_enforcement: true\n")
        (cyc / "plan.md").write_text(
            "# Plan\n\n## Tasks\n\n"
            "- [ ] **Task 1:** one\n  - **Files:** src/a.py\n"
            "- [ ] **Task 2:** two [DOC]\n  - **Output:** docs/x.md\n")
        (cyc / "manifest.md").write_text(
            '---\ncycle_id: "001-x"\ngate_state: building\n'
            "status: in-progress\n---\n# x\n")
        self.cyc = cyc
        r = subprocess.run(
            [sys.executable, str(REPO / "runtime" / "tools" / "ledger.py"),
             "init", str(cyc / "manifest.md"), str(cyc / "plan.md")],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    def gate(self):
        payload = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": str(self.cyc / "manifest.md"),
                           "old_string": "gate_state: building",
                           "new_string": "gate_state: gates-passed"},
            "cwd": str(self.root)})
        return subprocess.run(
            ["bash", str(SPEC_GATE)], input=payload, capture_output=True,
            text=True, env={"PATH": "/usr/bin:/bin",
                            "CLAUDE_PROJECT_DIR": str(self.root)}).returncode

    def mark(self, status, review):
        m = self.cyc / "manifest.md"
        t = m.read_text()
        t = t.replace("status: pending", "status: %s" % status)
        t = t.replace("review: pending", "review: %s" % review)
        m.write_text(t)

    def test_gate_blocks_then_allows_the_scaffolded_ledger(self):
        self.assertEqual(self.gate(), 2,
                         "pending ledger must block gates-passed (R101)")
        self.mark("done", "approved")
        self.assertEqual(self.gate(), 0,
                         "done+approved (with the model: field present) "
                         "must pass — the gate parser tolerates the schema")


class GraphTemplateHandshake(unittest.TestCase):
    """graph derive × the plan template (A8): the tightened grammar the
    template teaches is exactly what the parser accepts — including the
    template's own `Depends on:` skeleton lines."""

    def test_filled_template_tasks_derive_cleanly(self):
        filled = (PLAN_TEXT
                  .replace("{exact_file_paths}", "src/auth.ts")
                  .replace("{document_file_path}", "docs/guide.md"))
        tasks, findings = MAN.parse_plan_graph(filled)
        self.assertEqual(findings, [], "the template's own skeletons, with "
                         "paths filled in, are the grammar's happy path")
        self.assertEqual([t["id"] for t in tasks], [1, 2])
        self.assertEqual(tasks[1]["depends"], [1],
                         "the template's `Depends on: T1` must parse")
        self.assertNotIn("[DOC]", tasks[1]["title"],
                         "[DOC] is a marker, not title")

    def test_raw_template_refuses_rather_than_deriving_junk(self):
        _, findings = MAN.parse_plan_graph(PLAN_TEXT)
        self.assertTrue(findings,
                        "placeholder Files: must refuse fail-closed — an "
                        "unfilled template can never derive an empty lane")


if __name__ == "__main__":
    unittest.main(verbosity=2)
