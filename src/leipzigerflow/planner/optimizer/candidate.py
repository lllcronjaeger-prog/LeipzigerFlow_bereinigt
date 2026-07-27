from __future__ import annotations

from dataclasses import dataclass

from leipzigerflow.planner.engine.models import AssignmentScore


@dataclass(frozen=True, slots=True)
class OptimizationCandidate:
    """Stable wrapper around a scored dispatcher assignment.

    The wrapper deliberately keeps the existing AssignmentScore as its payload.
    Sprint 14.2 can add stop sequences without changing the ranking API.
    """

    candidate_id: str
    assignment: AssignmentScore
    current_score: int | None = None
    locked: bool = False

    @classmethod
    def from_assignment(cls, assignment: AssignmentScore) -> "OptimizationCandidate":
        resource = assignment.resource
        order = assignment.order
        return cls(
            candidate_id=f"order:{order.order_id}|vehicle:{resource.vehicle_id}",
            assignment=assignment,
        )
