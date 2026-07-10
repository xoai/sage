from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.backends.sage_memory import SageMemoryBackend
from sage_runtime.learning import (
    LearningConfigError,
    build_recall_query,
    recall_before_work,
    render_recall_context,
    resolve_learning_config,
)
from sage_runtime.learning_contracts import LearningContext, RecallRecord, RecallResult


def _context(**overrides: object) -> LearningContext:
    values: dict[str, object] = {
        "current_request": "Fix package installation in the Hermes adapter",
        "project_root": "/tmp/recall-project",
        "repo_name": "sage",
        "platform": "hermes",
        "active_capability": "change.implement",
        "selected_providers": ("sage:build", "external:brainstorm"),
        "touched_subsystem": "runtime/platforms/hermes",
        "touched_paths": ("runtime/platforms/hermes/setup/generate-hermes.sh",),
    }
    values.update(overrides)
    return LearningContext(**values)  # type: ignore[arg-type]


def _record(record_id: str, **overrides: object) -> RecallRecord:
    values: dict[str, object] = {
        "id": record_id,
        "title": f"Title that must not be injected {record_id}",
        "prevention": f"Prevention for {record_id}.",
        "rationale": f"Rationale for {record_id}.",
        "score": 0.9,
        "tags": ("self-learning", "correction"),
        "status": "active",
        "scope": "project",
        "project": "sage",
    }
    values.update(overrides)
    return RecallRecord(**values)  # type: ignore[arg-type]


class FakeBackend:
    def __init__(self, records: tuple[RecallRecord, ...]) -> None:
        self.records = records
        self.calls: list[tuple[str, LearningContext, int]] = []

    def search_learnings(self, query, context, limit=5):
        self.calls.append((query, context, limit))
        return RecallResult(query=query, records=self.records, backend="fake")

    def store_learning(self, record):
        raise AssertionError("recall observer must not store")

    def update_learning(self, record_id, record):
        raise AssertionError("recall observer must not update")

    def invalidate_learning(self, record_id, correction_id):
        raise AssertionError("recall observer must not invalidate")

    def link_learning(self, source_id, target_id, relation):
        raise AssertionError("recall observer must not link")

    def list_learnings(self, filters=None):
        raise AssertionError("recall observer must not list")


def test_query_contains_bounded_current_method_and_repo_context() -> None:
    query = build_recall_query(_context())

    assert "request=Fix package installation in the Hermes adapter" in query
    assert "capability=change.implement" in query
    assert "providers=sage:build,external:brainstorm" in query
    assert "repo=sage" in query
    assert "subsystem=runtime/platforms/hermes" in query
    assert len(query.encode("utf-8")) <= 4096


def test_recall_filters_selectors_supersession_and_duplicates_in_rank_order() -> None:
    duplicate_key = _record("duplicate-source").dedupe_key
    backend = FakeBackend(
        (
            _record(
                "project-match",
                platforms=("hermes",),
                capabilities=("change.implement",),
                providers=("external:brainstorm",),
                paths=("runtime/platforms/hermes",),
            ),
            _record("global-match", scope="global", project=None),
            _record(
                "superseded",
                status="superseded",
                superseded_by="replacement",
            ),
            _record("wrong-project", project="other"),
            _record("wrong-platform", platforms=("claude-code",)),
            _record("wrong-provider", providers=("other:method",)),
            _record("wrong-path", paths=("web/frontend",)),
            _record("duplicate-source"),
            _record("project-match"),
            _record("duplicate-key", dedupe_key=duplicate_key),
        )
    )

    result = recall_before_work(backend, _context(), limit=5)

    assert [item.id for item in result.records] == [
        "project-match",
        "global-match",
        "duplicate-source",
    ]
    assert len(backend.calls) == 1
    assert backend.calls[0][2] == 5


def test_capability_selector_mismatch_is_filtered() -> None:
    backend = FakeBackend(
        (
            _record("wrong", capabilities=("requirements.elicit",)),
            _record("right", capabilities=("change.implement",)),
        )
    )

    result = recall_before_work(backend, _context())
    assert [item.id for item in result.records] == ["right"]


def test_default_limit_is_five_and_zero_or_large_values_are_clamped() -> None:
    backend = FakeBackend(tuple(_record(f"lrn-{index}") for index in range(10)))

    default = recall_before_work(backend, _context())
    low = recall_before_work(backend, _context(), limit=0)
    high = recall_before_work(backend, _context(), limit=99)

    assert len(default.records) == 5
    assert len(low.records) == 1
    assert len(high.records) == 10
    assert [call[2] for call in backend.calls] == [5, 1, 10]


def test_render_injects_only_prevention_and_short_rationale() -> None:
    record = _record(
        "secret-id",
        title="SECRET TITLE",
        tags=("self-learning", "SECRET-TAG"),
        prevention="Check packageManager before installing dependencies.",
        rationale="The repository declares pnpm.",
    )
    rendered = render_recall_context(
        RecallResult(query="package manager", records=(record,), backend="fake")
    )

    assert "Prevention: Check packageManager" in rendered
    assert "Rationale: The repository declares pnpm." in rendered
    assert "SECRET TITLE" not in rendered
    assert "SECRET-TAG" not in rendered
    assert "secret-id" not in rendered
    assert "workflow" not in rendered.casefold()
    assert "gate" not in rendered.casefold()


def test_render_is_capped_by_utf8_bytes() -> None:
    records = tuple(
        _record(
            f"lrn-{index}",
            prevention="😀" * 500,
            rationale="because " + ("x" * 900),
        )
        for index in range(10)
    )
    rendered = render_recall_context(
        RecallResult(query="large", records=records), max_bytes=4096
    )

    assert len(rendered.encode("utf-8")) <= 4096
    assert rendered.endswith("[learning recall truncated]\n")


def test_backend_exception_is_one_bounded_fail_open_diagnostic() -> None:
    class BrokenBackend(FakeBackend):
        def search_learnings(self, query, context, limit=5):
            raise RuntimeError("😀" * 1000)

    result = recall_before_work(BrokenBackend(()), _context())

    assert result.ok is False
    assert result.records == ()
    assert len(result.diagnostics) == 1
    assert len(result.diagnostics[0].encode("utf-8")) <= 512


def test_recall_does_not_import_or_invoke_route_composition_or_gate(monkeypatch) -> None:
    import sage_runtime.gate as gate
    import sage_runtime.resolver as resolver
    import sage_runtime.router as router

    monkeypatch.setattr(gate, "evaluate", lambda *a, **k: pytest.fail("gate invoked"))
    monkeypatch.setattr(router, "route", lambda *a, **k: pytest.fail("router invoked"))
    monkeypatch.setattr(
        resolver, "resolve", lambda *a, **k: pytest.fail("composition invoked")
    )
    backend = FakeBackend((_record("safe"),))

    result = recall_before_work(backend, _context())
    assert [item.id for item in result.records] == ["safe"]


def _completed(stdout: str, returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["sage-memory"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_sage_memory_adapter_invokes_portable_cli_once(monkeypatch) -> None:
    calls = []
    payload = {
        "schema": "sage-memory-recall/v1",
        "ok": True,
        "project": "recall-project",
        "query": "package manager",
        "results": [
            {
                "id": "lrn-pnpm",
                "title": "Use package manager",
                "prevention": "Check packageManager first.",
                "rationale": "The repository declares pnpm.",
                "score": 0.92,
                "tags": ["self-learning", "correction"],
            }
        ],
        "diagnostics": [],
    }

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return _completed(json.dumps(payload))

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = SageMemoryBackend(timeout=1.5).search_learnings(
        "package manager", _context(), limit=5
    )

    assert calls[0][0] == [
        "sage-memory",
        "recall",
        "--query",
        "package manager",
        "--project",
        "/tmp/recall-project",
        "--format",
        "json",
        "--limit",
        "5",
    ]
    assert calls[0][1]["timeout"] == 1.5
    assert calls[0][1]["check"] is False
    assert [record.id for record in result.records] == ["lrn-pnpm"]
    assert result.ok is True


@pytest.mark.parametrize(
    "behavior",
    [
        "timeout",
        "missing",
        "malformed",
        "nonzero",
        "not-ok",
        "wrong-schema",
    ],
)
def test_sage_memory_adapter_failures_are_empty_and_bounded(
    monkeypatch, behavior: str
) -> None:
    def fake_run(command, **kwargs):
        if behavior == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if behavior == "missing":
            raise FileNotFoundError("sage-memory")
        if behavior == "malformed":
            return _completed("not-json")
        if behavior == "nonzero":
            return _completed("", returncode=9, stderr="failure " + ("x" * 1000))
        if behavior == "wrong-schema":
            return _completed(json.dumps({"schema": "other/v1", "ok": True}))
        return _completed(
            json.dumps(
                {
                    "schema": "sage-memory-recall/v1",
                    "ok": False,
                    "diagnostics": ["index unavailable"],
                }
            )
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = SageMemoryBackend().search_learnings(
        "package manager", _context(), limit=5
    )

    assert result.ok is False
    assert result.records == ()
    assert len(result.diagnostics) == 1
    assert len(result.diagnostics[0].encode("utf-8")) <= 512


def test_sage_memory_empty_result_is_success(monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _completed(
            json.dumps(
                {
                    "schema": "sage-memory-recall/v1",
                    "ok": True,
                    "project": "recall-project",
                    "query": "package manager",
                    "results": [],
                    "diagnostics": [],
                }
            )
        ),
    )

    result = SageMemoryBackend().search_learnings(
        "package manager", _context(), limit=5
    )
    assert result.ok is True
    assert result.records == ()
    assert result.diagnostics == ()


def test_learning_config_env_overrides_project_yaml(tmp_path, monkeypatch) -> None:
    config = tmp_path / ".sage" / "config.yaml"
    config.parent.mkdir()
    config.write_text(
        "learning:\n  backend: sage-memory\n  recall_owner: sage-learning\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SAGE_LEARNING_BACKEND", "openviking")

    resolved = resolve_learning_config(tmp_path)
    assert resolved.backend == "openviking"
    assert resolved.recall_owner == "sage-learning"


@pytest.mark.parametrize(
    "yaml_text",
    [
        "learning:\n  backends: [sage-memory, openviking]\n",
        "learning:\n  recall_owners: [sage-learning, hermes-native]\n",
    ],
)
def test_learning_config_rejects_multiple_backends_or_recall_owners(
    tmp_path, yaml_text: str
) -> None:
    config = tmp_path / ".sage" / "config.yaml"
    config.parent.mkdir()
    config.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(LearningConfigError, match="exactly one"):
        resolve_learning_config(tmp_path)
