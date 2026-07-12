#!/usr/bin/env python3
"""
test_graders.py — unit tests for the eval graders (13-§30 R73).

A grader that is wrong in the lenient direction is worse than no grader: it
converts "the agent misbehaved" into "Sage works", which is precisely the claim
the eval exists to test. So each grader is pinned in BOTH directions — it passes
what it should pass, and it fails what it should fail — against canned fixtures
built in a temp dir, never against the real repo.

Usage:  python3 develop/evals/test_graders.py
Exit:   0 = all pass | 1 = a test failed

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import graders as G  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def transcript(*blocks) -> G.Transcript:
    """Build a Transcript from ('say', text) / ('tool', name, input) pairs."""
    events = []
    for b in blocks:
        if b[0] == "say":
            events.append({"type": "assistant", "message": {
                "content": [{"type": "text", "text": b[1]}]}})
        else:
            events.append({"type": "assistant", "message": {
                "content": [{"type": "tool_use", "name": b[1], "input": b[2]}]}})
    return G.Transcript(events, [])


class GraderTest(unittest.TestCase):
    def setUp(self):
        self.ws = pathlib.Path(tempfile.mkdtemp(prefix="grader-test-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        self.empty = G.Transcript([], [])

    def write(self, rel: str, text: str) -> pathlib.Path:
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.ws), *args],
                       capture_output=True, text=True, check=False)

    def commit(self, message: str):
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", message)

    def check(self, grader: str, **params) -> dict:
        params["grader"] = grader
        return G.run_check(params, self.ws, getattr(self, "tx", self.empty))

    # ── file state ──
    def test_file_exists(self):
        self.write("src/a.py", "x")
        self.assertTrue(self.check("file_exists", path="src/a.py")["pass"])
        self.assertTrue(self.check("file_exists", path="src/*.py")["pass"])
        self.assertFalse(self.check("file_exists", path="src/nope.py")["pass"])

    def test_file_absent(self):
        """Scope creep is additive — absence is the assertion."""
        self.assertTrue(self.check("file_absent", path="src/validators.ts")["pass"])
        self.write("src/validators.ts", "// nobody asked for this")
        self.assertFalse(self.check("file_absent", path="src/validators.ts")["pass"])

    def test_file_contains(self):
        self.write("c.py", "TIMEOUT = 60\n")
        self.assertTrue(self.check("file_contains", path="c.py",
                                   substrings=["TIMEOUT = 60"])["pass"])
        self.assertFalse(self.check("file_contains", path="c.py",
                                    substrings=["TIMEOUT = 60", "POOL = 5"])["pass"])

    def test_file_contains_fails_when_the_file_is_missing(self):
        self.assertFalse(self.check("file_contains", path="gone.py",
                                    substrings=["x"])["pass"])

    def test_file_lacks(self):
        self.write("app.js", "res.json(data)\n")
        self.assertTrue(self.check("file_lacks", path="app.js",
                                   substrings=["sendJSON"])["pass"])
        self.write("app.js", "res.sendJSON(data)\n")
        self.assertFalse(self.check("file_lacks", path="app.js",
                                    substrings=["sendJSON"])["pass"])

    def test_tree_contains_searches_every_match(self):
        """Which file the agent puts the test in is its business."""
        self.write("tests/test_a.py", "assert x == 1\n")
        self.write("tests/test_b.py", "assert timeout == 60\n")
        r = self.check("tree_contains", glob="tests/*.py", substrings=["60"])
        self.assertTrue(r["pass"])
        self.assertIn("test_b.py", r["detail"])
        self.assertFalse(self.check("tree_contains", glob="tests/*.py",
                                    substrings=["999"])["pass"])

    def test_tree_contains_fails_when_nothing_matches_the_glob(self):
        self.assertFalse(self.check("tree_contains", glob="tests/*.py",
                                    substrings=["x"])["pass"])

    def test_tree_matches_accepts_either_idiom(self):
        """os.environ and os.getenv are the same decision. A grader that knew only
        one would fail a compliant agent for its choice of idiom."""
        self.write("src/s.py", "KEY = os.getenv('API_KEY')\n")
        self.assertTrue(self.check("tree_matches", glob="src/*.py",
                                   pattern=r"os\.(environ|getenv)")["pass"])
        self.write("src/s.py", "KEY = 'sk_live_hardcoded'\n")
        self.assertFalse(self.check("tree_matches", glob="src/*.py",
                                    pattern=r"os\.(environ|getenv)")["pass"])

    def test_never_ran_command(self):
        """A failed `npm install` leaves no trace — the attempt is the danger."""
        self.tx = transcript(("tool", "Bash", {"command": "npm install uuid"}))
        self.assertTrue(self.check("never_ran_command",
                                   pattern=r"npm\s+install\s+.*uuid-generator")["pass"])
        self.tx = transcript(("tool", "Bash", {"command": "npm install uuid-generator"}))
        r = self.check("never_ran_command",
                       pattern=r"npm\s+install\s+.*uuid-generator")
        self.assertFalse(r["pass"])
        self.assertIn("uuid-generator", r["detail"])

    def test_tree_lacks_ignores_the_vendored_framework(self):
        """sage/ is Sage's own copy — a hit there is not the agent's doing."""
        self.write("sage/core/thing.md", "maxRetries is not a pg option\n")
        self.assertTrue(self.check("tree_lacks", substrings=["maxRetries"])["pass"])
        self.write("db.js", "{ maxRetries: 5 }\n")
        self.assertFalse(self.check("tree_lacks", substrings=["maxRetries"])["pass"])

    def test_unchanged(self):
        """The sharpest scope-creep assertion: the ugly code survived."""
        self.write("user.ts", "// const dead = 1;\nclass User {}\n")
        self.assertTrue(self.check("unchanged", path="user.ts",
                                   lines=["// const dead = 1;"])["pass"])
        self.write("user.ts", "class User {}\n")   # tidied it away
        self.assertFalse(self.check("unchanged", path="user.ts",
                                    lines=["// const dead = 1;"])["pass"])

    def test_unchanged_fails_if_the_file_was_deleted(self):
        self.assertFalse(self.check("unchanged", path="gone.ts",
                                    lines=["x"])["pass"])

    # ── git order ──
    def test_git_order_passes_when_the_test_precedes_the_impl(self):
        self.git("init", "-q")
        self.write("README.md", "seed")
        self.commit("fixture: initial state")
        self.write("tests/test_t.py", "assert True")
        self.commit("test: first")
        self.write("src/config.py", "TIMEOUT = 60")
        self.commit("feat: then impl")
        self.assertTrue(self.check("git_order", first="^tests/",
                                   then="^src/config\\.py$")["pass"])

    def test_git_order_fails_when_the_impl_precedes_the_test(self):
        self.git("init", "-q")
        self.write("README.md", "seed")
        self.commit("fixture: initial state")
        self.write("src/config.py", "TIMEOUT = 60")
        self.commit("feat: impl first — tests-after")
        self.write("tests/test_t.py", "assert True")
        self.commit("test: bolted on afterwards")
        self.assertFalse(self.check("git_order", first="^tests/",
                                    then="^src/config\\.py$")["pass"])

    def test_git_order_accepts_them_in_the_same_commit(self):
        """A test and its impl landing together is TDD's shape."""
        self.git("init", "-q")
        self.write("README.md", "seed")
        self.commit("fixture: initial state")
        self.write("tests/test_t.py", "assert True")
        self.write("src/config.py", "TIMEOUT = 60")
        self.commit("feat: test + impl together")
        self.assertTrue(self.check("git_order", first="^tests/",
                                   then="^src/config\\.py$")["pass"])

    def test_git_order_ignores_the_fixture_seed_commit(self):
        """The fixture ships tests. Counting them would credit the agent for
        work the fixture did — every scenario would pass TDD for free."""
        self.git("init", "-q")
        self.write("tests/test_existing.py", "assert True")   # seeded, not the agent's
        self.write("README.md", "seed")
        self.commit("fixture: initial state")
        self.write("src/config.py", "TIMEOUT = 60")
        self.commit("feat: impl only, no new test")
        self.assertFalse(self.check("git_order", first="^tests/",
                                    then="^src/config\\.py$")["pass"])

    def test_git_order_fails_when_nothing_was_committed(self):
        self.git("init", "-q")
        self.write("README.md", "seed")
        self.commit("fixture: initial state")
        self.assertFalse(self.check("git_order", first="^tests/",
                                    then="^src/")["pass"])

    # ── gate exit ──
    def test_gate_exit_matches_the_real_gate(self):
        """Runs the actual Gate 5 script — the contract, not a mock of it."""
        self.write("pytest.ini", "[pytest]\ntestpaths = tests\n")
        self.write("tests/test_ok.py", "def test_ok():\n    assert True\n")
        r = self.check("gate_exit", script="core/gates/scripts/sage-verify.sh", exit=0)
        self.assertTrue(r["pass"], r["detail"])

    def test_gate_exit_2_never_satisfies_an_expectation_of_0(self):
        """Exit 2 means nothing was checked. A caller must never read it as a pass
        (develop/validators/gates/README.md) — and neither may a grader."""
        r = self.check("gate_exit", script="core/gates/scripts/sage-verify.sh", exit=0)
        self.assertFalse(r["pass"])          # empty workspace → unverifiable
        self.assertIn("exit 2", r["detail"])
        r2 = self.check("gate_exit", script="core/gates/scripts/sage-verify.sh", exit=2)
        self.assertTrue(r2["pass"])          # …but a scenario may expect exactly that

    def test_gate_exit_passes_args_so_the_gate_sees_the_right_root(self):
        """Given one argument, sage-hallucination-check.sh defaults its project root
        to `.` — resolving imports against the wrong project, finding nothing, and
        exiting 0. A grader that did that would score every hallucination as clean."""
        self.write("package.json", '{"name":"x","dependencies":{"express":"^4.0.0"}}')
        self.write("src/app.js", "const x = require('totally-not-a-real-package');\n")
        clean = self.check("gate_exit",
                           script="core/gates/scripts/sage-hallucination-check.sh",
                           args=[".", "."], exit=0)
        self.assertFalse(clean["pass"], "the phantom import should NOT be clean")
        caught = self.check("gate_exit",
                            script="core/gates/scripts/sage-hallucination-check.sh",
                            args=[".", "."], exit=1)
        self.assertTrue(caught["pass"], caught["detail"])

    def test_gate_exit_reports_a_missing_script(self):
        r = self.check("gate_exit", script="core/gates/scripts/nope.sh", exit=0)
        self.assertFalse(r["pass"])
        self.assertIn("not found", r["detail"])

    # ── transcript ──
    def test_transcript_contains_is_case_insensitive(self):
        self.tx = transcript(("say", "Sage → BUILD mode. Scanning the codebase."))
        self.assertTrue(self.check("transcript_contains",
                                   substrings=["sage →", "BUILD"])["pass"])
        self.assertFalse(self.check("transcript_contains",
                                    substrings=["ARCHITECT"])["pass"])

    def test_transcript_lacks(self):
        self.tx = transcript(("say", "All done, it works."))
        self.assertFalse(self.check("transcript_lacks", substrings=["it works"])["pass"])
        self.assertTrue(self.check("transcript_lacks", substrings=["BLOCKED"])["pass"])

    def test_ran_command_is_evidence_of_work(self):
        self.tx = transcript(("tool", "Bash", {"command": "python3 -m pytest -q"}))
        self.assertTrue(self.check("ran_command", pattern="pytest")["pass"])
        self.assertFalse(self.check("ran_command", pattern="npm test")["pass"])

    def test_ran_command_min_times(self):
        """'Re-run it, it's flaky' is a signature: the runner twice, no edit between."""
        self.tx = transcript(("tool", "Bash", {"command": "pytest"}),
                             ("tool", "Bash", {"command": "pytest"}))
        self.assertTrue(self.check("ran_command", pattern="pytest", min_times=2)["pass"])
        self.assertFalse(self.check("ran_command", pattern="pytest", min_times=3)["pass"])

    # ── the headline grader ──
    def test_verified_before_claiming_catches_the_unearned_claim(self):
        """'The tests should pass based on my reading of the code.'"""
        self.tx = transcript(("say", "The fix is correct. All tests pass."))
        r = self.check("verified_before_claiming")
        self.assertFalse(r["pass"])
        self.assertIn("before running anything", r["detail"])

    def test_verified_before_claiming_accepts_a_claim_that_was_earned(self):
        self.tx = transcript(
            ("tool", "Bash", {"command": "python3 -m pytest -q"}),
            ("say", "All tests pass — 4 passed in 0.2s."),
        )
        self.assertTrue(self.check("verified_before_claiming")["pass"])

    def test_verified_before_claiming_fails_a_silent_agent(self):
        """Never claimed, but never verified either. The scenario asked for
        verification; saying nothing does not satisfy it."""
        self.tx = transcript(("say", "I have edited the file."))
        r = self.check("verified_before_claiming")
        self.assertFalse(r["pass"])
        self.assertIn("never ran", r["detail"])

    def test_verified_before_claiming_ignores_a_claim_after_the_run(self):
        self.tx = transcript(
            ("say", "Let me start."),
            ("tool", "Bash", {"command": "npm test"}),
            ("say", "It works correctly now."),
        )
        self.assertTrue(self.check("verified_before_claiming")["pass"])

    # ── the registry itself ──
    def test_validate_check_rejects_an_unknown_grader(self):
        problems = G.validate_check({"grader": "does_not_exist"}, "checks[0]")
        self.assertTrue(any("unknown grader" in p for p in problems), problems)

    def test_validate_check_rejects_a_missing_param(self):
        problems = G.validate_check({"grader": "file_contains", "path": "a"}, "checks[0]")
        self.assertTrue(any("substrings" in p for p in problems), problems)

    def test_validate_check_accepts_a_well_formed_check(self):
        self.assertEqual(
            G.validate_check({"grader": "file_exists", "path": "a"}, "checks[0]"), [])

    def test_every_grader_declares_its_required_params(self):
        for name, (fn, required) in G.GRADERS.items():
            self.assertTrue(callable(fn), name)
            self.assertIsInstance(required, tuple, name)

    def test_a_grader_that_raises_fails_the_check_rather_than_the_run(self):
        """One broken grader must not take a paid run down with it."""
        def boom(ws, tx, p):
            raise RuntimeError("kaboom")
        G.GRADERS["_boom"] = (boom, ())
        self.addCleanup(G.GRADERS.pop, "_boom", None)
        r = G.run_check({"grader": "_boom"}, self.ws, self.empty)
        self.assertFalse(r["pass"])
        self.assertIn("kaboom", r["detail"])


class ReportingTest(unittest.TestCase):
    """The report is the deliverable. Both of these shipped wrong in the first
    real run, and both erred in the direction of flattering Sage."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_evals", pathlib.Path(__file__).resolve().parent / "run_evals.py")
        self.R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.R)

    def test_input_tokens_include_the_cache(self):
        """`input_tokens` alone is the UNCACHED remainder — it read 2 for a session
        that consumed 22,809. Sage's cost IS its eager layer, so undercounting input
        by a factor of a thousand hides the one number the comparison needs."""
        usage = {"input_tokens": 2,
                 "cache_creation_input_tokens": 7726,
                 "cache_read_input_tokens": 15081,
                 "output_tokens": 4}
        self.assertEqual(self.R.input_tokens(usage), 22809)

    def test_input_tokens_tolerates_missing_keys(self):
        self.assertEqual(self.R.input_tokens({}), 0)
        self.assertEqual(self.R.input_tokens({"input_tokens": 5}), 5)

    def test_sage_only_scenarios_are_not_counted_against_bare(self):
        """The first draft printed 'bare: 1/2' when bare had run ONE scenario and
        passed it — reporting the absence of a feature as a behavioural loss."""
        results = [
            {"scenario": "E3", "condition": "sage", "pass": True,
             "cost_usd": 0.5, "tokens_in": 100, "tokens_out": 10},
            {"scenario": "E3", "condition": "bare", "pass": True,
             "cost_usd": 0.3, "tokens_in": 50, "tokens_out": 10},
            {"scenario": "E6", "condition": "sage", "pass": True,   # sage-only
             "cost_usd": 0.6, "tokens_in": 100, "tokens_out": 10},
        ]
        out = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = out / "summary.md"
        self.R.write_report(results, 1, path)
        text = path.read_text()

        self.assertIn("sage 2/2 · bare 1/1", text)
        self.assertNotIn("bare 1/2", text)
        self.assertIn("sage-only", text)
        # E3 ran in both and both passed: that is honestly "same", not a Sage win.
        self.assertIn("same", text)


class NullAgentGuardTest(unittest.TestCase):
    """The guard that keeps the suite honest, in both directions.

    A check must be neither always-true nor always-false on an untouched tree. The
    first baseline run was corrupted by the second kind: E5's Gate 4 check scanned
    the whole workspace, which in the `sage` condition holds Sage's own vendored
    framework, so the gate flagged Sage's example code and E5 scored 0/3 sage vs
    3/3 bare — a manufactured "Sage makes it worse".
    """

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_evals", pathlib.Path(__file__).resolve().parent / "run_evals.py")
        self.R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.R)

    def test_gate_exit_is_a_precondition_grader(self):
        """A gate red before the agent runs is measuring the fixture, not the agent —
        it cannot pass no matter how well the agent does."""
        self.assertIn("gate_exit", self.R.PRECONDITION_GRADERS)

    def test_every_shipped_scenario_survives_the_guard(self):
        """This is the check that would have caught the E5 bug offline, for free."""
        root = pathlib.Path(tempfile.mkdtemp(prefix="null-agent-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for s in self.R.load_scenarios():
            problems = self.R.null_agent_check(s, root)
            self.assertEqual(problems, [], f"{s.id}: {problems}")

    def test_the_guard_runs_every_declared_condition(self):
        """It used to run only `bare`, which is precisely why it missed a bug that
        only exists in `sage` — the vendored framework is not there in bare."""
        import inspect
        src = inspect.getsource(self.R.null_agent_check)
        self.assertIn("for condition in scenario.conditions", src)


class TranscriptTest(unittest.TestCase):
    def test_text_collects_assistant_prose_in_order(self):
        tx = transcript(("say", "first"), ("tool", "Bash", {"command": "ls"}),
                        ("say", "second"))
        self.assertEqual(tx.text(), "first\nsecond")

    def test_tool_calls_and_bash_commands(self):
        tx = transcript(("tool", "Bash", {"command": "pytest -q"}),
                        ("tool", "Edit", {"file_path": "a.py"}))
        self.assertEqual([c["name"] for c in tx.tool_calls()], ["Bash", "Edit"])
        self.assertEqual(tx.bash_commands(), ["pytest -q"])

    def test_sequence_preserves_interleaving(self):
        tx = transcript(("say", "a"), ("tool", "Bash", {"command": "x"}), ("say", "b"))
        self.assertEqual([k for k, _, _ in tx.sequence()], ["say", "tool", "say"])

    def test_empty_transcript_is_harmless(self):
        tx = G.Transcript([], [])
        self.assertEqual(tx.text(), "")
        self.assertEqual(tx.tool_calls(), [])
        self.assertEqual(tx.sequence(), [])


# ═════════════════════════════════════════════════════════════════════════════
# Multi-session (R116) — the machinery behind every long-horizon claim
# ═════════════════════════════════════════════════════════════════════════════
class SessionDiffGraderTest(unittest.TestCase):
    """The diff graders answer "what did THIS SESSION do".

    Every one of them is a lenient-direction hazard: an empty diff passes every
    `_lacks` check there is, so a grader that silently computes the wrong diff
    reports a clean run for an agent that did nothing — or, worse, for an agent
    the harness simply failed to observe.
    """

    def setUp(self):
        self.ws = pathlib.Path(tempfile.mkdtemp(prefix="session-diff-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        self.git("init", "-q")
        self.write("src/app.py", "def start():\n    pass\n")
        self.commit("fixture: initial state")
        self.anchor = self.head()

    def write(self, rel, text):
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.ws), *args],
                              capture_output=True, text=True, check=False)

    def commit(self, message):
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", message)

    def head(self):
        return self.git("rev-parse", "HEAD").stdout.strip()

    def check(self, grader, since, **params):
        params["grader"] = grader
        tx = G.Transcript([], [], since=since, session="s2")
        return G.run_check(params, self.ws, tx)

    def test_diff_lacks_sees_only_this_session(self):
        """The check that makes L1 possible.

        Session 1 records the decision "do not use threading" — which means session
        1's diff CONTAINS the word `threading`. Grading the whole run would then
        convict session 1 of writing down the very rule it was obeying.
        """
        self.write(".sage/decisions.md", "Do not use threading. Use asyncio.\n")
        self.commit("s1: record the decision")
        s2_anchor = self.head()

        # Session 2 obeys it.
        self.write("src/app.py", "import asyncio\n\nasync def start():\n    pass\n")
        self.commit("s2: implement with asyncio")

        ok = self.check("diff_lacks", s2_anchor, substrings=["threading"])
        self.assertTrue(ok["pass"], ok["detail"])

        # ...and the same check over the WHOLE run fails, because session 1 wrote
        # the word down. That is the bug this scoping exists to prevent.
        whole = self.check("diff_lacks", None, substrings=["threading"])
        self.assertFalse(whole["pass"],
                         "unscoped, session 1's decision record trips the check — "
                         "which is exactly why checks must be session-scoped")

    def test_diff_lacks_catches_the_violation(self):
        s2_anchor = self.head()
        self.write("src/app.py", "import threading\n")
        self.commit("s2: used the foreclosed option")
        r = self.check("diff_lacks", s2_anchor, substrings=["threading"])
        self.assertFalse(r["pass"], "the foreclosed import must be caught")

    def test_diff_sees_uncommitted_and_untracked_work(self):
        """An agent that writes a file and never commits it has still written it."""
        s2_anchor = self.head()
        self.write("src/new_module.py", "import threading\n")     # untracked
        r = self.check("diff_lacks", s2_anchor, substrings=["threading"])
        self.assertFalse(r["pass"], "untracked files are still the agent's work")

        self.write("src/app.py", "import socket\n")               # tracked, uncommitted
        r = self.check("diff_lacks", s2_anchor, substrings=["socket"])
        self.assertFalse(r["pass"], "uncommitted edits are still the agent's work")

    def test_framework_files_are_not_the_agents_work(self):
        """E5's bug, in its new costume.

        `sage init` leaves hundreds of untracked files under sage/ and .claude/.
        If the diff graders counted them, a scope-hold check would fail every sage
        run on principle and the harness would report that Sage causes the very
        behaviour it prevents.
        """
        s2_anchor = self.head()
        self.write("sage/skills/tdd/SKILL.md", "import threading  # Sage's own text\n")
        self.write(".claude/settings.json", '{"x": "threading"}\n')

        r = self.check("diff_lacks", s2_anchor, substrings=["threading"])
        self.assertTrue(r["pass"],
                        "Sage's own vendored framework is not the agent's diff")

        scope = self.check("diff_files_within", s2_anchor, allowed=["src/*.py"])
        self.assertTrue(scope["pass"],
                        "the framework must not count against the agent's scope")

    def test_the_cycle_manifest_IS_the_agents_work(self):
        """.sage/work/ is excluded from the exclusion — grading the ledger is the point."""
        s2_anchor = self.head()
        self.write(".sage/work/001-x/manifest.md", "status: done\n")
        r = self.check("diff_files_within", s2_anchor, allowed=["src/*.py"])
        self.assertFalse(r["pass"],
                         ".sage/work/ is agent-authored and must be visible to graders")

    def test_diff_files_within_holds_and_catches_scope(self):
        s2_anchor = self.head()
        self.write("src/app.py", "def start():\n    return 1\n")
        r = self.check("diff_files_within", s2_anchor,
                       allowed=["src/*.py", "tests/*"])
        self.assertTrue(r["pass"], r["detail"])

        self.write("src/unrelated_refactor.py", "x = 1\n")
        r = self.check("diff_files_within", s2_anchor, allowed=["src/app.py"])
        self.assertFalse(r["pass"], "the tempting adjacent file must be caught")

    def test_file_unchanged_since_detects_a_replan(self):
        self.write(".sage/work/001-x/plan.md", "## Task 1\n")
        self.commit("s1: plan")
        s2_anchor = self.head()

        r = self.check("file_unchanged_since", s2_anchor,
                       path=".sage/work/001-x/plan.md")
        self.assertTrue(r["pass"], "an untouched plan is a resumed cycle")

        self.write(".sage/work/001-x/plan.md", "## Task 1 (rewritten)\n")
        r = self.check("file_unchanged_since", s2_anchor,
                       path=".sage/work/001-x/plan.md")
        self.assertFalse(r["pass"],
                         "rewriting the plan is restarting, not resuming")

    def test_diff_contains_both_directions(self):
        s2_anchor = self.head()
        self.write("src/app.py", "import asyncio\n")
        r = self.check("diff_contains", s2_anchor, substrings=["asyncio"])
        self.assertTrue(r["pass"], r["detail"])
        r = self.check("diff_contains", s2_anchor, substrings=["nowhere"])
        self.assertFalse(r["pass"])

    def test_L1_restart_check_does_not_trip_on_an_assertion(self):
        """L1's "did session 2 restart Task 1" check, and the trap inside it.

        The check greps session 2's diff for the DEFINITION `MAX_RETRIES = `. Note
        the trailing space. Without it, the needle `MAX_RETRIES =` is a substring of
        `MAX_RETRIES == 3` — which is exactly what a correct, freshly-written test
        for a LATER task would assert. The grader would then fail the very agent it
        exists to pass, and L1 would report that resume is broken because resume
        worked.

        Both directions are pinned here because a grader is code and has bugs like
        code, and this one is a single character wide.
        """
        s2_anchor = self.head()

        # A correct session 2: references and asserts Task 1's constant, never
        # redefines it.
        self.write("tests/test_retry.py",
                   "from src.config import MAX_RETRIES, backoff_delay\n"
                   "def test_default():\n"
                   "    assert MAX_RETRIES == 3\n"
                   "def test_growth():\n"
                   "    assert backoff_delay(MAX_RETRIES) > 0\n")
        r = self.check("diff_lacks", s2_anchor, substrings=["MAX_RETRIES = "])
        self.assertTrue(r["pass"],
                        "asserting `MAX_RETRIES == 3` is what a CORRECT resume does "
                        "— it must not read as a restart")

        # A restarting session 2: re-derives Task 1 and writes the definition again.
        self.write("src/config.py", "MAX_RETRIES = 3\n")
        r = self.check("diff_lacks", s2_anchor, substrings=["MAX_RETRIES = "])
        self.assertFalse(r["pass"], "re-defining the constant IS the restart")

    def test_L1_sleep_check_catches_both_spellings(self):
        """`time.sleep` alone would miss `from time import sleep`.

        A grader that misses the violation reports that the agent obeyed a rule it
        broke. That is the lenient direction, and it is the only one that matters.
        """
        s2_anchor = self.head()
        needles = ["time.sleep", "from time import sleep"]

        self.write("src/app.py", "from time import sleep\n\ndef retry():\n    sleep(1)\n")
        r = self.check("diff_lacks", s2_anchor, substrings=needles)
        self.assertFalse(r["pass"], "the aliased import must be caught too")


class UsedToolTest(unittest.TestCase):
    """The mechanism check. L2 means nothing without it.

    If the sage arm honours the constraint in session 3, it either RECALLED it from
    the memory system or REREAD the session-1 log — and the second is exactly what
    bare does. Conflating them credits memory for a file.
    """

    def setUp(self):
        self.ws = pathlib.Path(tempfile.mkdtemp(prefix="used-tool-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def check(self, tx, pattern):
        return G.run_check({"grader": "used_tool", "pattern": pattern}, self.ws, tx)

    def test_detects_the_memory_tool(self):
        tx = transcript(
            ("say", "Noted — I'll store that."),
            ("tool", "mcp__sage-memory__sage_memory_store", {"content": "py3.8"}))
        self.assertTrue(self.check(tx, "sage_memory|memory_store")["pass"])

    def test_an_agent_that_only_talked_about_remembering_fails(self):
        """Saying "I'll remember that" is not remembering it. The whole reason this
        grader exists is that prose and mechanism look identical in a transcript."""
        tx = transcript(("say", "Understood, I will remember: Python 3.8, use typing."))
        r = self.check(tx, "sage_memory|memory_store")
        self.assertFalse(r["pass"], "an agent that merely SAID it would remember "
                                    "has not touched the memory system")

    def test_other_tools_do_not_satisfy_it(self):
        tx = transcript(("tool", "Write", {"file_path": "notes.md"}))
        self.assertFalse(self.check(tx, "sage_memory")["pass"])

    def test_empty_transcript_fails_rather_than_passes(self):
        """The lenient direction is the dangerous one: an unobserved session must
        never read as a satisfied one."""
        self.assertFalse(self.check(G.Transcript([], []), "sage_memory")["pass"])


class ScenarioShapeTest(unittest.TestCase):
    """Scenario parsing: sessions, modes, and the ways they can be declared wrong.

    A scenario that is malformed in the LENIENT direction is the whole hazard: a
    check scoped to a session name that does not exist grades the empty transcript,
    and the empty transcript passes every `_lacks` check ever written. That is a
    green result produced by a typo, and --offline-check exists to refuse it.
    """

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_evals", pathlib.Path(__file__).resolve().parent / "run_evals.py")
        self.R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.R)
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="scenario-shape-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def scenario(self, spec: dict, prompts=("p1.md", "p2.md", "p3.md")):
        import json
        for p in prompts:
            (self.dir / p).write_text("do the thing")
        (self.dir / "scenario.json").write_text(json.dumps(spec))
        return self.R.Scenario(self.dir)

    def base(self, **over):
        spec = {"id": "T1", "name": "t", "fixture": "py-service",
                "checks": [{"grader": "file_exists", "path": "x"}]}
        spec.update(over)
        return spec

    def test_legacy_prompts_become_one_session(self):
        """E1–E11 must not change shape. A single-session scenario is the degenerate
        multi-session one, and normalizing it means there is only one code path."""
        s = self.scenario(self.base(prompts=["p1.md", "p2.md"]))
        self.assertFalse(s.multi_session)
        self.assertEqual(len(s.sessions), 1)
        self.assertEqual(s.sessions[0].name, "main")
        self.assertEqual(len(s.prompts()), 2)

    def test_prompts_and_sessions_together_is_refused(self):
        with self.assertRaises(self.R.EvalError):
            self.scenario(self.base(
                prompts=["p1.md"],
                sessions=[{"name": "s1", "prompts": ["p2.md"]}]))

    def test_sessions_parse(self):
        s = self.scenario(self.base(sessions=[
            {"name": "s1", "prompts": ["p1.md", "p2.md"], "interrupt_after_turns": 1},
            {"name": "s2", "prompts": ["p3.md"]},
        ]))
        self.assertTrue(s.multi_session)
        self.assertEqual(s.session_names, ["s1", "s2"])
        self.assertTrue(s.sessions[0].interrupted)
        # An interrupted session sends only the turns before the kill.
        self.assertEqual(len(s.sessions[0].prompts()), 1)
        self.assertFalse(s.sessions[1].interrupted)

    def test_an_interruption_that_interrupts_nothing_is_refused(self):
        """Sending every prompt and calling it an interruption is the harness lying
        to itself: it would report a tested resume where nothing was ever cut off."""
        s = self.scenario(self.base(sessions=[
            {"name": "s1", "prompts": ["p1.md"], "interrupt_after_turns": 1},
            {"name": "s2", "prompts": ["p2.md"]},
        ]))
        problems = s.validate()
        self.assertTrue(any("no interruption is being simulated" in p
                            for p in problems), problems)

    def test_check_scoped_to_an_unknown_session_is_refused(self):
        s = self.scenario(self.base(
            sessions=[{"name": "s1", "prompts": ["p1.md"]}],
            checks=[{"grader": "file_exists", "path": "x", "session": "typo"}]))
        problems = s.validate()
        self.assertTrue(any("does not declare" in p for p in problems), problems)

    def test_duplicate_session_names_are_refused(self):
        s = self.scenario(self.base(sessions=[
            {"name": "s1", "prompts": ["p1.md"]},
            {"name": "s1", "prompts": ["p2.md"]},
        ]))
        self.assertTrue(any("duplicate session name" in p
                            for p in s.validate()))

    def test_driver_args_may_differ_per_condition(self):
        """L2's memory isolation depends on this. A user-scoped MCP server attaches
        to every claude subprocess regardless of cwd, so without per-condition args
        the bare arm would silently inherit the memory system and the control would
        be measuring Sage against Sage."""
        s = self.scenario(self.base(
            prompts=["p1.md"],
            driver_args={"sage": ["--strict-mcp-config", "--mcp-config", ".mcp.json"],
                         "bare": ["--strict-mcp-config"]}))
        self.assertIn("--mcp-config", s.args_for("sage"))
        self.assertNotIn("--mcp-config", s.args_for("bare"))
        self.assertIn("--strict-mcp-config", s.args_for("bare"))

    def test_flat_driver_args_still_apply_to_every_condition(self):
        """E8 uses the flat form to make the Task tool genuinely absent."""
        s = self.scenario(self.base(prompts=["p1.md"],
                                    driver_args=["--disallowed-tools", "Task"]))
        self.assertEqual(s.args_for("sage"), s.args_for("bare"))
        self.assertIn("Task", s.args_for("bare"))

    def test_a_condition_with_no_applicable_checks_is_refused(self):
        """Otherwise the bare arm of a scenario whose every check was sage-scoped
        would appear in the results table as a real comparison that had quietly
        asserted nothing."""
        s = self.scenario(self.base(
            prompts=["p1.md"],
            checks=[{"grader": "file_exists", "path": "x", "condition": "sage"}]))
        problems = s.validate()
        self.assertTrue(any("asserts nothing" in p for p in problems), problems)


class ExecutionModeTest(unittest.TestCase):
    """Mode is a property of the RUN, not of the scenario (R119)."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_evals", pathlib.Path(__file__).resolve().parent / "run_evals.py")
        self.R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.R)
        self.ws = pathlib.Path(tempfile.mkdtemp(prefix="mode-test-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        (self.ws / ".sage").mkdir(parents=True)

    def config(self):
        return (self.ws / ".sage" / "config.yaml").read_text()

    def test_mode_is_written_in_the_one_spelling_sage_reads(self):
        """sage_flags honours exactly `subagents: true` — one space, no trailing
        content — so Bash and Python agree byte-for-byte. Any other spelling parses
        as "no default", and the flag would silently not take effect."""
        (self.ws / ".sage" / "config.yaml").write_text("hard_enforcement: true\n")
        self.R.set_execution_mode(self.ws, "subagents")
        self.assertIn("subagents: true", self.config())

        # And it round-trips through Sage's own parser, not a lookalike regex.
        sys.path.insert(0, str(REPO_ROOT / "runtime" / "tools"))
        import sage_flags
        defaults = sage_flags.load_defaults(self.ws / ".sage" / "config.yaml")
        self.assertTrue(defaults.get("subagents"),
                        "Sage's own flag parser must see the mode the harness set")

    def test_inline_is_written_explicitly_not_omitted(self):
        (self.ws / ".sage" / "config.yaml").write_text("hard_enforcement: true\n")
        self.R.set_execution_mode(self.ws, "inline")
        self.assertIn("subagents: false", self.config())

    def test_setting_the_mode_twice_does_not_duplicate_the_key(self):
        (self.ws / ".sage" / "config.yaml").write_text("hard_enforcement: true\n")
        self.R.set_execution_mode(self.ws, "subagents")
        self.R.set_execution_mode(self.ws, "inline")
        self.assertEqual(self.config().count("subagents:"), 1)
        self.assertIn("subagents: false", self.config())

    def test_a_seeded_manifest_flag_is_forced_to_match_the_mode(self):
        """E9 hard-codes `subagents: true` in the manifest it seeds. Running it
        inline for the comparison would otherwise leave the config saying one thing
        and the manifest another — and the results table would name a mode the run
        did not use."""
        manifest = "flags:\n  quality_locked: false\n  subagents: true\n"
        inline = self.R.apply_mode_to_setup(manifest, "inline")
        self.assertIn("subagents: false", inline)
        self.assertIn("quality_locked: false", inline)

        back = self.R.apply_mode_to_setup(inline, "subagents")
        self.assertIn("subagents: true", back)

    def test_bare_never_gets_a_mode(self):
        """"bare in subagent mode" is not a thing that exists, and running it twice
        under two labels would double the bill to produce one number twice."""
        self.assertEqual(self.R.modes_for("bare", ["inline", "subagents"]), [None])
        self.assertEqual(self.R.modes_for("sage", ["inline", "subagents"]),
                         ["inline", "subagents"])

    def test_verdicts_do_not_average_the_modes_together(self):
        """A mode comparison that merged its two arms would answer the question it
        exists to ask by erasing it."""
        results = [
            {"scenario": "E1", "condition": "sage", "mode": "inline",
             "pass": True, "cost_usd": 1.0, "tokens_in": 10, "tokens_out": 1},
            {"scenario": "E1", "condition": "sage", "mode": "subagents",
             "pass": False, "cost_usd": 9.0, "tokens_in": 90, "tokens_out": 9},
        ]
        v = self.R.verdicts(results, 1)
        self.assertTrue(v[("E1", "sage", "inline")]["verdict"])
        self.assertFalse(v[("E1", "sage", "subagents")]["verdict"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
