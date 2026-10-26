#!/usr/bin/env python3
"""
test_verify_baseline.py — Gate 5's baseline never excuses a failure it cannot
prove was already there (review 2026-10-26, L2).

The parser under test is the one sage-verify.sh embeds — extracted from the
script itself, so this cannot drift from what the gate runs. The fixtures are
REAL runner output (pytest, go, node --test, jest, vitest, mocha), captured
from small projects: each runner's baseline run, and a run where the cycle
added a failure designed to collide with a baseline one — the same leaf title
under another describe, a parametrize id with spaces, a new failure next to an
unhandled error, a collection error. Every one of those must come back NEW or
unattributable; a single EXCUSED here would be a gate that passes a broken
suite.

Usage:  python3 develop/validators/gates/test_verify_baseline.py
Exit:   0 = all pass | 1 = a test failed
Python 3.8+, stdlib only.
"""
from __future__ import annotations

import pathlib
import re
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
VERIFY = REPO_ROOT / "core" / "gates" / "scripts" / "sage-verify.sh"
OUT = pathlib.Path(__file__).resolve().parent / "fixtures" / "baseline-outputs"


def _load_parser():
    text = VERIFY.read_text(encoding="utf-8")
    m = re.search(r"cat > \"\$PY_BASE\" <<'PYEOF'\n(.*?)\nPYEOF\n", text, re.S)
    assert m, "sage-verify.sh no longer embeds the baseline helper"
    ns = {"__name__": "verify_baseline"}
    argv, sys.argv = sys.argv, ["verify_baseline", "--no-verb--"]
    try:
        exec(compile(m.group(1), str(VERIFY), "exec"), ns)
    finally:
        sys.argv = argv
    return ns


P = _load_parser()


def parse(runner, name):
    return P["parse"](runner, str(OUT / name))


class Attributable(unittest.TestCase):
    def assertIds(self, runner, name, expected):
        ids, files, why = parse(runner, name)
        self.assertIsNotNone(ids, why)
        self.assertEqual(sorted(ids), sorted(expected))

    def test_pytest_keeps_parametrize_ids_whole(self):
        self.assertIds("pytest", "pytest-baseline.txt", [
            "tests/test_a.py::test_old", "tests/test_a.py::test_p[a b]",
            "tests/test_a.py::test_p[a - b]", "tests/test_a.py::TestK::test_m",
            "tests/test_a.py::test_err"])

    def test_go_qualifies_by_package(self):
        self.assertIds("go-test", "go-baseline.txt", [
            "ex::TestA", "ex::TestA/x_y", "ex::TestB", "ex/sub::TestB"])

    def test_node_qualifies_by_location_and_marks_unloadable_files(self):
        ids, files, why = parse("npm-test", "node-baseline.txt")
        self.assertIsNotNone(ids, why)
        self.assertIn("test/a.test.mjs:4:26 formats", ids)
        self.assertIn("test/a.test.mjs:8:39 child fails", ids)     # leaf, not parent
        self.assertEqual(list(files.values()), ["test/load.test.mjs"])

    def test_jest_qualifies_by_file_and_describe_path(self):
        ids, files, why = parse("jest", "jest-baseline.txt")
        self.assertIsNotNone(ids, why)
        self.assertIn("test/a.test.js › Report › v1 › formats", ids)
        self.assertEqual(list(files.values()), ["test/load.test.js"])

    def test_vitest_qualifies_by_file_and_describe_path(self):
        ids, files, why = parse("vitest", "vitest-baseline.txt")
        self.assertIsNotNone(ids, why)
        self.assertIn("test/a.test.js > Report > v1 > formats", ids)
        self.assertEqual(list(files.values()), ["test/load.test.js"])

    def test_mocha_reads_the_full_title_and_keeps_numbers_in_it(self):
        self.assertIds("mocha", "mocha-baseline.txt", [
            "top fails", "Report › v1 › formats", "Report › v2 › waits 5s"])


class NeverExcused(unittest.TestCase):
    """The cycle's new failure collides with a baseline one by name. It must
    come back as NEW — or as unattributable — never inside the baseline."""

    def assertNew(self, runner, baseline, after, new_id):
        base, _, why = parse(runner, baseline)
        self.assertIsNotNone(base, why)
        ids, _, why = parse(runner, after)
        self.assertIsNotNone(ids, why)
        self.assertIn(new_id, ids)
        self.assertNotIn(new_id, base)

    def test_pytest_new_param_in_the_same_test(self):
        self.assertNew("pytest", "pytest-baseline.txt", "pytest-new-param.txt",
                       "tests/test_a.py::test_p[a c]")

    def test_go_new_test(self):
        self.assertNew("go-test", "go-baseline.txt", "go-new.txt", "ex::TestC")

    def test_node_same_leaf_title_elsewhere(self):
        base, _, _ = parse("npm-test", "node-baseline.txt")
        ids, _, why = parse("npm-test", "node-same-title.txt")
        self.assertIsNotNone(ids, why)
        self.assertTrue(set(ids) - set(base), ids)

    def test_jest_same_leaf_title_under_another_describe(self):
        self.assertNew("jest", "jest-baseline.txt", "jest-same-title.txt",
                       "test/a.test.js › Report › v2 › formats")

    def test_mocha_same_leaf_title_under_another_describe(self):
        self.assertNew("mocha", "mocha-baseline.txt", "mocha-same-title.txt",
                       "Report › v2 › formats")

    def test_pytest_collection_error_is_unattributable(self):
        ids, _, why = parse("pytest", "pytest-collection-error.txt")
        self.assertIsNone(ids)
        self.assertIn("Interrupted", why)

    def test_vitest_unhandled_error_is_unattributable(self):
        ids, _, why = parse("vitest", "vitest-unhandled.txt")
        self.assertIsNone(ids)
        self.assertIn("Unhandled", why)


class SecondReview(unittest.TestCase):
    """The second independent review's shapes (2026-10-26): tests that never
    ran, errors outside any test, and two false alarms."""

    def test_go_test_that_kills_the_binary_is_unattributable(self):
        ids, _, why = parse("go-test", "go-fatal.txt")       # log.Fatal in TestZNew
        self.assertIsNone(ids)
        self.assertIn("TestZNew never finished", why)

    def test_node_async_activity_after_a_test_is_unattributable(self):
        ids, _, why = parse("npm-test", "node-async.txt")
        self.assertIsNone(ids)
        self.assertIn("ℹ Error", why)

    def test_vitest_failing_hook_is_a_suite_that_did_not_run(self):
        base, _, _ = parse("vitest", "vitest-baseline.txt")
        ids, files, why = parse("vitest", "vitest-hook.txt")
        self.assertIsNotNone(ids, why)
        self.assertIn("test/b.test.js > Limiter <suite did not run>", ids)
        self.assertNotIn("test/b.test.js > Limiter <suite did not run>", base)
        self.assertEqual(files["test/b.test.js > Limiter <suite did not run>"],
                         "test/b.test.js")

    def test_marker_text_in_a_passing_title_is_not_a_banner(self):
        ids, _, why = parse("vitest", "vitest-title-marker.txt")
        self.assertIsNotNone(ids, why)

    def test_mocha_title_ending_in_a_colon_keeps_each_test_apart(self):
        base, _, why = parse("mocha", "mocha-colon-base.txt")
        self.assertIsNotNone(base, why)
        self.assertIn("Config: › reads the port", base)
        ids, _, why = parse("mocha", "mocha-colon-after.txt")
        self.assertIn("Config: › reads the host", ids)
        self.assertNotIn("Config: › reads the host", base)

    def test_mocha_failing_hook_is_unattributable(self):
        ids, _, why = parse("mocha", "mocha-hook.txt")
        self.assertIsNone(ids)
        self.assertIn("hook", why)


class FailFast(unittest.TestCase):
    """The final review's HIGH: a fail-fast setting stops the run at the first
    (pre-existing) failure, so every later failure — the cycle's — never runs
    and the output names only baseline ids. Sage's own argv overrides it
    (pytest --maxfail=0, mocha --no-bail, go -failfast=false); for any run,
    fewer tests than the baseline ran, or an incomplete count, is never
    excused."""

    def ran(self, runner, name):
        return P["tests_ran"](runner, str(OUT / name))

    def test_pytest_x_banner_is_unattributable(self):
        self.assertIsNone(parse("pytest", "pytest-x.txt")[0])

    def test_go_failfast_ran_fewer_tests(self):
        self.assertLess(self.ran("go-test", "go-failfast.txt"),
                        self.ran("go-test", "go-baseline.txt"))

    def test_mocha_bail_ran_fewer_tests(self):
        self.assertLess(self.ran("mocha", "mocha-bail.txt"),
                        self.ran("mocha", "mocha-baseline.txt"))

    def test_vitest_bail_is_an_incomplete_count(self):
        self.assertIsNone(self.ran("vitest", "vitest-bail.txt"))

    def test_counts_for_complete_runs(self):
        self.assertEqual(self.ran("pytest", "pytest-baseline.txt"), 5)
        self.assertEqual(self.ran("jest", "jest-baseline.txt"), 3)
        self.assertEqual(self.ran("vitest", "vitest-baseline.txt"), 3)
        self.assertEqual(self.ran("npm-test", "node-baseline.txt"), 6)

    def test_jest_partial_suite_run_is_incomplete(self):
        text = (OUT / "jest-baseline.txt").read_text().replace(
            "Test Suites: 2 failed, 2 total", "Test Suites: 1 failed, 1 of 2 total")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(text)
        try:
            self.assertIsNone(P["tests_ran"]("jest", fh.name))
        finally:
            pathlib.Path(fh.name).unlink()


class Completeness(unittest.TestCase):
    """When the runner counts more failures than could be named, nothing is
    excused — the unnamed one could be anything."""

    def test_pytest_count_mismatch(self):
        text = (OUT / "pytest-baseline.txt").read_text().replace(
            "4 failed, 1 error", "5 failed, 1 error")
        ids, _, why = P["_pytest"](text)
        self.assertIsNone(ids)
        self.assertIn("6 failure(s), 5 named", why)

    def test_jest_count_mismatch(self):
        text = (OUT / "jest-baseline.txt").read_text().replace(
            "Tests:       2 failed", "Tests:       3 failed")
        self.assertIsNone(P["_jest"](text)[0])

    def test_mocha_count_mismatch(self):
        text = (OUT / "mocha-baseline.txt").read_text().replace("3 failing", "4 failing")
        self.assertIsNone(P["_mocha"](text)[0])

    def test_node_leaf_count_mismatch(self):
        text = (OUT / "node-baseline.txt").read_text().replace(
            "✖ failing tests:", "✖ extra leaf (1ms)\n✖ failing tests:", 1)
        self.assertIsNone(P["_node"](text)[0])

    def test_go_package_failure_without_a_named_test(self):
        self.assertIsNone(P["_go"]("FAIL\tex\t0.1s\n")[0])

    def test_unknown_runner_output(self):
        self.assertIsNone(P["parse"]("flutter-test", str(OUT / "go-baseline.txt"))[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
