from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.backends.openviking import (
    OpenVikingBackend,
    TransportResponse,
)
from sage_runtime.learning import create_learning_backend, resolve_learning_config
from sage_runtime.learning_contracts import LearningContext, LearningContractError


RESOURCE = "viking://resources/example/learnings"


def _context(**overrides: object) -> LearningContext:
    values: dict[str, object] = {
        "current_request": "Fix package installation",
        "project_root": "/tmp/sage",
        "repo_name": "sage",
        "platform": "hermes",
        "active_capability": "change.implement",
        "selected_providers": ("sage:build",),
        "touched_subsystem": "runtime/platforms/hermes",
    }
    values.update(overrides)
    return LearningContext(**values)  # type: ignore[arg-type]


class FakeTransport:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def request(self, method, url, *, headers, json_body, timeout):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json_body": json_body,
                "timeout": timeout,
            }
        )
        if self.error:
            raise self.error
        if isinstance(self.response, list):
            return self.response.pop(0)
        return self.response


def _response(items: list[dict], *, status_code: int = 200) -> TransportResponse:
    return TransportResponse(
        status_code=status_code,
        payload={
            "status": "ok" if status_code < 400 else "error",
            "result": {"resources": items, "total": len(items)},
        },
        text="server response",
    )


def test_search_is_exactly_scoped_and_identity_is_constructor_supplied(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENVIKING_USER", "must-not-leak")
    monkeypatch.setenv("OPENVIKING_AGENT_ID", "must-not-leak")
    transport = FakeTransport(
        _response(
            [
                {
                    "uri": f"{RESOURCE}/lrn-pnpm.md",
                    "title": "Use the repository package manager",
                    "content": (
                        "Why: The repository declares pnpm.\n"
                        "Prevention: Check packageManager before installing dependencies."
                    ),
                    "score": 0.92,
                    "status": "active",
                    "tags": ["self-learning", "correction"],
                    "metadata": {
                        "scope": "project",
                        "project": "sage",
                        "platforms": ["hermes"],
                        "paths": ["runtime/platforms/hermes"],
                    },
                }
            ]
        )
    )
    backend = OpenVikingBackend(
        base_url="https://memory.example.test",
        resource_uri=RESOURCE,
        user="configured-user",
        agent_id="configured-agent",
        timeout=1.25,
        transport=transport,
    )

    result = backend.search_learnings("package manager", _context(), limit=5)

    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://memory.example.test/api/v1/search/find"
    assert call["json_body"] == {
        "query": "package manager",
        "target_uri": RESOURCE,
        "context_type": "resource",
        "limit": 5,
    }
    assert call["headers"] == {
        "Content-Type": "application/json",
        "X-OpenViking-User": "configured-user",
        "X-OpenViking-Actor-Peer": "configured-agent",
    }
    assert call["timeout"] == 1.25
    assert result.ok is True
    assert len(result.records) == 1
    record = result.records[0]
    assert record.id == f"{RESOURCE}/lrn-pnpm.md"
    assert record.title == "Use the repository package manager"
    assert record.prevention == (
        "Check packageManager before installing dependencies."
    )
    assert record.rationale == "The repository declares pnpm."
    assert record.status == "active"
    assert record.score == 0.92
    assert record.project == "sage"
    assert record.platforms == ("hermes",)


def test_records_outside_prefix_and_native_prefetch_ids_are_removed() -> None:
    already_seen = f"{RESOURCE}/seen.md"
    transport = FakeTransport(
        _response(
            [
                {
                    "uri": "viking://resources/other/leak.md",
                    "content": "Prevention: Never inject this.",
                    "score": 1.0,
                },
                {
                    "uri": already_seen,
                    "content": "Prevention: Already injected natively.",
                    "score": 0.9,
                },
                {
                    "uri": f"{RESOURCE}/.overview.md",
                    "content": "Prevention: Never inject generated summaries.",
                    "score": 0.85,
                },
                {
                    "uri": f"{RESOURCE}/fresh.md",
                    "content": "Prevention: Inject this once.",
                    "score": 0.8,
                },
                {
                    "uri": f"{RESOURCE}/fresh.md",
                    "content": "Prevention: Duplicate result.",
                    "score": 0.7,
                },
            ]
        )
    )
    backend = OpenVikingBackend(
        base_url="http://ov.test",
        resource_uri=RESOURCE,
        user="user",
        agent_id="agent",
        transport=transport,
    )

    result = backend.search_learnings(
        "query",
        _context(seen_record_ids=(already_seen,)),
        limit=10,
    )

    assert [record.id for record in result.records] == [f"{RESOURCE}/fresh.md"]


def test_search_hit_without_content_reads_scoped_full_record() -> None:
    uri = f"{RESOURCE}/full-record.md"
    transport = FakeTransport(
        [
            _response([{"uri": uri, "abstract": "Package correction", "score": 0.8}]),
            TransportResponse(
                200,
                {
                    "status": "ok",
                    "result": (
                        "Why: The project declares pnpm.\n"
                        "Prevention: Inspect packageManager before installing."
                    ),
                },
                "",
            ),
        ]
    )
    backend = OpenVikingBackend(
        base_url="http://ov.test",
        resource_uri=RESOURCE,
        user="user",
        agent_id="agent",
        transport=transport,
    )

    result = backend.search_learnings("query", _context(), limit=5)

    assert len(transport.calls) == 2
    assert transport.calls[1]["method"] == "GET"
    assert transport.calls[1]["url"].startswith(
        "http://ov.test/api/v1/content/read?uri="
    )
    assert result.records[0].prevention == (
        "Inspect packageManager before installing."
    )
    assert result.records[0].rationale == "The project declares pnpm."


def test_status_and_correction_links_are_normalized_from_metadata() -> None:
    transport = FakeTransport(
        _response(
            [
                {
                    "uri": f"{RESOURCE}/old.md",
                    "abstract": "Old package rule.",
                    "status": "superseded",
                    "metadata": {
                        "superseded_by": f"{RESOURCE}/new.md",
                        "tags": ["self-learning", "correction"],
                    },
                },
                {
                    "uri": f"{RESOURCE}/new.md",
                    "prevention": "Read packageManager first.",
                    "rationale": "The old npm-only rule was wrong.",
                    "metadata": {"corrects": f"{RESOURCE}/old.md"},
                },
            ]
        )
    )
    backend = OpenVikingBackend(
        base_url="http://ov.test",
        resource_uri=RESOURCE,
        user="user",
        agent_id="agent",
        transport=transport,
    )

    result = backend.search_learnings("query", _context(), limit=5)

    old, new = result.records
    assert old.status == "superseded"
    assert old.superseded_by == f"{RESOURCE}/new.md"
    assert new.status == "active"
    assert new.corrects == f"{RESOURCE}/old.md"


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (None, TimeoutError("slow")),
        (_response([], status_code=401), None),
        (_response([], status_code=500), None),
        (TransportResponse(200, {"status": "ok", "result": []}, "bad"), None),
    ],
)
def test_timeout_auth_server_and_shape_errors_fail_open(response, error) -> None:
    backend = OpenVikingBackend(
        base_url="http://ov.test",
        resource_uri=RESOURCE,
        user="user",
        agent_id="agent",
        transport=FakeTransport(response, error),
    )

    result = backend.search_learnings("query", _context(), limit=5)

    assert result.ok is False
    assert result.records == ()
    assert len(result.diagnostics) == 1
    assert len(result.diagnostics[0].encode("utf-8")) <= 512


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("base_url", ""),
        ("resource_uri", ""),
        ("resource_uri", "viking://user/private"),
        ("user", ""),
        ("agent_id", ""),
    ],
)
def test_constructor_has_no_personal_or_implicit_identity_defaults(
    field: str, value: str
) -> None:
    kwargs = {
        "base_url": "http://ov.test",
        "resource_uri": RESOURCE,
        "user": "user",
        "agent_id": "agent",
        "transport": FakeTransport(_response([])),
    }
    kwargs[field] = value
    with pytest.raises((LearningContractError, ValueError)):
        OpenVikingBackend(**kwargs)


def test_factory_resolves_only_named_environment_values(tmp_path, monkeypatch) -> None:
    config = tmp_path / ".sage" / "config.yaml"
    config.parent.mkdir()
    config.write_text(
        """learning:
  backend: openviking
  recall_owner: sage-lifecycle
  openviking:
    base_url_env: TEST_OV_URL
    resource_uri_env: TEST_OV_RESOURCE
    user_env: TEST_OV_USER
    agent_id_env: TEST_OV_AGENT
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_OV_URL", "http://ov.test")
    monkeypatch.setenv("TEST_OV_RESOURCE", RESOURCE)
    monkeypatch.setenv("TEST_OV_USER", "configured-user")
    monkeypatch.setenv("TEST_OV_AGENT", "configured-agent")

    resolved = resolve_learning_config(tmp_path)
    backend = create_learning_backend(
        resolved.backend,
        config=resolved,
        transport=FakeTransport(_response([])),
    )

    assert isinstance(backend, OpenVikingBackend)
    assert backend.base_url == "http://ov.test"
    assert backend.resource_uri == RESOURCE
    assert backend.user == "configured-user"
    assert backend.agent_id == "configured-agent"
