from datetime import datetime, timedelta

from leipzigerflow.planner.engine.models import AssignmentMode, ProposedAssignment
from leipzigerflow.planner.engine.tour_builder import AutomaticTourBuilder


def _assignment(order_id: int, vehicle_id: int, driver_id: int, hour: int, source_tour_id: int):
    start = datetime(2026, 7, 22, hour, 0)
    return ProposedAssignment(
        vehicle_id=vehicle_id,
        vehicle_label=f"L-{vehicle_id}",
        driver_id=driver_id,
        driver_label=f"Fahrer {driver_id}",
        order_id=order_id,
        order_number=f"A-{order_id}",
        score=100 - order_id,
        loading_at=start,
        available_again_at=start + timedelta(hours=1),
        mode=AssignmentMode.EXTEND_TOUR,
        source_tour_id=source_tour_id,
        source_tour_number=f"T-{source_tour_id}",
    )


def test_builder_groups_orders_by_vehicle_shift_and_orders_chronologically():
    assignments = [
        _assignment(2, 1, 10, 9, 100),
        _assignment(1, 1, 10, 7, 100),
        _assignment(3, 2, 20, 8, 200),
    ]

    tours = AutomaticTourBuilder().build(assignments)

    assert len(tours) == 2
    assert [item.order_number for item in tours[0].assignments] == ["A-1", "A-2"]
    assert [item.proposed_tour_position for item in tours[0].assignments] == [1, 2]
    assert tours[1].vehicle_id == 2
