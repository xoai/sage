from __future__ import annotations

from pathlib import Path

from sage_platforms import detect_hermes
from sage_runtime.catalog import compile_route_catalog, discover_workflows
from sage_runtime.composition import compile_composition


ROOT = Path(__file__).resolve().parents[2]
INSTRUCTIONS = ROOT / "runtime/platforms/_shared/instructions-body.sh"
SCREENSHOT = ROOT / "runtime/tools/sage-screenshot.sh"
SESSION_INIT = ROOT / "runtime/platforms/hermes/hooks/sage-session-init.sh"
HERMES_GENERATOR = ROOT / "runtime/platforms/hermes/setup/generate-hermes.sh"
CONSTITUTION = ROOT / "core/constitution/sage-process.constitution.md"
CORE_NAVIGATOR = ROOT / "core/capabilities/orchestration/sage-navigator/SKILL.md"
PLUGIN_NAVIGATOR = ROOT / "tools/sage-claude-plugin/skills/sage-navigator/SKILL.md"
SELF_LEARNING = ROOT / "skills/sage-self-learning/SKILL.md"
PLUGIN_SELF_LEARNING = ROOT / "tools/sage-claude-plugin/skills/sage-self-learning/SKILL.md"
PLUGIN_REFLECT = ROOT / "tools/sage-claude-plugin/skills/reflect/SKILL.md"


def _generated_body() -> str:
    source = INSTRUCTIONS.read_text(encoding="utf-8")
    start = source.index("cat <<'INSTRUCTIONS_EOF'")
    body = source.index("\n", start) + 1
    end = source.index("\nINSTRUCTIONS_EOF", body)
    return source[body:end]


def test_generated_instructions_are_advisory_and_composable() -> None:
    text = _generated_body()

    assert "Plain task prose never starts" in text
    assert "may combine Sage with any compatible skill" in text
    assert "active strict run" in text
    assert "configured recall owner" in text
    assert "search before store" in text

    assert "Keyword routing (check FIRST, deterministic)" not in text
    assert "Every substantial response starts with \"Sage →\"" not in text
    assert "enforced for both slash commands and free input" not in text
    assert "sage_memory_store" not in text


def test_review_regressions_are_encoded_in_platform_scripts() -> None:
    screenshot = SCREENSHOT.read_text(encoding="utf-8")
    session = SESSION_INIT.read_text(encoding="utf-8")
    generator = HERMES_GENERATOR.read_text(encoding="utf-8")

    assert "NODE_PATH_DELIMITER" in screenshot
    assert "require('path').delimiter" in screenshot
    assert "printf '%s' \"$ACTIVE_WORK\"" in session
    assert "HERMES_SESSION_ID" in session
    assert "owner=$SESSION_OWNER" in session
    assert "</INSTRUCTIONS>" not in generator
    assert "legacy_end" in generator
    assert "command -v python3" not in generator


def test_legacy_hermes_project_is_detected_without_local_home(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "<!-- BEGIN SAGE HERMES GENERATED -->\n",
        encoding="utf-8",
    )

    assert detect_hermes(tmp_path) is True


def test_canonical_policy_sources_do_not_restore_legacy_routing() -> None:
    for path in (CONSTITUTION, CORE_NAVIGATOR, PLUGIN_NAVIGATOR):
        text = path.read_text(encoding="utf-8")
        assert "explicit" in text.casefold()
        assert "composition" in text.casefold()
        assert "Keyword Matching (deterministic" not in text
        assert "Route Every Request" not in text
        assert "sage_memory_store" not in text


def test_self_learning_is_backend_neutral_and_paired_with_reflection() -> None:
    canonical = SELF_LEARNING.read_text(encoding="utf-8")
    bundled = PLUGIN_SELF_LEARNING.read_text(encoding="utf-8")
    reflect = PLUGIN_REFLECT.read_text(encoding="utf-8")

    assert canonical == bundled
    assert "OpenViking" in canonical
    assert "Exactly one configured backend" in canonical
    assert canonical.index("Search before store") < canonical.index("Persist")
    assert "raw memory call" in " ".join(canonical.split())
    assert "paired with `reflect`" in " ".join(canonical.split())
    assert "Activate alongside the sage-memory skill" not in canonical

    assert "sage_memory_store" not in reflect
    assert "reflection complete" in reflect
    assert "reflection skip" in reflect
    assert "evidence" in reflect.casefold()


def test_every_canonical_workflow_and_skill_has_a_deterministic_surface() -> None:
    capabilities = ROOT / "core" / "capabilities"
    skills = ROOT / "skills"
    workflows = ROOT / "core" / "workflows"
    method_ids = {path.parent.name for path in capabilities.rglob("SKILL.md")}
    skill_ids = {path.parent.name for path in skills.glob("*/SKILL.md")}
    workflow_ids = set(discover_workflows(workflows))
    installed = method_ids | skill_ids | workflow_ids

    composition = compile_composition(
        [capabilities, skills],
        None,
        None,
        installed,
        base_overlay=ROOT / "core" / "composition" / "defaults.yaml",
    )
    providers = set(composition["providers"])
    direct = set(composition["direct_skills"])

    assert method_ids <= providers
    assert skill_ids <= providers | direct
    assert providers.isdisjoint(direct)
    assert set(composition["workflow_defaults"]) == {
        f"sage:{name}" for name in workflow_ids
    }

    routes = compile_route_catalog(
        workflows,
        "hermes",
        {name: f"/{name}" for name in workflow_ids},
    )
    assert set(routes["routes"]) == workflow_ids
