"""Protocol implemented by learning storage and recall providers."""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from ..learning_contracts import LearningContext, RecallRecord, RecallResult


@runtime_checkable
class LearningBackend(Protocol):
    """Backend operations used by recall hooks and canonical learning skills.

    Lifecycle observers call only ``search_learnings``.  The mutation methods
    exist for adapters used by the canonical self-learning skill, keeping
    detection separate from semantic authoring and storage.
    """

    def search_learnings(
        self, query: str, context: LearningContext, limit: int = 5
    ) -> RecallResult: ...

    def store_learning(self, record: RecallRecord) -> RecallRecord: ...

    def update_learning(
        self, record_id: str, record: RecallRecord
    ) -> RecallRecord: ...

    def invalidate_learning(self, record_id: str, correction_id: str) -> bool: ...

    def link_learning(
        self, source_id: str, target_id: str, relation: str
    ) -> bool: ...

    def list_learnings(
        self, filters: Mapping[str, object] | None = None
    ) -> tuple[RecallRecord, ...]: ...
