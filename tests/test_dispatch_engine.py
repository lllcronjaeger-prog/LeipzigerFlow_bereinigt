from datetime import date, datetime, time
from types import SimpleNamespace

from leipzigerflow.planner.engine.dispatcher import AutomaticDispatcher
from leipzigerflow.planner.engine.models import (
    ResourceAvailability,
    ResourceState,
    VehicleClass,
)


def _location(location_id: int, name: str, opening_hours: str = "06:00-18:00"):
    return SimpleNamespace(
        id=location_id,
        name=name,
        full_display=name,
        opening_hours=opening_hours,
        loading_duration_minutes=60,
        unloading_duration_minutes=60,
    )


def _order(order_id: int, number: str, required_trailer_type: str = "Plane"):
    loading = _location(1, "Ladestelle")
    unloading = _location(2, "Entladestelle")
    return SimpleNamespace(
        id=order_id,
        order_number=number,
        loading_date=date(2026, 7, 21),
        loading_time_from=time(8, 0),
        loading_time_until=time(12, 0),
        unloading_date=date(2026, 7, 21),
        unloading_time_from=None,
        unloading_time_until=None,
        loading_location=loading,
        unloading_location=unloading,
        loading_location_id=1,
        unloading_location_id=2,
        status="Neu",
        remarks="",
        required_trailer_type=required_trailer_type,
    )


def _resource(vehicle_class=VehicleClass.STANDARD):
    return ResourceAvailability(
        vehicle_id=1,
        vehicle_label="L-LL 1001",
        driver_id=5,
        driver_label="Max Fahrer",
        available_at=datetime(2026, 7, 21, 6, 0),
        location_id=1,
        location_label="Ladestelle",
        state=ResourceState.FREE,
        vehicle_class=vehicle_class,
        trailer_type=("Mega-Plane" if vehicle_class is VehicleClass.MEGA else "Plane"),
    )


def test_dispatcher_assigns_feasible_order():
    result = AutomaticDispatcher().simulate([_resource()], [_order(1, "LF-1")], date(2026, 7, 21))
    assert result.assigned_count == 1
    assert result.open_count == 0
    assert result.assignments[0].order_number == "LF-1"


def test_standard_vehicle_cannot_take_mega_order():
    result = AutomaticDispatcher().simulate([_resource()], [_order(1, "LF-1", "Mega-Plane")], date(2026, 7, 21))
    assert result.assigned_count == 0
    assert result.open_count == 1
    assert any("Mega-Zugmaschine" in reason for reason in result.unassigned[0].reasons)


def test_existing_tour_is_preferred_as_extension():
    resource = _resource()
    resource.source_tour_id = 12
    resource.source_tour_number = "T-12"
    result = AutomaticDispatcher().simulate([resource], [_order(1, "LF-1")], date(2026, 7, 21))
    assert result.assignments[0].mode.value == "Bestehende Tour erweitern"
    assert result.extended_tour_count == 1


def test_simulation_contains_management_metrics_and_alternatives():
    first = _resource()
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    result = AutomaticDispatcher().simulate(
        [first, second],
        [_order(1, "LF-1")],
        date(2026, 7, 21),
    )
    assert result.assigned_count == 1
    assert result.utilized_vehicle_count == 1
    assert result.average_score > 0
    assert result.assignments[0].alternatives


def test_order_can_accept_multiple_trailer_types():
    standard = _resource()
    mega = _resource(vehicle_class=VehicleClass.MEGA)
    mega.vehicle_id = 2
    mega.vehicle_label = "L-LL 2002"
    order = _order(1, "LF-MULTI", "Plane;Mega-Plane")
    result = AutomaticDispatcher().simulate([standard, mega], [order], date(2026, 7, 21))
    assert result.assigned_count == 1
    assert result.assignments[0].vehicle_label in {standard.vehicle_label, mega.vehicle_label}


def test_box_trailer_is_rejected_when_only_plane_types_are_allowed():
    resource = _resource()
    resource.trailer_type = "Koffer"
    order = _order(1, "LF-PLANE", "Plane;Mega-Plane")
    result = AutomaticDispatcher().simulate([resource], [order], date(2026, 7, 21))
    assert result.open_count == 1
    assert any("Plane, Mega-Plane" in reason for reason in result.unassigned[0].reasons)


def test_standard_trailer_is_preferred_to_preserve_mega_resource():
    standard = _resource()
    mega = _resource(vehicle_class=VehicleClass.MEGA)
    mega.vehicle_id = 2
    mega.vehicle_label = "L-LL 2002"
    order = _order(1, "LF-RESERVE", "Plane;Mega-Plane")
    result = AutomaticDispatcher().simulate([mega, standard], [order], date(2026, 7, 21))
    assert result.assignments[0].vehicle_label == standard.vehicle_label
    assert any("Mega-Plane bleibt frei" in reason for reason in result.assignments[0].reasons)


def test_equivalent_assignments_are_marked_for_dispatcher_choice():
    first = _resource()
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    result = AutomaticDispatcher().simulate([first, second], [_order(1, "LF-TIE")], date(2026, 7, 21))
    assert result.assignments[0].equivalent_best is True
    assert result.assignments[0].confidence_label in {"Mittel", "Niedrig"}


def test_planning_horizon_rule_is_validated():
    from leipzigerflow.planner.engine.rules import DispatchRules
    rules = DispatchRules(planning_horizon_days=32)
    try:
        rules.validate()
    except ValueError as exc:
        assert "planning_horizon_days" in str(exc)
    else:
        raise AssertionError("Expected invalid planning horizon to raise")


def test_dispatcher_spreads_flexible_orders_across_available_vehicles():
    first = _resource()
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    orders = [_order(i, f"LF-{i}") for i in range(1, 8)]
    for order in orders:
        order.loading_time_until = time(23, 0)
    result = AutomaticDispatcher().simulate([first, second], orders, date(2026, 7, 21))
    used = {assignment.vehicle_id for assignment in result.assignments}
    assert used == {1, 2}


def test_driver_shift_end_is_a_hard_limit():
    resource = _resource()
    resource.duty_start_at = datetime(2026, 7, 21, 6, 0)
    resource.duty_end_at = datetime(2026, 7, 21, 11, 0)
    order = _order(1, "LF-SHIFT")
    order.loading_time_from = time(10, 0)
    order.loading_time_until = time(23, 0)
    result = AutomaticDispatcher().simulate([resource], [order], date(2026, 7, 21))
    assert result.open_count == 1
    assert any("Fahrerschicht endet" in reason for reason in result.unassigned[0].reasons)


def test_flexible_booked_window_can_be_moved_within_opening_hours():
    resource = _resource()
    resource.available_at = datetime(2026, 7, 21, 9, 30)
    order = _order(1, "LF-FLEX")
    order.loading_time_from = time(6, 0)
    order.loading_time_until = time(7, 0)
    order.loading_time_flexible = True
    order.loading_open_from = time(6, 0)
    order.loading_open_until = time(14, 0)
    order.unloading_time_flexible = True
    order.unloading_open_from = time(6, 0)
    order.unloading_open_until = time(18, 0)

    result = AutomaticDispatcher().simulate([resource], [order], date(2026, 7, 21))

    assert result.assigned_count == 1
    assignment = result.assignments[0]
    assert assignment.loading_rebooking_required is True
    assert assignment.loading_at == datetime(2026, 7, 21, 9, 30)
    assert "09:30" in assignment.proposed_loading_window
    assert any("Umbuchung Ladezeitfenster" in reason for reason in assignment.reasons)


def test_fixed_booked_window_remains_a_hard_rule():
    resource = _resource()
    resource.available_at = datetime(2026, 7, 21, 9, 30)
    order = _order(1, "LF-FIX")
    order.loading_time_from = time(6, 0)
    order.loading_time_until = time(7, 0)
    order.loading_time_flexible = False
    order.loading_open_from = time(6, 0)
    order.loading_open_until = time(14, 0)

    result = AutomaticDispatcher().simulate([resource], [order], date(2026, 7, 21))

    assert result.open_count == 1
    assert any("Ladezeitfenster nicht erreichbar" in reason for reason in result.unassigned[0].reasons)


def test_simulation_creates_actionable_planning_suggestions():
    first = _resource()
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    orders = [_order(i, f"LF-SUG-{i}") for i in range(1, 4)]
    for order in orders:
        order.loading_time_until = time(23, 0)
    result = AutomaticDispatcher().simulate([first, second], orders, date(2026, 7, 21))
    assert result.suggestion_count >= 1
    assert any(item.category in {"Tourenbildung", "Planqualität", "Flottenauslastung"} for item in result.suggestions)


def test_fleet_balancing_uses_both_equally_suitable_vehicles():
    first = _resource()
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    orders = [_order(i, f"LF-BAL-{i}") for i in range(1, 5)]
    for order in orders:
        order.loading_time_until = time(23, 0)
    result = AutomaticDispatcher().simulate([first, second], orders, date(2026, 7, 21))
    counts = {1: 0, 2: 0}
    for assignment in result.assignments:
        counts[assignment.vehicle_id] += 1
    assert counts[1] > 0 and counts[2] > 0
    assert abs(counts[1] - counts[2]) <= 2


def test_planning_core_creates_parallel_initial_wave_and_trace():
    first = _resource()
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    second.driver_id = 6
    second.driver_label = "Fahrer 6"
    orders = [_order(i, f"LF-WAVE-{i}") for i in range(1, 7)]
    for order in orders:
        order.loading_time_from = time(8, 0)
        order.loading_time_until = time(23, 0)
    result = AutomaticDispatcher().simulate([first, second], orders, date(2026, 7, 21))
    first_by_vehicle = {}
    for assignment in result.assignments:
        first_by_vehicle.setdefault(assignment.vehicle_id, assignment.loading_at)
    assert set(first_by_vehicle) == {1, 2}
    assert first_by_vehicle[1] == datetime(2026, 7, 21, 8, 0)
    assert first_by_vehicle[2] == datetime(2026, 7, 21, 8, 0)
    assert len(result.planning_trace) >= 7
    assert len(result.planning_variants) == 4
    assert result.estimated_capacity_minutes > 0


def test_six_identical_flexible_orders_create_two_non_overlapping_day_tours():
    first = _resource()
    first.driver_id = 11
    first.driver_label = "Fahrer 11"
    first.duty_start_at = datetime(2026, 7, 21, 8, 0)
    first.duty_end_at = datetime(2026, 7, 21, 18, 0)
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    second.driver_id = 22
    second.driver_label = "Fahrer 22"
    second.duty_start_at = datetime(2026, 7, 21, 8, 0)
    second.duty_end_at = datetime(2026, 7, 21, 18, 0)
    orders = [_order(i, f"LF-IDENT-{i}") for i in range(1, 7)]
    for order in orders:
        order.loading_time_from = time(8, 0)
        order.loading_time_until = time(9, 0)
        order.loading_time_flexible = True
        order.loading_open_from = time(8, 0)
        order.loading_open_until = time(18, 0)
        order.unloading_time_flexible = True
        order.unloading_open_from = time(8, 0)
        order.unloading_open_until = time(18, 0)
        order.loading_location.postal_code = "04109"
        order.unloading_location.postal_code = "06108"

    result = AutomaticDispatcher().simulate([first, second], orders, date(2026, 7, 21))

    assert result.assigned_count == 6
    assert result.proposed_tour_count == 2
    assert sorted(tour.order_count for tour in result.proposed_tours) == [3, 3]
    assert all("Region 06" in tour.cluster_label for tour in result.proposed_tours)
    for vehicle_id in (1, 2):
        vehicle_assignments = sorted(
            (item for item in result.assignments if item.vehicle_id == vehicle_id),
            key=lambda item: item.loading_at,
        )
        assert len(vehicle_assignments) == 3
        assert all(
            current.available_again_at <= following.loading_at
            for current, following in zip(vehicle_assignments, vehicle_assignments[1:])
        )


def test_same_driver_is_not_planned_in_parallel_on_two_vehicles():
    first = _resource()
    first.driver_id = 77
    first.duty_start_at = datetime(2026, 7, 21, 8, 0)
    first.duty_end_at = datetime(2026, 7, 21, 18, 0)
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    second.driver_id = 77
    second.driver_label = first.driver_label
    second.duty_start_at = datetime(2026, 7, 21, 8, 0)
    second.duty_end_at = datetime(2026, 7, 21, 18, 0)
    orders = [_order(i, f"LF-DRV-{i}") for i in range(1, 3)]
    for order in orders:
        order.loading_time_until = time(18, 0)
        order.loading_time_flexible = True
        order.loading_open_from = time(8, 0)
        order.loading_open_until = time(18, 0)
        order.unloading_time_flexible = True
        order.unloading_open_from = time(8, 0)
        order.unloading_open_until = time(18, 0)

    result = AutomaticDispatcher().simulate([first, second], orders, date(2026, 7, 21))
    driver_jobs = sorted(result.assignments, key=lambda item: item.loading_at)
    assert all(
        current.available_again_at <= following.loading_at
        for current, following in zip(driver_jobs, driver_jobs[1:])
    )


def _chain_order(
    order_id: int,
    number: str,
    loading_location,
    unloading_location,
    *,
    loading_date=date(2026, 7, 21),
    loading_from=time(6, 0),
    loading_until=time(23, 0),
    unloading_date=date(2026, 7, 21),
    unloading_from=None,
    unloading_until=None,
):
    return SimpleNamespace(
        id=order_id,
        order_number=number,
        loading_date=loading_date,
        loading_time_from=loading_from,
        loading_time_until=loading_until,
        unloading_date=unloading_date,
        unloading_time_from=unloading_from,
        unloading_time_until=unloading_until,
        loading_location=loading_location,
        unloading_location=unloading_location,
        loading_location_id=loading_location.id,
        unloading_location_id=unloading_location.id,
        status="Neu",
        remarks="",
        required_trailer_type="Plane",
        dispatch_priority="Eigenfuhrpark bevorzugt",
    )


def test_pe_001_global_chain_uses_own_fleet_before_subcontractor():
    """PE-001: Karlsruhe→Germersheim→Mannheim→Wöllstein stays intact."""
    karlsruhe = _location(10, "Karlsruhe", "00:00-23:59")
    germersheim = _location(20, "Germersheim", "00:00-23:59")
    mannheim = _location(30, "Mannheim", "00:00-23:59")
    woellstein = _location(40, "Wöllstein", "00:00-23:59")

    orders = [
        _chain_order(i, f"KA-GER-{i}", karlsruhe, germersheim)
        for i in range(1, 5)
    ]
    orders.append(_chain_order(5, "GER-MA", germersheim, mannheim))
    orders.append(_chain_order(
        6,
        "MA-WOE",
        mannheim,
        woellstein,
        unloading_date=date(2026, 7, 22),
        unloading_from=time(7, 0),
        unloading_until=time(10, 0),
    ))

    first = _resource()
    first.location_id = karlsruhe.id
    first.location_label = karlsruhe.full_display
    first.duty_end_at = None
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    second.driver_id = 6
    second.driver_label = "Erika Fahrer"
    second.location_id = karlsruhe.id
    second.location_label = karlsruhe.full_display
    second.duty_end_at = None

    result = AutomaticDispatcher().simulate([first, second], orders, date(2026, 7, 21))

    assert result.assigned_count == 6
    assert result.subcontractor_count == 0
    by_vehicle = {}
    for assignment in result.assignments:
        by_vehicle.setdefault(assignment.vehicle_id, []).append(assignment.order_number)

    chain_vehicle = next(
        vehicle_id for vehicle_id, numbers in by_vehicle.items()
        if "GER-MA" in numbers
    )
    assert "MA-WOE" in by_vehicle[chain_vehicle]
    assert sum(number.startswith("KA-GER-") for number in by_vehicle[chain_vehicle]) == 1
    other_vehicle = next(vehicle_id for vehicle_id in by_vehicle if vehicle_id != chain_vehicle)
    assert sum(number.startswith("KA-GER-") for number in by_vehicle[other_vehicle]) == 3


def test_own_fleet_orders_are_completed_before_sale_preferred_orders():
    first = _resource()
    first.driver_id = 11
    first.duty_start_at = datetime(2026, 7, 21, 6, 0)
    first.duty_end_at = datetime(2026, 7, 21, 18, 0)
    second = _resource()
    second.vehicle_id = 2
    second.vehicle_label = "L-LL 1002"
    second.driver_id = 22
    second.driver_label = "Fahrer 22"
    second.duty_start_at = datetime(2026, 7, 21, 6, 0)
    second.duty_end_at = datetime(2026, 7, 21, 18, 0)

    own_orders = [_order(i, f"OWN-{i}") for i in range(1, 7)]
    for order in own_orders:
        order.dispatch_priority = "Eigenfuhrpark bevorzugt"
        order.loading_time_until = time(23, 0)
        order.loading_time_flexible = True
        order.loading_open_from = time(6, 0)
        order.loading_open_until = time(23, 0)
        order.unloading_time_flexible = True
        order.unloading_open_from = time(6, 0)
        order.unloading_open_until = time(23, 0)

    sale = _order(99, "SALE-99")
    sale.dispatch_priority = "Verkauf bevorzugt"
    sale.route_distance_km = 220.0
    sale.loading_time_until = time(23, 0)
    sale.loading_time_flexible = True
    sale.loading_open_from = time(6, 0)
    sale.loading_open_until = time(23, 0)
    sale.unloading_time_flexible = True
    sale.unloading_open_from = time(6, 0)
    sale.unloading_open_until = time(23, 0)

    result = AutomaticDispatcher().simulate(
        [first, second], own_orders + [sale], date(2026, 7, 21)
    )

    assigned_numbers = [item.order_number for item in result.assignments]
    assert all(number in assigned_numbers for number in [f"OWN-{i}" for i in range(1, 7)])
    own_positions = [assigned_numbers.index(f"OWN-{i}") for i in range(1, 7)]
    if "SALE-99" in assigned_numbers:
        assert max(own_positions) < assigned_numbers.index("SALE-99")


def test_long_distance_sale_order_is_reserved_for_subcontractor():
    order = _order(1, "SALE-LONG")
    order.dispatch_priority = "Verkauf bevorzugt"
    order.route_distance_km = 200.0
    result = AutomaticDispatcher().simulate([_resource()], [order], date(2026, 7, 21))
    assert result.assigned_count == 0
    assert result.subcontractor_count == 1
    assert any("Subunternehmer" in reason for reason in result.unassigned[0].reasons)


def test_cumulative_driver_work_above_ten_hours_is_blocked():
    first = _resource()
    first.duty_start_at = datetime(2026, 7, 21, 6, 0)
    first.duty_end_at = datetime(2026, 7, 21, 16, 0)
    orders = [_order(i, f"LF-WORK-{i}") for i in range(1, 6)]
    for item in orders:
        item.loading_time_from = time(6, 0)
        item.loading_time_until = time(23, 0)
        item.dispatch_priority = "Eigenfuhrpark bevorzugt"
    result = AutomaticDispatcher().simulate([first], orders, date(2026, 7, 21))
    assert result.assigned_count <= 3
    assert result.open_count >= 2
    assert any(
        "Arbeitszeit" in reason and "10:00" in reason
        for unassigned in result.unassigned for reason in unassigned.reasons
    )


def test_dispatcher_uses_routing_duration_for_unloading_timeline():
    from leipzigerflow.routing.models import RouteResult

    class FixedRoutingService:
        def calculate(self, origin_location_id: int, destination_location_id: int):
            assert (origin_location_id, destination_location_id) == (1, 2)
            return RouteResult(180.0, 150, provider="test")

    resource = _resource()
    order = _order(1, "LF-ROUTE-TIME")
    order.loading_location._sa_instance_state = object()
    order.unloading_location._sa_instance_state = object()

    result = AutomaticDispatcher(routing_service=FixedRoutingService()).simulate(
        [resource], [order], date(2026, 7, 21)
    )

    assert result.assigned_count == 1
    assignment = result.assignments[0]
    assert assignment.loading_at == datetime(2026, 7, 21, 8, 0)
    assert assignment.unloading_at == datetime(2026, 7, 21, 11, 30)
    assert assignment.available_again_at == datetime(2026, 7, 21, 12, 30)
    assert any("Routing: 150 Minuten" in reason for reason in assignment.reasons)


def test_dispatcher_keeps_30_minute_fallback_without_routing_duration():
    from leipzigerflow.routing.models import RouteResult

    class MissingDurationRoutingService:
        def calculate(self, origin_location_id: int, destination_location_id: int):
            return RouteResult(None, 0, provider="fallback", estimated=True)

    resource = _resource()
    order = _order(1, "LF-ROUTE-FALLBACK")
    order.loading_location._sa_instance_state = object()
    order.unloading_location._sa_instance_state = object()

    result = AutomaticDispatcher(routing_service=MissingDurationRoutingService()).simulate(
        [resource], [order], date(2026, 7, 21)
    )

    assert result.assigned_count == 1
    assignment = result.assignments[0]
    assert assignment.unloading_at == datetime(2026, 7, 21, 9, 30)
    assert any("mit 30 Minuten geschätzt" in reason for reason in assignment.reasons)
