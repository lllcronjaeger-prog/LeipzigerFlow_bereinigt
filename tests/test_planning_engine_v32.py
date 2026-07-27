from datetime import date, datetime, time
from types import SimpleNamespace

from leipzigerflow.planner.engine.dispatcher import AutomaticDispatcher
from leipzigerflow.planner.engine.models import (
    AssignmentMode,
    PlanningStrategy,
    ProposedAssignment,
    ResourceAvailability,
    ResourceState,
    VehicleClass,
)
from leipzigerflow.planner.engine.tour_quality import TourQualityEvaluator
from leipzigerflow.planner.engine.transport_chains import TransportChainDetector


def _location(location_id: int, name: str):
    return SimpleNamespace(
        id=location_id,
        name=name,
        full_display=name,
        postal_code=str(10000 + location_id),
        opening_hours="00:00-23:59",
        loading_duration_minutes=30,
        unloading_duration_minutes=30,
    )


def _order(order_id, loading, unloading, *, load_hour=6, unload_hour=7, load_day=21, unload_day=21):
    return SimpleNamespace(
        id=order_id,
        order_number=f"PE-{order_id:03d}",
        loading_location_id=loading.id,
        unloading_location_id=unloading.id,
        loading_location=loading,
        unloading_location=unloading,
        loading_date=date(2026, 7, load_day),
        unloading_date=date(2026, 7, unload_day),
        loading_time_from=time(load_hour, 0),
        loading_time_until=time(min(23, load_hour + 1), 0),
        unloading_time_from=time(unload_hour, 0),
        unloading_time_until=time(min(23, unload_hour + 1), 0),
        status="Neu",
        remarks="",
        required_trailer_type="Plane",
        dispatch_priority="Eigenfuhrpark bevorzugt",
    )


def _assignment(number, loading, unloading, start, end, transfer=0):
    return ProposedAssignment(
        vehicle_id=1,
        vehicle_label="L-LL 1001",
        driver_id=1,
        driver_label="Fahrer A",
        order_id=int(number),
        order_number=f"PE-{number}",
        score=300,
        loading_at=start,
        available_again_at=end,
        mode=AssignmentMode.NEW_TOUR,
        loading_location_label=loading,
        unloading_location_label=unloading,
        transfer_minutes=transfer,
    )


def test_pe_002_longest_branch_is_selected_globally():
    a, b, c, d, e, x = [_location(i, chr(64 + i)) for i in range(1, 7)]
    orders = [
        _order(1, a, b, load_hour=6, unload_hour=7),
        _order(2, b, c, load_hour=8, unload_hour=9),
        _order(3, c, d, load_hour=10, unload_hour=11),
        _order(4, d, e, load_hour=12, unload_hour=13),
        _order(5, b, x, load_hour=8, unload_hour=9),
    ]
    plan = TransportChainDetector().build(orders)
    assert plan.chain_ids_from(1) == [1, 2, 3, 4]
    assert set(plan.alternative_successors(1)) == {2, 5}


def test_pe_003_round_trip_receives_higher_chain_value():
    a, b, c, x = [_location(i, chr(64 + i)) for i in range(1, 5)]
    round_trip = [
        _order(1, a, b, load_hour=6, unload_hour=7),
        _order(2, b, c, load_hour=8, unload_hour=9),
        _order(3, c, a, load_hour=10, unload_hour=11),
    ]
    open_chain = [
        _order(11, a, b, load_hour=6, unload_hour=7),
        _order(12, b, c, load_hour=8, unload_hour=9),
        _order(13, c, x, load_hour=10, unload_hour=11),
    ]
    first = TransportChainDetector().build(round_trip)
    second = TransportChainDetector().build(open_chain)
    assert first.is_round_trip(1, {item.id: item for item in round_trip})
    assert first.chain_score_from(1, {item.id: item for item in round_trip}) > second.chain_score_from(11, {item.id: item for item in open_chain})


def test_pe_004_competing_feeders_reserve_only_one_chain_owner():
    a, b, c = [_location(i, chr(64 + i)) for i in range(1, 4)]
    plan = TransportChainDetector().build([
        _order(1, a, b),
        _order(2, a, b),
        _order(3, b, c, load_hour=9, unload_hour=10),
    ])
    assert plan.predecessor(3) in {1, 2}
    assert sum(plan.successor(item) == 3 for item in (1, 2)) == 1


def test_pe_005_multi_day_assignment_records_duty_days_and_overnight_stop():
    a, b = _location(1, "Leipzig"), _location(2, "Hamburg")
    order = _order(1, a, b, load_hour=6, unload_hour=7, unload_day=22)
    resource = ResourceAvailability(
        vehicle_id=1,
        vehicle_label="L-LL 1001",
        driver_id=1,
        driver_label="Fahrer A",
        available_at=datetime(2026, 7, 21, 5, 0),
        location_id=a.id,
        location_label=a.full_display,
        state=ResourceState.FREE,
        vehicle_class=VehicleClass.STANDARD,
        trailer_type="Plane",
    )
    result = AutomaticDispatcher().simulate([resource], [order], date(2026, 7, 21))
    assignment = result.assignments[0]
    assert assignment.duty_days == 2
    assert assignment.overnight_stop_label == "Hamburg"
    assert any("tägliche Ruhezeit" in reason for reason in assignment.reasons)


def test_pe_006_own_fleet_strategy_is_visible_in_decision_reason():
    a, b = _location(1, "A"), _location(2, "B")
    order = _order(1, a, b)
    resource = ResourceAvailability(
        vehicle_id=1,
        vehicle_label="L-LL 1001",
        driver_id=1,
        driver_label="Fahrer A",
        available_at=datetime(2026, 7, 21, 5, 0),
        location_id=a.id,
        location_label=a.full_display,
        state=ResourceState.FREE,
        vehicle_class=VehicleClass.STANDARD,
        trailer_type="Plane",
    )
    result = AutomaticDispatcher().simulate(
        [resource], [order], date(2026, 7, 21), strategy=PlanningStrategy.OWN_FLEET_FIRST
    )
    assert result.subcontractor_count == 0
    assert any("Eigenfuhrpark vor Fremdvergabe" in reason for reason in result.assignments[0].reasons)


def test_pe_007_tour_quality_rewards_direct_connections_and_penalizes_empty_runs():
    direct = [
        _assignment(1, "A", "B", datetime(2026, 7, 21, 6), datetime(2026, 7, 21, 8)),
        _assignment(2, "B", "C", datetime(2026, 7, 21, 8), datetime(2026, 7, 21, 10)),
    ]
    empty = [
        _assignment(3, "A", "B", datetime(2026, 7, 21, 6), datetime(2026, 7, 21, 8), transfer=60),
        _assignment(4, "X", "C", datetime(2026, 7, 21, 9), datetime(2026, 7, 21, 11), transfer=90),
    ]
    evaluator = TourQualityEvaluator()
    assert evaluator.evaluate(direct).score > evaluator.evaluate(empty).score
