from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

import skill_manager
from sage_runtime.composition_contracts import CompositionError
from sage_runtime.metadata import extract_sage_metadata


def write_skill(path: Path, metadata: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
name: external-brainstorm
description: >-
  A scalar frontmatter description that remains compatible.
---

{metadata}

# External Brainstorm
""",
        encoding="utf-8",
    )
    return path


def valid_block() -> str:
    return """<!-- sage-metadata
composition:
  contract: composition/v1
  atomic: true
  provides:
    - capability: requirements.elicit
      role: owner
      combine: exclusive
      inputs: [request, codebase-context]
      outputs: [acceptance-criteria]
      terminal: design-approved
-->"""


def test_nested_sage_metadata_uses_real_yaml(tmp_path: Path) -> None:
    path = write_skill(tmp_path / "SKILL.md", valid_block())

    metadata = extract_sage_metadata(path)

    composition = metadata["composition"]
    assert composition["contract"] == "composition/v1"
    assert composition["atomic"] is True
    assert composition["provides"][0]["inputs"] == ["request", "codebase-context"]


def test_no_metadata_block_returns_empty_mapping(tmp_path: Path) -> None:
    path = write_skill(tmp_path / "SKILL.md")

    assert extract_sage_metadata(path) == {}


def test_multiple_metadata_blocks_are_rejected(tmp_path: Path) -> None:
    path = write_skill(tmp_path / "SKILL.md", f"{valid_block()}\n{valid_block()}")

    with pytest.raises(CompositionError, match="multiple"):
        extract_sage_metadata(path)


def test_malformed_yaml_reports_source_line(tmp_path: Path) -> None:
    path = write_skill(
        tmp_path / "SKILL.md",
        """<!-- sage-metadata
composition:
  provides: [unterminated
-->""",
    )

    with pytest.raises(CompositionError, match=r"SKILL\.md:\d+"):
        extract_sage_metadata(path)


def test_python_object_tags_are_rejected_by_safe_loader(tmp_path: Path) -> None:
    path = write_skill(
        tmp_path / "SKILL.md",
        """<!-- sage-metadata
composition: !!python/object/apply:os.system [echo unsafe]
-->""",
    )

    with pytest.raises(CompositionError, match="unsafe|tag|constructor"):
        extract_sage_metadata(path)


def test_metadata_root_must_be_a_mapping(tmp_path: Path) -> None:
    path = write_skill(tmp_path / "SKILL.md", "<!-- sage-metadata\n- item\n-->")

    with pytest.raises(CompositionError, match="mapping"):
        extract_sage_metadata(path)


def test_parser_rejects_files_over_the_bounded_size(tmp_path: Path) -> None:
    path = write_skill(tmp_path / "SKILL.md", valid_block() + ("\n" + "x" * 512))

    with pytest.raises(CompositionError, match="262"):
        extract_sage_metadata(path, max_bytes=262)


def test_skill_manager_exposes_only_the_composition_mapping(tmp_path: Path) -> None:
    path = write_skill(tmp_path / "SKILL.md", valid_block())

    composition = skill_manager.parse_composition_metadata(path)

    assert composition["contract"] == "composition/v1"
    assert composition["provides"][0]["terminal"] == "design-approved"


def test_existing_scalar_frontmatter_parser_remains_compatible() -> None:
    parsed = skill_manager.parse_frontmatter(
        """---
name: example
description: >-
  Existing scalar parsing still works.
internal: false
---
# Example
"""
    )

    assert parsed["name"] == "example"
    assert parsed["description"] == "Existing scalar parsing still works."
    assert parsed["internal"] == "false"
