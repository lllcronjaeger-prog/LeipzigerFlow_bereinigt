from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from leipzigerflow.planner.optimizer.candidate import OptimizationCandidate
from leipzigerflow.planner.optimizer.explanation import ExplanationKind, OptimizationExplanation


class HardRule(Protocol):
    code: str
    title: str

    def evaluate(self, candidate: OptimizationCandidate) -> tuple[OptimizationExplanation, ...]: ...


@dataclass(frozen=True, slots=True)
class ExistingFeasibilityRule:
    """Bridges the established Sprint-13 hard-rule evaluation into the new core."""

    code: str = "existing_feasibility"
    title: str = "Fachliche Machbarkeit"

    def evaluate(self, candidate: OptimizationCandidate) -> tuple[OptimizationExplanation, ...]:
        assignment = candidate.assignment
        if assignment.feasible:
            return (
                OptimizationExplanation(
                    rule_code=self.code,
                    title=self.title,
                    message="Alle fachlichen Muss-Regeln sind erfüllt.",
                    kind=ExplanationKind.HARD_RULE,
                    passed=True,
                ),
            )
        reasons = assignment.rejection_reasons or ["Kombination ist fachlich nicht zulässig."]
        return tuple(
            OptimizationExplanation(
                rule_code=self.code,
                title=self.title,
                message=reason,
                kind=ExplanationKind.HARD_RULE,
                passed=False,
            )
            for reason in reasons
        )


@dataclass(frozen=True, slots=True)
class LockedCandidateRule:
    code: str = "locked_candidate"
    title: str = "Änderungsschutz"

    def evaluate(self, candidate: OptimizationCandidate) -> tuple[OptimizationExplanation, ...]:
        if not candidate.locked:
            return ()
        return (
            OptimizationExplanation(
                rule_code=self.code,
                title=self.title,
                message="Die Kombination ist gesperrt und darf nicht automatisch verändert werden.",
                kind=ExplanationKind.HARD_RULE,
                passed=False,
            ),
        )
