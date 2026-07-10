from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, BrokenBarrierError

import pytest

from core.flag_parser.parser import parse as parse_canonical_flags

from sage_runtime import adapter
from sage_runtime import routing_lifecycle
from sage_runtime.routing_lifecycle import bind_route_decision
from sage_runtime.state import load_active_run, read_events


def _catalog(project: Path) -> None:
    runtime = project / ".sage" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "route-catalog.json").write_text(
        json.dumps(
            {
                "schema": "route-catalog/v1",
                "platform": "hermes",
                "hash": "catalog-hash",
                "routes": {
                    "build": {
                        "workflow": "build",
                        "target": "/build",
                        "source": "build.workflow.md",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (project / ".sage" / "composition.json").write_text(
        json.dumps(
            {
                "schema": "composition-catalog/v1",
                "providers": {
                    "implement": {
                        "id": "implement",
                        "atomic": False,
                        "provides": [
                            {
                                "capability": "change.implement",
                                "role": "owner",
                                "combine": "exclusive",
                            }
                        ],
                        "hash": "provider-hash",
                        "sources": [],
                    },
                    "quality-locked": {
                        "id": "quality-locked",
                        "atomic": True,
                        "provides": [
                            {
                                "capability": "quality.enforce",
                                "role": "owner",
                                "combine": "exclusive",
                                "terminal": "quality-loop-complete",
                            }
                        ],
                        "hash": "quality-hash",
                        "sources": [],
                    },
                    "autonomous": {
                        "id": "autonomous",
                        "atomic": False,
                        "provides": [
                            {
                                "capability": "execution.control",
                                "role": "owner",
                                "combine": "exclusive",
                            }
                        ],
                        "hash": "autonomous-hash",
                        "sources": [],
                    },
                },
                "policy": {"base": {}, "user": {}, "project": {}, "effective": {}},
                "workflow_defaults": {
                    "sage:build": {"change.implement": {"owner": "implement"}}
                },
                "sources": [],
                "generated_at": "2026-07-10T16:00:00Z",
                "hash": "composition-catalog-hash",
            }
        ),
        encoding="utf-8",
    )


def _decision(kind: str, *, target: str | None = None) -> dict[str, object]:
    return {
        "kind": kind,
        "target": target,
        "authoritative": kind in {"explicit", "switch", "cancel"},
        "arm_gate": False,
        "diagnostics": [],
    }


def test_explicit_route_binds_one_real_strict_run(monkeypatch, tmp_path: Path) -> None:
    _catalog(tmp_path)
    monkeypatch.setattr(
        adapter,
        "_run_cli",
        lambda *args, **kwargs: _decision("explicit", target="/build"),
    )

    first = adapter.route_context(
        "/build --strict add login",
        tmp_path,
        session_id="session-1",
        occurred_at="2026-07-10T17:00:00Z",
    )
    second = adapter.route_context(
        "/build --strict add login",
        tmp_path,
        session_id="session-1",
        occurred_at="2026-07-10T17:00:01Z",
    )

    state = load_active_run(tmp_path / ".sage" / "runtime")
    assert state is not None
    assert state.workflow_owner == "sage:build"
    assert state.explicit_intent is True
    assert state.strict is True
    assert state.composition_hash
    assert "Sage explicit route" in first
    assert "Sage explicit route" in second
    run_dirs = list((tmp_path / ".sage" / "runtime" / "runs").iterdir())
    assert len(run_dirs) == 1
    assert [event.type for event in read_events(run_dirs[0])] == [
        "run.started",
        "workflow.selected",
    ]
    started = read_events(run_dirs[0])[0]
    assert started.payload["resolved_composition"]["selected_workflow"] == "sage:build"
    assert started.payload["resolved_composition"]["bindings"][0]["provider_id"] == "implement"


def test_advisory_route_never_creates_run_state(monkeypatch, tmp_path: Path) -> None:
    _catalog(tmp_path)
    monkeypatch.setattr(
        adapter,
        "_run_cli",
        lambda *args, **kwargs: _decision("advisory", target="/build"),
    )
    adapter.route_context(
        "build a login page",
        tmp_path,
        session_id="session-1",
        occurred_at="2026-07-10T17:00:00Z",
    )
    assert load_active_run(tmp_path / ".sage" / "runtime") is None


def test_cancel_route_closes_the_bound_run(monkeypatch, tmp_path: Path) -> None:
    _catalog(tmp_path)
    decisions = iter(
        (_decision("explicit", target="/build"), _decision("cancel"))
    )
    monkeypatch.setattr(adapter, "_run_cli", lambda *args, **kwargs: next(decisions))
    adapter.route_context(
        "/build task",
        tmp_path,
        session_id="session-1",
        occurred_at="2026-07-10T17:00:00Z",
    )
    adapter.route_context(
        "/cancel",
        tmp_path,
        session_id="session-1",
        occurred_at="2026-07-10T17:01:00Z",
    )
    assert load_active_run(tmp_path / ".sage" / "runtime") is None
    run_dir = next((tmp_path / ".sage" / "runtime" / "runs").iterdir())
    assert read_events(run_dir)[-1].type == "run.cancelled"


def test_route_without_composition_clears_stale_choice(tmp_path: Path) -> None:
    _catalog(tmp_path)
    runtime = tmp_path / ".sage" / "runtime"
    choice = runtime / "choice-required.json"
    choice.write_text(
        json.dumps(
            {
                "schema": "choice-required/v1",
                "capability": "change.implement",
                "candidates": [{"provider_id": "old-owner"}],
            }
        ),
        encoding="utf-8",
    )

    run_dir = bind_route_decision(
        tmp_path,
        "/fix a defect",
        _decision("explicit", target="/fix"),
        session_id="session-1",
        occurred_at="2026-07-10T17:00:00Z",
    )

    assert run_dir is not None
    assert not choice.exists()


def test_exact_modes_join_composition_and_negative_flag_overrides_config(
    tmp_path: Path,
) -> None:
    _catalog(tmp_path)
    config = tmp_path / ".sage" / "config.yaml"
    config.write_text("quality_locked: true\nautonomous: false\n", encoding="utf-8")

    run_dir = bind_route_decision(
        tmp_path,
        "/build --no-quality-locked --autonomous ship it",
        _decision("explicit", target="/build"),
        session_id="session-modes",
        occurred_at="2026-07-10T17:00:00Z",
    )

    assert run_dir is not None
    started = read_events(run_dir)[0]
    assert started.payload["strict"] is False
    assert started.payload["modes"]["quality_locked"] is False
    assert started.payload["modes"]["autonomous"] is True
    assert started.payload["modes"]["sources"] == {
        "quality_locked": "flag",
        "autonomous": "flag",
    }
    assert {
        item["provider_id"]
        for item in started.payload["resolved_composition"]["bindings"]
    } == {"implement", "autonomous"}


def test_strict_word_in_goal_does_not_enable_strict_mode(tmp_path: Path) -> None:
    _catalog(tmp_path)

    run_dir = bind_route_decision(
        tmp_path,
        "/build implement a --strict command option",
        _decision("explicit", target="/build"),
        session_id="session-strict-prose",
        occurred_at="2026-07-10T17:00:00Z",
    )

    assert run_dir is not None
    assert read_events(run_dir)[0].payload["strict"] is False


@pytest.mark.parametrize(
    ("arguments", "defaults"),
    [
        ("", {}),
        ("--strict --quality-locked ship it", {}),
        ("--autonomous --no-quality-locked ship", {"quality_locked": True}),
        ("ship a --strict option", {}),
        ("--quality-locked --no-quality-locked ship", {}),
        ("--unknown ship", {}),
    ],
)
def test_runtime_mode_parser_matches_canonical_flag_values(
    tmp_path: Path, arguments: str, defaults: dict[str, bool]
) -> None:
    config = tmp_path / ".sage" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "".join(f"{key}: {'true' if value else 'false'}\n" for key, value in defaults.items()),
        encoding="utf-8",
    )
    expected = parse_canonical_flags(arguments, defaults=defaults)

    actual = routing_lifecycle._workflow_modes(tmp_path, f"/build {arguments}")

    assert actual["strict"] is expected.strict
    assert actual["quality_locked"] is expected.quality_locked
    assert actual["autonomous"] is expected.autonomous
    assert (actual["error"] is not None) is (expected.error is not None)


def test_concurrent_distinct_routes_allocate_distinct_runs(
    monkeypatch, tmp_path: Path
) -> None:
    _catalog(tmp_path)
    original = routing_lifecycle._next_run_id
    rendezvous = Barrier(2)

    def delayed(runtime: Path, session_id: str) -> str:
        value = original(runtime, session_id)
        try:
            rendezvous.wait(timeout=0.25)
        except BrokenBarrierError:
            pass
        return value

    monkeypatch.setattr(routing_lifecycle, "_next_run_id", delayed)
    requests = (
        ("/build concurrent task", _decision("explicit", target="/build")),
        ("/fix concurrent task", _decision("explicit", target="/fix")),
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                bind_route_decision,
                tmp_path,
                prompt,
                decision,
                session_id="session-race",
                occurred_at="2026-07-10T17:00:00Z",
            )
            for prompt, decision in requests
        ]
        results = [future.result() for future in futures]

    assert results[0] != results[1]
    run_dirs = list((tmp_path / ".sage" / "runtime" / "runs").iterdir())
    assert len(run_dirs) == 2
    assert {read_events(path)[0].payload["workflow_owner"] for path in run_dirs} == {
        "sage:build",
        "sage:fix",
    }
