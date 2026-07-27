from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leipzigerflow.planner.engine.models import AssignmentScore
from leipzigerflow.planner.engine.rules import DispatchRules
from leipzigerflow.planner.optimizer import OptimizationCandidate, TourOptimizationProfile, TourOptimizer


class OptimizationProfile(StrEnum):
    FAST = "Schnellplanung"
    BALANCED = "Ausgewogene Planung"
    THOROUGH = "Optimale Planung"

    def to_tour_profile(self) -> TourOptimizationProfile:
        return TourOptimizationProfile(self.value)


@dataclass(frozen=True, slots=True)
class RankedAssignment:
    score: AssignmentScore
    confidence_percent: int
    confidence_label: str
    equivalent_to_best: bool = False


class DispatchOptimizer:
    """Compatibility facade around the modular Sprint-14 TourOptimizer core."""

    def __init__(self, rules: DispatchRules | None = None):
        self.rules = rules or DispatchRules()
        self.rules.validate()
        self._core = TourOptimizer(self.rules)

    def rank(
        self,
        scores: list[AssignmentScore],
        profile: OptimizationProfile = OptimizationProfile.BALANCED,
    ) -> list[RankedAssignment]:
        result = self._core.optimize(
            (OptimizationCandidate.from_assignment(score) for score in scores),
            profile.to_tour_profile(),
        )
        ranked = ([result.selected] if result.selected is not None else []) + list(result.alternatives)
        return [
            RankedAssignment(
                score=item.candidate.assignment,
                confidence_percent=item.confidence_percent,
                confidence_label=item.confidence_label,
                equivalent_to_best=item.equivalent_to_best,
            )
            for item in ranked
        ]

    def should_replace_existing(self, current_score: int, proposed_score: int) -> bool:
        return proposed_score >= current_score + self.rules.stability_threshold_points
