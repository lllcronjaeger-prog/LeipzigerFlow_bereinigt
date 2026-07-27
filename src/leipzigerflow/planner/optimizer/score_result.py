from __future__ import annotations

from dataclasses import dataclass, field

from leipzigerflow.planner.optimizer.candidate import OptimizationCandidate
from leipzigerflow.planner.optimizer.explanation import OptimizationExplanation


@dataclass(frozen=True, slots=True)
class CandidateScoreResult:
    candidate: OptimizationCandidate
    total_score: int
    feasible: bool
    confidence_percent: int = 0
    confidence_label: str = "Nicht bewertet"
    equivalent_to_best: bool = False
    explanations: tuple[OptimizationExplanation, ...] = ()

    @property
    def hard_rule_failures(self) -> tuple[OptimizationExplanation, ...]:
        return tuple(item for item in self.explanations if not item.passed)

    @property
    def score_breakdown(self) -> tuple[OptimizationExplanation, ...]:
        return tuple(item for item in self.explanations if item.points)


@dataclass(frozen=True, slots=True)
class TourOptimizationResult:
    selected: CandidateScoreResult | None
    alternatives: tuple[CandidateScoreResult, ...] = ()
    rejected: tuple[CandidateScoreResult, ...] = ()
    evaluated_count: int = 0
    profile_label: str = "Ausgewogene Planung"

    @property
    def has_selection(self) -> bool:
        return self.selected is not None
