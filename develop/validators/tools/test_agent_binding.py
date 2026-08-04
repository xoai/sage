"""agent_binding.py — the per-role designation reader, pinned. (A6)

The rule under test is T4-rev2 extended per-role: a role is bound ONLY when
the user's opencode config defines the agent WITH a model. Modelless =
unbound — [V-E] proved live that a modelless config agent dispatches fine
and silently inherits the primary, which is exactly the spend trap the
resolver exists to prevent.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runtime" / "tools"))

import agent_binding as AB  # noqa: E402
import scope_judge as SJ    # noqa: E402

TOOL = REPO / "runtime" / "tools" / "agent_binding.py"

ROLES = ("sage-implementer", "sage-task-reviewer", "sage-branch-reviewer")


def cfg(agents):
    return json.dumps({"$schema": "x", "agent": agents}, indent=2)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="agent-binding-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.xdg = self.root / "xdg"
        (self.xdg / "opencode").mkdir(parents=True)
        self.env = {"XDG_CONFIG_HOME": str(self.xdg)}

    def resolve(self, name):
        return AB.agent_model(name, self.root, self.env)


class ResolverTest(Fixture):
    def test_bound_role_resolves_per_role(self):
        (self.root / "opencode.json").write_text(cfg({
            r: {"mode": "subagent", "model": "deepseek/deepseek-v4-flash",
                "permission": {"edit": "deny"}}
            for r in ROLES}))
        for r in ROLES:
            self.assertEqual(self.resolve(r), "deepseek/deepseek-v4-flash", r)

    def test_unbound_role_resolves_to_nothing(self):
        (self.root / "opencode.json").write_text(cfg(
            {"sage-implementer": {"model": "p/m"}}))
        self.assertEqual(self.resolve("sage-task-reviewer"), "")
        self.assertEqual(self.resolve("sage-branch-reviewer"), "")

    def test_bound_without_model_is_unbound(self):
        """[V-E]: the modelless entry dispatches fine and inherits the
        primary — looks routed, spends on the expensive model. Unbound."""
        (self.root / "opencode.json").write_text(cfg({
            "sage-implementer": {"mode": "subagent",
                                 "permission": {"edit": "deny"}}}))
        self.assertEqual(self.resolve("sage-implementer"), "")

    def test_project_wins_over_global(self):
        (self.xdg / "opencode" / "opencode.jsonc").write_text(cfg(
            {"sage-implementer": {"model": "global/model"}}))
        (self.root / "opencode.json").write_text(cfg(
            {"sage-implementer": {"model": "project/model"}}))
        self.assertEqual(self.resolve("sage-implementer"), "project/model")

    def test_global_covers_a_project_without_config(self):
        (self.xdg / "opencode" / "opencode.jsonc").write_text(cfg(
            {"sage-task-reviewer": {"model": "global/cheap"}}))
        self.assertEqual(self.resolve("sage-task-reviewer"), "global/cheap")

    def test_shell_metacharacters_are_not_a_model(self):
        (self.root / "opencode.json").write_text(cfg(
            {"sage-implementer": {"model": "p/m; rm -rf ."}}))
        self.assertEqual(self.resolve("sage-implementer"), "")


class CliTest(Fixture):
    def run_tool(self, *names):
        return subprocess.run(
            [sys.executable, str(TOOL), *names, "--root", str(self.root)],
            capture_output=True, text=True, env={**self.env, "PATH": "/usr/bin:/bin"})

    def test_multi_name_output_bound_lines_only(self):
        (self.root / "opencode.json").write_text(cfg({
            "sage-implementer": {"model": "a/big"},
            "sage-branch-reviewer": {"mode": "subagent"}}))
        r = self.run_tool(*ROLES)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "sage-implementer\ta/big\n",
                         "one line per BOUND role, unbound roles omitted")

    def test_no_config_anywhere_prints_nothing_exit_zero(self):
        r = self.run_tool(*ROLES)
        self.assertEqual((r.returncode, r.stdout), (0, ""),
                         "informational tool: silence, never a block")


class JudgeParityTest(Fixture):
    """The twin readers must never drift: scope_judge.py's T4-rev2 resolver
    and this generalized one, same fixtures, same answers."""

    CASES = (
        cfg({"sage-scope-judge": {"model": "deepseek/deepseek-v4-flash",
                                  "permission": {"edit": "deny",
                                                 "bash": "deny"}}}),
        cfg({"sage-scope-judge": {"permission": {"edit": "deny"}}}),
        cfg({"sage-reviewer": {"model": "p/other"}}),
        cfg({"sage-scope-judge": {"model": "p/m; rm -rf ."}}),
        '{\n  // comment\n  "agent": {\n    "sage-scope-judge": '
        '{ "model": "p/m-mini" }\n  }\n}',
    )

    def test_readers_agree_on_every_fixture(self):
        for i, text in enumerate(self.CASES):
            (self.root / "opencode.json").write_text(text)
            self.assertEqual(
                AB.agent_model("sage-scope-judge", self.root, self.env),
                SJ._opencode_designated_model(self.root, self.env),
                "fixture %d: the twin readers diverged — change both or "
                "neither" % i)


if __name__ == "__main__":
    unittest.main(verbosity=2)
