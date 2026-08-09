"""lanes.py — the parallel-lane scheduler and single writer, pinned. (A7)

The rule under test: dispatch is a CODE decision. Parallel-eligible iff
[P] + depends MERGED + files disjoint from in-flight claims; overlap
serializes; non-[P] runs alone; parked/errored freeze dependents and
hold claims; merges happen in dependency order and abort on conflict
rather than being resolved by model judgment.
"""
import contextlib
import io
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runtime" / "tools"))

import lanes as L       # noqa: E402
import manifest as MAN  # noqa: E402


def T(tid, files, depends=(), parallel=True):
    return {"id": tid, "title": "t%d" % tid, "files": list(files),
            "depends": list(depends), "parallel": parallel}


def graph(*tasks):
    return {"derived_from": "plan@abcd1234", "tasks": list(tasks)}


def lane(tid, state="open", branch=None, note=""):
    return {"task": tid, "branch": branch or "lane/t%d" % tid,
            "worktree": "../wt-t%d" % tid, "state": state,
            "model": "inherit", "note": note}


def lanes_block(*records, base="abc1234"):
    return {"burst_base": base, "records": list(records)}


class ScheduleTableTest(unittest.TestCase):
    """The scheduler decision table — the pack's graph cases."""

    def sched(self, g, statuses=None, lanes=None, cap=2):
        return L.schedule(g, statuses or {}, lanes, cap)

    def test_two_disjoint_P_tasks_dispatch_together(self):
        d = self.sched(graph(T(1, ["src/a.ts"]), T(2, ["src/b.ts"])))
        self.assertEqual(d["dispatch"], [1, 2])
        self.assertFalse(d["exclusive"])

    def test_cap_holds_the_third(self):
        d = self.sched(graph(T(1, ["a"]), T(2, ["b"]), T(3, ["c"])), cap=2)
        self.assertEqual(d["dispatch"], [1, 2])
        self.assertEqual(d["capped"], [3])

    def test_overlap_forces_serial_exact(self):
        d = self.sched(graph(T(1, ["src/shared.ts"]), T(2, ["src/shared.ts"])))
        self.assertEqual(d["dispatch"], [1])
        self.assertEqual(d["serialized"][0][0], 2)
        self.assertIn("overlap", d["serialized"][0][1])

    def test_overlap_forces_serial_glob_vs_file(self):
        """A dir glob and a file under it are a DECLARED overlap — string
        inequality must not launder it."""
        d = self.sched(graph(T(1, ["src/auth/**"]), T(2, ["src/auth/token.ts"])))
        self.assertEqual(d["dispatch"], [1])
        self.assertEqual([t for t, _ in d["serialized"]], [2])

    def test_overlap_with_an_inflight_lane_serializes(self):
        d = self.sched(graph(T(1, ["src/auth/**"]), T(2, ["src/auth/x.ts"])),
                       lanes=lanes_block(lane(1)))
        self.assertEqual(d["dispatch"], [])
        self.assertEqual([t for t, _ in d["serialized"]], [2])

    def test_parked_lane_freezes_dependents_siblings_continue(self):
        """The pack's blocked-freezes-dependents row: T2 depends on parked
        T1 and freezes; T3 is independent and still dispatches."""
        g = graph(T(1, ["a"]), T(2, ["b"], depends=[1]), T(3, ["c"]))
        d = self.sched(g, lanes=lanes_block(lane(1, state="parked")))
        self.assertEqual([t for t, _ in d["frozen"]], [2])
        self.assertIn("parked", d["frozen"][0][1])
        self.assertEqual(d["dispatch"], [3])

    def test_errored_lane_also_freezes_dependents(self):
        g = graph(T(1, ["a"]), T(2, ["b"], depends=[1]))
        d = self.sched(g, lanes=lanes_block(lane(1, state="errored")))
        self.assertEqual([t for t, _ in d["frozen"]], [2])

    def test_dep_in_flight_is_waiting_not_frozen(self):
        g = graph(T(1, ["a"]), T(2, ["b"], depends=[1]))
        d = self.sched(g, lanes=lanes_block(lane(1, state="open")))
        self.assertEqual(d["waiting"], [2])
        self.assertEqual(d["frozen"], [])

    def test_merged_lane_satisfies_the_edge(self):
        g = graph(T(1, ["a"]), T(2, ["b"], depends=[1]))
        d = self.sched(g, lanes=lanes_block(lane(1, state="merged")))
        self.assertEqual(d["dispatch"], [2])

    def test_sequentially_done_task_satisfies_the_edge(self):
        """A task completed on the sequential path (status done, no lane)
        counts as merged — the graph predates the parallel opt-in."""
        g = graph(T(1, ["a"]), T(2, ["b"], depends=[1]))
        d = self.sched(g, statuses={1: "done"})
        self.assertEqual(d["dispatch"], [2])

    def test_non_P_task_runs_alone(self):
        g = graph(T(1, ["a"], parallel=False), T(2, ["b"]))
        d = self.sched(g)
        self.assertEqual(d["dispatch"], [1])
        self.assertTrue(d["exclusive"])
        self.assertEqual([t for t, _ in d["serialized"]], [2])

    def test_non_P_task_waits_for_the_burst(self):
        g = graph(T(1, ["a"]), T(2, ["b"], parallel=False))
        d = self.sched(g, lanes=lanes_block(lane(1)))
        self.assertEqual(d["dispatch"], [])
        self.assertEqual([t for t, _ in d["serialized"]], [2])

    def test_inflight_non_P_lane_owns_the_burst(self):
        g = graph(T(1, ["a"], parallel=False), T(2, ["b"]))
        d = self.sched(g, lanes=lanes_block(lane(1)))
        self.assertEqual(d["dispatch"], [])
        self.assertIn("runs alone", d["serialized"][0][1])

    def test_failed_dep_freezes_not_waits(self):
        g = graph(T(1, ["a"]), T(2, ["b"], depends=[1]))
        d = self.sched(g, lanes=lanes_block(lane(1, state="failed")))
        self.assertEqual([t for t, _ in d["frozen"]], [2])


class HardeningTest(unittest.TestCase):
    """A9 — coupling serialization, budget stops, the one ungraded retry."""

    def sched(self, g, statuses=None, lanes=None, cap=2, **kw):
        return L.schedule(g, statuses or {}, lanes, cap, **kw)

    def test_ontology_coupling_warns_and_serializes(self):
        """Disjoint files, met deps — but the consult says the modules are
        coupled. Coupled ⇒ serialize; the second task waits."""
        g = graph(T(1, ["src/auth.py"]), T(2, ["src/session.py"]))
        d = self.sched(g, couplings=[{"a": 1, "b": 2,
                                      "via": "models.TokenPayload"}])
        self.assertEqual(d["dispatch"], [1])
        self.assertEqual(d["serialized"][0][0], 2)
        self.assertIn("ontology: coupled to T1 via models.TokenPayload",
                      d["serialized"][0][1])

    def test_coupling_to_an_inflight_lane_serializes_too(self):
        g = graph(T(1, ["src/auth.py"]), T(2, ["src/session.py"]))
        d = self.sched(g, lanes=lanes_block(lane(1)),
                       couplings=[{"a": 1, "b": 2}])
        self.assertEqual(d["dispatch"], [])
        self.assertIn("ontology: coupled", d["serialized"][0][1])

    def test_uncoupled_pairs_are_untouched_by_the_consult(self):
        g = graph(T(1, ["a"]), T(2, ["b"]), T(3, ["c"]))
        d = self.sched(g, cap=3, couplings=[{"a": 1, "b": 3}])
        self.assertEqual(d["dispatch"], [1, 2])
        self.assertEqual([t for t, _ in d["serialized"]], [3])

    def test_budget_exhaustion_holds_new_starts_explicitly(self):
        """No new starts, in-flight completes, held tasks REPORTED — a
        budget stop must never be a silent truncation."""
        g = graph(T(1, ["a"]), T(2, ["b"]))
        d = self.sched(g, lanes=lanes_block(lane(1)), budget_exhausted=True)
        self.assertEqual(d["dispatch"], [])
        self.assertEqual(d["budget_held"], [2])
        self.assertEqual(d["serialized"], [])


A_MANIFEST = """\
---
cycle_id: "005-par"
status: in-progress
gate_state: building
updated: 2026-01-01 00:00
execution_mode: subagent
tasks:
  - id: 1
    title: types
    status: pending
    attempts: 0
    model: ""
    lane_branch: ""
    review: pending
    commits: ""
  - id: 2
    title: auth
    status: pending
    attempts: 0
    model: ""
    lane_branch: ""
    review: pending
    commits: ""
  - id: 3
    title: session
    status: pending
    attempts: 0
    model: ""
    lane_branch: ""
    review: pending
    commits: ""
%s
---

# Cycle 005
"""


def manifest_with(graph_tasks):
    return A_MANIFEST % MAN._task_graph_block_lines("plan@abcd1234",
                                                    graph_tasks)


class OpenMarkTest(unittest.TestCase):
    """The single-writer surface: open/mark write the lanes: block AND the
    ledger's lane fields in one tool pass — never by hand."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="lanes-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.m = self.d / "manifest.md"
        self.m.write_text(manifest_with(
            [T(1, ["src/a.ts"]), T(2, ["src/b.ts"], depends=[1]),
             T(3, ["src/c.ts"])]))

    def quiet(self, fn, *a, **k):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*a, **k)

    def test_open_records_lane_and_marks_the_ledger(self):
        self.quiet(L.cmd_open, self.m, 1, "lane/t1-types", "../wt-t1",
                   "cheap/model", "abc1234", 2)
        text = self.m.read_text()
        lanes = MAN.read_lanes(text)
        self.assertEqual(lanes["burst_base"], "abc1234")
        self.assertEqual(lanes["records"][0]["task"], 1)
        self.assertEqual(lanes["records"][0]["state"], "open")
        self.assertIn("status: in-progress", text)
        self.assertIn("attempts: 1", text)
        self.assertIn('model: "cheap/model"', text)
        self.assertIn('lane_branch: "lane/t1-types"', text)

    def test_open_refuses_an_unmet_dependency(self):
        with self.assertRaises(L.Problem) as ctx:
            self.quiet(L.cmd_open, self.m, 2, "lane/t2", "../wt", "", "", 2)
        self.assertIn("not dispatchable", str(ctx.exception))

    def test_open_refuses_an_overlap(self):
        self.m.write_text(manifest_with(
            [T(1, ["src/auth/**"]), T(2, ["src/auth/x.ts"])]))
        self.quiet(L.cmd_open, self.m, 1, "lane/t1", "../wt1", "", "sha1", 2)
        with self.assertRaises(L.Problem) as ctx:
            self.quiet(L.cmd_open, self.m, 2, "lane/t2", "../wt2", "",
                       "sha1", 2)
        self.assertIn("overlap", str(ctx.exception))

    def test_open_refuses_a_second_lane_for_the_same_task(self):
        self.quiet(L.cmd_open, self.m, 1, "lane/t1", "../wt1", "", "s", 2)
        with self.assertRaises(L.Problem):
            self.quiet(L.cmd_open, self.m, 1, "lane/t1b", "../wt1b", "",
                       "s", 2)

    def test_open_refuses_a_mid_burst_base_change(self):
        """Dependent work forks from merged HEAD in a NEW burst — a second
        base mid-burst means someone is building on unmerged state."""
        self.quiet(L.cmd_open, self.m, 1, "lane/t1", "../wt1", "", "sha-A", 2)
        with self.assertRaises(L.Problem) as ctx:
            self.quiet(L.cmd_open, self.m, 3, "lane/t3", "../wt3", "",
                       "sha-B", 2)
        self.assertIn("burst base mismatch", str(ctx.exception))

    def test_mark_parked_blocks_the_ledger_task(self):
        self.quiet(L.cmd_open, self.m, 1, "lane/t1", "../wt1", "", "s", 2)
        self.quiet(L.cmd_mark, self.m, 1, "parked", "waiting on a decision")
        text = self.m.read_text()
        lanes = MAN.read_lanes(text)
        self.assertEqual(lanes["records"][0]["state"], "parked")
        self.assertEqual(lanes["records"][0]["note"], "waiting on a decision")
        self.assertIn("status: blocked", text)

    def test_mark_cannot_write_merged(self):
        """merged is the state that satisfies depends edges; it comes only
        from an actual `lanes.py merge` — never from prose."""
        self.quiet(L.cmd_open, self.m, 1, "lane/t1", "../wt1", "", "s", 2)
        with self.assertRaises(L.Problem):
            self.quiet(L.cmd_mark, self.m, 1, "merged", "")

    def test_everything_requires_a_derived_graph(self):
        (self.d / "bare.md").write_text("---\ngate_state: building\n---\n")
        with self.assertRaises(L.Problem) as ctx:
            self.quiet(L.cmd_schedule, self.d / "bare.md", 2)
        self.assertIn("task_graph", str(ctx.exception))

    def test_schedule_without_couplings_announces_the_degradation(self):
        """A9's standing line: an UNCHECKED coupling must never read as
        checked-and-clean."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            L.cmd_schedule(self.m, 2)
        self.assertIn("ontology consult: UNAVAILABLE", out.getvalue())
        self.assertIn("UNCHECKED", out.getvalue())

    def test_schedule_with_couplings_file_consumes_it(self):
        cj = self.d / "couplings.json"
        cj.write_text('{"pairs": [{"a": 1, "b": 3, "via": "shared types"}]}')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            L.cmd_schedule(self.m, 2, couplings_path=str(cj))
        self.assertNotIn("UNAVAILABLE", out.getvalue())
        self.assertIn("ontology: coupled to T1 via shared types",
                      out.getvalue())

    def test_retry_is_once_ungraded_and_leaves_attempts_alone(self):
        """The errored contract: one staggered retry, never graded, never
        a quality-locked attempt — attempts counts dispatches the quality
        loop judges, and this one it never judged."""
        self.quiet(L.cmd_open, self.m, 1, "lane/t1", "../wt1", "", "s", 2)
        self.quiet(L.cmd_mark, self.m, 1, "errored",
                   "rate-limit: tokens/min exceeded")
        self.assertIn("attempts: 1", self.m.read_text())
        self.quiet(L.cmd_retry, self.m, 1)
        text = self.m.read_text()
        rec = MAN.read_lanes(text)["records"][0]
        self.assertEqual(rec["state"], "open")
        self.assertEqual(rec["retries"], 1)
        self.assertIn("attempts: 1", text,
                      "a retry is not a graded attempt")
        # …and only once.
        self.quiet(L.cmd_mark, self.m, 1, "errored", "again")
        with self.assertRaises(L.Problem) as ctx:
            self.quiet(L.cmd_retry, self.m, 1)
        self.assertIn("one retry", str(ctx.exception))

    def test_retry_refuses_a_failed_lane(self):
        self.quiet(L.cmd_open, self.m, 1, "lane/t1", "../wt1", "", "s", 2)
        self.quiet(L.cmd_mark, self.m, 1, "failed", "review cap hit")
        with self.assertRaises(L.Problem) as ctx:
            self.quiet(L.cmd_retry, self.m, 1)
        self.assertIn("ERRORED", str(ctx.exception))

    def test_budget_stopped_may_mark_a_never_dispatched_task(self):
        """The burst ran out before T3's turn — that still leaves an
        explicit record, never a silent truncation graded as failure."""
        self.quiet(L.cmd_mark, self.m, 3, "budget-stopped",
                   "parallel_budget exhausted at burst 1")
        rec = next(r for r in MAN.read_lanes(self.m.read_text())["records"]
                   if r["task"] == 3)
        self.assertEqual(rec["state"], "budget-stopped")
        self.assertEqual(rec["branch"], "")
        self.assertIn("status: pending", self.m.read_text())

    def test_mark_other_states_still_require_a_record(self):
        with self.assertRaises(L.Problem):
            self.quiet(L.cmd_mark, self.m, 3, "parked", "no lane yet")


class MergeTest(unittest.TestCase):
    """Dependency-order merges; conflict aborts and reports — the merge is
    never resolved by model judgment."""

    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="lanes-merge-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.repo = self.d / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        (self.repo / "a.txt").write_text("base-a\n")
        (self.repo / "b.txt").write_text("base-b\n")
        self.commit("base")
        self.main = self.git("rev-parse", "--abbrev-ref",
                             "HEAD").stdout.strip()
        self.branch("lane-t1", "a.txt", "t1-change\n")
        self.branch("lane-t2", "b.txt", "t2-change\n")
        self.branch("lane-t3", "a.txt", "t3-conflicting\n")

        cyc = self.repo / ".sage" / "work" / "005-par"
        cyc.mkdir(parents=True)
        self.m = cyc / "manifest.md"
        text = manifest_with(
            [T(1, ["a.txt"]), T(2, ["b.txt"], depends=[1]), T(3, ["a.txt"])])
        lanes = [lane(1, branch="lane-t1"), lane(2, branch="lane-t2"),
                 lane(3, branch="lane-t3")]
        self.m.write_text(MAN.write_lanes_block(
            text, MAN._lanes_block_lines("base", lanes)))

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args],
                              capture_output=True, text=True)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def branch(self, name, path, content):
        self.git("checkout", "-q", "-b", name)
        (self.repo / path).write_text(content)
        self.commit(name)
        self.git("checkout", "-q", self.main)

    def merge(self, task):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = L.cmd_merge(self.m, task, self.repo)
        return rc, out.getvalue()

    def test_dependency_order_is_enforced(self):
        with self.assertRaises(L.Problem) as ctx:
            self.merge(2)
        self.assertIn("dependency order", str(ctx.exception))

    def test_clean_merges_land_in_order(self):
        rc, out = self.merge(1)
        self.assertEqual(rc, 0, out)
        self.assertIn("Integration proof still required", out)
        rc, _ = self.merge(2)
        self.assertEqual(rc, 0)
        lanes = MAN.read_lanes(self.m.read_text())
        states = {r["task"]: r["state"] for r in lanes["records"]}
        self.assertEqual(states[1], "merged")
        self.assertEqual(states[2], "merged")
        self.assertEqual((self.repo / "a.txt").read_text(), "t1-change\n")
        self.assertEqual((self.repo / "b.txt").read_text(), "t2-change\n")

    def test_conflict_aborts_and_files_a_scope_finding(self):
        rc, _ = self.merge(1)
        self.assertEqual(rc, 0)
        rc, out = self.merge(3)
        self.assertEqual(rc, 1)
        self.assertIn("declared-disjoint violated", out)
        self.assertIn("a.txt", out)
        self.assertIn("scope finding", out)
        self.assertIn("Never resolve a lane conflict by model judgment", out)
        # The tree is left clean (merge aborted), the lane stays open with
        # the conflict noted, and T1's change survives untouched.
        self.assertEqual(self.git("status", "--porcelain",
                                  "--untracked-files=no").stdout.strip(), "")
        self.assertEqual((self.repo / "a.txt").read_text(), "t1-change\n")
        rec = next(r for r in MAN.read_lanes(self.m.read_text())["records"]
                   if r["task"] == 3)
        self.assertEqual(rec["state"], "open")
        self.assertIn("merge-conflict: a.txt", rec["note"])

    def test_dirty_tracked_tree_refuses_to_merge(self):
        (self.repo / "a.txt").write_text("uncommitted\n")
        with self.assertRaises(L.Problem) as ctx:
            self.merge(1)
        self.assertIn("uncommitted tracked changes", str(ctx.exception))

    def test_burst_base_assertion_refuses_a_stale_base(self):
        """A9(4) as a scheduler assertion: with the integration checkout
        reachable, a new burst's base must BE its HEAD — dependent context
        packets are built from merged HEAD, not from memory."""
        m2 = self.repo / ".sage" / "work" / "005-par" / "m2.md"
        m2.write_text(manifest_with([T(1, ["b.txt"])]))
        head = self.git("rev-parse", "--short", "HEAD").stdout.strip()
        with self.assertRaises(L.Problem) as ctx:
            with contextlib.redirect_stdout(io.StringIO()):
                L.cmd_open(m2, 1, "lane-t1b", "../wt1b", "", "fffffff", 2,
                           repo_root=self.repo)
        self.assertIn("not the integration checkout's HEAD",
                      str(ctx.exception))
        with contextlib.redirect_stdout(io.StringIO()):
            L.cmd_open(m2, 1, "lane-t1b", "../wt1b", "", head, 2,
                       repo_root=self.repo)
        self.assertEqual(MAN.read_lanes(m2.read_text())["burst_base"], head)

    def test_only_an_open_lane_merges(self):
        with contextlib.redirect_stdout(io.StringIO()):
            L.cmd_mark(self.m, 1, "parked", "q pending")
        with self.assertRaises(L.Problem) as ctx:
            self.merge(1)
        self.assertIn("no OPEN lane", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
