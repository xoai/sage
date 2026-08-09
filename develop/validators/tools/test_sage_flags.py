#!/usr/bin/env python3
"""
test_sage_flags.py — tests for runtime/tools/sage_flags.py (30-§4).

Ports the case intent from the former core/flag_parser/tests/ and
core/quality_locked/tests/ so the behavior those packages guaranteed survives
their deletion. Behavior was additionally proven byte-for-byte equal to the old
packages before they were removed (parity harness in the P3-T11 commit body).

Usage:  python3 develop/validators/tools/test_sage_flags.py
Exit:   0 = all pass | 1 = a test failed

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import importlib.util
import pathlib
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
MOD = REPO_ROOT / "runtime" / "tools" / "sage_flags.py"
spec = importlib.util.spec_from_file_location("sage_flags", MOD)
sf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sf)


class FlagParseTest(unittest.TestCase):
    def p(self, args, defaults=None):
        return sf.parse_flags(args, defaults)

    def test_empty_and_goal_only(self):
        self.assertEqual(self.p("")["goal"], "")
        self.assertEqual(self.p("build a widget")["goal"], "build a widget")

    def test_flag_on_and_source(self):
        r = self.p("--quality-locked go")
        self.assertTrue(r["quality_locked"])
        self.assertEqual(r["quality_locked_source"], "flag")
        self.assertEqual(r["goal"], "go")

    def test_both_flags_order_independent(self):
        a = self.p("--quality-locked --autonomous go")
        b = self.p("--autonomous --quality-locked go")
        self.assertTrue(a["quality_locked"] and a["autonomous"])
        self.assertEqual(a["goal"], b["goal"], "go")

    def test_flag_in_middle_is_goal_text(self):
        r = self.p("build --quality-locked thing")
        self.assertFalse(r["quality_locked"])
        self.assertEqual(r["goal"], "build --quality-locked thing")

    def test_unknown_flag_errors(self):
        r = self.p("--bogus go")
        self.assertIsNotNone(r["error"])
        self.assertIn("Unknown flag", r["error"])

    def test_conflict_errors(self):
        r = self.p("--quality-locked --no-quality-locked go")
        self.assertIsNotNone(r["error"])
        self.assertIn("Conflicting", r["error"])

    def test_conflict_isolated_to_one_key(self):
        # autonomous conflict must not error on quality_locked
        r = self.p("--autonomous --no-autonomous go")
        self.assertIn("autonomous", r["error"])

    def test_precedence_flag_over_config(self):
        r = self.p("--no-quality-locked go", {"quality_locked": True})
        self.assertFalse(r["quality_locked"])
        self.assertEqual(r["quality_locked_source"], "flag")

    def test_config_default_when_no_flag(self):
        r = self.p("go", {"quality_locked": True})
        self.assertTrue(r["quality_locked"])
        self.assertEqual(r["quality_locked_source"], "config")

    def test_off_by_default_source_is_none(self):
        r = self.p("go")
        self.assertIsNone(r["quality_locked_source"])

    def test_false_default_is_no_default(self):
        r = self.p("go", {"quality_locked": False})
        self.assertFalse(r["quality_locked"])
        self.assertIsNone(r["quality_locked_source"])


class ConfigLoaderTest(unittest.TestCase):
    def load(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(lambda: pathlib.Path(f.name).unlink(missing_ok=True))
        return sf.load_defaults(f.name)

    def test_none_and_missing(self):
        self.assertEqual(sf.load_defaults(None), {})
        self.assertEqual(sf.load_defaults("/no/such/file.yaml"), {})

    def test_canonical_true(self):
        self.assertEqual(self.load("quality_locked: true\nautonomous: true\n"),
                         {"quality_locked": True, "autonomous": True})

    def test_realistic_config_ignores_other_keys(self):
        self.assertEqual(self.load("project: x\nquality_locked: true\nother: 5\n"),
                         {"quality_locked": True})

    def test_rejects_noncanonical_forms(self):
        for bad in ("quality_locked: True\n", 'quality_locked: "true"\n',
                    "quality_locked: yes\n", "quality_locked:true\n",
                    "quality_locked:  true\n", "quality_locked: true  # c\n",
                    "  quality_locked: true\n"):
            self.assertEqual(self.load(bad), {}, bad)


class ClassifyTest(unittest.TestCase):
    def test_all_none(self):
        self.assertEqual(sf.classify("CRITICAL: None\nMAJOR: None"),
                         {"critical": 0, "major": 0, "substantive": 0, "cosmetic": 0})

    def test_bullets_per_severity(self):
        out = sf.classify("CRITICAL:\n- a\n- b\nMAJOR:\n- c\nMINOR-substantive:\n- d")
        self.assertEqual(out, {"critical": 2, "major": 1, "substantive": 1, "cosmetic": 0})

    def test_quality_review_format_maps_warning_to_major(self):
        out = sf.classify("WARNING:\n- x\nSUGGESTION-cosmetic:\n- y")
        self.assertEqual(out["major"], 1)
        self.assertEqual(out["cosmetic"], 1)

    def test_bracketed_none_and_empty(self):
        self.assertEqual(sf.classify("CRITICAL: [None]")["critical"], 0)
        self.assertEqual(sf.classify(""), {"critical": 0, "major": 0, "substantive": 0, "cosmetic": 0})

    def test_minor_substantive_matches_before_bare(self):
        self.assertEqual(sf.classify("MINOR-substantive:\n- a")["substantive"], 1)

    def test_case_insensitive(self):
        self.assertEqual(sf.classify("critical:\n- a")["critical"], 1)


class DecideTest(unittest.TestCase):
    def z(self, **kw):
        c = {"critical": 0, "major": 0, "substantive": 0, "cosmetic": 0}
        c.update(kw)
        return c

    def test_pass_when_clean(self):
        self.assertEqual(sf.decide(self.z(cosmetic=3), 1, [])["action"], "PASS")

    def test_substantive_blocks_clean(self):
        self.assertEqual(sf.decide(self.z(substantive=1), 1, [])["action"], "REVISE")

    def test_cap_reached(self):
        self.assertEqual(sf.decide(self.z(critical=1), 10, [])["action"], "CAP_REACHED")

    def test_pass_beats_cap(self):
        self.assertEqual(sf.decide(self.z(), 10, [])["action"], "PASS")

    def test_escalate_when_stuck(self):
        hist = [{"counts": {"critical": 1, "major": 1}}] * 3
        self.assertEqual(sf.decide(self.z(critical=1, major=1), 4, hist)["action"], "ESCALATE")

    def test_not_stuck_when_improving(self):
        hist = [{"counts": {"critical": 3, "major": 0}},
                {"counts": {"critical": 2, "major": 0}},
                {"counts": {"critical": 1, "major": 0}}]
        self.assertEqual(sf.decide(self.z(critical=1), 4, hist)["action"], "REVISE")

    def test_not_stuck_when_all_zero(self):
        hist = [{"counts": {"critical": 0, "major": 0}}] * 3
        self.assertFalse(sf.is_stuck(hist))


class SubagentModeTest(unittest.TestCase):
    """--subagents (ADR-10, C13) — the one flag the platform can refuse."""

    CC = {"name": "claude-code", "capabilities": {"subagent-dispatch": True}}
    GENERIC = {"name": "generic", "capabilities": {"subagent-dispatch": False}}

    def test_default_is_off(self):
        """C13: opt-in in v1.3.0. Flipping the default is a v1.4 decision, and it
        is one that Phase 5's cost data gets to make, not this release."""
        r = sf.parse_flags("build a thing")
        self.assertFalse(r["subagents"])
        self.assertIsNone(r["subagents_source"])

    def test_flag_turns_it_on(self):
        r = sf.parse_flags("--subagents build a thing")
        self.assertTrue(r["subagents"])
        self.assertEqual(r["subagents_source"], "flag")
        self.assertEqual(r["goal"], "build a thing")

    def test_config_default(self):
        r = sf.parse_flags("build", defaults={"subagents": True})
        self.assertTrue(r["subagents"])
        self.assertEqual(r["subagents_source"], "config")

    def test_flag_beats_config(self):
        r = sf.parse_flags("--no-subagents build", defaults={"subagents": True})
        self.assertFalse(r["subagents"])
        self.assertEqual(r["subagents_source"], "flag")

    def test_conflict_errors(self):
        r = sf.parse_flags("--subagents --no-subagents build")
        self.assertIn("Conflicting flags for subagents", r["error"])

    def test_config_regex_accepts_subagents_key(self):
        """The config-default regex was a hand-written alternation. A new key that
        parses as a flag but is not in that regex would silently ignore
        `subagents: true` in config — working flag, dead config."""
        self.assertTrue(sf._TRUE_LINE_RE.search("subagents: true"))

    # ── Availability (R97) ──

    def test_available_where_the_contract_grants_it(self):
        self.assertTrue(sf.platform_supports_subagents(self.CC))
        self.assertEqual(sf.resolve_execution_mode(True, self.CC)["mode"], "subagent")

    def test_attested_counts_as_available(self):
        c = {"name": "x", "capabilities": {"subagent-dispatch": "attested"}}
        self.assertTrue(sf.platform_supports_subagents(c))

    def test_unavailable_degrades_loudly_not_silently(self):
        """The whole v1.2.x lesson in one assertion: a user who asked for per-task
        review and silently got a single shared context has been lied to by
        omission."""
        r = sf.resolve_execution_mode(True, self.GENERIC)
        self.assertEqual(r["mode"], "inline")
        self.assertTrue(r["degraded"])
        self.assertEqual(r["manifest_value"], "inline (subagents-unavailable)")
        self.assertIn("unavailable", r["announcement"])
        self.assertIn("NOT independent", r["announcement"])

    def test_unknown_platform_degrades_rather_than_dispatching_into_a_void(self):
        r = sf.resolve_execution_mode(True, None)
        self.assertEqual(r["mode"], "inline")
        self.assertTrue(r["degraded"])

    def test_not_requesting_it_is_not_a_degradation(self):
        """Silence when nothing was asked for. The default is not news, and a
        framework that announces its own defaults trains people to ignore it."""
        r = sf.resolve_execution_mode(False, self.GENERIC)
        self.assertFalse(r["degraded"])
        self.assertIsNone(r["announcement"])


class CliBoundaryTest(unittest.TestCase):
    """The SHIPPED calling convention, exercised at the process boundary.

    Field report 2026-08-04: `/build --subagents` crashed the parser with
    argparse's "unrecognized arguments" — the preamble's documented
    invocation passes $ARGUMENTS as a positional, and a positional can
    never begin with `--` under argparse. This suite ran green throughout
    because it only ever called the Python API. These tests invoke the
    tool exactly as every generated project's instructions do; if the
    calling convention breaks again, it breaks HERE first.
    """

    def run_cli(self, *argv):
        import json as _json
        import subprocess
        import sys as _sys
        r = subprocess.run([_sys.executable, str(MOD), *argv],
                           capture_output=True, text=True)
        try:
            payload = _json.loads(r.stdout)
        except ValueError:
            payload = None
        return r.returncode, payload, r.stderr

    def cfg(self, body=""):
        d = tempfile.mkdtemp()
        p = pathlib.Path(d) / "config.yaml"
        p.write_text(body)
        return str(p)

    def test_the_shipped_invocation_with_a_leading_dash_flag(self):
        rc, out, err = self.run_cli("parse", "--subagents",
                                    "--config-path", self.cfg())
        self.assertEqual(rc, 0, err)
        self.assertIsNone(out["error"])
        self.assertTrue(out["subagents"])

    def test_multiple_flags_and_prose_in_one_payload(self):
        rc, out, _ = self.run_cli(
            "parse", "--quality-locked --autonomous fix the login bug",
            "--config-path", self.cfg())
        self.assertEqual(rc, 0)
        self.assertTrue(out["quality_locked"])
        self.assertTrue(out["autonomous"])

    def test_reordered_invocation_still_parses(self):
        """Models reorder arguments; the payload is whatever is not ours."""
        rc, out, _ = self.run_cli("parse", "--config-path", self.cfg(),
                                  "--subagents")
        self.assertEqual(rc, 0)
        self.assertTrue(out["subagents"])

    def test_config_path_equals_form(self):
        rc, out, _ = self.run_cli("parse", "--subagents",
                                  "--config-path=" + self.cfg())
        self.assertEqual(rc, 0)
        self.assertTrue(out["subagents"])

    def test_empty_arguments_yield_defaults(self):
        rc, out, _ = self.run_cli("parse", "",
                                  "--config-path", self.cfg("subagents: true\n"))
        self.assertEqual(rc, 0)
        self.assertTrue(out["subagents"],
                        "config default survives an empty $ARGUMENTS")

    def test_explicit_separator_is_honored(self):
        rc, out, _ = self.run_cli("parse", "--", "--subagents")
        self.assertEqual(rc, 0)
        self.assertTrue(out["subagents"])

    def test_parse_help_still_prints_help(self):
        rc, _, _ = self.run_cli("parse", "-h")
        self.assertEqual(rc, 0)


class ParallelFlagTest(unittest.TestCase):
    """A7 — `--parallel[=N]`: the one value-taking flag. Default cap 2,
    hard cap 4 (clamped loudly, never errored), off unless asked, and only
    meaningful inside subagent execution (resolve_parallel)."""

    def p(self, args, defaults=None):
        return sf.parse_flags(args, defaults)

    def test_off_by_default(self):
        r = self.p("build a thing")
        self.assertFalse(r["parallel"])
        self.assertEqual(r["parallel_lanes"], 0)
        self.assertIsNone(r["parallel_note"])

    def test_bare_flag_gets_the_default_cap(self):
        r = self.p("--parallel go")
        self.assertTrue(r["parallel"])
        self.assertEqual(r["parallel_lanes"], sf.DEFAULT_LANE_CAP)
        self.assertEqual(r["parallel_source"], "flag")
        self.assertEqual(r["goal"], "go")

    def test_explicit_lane_count(self):
        self.assertEqual(self.p("--parallel=3 go")["parallel_lanes"], 3)

    def test_over_the_hard_cap_clamps_loudly(self):
        r = self.p("--parallel=9 go")
        self.assertEqual(r["parallel_lanes"], sf.HARD_LANE_CAP)
        self.assertIn("hard cap", r["parallel_note"])
        self.assertIsNone(r["error"])

    def test_zero_or_garbage_lane_count_errors(self):
        for bad in ("--parallel=0", "--parallel=two", "--parallel=-1",
                    "--parallel="):
            r = self.p(bad + " go")
            self.assertTrue(r["error"], bad)
            self.assertEqual(r["parallel_lanes"], 0, bad)

    def test_only_parallel_takes_a_value(self):
        r = self.p("--subagents=3 go")
        self.assertIn("takes no value", r["error"])

    def test_no_parallel_beats_config(self):
        r = self.p("--no-parallel go", {"parallel": True})
        self.assertFalse(r["parallel"])
        self.assertEqual(r["parallel_lanes"], 0)

    def test_config_default_gets_the_default_cap(self):
        r = self.p("go", {"parallel": True})
        self.assertTrue(r["parallel"])
        self.assertEqual(r["parallel_lanes"], sf.DEFAULT_LANE_CAP)
        self.assertEqual(r["parallel_source"], "config")

    def test_conflict_errors(self):
        r = self.p("--parallel --no-parallel go")
        self.assertIn("Conflicting", r["error"])

    def test_config_regex_accepts_parallel_key(self):
        self.assertRegex("parallel: true", sf._TRUE_LINE_RE)

    def test_with_subagents_both_parse(self):
        r = self.p("--subagents --parallel=3 build it")
        self.assertTrue(r["subagents"])
        self.assertEqual(r["parallel_lanes"], 3)
        self.assertEqual(r["goal"], "build it")


class ResolveParallelTest(unittest.TestCase):
    """Parallel exists only inside subagent execution — anything else is the
    LOUD degradation contract (ADR-10), never a silent fallback."""

    SUBAGENT = {"mode": "subagent", "degraded": False}
    INLINE = {"mode": "inline", "degraded": True}

    def test_not_requested_is_quiet(self):
        r = sf.resolve_parallel(0, self.SUBAGENT)
        self.assertFalse(r["parallel"])
        self.assertFalse(r["degraded"])
        self.assertIsNone(r["announcement"])
        self.assertEqual(r["manifest_value"], "sequential")

    def test_granted_inside_subagent_mode(self):
        r = sf.resolve_parallel(3, self.SUBAGENT)
        self.assertTrue(r["parallel"])
        self.assertEqual(r["lanes"], 3)
        self.assertEqual(r["manifest_value"], "parallel=3")
        self.assertIsNone(r["announcement"])

    def test_refused_outside_subagent_mode_is_loud(self):
        r = sf.resolve_parallel(2, self.INLINE)
        self.assertFalse(r["parallel"])
        self.assertTrue(r["degraded"])
        self.assertIn("requires subagent execution", r["announcement"])
        self.assertEqual(r["manifest_value"],
                         "sequential (parallel-requires-subagents)")

    def test_mode_string_form_accepted(self):
        self.assertTrue(sf.resolve_parallel(2, "subagent")["parallel"])
        self.assertTrue(sf.resolve_parallel(2, "inline")["degraded"])

    def test_hard_cap_holds_here_too(self):
        self.assertEqual(sf.resolve_parallel(9, self.SUBAGENT)["lanes"],
                         sf.HARD_LANE_CAP)


if __name__ == "__main__":
    unittest.main(verbosity=2)
