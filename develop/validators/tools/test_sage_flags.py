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


if __name__ == "__main__":
    unittest.main(verbosity=2)
