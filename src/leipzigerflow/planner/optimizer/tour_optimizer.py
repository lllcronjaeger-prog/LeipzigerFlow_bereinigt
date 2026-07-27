from __future__ import annotations

from collections.abc import Iterable

from leipzigerflow.planner.engine.rules import DispatchRules
from leipzigerflow.planner.optimizer.candidate import OptimizationCandidate
from leipzigerflow.planner.optimizer.explanation import ExplanationKind, OptimizationExplanation
from leipzigerflow.planner.optimizer.hard_rules import ExistingFeasibilityRule, HardRule, LockedCandidateRule
from leipzigerflow.planner.optimizer.optimization_profile import (
    PROFILE_SETTINGS,
    TourOptimizationProfile,
)
from leipzigerflow.planner.optimizer.score_result import CandidateScoreResult, TourOptimizationResult
from leipzigerflow.planner.optimizer.soft_rules import ExistingScoreRule, PlanningStabilityRule, SoftRule


class TourOptimizer:
    """Modular optimization core for assignment and future multi-stop candidates.

    Hard rules determine feasibility. Soft rules determine the transparent score.
    The class is intentionally UI- and database-independent.
    """

    def __init__(
        self,
        rules: DispatchRules | None = None,
        hard_rules: Iterable[HardRule] | None = None,
        soft_rules: Iterable[SoftRule] | None = None,
    ) -> None:
        self.rules = rules or DispatchRules()
        self.rules.validate()
        self.hard_rules = tuple(hard_rules or (LockedCandidateRule(), ExistingFeasibilityRule()))
        self.soft_rules = tuple(
            soft_rules
            or (
                ExistingScoreRule(),
                PlanningStabilityRule(self.rules.stability_threshold_points),
            )
        )

    def optimize(
        self,
        candidates: Iterable[OptimizationCandidate],
        profile: TourOptimizationProfile = TourOptimizationProfile.BALANCED,
    ) -> TourOptimizationResult:
        settings = PROFILE_SETTINGS[profile]
        evaluated = [self._evaluate(candidate) for candidate in candidates]
        feasible = [item for item in evaluated if item.feasible]
        feasible.sort(key=self._sort_key, reverse=True)
        if settings.candidate_limit is not None:
            feasible = feasible[: settings.candidate_limit]

        rejected = tuple(item for item in evaluated if not item.feasible)
        if not feasible:
            return TourOptimizationResult(
                selected=None,
                rejected=rejected,
                evaluated_count=len(evaluated),
                profile_label=profile.value,
            )

        best_score = feasible[0].total_score
        ranked: list[CandidateScoreResult] = []
        for index, item in enumerate(feasible):
            confidence, label = self._confidence(item, feasible, index)
            ranked.append(
                CandidateScoreResult(
                    candidate=item.candidate,
                    total_score=item.total_score,
                    feasible=True,
                    confidence_percent=confidence,
                    confidence_label=label,
                    equivalent_to_best=(
                        index > 0 and best_score - item.total_score <= self.rules.equivalent_score_margin
                    ),
                    explanations=item.explanations,
                )
            )

        return TourOptimizationResult(
            selected=ranked[0],
            alternatives=tuple(ranked[1 : 1 + settings.alternative_limit]),
            rejected=rejected,
            evaluated_count=len(evaluated),
            profile_label=profile.value,
        )

    def _evaluate(self, candidate: OptimizationCandidate) -> CandidateScoreResult:
        explanations: list[OptimizationExplanation] = []
        for rule in self.hard_rules:
            explanations.extend(rule.evaluate(candidate))
        feasible = not any(not item.passed for item in explanations)
        if not feasible:
            return CandidateScoreResult(
                candidate=candidate,
                total_score=candidate.assignment.score,
                feasible=False,
                explanations=tuple(explanations),
            )

        for rule in self.soft_rules:
            explanations.extend(rule.evaluate(candidate))
        total_score = sum(item.points for item in explanations if item.kind is ExplanationKind.SOFT_RULE)
        return CandidateScoreResult(
            candidate=candidate,
            total_score=total_score,
            feasible=True,
            explanations=tuple(explanations),
        )

    @staticmethod
    def _sort_key(item: CandidateScoreResult) -> tuple[int, int, int, float]:
        assignment = item.candidate.assignment
        loading_timestamp = assignment.planned_loading_at.timestamp() if assignment.planned_loading_at else 0.0
        return (
            item.total_score,
            -assignment.waiting_minutes,
            -assignment.transfer_minutes,
            -loading_timestamp,
        )

    def _confidence(
        self,
        item: CandidateScoreResult,
        ranked: list[CandidateScoreResult],
        index: int,
    ) -> tuple[int, str]:
        next_score = ranked[index + 1].total_score if index + 1 < len(ranked) else item.total_score - 20
        margin = max(0, item.total_score - next_score)
        confidence = 50 + min(35, margin * 2)
        if index == 0 and len(ranked) > 1 and margin <= self.rules.equivalent_score_margin:
            confidence = min(confidence, 69)
        assignment = item.candidate.assignment
        if assignment.waiting_minutes > 120:
            confidence -= 15
        confidence = max(0, min(100, confidence))
        if confidence >= 85:
            label = "Sehr hoch"
        elif confidence >= 70:
            label = "Hoch"
        elif confidence >= 50:
            label = "Mittel"
        else:
            label = "Niedrig"
        return confidence, label
