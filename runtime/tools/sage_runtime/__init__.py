"""Shared deterministic runtime primitives for Sage platform adapters."""

from .contracts import ContractError, NormalizedEvent, RunState
from .composition_contracts import (
    CapabilityBinding,
    CompositionError,
    CompositionPolicy,
    Provider,
    ResolvedBinding,
    ResolvedComposition,
)
from .io import atomic_write_json

__all__ = [
    "ContractError",
    "CapabilityBinding",
    "CompositionError",
    "CompositionPolicy",
    "NormalizedEvent",
    "Provider",
    "ResolvedBinding",
    "ResolvedComposition",
    "RunState",
    "atomic_write_json",
]
