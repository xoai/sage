"""Recall adapter for the portable ``sage-memory recall`` command."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Mapping

from ..learning_contracts import (
    MAX_DIAGNOSTIC_BYTES,
    LearningContext,
    LearningContractError,
    RecallRecord,
    RecallResult,
)


def _bounded(value: object, max_bytes: int = MAX_DIAGNOSTIC_BYTES) -> str:
    text = " ".join(str(value or "").split())
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()


@dataclass(frozen=True)
class SageMemoryBackend:
    executable: str = "sage-memory"
    timeout: float = 2.0

    def _failure(self, query: str, diagnostic: object) -> RecallResult:
        return RecallResult(
            query=query,
            backend="sage-memory",
            diagnostics=(_bounded(diagnostic),),
            ok=False,
        )

    def search_learnings(
        self, query: str, context: LearningContext, limit: int = 5
    ) -> RecallResult:
        bounded_limit = min(10, max(1, int(limit)))
        command = [
            self.executable,
            "recall",
            "--query",
            query,
            "--project",
            context.project_root,
            "--format",
            "json",
            "--limit",
            str(bounded_limit),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._failure(query, "sage-memory recall timed out")
        except FileNotFoundError:
            return self._failure(query, "sage-memory executable was not found")
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return self._failure(query, f"sage-memory recall failed: {exc}")
        if completed.returncode != 0:
            detail = completed.stderr or f"exit code {completed.returncode}"
            return self._failure(query, f"sage-memory recall failed: {detail}")
        if len(completed.stdout.encode("utf-8")) > 1024 * 1024:
            return self._failure(query, "sage-memory recall output exceeded 1 MiB")
        try:
            payload = json.loads(completed.stdout)
        except (json.JSONDecodeError, UnicodeError) as exc:
            return self._failure(query, f"sage-memory recall returned invalid JSON: {exc}")
        if not isinstance(payload, Mapping):
            return self._failure(query, "sage-memory recall returned a non-object payload")
        if payload.get("schema") != "sage-memory-recall/v1":
            return self._failure(query, "sage-memory recall returned an unsupported schema")
        if payload.get("ok") is not True:
            diagnostics = payload.get("diagnostics", [])
            detail = (
                diagnostics[0]
                if isinstance(diagnostics, list) and diagnostics
                else "sage-memory recall reported unavailable"
            )
            return self._failure(query, detail)
        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            return self._failure(query, "sage-memory recall results must be a list")

        records: list[RecallRecord] = []
        try:
            for item in raw_results[:bounded_limit]:
                if not isinstance(item, Mapping):
                    raise LearningContractError("recall result must be a mapping")
                records.append(
                    RecallRecord(
                        id=item.get("id"),  # type: ignore[arg-type]
                        title=item.get("title"),  # type: ignore[arg-type]
                        prevention=item.get("prevention", ""),  # type: ignore[arg-type]
                        rationale=item.get("rationale", ""),  # type: ignore[arg-type]
                        score=item.get("score", 0.0),  # type: ignore[arg-type]
                        tags=item.get("tags", ("self-learning",)),  # type: ignore[arg-type]
                        status="active",
                        scope="project",
                        project=context.repo_name,
                    )
                )
        except LearningContractError as exc:
            return self._failure(query, f"invalid sage-memory recall record: {exc}")
        return RecallResult(
            query=query,
            records=tuple(records),
            backend="sage-memory",
        )

    def store_learning(self, record: RecallRecord) -> RecallRecord:
        raise NotImplementedError("hook recall adapter does not author learnings")

    def update_learning(self, record_id: str, record: RecallRecord) -> RecallRecord:
        raise NotImplementedError("hook recall adapter does not author learnings")

    def invalidate_learning(self, record_id: str, correction_id: str) -> bool:
        raise NotImplementedError("hook recall adapter does not author learnings")

    def link_learning(self, source_id: str, target_id: str, relation: str) -> bool:
        raise NotImplementedError("hook recall adapter does not author learnings")

    def list_learnings(
        self, filters: Mapping[str, object] | None = None
    ) -> tuple[RecallRecord, ...]:
        raise NotImplementedError("hook recall adapter does not browse learnings")
