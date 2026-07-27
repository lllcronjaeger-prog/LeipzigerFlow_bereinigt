from types import SimpleNamespace

from leipzigerflow.planner.engine.models import PlanningStrategy, PlanningVariant
from leipzigerflow.planner.engine.service import DispatchSimulationService


def test_variant_carries_selectable_simulation_result():
    result = object()
    variant = PlanningVariant(
        name="Alternative",
        strategy=PlanningStrategy.BALANCED_FLEET,
        score=88,
        vehicle_count=2,
        tour_count=2,
        assigned_orders=6,
        total_minutes=1040,
        simulation_result=result,
    )
    assert variant.simulation_result is result


def test_variant_metrics_block_work_time_over_ten_hours():
    assignment = SimpleNamespace(
        vehicle_id=1,
        transfer_minutes=0,
        waiting_minutes=0,
        route_duration_minutes=500,
        route_distance_km=200.0,
        reasons=[],
    )
    result = SimpleNamespace(
        assignments=[assignment],
        assigned_count=1,
        orders_total=1,
        open_count=0,
        subcontractor_count=0,
        total_transfer_minutes=0,
    )
    score, _minutes, _distance, max_minutes, _reasons = DispatchSimulationService._variant_metrics(result)
    assert max_minutes == 620
    assert score == 0
