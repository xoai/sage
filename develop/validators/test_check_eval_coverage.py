from __future__ import annotations

import importlib.util
import pathlib


VALIDATOR = pathlib.Path(__file__).with_name("check-eval-coverage.py")
SPEC = importlib.util.spec_from_file_location("check_eval_coverage", VALIDATOR)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_discover_emits_registry_paths_with_forward_slashes(tmp_path: pathlib.Path) -> None:
    workflow = tmp_path / "core" / "workflows" / "sample.workflow.md"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("# sample\n", encoding="utf-8")
    setattr(MODULE, "EAGER_BODY", tmp_path / "missing-instructions-body.sh")

    discovered = MODULE.discover(tmp_path)

    assert "core/workflows/sample.workflow.md" in discovered
    assert all("\\" not in key for key in discovered)
