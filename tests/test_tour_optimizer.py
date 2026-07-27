from datetime import datetime

from leipzigerflow.planner.engine.models import (
    AssignmentMode,
    AssignmentScore,
    OrderCandidate,
    ResourceAvailability,
    ResourceState,
    VehicleClass,
)
from leipzigerflow.planner.engine.rules import DispatchRules
from leipzigerflow.planner.optimizer import (
    OptimizationCandidate,
    TourOptimizationProfile,
    TourOptimizer,
)


def _assignment(score: int, vehicle_id: int = 1, feasible: bool = True) -> AssignmentScore:
    resource = ResourceAvailability(
        vehicle_id=vehicle_id,
        vehicle_label=f"L-LL {vehicle_id}",
        driver_id=vehicle_id,
        driver_label=f"Fahrer {vehicle_id}",
        available_at=datetime(2026, 7, 21, 6, 0),
        location_id=1,
        location_label="Leipzig",
        state=ResourceState.FREE,
        vehicle_class=VehicleClass.STANDARD,
        trailer_type="Plane",
    )
    order = OrderCandidate(order_id=10, order_number="LF-10", priority_score=100)
    return AssignmentScore(
        resource=resource,
        order=order,
        score=score,
        feasible=feasible,
        planned_loading_at=datetime(2026, 7, 21, 8, 0),
        planned_available_at=datetime(2026, 7, 21, 12, 0),
        mode=AssignmentMode.NEW_TOUR,
        reasons=[f"Basisbewertung {score}"],
        rejection_reasons=[] if feasible else ["Trailertyp nicht zulässig"],
    )


def test_optimizer_selects_best_candidate_and_exposes_breakdown():
    optimizer = TourOptimizer()
    result = optimizer.optimize(
        [
            OptimizationCandidate.from_assignment(_assignment(80, 1)),
            OptimizationCandidate.from_assignment(_assignment(105, 2)),
        ]
    )
    assert result.has_selection
    assert result.selected.candidate.assignment.resource.vehicle_id == 2
    assert result.selected.total_score == 105
    assert result.selected.score_breakdown
    assert result.evaluated_count == 2


def test_optimizer_separates_hard_rule_rejections():
    result = TourOptimizer().optimize(
        [OptimizationCandidate.from_assignment(_assignment(200, feasible=False))]
    )
    assert result.selected is None
    assert len(result.rejected) == 1
    assert result.rejected[0].hard_rule_failures
    assert "Trailertyp" in result.rejected[0].hard_rule_failures[0].message


def test_locked_candidate_is_rejected():
    candidate = OptimizationCandidate(
        candidate_id="locked",
        assignment=_assignment(100),
        locked=True,
    )
    result = TourOptimizer().optimize([candidate])
    assert result.selected is None
    assert any("gesperrt" in item.message for item in result.rejected[0].hard_rule_failures)


def test_equal_candidates_are_marked_as_equivalent():
    optimizer = TourOptimizer(DispatchRules(equivalent_score_margin=10))
    result = optimizer.optimize(
        [
            OptimizationCandidate.from_assignment(_assignment(100, 1)),
            OptimizationCandidate.from_assignment(_assignment(95, 2)),
        ]
    )
    assert result.alternatives[0].equivalent_to_best is True
    assert result.selected.confidence_label in {"Mittel", "Niedrig"}


def test_fast_profile_limits_visible_alternatives():
    candidates = [OptimizationCandidate.from_assignment(_assignment(100 - i, i + 1)) for i in range(15)]
    result = TourOptimizer().optimize(candidates, TourOptimizationProfile.FAST)
    assert result.evaluated_count == 15
    assert len(result.alternatives) == 2
