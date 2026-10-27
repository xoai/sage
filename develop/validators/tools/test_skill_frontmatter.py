#!/usr/bin/env python3
"""
test_skill_frontmatter.py — tests for runtime/tools/skill_frontmatter.py.

Pins the two Claude Code install defects from the 2026-10-26 review:
  C2 — folded and long quoted descriptions produced empty or invalid stubs, so
       Claude Code silently dropped 9 of 33 skills;
  C1 — the Hermes port of the workflows (and a skill named `sage`, which
       shadows the /sage command) was deployed to .claude/skills/.

The check tests use the stub format the OLD generator actually wrote, so they
fail if check-claude ever goes back to accepting it. The real-tree tests run
over skills/, core/system-skills/ and packs/: a new skill whose frontmatter a
strict YAML reader would reject fails here, not silently in a user's session.

Usage:  python3 develop/validators/tools/test_skill_frontmatter.py
Exit:   0 = all pass | 1 = a test failed

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import importlib.util
import pathlib
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
MOD = REPO_ROOT / "runtime" / "tools" / "skill_frontmatter.py"
spec = importlib.util.spec_from_file_location("skill_frontmatter", MOD)
sf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sf)

LOADER = "Read and follow the full skill at sage/skills/{}/SKILL.md\n"


def skill(root: pathlib.Path, name: str, frontmatter: str, body: str = "") -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body or f'# {name}'}\n")


class ParseTest(unittest.TestCase):
    def test_folded_description(self):
        fm = sf.parse_frontmatter(
            "---\nname: m\ndescription: >\n  Captures context.\n  Use when the user\n"
            "  says remember.\nversion: \"1.2.0\"\n---\nbody\n")
        self.assertEqual(fm["description"], "Captures context. Use when the user says remember.")
        self.assertEqual(fm["version"], "1.2.0")

    def test_literal_description_keeps_lines(self):
        fm = sf.parse_frontmatter("---\ndescription: |\n  one\n  two\n---\n")
        self.assertEqual(fm["description"], "one\ntwo")

    def test_nested_block_scalar_stops_at_its_sibling(self):
        fm = sf.parse_frontmatter(
            "---\nmetadata:\n  note: >\n    folded\n    text\n  hermes:\n    tags: [a]\n---\n")
        self.assertEqual(fm["metadata"]["note"], "folded text")
        self.assertIn("hermes", fm["metadata"])

    def test_quoted_with_escapes_colons_and_comment(self):
        fm = sf.parse_frontmatter('---\ndescription: "a: b \\"c\\" — d"  # note\n---\n')
        self.assertEqual(fm["description"], 'a: b "c" — d')
        fm = sf.parse_frontmatter("---\ndescription: 'it''s'\n---\n")
        self.assertEqual(fm["description"], "it's")

    def test_yaml_only_escape_keeps_text(self):
        self.assertEqual(sf.parse_frontmatter('---\nd: "a\\_b"\n---\n')["d"], "a_b")

    def test_plain_scalar_drops_comment(self):
        self.assertEqual(sf.parse_frontmatter("---\nname: x  # c\n---\n")["name"], "x")

    def test_bom_and_crlf(self):
        fm = sf.parse_frontmatter("﻿---\r\nname: x\r\nmetadata:\r\n  hermes:\r\n"
                                  "    tags: [a]\r\n---\r\n")
        self.assertEqual(fm["name"], "x")
        self.assertEqual(sf.foreign_platform(fm), "hermes")

    def test_hermes_metadata_both_forms(self):
        block = sf.parse_frontmatter("---\nmetadata:\n  hermes:\n    tags: [a]\n---\n")
        flow = sf.parse_frontmatter("---\nmetadata: {hermes: {tags: [a]}}\n---\n")
        self.assertEqual(sf.foreign_platform(block), "hermes")
        self.assertEqual(sf.foreign_platform(flow), "hermes")
        self.assertIsNone(sf.foreign_platform(sf.parse_frontmatter("---\nname: x\n---\n")))

    def test_no_frontmatter(self):
        self.assertEqual(sf.parse_frontmatter("# just a doc\n"), {})

    def test_long_description_cut_at_word(self):
        d = sf.description_of({"description": "word " * 400})
        self.assertLessEqual(len(d), sf.MAX_DESCRIPTION)
        self.assertTrue(d.endswith("…"))


class LintTest(unittest.TestCase):
    def lint(self, fm):
        return sf.lint_frontmatter(f"---\n{fm}\n---\nbody\n")

    def test_clean(self):
        self.assertEqual(self.lint('name: a\ndescription: "x: y"\ntags: [a, "@b/c"]\n'
                                   'description2: >\n  @ fine inside a block\n'), [])

    def test_unterminated_quote_the_old_stub_shape(self):
        self.assertTrue(self.lint('description: "Corrects the 13 most common API design, an'))

    def test_reserved_first_character(self):
        self.assertTrue(self.lint("detected: [firebase, @firebase/app]"))   # the baas bug
        self.assertTrue(self.lint("x: `cmd`"))
        self.assertTrue(self.lint("list:\n  - @scope/pkg"))

    def test_unclosed_flow_and_bom(self):
        self.assertTrue(self.lint("tags: [a, b"))
        self.assertTrue(sf.lint_frontmatter("﻿---\nname: a\n---\n"))


class DeployTest(unittest.TestCase):
    """A project-shaped tree: sources under sage/skills/, stubs under .claude/skills/."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.src = self.root / "sage" / "skills"
        self.out = self.root / ".claude" / "skills"
        skill(self.src, "react", 'name: react\ndescription: "Use when: writing React — hooks, #state"')
        skill(self.src, "sage-memory", "name: sage-memory\ndescription: >\n  Use when the\n  user says remember.")
        skill(self.src, "sage-build", "name: sage-build\ndescription: \"Brief, Spec\"\n"
                                      "metadata:\n  hermes:\n    tags: [Sage]")
        skill(self.src, "sage", 'name: sage\ndescription: "Routes"')
        skill(self.src, "sage-gates", 'name: sage-gates\ndescription: "Use when blocked"')

    def tearDown(self):
        self.tmp.cleanup()

    def deploy(self, prefix=""):
        return sf.deploy_claude(self.src, self.out, prefix, ("sage-gates",))

    def test_selection(self):
        deployed, skipped = self.deploy()
        self.assertEqual(deployed, ["react", "sage-memory"])
        self.assertEqual(dict(skipped), {
            "sage": "would shadow the /sage command",
            "sage-build": "hermes port",
            "sage-gates": "delivered separately",
        })

    def test_stub_round_trips(self):
        self.deploy()
        fm = sf.parse_frontmatter((self.out / "sage-memory" / "SKILL.md").read_text())
        self.assertEqual(fm["description"], "Use when the user says remember.")
        fm = sf.parse_frontmatter((self.out / "react" / "SKILL.md").read_text())
        self.assertEqual(fm["description"], "Use when: writing React — hooks, #state")
        self.assertEqual(sf.check_claude(self.out), [])

    def test_prefix(self):
        self.deploy("sage:")
        self.assertTrue((self.out / "sage:react" / "SKILL.md").is_file())
        self.assertEqual(sf.check_claude(self.out), [])

    def test_stale_stubs_are_removed_and_the_users_own_kept(self):
        # What an older generator left: a Hermes-port stub, a `sage` stub, a
        # system-skill stub under the prefix, and an unprefixed stub after the
        # prefix was switched on.
        for name, rel in (("sage-build", "sage-build"), ("sage", "sage"),
                          ("sage:sage-gates", "sage-gates"), ("react", "react")):
            skill(self.out, name, f"name: {name}\ndescription: x", LOADER.format(rel))
        skill(self.out, "mine", "name: mine\ndescription: my own skill", "My instructions.")
        self.deploy("sage:")
        self.assertEqual(sorted(p.name for p in self.out.iterdir()),
                         ["mine", "sage:react", "sage:sage-memory"])
        self.assertEqual(sf.check_claude(self.out), [])

    def test_check_catches_what_the_old_generator_wrote(self):
        # Verbatim shapes from the pre-fix generator's output.
        skill(self.out, "api", 'name: api\ndescription: "Corrects the 13 most common API design '
                               'mistakes agents make — grounded in Geewax, Amundsen, Ousterhout, Kleppmann, an',
              LOADER.format("react"))
        skill(self.out, "sage-memory", "name: sage-memory\ndescription: >",
              LOADER.format("sage-memory"))
        skill(self.out, "sage-build", 'name: sage-build\ndescription: "Brief, Spec"',
              LOADER.format("sage-build"))
        skill(self.out, "sage", 'name: sage\ndescription: "Routes"', LOADER.format("sage"))
        skill(self.out, "gone", 'name: gone\ndescription: "x"', LOADER.format("gone"))
        problems = "\n".join(sf.check_claude(self.out))
        self.assertIn("api: line 3: description: unterminated double-quoted string", problems)
        self.assertIn("sage-memory: empty description", problems)
        self.assertIn("sage-build: is the hermes port", problems)
        self.assertIn("sage: shadows the /sage command", problems)
        self.assertIn("gone: loader points at missing sage/skills/gone/SKILL.md", problems)


class RealTreeTest(unittest.TestCase):
    def test_every_shipped_skill_deploys_cleanly(self):
        with tempfile.TemporaryDirectory() as t:
            root = pathlib.Path(t)
            (root / "sage").mkdir()
            (root / "sage" / "skills").symlink_to(REPO_ROOT / "skills")
            out = root / ".claude" / "skills"
            system = tuple(p.name for p in (REPO_ROOT / "core" / "system-skills").iterdir()
                           if p.is_dir())
            deployed, _ = sf.deploy_claude(REPO_ROOT / "skills", out, "", system)
            self.assertEqual(sf.check_claude(out), [])
            # The skills the old sed|cut loop dropped must now register.
            for name in ("sage-memory", "sage-self-learning", "sage-ontology",
                         "api", "web", "baas", "autoresearch"):
                self.assertIn(name, deployed)
            self.assertNotIn("sage", deployed)

    def test_every_shipped_frontmatter_is_strict_yaml(self):
        # Full skills are shipped as-is by the plugin and the system-skill copy:
        # Claude Code reads THEIR frontmatter, not a regenerated stub's.
        problems = []
        for base in ("skills", "core/system-skills", "packs"):
            for smd in sorted((REPO_ROOT / base).rglob("SKILL.md")):
                if "fixtures" in smd.parts:
                    continue
                for p in sf.lint_frontmatter(smd.read_text(encoding="utf-8")):
                    problems.append(f"{smd.relative_to(REPO_ROOT)}: {p}")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
