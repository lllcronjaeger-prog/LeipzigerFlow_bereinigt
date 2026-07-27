from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from leipzigerflow.planner.optimizer.candidate import OptimizationCandidate
from leipzigerflow.planner.optimizer.explanation import ExplanationKind, OptimizationExplanation


class SoftRule(Protocol):
    code: str
    title: str

    def evaluate(self, candidate: OptimizationCandidate) -> tuple[OptimizationExplanation, ...]: ...


@dataclass(frozen=True, slots=True)
class ExistingScoreRule:
    """Carries the transparent Sprint-13 score into the modular optimizer."""

    code: str = "assignment_score"
    title: str = "Dispositionsbewertung"

    def evaluate(self, candidate: OptimizationCandidate) -> tuple[OptimizationExplanation, ...]:
        assignment = candidate.assignment
        explanations = [
            OptimizationExplanation(
                rule_code=self.code,
                title=self.title,
                message=reason,
                kind=ExplanationKind.SOFT_RULE,
                points=0,
            )
            for reason in assignment.reasons
        ]
        explanations.append(
            OptimizationExplanation(
                rule_code=self.code,
                title=self.title,
                message=f"Gesamtwert der bestehenden Bewertungsregeln: {assignment.score} Punkte.",
                kind=ExplanationKind.SOFT_RULE,
                points=assignment.score,
            )
        )
        return tuple(explanations)


@dataclass(frozen=True, slots=True)
class PlanningStabilityRule:
    threshold_points: int
    code: str = "planning_stability"
    title: str = "Planungsstabilität"

    def evaluate(self, candidate: OptimizationCandidate) -> tuple[OptimizationExplanation, ...]:
        if candidate.current_score is None:
            return ()
        improvement = candidate.assignment.score - candidate.current_score
        passed = improvement >= self.threshold_points
        message = (
            f"Verbesserung um {improvement} Punkte überschreitet die Änderungsschwelle."
            if passed
            else f"Verbesserung um {improvement} Punkte ist für eine Umplanung zu gering."
        )
        return (
            OptimizationExplanation(
                rule_code=self.code,
                title=self.title,
                message=message,
                kind=ExplanationKind.SOFT_RULE,
                points=0 if passed else -self.threshold_points,
                passed=True,
            ),
        )
