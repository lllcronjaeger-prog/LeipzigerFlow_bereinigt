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


def test_local_resource_rejects_order_ending_next_day():
    from datetime import date, datetime, time
    from types import SimpleNamespace
    from leipzigerflow.planner.engine.dispatcher import AutomaticDispatcher
    from leipzigerflow.planner.engine.models import ResourceAvailability, ResourceState, VehicleClass

    day = date(2026, 7, 27)
    base = SimpleNamespace(id=1, full_display="Basis", name="Basis", loading_duration_minutes=60, unloading_duration_minutes=60)
    mannheim = SimpleNamespace(id=2, full_display="Mannheim", name="Mannheim", loading_duration_minutes=60, unloading_duration_minutes=60)
    customer = SimpleNamespace(disposition_priority=5, own_fleet_preferred=False)
    order = SimpleNamespace(
        id=9001, order_number="MANNHEIM", order_type="Transport",
        loading_date=day, unloading_date=date(2026, 7, 28),
        loading_time_from=None, loading_time_until=None,
        unloading_time_from=time(6, 0), unloading_time_until=None,
        loading_time_flexible=False, unloading_time_flexible=False,
        loading_open_from=None, loading_open_until=None,
        loading_location_id=1, unloading_location_id=2,
        loading_location=base, unloading_location=mannheim,
        required_trailer_type="Plane", customer=customer,
        dispatch_priority="Eigenfuhrpark bevorzugt", route_distance_km=80,
    )
    resource = ResourceAvailability(
        vehicle_id=1, vehicle_label="8043", driver_id=1, driver_label="Nah",
        available_at=datetime(2026, 7, 27, 6), location_id=1, location_label="Basis",
        state=ResourceState.FREE, vehicle_class=VehicleClass.STANDARD, trailer_type="Plane",
        duty_start_at=datetime(2026, 7, 27, 6), duty_end_at=datetime(2026, 7, 27, 15),
        return_to_base_required=True, home_base_location_id=1, home_base_location_label="Basis",
    )
    result = AutomaticDispatcher().simulate([resource], [order], day)
    assert result.assigned_count == 0
    assert any("am selben Arbeitstag" in reason for reason in result.unassigned[0].reasons)


def test_workday_calculator_uses_one_return_to_base_only():
    from leipzigerflow.planner.engine.workday import WorkdayCalculator
    from leipzigerflow.routing.models import RouteResult

    resource = _resource()
    order = _order(1, "LF-WORKDAY")
    score = SimpleNamespace(
        transfer_minutes=20,
        waiting_minutes=10,
        planned_loading_at=datetime(2026, 7, 21, 8, 0),
        planned_unloading_at=datetime(2026, 7, 21, 10, 0),
    )
    calculation = WorkdayCalculator().candidate(
        score=score,
        order=order,
        route_result=RouteResult(50.0, 60, provider="test"),
        return_to_base_minutes=40,
        already_planned_minutes=120,
    )

    assert calculation.assignment_minutes == 20 + 10 + 60 + 60 + 60
    assert calculation.total_minutes == 120 + calculation.assignment_minutes + 40
    assert calculation.components_text().count("Rückfahrt") == 1


def test_dispatch_result_contains_candidate_decision_protocol():
    result = AutomaticDispatcher().simulate(
        [_resource()], [_order(1, "LF-TRACE")], date(2026, 7, 21)
    )

    decisions = [item for item in result.candidate_decisions if item.order_number == "LF-TRACE"]
    assert decisions
    assert any(item.selected for item in decisions)
    selected = next(item for item in decisions if item.selected)
    assert selected.feasible is True
    assert "GEWÄHLT" in selected.as_text()
    assert any("Arbeitszeitbestandteile" in check for check in selected.checks)


def test_customer_priority_1_to_10_changes_score_without_overriding_hard_rules():
    low = _order(1, "LOW")
    high = _order(2, "HIGH")
    low.customer = SimpleNamespace(disposition_priority=1, own_fleet_preferred=False)
    high.customer = SimpleNamespace(disposition_priority=10, own_fleet_preferred=False)
    low_result = AutomaticDispatcher().simulate([_resource()], [low], date(2026, 7, 21))
    high_result = AutomaticDispatcher().simulate([_resource()], [high], date(2026, 7, 21))
    assert high_result.assignments[0].score > low_result.assignments[0].score

    impossible = _order(3, "IMPOSSIBLE", "Mega-Plane")
    impossible.customer = SimpleNamespace(disposition_priority=10, own_fleet_preferred=False)
    blocked = AutomaticDispatcher().simulate([_resource()], [impossible], date(2026, 7, 21))
    assert blocked.assigned_count == 0
    assert any("Mega" in reason for reason in blocked.unassigned[0].reasons)


def test_candidate_decision_contains_balanced_score_components():
    result = AutomaticDispatcher().simulate(
        [_resource()], [_order(1, "LF-SCORE-COMPONENTS")], date(2026, 7, 21)
    )
    selected = next(item for item in result.candidate_decisions if item.selected)

    assert selected.score_components
    assert sum(selected.score_components.values()) == selected.score
    assert "Priorität" in selected.score_components
    assert "Teil-Scores:" in selected.as_text()


def test_dispatch_reports_routing_cache_and_performance_metrics():
    orders = [_order(1, "LF-PERF-1"), _order(2, "LF-PERF-2")]
    result = AutomaticDispatcher().simulate([_resource()], orders, date(2026, 7, 21))

    metrics = result.performance_metrics
    assert metrics["candidate_evaluations"] >= 2
    assert metrics["order_route_cache_entries"] == 2
    assert metrics["transfer_route_cache_misses"] >= 1
    assert metrics["transfer_route_cache_hits"] >= 1
    assert metrics["simulation_milliseconds"] >= 0


def test_trailer_change_is_rejected_away_from_home_base():
    resource = _resource()
    resource.trailer_change_required = True
    resource.location_id = 200
    resource.home_base_location_id = 100
    order = _order(901, "LF-TRAILER-CUSTOMER")

    result = AutomaticDispatcher().simulate([resource], [order], date(2026, 7, 21))

    assert result.open_count == 1
    assert any(
        "Trailerwechsel nur an der Heimatbasis" in reason
        for reason in result.unassigned[0].reasons
    )


def test_loaded_trailer_change_at_base_is_allowed_but_penalized():
    normal = _resource()
    normal.vehicle_id = 1
    normal.vehicle_label = "L-LL 1001"
    normal.location_id = 100
    normal.home_base_location_id = 100

    exceptional = _resource()
    exceptional.vehicle_id = 2
    exceptional.vehicle_label = "L-LL 1002"
    exceptional.location_id = 100
    exceptional.home_base_location_id = 100
    exceptional.trailer_change_required = True
    exceptional.trailer_loaded = True

    order = _order(902, "LF-TRAILER-LOADED")
    dispatcher = AutomaticDispatcher()
    result = dispatcher.simulate([normal, exceptional], [order], date(2026, 7, 21))

    assert result.assigned_count == 1
    assert result.assignments[0].vehicle_id == 1
    exceptional_decisions = [
        decision for decision in result.candidate_decisions
        if decision.order_number == "LF-TRAILER-LOADED" and decision.vehicle_label == "L-LL 1002"
    ]
    assert exceptional_decisions
    assert exceptional_decisions[0].feasible is True
    assert any("Beladener Trailerwechsel" in check for check in exceptional_decisions[0].checks)


def test_customer_trailer_location_is_a_hard_rejection():
    from leipzigerflow.planner.engine.trailer_state import TrailerLocationKind

    resource = _resource()
    resource.trailer_location_kind = TrailerLocationKind.INVALID_CUSTOMER.value
    order = _order(903, "LF-TRAILER-LOCATION")

    result = AutomaticDispatcher().simulate([resource], [order], date(2026, 7, 21))

    assert result.open_count == 1
    assert any(
        "Trailer darf nicht beim Kunden" in reason
        for reason in result.unassigned[0].reasons
    )


def test_future_demand_index_rewards_longhaul_destination_only():
    from datetime import date
    from types import SimpleNamespace
    from leipzigerflow.planner.engine.multiday import FutureDemandIndex

    tomorrow = date(2026, 7, 28)
    order = SimpleNamespace(loading_location_id=200)
    index = FutureDemandIndex({tomorrow: [order, order]})

    score, reasons = index.score_for_destination(200, date(2026, 7, 27))
    assert score == 32
    assert reasons and "2 Folgeauftrag" in reasons[0]
    assert index.score_for_destination(999, date(2026, 7, 27)) == (0, [])


def test_multiday_state_projector_returns_local_vehicle_to_base_and_keeps_longhaul_destination():
    from datetime import date, datetime, timedelta
    from types import SimpleNamespace
    from leipzigerflow.planner.engine.models import ResourceAvailability, ResourceState, VehicleClass
    from leipzigerflow.planner.engine.multiday import MultiDayStateProjector

    day = date(2026, 7, 27)
    start = datetime(2026, 7, 27, 8, 0)
    local = ResourceAvailability(
        vehicle_id=1, vehicle_label="LOCAL", driver_id=1, driver_label="A",
        available_at=start, location_id=10, location_label="Basis",
        state=ResourceState.FREE, vehicle_class=VehicleClass.STANDARD,
        return_to_base_required=True, home_base_location_id=10,
        home_base_location_label="Basis",
    )
    longhaul = ResourceAvailability(
        vehicle_id=2, vehicle_label="LONG", driver_id=2, driver_label="B",
        available_at=start, location_id=10, location_label="Basis",
        state=ResourceState.FREE, vehicle_class=VehicleClass.STANDARD,
        return_to_base_required=False, home_base_location_id=10,
        home_base_location_label="Basis",
    )
    assignments = [
        SimpleNamespace(vehicle_id=1, available_again_at=start + timedelta(hours=8),
                        return_to_base_minutes=45, unloading_location_label="Mannheim",
                        projected_end_location_id=20),
        SimpleNamespace(vehicle_id=2, available_again_at=start + timedelta(hours=8),
                        return_to_base_minutes=0, unloading_location_label="Mannheim",
                        projected_end_location_id=20),
    ]
    simulation = SimpleNamespace(assignments=assignments)
    projector = MultiDayStateProjector()
    states = projector.project_day_end([local, longhaul], simulation, day)
    by_vehicle = {state.vehicle_id: state for state in states}

    assert by_vehicle[1].location_id == 10
    assert by_vehicle[1].location_label == "Basis"
    assert by_vehicle[2].location_id == 20
    assert by_vehicle[2].location_label == "Mannheim"

    next_resources = projector.resources_for_next_day([local, longhaul], states, day + timedelta(days=1))
    assert all(item.available_at.date() == day + timedelta(days=1) for item in next_resources)
    assert all(item.available_at.hour == 8 for item in next_resources)
    assert next(item for item in next_resources if item.vehicle_id == 2).location_id == 20


def test_apply_horizon_persists_every_simulated_day_in_order():
    from datetime import date
    from types import SimpleNamespace
    from leipzigerflow.planner.engine.service import DispatchSimulationService
    from leipzigerflow.planner.engine.multiday import MultiDayPlanningResult

    service = DispatchSimulationService.__new__(DispatchSimulationService)
    calls = []

    def fake_apply(day_result, planning_day):
        calls.append((planning_day, day_result.label))
        return day_result.created, day_result.assigned

    service.apply = fake_apply
    result = MultiDayPlanningResult(start_day=date(2026, 7, 27), horizon_days=3)
    result.daily_results = {
        date(2026, 7, 29): SimpleNamespace(label="Tag 3", created=1, assigned=2),
        date(2026, 7, 27): SimpleNamespace(label="Tag 1", created=2, assigned=6),
        date(2026, 7, 28): SimpleNamespace(label="Tag 2", created=1, assigned=5),
    }

    created, assigned = service.apply_horizon(result)

    assert calls == [
        (date(2026, 7, 27), "Tag 1"),
        (date(2026, 7, 28), "Tag 2"),
        (date(2026, 7, 29), "Tag 3"),
    ]
    assert created == 4
    assert assigned == 13


def test_apply_reuses_existing_empty_vehicle_tour(monkeypatch):
    from datetime import date, datetime
    from types import SimpleNamespace
    from leipzigerflow.planner.engine import service as service_module
    from leipzigerflow.planner.engine.service import DispatchSimulationService

    planning_day = date(2026, 7, 28)
    empty_tour = SimpleNamespace(
        id=22,
        planning_locked=False,
        driver_id=99,
        planned_start_time=None,
        positions=[],
    )
    order = SimpleNamespace(id=501)

    class FakeSession:
        def get(self, model, object_id):
            return order if int(object_id) == 501 else None

    class FakeTourService:
        created = []

        def __init__(self, session):
            self.session = session

        def get(self, tour_id):
            return None

        def create(self, values):
            self.created.append(values)
            return SimpleNamespace(positions=[])

        def add_order(self, tour, transport_order):
            tour.positions.append(SimpleNamespace(transport_order_id=transport_order.id))
            return tour

    monkeypatch.setattr(service_module, "TourService", FakeTourService)
    service = DispatchSimulationService.__new__(DispatchSimulationService)
    service.session = FakeSession()
    service._find_reusable_empty_tour = lambda day, vehicle_id: empty_tour

    assignment = SimpleNamespace(order_id=501, loading_date=planning_day)
    proposal = SimpleNamespace(
        source_tour_id=None,
        vehicle_id=43,
        driver_id=7,
        planned_start_at=datetime(2026, 7, 28, 6, 30),
        assignments=[assignment],
    )
    result = SimpleNamespace(
        proposed_tours=[proposal],
        planning_strategy=SimpleNamespace(value="Mehrtag"),
    )

    created, assigned = service.apply(result, planning_day)

    assert created == 0
    assert assigned == 1
    assert empty_tour.driver_id == 7
    assert empty_tour.planned_start_time.hour == 6
    assert empty_tour.positions[0].transport_order_id == 501
    assert FakeTourService.created == []


def test_apply_merges_multiple_proposals_for_same_vehicle_and_day(monkeypatch):
    from datetime import date, datetime
    from types import SimpleNamespace
    from leipzigerflow.planner.engine import service as service_module
    from leipzigerflow.planner.engine.service import DispatchSimulationService

    planning_day = date(2026, 7, 28)
    empty_tour = SimpleNamespace(
        id=22,
        planning_locked=False,
        driver_id=7,
        planned_start_time=None,
        positions=[],
    )
    orders = {501: SimpleNamespace(id=501), 502: SimpleNamespace(id=502)}

    class FakeSession:
        def get(self, model, object_id):
            return orders.get(int(object_id))

    class FakeTourService:
        created = []

        def __init__(self, session):
            self.session = session

        def get(self, tour_id):
            return None

        def create(self, values):
            self.created.append(values)
            return SimpleNamespace(positions=[], planning_locked=False)

        def add_order(self, tour, transport_order):
            tour.positions.append(SimpleNamespace(transport_order_id=transport_order.id))
            return tour

    monkeypatch.setattr(service_module, "TourService", FakeTourService)
    service = DispatchSimulationService.__new__(DispatchSimulationService)
    service.session = FakeSession()
    reusable_calls = []

    def find_reusable(day, vehicle_id):
        reusable_calls.append((day, vehicle_id))
        return empty_tour

    service._find_reusable_empty_tour = find_reusable
    proposals = [
        SimpleNamespace(
            source_tour_id=None,
            vehicle_id=44,
            driver_id=7,
            planned_start_at=datetime(2026, 7, 28, 6, 0),
            assignments=[SimpleNamespace(order_id=501, loading_date=planning_day)],
        ),
        SimpleNamespace(
            source_tour_id=None,
            vehicle_id=44,
            driver_id=7,
            planned_start_at=datetime(2026, 7, 28, 10, 0),
            assignments=[SimpleNamespace(order_id=502, loading_date=planning_day)],
        ),
    ]
    result = SimpleNamespace(
        proposed_tours=proposals,
        planning_strategy=SimpleNamespace(value="Mehrtag"),
    )

    created, assigned = service.apply(result, planning_day)

    assert created == 0
    assert assigned == 2
    assert [p.transport_order_id for p in empty_tour.positions] == [501, 502]
    assert reusable_calls == [(planning_day, 44)]
    assert FakeTourService.created == []

def test_planning_engine_facade_builds_kpis():
    from datetime import datetime
    from leipzigerflow.planner.engine.facade import PlanningEngine
    from leipzigerflow.planner.engine.models import DispatchSimulationResult
    summary=PlanningEngine.evaluate(DispatchSimulationResult(created_at=datetime.now(),resources_total=2,orders_total=0))
    assert summary.assigned_orders==0 and summary.utilization_percent==0.0

def test_planning_engine_facade_replay_preserves_trace_order():
    from datetime import datetime
    from leipzigerflow.planner.engine.facade import PlanningEngine
    from leipzigerflow.planner.engine.models import DispatchSimulationResult,PlanningPhase,PlanningTraceEntry
    result=DispatchSimulationResult(created_at=datetime.now())
    result.planning_trace.extend([PlanningTraceEntry(1,PlanningPhase.DAY_ANALYSIS,'Start'),PlanningTraceEntry(2,PlanningPhase.COMPLETED,'Auswahl')])
    assert [s.message for s in PlanningEngine.replay(result).steps]==['Start','Auswahl']
