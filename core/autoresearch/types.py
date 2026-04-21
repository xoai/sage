"""Core types for autoresearch runtime."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


class Direction(enum.Enum):
    LOWER = "lower"
    HIGHER = "higher"


class Termination(enum.Enum):
    TARGET = "target"
    ITERATIONS = "iterations"
    INTERRUPT = "interrupt"


class Status(enum.Enum):
    KEEP = "keep"
    DISCARD = "discard"
    CRASH = "crash"
    BASELINE = "baseline"


class Phase(enum.Enum):
    REVIEW = "review"
    IDEATE = "ideate"
    MODIFY = "modify"
    COMMIT = "commit"
    VERIFY = "verify"
    DECIDE = "decide"
    LOG = "log"
    REPEAT = "repeat"


@dataclass
class MetricConfig:
    name: str
    direction: Direction
    target: Optional[float] = None


@dataclass
class ScopeConfig:
    writable: list[str] = field(default_factory=list)
    frozen: list[str] = field(default_factory=list)


@dataclass
class BudgetConfig:
    per_run_seconds: int = 120
    max_iterations: Optional[int] = None
    termination: Termination = Termination.INTERRUPT


@dataclass
class BriefConfig:
    goal: str
    metric: MetricConfig
    verify: str
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    slug: str = ""
    keep_on_tie: bool = False

    @property
    def branch_name(self) -> str:
        return f"autoresearch/{self.slug}" if self.slug else "autoresearch/session"


@dataclass
class Iteration:
    iteration: int
    timestamp: str
    commit: str
    parent: str
    description: str
    metrics: dict[str, float]
    duration_s: float
    peak_memory_mb: Optional[float] = None
    status: Status = Status.BASELINE
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "timestamp": self.timestamp,
            "commit": self.commit,
            "parent": self.parent,
            "description": self.description,
            "metrics": self.metrics,
            "duration_s": round(self.duration_s, 1),
            "peak_memory_mb": self.peak_memory_mb,
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass
class PhaseState:
    """Persisted after each phase for crash recovery."""
    iteration: int
    phase: Phase
    brief_path: str
    work_dir: str
    branch: str
    pre_iteration_sha: str = ""
    last_commit: str = ""
    last_description: str = ""
    last_metrics: dict[str, float] = field(default_factory=dict)
    last_status: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "phase": self.phase.value,
            "brief_path": self.brief_path,
            "work_dir": self.work_dir,
            "branch": self.branch,
            "pre_iteration_sha": self.pre_iteration_sha,
            "last_commit": self.last_commit,
            "last_description": self.last_description,
            "last_metrics": self.last_metrics,
            "last_status": self.last_status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PhaseState:
        return cls(
            iteration=d["iteration"],
            phase=Phase(d["phase"]),
            brief_path=d["brief_path"],
            work_dir=d["work_dir"],
            branch=d["branch"],
            pre_iteration_sha=d.get("pre_iteration_sha", ""),
            last_commit=d.get("last_commit", ""),
            last_description=d.get("last_description", ""),
            last_metrics=d.get("last_metrics", {}),
            last_status=d.get("last_status"),
        )


@dataclass
class Decision:
    status: Status
    metrics: dict[str, float]
    improved: bool
    reason: str


@dataclass
class VerifyResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_s: float
    timed_out: bool = False
